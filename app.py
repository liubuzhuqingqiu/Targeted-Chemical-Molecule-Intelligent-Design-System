import os
import torch
import threading
import base64
from io import BytesIO
from flask import Flask, render_template, jsonify, request
from rdkit import Chem
from rdkit.Chem import Draw

from model import MoleculeVAE
from reconstruct import logits_to_smiles, evaluate_molecule
from train import train_custom_model
from config import BASE_DIR, MODEL_DIR, UPLOAD_DIR, get_device, MW_MIN, MW_MAX, LOGP_MIN, LOGP_MAX, HBD_MAX, HBA_MAX, ROT_BONDS_MAX, QED_MIN, SA_SCORE_MAX

app = Flask(__name__)
DEVICE = get_device()

def load_model(model_path, device):
    if not os.path.exists(model_path):
        return None
    
    try:
        checkpoint = torch.load(model_path, map_location=device)
        
        if 'state_dict' in checkpoint:
            max_nodes = checkpoint.get('max_nodes', 20)
            hidden_channels = checkpoint.get('hidden_channels', 64)
            
            model = MoleculeVAE(hidden_channels=hidden_channels, latent_dim=32, max_nodes=max_nodes).to(device)
            model.load_state_dict(checkpoint['state_dict'])
            print(f"✅ 成功加载模型: {os.path.basename(model_path)}")
            print(f"  - 隐藏维度: {hidden_channels}")
            print(f"  - 最大节点数: {max_nodes}")
            return model
        else:
            hidden_dims = [128, 64, 32, 256]
            max_nodes_list = [10, 20, 30, 40, 50]
            
            for dim in hidden_dims:
                for max_nodes in max_nodes_list:
                    try:
                        model = MoleculeVAE(hidden_channels=dim, latent_dim=32, max_nodes=max_nodes).to(device)
                        model.load_state_dict(checkpoint)
                        print(f"✅ 成功加载 {dim} 维度、{max_nodes} 最大节点数的模型: {os.path.basename(model_path)}")
                        return model
                    except Exception as e:
                        continue
    except Exception as e:
        print(f"加载模型时出错: {str(e)}")
    
    return None

training_status = {
    "status": "idle",
    "current_epoch": 0,
    "total_epochs": 0,
    "loss": 0.0,
    "logs": [],
    "lr": 0.0,
    "batch_size": 0
}

generate_status = {
    "status": "idle",
    "current_sample": 0,
    "total_samples": 0,
    "valid_molecules": [],
    "logs": [],
    "error": None
}

