"""Real-row inference and descriptive prototype boundary tests."""
import numpy as np
import pytest
import torch


@pytest.fixture(scope='module')
def artifact(tmp_path_factory):
    from src.models.tactical_encoder import load_m2, prepare_split, train_autoencoder
    from src.models.encoder_artifacts import save_artifacts
    from src.models.encoder_interpretation import build_prototypes
    from src.models.inference import EncoderInference
    rows = load_m2()
    split, scaler, x = prepare_split(rows, 42)
    model, history, best = train_autoencoder(x[split['train']], x[split['val']], 42, max_epochs=2)
    z = model.encoder(torch.tensor(x, dtype=torch.float32)).detach().numpy()
    prototypes, _ = build_prototypes(rows, z)
    directory = tmp_path_factory.mktemp('encoder')
    save_artifacts(directory, model, scaler, rows, split, z, prototypes,
                   dict(seed=42, best_epoch=best, history=history))
    return EncoderInference(directory), rows, z, directory


def test_saved_inference_reproduces_embedding_and_ignores_metadata(artifact):
    from src.analysis.team_role_space import ROLE_FEATURES
    engine, rows, z, directory = artifact
    row = {key: rows[0][key] for key in reversed(ROLE_FEATURES)}
    result = engine.encode_player_match(row)
    np.testing.assert_allclose(result['embedding'], z[0], atol=1e-6)
    assert result['feature_availability']['all_present']
    assert len(result['feature_availability']['available_features']) == 15
    assert {'nearest_prototype', 'cosine_similarity', 'prototype_euclidean_distance',
            'out_of_range', 'out_of_range_features'} <= result.keys()
    with pytest.warns(UserWarning, match='Extra columns'):
        again = engine.encode_player_match(dict(row, minutes=999999, player_name='ignored'))
    np.testing.assert_allclose(again['embedding'], result['embedding'], atol=1e-7)
    assert (directory / 'encoder.pt').is_file()
    assert (directory / 'autoencoder.pt').is_file()


@pytest.mark.parametrize('value', ['1.2', None, True, float('nan'), float('inf')])
def test_invalid_feature_names_problem(artifact, value):
    from src.analysis.team_role_space import ROLE_FEATURES
    engine, rows, _, _ = artifact
    row = {k: rows[0][k] for k in ROLE_FEATURES}
    row['passes_p90'] = value
    with pytest.raises(ValueError, match='passes_p90'):
        engine.encode_player_match(row)


def test_missing_feature_not_replaced_by_wrong_name(artifact):
    from src.analysis.team_role_space import ROLE_FEATURES
    engine, rows, _, _ = artifact
    row = {k: rows[0][k] for k in ROLE_FEATURES}
    row['wrong_passes'] = row.pop('passes_p90')
    with pytest.raises(ValueError, match='missing features: passes_p90'):
        engine.encode_player_match(row)


def test_dataset_and_out_of_range_flag(artifact):
    from src.analysis.team_role_space import ROLE_FEATURES
    engine, rows, z, _ = artifact
    records = [{k: r[k] for k in ROLE_FEATURES} for r in rows[:3]]
    results = engine.encode_player_dataset(records)
    np.testing.assert_allclose([r['embedding'] for r in results], z[:3], atol=1e-6)
    records[0]['passes_p90'] = 1000000.0
    result = engine.encode_player_match(records[0])
    assert result['out_of_range']
    assert 'passes_p90' in result['out_of_range_features']
    with pytest.raises(ValueError, match='Empty'):
        engine.encode_player_dataset([])


def test_bad_embedding_rejected(artifact):
    engine, _, _, _ = artifact
    for bad in ([1, 2, 3], [1, 2, 3, np.nan]):
        with pytest.raises(ValueError, match='embedding'):
            engine.compare_to_role_prototypes(bad)


def test_arrow_dataset_and_duplicate_column_error(artifact):
    import pyarrow as pa
    from src.analysis.team_role_space import ROLE_FEATURES
    engine, rows, z, _ = artifact
    table = pa.Table.from_pylist([{k: r[k] for k in ROLE_FEATURES} for r in rows[:3]])
    results = engine.encode_player_dataset(table)
    np.testing.assert_allclose([r['embedding'] for r in results], z[:3], atol=1e-6)
    duplicated = table.append_column('passes_p90', table['passes_p90'])
    with pytest.raises(ValueError, match='Duplicate feature columns'):
        engine.encode_player_dataset(duplicated)


def test_prototypes_thresholds_recomputed_without_wirtz(artifact):
    from src.models.encoder_interpretation import build_prototypes, POSITION_GROUPS
    _, rows, z, _ = artifact
    wirtz = next(r['player_id'] for r in rows if 'wirtz' in r['player_name'].lower())
    prototypes, skipped = build_prototypes(rows, z, exclude_player=wirtz)
    for p in prototypes:
        kept = [i for i, r in enumerate(rows) if r['player_id'] != wirtz
                and POSITION_GROUPS[r['nominal_position']] == p['group']]
        assert p['n_rows'] == len(kept) >= 20
        assert p['n_players'] == len({rows[i]['player_id'] for i in kept}) >= 2
        np.testing.assert_allclose([p[f'z{j+1}'] for j in range(4)], z[kept].mean(0), atol=1e-6)
    assert any(p['group'] == 'goalkeeper' and p['n_players'] == 1 for p in skipped)
    assert any(p['group'] == 'winger' and p['n_rows'] < 20 for p in skipped)
