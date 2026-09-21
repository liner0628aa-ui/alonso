"""Fixed CPU baseline and the existing M2 feature contract. No ingestion."""
import copy
import csv
import random
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import torch
from sklearn.preprocessing import StandardScaler
from torch import nn

from src.analysis.team_role_space import ROLE_FEATURES

ROOT = Path(__file__).resolve().parents[2]
M2_DIR = ROOT / 'outputs/alonso_team_role_space'
MODEL_DIR = ROOT / 'models/alonso_tactical_encoder_v1'
OUTPUT_DIR = ROOT / 'outputs/alonso_tactical_encoder_v1'
CONFIG = dict(architecture=[15, 12, 8, 4, 8, 12, 15], activation='GELU',
              bottleneck_activation='linear', output_activation='linear',
              latent_dim=4, loss='MSE', optimizer='Adam', lr=1e-3,
              weight_decay=1e-5, batch_size=32, max_epochs=500, patience=40,
              min_delta=0.0, device='cpu', threads=1)


def feature_matrix(rows, feature_order=ROLE_FEATURES):
    """Strict ordered numeric features; caller handles extra-column warnings."""
    matrix = []
    for i, row in enumerate(rows):
        missing = [k for k in feature_order if k not in row]
        if missing:
            raise ValueError(f'Row {i}: missing features: {", ".join(missing)}')
        values = []
        for key in feature_order:
            value = row[key]
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.number)) or np.iscomplexobj(value):
                raise ValueError(f'Row {i}: non-numeric feature {key}: {value!r}')
            if not np.isfinite(value):
                raise ValueError(f'Row {i}: NaN or inf in feature {key}')
            values.append(float(value))
        matrix.append(values)
    if not matrix:
        raise ValueError('Empty player-match dataset')
    return np.asarray(matrix, dtype=np.float64)


def load_m2(directory=M2_DIR):
    """Preserve M2's eligibility, order and raw feature semantics exactly."""
    directory = Path(directory)
    with (directory / 'feature_dictionary.csv').open() as f:
        dictionary = list(csv.DictReader(f))
    if [r['feature'] for r in dictionary] != list(ROLE_FEATURES):
        raise AssertionError('M2 feature dictionary/order differs from ROLE_FEATURES')
    rows = [r for r in pq.read_table(directory / 'player_match_tactical_features.parquet').to_pylist()
            if r['analysis_eligible']]
    counts = (len(rows), len({r['match_id'] for r in rows}),
              len({r['player_id'] for r in rows}), len(ROLE_FEATURES))
    if counts != (376, 34, 18, 15):
        raise AssertionError(f'M2 preflight mismatch: rows/matches/players/features={counts}')
    feature_matrix(rows)
    if len({(r['match_id'], r['player_id']) for r in rows}) != len(rows):
        raise AssertionError('Duplicate player-match rows')
    return rows


def split_matches(rows, seed):
    match_ids = np.array(sorted({r['match_id'] for r in rows}))
    if len(match_ids) != 34:
        raise ValueError('Expected the existing 34-match M2 dataset')
    shuffled = np.random.default_rng(seed).permutation(match_ids)
    groups = dict(train=set(shuffled[:24]), val=set(shuffled[24:29]), test=set(shuffled[29:]))
    return {name: np.array([i for i, r in enumerate(rows) if r['match_id'] in matches], dtype=int)
            for name, matches in groups.items()}


def prepare_split(rows, seed):
    split = split_matches(rows, seed)
    raw = feature_matrix(rows)
    scaler = StandardScaler().fit(raw[split['train']])
    return split, scaler, scaler.transform(raw)


class TacticalAutoencoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(15, 12), nn.GELU(), nn.Linear(12, 8),
                                     nn.GELU(), nn.Linear(8, 4))
        self.decoder = nn.Sequential(nn.Linear(4, 8), nn.GELU(), nn.Linear(8, 12),
                                     nn.GELU(), nn.Linear(12, 15))

    def forward(self, x):
        return self.decoder(self.encoder(x))


def train_autoencoder(train_x, val_x, seed, max_epochs=500):
    """Only training and validation arrays enter this function."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(CONFIG['threads'])
    torch.use_deterministic_algorithms(True)
    model = TacticalAutoencoder().cpu()
    train = torch.tensor(train_x, dtype=torch.float32, device='cpu')
    val = torch.tensor(val_x, dtype=torch.float32, device='cpu')
    optimizer = torch.optim.Adam(model.parameters(), lr=CONFIG['lr'], weight_decay=CONFIG['weight_decay'])
    generator = torch.Generator(device='cpu').manual_seed(seed)
    best_loss, best_epoch, stale, best_state = float('inf'), 0, 0, None
    history = []
    for epoch in range(1, max_epochs + 1):
        model.train()
        order = torch.randperm(len(train), generator=generator)
        for batch in order.split(CONFIG['batch_size']):
            optimizer.zero_grad(set_to_none=True)
            loss = torch.mean((model(train[batch]) - train[batch]) ** 2)
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            train_loss = float(torch.mean((model(train) - train) ** 2))
            val_loss = float(torch.mean((model(val) - val) ** 2))
        if not np.isfinite([train_loss, val_loss]).all():
            raise RuntimeError(f'Non-finite loss at epoch {epoch}')
        history.append(dict(epoch=epoch, train_loss=train_loss, val_loss=val_loss))
        if val_loss < best_loss:
            best_loss, best_epoch, stale = val_loss, epoch, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            stale += 1
        if stale >= CONFIG['patience']:
            break
    model.load_state_dict(best_state)
    model.eval()
    return model, history, best_epoch
