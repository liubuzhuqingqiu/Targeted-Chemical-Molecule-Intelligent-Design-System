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

app = Flask(__name__)
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

training_status = {
    "status": "idle",
    "current_epoch": 0,
    "total_epochs": 0,
    "loss": 0.0,
    "logs": [],
    "lr": 0.0,
    "batch_size": 0
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
@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    model_file = data.get('model_file')
    target = data.get('target', 'random')
    model_path = os.path.join(MODEL_DIR, model_file)

    if not os.path.exists(model_path):
        return jsonify({"error": "找不到模型"}), 404

    model = load_model(model_path, DEVICE)

    if model is None:
        return jsonify({"error": "模型维度不匹配或文件损坏，无法加载"}), 500

    model.eval()

    best_mol = None
    best_score = -float('inf')
    with torch.no_grad():
        for _ in range(30):
            z = torch.randn(1, 32).to(DEVICE)
            atom_logits = model.decoder_atoms(z).view(-1, 20, 10)
            edge_logits = model.decoder_edges(z).view(-1, 20, 20)
            smiles = logits_to_smiles(atom_logits, edge_logits)
            if smiles:
                m = evaluate_molecule(smiles)
                if not m: continue
                score = m['qed'] if target == 'high_qed' else (-m['logp'] if target == 'low_logp' else 1)
                if score > best_score:
                    best_score = score
                    best_mol = {"smiles": smiles, "metrics": m, "image": mol_to_base64(smiles)}

    return jsonify(best_mol) if best_mol else jsonify({"error": "未生成有效分子"}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)