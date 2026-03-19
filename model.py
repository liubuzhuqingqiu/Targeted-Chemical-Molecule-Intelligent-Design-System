import torch
import torch.nn as nn
from torch_geometric.nn import GCNConv, global_mean_pool
from config import NUM_ATOM_TYPES, NUM_PROPERTIES


class MoleculeVAE(nn.Module):
    """
    分子图变分自编码器 (Graph VAE)

    整体结构：
      输入(分子图) → 编码器(GCN) → 潜在空间(z) → 解码器(原子+键) + 属性预测器

    三大组件：
      1. 编码器：将分子图压缩为低维潜在向量 z
      2. 解码器：从 z 重建分子的原子类型和化学键
      3. 属性预测器：从 z 预测分子性质，用于性质导向生成
    """

    def __init__(self, hidden_channels=64, latent_dim=32, max_nodes=20):
        super().__init__()
        self.max_nodes = max_nodes
        self.latent_dim = latent_dim

        # ==================== 编码器 ====================
        # 将原子类型索引映射为向量
        self.embedding = nn.Embedding(NUM_ATOM_TYPES, hidden_channels)
        # 两层图卷积：聚合邻居节点信息，学习分子结构特征
        self.conv1 = GCNConv(hidden_channels, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels)
        # 输出潜在空间的均值和对数方差（VAE 的核心参数）
        self.fc_mu = nn.Linear(hidden_channels, latent_dim)
        self.fc_logvar = nn.Linear(hidden_channels, latent_dim)

        # ==================== 解码器 ====================
        # 原子解码器：从 z 预测每个节点位置的原子类型
        self.decoder_atoms = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.ReLU(),
            nn.Linear(128, max_nodes * NUM_ATOM_TYPES)
        )
        # 键解码器：从 z 预测节点对之间的键类型（无键/单键/双键/三键/芳香键）
        self.decoder_edges = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.ReLU(),
            nn.Linear(128, max_nodes * max_nodes * 5)
        )

        # ==================== 属性预测器 ====================
        # 从潜在向量 z 预测分子的 10 维化学性质
        # 用途：在生成阶段引导采样方向，使生成分子趋向目标性质
        self.predictor = nn.Sequential(
            nn.Linear(latent_dim, 64),
            nn.ReLU(),
            nn.Linear(64, NUM_PROPERTIES)
        )

    def encode(self, x, edge_index, batch):
        """编码器：分子图 → 潜在空间分布参数 (μ, log σ²)"""
        x = self.embedding(x.squeeze().long())
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index).relu()
        x = global_mean_pool(x, batch)
        return self.fc_mu(x), self.fc_logvar(x)

    def reparameterize(self, mu, logvar):
        """重参数化技巧：从 N(μ, σ²) 中采样，同时保持梯度可传播"""
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def predict_properties(self, z):
        """属性预测：从潜在向量预测分子性质（用于生成引导）"""
        return self.predictor(z)

    def forward(self, data):
        """前向传播：编码 → 采样 → 解码 + 属性预测"""
        mu, logvar = self.encode(data.x, data.edge_index, data.batch)
        z = self.reparameterize(mu, logvar)
        atom_logits = self.decoder_atoms(z).view(-1, self.max_nodes, NUM_ATOM_TYPES)
        edge_logits = self.decoder_edges(z).view(-1, self.max_nodes, self.max_nodes, 5)
        properties = self.predict_properties(z)
        return atom_logits, edge_logits, mu, logvar, properties
