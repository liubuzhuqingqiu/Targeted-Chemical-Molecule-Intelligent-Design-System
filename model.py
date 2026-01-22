# 定义MoleculeVAE模型结构，包含编码器、解码器和前向传播逻辑

import torch
import torch.nn as nn
from torch_geometric.nn import GCNConv, global_mean_pool


class MoleculeVAE(nn.Module):
    # 初始化模型参数和网络结构
    def __init__(self, hidden_channels=64, latent_dim=32, max_nodes=20):
        super(MoleculeVAE, self).__init__()
        self.max_nodes = max_nodes
        self.embedding = nn.Embedding(100, hidden_channels)
        self.conv1 = GCNConv(hidden_channels, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels)
        self.mu = nn.Linear(hidden_channels, latent_dim)
        self.logvar = nn.Linear(hidden_channels, latent_dim)
        self.decoder_atoms = nn.Sequential(
            nn.Linear(latent_dim, 64),
            nn.ReLU(),
            nn.Linear(64, max_nodes * 10)
        )
        self.decoder_edges = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.ReLU(),
            nn.Linear(128, max_nodes * max_nodes)
        )

    # 编码输入数据到潜在空间
    def encode(self, x, edge_index, batch):
        x = self.embedding(x.squeeze().long())
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index).relu()
        x = global_mean_pool(x, batch)
        return self.mu(x), self.logvar(x)

    # 重参数化技巧，从潜在分布中采样
    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    # 前向传播，执行编码、采样和解码
    def forward(self, data):
        mu, logvar = self.encode(data.x, data.edge_index, data.batch)
        z = self.reparameterize(mu, logvar)
        atom_logits = self.decoder_atoms(z).view(-1, self.max_nodes, 10)
        edge_logits = self.decoder_edges(z).view(-1, self.max_nodes, self.max_nodes)
        return atom_logits, edge_logits, mu, logvar