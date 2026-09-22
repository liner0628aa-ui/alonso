"""Reviewed track labels; unknown people never silently become a team."""


def validate_team_config(config):
    teams = config['teams']
    if not isinstance(teams, dict) or not teams:
        raise ValueError('Explicit teams and attacking directions required')
    for team, direction in teams.items():
        if not isinstance(team, str) or not team.strip() or direction not in ('positive_x', 'negative_x'):
            raise ValueError('Invalid team or attacking direction')
    assignments = config['team_assignments']
    if not isinstance(assignments, dict):
        raise ValueError('team_assignments must be a track mapping')
    for track, label in assignments.items():
        if not isinstance(track, str) or not track.strip() or not isinstance(label, dict):
            raise ValueError('Invalid track label')
        if label.get('source_method') != 'manual_review':
            raise ValueError('Team assignment must be manual_review')
        if 'exclude' in label and not isinstance(label['exclude'], bool):
            raise ValueError('exclude must be a boolean')
        if label.get('exclude', False):
            if not isinstance(label.get('reason'), str) or not label['reason'].strip():
                raise ValueError('Excluded nonplayer requires a manual reason')
            if label.get('team_id') is not None:
                raise ValueError('Excluded nonplayer must not have a team')
        elif label.get('team_id') not in teams:
            raise ValueError('Assigned team must have an explicit attacking direction')


def assign_team(row, config):
    label = config['team_assignments'].get(row['track_id'], {})
    return dict(row, team_id=label.get('team_id'), team_assignment_method=label.get('source_method'),
                excluded=label.get('exclude', False), exclusion_reason=label.get('reason'))


def canonical_rows(rows, config, *, match_id, period):
    validate_team_config(config)
    result = []
    for row in rows:
        if row['track_id'] is None or row['excluded']:
            continue
        if row['team_id'] not in config['teams'] or row['team_assignment_method'] != 'manual_review':
            raise ValueError(f'Missing reviewed team assignment for {row["track_id"]}')
        if row['homography_failure']:
            raise ValueError('Homography failure prevents canonical export')
        result.append(dict(match_id=match_id, period=period, timestamp_s=row['timestamp_s'],
            frame_id=row['frame_id'], team_id=row['team_id'], player_id=None, track_id=row['track_id'],
            x_m=row['pitch_x_raw'], y_m=row['pitch_y_raw'], visible=True, detected=True,
            source='broadcast_video_estimate', coordinate_confidence=None, identity_confidence=None,
            attacking_direction=config['teams'][row['team_id']]))
    return result
