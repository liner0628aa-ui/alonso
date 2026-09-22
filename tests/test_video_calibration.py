"""Synthetic geometry only, not evidence of broadcast measurement accuracy."""
import numpy as np
import pytest

from src.video_tracking.calibration import fit_calibration, transform_points, check_camera


PITCH = np.array([[0., 0.], [105., 0.], [105., 68.], [0., 68.],
                  [16.5, 13.84], [16.5, 54.16], [52.5, 0.], [52.5, 68.]])


def pixels(points):
    # Independent analytical projective fixture; not estimated by our code.
    x, y = np.asarray(points).T
    d = 1 + .001*x + .002*y
    return np.column_stack(((8*x + 2*y + 100)/d, (x + 6*y + 80)/d))


def config(n=8):
    return dict(frame_id=0, image_points_px=pixels(PITCH[:n]).tolist(),
                pitch_points_m=PITCH[:n].tolist(),
                landmark_names=[f'synthetic_landmark_{i}' for i in range(n)],
                ransac_threshold_px=2., max_inlier_error_px=3., min_inlier_fraction=.7)


@pytest.mark.parametrize('n', [4, 8])
def test_exact_homography_numeric(n):
    cal = fit_calibration(config(n))
    query = np.array([[30., 20.], [70., 45.], [105., 68.]])
    xy, outside = transform_points(cal, pixels(query))
    np.testing.assert_allclose(xy, query, atol=2e-5)
    assert not outside.any()
    assert cal['point_count'] == cal['inlier_count'] == n
    assert cal['reprojection_max_px'] < 1e-3


def test_noisy_correspondences_bound_independent_queries():
    c = config()
    c['image_points_px'] = (pixels(PITCH) + np.random.default_rng(42).normal(0, .2, (8, 2))).tolist()
    cal = fit_calibration(c)
    query = np.array([[30., 20.], [70., 45.]])
    xy, _ = transform_points(cal, pixels(query))
    assert np.max(np.linalg.norm(xy-query, axis=1)) < .2
    assert 0 < cal['reprojection_mean_px'] < 1


def test_ransac_outlier_residual_is_preserved():
    c = config()
    c['image_points_px'][-1][0] += 80
    cal = fit_calibration(c)
    assert cal['inlier_count'] == 7
    assert cal['reprojection_max_px'] > 70
    assert cal['inlier_reprojection_max_px'] < .001
    xy, _ = transform_points(cal, pixels([[30., 20.]]))
    np.testing.assert_allclose(xy, [[30., 20.]], atol=2e-5)


@pytest.mark.parametrize('points', [PITCH[:3], [[0, 0], [1, 1], [2, 2], [3, 3]],
    [[0, 0], [1, 0], [2, 0], [1, 5]], [[0, 0], [0, 0], [10, 10], [10, 0]]])
def test_invalid_landmarks_fail(points):
    c = config(4)
    c.update(image_points_px=pixels(points).tolist(), pitch_points_m=np.asarray(points).tolist())
    with pytest.raises(ValueError):
        fit_calibration(c)


def test_outside_calibration_region_is_flagged_not_clipped():
    c = config(4)
    c['pitch_points_m'] = [[20, 20], [80, 20], [80, 50], [20, 50]]
    c['image_points_px'] = pixels(c['pitch_points_m']).tolist()
    xy, outside = transform_points(fit_calibration(c), pixels([[10, 10], [120, 40]]))
    np.testing.assert_allclose(xy, [[10, 10], [120, 40]], atol=1e-4)
    assert outside.tolist() == [True, True]


def test_inaccurate_fit_or_inadequate_consensus_fails():
    c = config()
    c['image_points_px'] = (pixels(PITCH) + np.random.default_rng(4).normal(0, 20, (8, 2))).tolist()
    with pytest.raises(ValueError, match='consensus|residual'):
        fit_calibration(c)


def test_manual_camera_checks_reject_drift():
    cal = fit_calibration(config())
    check = dict(frame_id=29, pitch_points_m=PITCH[:4].tolist(),
                 image_points_px=pixels(PITCH[:4]).tolist())
    result = check_camera(cal, [check], max_error_px=3.)
    assert result[0]['max_error_px'] < .001
    check['image_points_px'][0][0] += 10
    with pytest.raises(ValueError, match='drift'):
        check_camera(cal, [check], max_error_px=3.)


def test_crossed_correspondences_with_horizon_through_landmark_hull_fail():
    c = config(4)
    c['image_points_px'][2], c['image_points_px'][3] = c['image_points_px'][3], c['image_points_px'][2]
    with pytest.raises(ValueError, match='horizon'):
        fit_calibration(c)


@pytest.mark.parametrize('field,value', [('ransac_threshold_px', 0),
    ('max_inlier_error_px', float('nan')), ('min_inlier_fraction', 0), ('frame_id', -1)])
def test_invalid_calibration_parameters(field, value):
    c = config()
    c[field] = value
    with pytest.raises(ValueError):
        fit_calibration(c)
