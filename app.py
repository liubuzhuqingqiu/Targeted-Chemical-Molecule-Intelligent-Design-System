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
from reconstruct import logits_to_smiles, evaluate_molecule, get_murcko_scaffold_smiles, scaffold_tanimoto_similarity
from train import train_custom_model
from molecule_processor import smiles_to_graph
from config import (
    MODEL_DIR, UPLOAD_DIR, get_device,
    MW_MIN, MW_MAX, LOGP_MIN, LOGP_MAX, HBD_MAX, HBA_MAX, ROT_BONDS_MAX, QED_MIN, SA_SCORE_MAX,
    NUM_ATOM_TYPES,
)

# 模型属性预测头的输出索引 → 前端/API 属性名的映射
_PROP_PRED_IDX = {
    'qed': 0, 'logp': 1, 'mw': 4, 'hbd': 5, 'hba': 6,
    'rot_bonds': 7, 'tpsa': 8, 'sa_score': 9,
}

app = Flask(__name__)
DEVICE = get_device()


def _in_constraint(value, constraints, range_key, max_key, default_max):
    """检查值是否在约束范围内（兼容 range 和 max 两种格式）。"""
    if range_key in constraints:
        return constraints[range_key][0] <= value <= constraints[range_key][1]
    return value <= constraints.get(max_key, default_max)


def _sort_by_target(results, direction):
    """按目标性质值排序（max=降序，min=升序），None 值排最后。"""
    if direction == "max":
        results.sort(key=lambda x: x.get("target_value") if x.get("target_value") is not None else -float("inf"), reverse=True)
    else:
        results.sort(key=lambda x: x.get("target_value") if x.get("target_value") is not None else float("inf"))

def load_model(model_path, device):
    if not os.path.exists(model_path):
        return None
    try:
        checkpoint = torch.load(model_path, map_location=device)
        max_nodes = checkpoint.get('max_nodes', 20)
        hidden_channels = checkpoint.get('hidden_channels', 64)
        latent_dim = checkpoint.get('latent_dim', 32)
        model = MoleculeVAE(hidden_channels=hidden_channels, latent_dim=latent_dim, max_nodes=max_nodes).to(device)
        model.load_state_dict(checkpoint['state_dict'])
        print(f"✅ 成功加载模型: {os.path.basename(model_path)} (hidden={hidden_channels}, latent={latent_dim}, max_nodes={max_nodes})")
        return model
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

scaffold_optimize_status = {
    "status": "idle",
    "current_sample": 0,
    "total_samples": 0,
    "derivatives": [],
    "hit_smiles": None,
    "hit_scaffold": None,
    "target_property": None,
    "logs": [],
    "error": None
}


def _latent_scaffold_optimize(model, hit_smiles, target_property, optimize_direction,
                              max_results=80, num_perturbations=192,
                              scaffold_sim_threshold=0.55):
    """
    潜在空间骨架优化（轻量版）：Hit 编码→微扰→解码→骨架过滤。
    采样规模缩小，快速完成，主要依赖阶段二规则补充。
    """
    from torch_geometric.data import Batch

    device = next(model.parameters()).device
    model.eval()

    graph = smiles_to_graph(hit_smiles)
    if graph is None:
        return []

    batch_data = Batch.from_data_list([graph]).to(device)
    with torch.no_grad():
        mu, logvar = model.encode(batch_data.x, batch_data.edge_index, batch_data.batch)
    z_hit = mu

    hit_scaffold = get_murcko_scaffold_smiles(hit_smiles)
    if not hit_scaffold:
        return []

    latent_dim = z_hit.shape[1]
    z_parts = []
    for scale in [0.08, 0.15, 0.25]:
        n = num_perturbations // 3
        noise = torch.randn(n, latent_dim, device=device) * scale
        z_parts.append(z_hit.expand(n, -1) + noise)
    z_candidates = torch.cat(z_parts, dim=0)

    prop_idx = _PROP_PRED_IDX.get(target_property)
    if prop_idx is not None:
        with torch.no_grad():
            preds = model.predict_properties(z_candidates)
        scores = preds[:, prop_idx]
        if optimize_direction == 'min':
            scores = -scores
        top_k = min(96, z_candidates.shape[0])
        top_indices = torch.topk(scores, k=top_k).indices
        z_candidates = z_candidates[top_indices]

    results = []
    seen = set()
    decode_bs = 32

    with torch.no_grad():
        for start in range(0, z_candidates.shape[0], decode_bs):
            z_batch = z_candidates[start:start + decode_bs]
            atom_logits = model.decoder_atoms(z_batch).view(-1, model.max_nodes, NUM_ATOM_TYPES)
            edge_logits = model.decoder_edges(z_batch).view(-1, model.max_nodes, model.max_nodes, 5)
            smiles_list = logits_to_smiles(atom_logits, edge_logits)

            for smi in smiles_list:
                if not smi or smi == hit_smiles or smi in seen:
                    continue
                gen_scaffold = get_murcko_scaffold_smiles(smi)
                if not gen_scaffold:
                    continue
                scaf_sim = scaffold_tanimoto_similarity(hit_scaffold, gen_scaffold)
                if scaf_sim < scaffold_sim_threshold:
                    continue
                m = evaluate_molecule(smi)
                if not m:
                    continue
                results.append({
                    "smiles": smi,
                    "metrics": m,
                    "image": mol_to_base64(smi),
                    "target_value": m.get(target_property),
                    "scaffold_similarity": round(scaf_sim, 4),
                    "method": "latent_perturbation",
                })
                seen.add(smi)
                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break

    _sort_by_target(results, optimize_direction)
    return results


