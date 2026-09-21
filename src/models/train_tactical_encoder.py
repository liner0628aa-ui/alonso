"""python -m src.models.train_tactical_encoder: the fixed Milestone 3 pipeline."""
import csv
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch

from src.analysis.team_role_space import ROLE_FEATURES
from src.models.tactical_encoder import (CONFIG, ROOT, M2_DIR, MODEL_DIR, OUTPUT_DIR,
    TacticalAutoencoder, load_m2, prepare_split, train_autoencoder)
from src.models.encoder_evaluation import evaluate_run, fit_pca, summarize_runs, COLLAPSE_THRESHOLD
from src.models.encoder_artifacts import save_artifacts, write_json, write_table
from src.models.encoder_interpretation import (POSITION_GROUPS, Z_KEYS, season_embeddings,
    build_prototypes, similarity_tables, wirtz_summary, latent_relationships)

SEEDS = list(range(42, 52))


def library_versions():
    return dict(python=platform.python_version(), **{name: importlib.metadata.version(name)
                for name in ['torch', 'numpy', 'scikit-learn', 'scipy', 'pyarrow', 'matplotlib']})


def git_commit():
    if not shutil.which('git'):
        return None
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else None


def split_description(rows, split):
    return {name: dict(match_ids=sorted({rows[i]['match_id'] for i in idx}), n_rows=len(idx),
                       n_matches=len({rows[i]['match_id'] for i in idx})) for name, idx in split.items()}


def export_wirtz(summary, out):
    query = dict(record_type='season_mean', **summary['season'])
    query.update({k: summary['season'][k + '_mean'] for k in Z_KEYS})
    records = [query]
    records += [dict(record_type='neighbour_player', **r) for r in summary['neighbours']]
    records += [dict(record_type='player_match', **r) for r in summary['matches']]
    records += [dict(record_type='prototype_without_wirtz', **r) for r in summary['prototypes_without_wirtz']]
    write_table(out / 'wirtz_embedding_neighbours.csv', records)


