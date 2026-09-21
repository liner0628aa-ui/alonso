import unittest

from src.data.coordinate_normalization import normalize_point, normalize_coordinates
from src.config.pitch_zones import classify_zone


class CoordinateTests(unittest.TestCase):
    def test_statsbomb_scale_and_preserve_source(self):
        r = normalize_coordinates(120, 80, 60, 40, width=120, height=80)
        self.assertEqual(r['source_x'], 120)
        self.assertEqual(r['normalized_x'], 100)
        self.assertEqual(r['normalized_end_y'], 50)

    def test_reverse_is_rotation_not_x_only(self):
        self.assertEqual(normalize_point(20, 10, direction='right_to_left'), (80, 90))

    def test_bottom_origin_and_already_normalized(self):
        self.assertEqual(normalize_point(20, 10, y_origin='bottom'), (20, 90))
        self.assertEqual(normalize_point(20, 10), (20, 10))

    def test_missing_pair_and_invalid_coordinates(self):
        self.assertEqual(normalize_point(None, None), (None, None))
        for x, y in [(None, 1), (-1, 0), (101, 1), (float('nan'), 2), (True, 2)]:
            with self.subTest(x=x), self.assertRaises(ValueError):
                normalize_point(x, y)
        for kw in [{'width': 0}, {'direction': 'unknown'}, {'y_origin': 'unknown'}]:
            with self.assertRaises(ValueError):
                normalize_point(1, 1, **kw)

    def test_zone_edges_and_box_overlap(self):
        self.assertEqual(classify_zone(0, 0), ('left_wing', 'defensive_third', False))
        self.assertEqual(classify_zone(100/3, 20)[:2], ('left_halfspace', 'middle_third'))
        self.assertEqual(classify_zone(100, 100)[:2], ('right_wing', 'final_third'))
        self.assertEqual(classify_zone(90, 50), ('centre', 'final_third', True))
        self.assertEqual(classify_zone(None, None), (None, None, None))
        with self.assertRaises(ValueError):
            classify_zone(101, 50)

    def test_corners_centre_and_all_lane_boundaries(self):
        for point in [(0, 0), (100, 100), (50, 50)]:
            self.assertEqual(normalize_point(*point), point)
        self.assertEqual(classify_zone(50, 50), ('centre', 'middle_third', False))
        for edge, left, right in [(20, 'left_wing', 'left_halfspace'),
                                  (40, 'left_halfspace', 'centre'),
                                  (60, 'centre', 'right_halfspace'),
                                  (80, 'right_halfspace', 'right_wing')]:
            self.assertEqual(classify_zone(50, edge-1e-8)[0], left)
            self.assertEqual(classify_zone(50, edge)[0], right)
            self.assertEqual(classify_zone(50, edge+1e-8)[0], right)
        self.assertEqual(normalize_point(0, 0, direction='right_to_left'), (100, 100))
        self.assertEqual(normalize_point(100, 100, direction='right_to_left'), (0, 0))

    def test_penalty_box_is_overlay_inside_final_third(self):
        for point in [(85, 22.5), (85, 77.5), (100, 50)]:
            self.assertEqual(classify_zone(*point)[1:], ('final_third', True))
        for point in [(85-1e-8, 50), (90, 22.5-1e-8), (90, 77.5+1e-8)]:
            self.assertEqual(classify_zone(*point)[1:], ('final_third', False))
        self.assertEqual(classify_zone(200/3, 50)[1], 'final_third')
