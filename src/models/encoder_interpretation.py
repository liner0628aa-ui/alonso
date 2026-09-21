"""Descriptive all-row summaries, separate from held-out evaluation."""
from collections import defaultdict

import numpy as np
import torch
from scipy.stats import rankdata

from src.analysis.team_role_space import ROLE_FEATURES, cosine

# All observed M2 nominal_position values, inspected before choosing this mapping.
POSITION_GROUPS = {
    'Goalkeeper': 'goalkeeper',
    'Left Center Back': 'centre_back', 'Center Back': 'centre_back',
    'Right Center Back': 'centre_back',
    'Left Wing Back': 'wing_back', 'Right Wing Back': 'wing_back',
    'Left Back': 'full_back',
    'Left Defensive Midfield': 'central_midfielder',
    'Right Defensive Midfield': 'central_midfielder',
    'Left Attacking Midfield': 'attacking_midfielder',
    'Right Attacking Midfield': 'attacking_midfielder',
    'Center Attacking Midfield': 'attacking_midfielder',
    'Left Wing': 'winger', 'Right Wing': 'winger',
    'Center Forward': 'striker', 'Left Center Forward': 'striker',
}
Z_KEYS = ['z1', 'z2', 'z3', 'z4']


def season_embeddings(rows, z):
    index = defaultdict(list)
    for i, r in enumerate(rows):
        index[r['player_id']].append(i)
    seasons = []
    for pid, idx in sorted(index.items(), key=lambda p: rows[p[1][0]]['player_name']):
        row = dict(player_id=pid, player_name=rows[idx[0]]['player_name'],
                   matches=len(idx), minutes=float(sum(rows[i]['minutes'] for i in idx)),
                   low_confidence=len(idx) < 5)
        for j, key in enumerate(Z_KEYS):
            row.update({key + '_mean': float(z[idx, j].mean()),
                        key + '_median': float(np.median(z[idx, j])),
                        key + '_std': float(z[idx, j].std(ddof=0))})
        row['rms_spread'] = float(np.sqrt(np.mean(np.sum((z[idx] - z[idx].mean(0)) ** 2, axis=1))))
        seasons.append(row)
    return seasons


def build_prototypes(rows, z, exclude_player=None):
    groups = defaultdict(list)
    for i, r in enumerate(rows):
        if r['player_id'] == exclude_player:
            continue
        position = r.get('nominal_position')
        if position not in POSITION_GROUPS:
            if position is not None:
                raise ValueError(f'Unmapped position label: {position}')
            groups['unknown_position'].append(i)
        else:
            groups[POSITION_GROUPS[position]].append(i)
    prototypes, skipped = [], []
    for group, idx in sorted(groups.items()):
        record = dict(group=group, n_rows=len(idx), n_players=len({rows[i]['player_id'] for i in idx}))
        reasons = []
        if group == 'unknown_position':
            reasons.append('position unavailable')
        if record['n_rows'] < 20:
            reasons.append('fewer than 20 rows')
        if record['n_players'] < 2:
            reasons.append('fewer than 2 distinct players')
        if reasons:
            skipped.append(dict(record, reason='; '.join(reasons)))
            continue
        for j, key in enumerate(Z_KEYS):
            record[key] = float(z[idx, j].mean())
            record[key + '_variance'] = float(z[idx, j].var(ddof=0))
        record.update({k + '_mean': float(np.mean([rows[i][k] for i in idx])) for k in ROLE_FEATURES})
        prototypes.append(record)
    return prototypes, skipped


def compare_embeddings(a, b, train_center):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    center = np.asarray(train_center, dtype=float)
    return dict(cosine_similarity=cosine(a - center, b - center),
                euclidean_distance=float(np.linalg.norm(a - b)))


