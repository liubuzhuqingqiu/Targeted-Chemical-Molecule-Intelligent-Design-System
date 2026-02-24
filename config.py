import os
import torch

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
UPLOAD_DIR = os.path.join(BASE_DIR, "datasets")

DEFAULT_MODEL_NAME = "default"
DEFAULT_MODEL_PATH = os.path.join(MODEL_DIR, f"{DEFAULT_MODEL_NAME}.pth")

MAX_NODES = 20
LATENT_DIM = 32
DEFAULT_HIDDEN_DIM = 128
# 属性向量维度：
# 0: QED
# 1: logP
# 2: heavy_atom_count
# 3: ring_count
# 4: MW
# 5: HBD
# 6: HBA
# 7: rotatable_bonds
# 8: TPSA
# 9: SA score
NUM_PROPERTIES = 10

DEFAULT_EPOCHS = 50
DEFAULT_LR = 0.001
DEFAULT_BATCH_SIZE = 32

DEFAULT_GENERATE_ATTEMPTS = 20
DEFAULT_GENERATE_BATCH_SIZE = 1

QED_THRESHOLD = 0.6
LOGP_THRESHOLD = 5.0

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