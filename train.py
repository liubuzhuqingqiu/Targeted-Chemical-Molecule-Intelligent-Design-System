import torch
import os
from model import MoleculeVAE
from molecule_processor import smiles_to_graph
from torch_geometric.loader import DataLoader


def vae_loss(atom_logits, edge_logits, mu, logvar):
    kl_loss = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    return kl_loss


def train_custom_model(dataset_path, model_name, save_dir, epochs=10, lr=0.001, batch_size=32, hidden_dim=64,
                       status_dict=None):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # --- 控制台打印：启动信息 ---
    print(f"\n{'=' * 50}")
    print(f" 🚀 启动训练任务: {model_name}")
    print(f" 运行设备: {device}")
    print(f"{'=' * 50}")

    # 1. 解析数据进度显示
    data_list = []
    with open(dataset_path, 'r') as f:
        lines = f.readlines()
        total_lines = len(lines)
        for i, line in enumerate(lines):
            smiles = line.strip().replace('"', '')
            if not smiles: continue
            g = smiles_to_graph(smiles)
            if g: data_list.append(g)

            # 实时进度同步
            if status_dict is not None and i % 50 == 0:
                msg = f"正在读取数据: {i}/{total_lines}"
                status_dict["logs"].append(msg)
                print(f"[数据解析] {msg}")

    completion_msg = f"数据读取完成，共计: {len(data_list)} 条有效分子"
    if status_dict:
        status_dict["logs"].append(completion_msg)
    print(f"✅ {completion_msg}")

    if not data_list:
        if status_dict: status_dict["status"] = "error"
        print("❌ 错误：未发现有效分子数据，训练终止。")
        return

    loader = DataLoader(data_list, batch_size=batch_size, shuffle=True)
    model = MoleculeVAE(hidden_channels=hidden_dim, latent_dim=32).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # 2. 训练进度显示
    print(f"\n开始训练循环 (总轮次: {epochs})...")
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

        # 同步到前端日志列表
        if status_dict is not None:
            status_dict["current_epoch"] = epoch
            status_dict["loss"] = avg_loss
            status_dict["logs"].append(log_str)

        # 打印到控制台
        print(log_str)

    # 3. 保存模型
    save_path = os.path.join(save_dir, f"{model_name}.pth")
    torch.save(model.state_dict(), save_path)

    print(f"\n{'-' * 18} 训练总结看板 {'-' * 18}")
    print(f" 模型名称   : {model_name}.pth")
    print(f" 保存路径   : {save_path}")
    print(f" 最终 Loss  : {avg_loss:.8f}")
    print(f" 训练参数   : [轮次={epochs}] [学习率={lr}] [批次大小={batch_size}] [隐藏层={hidden_dim}]")
    print(f" 运行设备   : {device}")
    print(f"{'=' * 50}\n")

    if status_dict:
        status_dict["status"] = "success"
        status_dict["logs"].append("✅ 训练完成，模型已成功保存至服务器。")

    # 清理上传的临时文件
    if os.path.exists(dataset_path):
        os.remove(dataset_path)