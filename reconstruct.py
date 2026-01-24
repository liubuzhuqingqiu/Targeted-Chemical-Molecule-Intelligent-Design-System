# 实现分子重建和评估功能，将模型输出转换为SMILES字符串并评估分子性质
# 核心功能包括：
# 1. 分子重建：将模型输出的logits转换为SMILES字符串
# 2. 价键约束：确保生成的分子在化学上有效，禁止违反化学规则的结构（如5价碳原子）
# 3. 性质评估：计算分子的QED（定量药物评估）和LogP（脂水分配系数）等性质

import torch
import os
from rdkit import Chem
from rdkit.Chem import ValenceType
from rdkit import RDLogger
from rdkit.Chem import QED, Descriptors
from model import MoleculeVAE
from config import MODEL_DIR, DEFAULT_MODEL_NAME, DEFAULT_HIDDEN_DIM, LATENT_DIM, DEFAULT_GENERATE_ATTEMPTS, DEFAULT_GENERATE_BATCH_SIZE, get_device


# 评估分子的物理化学性质
def evaluate_molecule(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol: return None

    try:
        qed_score = QED.qed(mol)
        logp_score = Descriptors.MolLogP(mol)
        mw_score = Descriptors.MolWt(mol)
        hbd = Descriptors.NumHDonors(mol)
        hba = Descriptors.NumHAcceptors(mol)

        return {
            "qed": round(qed_score, 3),
            "logp": round(logp_score, 3),
            "mw": round(mw_score, 2),
            "hbd": hbd,
            "hba": hba,
            "valid": "通过校验"
        }
    except:
        return None

RDLogger.DisableLog('rdApp.*')


# 将模型输出的logits转换为SMILES字符串
def logits_to_smiles(atom_logits, edge_logits):
    idx_to_atomic_num = {0: 6, 1: 7, 2: 8, 3: 9, 4: 16, 5: 17}
    atom_valency_limit = {6: 4, 7: 3, 8: 2, 9: 1, 16: 6, 17: 1}

    mol = Chem.RWMol()
    atom_types = torch.argmax(atom_logits, dim=-1)[0]

    added_atoms = []
    for i in range(atom_types.size(0)):
        atomic_num = idx_to_atomic_num.get(atom_types[i].item(), 6)
        atom_idx = mol.AddAtom(Chem.Atom(atomic_num))
        added_atoms.append(atom_idx)

    adj_matrix = torch.sigmoid(edge_logits[0])
    edges = []
    for i in range(len(added_atoms)):
        for j in range(i + 1, len(added_atoms)):
            edges.append((adj_matrix[i, j].item(), i, j))
    edges.sort(reverse=True)

    for prob, i, j in edges:
        if prob > 0.65:
            try:
                atom_i = mol.GetAtomWithIdx(i)
                atom_j = mol.GetAtomWithIdx(j)
                atom_i.UpdatePropertyCache(strict=False)
                atom_j.UpdatePropertyCache(strict=False)
                current_v_i = atom_i.GetValence(which=ValenceType.EXPLICIT)
                current_v_j = atom_j.GetValence(which=ValenceType.EXPLICIT)
                limit_i = atom_valency_limit.get(atom_i.GetAtomicNum(), 4)
                limit_j = atom_valency_limit.get(atom_j.GetAtomicNum(), 4)
                if current_v_i < limit_i and current_v_j < limit_j:
                    mol.AddBond(i, j, Chem.BondType.SINGLE)
            except:
                continue

    try:
        final_mol = mol.GetMol()
        Chem.SanitizeMol(final_mol)
        frags = Chem.GetMolFrags(final_mol, asMols=True)
        if not frags:
            return None
        res_mol = max(frags, key=lambda x: x.GetNumAtoms())
        return Chem.MolToSmiles(res_mol)
    except:
        return None


# 从潜在空间生成分子
def real_generate():
    device = get_device()
    print(f"正在使用设备: {device}")

    model = MoleculeVAE(hidden_channels=DEFAULT_HIDDEN_DIM, latent_dim=LATENT_DIM).to(device)

    try:
        default_model_path = os.path.join(MODEL_DIR, f"{DEFAULT_MODEL_NAME}.pth")
        model.load_state_dict(torch.load(default_model_path, map_location=device))
        print("✅ 已成功加载 VAE 模型权重。")
    except FileNotFoundError:
        print(f"⚠️ 未找到 {DEFAULT_MODEL_NAME}.pth，将使用随机初始化的模型进行演示。")

    model.eval()

    print("\n--- 正在从潜在空间进行批量采样生成 ---")

    success_count = 0
    max_attempts = DEFAULT_GENERATE_ATTEMPTS

    with torch.no_grad():
        for i in range(max_attempts):
            z = torch.randn(DEFAULT_GENERATE_BATCH_SIZE, LATENT_DIM).to(device)
            atom_logits = model.decoder_atoms(z).view(-1, 20, 10)
            edge_logits = model.decoder_edges(z).view(-1, 20, 20)
            res_smiles = logits_to_smiles(atom_logits, edge_logits)

            if res_smiles and len(res_smiles) > 1:
                print(f"🎉 尝试第 {i + 1} 次 - 成功生成分子: {res_smiles}")
                success_count += 1
            else:
                print(f"❌ 尝试第 {i + 1} 次 - 生成无效（化学规则拦截）")

    if success_count == 0:
        print("\n结论：本次采样未捕获到合法分子。")
        print("建议方案：1. 增加 train.py 的训练轮数；2. 增加数据集样本量。")
    else:
        print(f"\n生成结束，共获得 {success_count} 个合法分子。")


if __name__ == "__main__":
    real_generate()