def run_pipeline():
    # All assertions occur before training or replacing any artifacts.
    rows = load_m2()
    source = M2_DIR / 'player_match_tactical_features.parquet'
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    feature_dictionary = list(csv.DictReader((M2_DIR / 'feature_dictionary.csv').open()))
    positions = sorted({r['nominal_position'] for r in rows if r.get('nominal_position')})
    if set(positions) - POSITION_GROUPS.keys():
        raise ValueError(f'Unexpected position labels: {set(positions) - POSITION_GROUPS.keys()}')
    # Wirtz lookup is by name, before any model work.
    assert len({r['player_id'] for r in rows if 'wirtz' in r['player_name'].casefold()}) == 1
    previous_path = OUTPUT_DIR / 'metrics.json'
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else None
    runs, saved = [], None
    for seed in SEEDS:
        split, scaler, x = prepare_split(rows, seed)
        model, history, best_epoch = train_autoencoder(x[split['train']], x[split['val']], seed)
        pca = fit_pca(x[split['train']])
        result, z = evaluate_run(rows, split, x, model, pca)
        result.update(seed=seed, split=split_description(rows, split), best_epoch=best_epoch,
                      epochs=len(history), history=history,
                      scaler_fit_rows=int(scaler.n_samples_seen_), pca_fit_rows=int(pca.n_samples_))
        runs.append(result)
        if seed == 42:
            saved = dict(model=model, scaler=scaler, split=split, x=x, z=z, pca=pca)
        print(f"seed={seed} best_epoch={best_epoch} epochs={len(history)} "
              f"test_mse AE={result['test']['ae']['mse']:.6f} PCA={result['test']['pca']['mse']:.6f}", flush=True)

    model, scaler, split, x, z = (saved[k] for k in ['model', 'scaler', 'split', 'x', 'z'])
    train_center = z[split['train']].mean(0)
    labels = [''] * len(rows)
    for name, idx in split.items():
        for i in idx:
            labels[i] = name
    seasons = season_embeddings(rows, z)
    prototypes, skipped = build_prototypes(rows, z)
    similarity, role_similarity = similarity_tables(seasons, prototypes, train_center)
    wirtz = wirtz_summary(rows, z, labels, seasons, train_center)
    relationships = latent_relationships(model, x, z)
    first = runs[0]
    metadata = dict(seed=42, seeds=SEEDS, split=first['split'], epochs=first['epochs'],
        best_epoch=first['best_epoch'], losses={name: first[name]['ae'] for name in split},
        history=first['history'], feature_list=list(ROLE_FEATURES), library_versions=library_versions(),
        git_commit=git_commit(), git_commit_note='Unavailable if git executable or commit metadata is absent.',
        source_sha256=source_hash, source_path=str(source.relative_to(ROOT)),
        config=CONFIG, scaler_fit='train only', pca_fit='train only',
        checkpoint_selection='validation MSE only; restore best; test evaluated afterwards',
        season_aggregation='unweighted eligible match mean/median/population std',
        prototype_scope='all eligible rows, descriptive; Wirtz comparison excludes all Wirtz rows',
        collapse_threshold=COLLAPSE_THRESHOLD,
        defaults=dict(split_method='seeded permutation of sorted match IDs; 24/5/5 matches',
            same_player_cohesion='unordered Euclidean pairs among players with >=2 test rows in both pair sets',
            variance='population variance', across_split_std='sample standard deviation (ddof=1)',
            verdict='>=8 joint wins AND paired mean improvement > paired across-split sample std for BOTH primary metrics',
            latent_activation='linear', seeds='42..51 used for split, initialization and batch order',
            extra_dependencies='pytest is a validation tool; torch is the only new direct runtime dependency'))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_artifacts(MODEL_DIR, model, scaler, rows, split, z, prototypes, metadata)
    write_json(MODEL_DIR / 'pca_baseline.json', dict(components=saved['pca'].components_.tolist(),
        mean=saved['pca'].mean_.tolist(), explained_variance_ratio=saved['pca'].explained_variance_ratio_.tolist()))
    context_keys = ['match_id', 'match_date', 'player_id', 'player_name', 'minutes', 'nominal_position',
                    'starting_position', 'formation', 'opponent_name', 'home_away']
    embedded = [dict({k: r.get(k) for k in context_keys}, split=labels[i],
        **dict(zip(Z_KEYS, z[i].tolist()))) for i, r in enumerate(rows)]
    pq.write_table(pa.Table.from_pylist(embedded), OUTPUT_DIR / 'player_match_embeddings.parquet', compression='zstd')
    write_table(OUTPUT_DIR / 'player_season_embeddings.csv', seasons)
    write_table(OUTPUT_DIR / 'role_prototypes_v1.csv', prototypes)
    write_table(OUTPUT_DIR / 'skipped_role_prototypes.csv', skipped)
    write_table(OUTPUT_DIR / 'player_similarity_matrix.csv', similarity)
    write_table(OUTPUT_DIR / 'player_prototype_similarity.csv', role_similarity)
    write_table(OUTPUT_DIR / 'latent_feature_relationships.csv', relationships)
    write_table(OUTPUT_DIR / 'training_history.csv', [dict(seed=r['seed'], **h) for r in runs for h in r['history']])
    write_table(OUTPUT_DIR / 'robustness_runs.csv', [dict(seed=r['seed'], best_epoch=r['best_epoch'],
        **{f'{method}_{metric}': r['test'][method][metric] for method in ('ae', 'pca')
           for metric in ('mse', 'neighbour_overlap', 'cohesion')}, chance=r['test']['chance']) for r in runs])
    export_wirtz(wirtz, OUTPUT_DIR)
    from src.models.inference import EncoderInference
    inference = EncoderInference(MODEL_DIR)
    encoded = inference.encode_player_dataset([{k: r[k] for k in ROLE_FEATURES} for r in rows])
    reloaded_z = np.array([r['embedding'] for r in encoded])
    reload_error = float(np.max(np.abs(reloaded_z - z)))
    np.testing.assert_allclose(reloaded_z, z, atol=1e-6, rtol=1e-6)
    reloaded_model = TacticalAutoencoder()
    reloaded_model.load_state_dict(torch.load(MODEL_DIR / 'autoencoder.pt', weights_only=True, map_location='cpu'))
    test_tensor = torch.tensor(x[split['test']], dtype=torch.float32)
    with torch.no_grad():
        np.testing.assert_allclose(reloaded_model(test_tensor).numpy(), model(test_tensor).numpy(), atol=1e-7)
    reproducibility = dict(previous_run_available=False, tolerance=1e-5)
    if previous and previous['dataset']['source_sha256'] == source_hash and previous['config'] == CONFIG:
        old_mse = previous['runs'][0]['test']['ae']['mse']
        new_mse = first['test']['ae']['mse']
        delta = abs(old_mse - new_mse)
        reproducibility.update(previous_run_available=True, previous_test_mse=old_mse,
                               current_test_mse=new_mse, absolute_difference=delta, passed=delta <= 1e-5)
        if delta > 1e-5:
            raise AssertionError(f'Seed-42 repeat test MSE changed by {delta}')
    metrics = dict(name='Alonso Tactical Role Encoder v1', config=CONFIG,
        dataset=dict(rows=len(rows), matches=len({r['match_id'] for r in rows}),
                     players=len(seasons), features=list(ROLE_FEATURES), source_sha256=source_hash,
                     actual_positions=positions, feature_dictionary=feature_dictionary),
        metadata=metadata, runs=runs, robustness=summarize_runs(runs), seasons=seasons,
        prototypes=prototypes, skipped_prototypes=skipped, position_mapping=POSITION_GROUPS,
        wirtz=wirtz, relationships=relationships, latent_variance_all_rows=z.var(0).tolist(),
        collapse_threshold=COLLAPSE_THRESHOLD, player_similarity=similarity,
        verification=dict(encoder_reload_max_absolute_error=reload_error,
                          autoencoder_reload_passed=True, reproducibility=reproducibility))
    write_json(OUTPUT_DIR / 'metrics.json', metrics)
    # Reports and figures consume persisted metrics; no hand-entered result numbers.
    from src.analysis.tactical_encoder_plots import plot_encoder_outputs
    from src.analysis.tactical_encoder_report import write_report
    plot_encoder_outputs(OUTPUT_DIR)
    write_report(OUTPUT_DIR)
    print(json.dumps(dict(seed42_test=first['test'], robustness=metrics['robustness'],
                          verification=metrics['verification']), indent=2), flush=True)
    return metrics


if __name__ == '__main__':
    run_pipeline()
