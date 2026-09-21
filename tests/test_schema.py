import copy
import math
import unittest

from src.data.schema import (
    FEATURES, ROLE_DIMENSIONS, PlayerMatch, PeriodAggregate, RawEvent,
    numeric_matrix, per90, validate_cohort, NormalizedEvent,
)


def sample(player='wirtz', minutes=90, events=True):
    # Synthetic contract fixture; not a measured Wirtz/Palmer match.
    return PlayerMatch(
        player_id='test:'+player, player_name=player, team_id='test:team:'+player,
        team_name='Synthetic team', opponent_id='test:opponent', opponent_name='Synthetic opponent',
        match_id='test:match:'+player, competition='Synthetic league', season='2023/2024',
        match_date='2024-04-06', data_source='synthetic', source_match_id='match:'+player,
        source_player_id=player, minutes_played=minutes, home_away='home',
        event_data_available=events, spatial_data_available=events,
    )


class SchemaTests(unittest.TestCase):
    def test_wirtz_palmer_same_shape_and_missing_reasons(self):
        a, b = sample(), sample('palmer', events=False)
        for row in [a, b]:
            row.set_feature('passes_attempted_raw', 20, 'observed', 'synthetic:v1')
            row.validate()
        self.assertEqual(tuple(a.features), tuple(b.features))
        self.assertEqual(a.missing_feature_count, len(FEATURES)-1)
        self.assertEqual(b.feature_status['avg_touch_x'], 'unavailable')
        self.assertEqual(numeric_matrix([a, b], ['passes_attempted_raw']), [[20.0], [20.0]])

    def test_missing_matrix_is_not_silently_imputed(self):
        with self.assertRaises(ValueError):
            numeric_matrix([sample()], ['pressures_raw'])
        self.assertTrue(math.isnan(numeric_matrix([sample()], ['pressures_raw'], allow_missing=True)[0][0]))

    def test_matrix_rejects_metadata_and_duplicates(self):
        for columns in [['player_id'], ['shots_raw', 'shots_raw'], []]:
            with self.assertRaises(ValueError):
                numeric_matrix([sample()], columns)
        with self.assertRaises(ValueError):
            validate_cohort([sample(), sample()])

    def test_source_definitions_must_match(self):
        a, b = sample(), sample('palmer')
        a.set_feature('xG_raw', 1, 'derived', 'provider-a:xg-v1')
        b.set_feature('xG_raw', 1, 'observed', 'provider-b:xg-v1')
        with self.assertRaises(ValueError):
            numeric_matrix([a, b], ['xG_raw'])

    def test_per90_and_short_appearance_filter(self):
        self.assertEqual(per90(2, 20), 9)
        self.assertIsNone(per90(2, 0))
        self.assertIsNone(per90(2, None))
        row = sample(minutes=20)
        row.set_feature('shots_raw', 2, 'observed', 'synthetic:v1')
        with self.assertRaises(ValueError):
            numeric_matrix([row], ['shots_raw'], min_minutes=30)

    def test_invalid_values_rejected(self):
        for name, value in [('shots_raw', -1), ('shots_raw', 1.5), ('pass_completion', 1.1),
                            ('avg_touch_x', 101), ('xG_raw', float('inf')), ('shots_raw', True)]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                sample().set_feature(name, value, 'observed', 'test:v1')

    def test_no_fake_spatial_values_without_spatial_coverage(self):
        with self.assertRaises(ValueError):
            sample('palmer', events=False).set_feature('avg_touch_x', 50, 'derived', 'test:v1')

    def test_identifiers_dates_minutes_and_quality(self):
        for field, value in [('match_date', '2024-02-30'), ('minutes_played', -1),
                             ('player_id', ''), ('home_away', 'other')]:
            row = sample()
            setattr(row, field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                row.validate()
        self.assertEqual(sample().player_season_id, ('test:wirtz', 'Synthetic league', '2023/2024'))
        self.assertIn('partial_features', sample().data_quality_flag)

    def test_null_requires_reason_and_complete_registry(self):
        row = sample()
        row.missing_reasons['shots_raw'] = None
        with self.assertRaises(ValueError):
            row.validate()
        row = sample()
        row.features['provider_special'] = 1
        with self.assertRaises(ValueError):
            row.validate()
        self.assertTrue(all(set(v) <= set(FEATURES) for v in ROLE_DIMENSIONS.values()))

    def test_period_fallback_cannot_enter_match_matrix(self):
        period = PeriodAggregate('test:palmer', 'test:chelsea', 'Premier League', '2023/2024',
                                 'player-season', '2023-07-01', '2024-06-30', 'synthetic', 2000)
        period.validate()
        with self.assertRaises(ValueError):
            numeric_matrix([period], ['shots_raw'])

    def test_raw_payload_kept_without_provider_columns_in_matrix(self):
        payload = {'id': 'e1', 'type': {'name': 'Pass'}, 'custom': {'unknown': True}}
        raw = RawEvent('synthetic', 'm1', 'e1', copy.deepcopy(payload))
        raw.validate()
        self.assertEqual(raw.payload, payload)

    def test_normalized_event_contract(self):
        event = NormalizedEvent('test:m', 'test:e', 'synthetic', 'm', 'e', 1, 1, 0, 0, 'pass')
        event.validate()
        event.normalized_x = 50
        with self.assertRaises(ValueError):
            event.validate()
        event.normalized_y = 50
        event.source_x, event.source_y = 60, 40
        event.coordinate_transform = 'statsbomb-120x80-ltr-top-v1'
        event.validate()
        event.second = 60
        with self.assertRaises(ValueError):
            event.validate()

    def test_period_features_require_provenance(self):
        period = PeriodAggregate('test:p', 'test:t', 'league', '2023/2024',
                                 'player-season', '2023-07-01', '2024-06-30', 'synthetic', 2000)
        period.features['shots_raw'] = -1
        with self.assertRaises(ValueError):
            period.validate()

    def test_season_fallback_keeps_real_aggregate_without_fake_matches(self):
        period = PeriodAggregate('test:p', 'test:t', 'league', '2023/2024',
                                 'player-season', '2023-07-01', '2024-06-30', 'synthetic', 1800)
        period.features['shots_raw'] = 40
        period.feature_status['shots_raw'] = 'observed'
        period.missing_reasons['shots_raw'] = None
        period.definition_ids['shots_raw'] = 'test:shots-v1'
        period.validate()
        self.assertEqual(period.features['shots_raw'], 40)
        self.assertFalse(hasattr(period, 'match_id'))

    def test_multicolumn_matrix_preserves_explicit_order(self):
        rows = [sample(), sample('palmer', events=False)]
        for row, shots in zip(rows, (2, 3)):
            row.set_feature('shots_raw', shots, 'observed', 'synthetic:shots-v1')
            row.set_feature('passes_attempted_raw', 20, 'observed', 'synthetic:passes-v1')
            row.set_feature('shots_p90', shots, 'derived', 'synthetic:shots-p90-v1')
        self.assertEqual(numeric_matrix(rows, ['shots_p90', 'passes_attempted_raw']),
                         [[2.0, 20.0], [3.0, 20.0]])

    def test_inconsistent_per90_and_score_minutes(self):
        row = sample(minutes=20)
        row.set_feature('shots_raw', 2, 'observed', 'test:shots-v1')
        with self.assertRaises(ValueError):
            row.set_feature('shots_p90', 2, 'derived', 'test:shots-p90-v1')
        row.set_feature('score_state_minutes_winning', 20, 'derived', 'test:winning-v1')
        row.set_feature('score_state_minutes_drawing', 0, 'derived', 'test:drawing-v1')
        with self.assertRaises(ValueError):
            row.set_feature('score_state_minutes_losing', 10, 'derived', 'test:losing-v1')

    def test_completion_must_agree_with_counts(self):
        row = sample()
        row.set_feature('passes_attempted_raw', 10, 'observed', 'test:v1')
        row.set_feature('passes_completed_raw', 8, 'observed', 'test:v1')
        with self.assertRaises(ValueError):
            row.set_feature('pass_completion', 0.5, 'derived', 'test:v1')
        row.set_feature('pass_completion', 0.8, 'derived', 'test:v1')
        self.assertEqual(row.features['pass_completion'], 0.8)

    def test_zero_attempts_has_no_completion_rate(self):
        row = sample()
        row.set_feature('passes_attempted_raw', 0, 'observed', 'test:v1')
        with self.assertRaises(ValueError):
            row.set_feature('pass_completion', 0, 'observed', 'test:v1')

    def test_period_rejects_completed_over_attempted(self):
        period = PeriodAggregate('test:p', 'test:t', 'league', '2023/2024',
                                 'player-season', '2023-07-01', '2024-06-30', 'synthetic', 1800)
        for name, value in [('passes_attempted_raw', 1), ('passes_completed_raw', 2)]:
            period.features[name] = value
            period.feature_status[name] = 'observed'
            period.definition_ids[name] = 'test:v1'
            period.missing_reasons[name] = None
        with self.assertRaises(ValueError):
            period.validate()

    def test_context_is_not_role_input(self):
        from src.data.schema import ML_FEATURE_COLUMNS
        self.assertNotIn('team_possession', ML_FEATURE_COLUMNS)
        self.assertNotIn('player_id', ML_FEATURE_COLUMNS)
        with self.assertRaises(ValueError):
            numeric_matrix([sample()], ['score_state_minutes_winning'], allow_missing=True)

    def test_zero_and_missing_xa_are_distinct(self):
        a, b = sample(), sample('palmer', events=False)
        a.set_feature('xA_raw', 0, 'observed', 'synthetic:xa-v1')
        b.set_feature('xA_raw', None, missing_reason='source_not_provided')
        matrix = numeric_matrix([a, b], ['xA_raw'], allow_missing=True)
        self.assertEqual(matrix[0], [0.0])
        self.assertTrue(math.isnan(matrix[1][0]))

    def test_normalized_event_cannot_leave_source_coordinates_unconverted(self):
        event = NormalizedEvent('test:m', 'test:e', 'synthetic', 'm', 'e', 1, 1, 0, 0, 'pass',
                                source_x=60, source_y=40)
        with self.assertRaises(ValueError):
            event.validate()

    def test_named_synthetic_players_and_manager_filters(self):
        w, p = sample(minutes=20), sample('palmer', events=False)
        w.player_name, p.player_name = 'Florian Wirtz', 'Cole Palmer'
        w.team_name, p.team_name = 'Bayer Leverkusen', 'Chelsea'
        w.data_source, p.data_source = 'synthetic:event-source', 'synthetic:aggregate-source'
        w.manager, w.manager_id, w.manager_period = 'Xabi Alonso', 'test:alonso', 'test:leverkusen:alonso'
        p.manager, p.manager_id, p.manager_period = 'Synthetic manager', 'test:manager', 'test:chelsea:period'
        for row, count in [(w, 2), (p, 3)]:
            row.set_feature('shots_raw', count, 'observed', 'synthetic:shots-v1')
            row.set_feature('shots_p90', per90(count, row.minutes_played), 'derived', 'synthetic:shots-p90-v1')
        self.assertEqual(tuple(w.features), tuple(p.features))
        self.assertEqual(numeric_matrix([w, p], ['shots_raw', 'shots_p90']), [[2., 9.], [3., 3.]])
        self.assertEqual([r.player_name for r in [w, p] if r.team_id == w.team_id and
                          r.manager_id == 'test:alonso' and r.manager_period == 'test:leverkusen:alonso'], ['Florian Wirtz'])