def mol_to_base64(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        img = Draw.MolToImage(mol, size=(400, 400))
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_models')
def get_models():
    models = [f for f in os.listdir(MODEL_DIR) if f.endswith('.pth')]
    return jsonify({"models": sorted(list(set(models)))})

@app.route('/get_train_status')
def get_status():
    return jsonify(training_status)

@app.route('/start_train', methods=['POST'])
def start_train():
    global training_status
    file = request.files['dataset']
    model_name = request.form.get('model_name', 'new_model')
    epochs = int(request.form.get('epochs', 10))
    hidden_dim = int(request.form.get('hidden_dim', 64))
    lr = float(request.form.get('lr', 0.001))
    batch_size = int(request.form.get('batch_size', 32))

    dataset_path = os.path.join(UPLOAD_DIR, f"{model_name}.smi")
    file.save(dataset_path)

    training_status.update({
        "status": "training",
        "current_epoch": 0,
        "total_epochs": epochs,
        "loss": 0.0,
        "logs": ["> 正在建立后台连接..."],
        "lr": lr,
        "batch_size": batch_size
    })

    thread = threading.Thread(
        target=train_custom_model,
        args=(dataset_path, model_name, MODEL_DIR, epochs, lr, batch_size, hidden_dim, training_status)
    )
    thread.start()
    return jsonify({"msg": "训练任务已成功启动"})

def generate_molecules_core(model_file, constraints, generate_status, sample_count=100):
    try:
        generate_status.update({
            "status": "generating",
            "current_sample": 0,
            "total_samples": sample_count,
            "valid_molecules": [],
            "logs": ["> 正在建立后台连接..."],
            "error": None
        })

        model_path = os.path.join(MODEL_DIR, model_file)

        if not os.path.exists(model_path):
            generate_status.update({
                "status": "error",
                "error": "找不到模型"
            })
            return 

        model = load_model(model_path, DEVICE)

        if model is None:
            generate_status.update({
                "status": "error",
                "error": "模型维度不匹配或文件损坏，无法加载"
            })
            return

        model.eval()

        best_mol = None
        best_score = -float('inf')
        valid_molecules = []

        def calculate_fitness(z, model, constraints, device):
            with torch.no_grad():
                n_ensemble = 5
                qed_preds = []
                logp_preds = []
                mw_preds = []
                hbd_preds = []
                hba_preds = []
                
                for _ in range(n_ensemble):
                    z_noisy = z + torch.randn_like(z) * 0.01
                    properties = model.predict_properties(z_noisy)
                    qed_preds.append(properties[0, 0].item())
                    logp_preds.append(properties[0, 1].item())
                    mw_preds.append(properties[0, 4].item())
                    hbd_preds.append(properties[0, 5].item())
                    hba_preds.append(properties[0, 6].item())
                
                qed_pred = sum(qed_preds) / n_ensemble
                logp_pred = sum(logp_preds) / n_ensemble
                mw_pred = sum(mw_preds) / n_ensemble
                hbd_pred = sum(hbd_preds) / n_ensemble
                hba_pred = sum(hba_preds) / n_ensemble
                
                fitness = 0.0
                qed_weight = constraints.get('qed_weight', 0.5 if 'qed_min' in constraints else 0.3)
                fitness += qed_weight * max(qed_pred, constraints.get('qed_min', 0.0))
                logp_weight = constraints.get('logp_weight', 0.3)
                fitness += logp_weight * max(0, 1 - abs(logp_pred - sum(constraints['logp_range'])/2) / (constraints['logp_range'][1] - constraints['logp_range'][0] + 1e-6))
                mw_weight = constraints.get('mw_weight', 0.2)
                fitness += mw_weight * max(0, 1 - abs(mw_pred - sum(constraints['mw_range'])/2) / (constraints['mw_range'][1] - constraints['mw_range'][0] + 1e-6))
                
                penalty = 0
                mw_center = sum(constraints['mw_range']) / 2
                mw_range = constraints['mw_range'][1] - constraints['mw_range'][0]
                penalty += 0.01 * ((mw_pred - mw_center) ** 2) / (mw_range ** 2) * max(0, abs(mw_pred - mw_center) - mw_range/2)
                
                logp_center = sum(constraints['logp_range']) / 2
                logp_range = constraints['logp_range'][1] - constraints['logp_range'][0]
                penalty += 0.1 * ((logp_pred - logp_center) ** 2) / (logp_range ** 2) * max(0, abs(logp_pred - logp_center) - logp_range/2)
                
                if 'hbd_range' in constraints:
                    hbd_center = sum(constraints['hbd_range']) / 2
                    hbd_range = constraints['hbd_range'][1] - constraints['hbd_range'][0]
                    penalty += 0.5 * ((hbd_pred - hbd_center) ** 2) / (hbd_range ** 2 + 1e-6)
                else:
                    penalty += 0.5 * max(0, hbd_pred - constraints.get('hbd_max', HBD_MAX))
                
                if 'hba_range' in constraints:
                    hba_center = sum(constraints['hba_range']) / 2
                    hba_range = constraints['hba_range'][1] - constraints['hba_range'][0]
                    penalty += 0.3 * ((hba_pred - hba_center) ** 2) / (hba_range ** 2 + 1e-6)
                else:
                    penalty += 0.3 * max(0, hba_pred - constraints.get('hba_max', HBA_MAX))
                
                if 'sa_score_max' in constraints:
                    sa_pred = properties[0, 2].item() if properties.shape[1] > 2 else 3.0
                    penalty += 1.0 * max(0, sa_pred - constraints['sa_score_max']) ** 2
                
                lambda_kl = 0.1
                kl_penalty = lambda_kl * (torch.norm(z) ** 2).item()
                penalty += kl_penalty
                
                from atom_mapping import NUM_ATOM_TYPES
                atom_logits = model.decoder_atoms(z).view(-1, model.max_nodes, NUM_ATOM_TYPES)
                edge_logits = model.decoder_edges(z).view(-1, model.max_nodes, model.max_nodes, 4)
                smiles_list = logits_to_smiles(atom_logits, edge_logits, strict=False)
                
                valid_smiles_generated = False
                for smiles in smiles_list:
                    if smiles:
                        m = evaluate_molecule(smiles)
                        if m:
                            valid_smiles_generated = True
                            break
                
                if not valid_smiles_generated:
                    penalty += 1.0
                
                final_fitness = fitness - penalty
                
                all_predictors_favorable = model.check_all_predictors_favorable(z, constraints)
                if not all_predictors_favorable:
                    final_fitness -= 1.0
                
                return final_fitness

        def pso_optimization(model, constraints, device, n_particles=20, n_iterations=50, latent_dim=32):
            particles = torch.randn(n_particles, latent_dim, device=device)
            velocities = torch.randn(n_particles, latent_dim, device=device) * 0.1
            
            personal_best_positions = particles.clone()
            personal_best_fitness = torch.full((n_particles,), -float('inf'), device=device)
            global_best_position = None
            global_best_fitness = -float('inf')
            
            w = 0.7
            c1 = 1.5
            c2 = 1.5
            
            for iteration in range(n_iterations):
                for i in range(n_particles):
                    z = particles[i].unsqueeze(0)
                    fitness = calculate_fitness(z, model, constraints, device)
                    
                    if fitness > personal_best_fitness[i]:
                        personal_best_fitness[i] = fitness
                        personal_best_positions[i] = particles[i].clone()
                    
                    if fitness > global_best_fitness:
                        global_best_fitness = fitness
                        global_best_position = particles[i].clone()
                
                r1 = torch.rand(n_particles, latent_dim, device=device)
                r2 = torch.rand(n_particles, latent_dim, device=device)
                
                velocities = w * velocities + \
                             c1 * r1 * (personal_best_positions - particles) + \
                             c2 * r2 * (global_best_position.unsqueeze(0) - particles)
                
                particles = particles + velocities
                
                with torch.no_grad():
                    for i in range(n_particles):
                        norm = torch.norm(particles[i])
                        if norm > 3.0:
                            particles[i] = particles[i] * (3.0 / norm)
            
            if global_best_position is None:
                global_best_position = particles[0]
            return global_best_position.unsqueeze(0)

        def cma_es_optimization(model, constraints, device, n_individuals=20, n_iterations=50, latent_dim=32):
            import numpy as np
            
            mean = np.zeros(latent_dim)
            sigma = 0.5
            
            C = np.eye(latent_dim)
            
            lambda_ = n_individuals
            mu = lambda_ // 2
            weights = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
            weights /= np.sum(weights)
            
            mueff = np.sum(weights) ** 2 / np.sum(weights ** 2)
            cc = (4 + mueff / latent_dim) / (latent_dim + 4 + 2 * mueff / latent_dim)
            cs = (mueff + 2) / (latent_dim + mueff + 5)
            c1 = 2 / ((latent_dim + 1.3) ** 2 + mueff)
            cmu = min(1 - c1, 2 * (mueff - 2 + 1 / mueff) / ((latent_dim + 2) ** 2 + mueff))
            damps = 1 + 2 * max(0, np.sqrt((mueff - 1) / (latent_dim + 1)) - 1) + cs
            
            pc = np.zeros(latent_dim)
            ps = np.zeros(latent_dim)
            
            best_fitness = -float('inf')
            best_solution = None
            
            for iteration in range(n_iterations):
                individuals = []
                fitnesses = []
                
                for _ in range(lambda_):
                    x = np.random.multivariate_normal(mean, sigma**2 * C)
                    z = torch.tensor(x, dtype=torch.float32, device=device).unsqueeze(0)
                    fitness = calculate_fitness(z, model, constraints, device)
                    
                    individuals.append(x)
                    fitnesses.append(fitness)
                    
                    if fitness > best_fitness:
                        best_fitness = fitness
                        best_solution = x
                
                sorted_indices = np.argsort(fitnesses)[::-1]
                sorted_individuals = [individuals[i] for i in sorted_indices]
                
                selected_individuals = sorted_individuals[:mu]
                
                old_mean = mean.copy()
                mean = np.sum([w * ind for w, ind in zip(weights, selected_individuals)], axis=0)
                
                ps = (1 - cs) * ps + np.sqrt(cs * (2 - cs) * mueff) * (mean - old_mean) / sigma
                
                artmp = [(ind - old_mean) / sigma for ind in selected_individuals]
                C = (1 - c1 - cmu) * C + c1 * (np.outer(pc, pc) if np.linalg.norm(pc) < np.sqrt(latent_dim + 2) else np.eye(latent_dim))
                C += cmu * np.sum([w * np.outer(a, a) for w, a in zip(weights, artmp)], axis=0)
                
                sigma *= np.exp((cs / damps) * (np.linalg.norm(ps) / np.sqrt(latent_dim) - 1))
                
                C = (C + C.T) / 2
                
                if np.linalg.norm(mean) > 3.0:
                    mean = mean * (3.0 / np.linalg.norm(mean))
            
            if best_solution is None:
                best_solution = mean
            return torch.tensor(best_solution, dtype=torch.float32, device=device).unsqueeze(0)

        generate_status["logs"].append("> 启动多算法优化...")
        generate_status["logs"].append("> 1. 运行PSO优化...")
        pso_result = pso_optimization(model, constraints, DEVICE)
        
        generate_status["logs"].append("> 2. 运行CMA-ES优化...")
        cma_es_result = cma_es_optimization(model, constraints, DEVICE)
        
        pso_fitness = calculate_fitness(pso_result, model, constraints, DEVICE)
        cma_es_fitness = calculate_fitness(cma_es_result, model, constraints, DEVICE)
        
        generate_status["logs"].append(f"> PSO适应度: {pso_fitness:.4f}")
        generate_status["logs"].append(f"> CMA-ES适应度: {cma_es_fitness:.4f}")
        
        if pso_fitness > cma_es_fitness:
            generate_status["logs"].append("> 选择PSO结果")
            best_z = pso_result
        else:
            generate_status["logs"].append("> 选择CMA-ES结果")
            best_z = cma_es_result

        with torch.no_grad():
            n_samples = sample_count
            noise = torch.randn(n_samples, 32, device=DEVICE) * 0.12
            z_samples = best_z.repeat(n_samples, 1) + noise
            
            for i in range(n_samples):
                norm = torch.norm(z_samples[i])
                if norm > 3.0:
                    z_samples[i] = z_samples[i] * (3.0 / norm)
            
            generate_status["logs"].append("> 开始解码样本...")
            from atom_mapping import NUM_ATOM_TYPES
            for i in range(n_samples):
                generate_status["current_sample"] = i + 1
                generate_status["logs"].append(f"> 处理样本 {i+1}/{n_samples}")
                
                z = z_samples[i].unsqueeze(0)
                atom_logits = model.decoder_atoms(z).view(-1, model.max_nodes, NUM_ATOM_TYPES)
                edge_logits = model.decoder_edges(z).view(-1, model.max_nodes, model.max_nodes, 4)
                smiles_list = logits_to_smiles(atom_logits, edge_logits, strict=False)
                
                for smiles in smiles_list:
                    if smiles:
                        m = evaluate_molecule(smiles)
                        if not m:
                            continue
                        
                        valid = True
                        
                        if m['mw'] < constraints['mw_range'][0] or m['mw'] > constraints['mw_range'][1]:
                            valid = False
                        if 'hbd_range' in constraints:
                            if m['hbd'] < constraints['hbd_range'][0] or m['hbd'] > constraints['hbd_range'][1]:
                                valid = False
                        else:
                            if m['hbd'] > constraints.get('hbd_max', HBD_MAX):
                                valid = False
                        if 'hba_range' in constraints:
                            if m['hba'] < constraints['hba_range'][0] or m['hba'] > constraints['hba_range'][1]:
                                valid = False
                        else:
                            if m['hba'] > constraints.get('hba_max', HBA_MAX):
                                valid = False
                        if m['logp'] < constraints['logp_range'][0] or m['logp'] > constraints['logp_range'][1]:
                            valid = False
                        
                        if 'rot_bonds_range' in constraints:
                            if m['rot_bonds'] < constraints['rot_bonds_range'][0] or m['rot_bonds'] > constraints['rot_bonds_range'][1]:
                                valid = False
                        else:
                            if m['rot_bonds'] > constraints.get('rot_bonds_max', ROT_BONDS_MAX):
                                valid = False
                        
                        if m['qed'] < constraints['qed_min']:
                            valid = False
                        
                        if m['sa_score'] > constraints['sa_score_max']:
                            valid = False
                        
                        if not valid:
                            continue
                        
                        score = 0.3 * m['qed'] + 0.2 * m['logp']
                        if m['lipinski_ro5_violations'] > 1:
                            score -= 0.2 * m['lipinski_ro5_violations']
                        if m['sa_score'] > constraints['sa_score_max']:
                            score -= 0.1 * (m['sa_score'] - constraints['sa_score_max'])
                        
                        mol_obj = {"smiles": smiles, "metrics": m, "image": mol_to_base64(smiles), "score": score}
                        valid_molecules.append(mol_obj)
                        
                        if score > best_score:
                            best_score = score
                            best_mol = mol_obj
                            generate_status["logs"].append(f"> 找到更好的分子，分数: {score}")

        generate_status.update({
            "status": "success",
            "valid_molecules": valid_molecules,
            "best_mol": best_mol
        })
        generate_status["logs"].append(f"> 生成过程完成，找到 {len(valid_molecules)} 个有效分子")

    except Exception as e:
        error_msg = f"生成分子时出错: {str(e)}"
        print(error_msg)
        generate_status.update({
            "status": "error",
            "error": error_msg
        })

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    model_file = data.get('model_file')
    sample_count = data.get('sample_count', 100)
    constraints = data.get('constraints', {
        'mw_range': [MW_MIN, MW_MAX],
        'logp_range': [LOGP_MIN, LOGP_MAX],
        'hbd_max': HBD_MAX,
        'hba_max': HBA_MAX,
        'rot_bonds_max': ROT_BONDS_MAX,
        'qed_min': QED_MIN,
        'sa_score_max': SA_SCORE_MAX
    })
    
    print("\n=== 前端传来的生成参数 ===")
    print(f"模型文件: {model_file}")
    print(f"样本数量: {sample_count}")
    print(f"约束参数: {constraints}")
    print("==========================\n")
    
    model_path = os.path.join(MODEL_DIR, model_file)

    if not os.path.exists(model_path):
        return jsonify({"error": "找不到模型"}), 404

    model = load_model(model_path, DEVICE)
    if model is None:
        return jsonify({"error": "模型维度不匹配或文件损坏，无法加载"}), 500
    
    thread = threading.Thread(
        target=generate_molecules_core,
        args=(model_file, constraints, generate_status, sample_count)
    )
    thread.start()
    
    return jsonify({"message": "分子生成任务已启动，请轮询状态获取结果"})

@app.route('/get_generate_status')
def get_generate_status():
    return jsonify(generate_status)

if __name__ == '__main__':
    app.run(debug=True, port=5000)