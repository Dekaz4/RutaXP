"""Public world-map service data, projected independently of the current guide."""

import json
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]


class MapServiceTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("""
            faction, class = "Alliance", "PALADIN"
            UnitFactionGroup = function() return faction end
            UnitClass = function() return class, class end
            ns = { ResolveWaypointPoint = function(self, s)
                if not available and s.f == "e" then return nil end
                local offset = s.f == "e" and 0.001 or 0
                return {mapID = s.map, x = s.x/100 + offset, y = s.y/100}
            end }
        """)
        self.ns = self.lua.globals().ns
        self.lua.execute((ROOT / "RutaXP/MapServices.lua").read_text(encoding="utf-8"),
                         "RutaXP", self.ns)

    def points(self, zone):
        return list(self.ns.GetMapServicePoints(self.ns, zone).values())

    def test_unavailable_era_points_retry_and_live_coordinates_are_unchanged(self):
        points = self.points(1453)
        self.assertFalse(any(p.category == "auction" for p in points))
        inn = next(p for p in points if p.category == "inn")
        self.assertAlmostEqual(inn.x, .6039)
        self.lua.globals().available = True
        auction = next(p for p in self.points(1453) if p.name == "Subastador Fitch")
        self.assertAlmostEqual(auction.x, .537)
        self.assertAlmostEqual(auction.y, .605)
        self.assertFalse(self.points(999999))

    def test_faction_and_class_select_only_accessible_services_without_a_guide(self):
        self.lua.globals().available = True
        paladin = self.points(1453)
        self.assertEqual({p.category for p in paladin},
                         {"bank", "auction", "repair", "vendor", "inn", "flight", "mailbox", "trainer",
                          "vendor_goods", "vendor_food", "vendor_equipment", "vendor_supplies",
                          "vendor_reagents", "vendor_bags", "vendor_mounts"})
        self.assertFalse(any(p.name == "Osborne" for p in paladin))
        self.lua.globals()["class"] = "ROGUE"
        self.assertTrue(any(p.name == "Osborne" for p in self.points(1453)))
        ally_flights = [p.x for p in self.points(1446) if p.category == "flight"]
        self.lua.globals().faction = "Horde"
        self.assertFalse(any(p.category == "mailbox" for p in self.points(1453)))
        horde_flights = [p.x for p in self.points(1446) if p.category == "flight"]
        self.assertEqual((len(ally_flights), len(horde_flights)), (1, 1))
        self.assertNotEqual(ally_flights, horde_flights)

    def test_merchants_keep_their_names_and_show_a_sourced_specialty(self):
        self.lua.globals().available = True
        points = {p.npc: p for p in self.points(1453) if p.npc}
        cases = {
            1321: ("vendor_bags", "Bolsas"),
            1326: ("vendor_reagents", "Venenos"),
            5565: ("vendor_supplies", "Suministros de peletería"),
            3518: ("vendor_food", "Pan y productos de panadería"),
            1304: ("vendor_goods", "Fuegos artificiales"),
            1297: ("repair", "Arcos y armas de fuego"),
        }
        for npc, expected in cases.items():
            with self.subTest(npc=npc):
                self.assertEqual((points[npc].category, points[npc].detail), expected)
                self.assertTrue(points[npc].name)
        # A name alone (the seasonal vendor) is not evidence of its stock.
        self.assertEqual(points[15898].category, "vendor")
        self.assertIsNone(points[15898].detail)

    def test_hillsbrad_merchants_use_the_correct_filters_and_vendor_stops(self):
        self.lua.globals().available = True
        points = [p for p in self.points(1424) if p.npc in (2404, 3543)]
        self.assertCountEqual([(p.npc, p.category, p.detail) for p in points], [
            (2404, "vendor_equipment", "Armas · En la herrería o sus alrededores"),
            (3543, "vendor_equipment", "Armaduras"),
        ])
        document = json.loads((ROOT / "RutaXP/Source/leveling.json").read_text(encoding="utf-8"))
        options = [{site.get("npc") for site in goal["candidates"]}
                   for guide in document["guides"] for step in guide["steps"] for goal in step["goals"]
                   if goal["t"] == "vendor" and goal.get("candidates")]
        self.assertTrue(any(3543 in merchants for merchants in options))
        self.assertFalse(any(2404 in merchants for merchants in options))


if __name__ == "__main__":
    unittest.main()
