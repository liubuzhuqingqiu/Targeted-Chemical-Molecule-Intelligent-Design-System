# 实现模型训练功能，处理数据加载、训练循环和模型保存

import torch
import os
from model import MoleculeVAE
from molecule_processor import smiles_to_graph
from torch_geometric.loader import DataLoader
from config import DEFAULT_EPOCHS, DEFAULT_LR, DEFAULT_BATCH_SIZE, DEFAULT_HIDDEN_DIM, get_device


# 计算VAE损失函数
def vae_loss(atom_logits, edge_logits, mu, logvar):
    kl_loss = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    return kl_loss


# 统一的日志记录函数
def log_message(msg, status_dict=None):
    if status_dict is not None:
        status_dict["logs"].append(msg)
    print(f"[日志] {msg}")


# 训练自定义模型
def train_custom_model(dataset_path, model_name, save_dir, epochs=10, lr=0.001, batch_size=32, hidden_dim=64,
                       status_dict=None):
    device = get_device()

    print(f"\n{'=' * 50}")
    print(f" 🚀 启动训练任务: {model_name}")
    print(f" 运行设备: {device}")
    print(f"{'=' * 50}")

    data_list = []
    with open(dataset_path, 'r') as f:
        lines = f.readlines()
        total_lines = len(lines)
        for i, line in enumerate(lines):
            smiles = line.strip().replace('"', '')
            if not smiles: continue
            g = smiles_to_graph(smiles)
            if g: data_list.append(g)

            if status_dict is not None and i % 50 == 0:
                msg = f"正在读取数据: {i}/{total_lines}"
                log_message(msg, status_dict)

    completion_msg = f"数据读取完成，共计: {len(data_list)} 条有效分子"
    log_message(f"✅ {completion_msg}", status_dict)

    if not data_list:
        if status_dict: status_dict["status"] = "error"
        log_message("❌ 错误：未发现有效分子数据，训练终止。", status_dict)
        return

    loader = DataLoader(data_list, batch_size=batch_size, shuffle=True)
    model = MoleculeVAE(hidden_channels=hidden_dim, latent_dim=32).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    log_message(f"\n开始训练循环 (总轮次: {epochs})...", status_dict)
    model.train()
    for epoch in range(1, epochs + 1):
        total_loss = 0
        for batch in loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            atom_logits, edge_logits, mu, logvar = model(batch)
            loss = vae_loss(atom_logits, edge_logits, mu, logvar)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg_loss = total_loss / len(loader)
        log_str = f" >>> 第 [{epoch:03d}/{epochs}] 轮 | 损失值 (Loss): {avg_loss:.8f}"

        if status_dict is not None:
            status_dict["current_epoch"] = epoch
            status_dict["loss"] = avg_loss
            status_dict["logs"].append(log_str)

        print(log_str)

    save_path = os.path.join(save_dir, f"{model_name}.pth")
    torch.save(model.state_dict(), save_path)

    summary = [
        f"\n{'-' * 18} 训练总结看板 {'-' * 18}",
        f" 模型名称   : {model_name}.pth",
        f" 保存路径   : {save_path}",
        f" 最终 Loss  : {avg_loss:.8f}",
        f" 训练参数   : [轮次={epochs}] [学习率={lr}] [批次大小={batch_size}] [隐藏层={hidden_dim}]",
        f" 运行设备   : {device}",
        f"{'=' * 50}\n"
    ]
    for line in summary:
        print(line)

    if status_dict:
        status_dict["status"] = "success"
        log_message("✅ 训练完成，模型已成功保存至服务器。", status_dict)

    if os.path.exists(dataset_path):
        os.remove(dataset_path)


# 获取自定义数据集的DataLoader
def get_custom_loader(dataset_path, batch_size=DEFAULT_BATCH_SIZE):
    from torch_geometric.data import DataListLoader
    
    smiles_list = []
    try:
        with open(dataset_path, 'r') as f:
            smiles_list = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"加载数据集失败: {e}")
        return None
    
    data_list = []
    for smiles in smiles_list:
        data = smiles_to_graph(smiles)
        if data:
            data_list.append(data)
    
    if not data_list:
        print("未找到有效的分子数据")
        return None
    
    loader = DataLoader(data_list, batch_size=batch_size, shuffle=True)
    return loader