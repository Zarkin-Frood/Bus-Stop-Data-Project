import os
import sys
import tempfile
import time
import unittest
import urllib.error
from datetime import date
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from busstopdata import BusStopService
from crime_stats import CrimeStatsService


def crime_row(**overrides):
    row = {
        "Incident": "1001", "Occurrence Date": "3/15/2025", "Occurrence Hour": "14",
        "NIBRS Class": "23F", "NIBRS Description": "THEFT FROM MOTOR VEHICLE",
        "Offense Count": "1", "Beat": "10H10", "Premise": "STREET",
        "Street Number": "100", "Street Name": "MAIN", "Street Type": "ST",
        "Street Suffix": "", "City": "HOUSTON", "ZIP Code": "77002",
        "Map Longitude": "-95.36", "Map Latitude": "29.76",
    }
    row.update(overrides)
    return row


class CrimeParsingTests(unittest.TestCase):
    def setUp(self):
        self.service = CrimeStatsService(start_date=date(2025, 1, 1), end_date=date(2025, 12, 31))

    def parse(self, *rows):
        return self.service._parse_rows(rows)

    def test_keeps_valid_row(self):
        crimes = self.parse(crime_row())
        self.assertEqual(len(crimes), 1)
        self.assertEqual(crimes[0].street, "100 MAIN ST")
        self.assertEqual(crimes[0].occurred_at.hour, 14)

    def test_drops_zero_and_out_of_area_coordinates(self):
        crimes = self.parse(
            crime_row(**{"Map Longitude": "0", "Map Latitude": "0"}),
            crime_row(**{"Map Longitude": "", "Map Latitude": ""}),
            crime_row(**{"Map Longitude": "-118.2", "Map Latitude": "34.0"}),
        )
        self.assertEqual(crimes, [])
        self.assertEqual(self.service.last_load_stats["bad_coords"], 3)

    def test_drops_rows_outside_window(self):
        crimes = self.parse(crime_row(**{"Occurrence Date": "12/31/2024"}),
                            crime_row(**{"Occurrence Date": "1/1/2026"}))
        self.assertEqual(crimes, [])
        self.assertEqual(self.service.last_load_stats["outside_window"], 2)

    def test_bad_date_is_counted_not_silent(self):
        self.parse(crime_row(**{"Occurrence Date": "not a date"}))
        self.assertEqual(self.service.last_load_stats["bad_date"], 1)

    def test_blank_hour_defaults_to_midnight(self):
        crimes = self.parse(crime_row(**{"Occurrence Hour": ""}))
        self.assertEqual(crimes[0].occurred_at.hour, 0)

    def test_rolling_window_excludes_old_data(self):
        rolling = CrimeStatsService(recent_days=30)
        self.assertEqual(rolling._parse_rows([crime_row()]), [])


class CrimeCacheTests(unittest.TestCase):
    def test_fresh_cache_skips_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cache.csv")
            with open(path, "w") as f:
                f.write("a,b\n1,2\n")
            service = CrimeStatsService(cache_path=path)
            with mock.patch("crime_stats.urllib.request.urlopen", side_effect=AssertionError("downloaded")):
                self.assertIn("1,2", service._fetch_text())

    def test_stale_cache_used_when_download_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cache.csv")
            with open(path, "w") as f:
                f.write("a,b\n1,2\n")
            old = time.time() - 72 * 3600
            os.utime(path, (old, old))
            service = CrimeStatsService(cache_path=path)
            with mock.patch("crime_stats.urllib.request.urlopen",
                            side_effect=urllib.error.URLError("offline")):
                self.assertIn("1,2", service._fetch_text())

    def test_no_cache_and_download_fails_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = CrimeStatsService(cache_path=os.path.join(tmp, "missing.csv"))
            with mock.patch("crime_stats.urllib.request.urlopen",
                            side_effect=urllib.error.URLError("offline")):
                with self.assertRaises(urllib.error.URLError):
                    service._fetch_text()


def stop_feature(routes="82", coords=(-95.4, 29.7), stop_id="S1"):
    return {
        "properties": {"STOPID": stop_id, "STOPNAME": "Test Stop", "SRVD_RTS": routes},
        "geometry": {"coordinates": list(coords)} if coords else None,
    }


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get_json(self, url, params=None):
        i = len(self.calls)
        self.calls.append(dict(params))
        return {"features": self.pages[i] if i < len(self.pages) else []}


class BusStopTests(unittest.TestCase):
    def test_exact_route_match(self):
        features = [
            stop_feature("82", stop_id="a"),
            stop_feature("50,82,100", stop_id="b"),
            stop_feature("182", stop_id="c"),
            stop_feature("820", stop_id="d"),
            stop_feature(None, stop_id="e"),
        ]
        service = BusStopService(FakeClient([]))
        stops = service._parse_geojson(features, "82")
        self.assertEqual([s.stop_id for s in stops], ["a", "b"])
        self.assertEqual(service.last_load_stats["wrong_route"], 3)

    def test_skips_missing_geometry(self):
        service = BusStopService(FakeClient([]))
        stops = service._parse_geojson([stop_feature(coords=None), stop_feature(stop_id="ok")], "82")
        self.assertEqual([s.stop_id for s in stops], ["ok"])
        self.assertEqual(service.last_load_stats["no_coords"], 1)

    def test_pages_until_empty(self):
        client = FakeClient([
            [stop_feature(stop_id="1"), stop_feature(stop_id="2")],
            [stop_feature(stop_id="3")],
        ])
        service = BusStopService(client)
        service.load_route_82()
        self.assertEqual(len(service.get_stops()), 3)
        self.assertEqual([c["resultOffset"] for c in client.calls], [0, 2, 3])

    def test_arcgis_error_raises(self):
        class ErrClient:
            def get_json(self, url, params=None):
                return {"error": {"code": 400, "message": "Invalid query"}}
        with self.assertRaises(RuntimeError):
            BusStopService(ErrClient()).load_route_82()

    def test_rejects_odd_route_values(self):
        with self.assertRaises(ValueError):
            BusStopService(FakeClient([])).load_route("82' OR '1'='1")


if __name__ == "__main__":
    unittest.main()
