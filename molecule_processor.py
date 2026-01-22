import torch
from rdkit import Chem
from torch_geometric.data import Data


def smiles_to_graph(smiles):
    """将分子字符串转为图数据对象"""
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None

    # 节点特征：提取原子序数 (例如 C=6, O=8)
    xs = [[atom.GetAtomicNum()] for atom in mol.GetAtoms()]
    x = torch.tensor(xs, dtype=torch.float)

    # 边特征：提取化学键连接关系
    edge_indices = []
    for bond in mol.GetBonds():
        i = bond.GetBeginAtomIdx()
        j = bond.GetEndAtomIdx()
        edge_indices += [[i, j], [j, i]]  # 无向图需要双向连接

    edge_index = torch.tensor(edge_indices, dtype=torch.long).t().contiguous()
    return Data(x=x, edge_index=edge_index)


def validate_molecule(smiles):
    """化学有效性检查 (对应文档过滤器功能)"""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None: return False
    try:
        Chem.SanitizeMol(mol)  # 检查价键是否合理
        return True
    except:
        return False