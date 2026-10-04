"""Exact Overpass query identity must survive cache reuse without case aliasing."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('itinerary_map', Path(__file__).resolve().parents[1] / '.claude/scripts/itinerary-map.py')
MAP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MAP)


class ExactPoiCache(unittest.TestCase):
    def test_case_variants_have_distinct_results_and_repeat_uses_cache(self):
        bbox = [1, 2, 3, 4]
        hit = {'lat': 1, 'lon': 2, 'display': 'Example Cafe'}
        cache = {}
        with patch.object(MAP, '_overpass_query_once', side_effect=[None, hit]) as query:
            self.assertIsNone(MAP.overpass_geocode('example cafe', bbox, cache, True))
            self.assertEqual(hit, MAP.overpass_geocode('Example Cafe', bbox, cache, True))
            self.assertEqual(hit, MAP.overpass_geocode('Example Cafe', bbox, cache, False))
            self.assertIsNone(MAP.overpass_geocode('example cafe', bbox, cache, False))
            self.assertEqual(2, query.call_count)

    def test_old_lowercase_zero_is_not_authority_for_corrected_case(self):
        bbox = [1, 2, 3, 4]
        old_key = 'overpass::example cafe::1.000,2.000,3.000,4.000'
        cache = {old_key: None}
        hit = {'lat': 1, 'lon': 2, 'display': 'Example Cafe'}
        with patch.object(MAP, '_overpass_query_once', return_value=hit) as query:
            self.assertIsNone(MAP.overpass_geocode('Example Cafe', bbox, cache, False))
            query.assert_not_called()
            self.assertEqual(hit, MAP.overpass_geocode('Example Cafe', bbox, cache, True))
            query.assert_called_once_with('Example Cafe', bbox, True)
        self.assertIn(old_key, cache)
        self.assertIsNone(cache[old_key])

    def test_network_error_is_not_cached_as_an_honest_zero(self):
        cache = {}
        with patch.object(MAP, '_overpass_query_once', side_effect=MAP.GeocodeNetworkError('unavailable')):
            with self.assertRaises(MAP.GeocodeNetworkError):
                MAP.overpass_geocode('Example Cafe', [1, 2, 3, 4], cache, True)
        self.assertEqual({}, cache)


if __name__ == '__main__':
    unittest.main()
