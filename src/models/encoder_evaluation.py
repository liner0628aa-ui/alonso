"""Held-out metrics and the pre-registered paired-split verdict."""
from collections import Counter

import numpy as np
import torch
from sklearn.decomposition import PCA

from src.analysis.team_role_space import ROLE_FEATURES

COLLAPSE_THRESHOLD = 1e-6
NOT_BETTER = 'At this dataset size the autoencoder is comparable to or worse than the PCA baseline.'


def fit_pca(train_x):
    return PCA(n_components=4, svd_solver='full').fit(train_x)


def distances(x):
    x = np.asarray(x, dtype=float)
    return np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2)


def neighbour_overlap(raw, latent, k=5):
    if len(raw) <= k:
        raise ValueError(f'Need more than {k} rows for neighbour evaluation')
    neighbours = []
    for values in (raw, latent):
        d = distances(values)
        np.fill_diagonal(d, np.inf)
        neighbours.append(np.argsort(d, axis=1, kind='stable')[:, :k])
    overlaps = [len(set(a) & set(b)) / k for a, b in zip(*neighbours)]
    return dict(overlap=float(np.mean(overlaps)), chance=k / (len(raw) - 1), k=k, n_rows=len(raw))


def player_cohesion(values, player_ids):
    counts = Counter(player_ids)
    keep = np.array([counts[p] >= 2 for p in player_ids])
    ids = np.asarray(player_ids)[keep]
    d = distances(np.asarray(values)[keep])
    upper = np.triu(np.ones(d.shape, dtype=bool), 1)
    same = ids[:, None] == ids[None, :]
    within, between = d[upper & same], d[upper & ~same]
    a = float(within.mean()) if len(within) else None
    b = float(between.mean()) if len(between) else None
    return dict(ratio=a / b if a is not None and b is not None and b > 1e-12 else None,
                same_mean_distance=a, different_mean_distance=b,
                same_pairs=len(within), different_pairs=len(between),
                eligible_players=len(set(ids)), eligible_rows=int(keep.sum()))


def reconstruction(actual, predicted):
    per_feature = np.mean((actual - predicted) ** 2, axis=0)
    return dict(mse=float(per_feature.mean()),
                per_feature_mse=dict(zip(ROLE_FEATURES, per_feature.tolist())))


def evaluate_run(rows, split, x, model, pca):
    """Called only after best validation checkpoint has been restored."""
    with torch.no_grad():
        tensors = torch.tensor(x, dtype=torch.float32)
        z = model.encoder(tensors).numpy().astype(float)
        reconstructed = model(tensors).numpy().astype(float)
    pca_z = pca.transform(x)
    pca_reconstructed = pca.inverse_transform(pca_z)
    results = {}
    for name, idx in split.items():
        results[name] = dict(ae=reconstruction(x[idx], reconstructed[idx]),
                             pca=reconstruction(x[idx], pca_reconstructed[idx]),
                             mean=reconstruction(x[idx], np.broadcast_to(x[split['train']].mean(0), x[idx].shape)))
    test_idx = split['test']
    ids = [rows[i]['player_id'] for i in test_idx]
    for name, embedding in [('ae', z), ('pca', pca_z)]:
        overlap = neighbour_overlap(x[test_idx], embedding[test_idx])
        cohesion = player_cohesion(embedding[test_idx], ids)
        variance = embedding[test_idx].var(0)
        results['test'][name].update(neighbour_overlap=overlap['overlap'], cohesion=cohesion['ratio'],
            cohesion_details=cohesion, latent_variance=variance.tolist(),
            collapsed_dimensions=[i + 1 for i, v in enumerate(variance) if v <= COLLAPSE_THRESHOLD])
    raw_cohesion = player_cohesion(x[test_idx], ids)
    results['test']['raw'] = dict(cohesion=raw_cohesion['ratio'], cohesion_details=raw_cohesion)
    results['test']['chance'] = 5 / (len(test_idx) - 1)
    results['test']['n_rows'] = len(test_idx)
    results['latent_variance_by_split'] = {
        name: dict(ae=z[idx].var(0).tolist(), pca=pca_z[idx].var(0).tolist())
        for name, idx in split.items()}
    return results, z


def summarize_runs(runs):
    summary, differences, wins = {}, {}, {}
    for metric, sign in [('mse', -1), ('neighbour_overlap', 1), ('cohesion', -1)]:
        values = {name: np.array([r['test'][name][metric] for r in runs], dtype=float)
                  for name in ('ae', 'pca')}
        if not all(np.isfinite(v).all() for v in values.values()):
            raise ValueError(f'Undefined across-run metric: {metric}')
        summary[metric] = {name: dict(mean=float(v.mean()), std=float(v.std(ddof=1)))
                           for name, v in values.items()}
        improvement = sign * (values['ae'] - values['pca'])
        differences[metric] = dict(mean=float(improvement.mean()), std=float(improvement.std(ddof=1)))
        wins[metric] = int((improvement > 0).sum())
    for label, key in [('mean_reference_mse', ('mean', 'mse')), ('raw_cohesion', ('raw', 'cohesion'))]:
        values = np.array([r['test'][key[0]][key[1]] for r in runs])
        summary[label] = dict(mean=float(values.mean()), std=float(values.std(ddof=1)))
    chance = np.array([r['test']['chance'] for r in runs])
    summary['chance'] = dict(mean=float(chance.mean()), std=float(chance.std(ddof=1)))
    joint = sum(r['test']['ae']['mse'] < r['test']['pca']['mse'] and
                r['test']['ae']['neighbour_overlap'] > r['test']['pca']['neighbour_overlap'] for r in runs)
    clear = joint >= 8 and all(differences[m]['mean'] > differences[m]['std']
                              for m in ('mse', 'neighbour_overlap'))
    # The pre-registered rule has a binary conclusion. Do not invent a significance
    # threshold to split its fallback into statistical equivalence or inferiority.
    return dict(n_runs=len(runs), metrics=summary, paired_improvements=differences,
                ae_beats_pca=wins, joint_wins=joint, clearly_better=bool(clear),
                verdict='The autoencoder is clearly better than PCA under the pre-registered rule.' if clear else NOT_BETTER,
                model_verdict='clearly better' if clear else 'comparable')