def _generate_scaffold_constrained_derivatives(hit_smiles, target_property, optimize_direction, max_results=80):
    """
    规则侧链替换（补充方法）：固定 Hit 的 Murcko 骨架，通过替换末端原子/扩展侧链生成衍生物。
    """
    hit_mol = Chem.MolFromSmiles(hit_smiles)
    if hit_mol is None:
        return []

    hit_scaffold = get_murcko_scaffold_smiles(hit_smiles)
    if not hit_scaffold:
        return []
    scaffold_mol = Chem.MolFromSmiles(hit_scaffold)
    if scaffold_mol is None:
        return []
    scaffold_match = hit_mol.GetSubstructMatch(scaffold_mol)
    scaffold_atom_set = set(scaffold_match) if scaffold_match else set()

    # 仅在“非骨架且末端”的侧链原子上做替换，保证骨架不动
    side_terminal_atoms = []
    for atom in hit_mol.GetAtoms():
        idx = atom.GetIdx()
        if idx in scaffold_atom_set:
            continue
        if atom.GetDegree() != 1:
            continue
        nbr = atom.GetNeighbors()[0]
        bond = hit_mol.GetBondBetweenAtoms(idx, nbr.GetIdx())
        if bond is None or bond.GetBondType() != Chem.BondType.SINGLE:
            continue
        side_terminal_atoms.append(idx)

    if not side_terminal_atoms:
        return []

    allowed_atomic_nums = [6, 7, 8, 9, 16, 17]
    results = []
    seen = set()

    # 策略 A：末端原子类型替换（最稳健，成功率高）
    for atom_idx in side_terminal_atoms:
        origin_z = hit_mol.GetAtomWithIdx(atom_idx).GetAtomicNum()
        for new_z in allowed_atomic_nums:
            if new_z == origin_z:
                continue
            rw = Chem.RWMol(hit_mol)
            try:
                rw.GetAtomWithIdx(atom_idx).SetAtomicNum(new_z)
                m_new = rw.GetMol()
                Chem.SanitizeMol(m_new)
                smi = Chem.MolToSmiles(m_new, isomericSmiles=False)
            except Exception:
                continue
            if not smi or smi == hit_smiles or smi in seen:
                continue
            m = evaluate_molecule(smi)
            if not m:
                continue
            gen_scaffold = get_murcko_scaffold_smiles(smi)
            if not gen_scaffold:
                continue
            scaf_sim = scaffold_tanimoto_similarity(hit_scaffold, gen_scaffold)
            if scaf_sim < 0.95:
                continue
            results.append({
                "smiles": smi,
                "metrics": m,
                "image": mol_to_base64(smi),
                "target_value": m.get(target_property),
                "scaffold_similarity": round(scaf_sim, 4),
                "method": "terminal_atom_mutation",
            })
            seen.add(smi)
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break

    # 策略 B：在末端侧链继续加一个碳（轻度扩展）
    if len(results) < max_results:
        for atom_idx in side_terminal_atoms:
            rw = Chem.RWMol(hit_mol)
            try:
                new_idx = rw.AddAtom(Chem.Atom(6))
                rw.AddBond(atom_idx, new_idx, Chem.BondType.SINGLE)
                m_new = rw.GetMol()
                Chem.SanitizeMol(m_new)
                smi = Chem.MolToSmiles(m_new, isomericSmiles=False)
            except Exception:
                continue
            if not smi or smi == hit_smiles or smi in seen:
                continue
            m = evaluate_molecule(smi)
            if not m:
                continue
            gen_scaffold = get_murcko_scaffold_smiles(smi)
            if not gen_scaffold:
                continue
            scaf_sim = scaffold_tanimoto_similarity(hit_scaffold, gen_scaffold)
            if scaf_sim < 0.95:
                continue
            results.append({
                "smiles": smi,
                "metrics": m,
                "image": mol_to_base64(smi),
                "target_value": m.get(target_property),
                "scaffold_similarity": round(scaf_sim, 4),
                "method": "terminal_extension",
            })
            seen.add(smi)
            if len(results) >= max_results:
                break

    _sort_by_target(results, optimize_direction)
    return results


