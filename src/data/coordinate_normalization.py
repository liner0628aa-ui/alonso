"""Pure coordinate transforms; source direction must be supplied, never guessed."""
import math


def normalize_point(x, y, *, width=100, height=100,
                    direction='left_to_right', y_origin='top'):
    if direction not in ('left_to_right', 'right_to_left') or y_origin not in ('top', 'bottom'):
        raise ValueError('Explicit supported direction and y origin required')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) or v <= 0 for v in (width, height)):
        raise ValueError('Source extents must be finite and positive')
    if x is None and y is None:
        return None, None
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) for v in (x, y)):
        raise ValueError('Coordinates must be a complete finite pair')
    if not 0 <= x <= width or not 0 <= y <= height:
        raise ValueError('Coordinates outside source pitch; no silent clipping')
    nx, ny = x / width * 100, y / height * 100
    if y_origin == 'bottom':
        ny = 100 - ny
    if direction == 'right_to_left':
        nx, ny = 100 - nx, 100 - ny
    return nx, ny


def normalize_coordinates(x, y, end_x=None, end_y=None, **kwargs):
    nx, ny = normalize_point(x, y, **kwargs)
    ex, ey = normalize_point(end_x, end_y, **kwargs)
    return dict(source_x=x, source_y=y, source_end_x=end_x, source_end_y=end_y,
                normalized_x=nx, normalized_y=ny, normalized_end_x=ex, normalized_end_y=ey)
