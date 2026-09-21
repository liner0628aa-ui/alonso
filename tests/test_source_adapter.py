import copy
import json
from pathlib import Path
import unittest
from src.data.sources.statsbomb import StatsBombAdapter
from src.data.sources.aggregate_csv import AggregateCSVAdapter

FIXTURE = Path(__file__).parent / 'fixtures/ingestion_sample.json'

class SourceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.f = json.loads(FIXTURE.read_text())
        self.a = StatsBombAdapter()

    def test_event_conversion_and_no_halftime_double_flip(self):
        for e in (self.f['events'][0], self.f['events'][2]):
            r = self.a.normalize_event(e, '10')
            self.assertEqual(r['event_type'], 'PASS')
            self.assertEqual(r['player_id'], 'statsbomb:player:7')
            self.assertEqual(r['source_player_id'], '7')
            self.assertEqual((r['normalized_x'], r['normalized_y']), (0., 0.))
            self.assertEqual((r['normalized_end_x'], r['normalized_end_y']), (100., 100.))
            self.assertEqual(r['source_end_x'], 120)
            self.assertEqual(r['outcome'], 'COMPLETE')
        self.assertIs(self.a.normalize_event(self.f['events'][0], '10')['under_pressure'], False)
        self.assertIsNone(self.a.normalize_event(self.f['events'][2], '10')['under_pressure'])

    def test_missing_coordinates_and_nonplayer_event(self):
        r = self.a.normalize_event(self.f['events'][1], '10')
        self.assertIsNone(r['normalized_x'])
        self.assertIsNone(r['player_id'])
        self.assertEqual(r['event_type'], 'OTHER')

    def test_unknown_type_and_stable_fallback_id(self):
        e = copy.deepcopy(self.f['events'][1]); e.pop('id'); e['type']['name'] = 'New type'
        r = self.a.normalize_event(e, '10')
        self.assertEqual(r['event_type'], 'OTHER')
        self.assertEqual(r, self.a.normalize_event(e, '10'))
        self.assertEqual(r['source_event_id'], 'index:2')

    def test_invalid_coordinate_rejected(self):
        e = copy.deepcopy(self.f['events'][0]); e['location'] = [121, 0]
        with self.assertRaises(ValueError): self.a.normalize_event(e, '10')

    def test_tackle_taxonomy(self):
        e = copy.deepcopy(self.f['events'][0]); e['type']['name'] = 'Duel'; e['duel']={'type':{'name':'Tackle'}}
        self.assertEqual(self.a.normalize_event(e, '10')['event_type'], 'TACKLE')

    def test_match_and_player_minutes_include_added_time_not_break(self):
        m = self.a.normalize_match(self.f['match'])
        self.assertEqual(m['home_manager_id'], 'statsbomb:manager:9')
        p = self.a.normalize_player(self.f['lineups'][0]['lineup'][0], self.f['lineups'][0], m, self.f['events'])
        self.assertEqual(p['minutes_played'], 95.)
        self.assertIsNone(p['manager_period'])
        self.assertEqual(p['starting_position'], 'Attacking Midfield')

    def test_missing_half_end_keeps_minutes_unknown(self):
        m = self.a.normalize_match(self.f['match'])
        p = self.a.normalize_player(self.f['lineups'][0]['lineup'][0], self.f['lineups'][0], m, [])
        self.assertIsNone(p['minutes_played'])

    def test_aggregate_raw_only_and_missing_zero_distinction(self):
        metadata = {'source_name':'synthetic_export','source_version':'test-v1',
                    'source_url':'https://example.invalid/synthetic','license_notice':'synthetic test',
                    'permission_basis':'synthetic test fixture, not real data', 'event_definition_notes':'test counts',
                    'column_map':{'shots_raw':'Shots','xA_raw':'xA'}}
        a = AggregateCSVAdapter(metadata=metadata)
        row = {'source_match_id':'10','source_player_id':'7','source_team_id':'1', 'source_opponent_id':'2',
               'player_name':'Test Player','team_name':'Home','opponent_name':'Away','competition':'Test League',
               'season':'2023/2024','match_date':'2024-04-06','home_away':'home','minutes_played':'20','Shots':'0','xA':''}
        r = a.normalize_aggregate_stat_row(row)
        self.assertEqual(r['shots_raw'], 0)
        self.assertIsNone(r['xA_raw'])
        self.assertFalse(any(k.endswith('_p90') for k in r))
        self.assertEqual(r['player_id'], 'synthetic_export:player:7')
        self.assertFalse(r['event_data_available'])
        row['Shots'] = '-1'
        with self.assertRaises(ValueError): a.normalize_aggregate_stat_row(row)

    def test_aggregate_rejects_unapproved_or_derived_columns(self):
        with self.assertRaises(ValueError): AggregateCSVAdapter(metadata={})

    def test_substitute_second_half_minutes(self):
        p=copy.deepcopy(self.f['lineups'][0]['lineup'][0])
        p['positions'][0].update({'from':'60:00','from_period':2,'start_reason':'Substitution'})
        r=self.a.normalize_player(p,self.f['lineups'][0],self.a.normalize_match(self.f['match']),self.f['events'])
        self.assertEqual(r['minutes_played'],33.)
        self.assertFalse(r['starter'])

    def test_extra_time_minutes(self):
        events=copy.deepcopy(self.f['events'])
        for period,clock in [(3,'00:16:00.000'),(4,'00:17:00.000')]:
            events.append({'type':{'name':'Half End'},'period':period,'timestamp':clock})
        r=self.a.normalize_player(self.f['lineups'][0]['lineup'][0],self.f['lineups'][0],
                                  self.a.normalize_match(self.f['match']),events)
        self.assertEqual(r['minutes_played'],128.)

    def test_known_action_without_player_is_invalid(self):
        from src.data.ingestion import build_statsbomb_dataset
        self.f['events'][0].pop('player')
        with self.assertRaises(ValueError):
            build_statsbomb_dataset(self.a,[self.f['match']],{'10':self.f['lineups']},{'10':self.f['events']})
