# 集中管理所有路径和参数配置

import os
import torch

# 项目基础目录路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 模型保存目录路径
MODEL_DIR = os.path.join(BASE_DIR, "models")
# 自定义数据集上传目录路径
UPLOAD_DIR = os.path.join(BASE_DIR, "datasets")

# 默认模型名称
DEFAULT_MODEL_NAME = "default"
# 默认模型保存路径
DEFAULT_MODEL_PATH = os.path.join(MODEL_DIR, f"{DEFAULT_MODEL_NAME}.pth")

# 最大分子节点数（原子数）
MAX_NODES = 20
# 潜在空间维度
LATENT_DIM = 32
# 默认隐藏层维度
DEFAULT_HIDDEN_DIM = 64

# 默认训练轮次
DEFAULT_EPOCHS = 10
# 默认学习率
DEFAULT_LR = 0.001
# 默认批次大小
DEFAULT_BATCH_SIZE = 32

# 默认生成尝试次数
DEFAULT_GENERATE_ATTEMPTS = 20
# 默认生成批次大小
DEFAULT_GENERATE_BATCH_SIZE = 1

# QED（定量药物评估）阈值
QED_THRESHOLD = 0.5
# LogP（脂水分配系数）阈值
LOGP_THRESHOLD = 5.0

os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


# 获取可用的设备（GPU或CPU）
def get_device():
    return torch.device('cuda' if torch.cuda.is_available() else 'cpu')
