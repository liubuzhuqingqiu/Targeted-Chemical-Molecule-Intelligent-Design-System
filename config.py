import os
import torch

# ==================== 路径配置 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
UPLOAD_DIR = os.path.join(BASE_DIR, "datasets")

# ==================== 原子类型映射 ====================
ATOM_TO_IDX = {
    6: 0,    # C
    7: 1,    # N
    8: 2,    # O
    9: 3,    # F
    16: 4,   # S
    17: 5    # Cl
}

IDX_TO_ATOM = {v: k for k, v in ATOM_TO_IDX.items()}

ATOM_VALENCY_LIMIT = {
    6: 4,    # C
    7: 3,    # N
    8: 2,    # O
    9: 1,    # F
    16: 6,   # S
    17: 1    # Cl
}

ALLOWED_ATOMS = set(ATOM_TO_IDX.keys())
NUM_ATOM_TYPES = len(ATOM_TO_IDX)

# ==================== 模型参数 ====================
# 属性向量维度：
# 0: QED, 1: logP, 2: heavy_atom_count, 3: ring_count, 4: MW
# 5: HBD, 6: HBA, 7: rotatable_bonds, 8: TPSA, 9: SA score
NUM_PROPERTIES = 10

# ==================== 约束阈值 ====================
MW_MIN = 50
MW_MAX = 600

LOGP_MIN = -3
LOGP_MAX = 7

HBD_MAX = 5
HBA_MAX = 10
ROT_BONDS_MAX = 10

QED_MIN = 0.3
SA_SCORE_MAX = 6.0

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_device():
    return torch.device('cuda' if torch.cuda.is_available() else 'cpu')
