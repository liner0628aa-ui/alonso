"""Phase 2 contracts only. No ingestion, estimation, imputation, or model fitting."""
from dataclasses import dataclass, field
from datetime import date
import math

SCHEMA_VERSION = '2.0.1'

# All metrics are candidates, not claims of content verified in Phase 1.
GROUPS = {
    'involvement': 'touches receptions passes_attempted passes_completed',
    'progression': 'progressive_passes progressive_carries final_third_entries carries_into_final_third carries_into_penalty_area passes_into_final_third passes_into_penalty_area',
    'creation': 'key_passes shot_assists through_balls xA shot_creating_actions goal_creating_actions',
    'shooting': 'shots shots_on_target xG non_penalty_xG box_touches penalty_area_receptions',
    'carrying': 'carries carry_distance progressive_carry_distance take_ons_attempted take_ons_completed',
    'security': 'dispossessions miscontrols turnovers',
    'defensive': 'pressures successful_pressures tackles interceptions recoveries',
}
UNAVAILABLE = {'touches', 'box_touches', 'xA', 'shot_creating_actions',
               'goal_creating_actions', 'turnovers', 'successful_pressures'}
SPATIAL = set('avg_touch_x avg_touch_y avg_reception_x avg_reception_y left_halfspace_touch_share right_halfspace_touch_share central_touch_share wing_touch_share final_third_touch_share box_touch_share'.split())
EVENT_SPATIAL = SPATIAL - {'final_third_touch_share', 'box_touch_share'}
CONTEXT = set('team_possession opponent_possession score_state_minutes_winning score_state_minutes_drawing score_state_minutes_losing team_pass_volume team_shots match_tempo_proxy'.split())
FEATURES = {}
for group, names in GROUPS.items():
    for name in names.split():
        unit = 'pitch_units' if 'distance' in name else ('expected_goals' if name in {'xA', 'xG', 'non_penalty_xG'} else 'count')
        status = 'unavailable_pending_definition' if name in UNAVAILABLE else 'candidate_unverified_content'
        for suffix in ('raw', 'p90'):
            FEATURES[f'{name}_{suffix}'] = dict(group=group, unit=unit if suffix == 'raw' else unit+'/90min',
                dtype='int' if unit == 'count' and suffix == 'raw' else 'float',
                kind='source_or_derived' if suffix == 'raw' else 'derived', availability=status)
for name in sorted(SPATIAL | CONTEXT | {'pass_completion'}):
    unit = 'share' if 'share' in name or name in {'pass_completion', 'team_possession', 'opponent_possession'} else (
        'normalized_coordinate' if name.startswith('avg_') else 'minutes' if 'minutes' in name else
        'count' if name in {'team_pass_volume', 'team_shots'} else 'events/minute')
    FEATURES[name] = dict(group='spatial' if name in SPATIAL else 'security' if name == 'pass_completion' else 'context',
        unit=unit, dtype='int' if unit == 'count' else 'float', kind='source_or_derived', availability='candidate_unverified_content')

# Context is for later adjustment, never an accidental role input.
ML_FEATURE_COLUMNS = tuple(name for name in FEATURES if name not in CONTEXT)

ROLE_DIMENSIONS = {
    'progression_score_inputs': ('progressive_passes_p90', 'progressive_carries_p90', 'passes_into_final_third_p90'),
    'creation_score_inputs': ('key_passes_p90', 'through_balls_p90', 'xA_p90', 'shot_creating_actions_p90'),
    'carrying_score_inputs': ('carries_p90', 'carry_distance_p90', 'take_ons_completed_p90'),
    'halfspace_usage_inputs': ('left_halfspace_touch_share', 'right_halfspace_touch_share'),
    'box_threat_inputs': ('non_penalty_xG_p90', 'shots_p90', 'penalty_area_receptions_p90', 'box_touch_share'),
    'combination_play_inputs': ('receptions_p90', 'passes_completed_p90', 'pass_completion'),
    'defensive_activity_inputs': ('pressures_p90', 'tackles_p90', 'interceptions_p90', 'recoveries_p90'),
}
MISSING_REASONS = {'not_collected', 'source_not_provided', 'definition_unverified',
    'definition_incompatible', 'outside_visible_area', 'insufficient_minutes', 'access_failed', 'not_applicable'}


def _number(value, name, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{name}: finite nonnegative number required')
    if maximum is not None and value > maximum:
        raise ValueError(f'{name}: exceeds {maximum}')


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name}: nonempty string required')


