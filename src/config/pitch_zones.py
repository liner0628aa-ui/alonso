"""Attacking left-to-right; y=0 is the attacker's left touchline."""
import math

LANE_BOUNDARIES = (20.0, 40.0, 60.0, 80.0)
LANE_NAMES = ('left_wing', 'left_halfspace', 'centre', 'right_halfspace', 'right_wing')
THIRD_BOUNDARIES = (100 / 3, 200 / 3)
THIRD_NAMES = ('defensive_third', 'middle_third', 'final_third')
# StatsBomb 120x80 canonical box geometry, scaled to 100x100.
# Other sources must explicitly establish equivalence before using this policy.
BOX_X_MIN = 102 / 120 * 100
BOX_Y_MIN = 18 / 80 * 100
BOX_Y_MAX = 62 / 80 * 100
ZONE_VERSION = 'statsbomb-proportional-v1'


def classify_zone(x, y):
    if x is None and y is None:
        return None, None, None
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) or not 0 <= v <= 100 for v in (x, y)):
        raise ValueError('Zone coordinates must be a complete finite 0–100 pair')
    return (LANE_NAMES[sum(y >= b for b in LANE_BOUNDARIES)],
            THIRD_NAMES[sum(x >= b for b in THIRD_BOUNDARIES)],
            x >= BOX_X_MIN and BOX_Y_MIN <= y <= BOX_Y_MAX)
