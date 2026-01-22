import torch
import torch.nn as nn
from torch_geometric.nn import GCNConv, global_mean_pool


class MoleculeVAE(nn.Module):
    def __init__(self, hidden_channels=64, latent_dim=32, max_nodes=20):
        super(MoleculeVAE, self).__init__()
        self.max_nodes = max_nodes
        self.embedding = nn.Embedding(100, hidden_channels)

        # 1. 编码器 (Encoder): 图卷积层
        self.conv1 = GCNConv(hidden_channels, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels)

        # 2. 潜在空间映射 (对应文档：Latent Space Mapping)
        self.mu = nn.Linear(hidden_channels, latent_dim)  # 均值
        self.logvar = nn.Linear(hidden_channels, latent_dim)  # 方差

        # 3. 解码器 (Decoder): 尝试还原原子类型和连接矩阵
        self.decoder_atoms = nn.Sequential(
            nn.Linear(latent_dim, 64),
            nn.ReLU(),
            nn.Linear(64, max_nodes * 10)  # 假设最多20个原子，每个原子10种可能
        )
        self.decoder_edges = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.ReLU(),
            nn.Linear(128, max_nodes * max_nodes)  # 还原邻接矩阵
        )


    def encode(self, x, edge_index, batch):
        x = self.embedding(x.squeeze().long())
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index).relu()
        x = global_mean_pool(x, batch)
        return self.mu(x), self.logvar(x)

    def reparameterize(self, mu, logvar):
        # 重参数化技巧 (Reparameterization Trick)
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def forward(self, data):
        mu, logvar = self.encode(data.x, data.edge_index, data.batch)
        z = self.reparameterize(mu, logvar)

        # 解码原子和边
        atom_logits = self.decoder_atoms(z).view(-1, self.max_nodes, 10)
        edge_logits = self.decoder_edges(z).view(-1, self.max_nodes, self.max_nodes)

        return atom_logits, edge_logits, mu, logvar