def per90(value, minutes):
    if value is not None:
        _number(value, 'value')
    if minutes is not None:
        _number(minutes, 'minutes')
    return None if value is None or minutes is None or minutes == 0 else value * 90 / minutes


def _validate_feature_relationships(features, minutes_played):
    for completed, attempted in [('passes_completed_raw', 'passes_attempted_raw'),
                                 ('take_ons_completed_raw', 'take_ons_attempted_raw'), ('shots_on_target_raw', 'shots_raw')]:
        a, b = features[completed], features[attempted]
        if a is not None and b is not None and a > b:
            raise ValueError('Completed count exceeds attempts')
    score_minutes = [features['score_state_minutes_'+s] for s in ('winning', 'drawing', 'losing')]
    if all(v is not None for v in score_minutes) and minutes_played is not None:
        if not math.isclose(sum(score_minutes), minutes_played, abs_tol=0.02):
            raise ValueError('Score-state minutes must sum to player on-pitch minutes')
    completion = features['pass_completion']
    attempted, completed = features['passes_attempted_raw'], features['passes_completed_raw']
    if completion is not None:
        if attempted == 0:
            raise ValueError('Zero attempts means undefined completion, not zero completion')
        if attempted is not None and completed is not None:
            if not math.isclose(completion, completed / attempted, abs_tol=1e-6):
                raise ValueError('Pass completion disagrees with retained counts')
    for state in ('winning', 'drawing', 'losing'):
        value = features['score_state_minutes_'+state]
        if value is not None and minutes_played is not None and value > minutes_played + 0.02:
            raise ValueError('Score-state minutes exceed on-pitch minutes')


@dataclass
class RawEvent:
    data_source: str
    source_match_id: str
    source_event_id: str
    payload: dict

    def validate(self):
        for name in ('data_source', 'source_match_id', 'source_event_id'):
            _text(getattr(self, name), name)
        if not isinstance(self.payload, dict):
            raise ValueError('Unmodified source JSON object required')


@dataclass
class NormalizedEvent:
    match_id: str
    event_id: str
    data_source: str
    source_match_id: str
    source_event_id: str
    event_index: int
    period: int
    minute: int
    second: float
    event_type: str
    player_id: str | None = None
    team_id: str | None = None
    source_player_id: str | None = None
    source_team_id: str | None = None
    source_x: float | None = None
    source_y: float | None = None
    source_end_x: float | None = None
    source_end_y: float | None = None
    normalized_x: float | None = None
    normalized_y: float | None = None
    normalized_end_x: float | None = None
    normalized_end_y: float | None = None
    outcome: str | None = None
    body_part: str | None = None
    under_pressure: bool | None = None
    possession_id: str | None = None
    play_pattern: str | None = None
    coordinate_transform: str | None = None

    def validate(self):
        for name in ('match_id', 'event_id', 'data_source', 'source_match_id', 'source_event_id', 'event_type'):
            _text(getattr(self, name), name)
        for name in ('event_index', 'period', 'minute'):
            v = getattr(self, name)
            if type(v) is not int or v < 0:
                raise ValueError('Nonnegative integer event ordering required')
        if self.period not in (1, 2, 3, 4, 5):
            raise ValueError('Unknown period')
        _number(self.second, 'second')
        if self.second >= 60:
            raise ValueError('second must be less than 60')
        if self.under_pressure is not None and type(self.under_pressure) is not bool:
            raise ValueError('under_pressure must be boolean or null')
        for x, y in [('source_x', 'source_y'), ('source_end_x', 'source_end_y'),
                     ('normalized_x', 'normalized_y'), ('normalized_end_x', 'normalized_end_y')]:
            a, b = getattr(self, x), getattr(self, y)
            if (a is None) != (b is None):
                raise ValueError('Incomplete coordinate pair')
            if a is not None:
                _number(a, x, 100 if x.startswith('normalized') else None)
                _number(b, y, 100 if y.startswith('normalized') else None)
        for name in ('x', 'end_x'):
            if (getattr(self, 'source_'+name) is None) != (getattr(self, 'normalized_'+name) is None):
                raise ValueError('Normalized event must transform every available source coordinate pair')
            if getattr(self, 'normalized_'+name) is not None:
                if getattr(self, 'source_'+name) is None:
                    raise ValueError('Retain source coordinates')
                _text(self.coordinate_transform, 'coordinate_transform')


