"""Small synthetic unit cases only; never used by the real report."""
import unittest
from unittest.mock import Mock
from src.data.ingestion import inspect_360_optional

class Optional360Tests(unittest.TestCase):
    def test_invalid_frames_do_not_block_event_ingestion(self):
        a=Mock(); a.load_360.return_value=[{'event_uuid':'orphan'}]
        self.assertEqual(inspect_360_optional(a,'1',[{'id':'real'}])['status'],'invalid_linkage')

class TacticalMetricsTests(unittest.TestCase):
    def test_receipts_proxy_and_progression_boundaries(self):
        from src.analysis.wirtz_role_mvp import metrics
        def e(t,x=60,y=20,ex=70,ey=20,outcome='COMPLETE',period=1):
            return dict(event_type=t, normalized_x=x,normalized_y=y,normalized_end_x=ex,
                        normalized_end_y=ey,outcome=outcome,period=period)
        rows=[e('PASS'),e('PASS',outcome='INCOMPLETE'),e('CARRY',x=80,ex=90),
              e('RECEIPT'),e('RECEIPT',outcome='INCOMPLETE'),e('PRESSURE'),
              e('SHOT',period=5),e('PASS',x=None,y=None,ex=None,ey=None)]
        m=metrics(rows,90)
        self.assertEqual(m['touches_proxy'],5)
        self.assertEqual(m['located_touches_proxy'],4)
        self.assertEqual(m['receptions'],1)
        self.assertEqual(m['progressive_passes'],1)
        self.assertEqual(m['progressive_carries'],1)
        self.assertEqual(m['final_third_entries'],1)
        self.assertEqual(m['penalty_area_entries'],0) # y=20 is outside box
        self.assertEqual(m['left_halfspace_share'],1)
        self.assertEqual(m['pressures'],1)
        self.assertEqual(m['shots'],0)

    def test_empty_spatial_and_unknown_minutes_stay_null(self):
        from src.analysis.wirtz_role_mvp import metrics
        m=metrics([],None)
        self.assertIsNone(m['avg_touch_x'])
        self.assertIsNone(m['left_share'])
        self.assertIsNone(m['passes_p90'])
        self.assertIsNone(m['nearest_defender_distance'])

    def test_unknown_endpoints_and_box_boundaries(self):
        from src.analysis.wirtz_role_mvp import action_flags
        e=dict(event_type='CARRY',normalized_x=80,normalized_y=22.5,normalized_end_x=None,normalized_end_y=None,outcome=None)
        self.assertIsNone(action_flags(e)['progressive'])
        e.update(normalized_end_x=85,normalized_end_y=22.5)
        self.assertTrue(action_flags(e)['penalty_area_entry'])
        e.update(normalized_x=85)
        self.assertFalse(action_flags(e)['penalty_area_entry'])
        e.update(normalized_x=60,normalized_end_x=200/3)
        self.assertTrue(action_flags(e)['final_third_entry'])
        e.update(normalized_x=200/3)
        self.assertFalse(action_flags(e)['final_third_entry'])
