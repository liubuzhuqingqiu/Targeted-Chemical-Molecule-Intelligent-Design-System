import torch
from rdkit import Chem
from rdkit import RDLogger
from rdkit.Chem import QED, Descriptors
from rdkit.Chem import rdMolDescriptors
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit.Chem import DataStructs
from rdkit.Chem.AllChem import GetMorganFingerprintAsBitVect
from molecule_processor import calculate_sa_score
from config import IDX_TO_ATOM, ATOM_VALENCY_LIMIT, NUM_ATOM_TYPES


# ==================== 骨架工具 ====================

def get_murcko_scaffold_smiles(smiles):
    """
    提取分子的 Bemis-Murcko 骨架 SMILES（环系 + 连接键，去除侧链）。
    用于骨架跃迁与优化时判断生成分子是否与 Hit 保持相同核心骨架。
    """
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    try:
        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
        if scaffold is None or scaffold.GetNumAtoms() < 2:
            return None
        return Chem.MolToSmiles(scaffold, isomericSmiles=False)
    except Exception:
        return None


def scaffold_tanimoto_similarity(scaffold_smiles_a, scaffold_smiles_b, fp_radius=2, fp_bits=2048):
    """
    计算两个 Murcko 骨架 SMILES 的 Tanimoto 相似度（基于骨架分子的 Morgan 指纹）。
    用于骨架跃迁时放宽「同骨架」判定：相似度 >= 阈值即视为骨架一致（避免因 SMILES 规范化
    或解码细微差异导致完全匹配失败）。返回 0.0~1.0，任一骨架无效时返回 0.0。
    """
    if not scaffold_smiles_a or not scaffold_smiles_b:
        return 0.0
    try:
        mol_a = Chem.MolFromSmiles(scaffold_smiles_a)
        mol_b = Chem.MolFromSmiles(scaffold_smiles_b)
        if mol_a is None or mol_b is None:
            return 0.0
        fp_a = GetMorganFingerprintAsBitVect(mol_a, fp_radius, nBits=fp_bits)
        fp_b = GetMorganFingerprintAsBitVect(mol_b, fp_radius, nBits=fp_bits)
        return float(DataStructs.TanimotoSimilarity(fp_a, fp_b))
    except Exception:
        return 0.0


# ==================== ADMET 评估 ====================

def _esol_log_s(logp, mw, rot_bonds, mol):
    """
    ESOL 估计水溶性 log(S)，单位 mol/L。
    公式: log(S) = 0.16 - 0.63*clogP - 0.0062*MW + 0.066*RB - 0.74*AP
    AP=芳香重原子比例 (Delaney, J. Chem. Inf. Model., 2004)
    """
    try:
        heavy = mol.GetNumHeavyAtoms()
        if heavy == 0:
            return 0.0
        aromatic_heavy = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic() and a.GetAtomicNum() != 1)
        ap = aromatic_heavy / heavy
        log_s = 0.16 - 0.63 * logp - 0.0062 * mw + 0.066 * rot_bonds - 0.74 * ap
        return round(log_s, 3)
    except Exception:
        return None


def _permeability_label(tpsa, logp):
    """基于 TPSA 与 LogP 的渗透性倾向（口服吸收相关）。"""
    if tpsa <= 90 and 0 <= logp <= 5:
        return "高"
    if tpsa <= 140 and -1 <= logp <= 6:
        return "中"
    return "低"


def _bbb_potential(tpsa, logp, mw):
    """血脑屏障透过潜力（经验规则：TPSA 较小、LogP 适中时更易透过 BBB）。"""
    if mw > 500:
        return "不易"
    if tpsa < 90 and 1 <= logp <= 5:
        return "可能"
    if tpsa < 120 and 0 <= logp <= 6:
        return "一般"
    return "不易"


_RISK_SMARTS = [
    "[$([N+](=O)[O-])]",          # 硝基
    "[#7]-[#7]",                   # N-N 肼/偶氮
    "[NX3](=O)([#6])[#6]",        # 硝基另一写法
]
_RISK_NAMES = ["硝基", "肼/偶氮", "硝基(芳)"]


