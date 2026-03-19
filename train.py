import torch
import torch.nn.functional as F
import os
from model import MoleculeVAE
from molecule_processor import smiles_to_graph
from torch_geometric.loader import DataLoader
from torch_geometric.utils import to_dense_batch, to_dense_adj
from config import NUM_ATOM_TYPES, get_device


def vae_loss(atom_logits, edge_logits, mu, logvar, properties_pred, properties_true, batch, beta=1.0):
    """
    VAE 总损失 = 原子重构 + 3×键重构 + β×KL散度 + 0.3×属性预测

    各项含义：
      - 原子/键重构损失：衡量解码器还原分子结构的准确度
      - KL 散度：约束潜在空间接近标准正态分布，保证采样质量
      - 属性预测损失：让潜在空间编码分子性质信息，支持性质导向生成
    """

    batch_size = mu.shape[0]

    # KL 散度
    kl_loss = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())

    # 属性预测损失（均方误差）
    prop_loss = torch.tensor(0.0, device=mu.device)
    if properties_true is not None:
        prop_loss = F.mse_loss(properties_pred, properties_true)

    max_nodes = atom_logits.shape[1]

    # 原子类型重构损失（交叉熵）
    x_dense, mask = to_dense_batch(batch.x, batch.batch, max_num_nodes=max_nodes, fill_value=NUM_ATOM_TYPES)
    x_dense = torch.clamp(x_dense.squeeze(-1), 0, NUM_ATOM_TYPES).long()
    recon_atom_loss = F.cross_entropy(
        atom_logits.view(-1, NUM_ATOM_TYPES),
        x_dense.view(-1),
        ignore_index=NUM_ATOM_TYPES
    )

    # 键类型重构损失（交叉熵 + 掩码）
    edge_mask = mask.unsqueeze(2) * mask.unsqueeze(1)
    edge_labels = torch.zeros(batch_size, max_nodes, max_nodes, dtype=torch.long, device=mu.device)

    if hasattr(batch, 'edge_attr') and batch.edge_attr is not None:
        edge_true = to_dense_adj(batch.edge_index, batch.batch, edge_attr=batch.edge_attr, max_num_nodes=max_nodes)
        edge_labels = edge_true.squeeze(-1).long()
    else:
        edge_true = to_dense_adj(batch.edge_index, batch.batch, max_num_nodes=max_nodes)
        edge_labels = torch.clamp(edge_true.squeeze(-1).long(), 0, 4)

    loss_per_element = F.cross_entropy(
        edge_logits.view(-1, 5),
        edge_labels.view(-1),
        reduction='none',
        ignore_index=5
    )
    masked_loss = loss_per_element * edge_mask.float().view(-1)
    recon_edge_loss = masked_loss.sum() / edge_mask.sum() if edge_mask.sum() > 0 else torch.tensor(0.0, device=mu.device)

    # 总损失
    total_loss = (
        1.0 * recon_atom_loss
        + 3.0 * recon_edge_loss
        + beta * kl_loss / batch_size
        + 0.3 * prop_loss
    )
    recon_loss = recon_atom_loss + recon_edge_loss

    return total_loss, recon_loss, kl_loss, prop_loss


def log_message(msg, status_dict=None):
    if status_dict is not None:
        status_dict["logs"].append(msg)
    print(f"[日志] {msg}")


