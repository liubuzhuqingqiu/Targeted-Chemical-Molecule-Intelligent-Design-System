import torch
from model import MoleculeVAE
from reconstruct import logits_to_smiles


def real_generate():
    # 1. 自动检测设备
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"正在使用设备: {device}")

    # 2. 初始化模型
    model = MoleculeVAE(hidden_channels=64, latent_dim=32).to(device)

    # 3. 加载训练好的权重
    try:
        model.load_state_dict(torch.load("models/defualt.pth", map_location=device))
        print("✅ 已成功加载 VAE 模型权重。")
    except FileNotFoundError:
        print("⚠️ 未找到 defualt.pth，将使用随机初始化的模型进行演示。")

    model.eval()

    print("\n--- 正在从潜在空间进行批量采样生成 ---")

    success_count = 0
    max_attempts = 20

    with torch.no_grad():
        for i in range(max_attempts):
            z = torch.randn(1, 32).to(device)

            atom_logits = model.decoder_atoms(z).view(-1, 20, 10)
            edge_logits = model.decoder_edges(z).view(-1, 20, 20)

            res_smiles = logits_to_smiles(atom_logits, edge_logits)

            if res_smiles and len(res_smiles) > 1:
                print(f"🎉 尝试第 {i + 1} 次 - 成功生成分子: {res_smiles}")
                success_count += 1
            else:
                print(f"❌ 尝试第 {i + 1} 次 - 生成无效（化学规则拦截）")

    if success_count == 0:
        print("\n结论：本次采样未捕获到合法分子。")
        print("建议方案：1. 增加 train.py 的训练轮数；2. 增加数据集样本量。")
    else:
        print(f"\n生成结束，共获得 {success_count} 个合法分子。")


if __name__ == "__main__":
    real_generate()