@dataclass
class PlayerMatch:
    player_id: str
    player_name: str
    team_id: str
    team_name: str
    opponent_id: str
    opponent_name: str
    match_id: str
    competition: str
    season: str
    match_date: str
    data_source: str
    source_match_id: str
    source_player_id: str
    minutes_played: float | None
    home_away: str
    event_data_available: bool = False
    spatial_data_available: bool = False
    manager_id: str | None = None
    manager: str | None = None
    manager_period: str | None = None
    nominal_position: str | None = None
    starting_position: str | None = None
    formation: str | None = None
    source_team_id: str | None = None
    source_opponent_id: str | None = None
    features: dict = field(default_factory=lambda: dict.fromkeys(FEATURES))
    feature_status: dict = field(default_factory=lambda: dict.fromkeys(FEATURES, 'unavailable'))
    missing_reasons: dict = field(default_factory=lambda: dict.fromkeys(FEATURES, 'not_collected'))
    definition_ids: dict = field(default_factory=lambda: dict.fromkeys(FEATURES))

    @property
    def player_season_id(self):
        return self.player_id, self.competition, self.season

    @property
    def team_season_id(self):
        return self.team_id, self.competition, self.season

    @property
    def missing_feature_count(self):
        return sum(v is None for v in self.features.values())

    @property
    def data_quality_flag(self):
        return tuple(flag for flag, condition in (
            ('partial_features', self.missing_feature_count > 0),
            ('unknown_minutes', self.minutes_played is None),
            ('zero_minutes', self.minutes_played == 0),
            ('aggregate_only', not self.event_data_available)) if condition)

    def set_feature(self, name, value, status='unavailable', definition_id=None, missing_reason=None):
        if name not in FEATURES:
            raise ValueError('Unknown canonical feature')
        previous = (self.features[name], self.feature_status[name], self.definition_ids[name], self.missing_reasons[name])
        self.features[name], self.feature_status[name] = value, status
        self.definition_ids[name], self.missing_reasons[name] = definition_id, missing_reason
        try:
            self.validate()
        except ValueError:
            self.features[name], self.feature_status[name], self.definition_ids[name], self.missing_reasons[name] = previous
            raise

    def validate(self):
        for name in ('player_id', 'player_name', 'team_id', 'team_name', 'opponent_id', 'opponent_name',
                     'match_id', 'competition', 'season', 'data_source', 'source_match_id', 'source_player_id'):
            _text(getattr(self, name), name)
        try:
            date.fromisoformat(self.match_date)
        except (TypeError, ValueError):
            raise ValueError('ISO match_date required') from None
        if self.home_away not in ('home', 'away'):
            raise ValueError('home_away must be home or away (fixture designation)')
        for name in ('manager_id', 'manager', 'manager_period', 'nominal_position', 'starting_position',
                     'formation', 'source_team_id', 'source_opponent_id'):
            if getattr(self, name) is not None:
                _text(getattr(self, name), name)
        if self.minutes_played is not None:
            _number(self.minutes_played, 'minutes_played')
        if type(self.event_data_available) is not bool or type(self.spatial_data_available) is not bool:
            raise ValueError('Availability flags must be boolean')
        if self.spatial_data_available and not self.event_data_available:
            raise ValueError('Spatial availability denotes event coordinates, not coarse aggregates')
        for mapping in (self.features, self.feature_status, self.missing_reasons, self.definition_ids):
            if set(mapping) != set(FEATURES):
                raise ValueError('Canonical feature registry mismatch')
        for name, value in self.features.items():
            status = self.feature_status[name]
            if value is None:
                if status != 'unavailable' or self.missing_reasons[name] not in MISSING_REASONS:
                    raise ValueError(f'{name}: explicit missing reason required')
                continue
            if status not in ('observed', 'derived', 'coarse_proxy') or self.missing_reasons[name] is not None:
                raise ValueError(f'{name}: inconsistent measurement status')
            _text(self.definition_ids[name], name+' definition_id')
            spec = FEATURES[name]
            _number(value, name, 1 if spec['unit'] == 'share' else 100 if spec['unit'] == 'normalized_coordinate' else None)
            if spec['dtype'] == 'int' and int(value) != value:
                raise ValueError(f'{name}: integer count required')
            if name in EVENT_SPATIAL and (not self.spatial_data_available or status == 'coarse_proxy'):
                raise ValueError(f'{name}: event coordinates required')
            if name.endswith('_p90') and (self.minutes_played is None or self.minutes_played == 0):
                raise ValueError('per90 requires positive known minutes')
            if name.endswith('_p90'):
                raw = self.features[name[:-4] + '_raw']
                if raw is None or not math.isclose(value, per90(raw, self.minutes_played), rel_tol=1e-6, abs_tol=1e-8):
                    raise ValueError('per90 must match retained raw value and minutes')
        _validate_feature_relationships(self.features, self.minutes_played)


