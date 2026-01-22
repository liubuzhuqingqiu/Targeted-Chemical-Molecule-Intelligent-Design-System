# 处理分子数据转换，将SMILES字符串转换为图数据对象

import torch
from rdkit import Chem
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
    return Data(x=x, edge_index=edge_index)


# 检查分子的化学有效性
def validate_molecule(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None: return False
    try:
        Chem.SanitizeMol(mol)
        return True
    except:
        return False