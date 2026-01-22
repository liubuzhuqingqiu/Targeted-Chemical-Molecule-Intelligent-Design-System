import os
import torch
import threading
import base64
from io import BytesIO
from flask import Flask, render_template, jsonify, request
from rdkit import Chem
from rdkit.Chem import Draw, QED, Descriptors

from model import MoleculeVAE
from reconstruct import logits_to_smiles
from train import train_custom_model

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
UPLOAD_DIR = os.path.join(BASE_DIR, "custom_datasets")
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

training_status = {
    "status": "idle",
    "current_epoch": 0,
    "total_epochs": 0,
    "loss": 0.0,
    "logs": [],
    "lr": 0.0,
    "batch_size": 0
}

def mol_to_base64(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        img = Draw.MolToImage(mol, size=(400, 400))
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    return None

def evaluate_molecule(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol: return None
    return {"qed": round(QED.qed(mol), 3), "logp": round(Descriptors.MolLogP(mol), 3),
            "mw": round(Descriptors.MolWt(mol), 2), "hbd": Descriptors.NumHDonors(mol),
            "hba": Descriptors.NumHAcceptors(mol)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_models')
def get_models():
    models = [f for f in os.listdir(MODEL_DIR) if f.endswith('.pth')]
    return jsonify({"models": sorted(list(set(models)))})

@app.route('/get_train_status')
def get_status():
    return jsonify(training_status)

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


@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    model_file = data.get('model_file')
    target = data.get('target', 'random')
    model_path = os.path.join(MODEL_DIR, model_file)

    if not os.path.exists(model_path):
        return jsonify({"error": "找不到模型"}), 404

    # 尝试常见的几个维度，直到加载成功
    model = None
    for dim in [128, 64, 32, 256]:
        try:
            temp_model = MoleculeVAE(hidden_channels=dim, latent_dim=32).to(DEVICE)
            temp_model.load_state_dict(torch.load(model_path, map_location=DEVICE))
            model = temp_model
            print(f"✅ 成功加载 {dim} 维度的模型: {model_file}")
            break
        except Exception as e:
            continue

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