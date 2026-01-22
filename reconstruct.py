import torch
from rdkit import Chem
from rdkit.Chem import ValenceType
from rdkit import RDLogger
from rdkit.Chem import QED, Descriptors


def evaluate_molecule(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol: return None

    try:
        # 计算文档要求的各项指标
        qed_score = QED.qed(mol)  # 类药性
        logp_score = Descriptors.MolLogP(mol)  # 脂水分配系数
        mw_score = Descriptors.MolWt(mol)  # 分子量
        hbd = Descriptors.NumHDonors(mol)  # 氢键供体
        hba = Descriptors.NumHAcceptors(mol)  # 氢键受体

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


def logits_to_smiles(atom_logits, edge_logits):
    # 1. 原子映射与最大价态限制
    idx_to_atomic_num = {0: 6, 1: 7, 2: 8, 3: 9, 4: 16, 5: 17}
    atom_valency_limit = {6: 4, 7: 3, 8: 2, 9: 1, 16: 6, 17: 1}

    mol = Chem.RWMol()
    # 预测原子类型 (取每个位置概率最大的原子)
    atom_types = torch.argmax(atom_logits, dim=-1)[0]

    added_atoms = []
    for i in range(atom_types.size(0)):
        atomic_num = idx_to_atomic_num.get(atom_types[i].item(), 6)
        atom_idx = mol.AddAtom(Chem.Atom(atomic_num))
        added_atoms.append(atom_idx)

    # 2. 预测边关系并按概率排序
    adj_matrix = torch.sigmoid(edge_logits[0])
    edges = []
    for i in range(len(added_atoms)):
        for j in range(i + 1, len(added_atoms)):
            edges.append((adj_matrix[i, j].item(), i, j))
    edges.sort(reverse=True)

    # 3. 按照化学规则连线
    for prob, i, j in edges:
        if prob > 0.65:  # 略微提高阈值，保证分子质量
            try:
                atom_i = mol.GetAtomWithIdx(i)
                atom_j = mol.GetAtomWithIdx(j)

                # 更新属性缓存，确保价态计算准确
                atom_i.UpdatePropertyCache(strict=False)
                atom_j.UpdatePropertyCache(strict=False)

                # 使用最新规范的 GetValence 方法，彻底消除警告
                current_v_i = atom_i.GetValence(which=ValenceType.EXPLICIT)
                current_v_j = atom_j.GetValence(which=ValenceType.EXPLICIT)

                limit_i = atom_valency_limit.get(atom_i.GetAtomicNum(), 4)
                limit_j = atom_valency_limit.get(atom_j.GetAtomicNum(), 4)

                # 只有在双方都有“空位”时才连线
                if current_v_i < limit_i and current_v_j < limit_j:
                    mol.AddBond(i, j, Chem.BondType.SINGLE)
            except:
                continue

                # 4. 后处理：提取合法分子
    try:
        final_mol = mol.GetMol()
        # 自动清洗分子（处理电荷、价态平衡等）
        Chem.SanitizeMol(final_mol)

        # 过滤掉碎片，只保留最大的连通体
        frags = Chem.GetMolFrags(final_mol, asMols=True)
        if not frags:
            return None
        res_mol = max(frags, key=lambda x: x.GetNumAtoms())

        return Chem.MolToSmiles(res_mol)
    except:
        return None