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

        # 简化生成流程：直接在潜空间中随机采样，再用 RDKit 真实性质做筛选
        with torch.no_grad():
            n_samples = sample_count
            latent_dim = getattr(model, "latent_dim", 32)

            generate_status["logs"].append("> 直接在潜在空间随机采样...")
            from atom_mapping import NUM_ATOM_TYPES

            for i in range(n_samples):
                generate_status["current_sample"] = i + 1
                if i % 50 == 0:
                    generate_status["logs"].append(f"> 处理样本 {i+1}/{n_samples}")

                # 从标准正态采样潜在向量，并限制范数，避免过远区域
                z = torch.randn(1, latent_dim, device=DEVICE)
                norm = torch.norm(z)
                if norm > 3.0:
                    z = z * (3.0 / norm)

                atom_logits = model.decoder_atoms(z).view(-1, model.max_nodes, NUM_ATOM_TYPES)
                edge_logits = model.decoder_edges(z).view(-1, model.max_nodes, model.max_nodes, 5)
                smiles_list = logits_to_smiles(atom_logits, edge_logits, strict=False)

                for smiles in smiles_list:
                    if not smiles:
                        continue
                    m = evaluate_molecule(smiles)
                    if not m:
                        continue

                    valid = True

                    # 依据前端/后端约束做最终筛选
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