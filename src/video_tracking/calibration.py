"""Manual planar calibration. Residuals are fit diagnostics, not accuracy bounds."""
from hashlib import sha256
from itertools import combinations
import json

import cv2
import numpy as np


def _points(value):
    points = np.asarray(value, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise ValueError('Landmarks must be finite Nx2 coordinates')
    return points


def _geometry(points):
    if len(points) < 4 or len(np.unique(points, axis=0)) != len(points):
        raise ValueError('At least four distinct calibration points required')
    centred = points - points.mean(axis=0)
    scale = np.linalg.norm(centred, axis=1).max()
    if scale == 0 or np.linalg.svd(centred/scale, compute_uv=False)[-1] < 1e-4:
        raise ValueError('Collinear or nearly collinear calibration points')
    if len(points) == 4:
        for a, b, c in combinations(points/scale, 3):
            u, v = b-a, c-a
            if abs(u[0]*v[1] - u[1]*v[0]) < 1e-6:
                raise ValueError('Four-point homography cannot contain a collinear triple')


def _project(matrix, points):
    if not len(points):
        return np.empty((0, 2), dtype=float)
    homogeneous = np.column_stack((points, np.ones(len(points)))) @ matrix.T
    if np.any(np.abs(homogeneous[:, 2]) < 1e-10):
        raise ValueError('Homography maps ground point to infinity')
    result = cv2.perspectiveTransform(points.reshape(-1, 1, 2), matrix).reshape(-1, 2)
    if not np.isfinite(result).all():
        raise ValueError('Nonfinite homography result')
    return result


def fit_calibration(config):
    image = _points(config['image_points_px'])
    pitch = _points(config['pitch_points_m'])
    if image.shape != pitch.shape:
        raise ValueError('Image and pitch correspondences must have equal length')
    _geometry(image)
    _geometry(pitch)
    if (pitch < 0).any() or (pitch > [105., 68.]).any():
        raise ValueError('Landmarks must use canonical 105x68 pitch coordinates')
    frame = config['frame_id']
    if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
        raise ValueError('Invalid calibration frame_id')
    names = config.get('landmark_names', [])
    if len(names) != len(image) or any(not isinstance(n, str) or not n.strip() for n in names):
        raise ValueError('Name every unambiguous landmark for manual review')
    threshold = config.get('ransac_threshold_px', 2.)
    maximum = config.get('max_inlier_error_px', 3.)
    fraction = config.get('min_inlier_fraction', .75)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v) or v <= 0
           for v in (threshold, maximum, fraction)) or fraction > 1:
        raise ValueError('Invalid calibration thresholds')
    cv2.setRNGSeed(0)
    forward, mask = cv2.findHomography(pitch, image, cv2.RANSAC if len(image) > 4 else 0,
                                       ransacReprojThreshold=threshold, maxIters=5000, confidence=.999)
    if forward is None or mask is None or not np.isfinite(forward).all():
        raise ValueError('Homography estimation failed')
    inliers = mask.ravel().astype(bool)
    if inliers.sum() < 4 or inliers.mean() < fraction:
        raise ValueError('Insufficient homography consensus')
    _geometry(image[inliers])
    _geometry(pitch[inliers])
    try:
        inverse = np.linalg.inv(forward)
    except np.linalg.LinAlgError as exc:
        raise ValueError('Singular homography') from exc
    # A finite continuous plane cannot cross the projective horizon inside the
    # landmark hull. Exact but crossed four-point correspondences otherwise fit.
    for matrix, points in ((forward, pitch[inliers]), (inverse, image[inliers])):
        denominator = np.column_stack((points, np.ones(len(points)))) @ matrix[2]
        if not (np.all(denominator > 1e-10) or np.all(denominator < -1e-10)):
            raise ValueError('Homography horizon crosses calibration hull; review landmark pairing')
    errors = np.linalg.norm(_project(forward, pitch)-image, axis=1)
    if errors[inliers].max() > maximum:
        raise ValueError('Excessive inlier reprojection residual')
    result = dict(homography_id=sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16],
                  frame_id=frame, source_method='manual_review', point_count=len(image),
                  inlier_count=int(inliers.sum()), inlier_mask=inliers.tolist(),
                  reprojection_errors_px=errors.tolist(), pitch_to_image=forward.tolist(),
                  image_to_pitch=inverse.tolist(),
                  image_hull=cv2.convexHull(image[inliers].astype(np.float32)).reshape(-1, 2).tolist())
    for prefix, values in (('reprojection', errors), ('inlier_reprojection', errors[inliers])):
        result.update({f'{prefix}_{name}_px': float(fn(values))
                       for name, fn in (('mean', np.mean), ('median', np.median), ('max', np.max))})
    return result


def transform_points(calibration, image_points):
    points = _points(image_points)
    xy = _project(np.asarray(calibration['image_to_pitch']), points)
    hull = np.asarray(calibration['image_hull'], dtype=np.float32)
    outside = np.array([cv2.pointPolygonTest(hull, tuple(map(float, p)), True) < -1e-4
                        for p in points], dtype=bool)
    return xy, outside


def check_camera(calibration, checks, *, max_error_px):
    if isinstance(max_error_px, bool) or not np.isfinite(max_error_px) or max_error_px <= 0:
        raise ValueError('Positive camera-check threshold required')
    results = []
    for check in checks:
        pitch, image = _points(check['pitch_points_m']), _points(check['image_points_px'])
        if pitch.shape != image.shape:
            raise ValueError('Camera check points must correspond')
        _geometry(pitch)
        _geometry(image)
        errors = np.linalg.norm(_project(np.asarray(calibration['pitch_to_image']), pitch)-image, axis=1)
        if errors.max() > max_error_px:
            raise ValueError(f'Material camera drift / inconsistent landmarks at frame {check["frame_id"]}: '
                             f'{errors.max():.3f}px exceeds {max_error_px:g}px')
        results.append(dict(frame_id=check['frame_id'], mean_error_px=float(errors.mean()),
                            max_error_px=float(errors.max()), source_method='manual_review'))
    return results