def rank_comparisons(records):
    """Rank undefined cosine last; keep a separate Euclidean cross-check rank."""
    ordered = sorted(records, key=lambda r: (r['cosine_similarity'] is None,
                                            -(r['cosine_similarity'] or 0), r.get('player_id', r.get('group', ''))))
    euclidean = sorted(records, key=lambda r: r['euclidean_distance'])
    ranks = {id(r): i + 1 for i, r in enumerate(euclidean)}
    return [dict(r, cosine_rank=i + 1, euclidean_rank=ranks[id(r)]) for i, r in enumerate(ordered)]


def similarity_tables(seasons, prototypes, train_center):
    centers = np.array([[r[k + '_mean'] for k in Z_KEYS] for r in seasons])
    matrix, pairs = [], []
    for i, player in enumerate(seasons):
        matrix.append(dict(player_id=player['player_id'], player_name=player['player_name'],
            **{other['player_id']: compare_embeddings(centers[i], centers[j], train_center)['cosine_similarity']
               for j, other in enumerate(seasons)}))
        for prototype in prototypes:
            pairs.append(dict(player_id=player['player_id'], player_name=player['player_name'],
                group=prototype['group'], **compare_embeddings(centers[i], [prototype[k] for k in Z_KEYS], train_center)))
    return matrix, pairs


def wirtz_summary(rows, z, split_labels, seasons, train_center):
    ids = {r['player_id'] for r in rows if 'wirtz' in r['player_name'].casefold()}
    if len(ids) != 1:
        raise AssertionError(f'Expected one player found by Wirtz name, got {ids}')
    pid = next(iter(ids))
    season = next(r for r in seasons if r['player_id'] == pid)
    centroid = np.array([season[k + '_mean'] for k in Z_KEYS])
    neighbours = rank_comparisons([dict(player_id=r['player_id'], player_name=r['player_name'],
        matches=r['matches'], **{k: r[k + '_mean'] for k in Z_KEYS},
        **compare_embeddings(centroid, [r[k + '_mean'] for k in Z_KEYS], train_center))
        for r in seasons if r['player_id'] != pid])
    prototypes, skipped = build_prototypes(rows, z, exclude_player=pid)
    roles = rank_comparisons([dict(group=p['group'], n_rows=p['n_rows'], n_players=p['n_players'],
        **{k: p[k] for k in Z_KEYS}, **compare_embeddings(centroid, [p[k] for k in Z_KEYS], train_center))
        for p in prototypes])
    matches = [dict(match_id=r['match_id'], player_id=pid, player_name=r['player_name'], minutes=r['minutes'],
        split=split_labels[i], **dict(zip(Z_KEYS, z[i].tolist())),
        distance_to_season_mean=float(np.linalg.norm(z[i] - centroid)))
        for i, r in enumerate(rows) if r['player_id'] == pid]
    return dict(player_id=pid, player_name=season['player_name'], season=season,
                neighbours=neighbours, matches=matches, prototypes_without_wirtz=roles,
                skipped_without_wirtz=skipped, nearest_prototype=roles[0]['group'] if roles else None)


def latent_relationships(model, x, z):
    """Correlations and |dz/dx| with respect to train-standardized features."""
    inputs = torch.tensor(x, dtype=torch.float32, requires_grad=True)
    latent = model.encoder(inputs)
    gradients = [torch.autograd.grad(latent[:, j].sum(), inputs, retain_graph=j < 3)[0]
                 .abs().mean(0).detach().numpy() for j in range(4)]
    results = []
    for j, key in enumerate(Z_KEYS):
        for k, feature in enumerate(ROLE_FEATURES):
            if np.std(z[:, j]) <= 1e-12 or np.std(x[:, k]) <= 1e-12:
                pearson, spearman = None, None
            else:
                pearson = float(np.corrcoef(z[:, j], x[:, k])[0, 1])
                spearman = float(np.corrcoef(rankdata(z[:, j]), rankdata(x[:, k]))[0, 1])
            results.append(dict(dimension=key, feature=feature, pearson=pearson, spearman=spearman,
                                mean_abs_sensitivity=float(gradients[j][k])))
    return results
