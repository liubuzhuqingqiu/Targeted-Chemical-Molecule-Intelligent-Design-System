import torch
import os
from model import MoleculeVAE
from molecule_processor import smiles_to_graph
from torch_geometric.loader import DataLoader
from config import DEFAULT_EPOCHS, DEFAULT_LR, DEFAULT_BATCH_SIZE, DEFAULT_HIDDEN_DIM, get_device


def vae_loss(atom_logits, edge_logits, mu, logvar, properties_pred, properties_true, batch, current_batch_max_nodes, beta=1.0, all_properties=None):
    from torch_geometric.utils import to_dense_batch, to_dense_adj
    from atom_mapping import NUM_ATOM_TYPES
    import torch.nn.functional as F
    
    batch_size = mu.shape[0]
    
    kl_loss = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    free_bits = 1.0
    kl_loss = torch.max(kl_loss, torch.tensor(free_bits * batch_size, device=mu.device))
    property_weights = torch.tensor([100.0, 10.0, 10.0, 50.0, 0.1, 20.0, 10.0], device=mu.device).view(1, -1)
    
    prop_loss = torch.tensor(0.0, device=mu.device)
    if properties_true is not None:
        if all_properties is not None:
            for pred in all_properties:
                weighted_error = (pred - properties_true) ** 2 * property_weights
                prop_loss += torch.mean(weighted_error)
            prop_loss /= len(all_properties)
        else:
            weighted_error = (properties_pred - properties_true) ** 2 * property_weights
            prop_loss = torch.mean(weighted_error)
    
    max_nodes = atom_logits.shape[1]
    
    assert atom_logits.shape[0] == batch_size, f"atom_logits batch_size mismatch: {atom_logits.shape[0]} != {batch_size}"
    
    x_dense, mask = to_dense_batch(batch.x, batch.batch, max_num_nodes=max_nodes, fill_value=NUM_ATOM_TYPES)
    x_dense = torch.clamp(x_dense.squeeze(-1), 0, NUM_ATOM_TYPES).long()
    
    padded_x = x_dense.clone()
    
    atom_class_weights = torch.ones(NUM_ATOM_TYPES, device=mu.device)
    atom_class_weights[0] = 1.0
    atom_class_weights[1] = 2.0
    atom_class_weights[2] = 2.5
    atom_class_weights[3] = 4.0
    atom_class_weights[4] = 5.0
    atom_class_weights[5] = 5.0
    
    recon_atom_loss = F.cross_entropy(
        atom_logits.view(-1, NUM_ATOM_TYPES),
        padded_x.view(-1),
        weight=atom_class_weights,
        ignore_index=NUM_ATOM_TYPES
    )
    
    edge_mask = mask.unsqueeze(2) * mask.unsqueeze(1)
    
    edge_labels = torch.zeros(batch_size, max_nodes, max_nodes, dtype=torch.long, device=mu.device)
    
    if hasattr(batch, 'edge_attr') and batch.edge_attr is not None:
        edge_true = to_dense_adj(batch.edge_index, batch.batch, edge_attr=batch.edge_attr, max_num_nodes=max_nodes)
        edge_true = edge_true.squeeze(-1)
        edge_labels = edge_true.long()
    else:
        edge_true = to_dense_adj(batch.edge_index, batch.batch, max_num_nodes=max_nodes)
        edge_true = edge_true.squeeze(-1)
        edge_labels = edge_true.long()
        edge_labels = torch.clamp(edge_labels, 0, 3)
    
    edge_class_weights = torch.tensor([0.1, 5.0, 7.0, 10.0], device=mu.device)
    
    loss_per_element = F.cross_entropy(
        edge_logits.view(-1, 4),
        edge_labels.view(-1),
        weight=edge_class_weights,
        reduction='none',
        ignore_index=4
    )
    
    masked_loss = loss_per_element * edge_mask.float().view(-1)
    
    if edge_mask.sum() > 0:
        recon_edge_loss = masked_loss.sum() / edge_mask.sum()
    else:
        recon_edge_loss = torch.tensor(0.0, device=mu.device)
    
    from atom_mapping import ATOM_VALENCY_LIMIT, IDX_TO_ATOM
    valency_penalty = torch.tensor(0.0, device=mu.device)
    
    atom_pred = torch.argmax(atom_logits, dim=-1)
    bond_pred = torch.argmax(edge_logits, dim=-1)
    
    bond_order_map = torch.tensor([0, 1, 2, 3, 1], device=mu.device)
    
    bond_orders = bond_order_map[bond_pred]
    total_bond_order = bond_orders.sum(dim=-1)
    
    max_valence_list = []
    for atom_idx in range(NUM_ATOM_TYPES):
        atomic_num = IDX_TO_ATOM.get(atom_idx, 6)
        max_valence_list.append(ATOM_VALENCY_LIMIT.get(atomic_num, 4))
    max_valence_tensor = torch.tensor(max_valence_list, device=mu.device)
    
    atom_max_valence = max_valence_tensor[atom_pred]
    valency_violations = torch.clamp(total_bond_order - atom_max_valence, min=0)
    valency_penalty = valency_violations.sum() / (batch_size * max_nodes + 1e-6)
    
    total_loss = (1.0 * recon_atom_loss) + (5.0 * recon_edge_loss) + (beta * kl_loss / batch_size) + (0.1 * prop_loss) + (0.3 * valency_penalty)
    
    recon_loss = recon_atom_loss + recon_edge_loss
    
    return total_loss, recon_loss, kl_loss, prop_loss


