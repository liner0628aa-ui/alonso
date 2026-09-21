"""Seven static, real-data M3 figures. Projection is visualization only."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pyarrow.parquet as pq
from sklearn.decomposition import PCA


FIGURES = ['training_curve.png', 'embedding_player_map.png', 'embedding_by_player.png',
           'neural_similarity_heatmap.png', 'wirtz_embedding_neighbours.png',
           'autoencoder_vs_pca.png', 'latent_feature_relationships.png']


def plot_encoder_outputs(directory):
    out = Path(directory)
    m = json.loads((out / 'metrics.json').read_text())
    rows = pq.read_table(out / 'player_match_embeddings.parquet').to_pylist()
    seasons, run = m['seasons'], m['runs'][0]
    plt.rcParams.update({'font.size': 10, 'figure.facecolor': '#f8fafc', 'axes.facecolor': '#f8fafc'})
    colors = plt.get_cmap('tab20')(np.linspace(0, 1, len(seasons)))
    color_by_id = {r['player_id']: colors[i] for i, r in enumerate(seasons)}

    def save(fig, filename):
        fig.text(.015, .01, 'StatsBomb Open Data | Leverkusen 2023/24 | Observed behaviour, not player quality',
                 color='#475569', fontsize=8)
        fig.tight_layout(rect=(0, .04, 1, .98))
        fig.savefig(out / filename, dpi=160)
        plt.close(fig)

    def key_panel(ax):
        ax.axis('off')
        ax.set_title('Player / eligible matches', loc='left')
        for i, r in enumerate(seasons):
            y = .97 - i * .052
            ax.scatter(.015, y + .007, s=45, color=color_by_id[r['player_id']],
                       edgecolor='#475569', linewidth=.5, transform=ax.transAxes)
            ax.text(.05, y, f"{i+1:02d}  {r['player_name']} (n={r['matches']})",
                    color='#1e293b', transform=ax.transAxes, fontsize=9)

    fig, ax = plt.subplots(figsize=(10, 5))
    history = run['history']
    for name in ('train', 'val'):
        ax.plot([r['epoch'] for r in history], [r[name + '_loss'] for r in history], label=name)
    ax.axvline(run['best_epoch'], color='#64748b', linestyle='--', label=f"Best epoch {run['best_epoch']}")
    ax.set(xlabel='Epoch', ylabel='MSE in train-scaled feature space', title='Seed 42 | Training and validation loss')
    ax.legend(); ax.grid(alpha=.2)
    save(fig, 'training_curve.png')

    z = np.array([[r[f'z{j}'] for j in range(1, 5)] for r in rows])
    projected = PCA(n_components=2, svd_solver='full').fit_transform(z)
    fig, axes = plt.subplots(1, 3, figsize=(19, 7), gridspec_kw={'width_ratios': [1.3, 1.3, 1]})
    for ax, points, names, title in [(axes[0], z[:, :2], ('z1', 'z2'), 'Raw latent axes'),
                                    (axes[1], projected, ('Projection PC1', 'Projection PC2'), '4-D → 2-D PCA (visualization only)')]:
        for s in seasons:
            idx = [i for i, r in enumerate(rows) if r['player_id'] == s['player_id']]
            ax.scatter(points[idx, 0], points[idx, 1], color=color_by_id[s['player_id']], s=22, alpha=.65)
        ax.set(xlabel=names[0], ylabel=names[1], title=title)
        ax.grid(alpha=.2)
    key_panel(axes[2])
    fig.suptitle('All eligible player-match embeddings | Descriptive, includes development rows')
    save(fig, 'embedding_player_map.png')

    fig, (ax, key) = plt.subplots(1, 2, figsize=(13, 8), gridspec_kw={'width_ratios': [1.6, 1]})
    for i, r in enumerate(seasons):
        ax.scatter(r['z1_mean'], r['z2_mean'], s=100, color=color_by_id[r['player_id']], edgecolor='#334155')
        ax.annotate(str(i+1), (r['z1_mean'], r['z2_mean']), xytext=(5, 6), textcoords='offset points')
    ax.set(xlabel='z1 mean', ylabel='z2 mean', title='Player season centroids | Unweighted eligible matches')
    ax.grid(alpha=.2); key_panel(key)
    save(fig, 'embedding_by_player.png')

    names = [r['player_name'] for r in seasons]
    matrix = [[np.nan if r[s['player_id']] is None else r[s['player_id']] for s in seasons]
              for r in m['player_similarity']]
    fig, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(matrix, cmap='RdBu_r', vmin=-1, vmax=1)
    ax.set_xticks(range(len(names)), names, rotation=65, ha='right', fontsize=8)
    ax.set_yticks(range(len(names)), names, fontsize=8)
    ax.set_title('Season embedding cosine | Centred on training-row latent mean')
    fig.colorbar(im, ax=ax, shrink=.75, label='Cosine similarity')
    save(fig, 'neural_similarity_heatmap.png')

    neighbours = m['wirtz']['neighbours'][:5]
    fig, (ax, dist) = plt.subplots(1, 2, figsize=(14, 5), gridspec_kw={'width_ratios': [1.7, 1]})
    labels = [f"{r['player_name']} (n={r['matches']})" for r in neighbours]
    ax.barh(labels, [r['cosine_similarity'] for r in neighbours], color='#2563eb')
    ax.invert_yaxis(); ax.set(xlim=(-1, 1), xlabel='Train-mean-centred cosine', title='Wirtz | Five nearest season embeddings')
    dist.barh(range(len(labels)), [r['euclidean_distance'] for r in neighbours], color='#0d9488')
    dist.set_yticks(range(len(labels)), [f"Euclidean rank {r['euclidean_rank']}" for r in neighbours])
    dist.invert_yaxis(); dist.set(xlabel='4-D Euclidean distance', title='Cross-check | Same player order')
    save(fig, 'wirtz_embedding_neighbours.png')

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, metric, label in zip(axes, ['mse', 'neighbour_overlap', 'cohesion'],
                                ['Test reconstruction MSE ↓', 'Top-5 neighbour overlap ↑', 'Same-player distance ratio ↓']):
        methods = ['ae', 'pca']
        values = [m['robustness']['metrics'][metric][name]['mean'] for name in methods]
        error = [m['robustness']['metrics'][metric][name]['std'] for name in methods]
        ax.bar(['Autoencoder', 'PCA (4-D)'], values, yerr=error, capsize=6, color=['#2563eb', '#ea580c'])
        ref = {'mse': 'mean_reference_mse', 'neighbour_overlap': 'chance', 'cohesion': 'raw_cohesion'}[metric]
        ax.axhline(m['robustness']['metrics'][ref]['mean'], color='#64748b', linestyle='--', label=ref.replace('_', ' '))
        ax.set(title=label, ylim=(0, None)); ax.legend(fontsize=8); ax.grid(axis='y', alpha=.2)
    fig.suptitle('10 match-group splits | Mean ± sample std (not confidence intervals)')
    save(fig, 'autoencoder_vs_pca.png')

    features = m['dataset']['features']
    fig, axes = plt.subplots(1, 3, figsize=(16, 8), sharey=True)
    for ax, field, title in zip(axes, ['pearson', 'spearman', 'mean_abs_sensitivity'],
                               ['Pearson correlation', 'Spearman correlation', 'Mean |dz / dx|; x train-scaled']):
        values = np.array([[next(r[field] for r in m['relationships'] if r['dimension'] == f'z{j}' and r['feature'] == f)
                            for j in range(1, 5)] for f in features], dtype=float)
        im = ax.imshow(values, cmap='viridis' if field == 'mean_abs_sensitivity' else 'RdBu_r',
                       vmin=0 if field == 'mean_abs_sensitivity' else -1,
                       vmax=None if field == 'mean_abs_sensitivity' else 1, aspect='auto')
        ax.set_xticks(range(4), ['z1', 'z2', 'z3', 'z4'])
        ax.set_yticks(range(len(features)), features)
        ax.set_title(title, fontsize=10)
        fig.colorbar(im, ax=ax, shrink=.7)
    fig.suptitle('All-row latent–feature relationships | Descriptive, not causal')
    save(fig, 'latent_feature_relationships.png')