def _analyze_risk_substructures(mol):
    """统计分子中匹配的警示子结构，同时返回总数和各类摘要。"""
    total = 0
    parts = []
    try:
        for sma, name in zip(_RISK_SMARTS, _RISK_NAMES):
            pat = Chem.MolFromSmarts(sma)
            if pat is None:
                continue
            n = len(mol.GetSubstructMatches(pat))
            total += n
            parts.append(f"{name}:{n}")
    except Exception:
        return 0, "—"
    return total, ("，".join(parts) if parts else "无")


def _admet_predict(mol, logp, mw, tpsa, rot_bonds):
    """对单个分子计算 ADMET 相关指标（吸收、分布、毒性等）。"""
    result = {
        "log_solubility": None,
        "solubility_label": "—",
        "permeability": "—",
        "bbb_potential": "—",
        "mol_refractivity": None,
        "risk_substructure_count": 0,
        "risk_summary": "—",
    }
    if mol is None:
        return result
    try:
        log_s = _esol_log_s(logp, mw, rot_bonds, mol)
        result["log_solubility"] = log_s
        if log_s is not None:
            if log_s >= -4:
                result["solubility_label"] = "较好"
            elif log_s >= -6:
                result["solubility_label"] = "中等"
            else:
                result["solubility_label"] = "较差"
        result["permeability"] = _permeability_label(tpsa, logp)
        result["bbb_potential"] = _bbb_potential(tpsa, logp, mw)
        result["mol_refractivity"] = round(Descriptors.MolMR(mol), 2)
        risk_count, risk_summary = _analyze_risk_substructures(mol)
        result["risk_substructure_count"] = risk_count
        result["risk_summary"] = risk_summary
    except Exception:
        pass
    return result


# ==================== 分子评估 ====================

