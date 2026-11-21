"""Data contract for OpenMap's remote service pins, on the distributed files alone."""

import unittest
from pathlib import Path

from lupa.lua51 import LuaRuntime


CATALOG = Path(__file__).resolve().parents[1] / "RutaXP" / "WorldMapServiceData.lua"
SERVICES = {"auctioneer", "banker", "battlemaster", "innkeeper", "mailbox", "classTrainer",
            "profTrainer", "repair", "stable"}


class WorldMapServiceDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lua = LuaRuntime()
        ns = lua.table()
        lua.execute(CATALOG.read_bytes(), "RutaXP", ns)
        cls.era = ns.worldMapServiceEra
        cls.maps = {map_id: list(points.values()) for map_id, points in ns.worldMapServiceData.items()}

    def test_both_factions_can_plan_remote_capital_visits(self):
        for map_id, side in ((1453, "A"), (1455, "A"), (1454, "H")):
            with self.subTest(map_id=map_id):
                self.assertEqual({p[1] for p in self.maps[map_id] if p[2] in (side, "AH")}, SERVICES)
        self.assertTrue(any(p[1] == "profTrainer" and p[7] == "Ingeniería" and p[2] == "AH"
                            for p in self.maps[1446]))

    def test_coordinates_have_an_explicit_frame_and_specialized_trainers(self):
        for map_id, points in self.maps.items():
            for row in points:
                self.assertIn(row[1], SERVICES)
                self.assertIn(row[2], ("A", "H", "AH"))
                self.assertTrue(0 < row[3] < 100 and 0 < row[4] < 100)
                self.assertIsInstance(row[5], str)
                self.assertEqual(bool(row[6]), row[1] == "classTrainer")
                self.assertEqual(bool(row[7]), row[1] == "profTrainer")
                self.assertIsInstance(row[8], bool)
                if row[8]:
                    frame = self.era[map_id]
                    self.assertIsNotNone(frame, map_id)
                    self.assertGreater(frame[2], frame[4])
                    self.assertGreater(frame[3], frame[5])
        self.assertTrue(any(p[9] == 251373 and p[6] == "DRUID" and not p[8] for p in self.maps[2521]))
        self.assertTrue(any(p[1] == "mailbox" and (p[3], p[4], p[8]) == (61.7, 70.7, False)
                            for p in self.maps[1453]))

    def test_unreliable_legacy_repair_offers_do_not_reappear(self):
        repairs = {p[9] for points in self.maps.values() for p in points if p[1] == "repair"}
        self.assertTrue({2404, 3543}.isdisjoint(repairs))
        self.assertIn(54, repairs)
