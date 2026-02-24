# ADMET 评估模块：吸收、分布、毒性等预测（基于 RDKit，无额外依赖）
from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors


# ---------- 吸收 (Absorption) ----------

def esol_log_s(mol):
    """
    ESOL 估计水溶性 log(S)，单位 mol/L。
    公式: log(S) = 0.16 - 0.63*clogP - 0.0062*MW + 0.066*RB - 0.74*AP
    RB=可旋转键数, AP=芳香重原子比例 (Delaney, J. Chem. Inf. Model., 2004)
    """
    try:
        logp = Descriptors.MolLogP(mol)
        mw = Descriptors.MolWt(mol)
        rot_bonds = rdMolDescriptors.CalcNumRotatableBonds(mol)
        heavy = mol.GetNumHeavyAtoms()
        if heavy == 0:
            return 0.0
        aromatic_heavy = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic() and a.GetAtomicNum() != 1)
        ap = aromatic_heavy / heavy
        log_s = 0.16 - 0.63 * logp - 0.0062 * mw + 0.066 * rot_bonds - 0.74 * ap
        return round(log_s, 3)
    except Exception:
        return None


def permeability_label(mol):
    """
    基于 TPSA 与 LogP 的渗透性倾向（口服吸收相关）。
    规则参考：TPSA > 140 或 LogP 极端时渗透性差。
    """
    try:
        tpsa = rdMolDescriptors.CalcTPSA(mol)
        logp = Descriptors.MolLogP(mol)
        if tpsa <= 90 and 0 <= logp <= 5:
            return "高"
        if tpsa <= 140 and -1 <= logp <= 6:
            return "中"
        return "低"
    except Exception:
        return "—"


# ---------- 分布 (Distribution) ----------

def bbb_potential(mol):
    """
    血脑屏障透过潜力（经验规则：TPSA 较小、LogP 适中时更易透过 BBB）。
    """
    try:
        tpsa = rdMolDescriptors.CalcTPSA(mol)
        logp = Descriptors.MolLogP(mol)
        mw = Descriptors.MolWt(mol)
        if mw > 500:
            return "不易"
        if tpsa < 90 and 1 <= logp <= 5:
            return "可能"
        if tpsa < 120 and 0 <= logp <= 6:
            return "一般"
        return "不易"
    except Exception:
        return "—"


def mol_refractivity(mol):
    """分子折射率 MR，与极性、体积相关，常用于 ADMET 经验式。"""
    try:
        return round(Descriptors.MolMR(mol), 2)
    except Exception:
        return None


# ---------- 毒性参考（警示子结构） ----------

# 潜在毒性/警示子结构 SMARTS（常见 PAINS/警示结构子集，仅作参考）
RISK_SMARTS = [
    "[NX3](=[OX1])([#6])[#6]",   # 硝基类
    "[NX3H2]",                     # 伯胺（可扩展为更严格规则）
    "[$([N+](=O)[O-])]",          # 硝基 N+O-
    "[S](=O)(=O)([#6])[#6]",      # 磺酰基
    "[#7]-[#7]",                   # 肼/偶氮类
    "[CX3](=O)[NX3]",             # 酰胺（一般不危险，可选）
]
# 仅保留明显警示：硝基、肼类（用于计数与分类展示）
RISK_SMARTS_STRICT = [
    "[$([N+](=O)[O-])]",          # 硝基
    "[#7]-[#7]",                   # N-N 肼/偶氮
    "[NX3](=O)([#6])[#6]",        # 硝基另一写法
]
RISK_NAMES = ["硝基", "肼/偶氮", "硝基(芳)"]


def count_risk_substructures(mol, strict=True):
    """统计分子中匹配的警示子结构数量（用于 ADMET 毒性参考）。"""
    patterns = RISK_SMARTS_STRICT if strict else RISK_SMARTS
    count = 0
    try:
        for sma in patterns:
            pat = Chem.MolFromSmarts(sma)
            if pat is None:
                continue
            count += len(mol.GetSubstructMatches(pat))
    except Exception:
        pass
    return count


def risk_substructure_summary(mol):
    """返回各类警示子结构的数量摘要，如 '硝基:0, 肼/偶氮:0'。"""
    try:
        parts = []
        for sma, name in zip(RISK_SMARTS_STRICT, RISK_NAMES):
            pat = Chem.MolFromSmarts(sma)
            if pat is None:
                continue
            n = len(mol.GetSubstructMatches(pat))
            parts.append(f"{name}:{n}")
        return "，".join(parts) if parts else "无"
    except Exception:
        return "—"


def admet_predict(mol):
    """
    对单个分子计算 ADMET 相关指标（吸收、分布、毒性等）。
    返回 dict 包含：溶解度、渗透性、BBB、分子折射率、警示子结构等。
    """
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
        log_s = esol_log_s(mol)
        result["log_solubility"] = log_s
        if log_s is not None:
            if log_s >= -4:
                result["solubility_label"] = "较好"
            elif log_s >= -6:
                result["solubility_label"] = "中等"
            else:
                result["solubility_label"] = "较差"
        result["permeability"] = permeability_label(mol)
        result["bbb_potential"] = bbb_potential(mol)
        result["mol_refractivity"] = mol_refractivity(mol)
        result["risk_substructure_count"] = count_risk_substructures(mol)
        result["risk_summary"] = risk_substructure_summary(mol)
    except Exception:
        pass
    return result
