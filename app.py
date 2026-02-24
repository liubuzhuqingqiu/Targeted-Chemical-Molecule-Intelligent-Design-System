import os
import torch
import threading
import base64
from io import BytesIO
from flask import Flask, render_template, jsonify, request
from rdkit import Chem
from rdkit.Chem import Draw, DataStructs
from rdkit.Chem.AllChem import GetMorganFingerprintAsBitVect

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
            latent_dim = checkpoint.get('latent_dim', 32)
            model = MoleculeVAE(hidden_channels=hidden_channels, latent_dim=latent_dim, max_nodes=max_nodes).to(device)
            model.load_state_dict(checkpoint['state_dict'])
            print(f"✅ 成功加载模型: {os.path.basename(model_path)}")
            print(f"  - 隐藏维度: {hidden_channels}, 潜在维度: {latent_dim}, 最大节点数: {max_nodes}")
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


def deduplicate_by_tanimoto(mol_list, threshold=0.85, fp_radius=2, fp_bits=2048):
    """
    基于 Tanimoto 相似度（Morgan 指纹）去重，保留多样性。
    先按 SMILES 去重，再对剩余分子若与已保留分子最大相似度 > threshold 则剔除。
    返回去重后的列表（保持顺序，保留首次出现的分子）。
    """
    if not mol_list:
        return []
    seen_smiles = set()
    kept = []
    kept_fps = []
    for mol_obj in mol_list:
        smiles = mol_obj.get("smiles") or ""
        if smiles in seen_smiles:
            continue
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue
        try:
            fp = GetMorganFingerprintAsBitVect(mol, fp_radius, nBits=fp_bits)
        except Exception:
            kept.append(mol_obj)
            kept_fps.append(None)
            seen_smiles.add(smiles)
            continue
        if not kept_fps:
            kept.append(mol_obj)
            kept_fps.append(fp)
            seen_smiles.add(smiles)
            continue
        max_sim = 0.0
        for k_fp in kept_fps:
            if k_fp is None:
                continue
            sim = DataStructs.TanimotoSimilarity(fp, k_fp)
            if sim > max_sim:
                max_sim = sim
        if max_sim <= threshold:
            kept.append(mol_obj)
            kept_fps.append(fp)
            seen_smiles.add(smiles)
    return kept

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
    if training_status.get('status') == 'training':
        return jsonify({"error": "已有训练任务进行中，请等待完成后再试"}), 400
    file = request.files['dataset']
    model_name = request.form.get('model_name', 'new_model')
    epochs = int(request.form.get('epochs', 10))
    hidden_dim = int(request.form.get('hidden_dim', 64))
    lr = float(request.form.get('lr', 0.001))
    batch_size = int(request.form.get('batch_size', 32))
    patience = int(request.form.get('patience', 10))
    validation_split = float(request.form.get('validation_split', 0.1))
    latent_dim = int(request.form.get('latent_dim', 32))

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
        args=(dataset_path, model_name, MODEL_DIR, epochs, lr, batch_size, hidden_dim, training_status, patience, validation_split, latent_dim)
    )
    thread.start()
    return jsonify({"msg": "训练任务已成功启动"})

