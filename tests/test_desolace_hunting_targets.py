"""Exercise the later Desolace hunting overlay independently of the 0.7.36 routes."""
import json
import unittest

import test_quest_engine as fixtures
from tools.desolace_solo_targets import apply_desolace_targets


class DesolaceHuntingTargets(unittest.TestCase):
    def setUp(self):
        fixtures.NavigationAndFullTocTests.setUp(self)
        self.host.state.level = 33
        self.host.state.mapID = 1443
        data = json.loads((fixtures.ADDON / "Source" / "leveling.json").read_bytes())
        apply_desolace_targets(data)
        chapter = next(g for g in data["guides"] if g["id"] == "forever/alliance/30-40/02-desolace")
        self.goals = {g["item"]: self.host.table(g) for step in chapter["steps"] for g in step["goals"]
                      if g["t"] == "collect" and g.get("quest") in (1459, 1387)}

    def assert_waypoint(self, item, player, expected):
        self.host.state.x, self.host.state.y = [c / 100 for c in player]
        point = self.host.call("GetGoalWaypoint", self.goals[item])
        self.assertEqual(point.mapID, 1443)
        self.assertAlmostEqual(point.x * 100, expected[0])
        self.assertAlmostEqual(point.y * 100, expected[1])

    def test_venom_uses_the_nearby_lasher_or_the_easier_snapper_along_the_way(self):
        self.assert_waypoint(6248, (44.7, 50.0), (45.24, 47.94))
        self.assert_waypoint(6248, (42.7, 50.1), (42.68, 50.14))
        self.assert_waypoint(6248, (59.4, 64.2), (59.45, 64.24))

    def test_hides_stay_in_the_graveyard_from_north_and_south(self):
        self.assert_waypoint(6249, (49.4, 41.2), (49.36, 41.23))
        self.assert_waypoint(6249, (52.0, 56.1), (51.95, 56.10))

    def test_ears_point_to_the_kolkar_village_even_from_the_old_magram_marker(self):
        self.assert_waypoint(6067, (65.59, 70.30), (68.55, 52.17))
        self.assert_waypoint(6067, (69.4, 46.9), (69.35, 46.87))
