import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api import atlas_routes


class AtlasRoutesTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_geojson_supports_points_and_lines(self):
        document = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"name": "Site"}, "geometry": {"type": "Point", "coordinates": [2.0, 48.0]}},
            {"type": "Feature", "properties": {"name": "Ligne"}, "geometry": {"type": "LineString", "coordinates": [[-5.0, 48.0], [2.0, 49.0]]}},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "data" / "atlas"
            target.mkdir(parents=True)
            (target / "nuclear.geojson").write_text(json.dumps(document), encoding="utf-8")
            with patch.object(atlas_routes, "_root", Path(directory)):
                result = await atlas_routes._local_geojson("nuclear")
        self.assertEqual(result["status"], "static")
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["paths"][0]["points"], [[48.0, -5.0], [49.0, 2.0]])

    async def test_ais_uses_public_digitraffic_fallback_without_key(self):
        payload = {"dataUpdatedTime": "2026-09-12T12:00:00Z", "features": [{
            "mmsi": 123456789,
            "geometry": {"type": "Point", "coordinates": [24.9, 60.1]},
            "properties": {"sog": 8.2, "heading": 90, "timestampExternal": 1789214400000},
        }]}
        with patch.dict("os.environ", {}, clear=True), patch.object(atlas_routes, "_json_get", return_value=payload):
            result = await atlas_routes._ships()
        self.assertEqual(result["status"], "limited")
        self.assertEqual(result["provider"], "Fintraffic Digitraffic")
        self.assertEqual(result["events"][0]["id"], "digitraffic:123456789")


if __name__ == "__main__":
    unittest.main()
