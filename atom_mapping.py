# 统一的原子类型映射配置
# 定义全局原子类型映射字典，确保输入预处理、模型输出和解码逻辑保持一致

# 原子类型映射字典：原子序数 → 索引
ATOM_TO_IDX = {
    6: 0,    # C
    7: 1,    # N
    8: 2,    # O
    9: 3,    # F
    16: 4,   # S
    17: 5    # Cl
}

# 反向映射：索引 → 原子序数
IDX_TO_ATOM = {
    0: 6,    # C
    1: 7,    # N
    2: 8,    # O
    3: 9,    # F
    4: 16,   # S
    5: 17    # Cl
}

# 原子价态限制
ATOM_VALENCY_LIMIT = {
    6: 4,    # C
    7: 3,    # N
    8: 2,    # O
    9: 1,    # F
    16: 6,   # S
    17: 1    # Cl
}

# 允许的原子序数集合
ALLOWED_ATOMS = set(ATOM_TO_IDX.keys())

# 原子类型数量
NUM_ATOM_TYPES = len(ATOM_TO_IDX)
