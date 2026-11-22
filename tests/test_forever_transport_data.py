from collections import Counter
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime


class ForeverTransportDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lua = LuaRuntime()
        cls.ns = lua.table()
        addon = Path(__file__).resolve().parents[1] / "RutaXP"
        lua.execute(
            (addon / "TravelConnections.lua").read_text(encoding="utf8"),
            "RutaXP",
            cls.ns,
        )
        cls.fixed = {r.id: r for r in cls.ns.GuideTravelConnections.values() if r.id}

    def test_three_port_loop_has_directional_stopovers_and_distinct_menethil_piers(
        self,
    ):
        sections = self.fixed
        harbor = sections["boat-menethil-auberdine"]
        self.assertEqual((harbor.a.map, harbor.a.x, harbor.a.y), (1437, 4.49, 56.66))
        self.assertEqual(
            (harbor.stopAB.name, harbor.stopAB.map, harbor.b.map),
            ("Costasur", 1424, 1439),
        )
        self.assertIsNone(harbor.stopBA)
        self.assertEqual(
            sections["boat-southshore-auberdine"].stopBA.name, "Puerto de Menethil"
        )
        self.assertEqual(sections["boat-menethil-southshore"].stopBA.name, "Auberdine")
        south = sections["boat-menethil-theramore"]
        self.assertEqual((south.a.x, south.a.y, south.b.map), (4.74, 63.76, 1445))
        self.assertIsNone(south.stopAB)
        self.assertIsNone(south.stopBA)

    def test_physical_taxi_routes_stay_on_the_same_continent_and_allow_the_same_faction(
        self,
    ):
        nodes = self.ns.GuideTaxiNodes
        self.assertEqual(len(list(nodes)), 61)
        self.assertEqual(
            sum(len(list(v)) for v in self.ns.GuideTaxiPaths.values()), 266
        )
        for origin, outgoing in self.ns.GuideTaxiPaths.items():
            for dest, distance in outgoing.items():
                self.assertGreater(distance, 0)
                self.assertEqual(nodes[origin].continent, nodes[dest].continent)
                self.assertTrue(nodes[origin].mask & nodes[dest].mask)
        self.assertEqual(
            (nodes[26].name, nodes[28].name, nodes[26].mask),
            ("Auberdine", "Astranaar", 1),
        )
        self.assertGreater(self.ns.GuideTaxiPaths[26][28], 0)
        self.assertIsNone(self.ns.GuideTaxiPaths[7][26])

    def test_horde_towers_and_neutral_ship_are_separate_from_alliance_ports(self):
        self.assertEqual(
            Counter(r.kind for r in self.fixed.values()),
            {"boat": 8, "zeppelin": 3, "tram": 1, "portal": 2},
        )
        self.assertEqual(self.fixed["zeppelin-orgrimmar-undercity"].mask, 2)
        self.assertEqual(self.fixed["zeppelin-orgrimmar-gromgol"].mask, 2)
        self.assertEqual(self.fixed["boat-menethil-auberdine"].mask, 1)
        self.assertEqual(self.fixed["boat-bootybay-ratchet"].mask, 3)
