"""Local, reproducible artifacts; state dictionaries contain tensors only."""
import csv
import json
import pickle
from pathlib import Path

import torch

from src.analysis.team_role_space import ROLE_FEATURES
from src.models.tactical_encoder import CONFIG, feature_matrix


def write_json(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def write_table(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def save_artifacts(directory, model, scaler, rows, split, z, prototypes, metadata):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), directory / 'autoencoder.pt')
    torch.save(model.encoder.state_dict(), directory / 'encoder.pt')
    with (directory / 'scaler.pkl').open('wb') as f:
        pickle.dump(scaler, f, protocol=pickle.HIGHEST_PROTOCOL)
    train_raw = feature_matrix(rows)[split['train']]
    write_json(directory / 'scaler.json', dict(mean=scaler.mean_.tolist(), scale=scaler.scale_.tolist(),
        variance=scaler.var_.tolist(), n_samples_seen=int(scaler.n_samples_seen_),
        train_min=train_raw.min(0).tolist(), train_max=train_raw.max(0).tolist(),
        latent_train_mean=z[split['train']].mean(0).tolist()))
    write_json(directory / 'model_config.json', CONFIG)
    write_json(directory / 'feature_order.json', list(ROLE_FEATURES))
    write_json(directory / 'training_metadata.json', metadata)
    write_json(directory / 'role_prototypes.json', prototypes)
