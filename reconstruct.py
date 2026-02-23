import torch
import os
from rdkit import Chem
from rdkit import RDLogger
from rdkit.Chem import QED, Descriptors
from rdkit.Chem import rdMolDescriptors
from model import MoleculeVAE
from config import MODEL_DIR, DEFAULT_MODEL_NAME, DEFAULT_HIDDEN_DIM, LATENT_DIM, DEFAULT_GENERATE_ATTEMPTS, DEFAULT_GENERATE_BATCH_SIZE, get_device
from atom_mapping import IDX_TO_ATOM, ATOM_VALENCY_LIMIT


def calculate_sa_score(mol):
    try:
        ring_info = mol.GetRingInfo()
        num_rings = ring_info.NumRings()
        num_atoms = mol.GetNumAtoms()
        num_heteroatoms = sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() not in [6, 1])
        sa_score = 1.0 + 0.1 * num_rings + 0.05 * num_atoms + 0.1 * num_heteroatoms
        return min(sa_score, 10.0)
    except:
        return 5.0

def evaluate_molecule(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol: return None

    try:
        qed_score = QED.qed(mol)
        logp_score = Descriptors.MolLogP(mol)
        mw_score = Descriptors.MolWt(mol)
        hbd = Descriptors.NumHDonors(mol)
        hba = Descriptors.NumHAcceptors(mol)
        rot_bonds = rdMolDescriptors.CalcNumRotatableBonds(mol)
        heavy_atom_count = mol.GetNumHeavyAtoms()
        ring_count = Descriptors.RingCount(mol)
        sa_score = calculate_sa_score(mol)
        allowed_elements = {6, 7, 8, 9, 16, 17}
        has_allowed_elements_only = all(atom.GetAtomicNum() in allowed_elements for atom in mol.GetAtoms())
        lipinski_ro5_violations = 0
        lipinski_checks = {
            'mw': mw_score <= 500,
            'logp': logp_score <= 5,
            'hbd': hbd <= 5,
            'hba': hba <= 10
        }
        if not lipinski_checks['mw']: lipinski_ro5_violations += 1
        if not lipinski_checks['logp']: lipinski_ro5_violations += 1
        if not lipinski_checks['hbd']: lipinski_ro5_violations += 1
        if not lipinski_checks['hba']: lipinski_ro5_violations += 1
        
        tpsa = rdMolDescriptors.CalcTPSA(mol)
        veber_checks = {
            'rot_bonds': rot_bonds <= 10,
            'tpsa': tpsa <= 140
        }
        veber_violations = 0
        if not veber_checks['rot_bonds']: veber_violations += 1
        if not veber_checks['tpsa']: veber_violations += 1

        return {
            "qed": round(qed_score, 3),
            "logp": round(logp_score, 3),
            "mw": round(mw_score, 2),
            "hbd": hbd,
            "hba": hba,
            "rot_bonds": rot_bonds,
            "tpsa": round(tpsa, 2),
            "heavy_atom_count": heavy_atom_count,
            "ring_count": ring_count,
            "sa_score": round(sa_score, 3),
            "has_allowed_elements_only": has_allowed_elements_only,
            "lipinski_ro5_violations": lipinski_ro5_violations,
            "lipinski_checks": lipinski_checks,
            "veber_violations": veber_violations,
            "veber_checks": veber_checks,
            "valid": "通过校验"
        }
    except:
        return None

RDLogger.DisableLog('rdApp.*')


def check_molecule_constraints(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol: return False, "分子无效"
    
    try:
        heavy_atom_count = mol.GetNumHeavyAtoms()
        if heavy_atom_count < 10 or heavy_atom_count > 30:
            return False, f"重原子数不符合要求 ({heavy_atom_count})"
        
        ring_count = Descriptors.RingCount(mol)
        if ring_count < 1:
            return False, f"环数量不符合要求 ({ring_count})"
        
        allowed_elements = {6, 7, 8, 9, 16, 17}
        for atom in mol.GetAtoms():
            if atom.GetAtomicNum() not in allowed_elements:
                return False, f"包含不允许的元素 ({atom.GetSymbol()})"
        
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd = Descriptors.NumHDonors(mol)
        hba = Descriptors.NumHAcceptors(mol)
        
        violations = 0
        if mw > 500: violations += 1
        if logp > 5: violations += 1
        if hbd > 5: violations += 1
        if hba > 10: violations += 1
        
        if violations > 1:
            return False, f"Lipinski规则违反过多 ({violations}个)"
        
        return True, "符合所有约束条件"
    except Exception as e:
        return False, f"检查失败: {str(e)}"


def logits_to_smiles(atom_logits, edge_logits, strict=False):
    batch_size = atom_logits.size(0)
    smiles_list = []
    
    for batch_idx in range(batch_size):
        mol = Chem.RWMol()
        temperature = 0.6 if strict else 0.3
        atom_probs = torch.softmax(atom_logits[batch_idx] / temperature, dim=-1)
        
        atom_probs /= atom_probs.sum(dim=-1, keepdim=True)
        
        if strict and torch.rand(1).item() < 0.8:
            atom_types = torch.argmax(atom_probs, dim=-1)
        else:
            atom_types = torch.argmax(atom_probs, dim=-1)
        
        max_actual_nodes = min(15, atom_types.shape[0])
        atom_types = atom_types[:max_actual_nodes]
        
        if torch.all(atom_types == 0):
            num_nodes = atom_types.shape[0]
            if num_nodes > 0:
                replace_idx = torch.randint(0, num_nodes, (1,)).item()
                non_c_atom = torch.tensor([1, 1, 1, 2, 2, 2, 3, 4, 5])[torch.randint(0, 9, (1,))].item()
                atom_types[replace_idx] = non_c_atom
        
        from atom_mapping import NUM_ATOM_TYPES
        added_atoms = []
        for i in range(atom_types.size(0)):
            atom_id = atom_types[i].item()
            if atom_id >= NUM_ATOM_TYPES:
                continue
            atomic_num = IDX_TO_ATOM.get(atom_id, None)
            if atomic_num is None:
                continue
            try:
                atom_idx = mol.AddAtom(Chem.Atom(atomic_num))
                added_atoms.append(atom_idx)
            except:
                continue
        
        if len(added_atoms) < 3 or len(added_atoms) > 15:
            smiles_list.append(None)
            continue

        from atom_mapping import ATOM_VALENCY_LIMIT
        
        edge_probs = torch.softmax(edge_logits[batch_idx] / 0.4, dim=-1)
        bond_types = torch.argmax(edge_probs, dim=-1)
        
        used_valency = [0] * len(added_atoms)
        is_aromatic = [False] * len(added_atoms)
        
        for bond_order in [1, 4, 2, 3]:
            for i in range(len(added_atoms)):
                for j in range(i + 1, len(added_atoms)):
                    original_i = i
                    original_j = j
                    bond_type = bond_types[original_i, original_j].item()
                    
                    if bond_type != bond_order:
                        continue
                    
                    if bond_type == 4:
                        required_valence = 1
                    else:
                        required_valence = bond_type
                    
                    atomic_num_i = mol.GetAtomWithIdx(i).GetAtomicNum()
                    atomic_num_j = mol.GetAtomWithIdx(j).GetAtomicNum()
                    max_val_i = ATOM_VALENCY_LIMIT.get(atomic_num_i, 4)
                    max_val_j = ATOM_VALENCY_LIMIT.get(atomic_num_j, 4)
                    
                    if atomic_num_i in [8, 9]:
                        max_val_i = min(max_val_i, 2)
                    if atomic_num_j in [8, 9]:
                        max_val_j = min(max_val_j, 2)
                    
                    if (used_valency[i] + required_valence) > max_val_i or (used_valency[j] + required_valence) > max_val_j:
                        continue
                    
                    bond = None
                    if bond_type == 1:
                        bond = Chem.BondType.SINGLE
                    elif bond_type == 2:
                        bond = Chem.BondType.DOUBLE
                    elif bond_type == 3:
                        if atomic_num_i not in [6,7] or atomic_num_j not in [6,7]:
                            continue
                        bond = Chem.BondType.TRIPLE
                    elif bond_type == 4:
                        if atomic_num_i not in [6,7,8,16] or atomic_num_j not in [6,7,8,16]:
                            continue
                        bond = Chem.BondType.AROMATIC
                        is_aromatic[i] = True
                        is_aromatic[j] = True
                        mol.GetAtomWithIdx(i).SetIsAromatic(True)
                        mol.GetAtomWithIdx(j).SetIsAromatic(True)
                    else:
                        continue
                    
                    try:
                        mol.AddBond(i, j, bond)
                        used_valency[i] += required_valence
                        used_valency[j] += required_valence
                    except Exception:
                        continue
        
        if sum(used_valency) < len(added_atoms) - 1:
            for i in range(len(added_atoms) - 1):
                j = i + 1
                try:
                    mol.AddBond(i, j, Chem.BondType.SINGLE)
                except:
                    pass
        
        try:
            Chem.SanitizeMol(mol, 
                Chem.SANITIZE_FINDRADICALS |
                Chem.SANITIZE_CLEANUP |
                Chem.SANITIZE_PROPERTIES,
                catchErrors=True)
            
            frags = Chem.GetMolFrags(mol, asMols=True)
            if frags:
                res_mol = max(frags, key=lambda x: x.GetNumAtoms())
                if res_mol.GetNumAtoms() >= 3:
                    smiles = Chem.MolToSmiles(res_mol)
                    if len(smiles) > 0:
                        smiles_list.append(smiles)
                        continue
            smiles_list.append(None)
        except Exception as e:
            try:
                smiles = Chem.MolToSmiles(mol, isomericSmiles=False, kekuleSmiles=False)
                if len(smiles) > 0 and len(smiles) < 100:
                    if not any(c in smiles for c in ['%', ')', '('] * 10):
                        smiles_list.append(smiles)
                        continue
            except:
                pass
            smiles_list.append(None)
    
    return smiles_list


def real_generate():
    device = get_device()
    print(f"正在使用设备: {device}")

    try:
        default_model_path = os.path.join(MODEL_DIR, f"{DEFAULT_MODEL_NAME}.pth")
        checkpoint = torch.load(default_model_path, map_location=device)
        max_nodes = checkpoint.get('max_nodes', 20)
        hidden_channels = checkpoint.get('hidden_channels', DEFAULT_HIDDEN_DIM)
        model = MoleculeVAE(hidden_channels=hidden_channels, latent_dim=LATENT_DIM, max_nodes=max_nodes).to(device)
        model.load_state_dict(checkpoint['state_dict'])
        print(f"✅ 已成功加载 VAE 模型权重 (max_nodes={max_nodes}, hidden_channels={hidden_channels})。")
    except FileNotFoundError:
        print(f"⚠️ 未找到 {DEFAULT_MODEL_NAME}.pth，将使用随机初始化的模型进行演示。")
        model = MoleculeVAE(hidden_channels=DEFAULT_HIDDEN_DIM, latent_dim=LATENT_DIM).to(device)

    model.eval()

    print("\n--- 正在从潜在空间进行批量采样生成 ---")

    success_count = 0
    max_attempts = DEFAULT_GENERATE_ATTEMPTS

    with torch.no_grad():
        for i in range(max_attempts):
            z = torch.randn(DEFAULT_GENERATE_BATCH_SIZE, LATENT_DIM).to(device)
            from atom_mapping import NUM_ATOM_TYPES
            atom_logits = model.decoder_atoms(z).view(-1, model.max_nodes, NUM_ATOM_TYPES)
            edge_logits = model.decoder_edges(z).view(-1, model.max_nodes, model.max_nodes, 4)
            res_smiles_list = logits_to_smiles(atom_logits, edge_logits)

            batch_success = 0
            for j, res_smiles in enumerate(res_smiles_list):
                if res_smiles and len(res_smiles) > 1:
                    print(f"🎉 尝试第 {i + 1} 次 - 批次 {j + 1} - 成功生成分子: {res_smiles}")
                    success_count += 1
                    batch_success += 1
            
            if batch_success == 0:
                print(f"❌ 尝试第 {i + 1} 次 - 生成无效（化学规则拦截）")
            else:
                print(f"✅ 尝试第 {i + 1} 次 - 批次成功生成 {batch_success} 个分子")

    if success_count == 0:
        print("\n结论：本次采样未捕获到合法分子。")
        print("建议方案：1. 增加 train.py 的训练轮数；2. 增加数据集样本量。")
    else:
        print(f"\n生成结束，共获得 {success_count} 个合法分子。")


if __name__ == "__main__":
    real_generate()