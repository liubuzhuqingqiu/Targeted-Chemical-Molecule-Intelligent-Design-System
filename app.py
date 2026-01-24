# Flask Web应用主文件，处理HTTP请求，提供Web界面和API接口

import os
import torch
import threading
import base64
from io import BytesIO
from flask import Flask, render_template, jsonify, request
from rdkit import Chem
from rdkit.Chem import Draw

from model import MoleculeVAE
from reconstruct import logits_to_smiles, evaluate_molecule
from train import train_custom_model
from config import BASE_DIR, MODEL_DIR, UPLOAD_DIR, get_device

# Flask应用实例，用于处理HTTP请求和路由
app = Flask(__name__)
# 设备信息，自动检测并使用可用的GPU或CPU
DEVICE = get_device()

# 加载模型，尝试不同的隐藏维度直到成功
def load_model(model_path, device):
    if not os.path.exists(model_path):
        return None
    
    for dim in [128, 64, 32, 256]:
        try:
            model = MoleculeVAE(hidden_channels=dim, latent_dim=32).to(device)
            model.load_state_dict(torch.load(model_path, map_location=device))
            print(f"✅ 成功加载 {dim} 维度的模型: {os.path.basename(model_path)}")
            return model
        except Exception as e:
            continue
    
    return None

# 训练状态全局变量，用于跟踪和返回训练进度信息
training_status = {
    "status": "idle",          # 训练状态：idle（空闲）、training（训练中）、success（成功）、error（错误）
    "current_epoch": 0,         # 当前训练轮次
    "total_epochs": 0,          # 总训练轮次
    "loss": 0.0,                # 当前训练损失值
    "logs": [],                 # 训练日志信息
    "lr": 0.0,                  # 学习率
    "batch_size": 0             # 批次大小
}

# 将分子的SMILES字符串转换为Base64编码的图像
def mol_to_base64(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        img = Draw.MolToImage(mol, size=(400, 400))
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    return None

# 渲染主页面模板
@app.route('/')
def index():
    return render_template('index.html')

# 获取所有.pth模型文件并返回排序后的列表
@app.route('/get_models')
def get_models():
    models = [f for f in os.listdir(MODEL_DIR) if f.endswith('.pth')]
    return jsonify({"models": sorted(list(set(models)))})

# 返回当前训练状态信息
@app.route('/get_train_status')
def get_status():
    return jsonify(training_status)

# 接收训练参数，启动后台训练任务
@app.route('/start_train', methods=['POST'])
def start_train():
    global training_status
    file = request.files['dataset']
    model_name = request.form.get('model_name', 'new_model')
    epochs = int(request.form.get('epochs', 10))
    hidden_dim = int(request.form.get('hidden_dim', 64))
    lr = float(request.form.get('lr', 0.001))
    batch_size = int(request.form.get('batch_size', 32))

    dataset_path = os.path.join(UPLOAD_DIR, f"{model_name}.smi")
    file.save(dataset_path)

    training_status.update({
        "status": "training",
        "current_epoch": 0,
        "total_epochs": epochs,
        "loss": 0.0,
        "logs": ["> 正在建立后台连接..."],
        "lr": lr,
        "batch_size": batch_size
    })

    thread = threading.Thread(
        target=train_custom_model,
        args=(dataset_path, model_name, MODEL_DIR, epochs, lr, batch_size, hidden_dim, training_status)
    )
    thread.start()
    return jsonify({"msg": "训练任务已成功启动"})

# 使用训练好的模型生成新分子
# 实现性质导向优化：在潜在空间中使用梯度上升引导生成方向
@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    model_file = data.get('model_file')
    target = data.get('target', 'random')  # 生成目标：high_qed（高药物评估值）、high_logp（高脂水分配系数）或random（随机）
    model_path = os.path.join(MODEL_DIR, model_file)

    if not os.path.exists(model_path):
        return jsonify({"error": "找不到模型"}), 404

    model = load_model(model_path, DEVICE)

    if model is None:
        return jsonify({"error": "模型维度不匹配或文件损坏，无法加载"}), 500

    model.eval()

    best_mol = None
    best_score = -float('inf')
    
    try:
        # 尝试多个初始点
        for init_idx in range(5):
            # 在潜在空间中随机初始化
            z = torch.randn(1, 32).to(DEVICE)
            z.requires_grad_(True)
            
            # 梯度上升优化
            if target != 'random':
                optimizer = torch.optim.Adam([z], lr=0.1)
                for step in range(20):
                    optimizer.zero_grad()
                    # 预测性质
                    properties = model.predict_properties(z)
                    qed_pred = properties[0, 0]
                    logp_pred = properties[0, 1]
                    
                    # 根据目标计算损失函数
                    if target == 'high_qed':
                        loss = -qed_pred  # 最大化QED
                    elif target == 'high_logp':
                        loss = -logp_pred  # 最大化LogP
                    else:
                        loss = 0
                    
                    # 反向传播计算梯度
                    loss.backward()
                    optimizer.step()
            
            with torch.no_grad():
                # 解码生成分子
                atom_logits = model.decoder_atoms(z).view(-1, 20, 10)
                edge_logits = model.decoder_edges(z).view(-1, 20, 20)
                smiles = logits_to_smiles(atom_logits, edge_logits)
                
                if smiles:
                    # 评估分子性质
                    m = evaluate_molecule(smiles)
                    if not m: continue
                    # 根据目标计算分数
                    score = m['qed'] if target == 'high_qed' else (m['logp'] if target == 'high_logp' else 1)
                    if score > best_score:
                        best_score = score
                        best_mol = {"smiles": smiles, "metrics": m, "image": mol_to_base64(smiles)}

        return jsonify(best_mol) if best_mol else jsonify({"error": "未生成有效分子"}), 400
    except Exception as e:
        print(f"生成分子时出错: {str(e)}")
        return jsonify({"error": f"生成分子时出错: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)