# 集中管理所有路径和参数配置

import os
import torch

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
UPLOAD_DIR = os.path.join(BASE_DIR, "custom_datasets")

DEFAULT_MODEL_NAME = "default"
DEFAULT_MODEL_PATH = os.path.join(MODEL_DIR, f"{DEFAULT_MODEL_NAME}.pth")

MAX_NODES = 20
LATENT_DIM = 32
DEFAULT_HIDDEN_DIM = 64

DEFAULT_EPOCHS = 10
DEFAULT_LR = 0.001
DEFAULT_BATCH_SIZE = 32

DEFAULT_GENERATE_ATTEMPTS = 20
DEFAULT_GENERATE_BATCH_SIZE = 1

QED_THRESHOLD = 0.5
LOGP_THRESHOLD = 5.0

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


# 获取可用的设备（GPU或CPU）
def get_device():
    return torch.device('cuda' if torch.cuda.is_available() else 'cpu')
