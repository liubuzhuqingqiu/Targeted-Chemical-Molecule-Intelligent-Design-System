import torch
from rdkit import Chem
from rdkit.Chem import QED, Descriptors
from torch_geometric.data import Data
from atom_mapping import ATOM_TO_IDX, ALLOWED_ATOMS
from config import NUM_PROPERTIES


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
        if bt == Chem.BondType.DOUBLE: bond_type = 2
        elif bt == Chem.BondType.TRIPLE: bond_type = 3
        elif bt == Chem.BondType.AROMATIC: bond_type = 1
        
        edge_indices += [[i, j], [j, i]]
        edge_attrs += [bond_type, bond_type]

    edge_index = torch.tensor(edge_indices, dtype=torch.long).t().contiguous()
    edge_attr = torch.tensor(edge_attrs, dtype=torch.long)
    
    try:
        qed = QED.qed(mol)
        logp = Descriptors.MolLogP(mol)
        heavy_atom_count = mol.GetNumHeavyAtoms()
        ring_count = Descriptors.RingCount(mol)
        mw = Descriptors.MolWt(mol)
        hbd = Descriptors.NumHDonors(mol)
        hba = Descriptors.NumHAcceptors(mol)
        y = torch.tensor([[qed, logp, heavy_atom_count, ring_count, mw, hbd, hba]], dtype=torch.float)
        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y=y)
    except:
        return None


def validate_molecule(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None: return False
    try:
        Chem.SanitizeMol(mol)
        return True
    except:
        return False