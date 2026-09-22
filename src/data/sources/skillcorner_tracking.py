"""SkillCorner's published JSONL -> shared canonical rows; no feature logic.

Contract inspected at SkillCorner/opendata commit
4340d274572876239c154c90bc507a9b3250a656: README, assets/field.jpg and match
1886347 metadata. x is centred metres to the right; y is centred metres up.
home_team_side supplies direction by half. No direction inference from positions.
"""
import re

from src.spatial.coordinates import canonical_table, finite_number


def parse_timestamp(value):
    """Preserve the source match-clock timebase; never infer a period offset."""
    if not isinstance(value, str) or not re.fullmatch(r'\d{2}:\d{2}:\d{2}(?:\.\d+)?', value):
        raise ValueError('Expected SkillCorner HH:MM:SS.fraction timestamp')
    hours, minutes, seconds = map(float, value.split(':'))
    if minutes >= 60 or seconds >= 60:
        raise ValueError('Invalid timestamp clock components')
    return hours*3600 + minutes*60 + seconds


def adapt_frames(frames, metadata):
    """Scale actual pitch dimensions to 105x68; y inversion follows official diagram.

    is_detected=True is the provider's on-screen detection proxy for visibility.
    False extrapolations and unknown flags are retained but excluded by the core.
    Confidence is NULL: a global accuracy statement is not row-level confidence.
    """
    length, width = metadata.get('pitch_length'), metadata.get('pitch_width')
    if not all(finite_number(v) and v > 0 for v in (length, width)):
        raise ValueError('Documented finite pitch dimensions required')
    sides = metadata.get('home_team_side', [])
    if len(sides) != 2 or any(s not in ('left_to_right', 'right_to_left') for s in sides):
        raise ValueError('Documented home_team_side required for both halves')
    roster = {p['id']: p for p in metadata['players']}
    if len(roster) != len(metadata['players']):
        raise ValueError('Duplicate roster player ID')
    home, away = metadata['home_team']['id'], metadata['away_team']['id']
    if home == away:
        raise ValueError('Distinct home and away teams required')
    rows = []
    for frame in frames:
        if frame['period'] is None and frame['timestamp'] is None and not frame['player_data']:
            continue  # Explicit pre-match empty frames have no valid match time.
        if frame['period'] not in (1, 2):
            raise ValueError('This adapter supports documented periods 1 and 2 only')
        timestamp = parse_timestamp(frame['timestamp'])
        home_positive = sides[frame['period']-1] == 'left_to_right'
        for player in frame['player_data']:
            if player['player_id'] not in roster:
                raise ValueError('Tracking player absent from metadata roster')
            identity = roster[player['player_id']]
            if identity['team_id'] not in (home, away) or identity.get('trackable_object') is None:
                raise ValueError('Verified team and track identity required')
            x, y = player['x'], player['y']
            if x is None and y is None:
                cx = cy = None
            elif not all(finite_number(v) for v in (x, y)):
                raise ValueError('Provider coordinates must be finite pairs or NULL pairs')
            else:
                cx, cy = (x/length + .5)*105, (.5-y/width)*68
            positive = home_positive if identity['team_id'] == home else not home_positive
            rows.append(dict(match_id=f"skillcorner:match:{metadata['id']}",
                period=frame['period'], timestamp_s=timestamp, frame_id=frame['frame'],
                team_id=f"skillcorner:team:{identity['team_id']}",
                player_id=f"skillcorner:player:{identity['id']}",
                track_id=f"skillcorner:track:{identity['trackable_object']}",
                x_m=cx, y_m=cy, visible=player['is_detected'], detected=player['is_detected'],
                source='skillcorner_open_broadcast_estimates', coordinate_confidence=None,
                identity_confidence=None, attacking_direction='positive_x' if positive else 'negative_x'))
    return canonical_table(rows)
