import torch
from rdkit import Chem
from rdkit.Chem import QED, Descriptors
from rdkit.Chem import rdMolDescriptors
from torch_geometric.data import Data
from atom_mapping import ATOM_TO_IDX, ALLOWED_ATOMS
from config import NUM_PROPERTIES


def _calculate_sa_score(mol):
    """
    与 reconstruct.calculate_sa_score 使用同一套简化 SA 逻辑，
    保证训练标签与生成阶段评估的一致性。
    """
    try:
        ring_info = mol.GetRingInfo()
        num_rings = ring_info.NumRings()
        num_atoms = mol.GetNumAtoms()
        num_heteroatoms = sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() not in [6, 1])
        sa_score = 1.0 + 0.1 * num_rings + 0.05 * num_atoms + 0.1 * num_heteroatoms
        return min(sa_score, 10.0)
    except Exception:
        return 5.0


def smiles_to_graph(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None

    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() not in ALLOWED_ATOMS:
            return None
    
    max_allowed_atoms = 50
    if mol.GetNumAtoms() > max_allowed_atoms:
        return None

    xs = [[ATOM_TO_IDX[atom.GetAtomicNum()]] for atom in mol.GetAtoms()]
    x = torch.tensor(xs, dtype=torch.long)

    edge_indices = []
    edge_attrs = []
    
    for bond in mol.GetBonds():
        i = bond.GetBeginAtomIdx()
        j = bond.GetEndAtomIdx()
        
        bt = bond.GetBondType()
        bond_type = 1
        if bt == Chem.BondType.DOUBLE:
            bond_type = 2
        elif bt == Chem.BondType.TRIPLE:
            bond_type = 3
        elif bt == Chem.BondType.AROMATIC:
            bond_type = 4
        
        edge_indices += [[i, j], [j, i]]
        edge_attrs += [bond_type, bond_type]

    edge_index = torch.tensor(edge_indices, dtype=torch.long).t().contiguous()
    edge_attr = torch.tensor(edge_attrs, dtype=torch.long)
    
    try:
        # 按照 config.NUM_PROPERTIES 中的顺序构造标签
        qed = QED.qed(mol)                                   # 0
        logp = Descriptors.MolLogP(mol)                      # 1
        heavy_atom_count = mol.GetNumHeavyAtoms()            # 2
        ring_count = Descriptors.RingCount(mol)              # 3
        mw = Descriptors.MolWt(mol)                          # 4
        hbd = Descriptors.NumHDonors(mol)                    # 5
        hba = Descriptors.NumHAcceptors(mol)                 # 6
        rot_bonds = rdMolDescriptors.CalcNumRotatableBonds(mol)  # 7
        tpsa = rdMolDescriptors.CalcTPSA(mol)                # 8
        sa_score = _calculate_sa_score(mol)                  # 9

        y_list = [
            float(qed),
            float(logp),
            float(heavy_atom_count),
            float(ring_count),
            float(mw),
            float(hbd),
            float(hba),
            float(rot_bonds),
            float(tpsa),
            float(sa_score),
        ]

        if len(y_list) != NUM_PROPERTIES:
            return None

        y = torch.tensor([y_list], dtype=torch.float)
        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y=y)
    except Exception:
        return None


def validate_molecule(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return False
    try:
        Chem.SanitizeMol(mol)
        return True
    except Exception:
        return False