def scaffold_optimize_core(hit_smiles, target_property, optimize_direction, num_candidates,
                          scaffold_optimize_status, model_file=None, tanimoto_threshold=0.85):
    """
    骨架跃迁与优化：
      阶段一（主方法）：用 VAE 潜在空间微扰生成衍生物
      阶段二（补充）：规则侧链替换补充更多候选
      最终合并去重，按目标性质排序。
    """
    try:
        scaffold_optimize_status.update({
            "status": "optimizing",
            "current_sample": 0,
            "total_samples": num_candidates,
            "derivatives": [],
            "hit_smiles": hit_smiles,
            "hit_scaffold": None,
            "target_property": target_property,
            "logs": ["> 正在进行骨架跃迁与优化..."],
            "error": None
        })
        hit_scaffold = get_murcko_scaffold_smiles(hit_smiles)
        hit_image = mol_to_base64(hit_smiles)
        hit_metrics = evaluate_molecule(hit_smiles)
        scaffold_optimize_status["hit_scaffold"] = hit_scaffold
        scaffold_optimize_status["hit_image"] = hit_image

        all_candidates = []

        # 阶段一：潜在空间微扰（核心方法，对应毕设"微调潜在向量"）
        if model_file:
            model_path = os.path.join(MODEL_DIR, model_file)
            model = load_model(model_path, DEVICE)
            if model is not None:
                scaffold_optimize_status["logs"].append(
                    f"> 阶段一（轻量）：Hit 编码→微扰→解码（模型: {model_file}）..."
                )
                latent_candidates = _latent_scaffold_optimize(
                    model, hit_smiles, target_property, optimize_direction,
                    max_results=max(80, num_candidates),
                )
                all_candidates.extend(latent_candidates)
                scaffold_optimize_status["logs"].append(
                    f"> 潜在空间微扰生成 {len(latent_candidates)} 个同骨架衍生物"
                )
            else:
                scaffold_optimize_status["logs"].append("> 模型加载失败，跳过潜在空间方法")
        else:
            scaffold_optimize_status["logs"].append("> 未选择模型，跳过潜在空间微扰阶段")

        # 阶段二：规则侧链替换（补充更多候选）
        scaffold_optimize_status["logs"].append("> 阶段二：规则侧链替换补充衍生物...")
        rule_candidates = _generate_scaffold_constrained_derivatives(
            hit_smiles=hit_smiles,
            target_property=target_property,
            optimize_direction=optimize_direction,
            max_results=max(80, num_candidates),
        )
        all_candidates.extend(rule_candidates)
        scaffold_optimize_status["logs"].append(
            f"> 规则方法生成 {len(rule_candidates)} 个同骨架衍生物"
        )

        # 合并去重
        if all_candidates:
            all_candidates = deduplicate_by_tanimoto(all_candidates, threshold=tanimoto_threshold)
            _sort_by_target(all_candidates, optimize_direction)
            final_log = f"> 合并去重后共 {len(all_candidates)} 个衍生物，按「{target_property}」({optimize_direction}) 排序，展示前 {min(len(all_candidates), 50)} 个。"
        else:
            final_log = "> 未找到可用衍生物，请更换 Hit 或目标性质后重试。"

        scaffold_optimize_status.update({
            "status": "success",
            "derivatives": all_candidates[:50],
            "hit_smiles": hit_smiles,
            "hit_image": hit_image,
            "hit_metrics": hit_metrics,
            "hit_scaffold": hit_scaffold,
            "logs": scaffold_optimize_status["logs"] + [final_log]
        })
    except Exception as e:
        scaffold_optimize_status.update({
            "status": "error",
            "error": str(e)
        })


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