def log_message(msg, status_dict=None):
    if status_dict is not None:
        status_dict["logs"].append(msg)
    print(f"[日志] {msg}")


def train_custom_model(dataset_path, model_name, save_dir, epochs=50, lr=0.001, batch_size=32, hidden_dim=64,
                       status_dict=None, patience=10, validation_split=0.1):
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
            if not smiles: continue
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
    log_message(f"{completion_msg}", status_dict)

    if not data_list:
        if status_dict: status_dict["status"] = "error"
        log_message("错误：未发现有效分子数据，训练终止。", status_dict)
        return

    max_nodes = max(max_nodes, 1)
    log_message(f"扫描数据集确定的最大节点数: {max_nodes}", status_dict)

    from torch.utils.data import random_split
    import torch
    
    dataset_size = len(data_list)
    val_size = int(dataset_size * validation_split)
    train_size = dataset_size - val_size
    
    train_dataset, val_dataset = random_split(data_list, [train_size, val_size])
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    log_message(f"数据集分割: 训练集 {train_size} 个分子, 验证集 {val_size} 个分子", status_dict)

    model = MoleculeVAE(hidden_channels=hidden_dim, latent_dim=32, max_nodes=max_nodes).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5, verbose=True)

    best_val_loss = float('inf')
    best_epoch = 0
    patience_counter = 0
    best_model_state = None

    log_message(f"\n开始训练循环 (总轮次: {epochs})...", status_dict)
    for epoch in range(1, epochs + 1):
        model.train()
        beta_max = 0.05
        warmup_epochs = int(epochs * 0.3)
        
        if epoch < warmup_epochs:
            beta = (epoch / warmup_epochs) * beta_max
        else:
            beta = beta_max
        
        total_loss = 0
        total_recon_loss = 0
        total_kl_loss = 0
        total_prop_loss = 0
        
        for batch in train_loader:
            batch_size = batch.num_graphs
            num_nodes_per_graph = torch.bincount(batch.batch, minlength=batch_size)
            current_batch_max_nodes = num_nodes_per_graph.max().item()
            
            batch = batch.to(device)
            optimizer.zero_grad()
            atom_logits, edge_logits, mu, logvar, properties_pred, all_properties = model(batch)
            properties_true = batch.y
            loss, recon_loss, kl_loss, prop_loss = vae_loss(atom_logits, edge_logits, mu, logvar, properties_pred, properties_true, batch, model.max_nodes, beta=beta, all_properties=all_properties)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            total_recon_loss += recon_loss.item()
            total_kl_loss += kl_loss.item()
            total_prop_loss += prop_loss.item()

        avg_loss = total_loss / len(train_loader)
        avg_recon_loss = total_recon_loss / len(train_loader)
        avg_kl_loss = total_kl_loss / len(train_loader)
        avg_prop_loss = total_prop_loss / len(train_loader)
        
        model.eval()
        val_total_loss = 0
        with torch.no_grad():
            for val_batch in val_loader:
                val_batch = val_batch.to(device)
                val_atom_logits, val_edge_logits, val_mu, val_logvar, val_properties_pred, val_all_properties = model(val_batch)
                val_properties_true = val_batch.y
                val_loss, _, _, _ = vae_loss(val_atom_logits, val_edge_logits, val_mu, val_logvar, val_properties_pred, val_properties_true, val_batch, model.max_nodes, beta=beta, all_properties=val_all_properties)
                val_total_loss += val_loss.item()
        avg_val_loss = val_total_loss / len(val_loader) if len(val_loader) > 0 else 0
        
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
                'hidden_channels': hidden_dim
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
            'hidden_channels': hidden_dim
        }, save_path)

    summary = [
        f"\n{'-' * 18} 训练总结看板 {'-' * 18}",
        f" 模型名称   : {model_name}.pth",
        f" 保存路径   : {save_path}",
        f" 最佳验证损失: {best_val_loss:.8f} (第 {best_epoch} 轮)",
        f" 训练参数   : [轮次={epochs}] [学习率={lr}] [批次大小={batch_size}] [隐藏层={hidden_dim}]",
        f" 运行设备   : {device}",
        f"{'=' * 50}\n"
    ]
    for line in summary:
        print(line)

    if status_dict:
        status_dict["status"] = "success"
        log_message("训练完成，模型已成功保存至服务器。", status_dict)


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