def generate_molecules_core(model_file, constraints, generate_status, sample_count=100, decode_batch_size=8, tanimoto_threshold=0.85):
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
        n_decoded_ok = 0
        n_eval_ok = 0
        n_constraint_ok = 0
        fallback_mol = None   # 校验通过但未满足约束时，保留一个供参考
        fallback_score = -float('inf')

        # 简化生成流程：直接在潜空间中随机采样，再用 RDKit 真实性质做筛选
        with torch.no_grad():
            n_samples = sample_count
            latent_dim = getattr(model, "latent_dim", 32)

            generate_status["logs"].append(f"> 潜在空间随机采样（每轮 {decode_batch_size} 个 z，共 {n_samples} 轮）...")
            from atom_mapping import NUM_ATOM_TYPES

            for i in range(n_samples):
                generate_status["current_sample"] = i + 1
                if i % 100 == 0 and i > 0:
                    generate_status["logs"].append(f"> 已处理 {i}/{n_samples} 轮 | 解码成功: {n_decoded_ok} | 校验通过: {n_eval_ok} | 约束通过: {n_constraint_ok}")

                # 每轮采样 decode_batch_size 个 z，批量解码以提高有效分子产出
                z = torch.randn(decode_batch_size, latent_dim, device=DEVICE)
                norms = torch.norm(z, dim=1, keepdim=True).clamp(min=1e-6)
                scale = torch.where(norms > 3.0, 3.0 / norms, torch.where(norms < 0.5, 0.5 / norms, torch.ones_like(norms)))
                z = z * scale

                atom_logits = model.decoder_atoms(z).view(-1, model.max_nodes, NUM_ATOM_TYPES)
                edge_logits = model.decoder_edges(z).view(-1, model.max_nodes, model.max_nodes, 5)
                smiles_list = logits_to_smiles(atom_logits, edge_logits, strict=False)

                for smiles in smiles_list:
                    if not smiles:
                        continue
                    n_decoded_ok += 1
                    m = evaluate_molecule(smiles)
                    if not m:
                        continue
                    n_eval_ok += 1

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

                    score = 0.3 * m['qed'] + 0.2 * m['logp']
                    if m['lipinski_ro5_violations'] > 1:
                        score -= 0.2 * m['lipinski_ro5_violations']

                    if not valid:
                        if score > fallback_score:
                            fallback_score = score
                            fallback_mol = {"smiles": smiles, "metrics": m, "image": mol_to_base64(smiles), "score": score, "relaxed": True}
                        continue
                    n_constraint_ok += 1

                    mol_obj = {"smiles": smiles, "metrics": m, "image": mol_to_base64(smiles), "score": score}
                    valid_molecules.append(mol_obj)

                    if score > best_score:
                        best_score = score
                        best_mol = mol_obj
                        generate_status["logs"].append(f"> 找到更好的分子，分数: {score}")

        # 基于 Tanimoto 相似度去重，提升多样性
        before_dedup = len(valid_molecules)
        valid_molecules = deduplicate_by_tanimoto(valid_molecules, threshold=tanimoto_threshold)
        after_dedup = len(valid_molecules)
        if before_dedup > after_dedup:
            generate_status["logs"].append(f"> Tanimoto 去重: 保留 {after_dedup} 个（剔除 {before_dedup - after_dedup} 个相似分子，阈值 {tanimoto_threshold}）")
        best_mol = None
        if valid_molecules:
            best_mol = max(valid_molecules, key=lambda x: x.get("score", -float("inf")))
        elif fallback_mol is not None:
            valid_molecules = [fallback_mol]
            best_mol = fallback_mol
            generate_status["logs"].append("> 约束过严，当前无满足全部条件的分子；已展示 1 个「校验通过但未满足约束」的分子供参考，可据此放宽条件后再生成。")
        # 按分数降序排列，方便展示（分数 = 0.3*QED + 0.2*LogP - Lipinski 违规惩罚，越高越好）
        valid_molecules.sort(key=lambda x: x.get("score", -float("inf")), reverse=True)
        if valid_molecules:
            best_mol = valid_molecules[0]

        generate_status.update({
            "status": "success",
            "valid_molecules": valid_molecules,
            "best_mol": best_mol
        })
        generate_status["logs"].append(
            f"> 生成过程完成 | 解码成功: {n_decoded_ok} | 校验通过: {n_eval_ok} | 约束通过: {n_constraint_ok} | 最终保留: {len(valid_molecules)} 个"
        )
        if len(valid_molecules) == 0:
            if n_decoded_ok == 0:
                generate_status["logs"].append("> 建议：解码几乎无有效结构，请检查模型是否训练充分或尝试换用/重新训练模型。")
            elif n_eval_ok == 0:
                generate_status["logs"].append("> 建议：解码有结构但 RDKit 校验均未通过，多为化学价/成键异常，需加强模型训练。")
            else:
                generate_status["logs"].append("> 建议：放宽约束（如扩大分子量/LogP 范围、降低 QED 下限、提高 SA 上限）后再试。")

    except Exception as e:
        error_msg = f"生成分子时出错: {str(e)}"
        print(error_msg)
        generate_status.update({
            "status": "error",
            "error": error_msg
        })

# 生成接口使用的约束默认值，与前端滑块一致
DEFAULT_CONSTRAINTS = {
    'mw_range': [MW_MIN, MW_MAX],
    'logp_range': [LOGP_MIN, LOGP_MAX],
    'hbd_max': HBD_MAX,
    'hba_max': HBA_MAX,
    'rot_bonds_max': ROT_BONDS_MAX,
    'qed_min': QED_MIN,
    'sa_score_max': SA_SCORE_MAX,
}


@app.route('/generate', methods=['POST'])
def generate():
    if generate_status.get('status') == 'generating':
        return jsonify({"error": "已有生成任务进行中，请等待完成后再试"}), 400
    data = request.json
    model_file = data.get('model_file')
    sample_count = data.get('sample_count', 100)
    # 与默认约束合并，避免前端只传部分键时产生 KeyError
    constraints = dict(DEFAULT_CONSTRAINTS)
    constraints.update(data.get('constraints') or {})
    
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
    
    decode_batch_size = int(data.get('decode_batch_size', 8))
    tanimoto_threshold = float(data.get('tanimoto_threshold', 0.85))
    thread = threading.Thread(
        target=generate_molecules_core,
        args=(model_file, constraints, generate_status, sample_count, decode_batch_size, tanimoto_threshold)
    )
    thread.start()
    
    return jsonify({"message": "分子生成任务已启动，请轮询状态获取结果"})

@app.route('/get_generate_status')
def get_generate_status():
    return jsonify(generate_status)

if __name__ == '__main__':
    app.run(debug=True, port=5000)