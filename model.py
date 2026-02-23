import torch
import torch.nn as nn
from torch_geometric.nn import GCNConv, global_mean_pool
from atom_mapping import NUM_ATOM_TYPES
from config import NUM_PROPERTIES


class MoleculeVAE(nn.Module):
    def __init__(self, hidden_channels=64, latent_dim=32, max_nodes=20):
        super(MoleculeVAE, self).__init__()
        self.max_nodes = max_nodes
        self.latent_dim = latent_dim
        self.embedding = nn.Embedding(100, hidden_channels)
        self.conv1 = GCNConv(hidden_channels, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels)
        self.conv3 = GCNConv(hidden_channels, hidden_channels)
        self.mu = nn.Linear(hidden_channels, latent_dim)
        self.logvar = nn.Linear(hidden_channels, latent_dim)
        self.decoder_atoms = nn.Sequential(
            nn.Linear(latent_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Linear(128, max_nodes * NUM_ATOM_TYPES)
        )
        self.decoder_edges = nn.Sequential(
            nn.Linear(latent_dim, 256),
            nn.ReLU(),
            nn.BatchNorm1d(256),
            nn.Linear(256, max_nodes * max_nodes * 4)
        )
        self.num_predictors = 5
        self.predictors = nn.ModuleList()
        for _ in range(self.num_predictors):
            predictor = nn.Sequential(
                nn.Linear(latent_dim, 64),
                nn.ReLU(),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Linear(32, NUM_PROPERTIES)
            )
            for layer in predictor:
                if isinstance(layer, nn.Linear):
                    nn.init.xavier_uniform_(layer.weight)
                    if layer.bias is not None:
                        nn.init.zeros_(layer.bias)
            self.predictors.append(predictor)
        
        self.predictor = self.predictors[0]

    def encode(self, x, edge_index, batch):
        x = self.embedding(x.squeeze().long())
        x = self.conv1(x, edge_index).relu()
        x = self.conv2(x, edge_index).relu()
        x = self.conv3(x, edge_index).relu()
        x = global_mean_pool(x, batch)
        return self.mu(x), self.logvar(x)

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def predict_properties(self, z):
        return self.predictor(z)
    
    def predict_properties_ensemble(self, z):
        predictions = []
        for predictor in self.predictors:
            predictions.append(predictor(z))
        return torch.stack(predictions)
    
    def check_all_predictors_favorable(self, z, constraints):
        with torch.no_grad():
            all_predictions = self.predict_properties_ensemble(z)
            batch_size = z.size(0)
            
            for b in range(batch_size):
                favorable_count = 0
                for pred in all_predictions:
                    qed_pred = pred[b, 0].item()
                    logp_pred = pred[b, 1].item()
                    mw_pred = pred[b, 4].item()
                    hbd_pred = pred[b, 5].item()
                    hba_pred = pred[b, 6].item()
                    
                    is_favorable = True
                    is_favorable &= (qed_pred >= constraints.get('qed_min', 0.0))
                    is_favorable &= (logp_pred >= constraints.get('logp_range', [-float('inf'), float('inf')])[0])
                    is_favorable &= (logp_pred <= constraints.get('logp_range', [-float('inf'), float('inf')])[1])
                    is_favorable &= (mw_pred >= constraints.get('mw_range', [0, float('inf')])[0])
                    is_favorable &= (mw_pred <= constraints.get('mw_range', [0, float('inf')])[1])
                    is_favorable &= (hbd_pred <= constraints.get('hbd_max', float('inf')))
                    is_favorable &= (hba_pred <= constraints.get('hba_max', float('inf')))
                    
                    if is_favorable:
                        favorable_count += 1
                
                if favorable_count == len(self.predictors):
                    return True
            
            return False

    def forward(self, data):
        mu, logvar = self.encode(data.x, data.edge_index, data.batch)
        z = self.reparameterize(mu, logvar)
        atom_logits = self.decoder_atoms(z).view(-1, self.max_nodes, NUM_ATOM_TYPES)
        edge_logits = self.decoder_edges(z).view(-1, self.max_nodes, self.max_nodes, 4)
        all_properties = self.predict_properties_ensemble(z)
        properties = all_properties[0]
        return atom_logits, edge_logits, mu, logvar, properties, all_properties