def select_guided_latents(model, constraints, decode_batch_size, latent_dim, device, pool_factor=8):
    """
    轻量“性质引导采样”：
    - 先在潜在空间随机采样一批 z
    - 用模型性质预测头对 z 打分
    - 选择更符合用户约束/目标的 top-k z 进行解码
    这能在不改训练流程的前提下，提升有效分子命中率。
    """
    pool_size = max(decode_batch_size * pool_factor, decode_batch_size)
    z_pool = torch.randn(pool_size, latent_dim, device=device)
    norms = torch.norm(z_pool, dim=1, keepdim=True).clamp(min=1e-6)
    scale = torch.where(
        norms > 3.0,
        3.0 / norms,
        torch.where(norms < 0.5, 0.5 / norms, torch.ones_like(norms))
    )
    z_pool = z_pool * scale

    try:
        preds = model.predict_properties(z_pool)  # [pool_size, num_properties]
    except Exception:
        return z_pool[:decode_batch_size], False

    # 预测头索引定义见训练标签：
    # 0:QED, 1:logP, 4:MW, 5:HBD, 6:HBA
    qed_pred = preds[:, 0]
    logp_pred = preds[:, 1]
    mw_pred = preds[:, 4]
    hbd_pred = preds[:, 5]
    hba_pred = preds[:, 6]

    logp_mid = (constraints['logp_range'][0] + constraints['logp_range'][1]) / 2.0
    mw_min, mw_max = constraints['mw_range'][0], constraints['mw_range'][1]
    hbd_max = constraints['hbd_range'][1] if 'hbd_range' in constraints else constraints.get('hbd_max', HBD_MAX)
    hba_max = constraints['hba_range'][1] if 'hba_range' in constraints else constraints.get('hba_max', HBA_MAX)
    qed_min = constraints.get('qed_min', QED_MIN)

    # 分数越高越优：偏好高QED、LogP靠近目标范围中心，同时惩罚明显越界
    score = 1.8 * qed_pred - 0.25 * torch.abs(logp_pred - logp_mid)
    score -= 0.004 * torch.clamp(mw_pred - mw_max, min=0)
    score -= 0.004 * torch.clamp(mw_min - mw_pred, min=0)
    score -= 0.20 * torch.clamp(hbd_pred - hbd_max, min=0)
    score -= 0.15 * torch.clamp(hba_pred - hba_max, min=0)
    score += 0.80 * torch.clamp(qed_pred - qed_min, min=0)

    top_k = min(decode_batch_size, pool_size)
    top_idx = torch.topk(score, k=top_k, dim=0).indices
    return z_pool[top_idx], True

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

