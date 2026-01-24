# 处理分子数据转换，将SMILES字符串转换为图数据对象

import torch
from rdkit import Chem
from rdkit.Chem import QED, Descriptors
from torch_geometric.data import Data


# 将分子SMILES字符串转换为图数据对象
def smiles_to_graph(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None

    xs = [[atom.GetAtomicNum()] for atom in mol.GetAtoms()]
    x = torch.tensor(xs, dtype=torch.float)

    edge_indices = []
    for bond in mol.GetBonds():
        i = bond.GetBeginAtomIdx()
        j = bond.GetEndAtomIdx()
        edge_indices += [[i, j], [j, i]]

    edge_index = torch.tensor(edge_indices, dtype=torch.long).t().contiguous()
    
    # 计算分子性质
    try:
        qed = QED.qed(mol)
        logp = Descriptors.MolLogP(mol)
        # 将性质添加到数据对象中，形状为[1, 2]，确保批次化时正确堆叠
        y = torch.tensor([[qed, logp]], dtype=torch.float)
        return Data(x=x, edge_index=edge_index, y=y)
    except:
        return None


# 检查分子的化学有效性
def validate_molecule(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None: return False
    try:
        Chem.SanitizeMol(mol)
        return True
    except:
        return False