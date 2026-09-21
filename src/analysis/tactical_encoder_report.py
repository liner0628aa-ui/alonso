"""Render every result number from persisted metrics.json."""
import json
from pathlib import Path


def number(value):
    if value is None:
        return 'undefined'
    if isinstance(value, bool):
        return str(value)
    return f'{value:.6f}' if isinstance(value, float) else str(value)


def table(headers, rows):
    def cell(v):
        return number(v).replace('|', '\\|').replace('\n', ' ')
    lines = ['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |']
    lines.extend('| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows)
    return '\n'.join(lines)


def write_report(directory):
    out = Path(directory)
    m = json.loads((out / 'metrics.json').read_text())
    d, run, robust = m['dataset'], m['runs'][0], m['robustness']
    # Narrative added after inspecting the first completed real-data run. Every
    # numeric observation remains derived from saved metrics, never typed by hand.
    lowest_spread = min(m['seasons'], key=lambda r: r['rms_spread'])
    highest_spread = max(m['seasons'], key=lambda r: r['rms_spread'])
    cosine_first = m['wirtz']['neighbours'][0]
    euclidean_first = min(m['wirtz']['neighbours'], key=lambda r: r['euclidean_distance'])
    largest_gain = max(d['features'], key=lambda f: run['test']['pca']['per_feature_mse'][f] - run['test']['ae']['per_feature_mse'][f])
    blocks = ['# Alonso Tactical Role Encoder v1',
        'A baseline neural representation of observed 2023/24 Bayer Leverkusen player-match tactical behaviour in a low-dimensional embedding. '
        'Interpretation: **observed average tactical role in the 2023/24 Alonso system**. '
        'This document is rendered from saved `metrics.json`; CSVs and figures use the same run artifacts.',
        '## Dataset size',
        table(['Player-match rows', 'Matches', 'Players', 'Features'], [[d['rows'], d['matches'], d['players'], len(d['features'])]]),
        'M2 eligibility and feature semantics are reused unchanged. Inputs are original feature values, not M2 all-row z scores or PCA coordinates. '
        'Only existing local real data is used. Every selected input is finite. Source SHA-256: `' + d['source_sha256'] + '`.',
        '## Train/validation/test matches',
        table(['Split', 'Matches', 'Rows', 'Match IDs'], [[name, s['n_matches'], s['n_rows'], ', '.join(s['match_ids'])]
            for name, s in run['split'].items()]),
        'Sorted match IDs are permuted by the split seed and assigned to disjoint groups. StandardScaler and PCA are fitted on training rows only. '
        'Validation selects the checkpoint; test rows are first evaluated after selection. Train/validation rows are in-sample for encoder development: '
        'training fits weights and validation selects the epoch. The all-row descriptive exports include all three splits; they are not held-out evidence.',
        '## Input features',
        table(['Order', 'Feature', 'Unit', 'M2 definition'], [[i+1, r['feature'], r['unit'], r['definition']]
            for i, r in enumerate(d['feature_dictionary'])]),
        'Identity, player name, match ID, position, formation, minutes and all other context are excluded from model input. '
        'Feature order is serialized and enforced at inference.',
        '## Architecture and fixed defaults',
        '```json\n' + json.dumps(m['config'], indent=2) + '\n```',
        'The bottleneck is linear; GELU follows each hidden layer except the bottleneck and final output. '
        'Python, NumPy and torch are seeded. CPU execution uses deterministic algorithms and one torch thread. '
        'No hyperparameter search or test-guided model changes. Each robustness run changes both match partition and model/batch random seed.',
        '```json\n' + json.dumps(m['metadata']['defaults'], indent=2) + '\n```',
        '## Best epoch',
        table(['Saved seed', 'Best epoch', 'Epochs run', 'Scaler fit rows', 'PCA fit rows'],
              [[run['seed'], run['best_epoch'], run['epochs'], run['scaler_fit_rows'], run['pca_fit_rows']]]),
        'The minimum validation-loss state_dict was restored before final evaluation. Full epoch histories for every run are saved in `training_history.csv`.',
        '## Train/validation/test reconstruction MSE',
        table(['Split', 'Autoencoder', 'PCA', 'Training-mean reference'],
              [[s, run[s]['ae']['mse'], run[s]['pca']['mse'], run[s]['mean']['mse']] for s in ('train', 'val', 'test')]),
        'All errors use the same train-standardized feature units, with equal weight for each feature and each row. The reference predicts the training feature mean.',
        table(['Test feature', 'Autoencoder MSE', 'PCA MSE', 'Mean reference MSE'],
              [[f, run['test']['ae']['per_feature_mse'][f], run['test']['pca']['per_feature_mse'][f],
                run['test']['mean']['per_feature_mse'][f]] for f in d['features']]),
        '## PCA baseline',
        'The comparison uses sklearn PCA with four components and full SVD, refitted independently inside each training split. '
        'The M2 all-row PCA is not used for evaluation. Its existing loadings were inspected during preflight. '
        'The optional two-dimensional projection of neural embeddings is an all-row visualization only.',
        '## Neighbour preservation',
        table(['Test rows', 'Autoencoder overlap', 'PCA overlap', 'Chance k/(n−1)'],
              [[run['test']['n_rows'], run['test']['ae']['neighbour_overlap'], run['test']['pca']['neighbour_overlap'], run['test']['chance']]]),
        'For each test row, compare its five nearest other test rows in standardized feature space with its five nearest other test rows in the corresponding embedding. '
        'Distances are Euclidean, self-neighbours excluded, overlap is intersection size divided by five. Ties use stable input order. '
        'Chance is the expected overlap for independent uniformly random neighbour sets, not a hypothesis-test p-value.',
        '## Same-player cohesion',
        table(['Representation', 'Within/between distance ratio', 'Same-player pairs', 'Different-player pairs', 'Eligible players'],
              [[name, run['test'][name]['cohesion'], run['test'][name]['cohesion_details']['same_pairs'],
                run['test'][name]['cohesion_details']['different_pairs'], run['test'][name]['cohesion_details']['eligible_players']]
               for name in ('ae', 'pca', 'raw')]),
        'Lower ratios indicate closer same-player observations relative to different-player observations. '
        'Only players with at least two test rows enter either pair set; unordered pairs receive equal weight. '
        'This measure is confounded with position and is descriptive only. It is not part of the superiority verdict.',
        '## Latent variance and collapse diagnostics',
        table(['Dimension', 'AE train variance', 'AE test variance', 'AE all-row variance', 'PCA test variance'],
              [[f'z{i+1}', run['latent_variance_by_split']['train']['ae'][i], run['test']['ae']['latent_variance'][i],
                m['latent_variance_all_rows'][i], run['test']['pca']['latent_variance'][i]] for i in range(m['config']['latent_dim'])]),
        'Collapse flag uses absolute population variance ≤ ' + number(m['collapse_threshold']) + '. '
        'Seed-42 test collapsed AE dimensions: ' + str(run['test']['ae']['collapsed_dimensions']) + '; PCA: '
        + str(run['test']['pca']['collapsed_dimensions']) + '. This flags near-constant coordinates, not every form of redundant latent information.',
        '## 10-split robustness and pre-registered verdict',
        table(['Seed', 'Train/val/test rows', 'Best epoch', 'AE MSE', 'PCA MSE', 'AE overlap', 'PCA overlap', 'AE cohesion', 'PCA cohesion'],
              [[r['seed'], '/'.join(str(r['split'][s]['n_rows']) for s in ('train', 'val', 'test')), r['best_epoch'],
                *[r['test'][method][metric] for metric in ('mse', 'neighbour_overlap', 'cohesion') for method in ('ae', 'pca')]] for r in m['runs']]),
        table(['Metric', 'AE mean ± std', 'PCA mean ± std', 'AE wins', 'Mean improvement', 'Std of improvement'],
              [[metric, f"{number(values['ae']['mean'])} ± {number(values['ae']['std'])}",
                f"{number(values['pca']['mean'])} ± {number(values['pca']['std'])}",
                robust['ae_beats_pca'][metric], robust['paired_improvements'][metric]['mean'], robust['paired_improvements'][metric]['std']]
               for metric, values in robust['metrics'].items() if metric in ('mse', 'neighbour_overlap', 'cohesion')]),
        'Across-run standard deviations are sample standard deviations. Positive paired improvement means PCA−AE for MSE/cohesion and AE−PCA for overlap. '
        'The mean reference MSE is ' + number(robust['metrics']['mean_reference_mse']['mean']) + ' ± '
        + number(robust['metrics']['mean_reference_mse']['std']) + '; raw-space cohesion is '
        + number(robust['metrics']['raw_cohesion']['mean']) + ' ± ' + number(robust['metrics']['raw_cohesion']['std']) + '.',
        'Pre-registered rule: at least eight of ten splits must have BOTH lower AE test MSE and higher AE neighbour overlap; '
        'for EACH of those two metrics the mean paired improvement must also exceed its across-split sample standard deviation. '
        'Joint wins: **' + str(robust['joint_wins']) + '/' + str(robust['n_runs']) + '**. '
        'The split sets overlap and are not independent replications; error bars are not confidence intervals. '
        'Metrics are computed within each run. Latent vectors from different models are never pooled.',
        '**' + robust['verdict'] + '**',
        'The AE has lower reconstruction MSE in ' + str(robust['ae_beats_pca']['mse']) + ' of '
        + str(robust['n_runs']) + ' splits, but higher neighbour overlap in '
        + str(robust['ae_beats_pca']['neighbour_overlap']) + '. Reconstruction improvement therefore does not establish '
        'a better role-neighbour geometry. In the saved run the largest per-feature reconstruction reduction is for `'
        + largest_gain + '` (PCA ' + number(run['test']['pca']['per_feature_mse'][largest_gain]) + ', AE '
        + number(run['test']['ae']['per_feature_mse'][largest_gain]) + '). '
        'The categorical fallback “comparable” denotes failure to establish the pre-registered superiority claim; it is not a statistical equivalence finding.',
        '## Player embedding observations',
        table(['Player', 'Matches', 'Minutes', 'z1 mean', 'z2 mean', 'z3 mean', 'z4 mean', 'RMS spread', 'Low confidence'],
              [[r['player_name'], r['matches'], r['minutes'], *[r[f'z{j}_mean'] for j in range(1, 5)], r['rms_spread'], r['low_confidence']]
               for r in m['seasons']]),
        'Season means, medians and population standard deviations use equal weight for each eligible match. Minutes and match counts are context. '
        'Players with fewer than five eligible matches are flagged low-confidence. These are descriptions of the observed sample; no dimensions are named as tactical roles.',
        'The smallest within-player RMS spread is ' + lowest_spread['player_name'] + ' ('
        + number(lowest_spread['rms_spread']) + '); the largest is ' + highest_spread['player_name'] + ' ('
        + number(highest_spread['rms_spread']) + '). These values describe variation under this encoder and do not measure consistency of player quality. '
        'The compact goalkeeper observations visible in the plots also illustrate the influence of including that distinct position in training.',
        '## Wirtz observations',
        table(['Matches', 'Minutes', 'RMS spread', 'z1 std', 'z2 std', 'z3 std', 'z4 std'],
              [[m['wirtz']['season'][k] for k in ['matches', 'minutes', 'rms_spread', 'z1_std', 'z2_std', 'z3_std', 'z4_std']]]),
        table(['Nearest player by cosine', 'Matches', 'Cosine', 'Euclidean distance', 'Euclidean rank'],
              [[r['player_name'], r['matches'], r['cosine_similarity'], r['euclidean_distance'], r['euclidean_rank']]
               for r in m['wirtz']['neighbours'][:5]]),
        table(['Prototype excluding Wirtz', 'Rows', 'Players', 'Cosine', 'Euclidean distance'],
              [[r['group'], r['n_rows'], r['n_players'], r['cosine_similarity'], r['euclidean_distance']]
               for r in m['wirtz']['prototypes_without_wirtz']]),
        'All Wirtz rows are removed before recomputing prototype centroids and minimum group eligibility. '
        'The same training latent mean centres both comparison vectors. Wirtz still belongs to the training reference where his rows were assigned to train; '
        'this is a descriptive exclusion from prototypes, not leave-one-player-out model evaluation. '
        'The CSV contains typed season_mean, neighbour_player, player_match (with split) and prototype_without_wirtz records. '
        'These similarities describe observed tactical behaviour, not a quality comparison.',
        'The nearest season centroid by centred cosine is ' + cosine_first['player_name'] + ' (cosine '
        + number(cosine_first['cosine_similarity']) + ', Euclidean rank ' + str(cosine_first['euclidean_rank'])
        + '), while the nearest by Euclidean distance is ' + euclidean_first['player_name']
        + '. The ranking depends on the chosen geometry. The nearest eligible prototype after excluding Wirtz is `'
        + str(m['wirtz']['nearest_prototype']) + '`. This nearest broad-group centroid does not assign Wirtz a position or prove a tactical role.',
        '## Role prototype summary',
        'Position metadata comes from M2 `nominal_position`, including substitutes. The inspected position mapping is explicit:',
        '```json\n' + json.dumps(m['position_mapping'], indent=2) + '\n```',
        table(['Built group', 'Rows', 'Distinct players'], [[r['group'], r['n_rows'], r['n_players']] for r in m['prototypes']]),
        table(['Skipped group', 'Rows', 'Distinct players', 'Reason'],
              [[r['group'], r['n_rows'], r['n_players'], r['reason']] for r in m['skipped_prototypes']]),
        'A prototype needs at least twenty rows and two distinct players. Its centroid, per-dimension population variance and original-feature means use all eligible rows. '
        'General player↔prototype similarity can include the queried player in the prototype; the Wirtz-specific result excludes him. '
        'These all-row summaries must not be treated as held-out prototype validation. **Position is not role.**',
        'Skipped groups after Wirtz exclusion:',
        table(['Group', 'Rows', 'Players', 'Reason'], [[r['group'], r['n_rows'], r['n_players'], r['reason']] for r in m['wirtz']['skipped_without_wirtz']]),
        '## Latent–feature relationships',
        'Pearson and Spearman correlations use all rows. Sensitivity is mean absolute autograd derivative with respect to the train-scaled input feature. '
        'The table lists the three strongest features separately for each measure; full values are in CSV.',
    ]
    relationship_rows = []
    for i in range(1, m['config']['latent_dim'] + 1):
        dim = f'z{i}'
        subset = [r for r in m['relationships'] if r['dimension'] == dim]
        cells = [dim]
        for field in ['pearson', 'spearman', 'mean_abs_sensitivity']:
            ordered = sorted(subset, key=lambda r: abs(r[field]) if r[field] is not None else -1, reverse=True)[:3]
            cells.append('; '.join(r['feature'] + ' (' + number(r[field]) + ')' for r in ordered))
        relationship_rows.append(cells)
    blocks += [table(['Dimension', 'Top |Pearson|', 'Top |Spearman|', 'Top sensitivity'], relationship_rows),
        'These associations and sensitivities are descriptive, not causal. Autoencoder latent axes have arbitrary sign/rotation, are not identifiable '
        'and are not stable across seeds. Distances and angular relationships also depend on the learned latent geometry; reconstruction alone does not constrain '
        'that geometry to preserve neighbours. No semantic names are assigned to axes.',
        '## Inference and artifact verification',
        'Offline `encode_player_match`, `encode_player_dataset` and `compare_to_role_prototypes` are in `src/models/inference.py`. '
        'Missing, nonnumeric and non-finite features raise named errors; extra columns are ignored with warnings. '
        'Range flags compare raw inputs with the training feature min/max; a flag is descriptive and is not a calibrated out-of-distribution probability. '
        'Near-zero centred vectors have undefined cosine (JSON null). Checkpoints reload with `weights_only=True`; inference reads scaler parameters from JSON. '
        '`scaler.pkl` is also saved for local reproducibility.',
        '```json\n' + json.dumps(m['verification'], indent=2) + '\n```',
        'Library versions: `' + json.dumps(m['metadata']['library_versions']) + '`. Git commit: `'
        + str(m['metadata']['git_commit']) + '` (' + m['metadata']['git_commit_note'] + ').',
        '## Limitations',
        f"{d['matches']} matches / {d['rows']} rows / {d['players']} players is small for a neural network. "
        f"The seed-42 test set has only {run['split']['test']['n_matches']} matches. "
        'Single team, single season, single coach; no external validation. Latent axes are not identifiable. Position is not role. '
        'Player-match observations are correlated within players and matches; repeated random splits overlap and do not create more independent data. '
        'Players are shared across train/test, so the test measures held-out matches, not unseen-player generalization. '
        'The splits are random, not chronological forecasts. The eligibility filter omits short, unknown-minute and incomplete appearances. '
        'Events describe on-ball behaviour, not off-ball positioning, instructions or causal effects. Goalkeepers remain included in model training, '
        'which can influence reconstruction and geometry. Sparse features and extreme observations can dominate squared error. '
        'No confidence intervals, calibrated recruitment/system-fit score, player-quality ranking or external-player predictions are claimed.',
        '## Outputs and attribution',
        'Seven PNGs, metrics.json, full training histories, match/season embeddings, prototype tables, similarity tables and Wirtz records are saved beside this report. '
        'Model/scaler/configuration/feature-order/training metadata artifacts are in `models/alonso_tactical_encoder_v1/`. '
        'Data: StatsBomb Open Data. Retain the existing M2 attribution and source-use conditions. '
        'Milestone 3 stops at this descriptive baseline.']
    (out / 'model_report.md').write_text('\n\n'.join(blocks) + '\n')