def evaluate_molecule(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol: return None

    try:
        qed_score = QED.qed(mol)
        logp_score = Descriptors.MolLogP(mol)
        mw_score = Descriptors.MolWt(mol)
        hbd = Descriptors.NumHDonors(mol)
        hba = Descriptors.NumHAcceptors(mol)
        rot_bonds = rdMolDescriptors.CalcNumRotatableBonds(mol)
        heavy_atom_count = mol.GetNumHeavyAtoms()
        ring_count = Descriptors.RingCount(mol)
        tpsa = rdMolDescriptors.CalcTPSA(mol)
        sa_score = calculate_sa_score(mol)

        lipinski_checks = {
            'mw': mw_score <= 500,
            'logp': logp_score <= 5,
            'hbd': hbd <= 5,
            'hba': hba <= 10
        }
        lipinski_ro5_violations = sum(1 for v in lipinski_checks.values() if not v)

        veber_checks = {
            'rot_bonds': rot_bonds <= 10,
            'tpsa': tpsa <= 140
        }
        veber_violations = sum(1 for v in veber_checks.values() if not v)

        admet = _admet_predict(mol, logp_score, mw_score, tpsa, rot_bonds)
        return {
            "qed": round(qed_score, 3),
            "logp": round(logp_score, 3),
            "mw": round(mw_score, 2),
            "hbd": hbd,
            "hba": hba,
            "rot_bonds": rot_bonds,
            "tpsa": round(tpsa, 2),
            "heavy_atom_count": heavy_atom_count,
            "ring_count": ring_count,
            "sa_score": round(sa_score, 3),
            "lipinski_ro5_violations": lipinski_ro5_violations,
            "lipinski_checks": lipinski_checks,
            "veber_violations": veber_violations,
            "veber_checks": veber_checks,
            "log_solubility": admet.get("log_solubility"),
            "solubility_label": admet.get("solubility_label", "—"),
            "permeability": admet.get("permeability", "—"),
            "bbb_potential": admet.get("bbb_potential", "—"),
            "mol_refractivity": admet.get("mol_refractivity"),
            "risk_substructure_count": admet.get("risk_substructure_count", 0),
            "risk_summary": admet.get("risk_summary", "—"),
        }
    except Exception:
        return None

RDLogger.DisableLog('rdApp.*')


# ==================== 解码器 ====================

MAX_DECODE_NODES = 30


def logits_to_smiles(atom_logits, edge_logits):
    batch_size = atom_logits.size(0)
    smiles_list = []
    model_max_nodes = atom_logits.size(1)
    max_actual_nodes = min(model_max_nodes, MAX_DECODE_NODES)

    for batch_idx in range(batch_size):
        mol = Chem.RWMol()

        atom_temperature = 0.8
        atom_probs = torch.softmax(atom_logits[batch_idx] / atom_temperature, dim=-1)
        atom_probs = atom_probs[:max_actual_nodes]
        atom_types = torch.multinomial(atom_probs, num_samples=1).squeeze(-1)

        added_atoms = []
        for i in range(atom_types.size(0)):
            atom_id = atom_types[i].item()
            if atom_id >= NUM_ATOM_TYPES:
                continue
            atomic_num = IDX_TO_ATOM.get(atom_id, None)
            if atomic_num is None:
                continue
            try:
                atom_idx = mol.AddAtom(Chem.Atom(atomic_num))
                added_atoms.append(atom_idx)
            except:
                continue
        
        if len(added_atoms) < 3 or len(added_atoms) > max_actual_nodes:
            smiles_list.append(None)
            continue

        edge_temperature = 0.6
        edge_probs = torch.softmax(edge_logits[batch_idx] / edge_temperature, dim=-1)
        n = edge_probs.shape[0]
        bond_types = torch.multinomial(edge_probs.view(-1, 5), num_samples=1).squeeze(-1).view(n, n)
        
        used_valency = [0] * len(added_atoms)
        
        for bond_order in [1, 4, 2, 3]:
            for i in range(len(added_atoms)):
                for j in range(i + 1, len(added_atoms)):
                    bond_type = bond_types[i, j].item()
                    
                    if bond_type != bond_order:
                        continue
                    
                    if bond_type == 4:
                        required_valence = 1
                    else:
                        required_valence = bond_type
                    
                    atomic_num_i = mol.GetAtomWithIdx(i).GetAtomicNum()
                    atomic_num_j = mol.GetAtomWithIdx(j).GetAtomicNum()
                    max_val_i = ATOM_VALENCY_LIMIT.get(atomic_num_i, 4)
                    max_val_j = ATOM_VALENCY_LIMIT.get(atomic_num_j, 4)
                    
                    if atomic_num_i in [8, 9]:
                        max_val_i = min(max_val_i, 2)
                    if atomic_num_j in [8, 9]:
                        max_val_j = min(max_val_j, 2)
                    
                    if (used_valency[i] + required_valence) > max_val_i or (used_valency[j] + required_valence) > max_val_j:
                        continue
                    
                    bond = None
                    if bond_type == 1:
                        bond = Chem.BondType.SINGLE
                    elif bond_type == 2:
                        bond = Chem.BondType.DOUBLE
                    elif bond_type == 3:
                        if atomic_num_i not in [6,7] or atomic_num_j not in [6,7]:
                            continue
                        bond = Chem.BondType.TRIPLE
                    elif bond_type == 4:
                        if atomic_num_i not in [6,7,8,16] or atomic_num_j not in [6,7,8,16]:
                            continue
                        bond = Chem.BondType.AROMATIC
                        mol.GetAtomWithIdx(i).SetIsAromatic(True)
                        mol.GetAtomWithIdx(j).SetIsAromatic(True)
                    else:
                        continue
                    
                    try:
                        mol.AddBond(i, j, bond)
                        used_valency[i] += required_valence
                        used_valency[j] += required_valence
                    except Exception:
                        continue
        
        if sum(used_valency) < len(added_atoms) - 1:
            for i in range(len(added_atoms) - 1):
                j = i + 1
                try:
                    mol.AddBond(i, j, Chem.BondType.SINGLE)
                except:
                    pass
        
        try:
            Chem.SanitizeMol(mol, 
                Chem.SANITIZE_FINDRADICALS |
                Chem.SANITIZE_CLEANUP |
                Chem.SANITIZE_PROPERTIES,
                catchErrors=True)
            
            frags = Chem.GetMolFrags(mol, asMols=True)
            if frags:
                res_mol = max(frags, key=lambda x: x.GetNumAtoms())
                if res_mol.GetNumAtoms() >= 3:
                    smiles = Chem.MolToSmiles(res_mol)
                    if len(smiles) > 0:
                        smiles_list.append(smiles)
                        continue
            smiles_list.append(None)
        except Exception as e:
            try:
                smiles = Chem.MolToSmiles(mol, isomericSmiles=False, kekuleSmiles=False)
                if len(smiles) > 0 and len(smiles) < 100:
                    if not any(c in smiles for c in ['%', ')', '('] * 10):
                        smiles_list.append(smiles)
                        continue
            except:
                pass
            smiles_list.append(None)
    
    return smiles_list
