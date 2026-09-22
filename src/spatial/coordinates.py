"""Canonical shared-frame metres and explicit attacking-frame rotation."""
from dataclasses import dataclass
from numbers import Integral, Real

import numpy as np
import pyarrow as pa

VERSION = 'spatial-v1'
ZONES = ('left_wide', 'left_halfspace', 'central', 'right_halfspace', 'right_wide')


@dataclass(frozen=True)
class PitchConfig:
    """Project v1 zones, not universal football boundaries. Never clip positions."""
    length_m: float = 105.
    width_m: float = 68.
    tolerance_m: float = .1
    lane_fractions: tuple = (.2, .4, .6, .8)

    def __post_init__(self):
        if (self.length_m, self.width_m) != (105., 68.):
            raise ValueError('spatial-v1 canonical pitch must be 105 by 68 metres')
        if not finite_number(self.tolerance_m) or not 0 <= self.tolerance_m <= .5:
            raise ValueError('Pitch tolerance must be finite and between 0 and 0.5m')
        if (len(self.lane_fractions) != 4 or
                any(not finite_number(v) or not 0 < v < 1 for v in self.lane_fractions) or
                any(a >= b for a, b in zip(self.lane_fractions, self.lane_fractions[1:]))):
            raise ValueError('Four strictly increasing lane fractions in (0,1) required')


def finite_number(value):
    return isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and np.isfinite(value)


TRACKING_SCHEMA = pa.schema([
    ('match_id', pa.string()), ('period', pa.int64()), ('timestamp_s', pa.float64()),
    ('frame_id', pa.int64()), ('team_id', pa.string()), ('player_id', pa.string()),
    ('track_id', pa.string()), ('x_m', pa.float64()), ('y_m', pa.float64()),
    ('visible', pa.bool_()), ('detected', pa.bool_()), ('source', pa.string()),
    # Provider scales are preserved as text, not assumed to be calibrated probabilities.
    ('coordinate_confidence', pa.string()), ('identity_confidence', pa.string()),
    ('attacking_direction', pa.string()),
])


def team_relative(x, y, direction, pitch=None):
    """180° rotation preserves handedness: team y=0 is the attacker's left."""
    pitch = pitch or PitchConfig()
    if direction not in ('positive_x', 'negative_x'):
        raise ValueError('Explicit attacking direction required')
    if x is None and y is None:
        return None, None
    if not all(finite_number(v) for v in (x, y)):
        raise ValueError('Coordinates must be a complete finite pair')
    return (x, y) if direction == 'positive_x' else (pitch.length_m-x, pitch.width_m-y)


def in_pitch(row, pitch):
    return (row['x_m'] is not None and 0 <= row['x_m'] <= pitch.length_m
            and 0 <= row['y_m'] <= pitch.width_m)


def canonical_table(rows, *, pitch=None):
    """Validate canonical rows before Arrow coercion; NULL pairs remain NULL.

    x_m/y_m are shared stadium-frame coordinates, not separately rotated by team.
    Timestamps are numeric seconds on a documented provider timebase within period.
    Track IDs must be scoped by the adapter to avoid collisions across segments.
    """
    pitch = pitch or PitchConfig()
    rows = rows.to_pylist() if isinstance(rows, pa.Table) else list(rows)
    seen_tracks, seen_players, clocks, directions, identities, time_frames = set(), set(), {}, {}, {}, {}
    for row in rows:
        missing = set(TRACKING_SCHEMA.names) - row.keys()
        if missing:
            raise ValueError(f'Missing canonical fields: {sorted(missing)}')
        for key in ('match_id', 'team_id', 'track_id', 'source'):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError(f'{key} must be a nonempty string')
        for key in ('player_id', 'coordinate_confidence', 'identity_confidence'):
            if row[key] is not None and (not isinstance(row[key], str) or not row[key].strip()):
                raise ValueError(f'{key} must be a nonempty string or NULL')
        for key in ('period', 'frame_id'):
            if isinstance(row[key], bool) or not isinstance(row[key], Integral) or row[key] < (1 if key == 'period' else 0):
                raise ValueError(f'{key} must be a valid integer')
        if not finite_number(row['timestamp_s']) or row['timestamp_s'] < 0:
            raise ValueError('timestamp_s must be nonnegative numeric seconds')
        for key in ('visible', 'detected'):
            if row[key] is not None and not isinstance(row[key], bool):
                raise ValueError(f'{key} must be boolean or NULL')
        x, y = row['x_m'], row['y_m']
        if not (x is None and y is None):
            if not all(finite_number(v) for v in (x, y)):
                raise ValueError('Coordinates must be a complete finite pair or two NULLs')
            tol = pitch.tolerance_m
            if not (-tol <= x <= pitch.length_m+tol and -tol <= y <= pitch.width_m+tol):
                raise ValueError('Coordinate outside pitch tolerance; no silent clipping')
        team_relative(x, y, row['attacking_direction'], pitch)
        frame = (row['match_id'], row['period'], row['frame_id'])
        track = frame + (row['track_id'],)
        player = frame + (row['team_id'], row['player_id'])
        if track in seen_tracks or (row['player_id'] is not None and player in seen_players):
            raise ValueError('Duplicate track/player observation in frame')
        seen_tracks.add(track)
        seen_players.add(player)
        if clocks.setdefault(frame, row['timestamp_s']) != row['timestamp_s']:
            raise ValueError('Inconsistent frame timestamp')
        moment = (row['match_id'], row['period'], row['timestamp_s'])
        if time_frames.setdefault(moment, row['frame_id']) != row['frame_id']:
            raise ValueError('Multiple frame IDs at same timestamp')
        team = (row['match_id'], row['period'], row['team_id'])
        if directions.setdefault(team, row['attacking_direction']) != row['attacking_direction']:
            raise ValueError('Inconsistent team/period direction')
        identity = (row['team_id'], row['player_id'], row['source'])
        track_scope = (row['match_id'], row['period'], row['track_id'])
        if identities.setdefault(track_scope, identity) != identity:
            raise ValueError('Track changes identity/team/source; split track explicitly')
    return pa.Table.from_pylist(rows, schema=TRACKING_SCHEMA)
