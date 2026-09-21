import copy
import json
from pathlib import Path
import tempfile
import unittest
from src.data.ingestion import build_statsbomb_dataset, save_dataset, read_dataset
from src.data.validation import validate_dataset, quality_report
from src.data.sources.statsbomb import StatsBombAdapter, discover_season

class IngestionTests(unittest.TestCase):
    def setUp(self):
        f=json.loads((Path(__file__).parent/'fixtures/ingestion_sample.json').read_text())
        self.f=f
        self.d=build_statsbomb_dataset(StatsBombAdapter(), [f['match']], {'10':f['lineups']}, {'10':f['events']})

    def test_fixture_schema_and_report(self):
        validate_dataset(self.d)
        r=quality_report(self.d)
        self.assertEqual(r['matches'],1);self.assertEqual(r['events'],4)
        self.assertEqual(r['missing_player_id_pct'],50.)
        self.assertEqual(r['event_type_counts'],{'PASS':2,'OTHER':2})
        self.assertEqual(r['coordinate_ranges']['normalized_x'],[0.,0.])

    def test_repeated_write_and_typed_roundtrip(self):
        with tempfile.TemporaryDirectory() as p:
            save_dataset(self.d,Path(p),{'license_notice':'synthetic'})
            first=read_dataset(Path(p))
            save_dataset(self.d,Path(p),{'license_notice':'synthetic'})
            self.assertEqual(first,read_dataset(Path(p)))
            self.assertEqual(len(first['events']),4)
            self.assertIs(first['events'][0]['under_pressure'],False)
            self.assertIsNone(first['events'][2]['under_pressure'])
            self.assertIsInstance(first['events'][0]['event_index'],int)

    def test_duplicates_and_relationships_rejected(self):
        for kind in ['duplicate','team','player','order','coordinate']:
            d=copy.deepcopy(self.d)
            if kind=='duplicate': d['events'].append(d['events'][0])
            if kind=='team': d['events'][0]['team_id']='statsbomb:team:999'
            if kind=='player': d['events'][0]['player_id']='statsbomb:player:999'
            if kind=='order': d['events'].reverse()
            if kind=='coordinate': d['events'][0]['normalized_x']=101
            with self.subTest(kind=kind), self.assertRaises(ValueError): validate_dataset(d)

    def test_dynamic_season_id(self):
        c=[{'competition_id':9,'season_id':999,'season_name':'2023/2024'}]
        self.assertEqual(discover_season(c,9,'2023/2024'),999)
        with self.assertRaises(ValueError): discover_season(c,9,'2024/2025')

    def test_aggregate_csv_full_roundtrip(self):
        import csv
        from src.data.sources.aggregate_csv import AggregateCSVAdapter
        from src.data.ingestion import build_aggregate_dataset
        metadata={'source_name':'synthetic_export','source_version':'test-v1','source_url':'https://example.invalid',
                  'license_notice':'synthetic','permission_basis':'synthetic fixture','event_definition_notes':'test',
                  'column_map':{'shots_raw':'Shots','xA_raw':'xA'}}
        row={'source_match_id':'10','source_player_id':'7','source_team_id':'1','source_opponent_id':'2',
             'player_name':'Synthetic Palmer','team_name':'Synthetic Chelsea','opponent_name':'Synthetic Away',
             'competition':'Test League','season':'2023/2024','match_date':'2024-04-06',
             'home_away':'home','minutes_played':'20','Shots':'0','xA':''}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.csv'
            with path.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=row);writer.writeheader();writer.writerow(row)
            d=build_aggregate_dataset(AggregateCSVAdapter(path,metadata),1)
            save_dataset(d,Path(tmp)/'output',metadata)
            result=read_dataset(Path(tmp)/'output')
            self.assertEqual(result['events'],[])
            self.assertEqual(result['player_match_aggregate_stats'][0]['shots_raw'],0)
            self.assertIsNone(result['player_match_aggregate_stats'][0]['xA_raw'])
            self.assertEqual(result['players'][0]['minutes_played'],20.)

    def test_processed_checksum_detects_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);save_dataset(self.d,p,{'license_notice':'synthetic'})
            with (p/'events.parquet').open('ab') as f: f.write(b'bad')
            with self.assertRaises(ValueError): read_dataset(p)

    def test_raw_cache_offline_and_catalogue_refresh(self):
        from src.data.sources.base import JSONCache
        from unittest.mock import patch
        import io
        with tempfile.TemporaryDirectory() as tmp:
            cache=JSONCache(tmp,'https://example.invalid')
            with patch('urllib.request.urlopen',side_effect=[io.BytesIO(b'[1]'),io.BytesIO(b'[2]')]) as download:
                self.assertEqual(cache.load('competitions.json',refresh=True),[1])
                self.assertEqual(cache.load('competitions.json'),[1])
                self.assertEqual(cache.load('competitions.json',refresh=True),[2])
                self.assertEqual(download.call_count,2)
            offline=JSONCache(tmp,'https://example.invalid',offline=True)
            self.assertEqual(offline.load('competitions.json',refresh=True),[2])
            with self.assertRaises(FileNotFoundError): offline.load('absent.json')
            (Path(tmp)/'competitions.json').write_text('[3]')
            with self.assertRaises(ValueError): offline.load('competitions.json')

    def test_reversed_source_events_sorted_before_validation(self):
        d=build_statsbomb_dataset(StatsBombAdapter(),[self.f['match']],{'10':self.f['lineups']},
                                 {'10':list(reversed(self.f['events']))})
        self.assertEqual([r['event_index'] for r in d['events']],[1,2,3,4])

    def test_360_uuid_integrity_and_optional_cache_miss(self):
        from src.data.ingestion import inspect_360
        from unittest.mock import Mock
        adapter=Mock()
        adapter.load_360.return_value=[{'event_uuid':'e1'}]
        self.assertEqual(inspect_360(adapter,'10',self.f['events'])['frames'],1)
        adapter.load_360.return_value=[{'event_uuid':'orphan'}]
        with self.assertRaises(ValueError): inspect_360(adapter,'10',self.f['events'])
        adapter.load_360.side_effect=FileNotFoundError('not downloaded')
        self.assertEqual(inspect_360(adapter,'10',self.f['events'])['status'],'not_cached')

    def test_playerless_team_does_not_validate_unknown_player(self):
        d=copy.deepcopy(self.d)
        d['events'][0]['event_type']='OTHER'
        d['events'][0]['team_id']=None
        d['events'][0]['player_id']='statsbomb:player:999'
        with self.assertRaises(ValueError): validate_dataset(d)

    def test_timestamp_and_nominal_minute_agree(self):
        d=copy.deepcopy(self.d)
        d['events'][2]['minute']=0
        with self.assertRaises(ValueError): validate_dataset(d)
