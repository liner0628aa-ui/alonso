"""Offline encoder inference with strict ordered tactical features."""
import json
import warnings
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch

from src.models.tactical_encoder import MODEL_DIR, TacticalAutoencoder, feature_matrix
from src.models.encoder_interpretation import Z_KEYS, compare_embeddings, rank_comparisons


class EncoderInference:
    def __init__(self, model_dir=MODEL_DIR):
        directory = Path(model_dir)
        self.feature_order = json.loads((directory / 'feature_order.json').read_text())
        if len(self.feature_order) != 15 or len(set(self.feature_order)) != 15:
            raise ValueError('feature_order.json must contain 15 unique feature names')
        self.scaler = json.loads((directory / 'scaler.json').read_text())
        self.prototypes = json.loads((directory / 'role_prototypes.json').read_text())
        self.model = TacticalAutoencoder().cpu()
        self.model.encoder.load_state_dict(torch.load(directory / 'encoder.pt', map_location='cpu', weights_only=True))
        self.model.eval()

    def compare_to_role_prototypes(self, embedding):
        try:
            vector = np.asarray(embedding, dtype=float)
        except (ValueError, TypeError) as exc:
            raise ValueError('embedding must contain four finite numeric values') from exc
        if vector.shape != (4,) or not np.isfinite(vector).all():
            raise ValueError('embedding must contain four finite numeric values')
        return rank_comparisons([dict(group=p['group'], n_rows=p['n_rows'], n_players=p['n_players'],
            **compare_embeddings(vector, [p[k] for k in Z_KEYS], self.scaler['latent_train_mean']))
            for p in self.prototypes])

    def encode_player_match(self, features):
        if not isinstance(features, Mapping):
            raise ValueError('features must be a mapping with the 15 named tactical features')
        return self.encode_player_dataset([features])[0]

    def encode_player_dataset(self, df):
        column_names = (df.column_names if hasattr(df, 'column_names')
                        else df.columns if hasattr(df, 'columns') else None)
        if column_names is not None and len(set(column_names)) != len(column_names):
            raise ValueError('Duplicate feature columns in dataset')
        if hasattr(df, 'to_pylist'):
            records = df.to_pylist()
        elif hasattr(df, 'to_dict') and not isinstance(df, Mapping):
            records = df.to_dict(orient='records')
        elif isinstance(df, (list, tuple)):
            records = list(df)
        else:
            raise ValueError('dataset must be a dataframe, Arrow table, or list of row mappings')
        if any(not isinstance(r, Mapping) for r in records):
            raise ValueError('Each dataset row must be a mapping of named features')
        raw = feature_matrix(records, self.feature_order)
        extra = sorted({str(k) for r in records for k in r if k not in self.feature_order})
        if extra:
            warnings.warn('Extra columns ignored: ' + ', '.join(extra), UserWarning, stacklevel=2)
        x = (raw - self.scaler['mean']) / self.scaler['scale']
        # Catch overflow before sending extreme but finite inputs into float32 layers.
        if not np.isfinite(x).all() or np.any(np.abs(x) > np.finfo(np.float32).max):
            bad = np.where((~np.isfinite(x)) | (np.abs(x) > np.finfo(np.float32).max))[1]
            raise ValueError('Features outside supported numeric range: ' + ', '.join(self.feature_order[j] for j in sorted(set(bad))))
        with torch.no_grad():
            embeddings = self.model.encoder(torch.tensor(x, dtype=torch.float32)).numpy()
        if not np.isfinite(embeddings).all():
            raise ValueError('Input features produce non-finite embedding; values exceed model numeric range')
        output = []
        for row, vector in zip(raw, embeddings):
            outside = (row < self.scaler['train_min']) | (row > self.scaler['train_max'])
            compared = self.compare_to_role_prototypes(vector)
            nearest = compared[0] if compared else None
            output.append(dict(embedding=vector.tolist(),
                nearest_prototype=nearest['group'] if nearest else None,
                cosine_similarity=nearest['cosine_similarity'] if nearest else None,
                prototype_euclidean_distance=nearest['euclidean_distance'] if nearest else None,
                feature_availability=dict(all_present=True, available_features=self.feature_order, missing_features=[]),
                out_of_range=bool(outside.any()),
                out_of_range_features=[k for k, flag in zip(self.feature_order, outside) if flag],
                prototype_comparisons=compared))
        return output


@lru_cache(maxsize=1)
def _default_encoder():
    return EncoderInference()


def encode_player_match(features):
    return _default_encoder().encode_player_match(features)


def encode_player_dataset(df):
    return _default_encoder().encode_player_dataset(df)


def compare_to_role_prototypes(embedding):
    return _default_encoder().compare_to_role_prototypes(embedding)