def generate_molecules_core(model_file, constraints, generate_status, sample_count=100, decode_batch_size=4, tanimoto_threshold=0.90):
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
        final_has_fallback = False
        n_decoded_ok = 0
        n_eval_ok = 0
        n_constraint_ok = 0
        fallback_mol = None   # 校验通过但未满足约束时，保留一个供参考
        fallback_score = -float('inf')

        # 简化生成流程：直接在潜空间中随机采样，再用 RDKit 真实性质做筛选
        with torch.no_grad():
            n_samples = sample_count
            latent_dim = getattr(model, "latent_dim", 32)

            generate_status["logs"].append(f"> 潜在空间引导采样（每轮 {decode_batch_size} 个 z，共 {n_samples} 轮）...")
            guided_ok_count = 0

            for i in range(n_samples):
                generate_status["current_sample"] = i + 1
                if i % 100 == 0 and i > 0:
                    generate_status["logs"].append(f"> 已处理 {i}/{n_samples} 轮 | 解码成功: {n_decoded_ok} | 校验通过: {n_eval_ok} | 约束通过: {n_constraint_ok}")

                # 每轮先采样更大的 z 池，再用性质预测头挑选更可能满足目标的 z
                z, guided_used = select_guided_latents(
                    model=model,
                    constraints=constraints,
                    decode_batch_size=decode_batch_size,
                    latent_dim=latent_dim,
                    device=DEVICE,
                    pool_factor=8,
                )
                if guided_used:
                    guided_ok_count += 1

                atom_logits = model.decoder_atoms(z).view(-1, model.max_nodes, NUM_ATOM_TYPES)
                edge_logits = model.decoder_edges(z).view(-1, model.max_nodes, model.max_nodes, 5)
                smiles_list = logits_to_smiles(atom_logits, edge_logits)

                for smiles in smiles_list:
                    if not smiles:
                        continue
                    n_decoded_ok += 1
                    m = evaluate_molecule(smiles)
                    if not m:
                        continue
                    n_eval_ok += 1

                    valid = (
                        constraints['mw_range'][0] <= m['mw'] <= constraints['mw_range'][1]
                        and constraints['logp_range'][0] <= m['logp'] <= constraints['logp_range'][1]
                        and _in_constraint(m['hbd'], constraints, 'hbd_range', 'hbd_max', HBD_MAX)
                        and _in_constraint(m['hba'], constraints, 'hba_range', 'hba_max', HBA_MAX)
                        and _in_constraint(m['rot_bonds'], constraints, 'rot_bonds_range', 'rot_bonds_max', ROT_BONDS_MAX)
                        and m['qed'] >= constraints['qed_min']
                        and m['sa_score'] <= constraints['sa_score_max']
                    )

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
            final_has_fallback = True
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
        generate_status["logs"].append(f"> 引导采样生效轮次: {guided_ok_count}/{n_samples}")
        if final_has_fallback:
            generate_status["logs"].append("> 注：最终保留数量包含 1 个参考分子（未满足全部约束）。")
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
    
    model_path = os.path.join(MODEL_DIR, model_file)
    if not os.path.exists(model_path):
        return jsonify({"error": "找不到模型"}), 404

    decode_batch_size = int(data.get('decode_batch_size', 4))
    tanimoto_threshold = float(data.get('tanimoto_threshold', 0.90))
    thread = threading.Thread(
        target=generate_molecules_core,
        args=(model_file, constraints, generate_status, sample_count, decode_batch_size, tanimoto_threshold)
    )
    thread.start()
    
    return jsonify({"message": "分子生成任务已启动，请轮询状态获取结果"})

@app.route('/get_generate_status')
def get_generate_status():
    return jsonify(generate_status)


@app.route('/scaffold_optimize', methods=['POST'])
def scaffold_optimize():
    if scaffold_optimize_status.get('status') == 'optimizing':
        return jsonify({"error": "已有骨架优化任务进行中，请等待完成后再试"}), 400
    data = request.json or {}
    hit_smiles = (data.get('hit_smiles') or '').strip()
    if not hit_smiles:
        return jsonify({"error": "请提供苗头化合物 SMILES"}), 400
    target_property = data.get('target_property', 'log_solubility')
    optimize_direction = data.get('optimize_direction', 'max')
    num_candidates = int(data.get('num_candidates', 100))
    tanimoto_threshold = float(data.get('tanimoto_threshold', 0.85))
    model_file = (data.get('model_file') or '').strip() or None

    scaffold_optimize_status.update({
        "status": "optimizing",
        "derivatives": [],
        "logs": [],
        "error": None
    })
    thread = threading.Thread(
        target=scaffold_optimize_core,
        args=(hit_smiles, target_property, optimize_direction, num_candidates,
              scaffold_optimize_status, model_file, tanimoto_threshold)
    )
    thread.start()
    return jsonify({"message": "骨架跃迁与优化任务已启动，请轮询状态获取结果"})


@app.route('/get_scaffold_optimize_status')
def get_scaffold_optimize_status():
    return jsonify(scaffold_optimize_status)


if __name__ == '__main__':
    app.run(debug=True, port=5000)