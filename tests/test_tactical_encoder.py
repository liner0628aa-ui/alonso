"""Core leakage, metric and serialization contracts for Milestone 3."""
import io

import numpy as np
import pytest
import torch


def test_feature_order_and_metadata_never_enter_model():
    from src.models.tactical_encoder import feature_matrix, load_m2
    from src.analysis.team_role_space import ROLE_FEATURES
    rows = load_m2()
    assert (len(rows), len({r['match_id'] for r in rows}),
            len({r['player_id'] for r in rows})) == (376, 34, 18)
    expected = np.array([[rows[0][k] for k in ROLE_FEATURES]])
    shuffled = dict(reversed(list(rows[0].items())))
    shuffled.update(player_id='ignored', minutes=float('nan'), PC1=1e99)
    np.testing.assert_array_equal(feature_matrix([shuffled]), expected)
    assert feature_matrix(rows).shape == (376, 15)


def test_match_split_disjoint_and_scaler_train_only():
    from src.models.tactical_encoder import load_m2, prepare_split, feature_matrix
    rows = load_m2()
    split, scaler, x = prepare_split(rows, 42)
    groups = [{rows[i]['match_id'] for i in indices} for indices in split.values()]
    assert list(map(len, groups)) == [24, 5, 5]
    assert not (groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2])
    assert sum(map(len, split.values())) == 376
    np.testing.assert_allclose(scaler.mean_, feature_matrix(rows)[split['train']].mean(0))
    changed = [dict(r) for r in rows]
    for i in np.concatenate([split['val'], split['test']]):
        changed[i]['passes_p90'] += 100000
    _, other, _ = prepare_split(changed, 42)
    np.testing.assert_array_equal(scaler.mean_, other.mean_)
    np.testing.assert_array_equal(scaler.scale_, other.scale_)
    np.testing.assert_allclose(x[split['train']].mean(0), 0, atol=1e-12)


def test_best_model_reload_and_four_dimensional_encoding():
    from src.models.tactical_encoder import load_m2, prepare_split, train_autoencoder, TacticalAutoencoder
    split, _, x = prepare_split(load_m2(), 42)
    model, history, best_epoch = train_autoencoder(x[split['train']], x[split['val']], 42, max_epochs=3)
    with torch.no_grad():
        batch = torch.tensor(x[:6], dtype=torch.float32)
        encoded = model.encoder(batch)
        assert encoded.shape == (6, 4)
        loss = float(torch.mean((model(torch.tensor(x[split['val']], dtype=torch.float32))
                                 - torch.tensor(x[split['val']], dtype=torch.float32)) ** 2))
    assert loss == pytest.approx(min(r['val_loss'] for r in history), abs=1e-7)
    assert best_epoch == min(history, key=lambda r: r['val_loss'])['epoch']
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    buffer.seek(0)
    loaded = TacticalAutoencoder()
    loaded.load_state_dict(torch.load(buffer, weights_only=True, map_location='cpu'))
    np.testing.assert_allclose(loaded.encoder(batch).detach().numpy(), encoded.numpy(), atol=1e-7)


def test_neighbours_exclude_self_and_chance_is_correct():
    from src.models.encoder_evaluation import neighbour_overlap
    x = np.arange(7, dtype=float).reshape(-1, 1)
    score = neighbour_overlap(x, x, k=5)
    assert score['overlap'] == 1
    assert score['chance'] == pytest.approx(5 / 6)
    # With self included both sets would contain self and falsely overlap fully.
    # True nearest indices are [1,0,1,2] versus [2,3,0,1]: zero intersections.
    changed = neighbour_overlap(np.array([[0.], [1.], [3.], [8.]]),
                                np.array([[0.], [7.], [3.], [8.]]), k=1)
    assert changed['overlap'] == 0
    assert changed['chance'] == pytest.approx(1 / 3)


def test_cohesion_excludes_singletons_from_both_pair_sets():
    from src.models.encoder_evaluation import player_cohesion
    x = np.array([[0.], [2.], [10.], [12.], [1000.]])
    result = player_cohesion(x, ['a', 'a', 'b', 'b', 'singleton'])
    assert result['ratio'] == pytest.approx(2 / 10)
    assert result['same_pairs'] == 2
    assert result['different_pairs'] == 4


def test_verdict_requires_joint_wins_and_paired_effect_sizes():
    from src.models.encoder_evaluation import summarize_runs
    def runs(wins):
        return [dict(seed=42+i, test=dict(
            ae=dict(mse=0.2 if i < wins else 0.6, neighbour_overlap=0.8 if i < wins else 0.4, cohesion=0.5),
            pca=dict(mse=0.4, neighbour_overlap=0.6, cohesion=0.6),
            mean=dict(mse=1.), raw=dict(cohesion=0.7), chance=0.1)) for i in range(10)]
    assert summarize_runs(runs(10))['clearly_better']
    assert not summarize_runs(runs(7))['clearly_better']
    result = summarize_runs(runs(8))
    assert result['joint_wins'] == 8
    assert not result['clearly_better']  # paired std > mean even with eight wins
    assert result['verdict'] == 'At this dataset size the autoencoder is comparable to or worse than the PCA baseline.'
    disjoint_wins = runs(10)
    for i, run in enumerate(disjoint_wins):
        run['test']['ae']['mse'] = 0.2 if i < 8 else 0.401
        run['test']['ae']['neighbour_overlap'] = 0.8 if i >= 2 else 0.599
    result = summarize_runs(disjoint_wins)
    assert result['ae_beats_pca']['mse'] == result['ae_beats_pca']['neighbour_overlap'] == 8
    assert result['joint_wins'] == 6
    assert all(result['paired_improvements'][k]['mean'] > result['paired_improvements'][k]['std']
               for k in ('mse', 'neighbour_overlap'))
    assert not result['clearly_better']


def test_pca_fit_excludes_test_rows():
    from src.models.tactical_encoder import load_m2, prepare_split
    from src.models.encoder_evaluation import fit_pca
    split, _, x = prepare_split(load_m2(), 42)
    pca = fit_pca(x[split['train']])
    np.testing.assert_allclose(pca.mean_, x[split['train']].mean(0), atol=1e-14)
    assert pca.n_samples_ == len(split['train'])
    assert pca.transform(x).shape == (376, 4)
