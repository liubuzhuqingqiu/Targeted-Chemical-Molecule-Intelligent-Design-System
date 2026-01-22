from torch_geometric.datasets import ZINC
from torch_geometric.loader import DataLoader
import os


def get_zinc_loader(batch_size=32):

    path = os.path.join(os.getcwd(), 'data', 'ZINC')

    dataset = ZINC(path, subset=True, split='train')

    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    return loader