@dataclass
class PeriodAggregate:
    player_id: str
    team_id: str
    competition: str
    season: str
    grain: str
    period_start: str
    period_end: str
    data_source: str
    minutes_played: float | None
    manager_period: str | None = None
    features: dict = field(default_factory=lambda: dict.fromkeys(FEATURES))
    feature_status: dict = field(default_factory=lambda: dict.fromkeys(FEATURES, 'unavailable'))
    missing_reasons: dict = field(default_factory=lambda: dict.fromkeys(FEATURES, 'not_collected'))
    definition_ids: dict = field(default_factory=lambda: dict.fromkeys(FEATURES))
    source_player_id: str | None = None
    source_period_id: str | None = None
    contributing_match_ids: tuple = ()

    def validate(self):
        for name in ('player_id', 'team_id', 'competition', 'season', 'data_source'):
            _text(getattr(self, name), name)
        if self.grain not in ('player-season', 'player-manager-period', 'player-90-minutes-window'):
            raise ValueError('Explicit period grain required')
        if date.fromisoformat(self.period_start) > date.fromisoformat(self.period_end):
            raise ValueError('Invalid period')
        if self.grain == 'player-manager-period' and not self.manager_period:
            raise ValueError('Manager period required')
        if self.minutes_played is not None:
            _number(self.minutes_played, 'minutes_played')
        if set(self.features) != set(FEATURES):
            raise ValueError('Canonical feature registry mismatch')
        for mapping in (self.feature_status, self.missing_reasons, self.definition_ids):
            if set(mapping) != set(FEATURES):
                raise ValueError('Canonical metadata registry mismatch')
        for name, value in self.features.items():
            if value is None:
                if self.feature_status[name] != 'unavailable' or self.missing_reasons[name] not in MISSING_REASONS:
                    raise ValueError('Explicit period missing reason required')
                continue
            spec = FEATURES[name]
            _number(value, name, 1 if spec['unit'] == 'share' else 100 if spec['unit'] == 'normalized_coordinate' else None)
            if spec['dtype'] == 'int' and int(value) != value:
                raise ValueError('Integer count required')
            if self.feature_status[name] not in ('observed', 'derived', 'coarse_proxy') or self.missing_reasons[name] is not None:
                raise ValueError('Period measurement status inconsistent')
            _text(self.definition_ids[name], 'definition_id')
            if name.endswith('_p90'):
                expected = per90(self.features[name[:-4]+'_raw'], self.minutes_played)
                if expected is None or not math.isclose(value, expected, rel_tol=1e-6, abs_tol=1e-8):
                    raise ValueError('Period per90 inconsistent')

        _validate_feature_relationships(self.features, self.minutes_played)


def validate_cohort(rows):
    seen = set()
    for row in rows:
        if not isinstance(row, PlayerMatch):
            raise ValueError('Only player-match rows allowed; never expand season totals')
        row.validate()
        key = row.player_id, row.match_id
        if key in seen:
            raise ValueError('Duplicate player-match, including duplicate providers')
        seen.add(key)


def numeric_matrix(rows, columns, *, allow_missing=False, min_minutes=0):
    """Numeric list-of-lists for later numpy/sklearn/torch conversion, without fitting.

    Default fails closed on missing values. allow_missing is inspection-only (NaN).
    Caller must choose a common, semantically compatible feature subset explicitly.
    """
    rows, columns = list(rows), list(columns)
    if not rows or not columns or len(set(columns)) != len(columns) or not set(columns) <= set(ML_FEATURE_COLUMNS):
        raise ValueError('Nonempty rows and unique canonical numeric columns required')
    _number(min_minutes, 'min_minutes')
    validate_cohort(rows)
    for column in columns:
        definitions = {r.definition_ids[column] for r in rows if r.features[column] is not None}
        if len(definitions) > 1:
            raise ValueError(f'{column}: incompatible definitions')
    result = []
    for row in rows:
        if row.minutes_played is None or row.minutes_played <= 0 or row.minutes_played < min_minutes:
            raise ValueError('Unknown/zero/insufficient minutes: filter explicitly')
        values = [row.features[c] for c in columns]
        if not allow_missing and any(v is None for v in values):
            raise ValueError('Missing features: select common inputs or fit train-only preprocessing later')
        result.append([float('nan') if v is None else float(v) for v in values])
    return result