def train_custom_model(dataset_path, model_name, save_dir, epochs=50, lr=0.001, batch_size=32, hidden_dim=64,
                       status_dict=None, patience=10, validation_split=0.1, latent_dim=32):
    device = get_device()

    print(f"\n{'=' * 50}")
    print(f"启动训练任务: {model_name}")
    print(f" 运行设备: {device}")
    print(f"{'=' * 50}")

    data_list = []
    max_nodes = 0
    with open(dataset_path, 'r') as f:
        lines = f.readlines()
        total_lines = len(lines)
        for i, line in enumerate(lines):
            smiles = line.strip().replace('"', '')
            if not smiles:
                continue
            g = smiles_to_graph(smiles)
            if g:
                data_list.append(g)
                num_atoms = g.x.shape[0]
                if num_atoms > max_nodes:
                    max_nodes = num_atoms

            if status_dict is not None and i % 50 == 0:
                msg = f"正在读取数据: {i}/{total_lines}"
                log_message(msg, status_dict)

    completion_msg = f"数据读取完成，共计: {len(data_list)} 条有效分子"
    log_message(completion_msg, status_dict)

    if not data_list:
        if status_dict:
            status_dict["status"] = "error"
        log_message("错误：未发现有效分子数据，训练终止。", status_dict)
        return

    max_nodes = max(max_nodes, 1)
    log_message(f"扫描数据集确定的最大节点数: {max_nodes}", status_dict)

    from torch.utils.data import random_split

    dataset_size = len(data_list)
    val_size = int(dataset_size * validation_split)
    train_size = dataset_size - val_size
    if train_size < 1:
        train_size = dataset_size
        val_size = 0
    train_dataset, val_dataset = random_split(data_list, [train_size, val_size])
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    log_message(f"数据集分割: 训练集 {train_size} 个分子, 验证集 {val_size} 个分子", status_dict)
    if val_size == 0:
        log_message("验证集为空，将使用训练损失选取最佳模型", status_dict)

    model = MoleculeVAE(hidden_channels=hidden_dim, latent_dim=latent_dim, max_nodes=max_nodes).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5, verbose=True)

    best_val_loss = float('inf')
    best_epoch = 0
    patience_counter = 0
    best_model_state = None

    log_message(f"\n开始训练循环 (总轮次: {epochs})...", status_dict)
    for epoch in range(1, epochs + 1):
        model.train()

        # KL 退火：前 30% 轮次 β 从 0 线性增长到 beta_max
        beta_max = 0.05
        warmup_epochs = int(epochs * 0.3)
        beta = (epoch / warmup_epochs) * beta_max if epoch < warmup_epochs else beta_max

        total_loss = 0
        total_recon_loss = 0
        total_kl_loss = 0
        total_prop_loss = 0

        for batch in train_loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            atom_logits, edge_logits, mu, logvar, properties_pred = model(batch)
            properties_true = batch.y
            loss, recon_loss, kl_loss, prop_loss = vae_loss(
                atom_logits, edge_logits, mu, logvar,
                properties_pred, properties_true, batch,
                beta=beta,
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            total_loss += loss.item()
            total_recon_loss += recon_loss.item()
            total_kl_loss += kl_loss.item()
            total_prop_loss += prop_loss.item()

        avg_loss = total_loss / len(train_loader)
        avg_recon_loss = total_recon_loss / len(train_loader)
        avg_kl_loss = total_kl_loss / len(train_loader)
        avg_prop_loss = total_prop_loss / len(train_loader)

        # 验证阶段
        model.eval()
        val_total_loss = 0
        if len(val_loader) > 0:
            with torch.no_grad():
                for val_batch in val_loader:
                    val_batch = val_batch.to(device)
                    val_atom_logits, val_edge_logits, val_mu, val_logvar, val_properties_pred = model(val_batch)
                    val_properties_true = val_batch.y
                    val_loss, _, _, _ = vae_loss(
                        val_atom_logits, val_edge_logits, val_mu, val_logvar,
                        val_properties_pred, val_properties_true, val_batch,
                        beta=beta,
                    )
                    val_total_loss += val_loss.item()
            avg_val_loss = val_total_loss / len(val_loader)
        else:
            avg_val_loss = avg_loss

        log_str = f" >>> 第 [{epoch:03d}/{epochs}] 轮 | 总损失: {avg_loss:.8f} | 验证损失: {avg_val_loss:.8f} | 重构损失: {avg_recon_loss:.8f} | KL损失: {avg_kl_loss:.8f} | 性质损失: {avg_prop_loss:.8f} | Beta: {beta:.4f}"

        if status_dict is not None:
            status_dict["current_epoch"] = epoch
            status_dict["loss"] = avg_loss
            status_dict["val_loss"] = avg_val_loss
            status_dict["logs"].append(log_str)

        print(log_str)

        scheduler.step(avg_val_loss)

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_epoch = epoch
            patience_counter = 0
            best_model_state = {
                'state_dict': model.state_dict(),
                'max_nodes': model.max_nodes,
                'hidden_channels': hidden_dim,
                'latent_dim': latent_dim
            }
            log_message(f"  *** 发现更好的模型，验证损失: {best_val_loss:.8f} (第 {best_epoch} 轮)", status_dict)
        else:
            patience_counter += 1
            if patience_counter >= patience:
                log_message(f"  *** 早停触发: 验证损失 {patience} 轮未改善", status_dict)
                break

    save_path = os.path.join(save_dir, f"{model_name}.pth")
    if best_model_state is not None:
        torch.save(best_model_state, save_path)
        log_message(f"  *** 保存最佳模型 (第 {best_epoch} 轮, 验证损失: {best_val_loss:.8f})")
    else:
        torch.save({
            'state_dict': model.state_dict(),
            'max_nodes': model.max_nodes,
            'hidden_channels': hidden_dim,
            'latent_dim': latent_dim
        }, save_path)

    summary = [
        f"\n{'-' * 18} 训练总结看板 {'-' * 18}",
        f" 模型名称   : {model_name}.pth",
        f" 保存路径   : {save_path}",
        f" 最佳验证损失: {best_val_loss:.8f} (第 {best_epoch} 轮)",
        f" 训练参数   : [轮次={epochs}] [学习率={lr}] [批次={batch_size}] [隐藏层={hidden_dim}] [潜在维={latent_dim}]",
        f" 运行设备   : {device}",
        f"{'=' * 50}\n"
    ]
    for line in summary:
        print(line)

    if status_dict:
        status_dict["status"] = "success"
        log_message("训练完成，模型已成功保存至服务器。", status_dict)


