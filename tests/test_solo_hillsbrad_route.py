"""Check the two Syndicate tables in world space and Bartolo's complete errand."""
import copy
import json
import unittest

import test_quest_engine as engine
from test_addon import ROOT
from tools.solo_hillsbrad_route import ARATHI, HILLSBRAD, apply_hillsbrad_detours


class HillsbradDetourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((ROOT / "RutaXP/Source/leveling.json").read_text(encoding="utf-8"))
        cls.route = {"guides": [guide for guide in catalog["guides"] if guide["id"] in (HILLSBRAD, ARATHI)]}

    def setUp(self):
        self.route = copy.deepcopy(self.route)
        self.goals = [goal for guide in self.route["guides"] for step in guide["steps"] for goal in step["goals"]]
        self.papers = [goal for goal in self.goals if goal["t"] == "accept" and goal.get("quest") in (510, 511)]
        # Exercise the transform on a first import even after the snapshot has been regenerated.
        for goal in self.goals:
            if goal in self.papers:
                goal.pop("spots", None)
            for key in ("levelingDetour", "detourItems", "detourQuest"):
                goal.pop(key, None)

    def test_bartolo_only_changes_its_own_materials_and_handin(self):
        before = [(goal["t"], goal.get("quest")) for goal in self.goals]
        apply_hillsbrad_detours(self.route)
        modified = [goal for goal in self.goals if goal.get("levelingDetour")]
        self.assertCountEqual([(goal["t"], goal.get("quest")) for goal in modified],
                              [("accept", 565), ("collect", 565), ("note", None), ("turnin", 565)])
        self.assertTrue(all(goal["detourItems"] == {"2997": 1, "2321": 1, "3719": 1, "3720": 10}
                            for goal in modified))
        self.assertEqual(next(goal for goal in modified if goal["t"] == "note")["detourQuest"], 565)
        self.assertEqual(before, [(goal["t"], goal.get("quest")) for goal in self.goals])
        once = copy.deepcopy(self.route)
        apply_hillsbrad_detours(self.route)
        self.assertEqual(self.route, once)

    def test_both_quests_point_to_the_nearer_table_across_zone_frames(self):
        apply_hillsbrad_detours(self.route)
        self.assertEqual([goal["quest"] for goal in self.papers], [510, 511])
        engine.NavigationAndFullTocTests.setUp(self)
        host = self.host
        # Give the live maps different bounds from Era and from each other.
        # The player is in Alterac, whereas the authored destinations are in Hillsbrad.
        live = {
            1416: {"c": 0, "top": 1600, "bottom": -500, "left": 900, "right": -2250},
            1424: {"c": 0, "top": 500, "bottom": -1900, "left": 1200, "right": -2400},
        }
        host.globals.RUTAXP_TEST_BOUNDS = host.table(live)
        host.state.mapID = 1416
        alterac = host.ns.mapFrames.era[1416]
        goals = [host.table(goal) for goal in self.papers]
        for x, y in [(47.94, 82.15), (58.3, 68.0), (47.94, 82.15)]:
            with self.subTest(alterac=(x, y)):
                north = alterac.top + (alterac.bottom - alterac.top) * y / 100
                west = alterac.left + (alterac.right - alterac.left) * x / 100
                host.state.x = (west - 900) / -3150
                host.state.y = (north - 1600) / -2100
                for goal in goals:
                    waypoint = host.call("GetGoalWaypoint", goal)
                    self.assertEqual(waypoint.source, "guide")
                    continent, target_north, target_west = host.call("GetWaypointWorldPosition", waypoint)
                    self.assertEqual(continent, 0)
                    # The original Sofera guide pin is rounded to a tenth of a percent.
                    self.assertAlmostEqual(target_north, north, delta=2)
                    self.assertAlmostEqual(target_west, west, delta=2)

    def test_live_offers_follow_player_movement_between_map_queries(self):
        engine.NavigationAndFullTocTests.setUp(self)
        host = self.host
        goal = host.table(self.papers[0])
        host.lua.execute("""
            TEST.now, TEST.mapReads = 10, 0
            function GetTime() return TEST.now end
            function C_QuestLog.GetQuestsOnMap()
                TEST.mapReads = TEST.mapReads + 1
                if TEST.mapReads > 1 then return {{questID=510, x=.42, y=.15}} end
                return {
                    {questID=510, x=2, y=.2}, {questID=999, x=.51, y=.2},
                    {questID=510, x=.60, y=.08}, {questID=510, x=.51, y=.20},
                }
            end
        """)
        host.state.mapID = 1424
        host.state.x, host.state.y = .51, .20
        near = host.call("GetGoalWaypoint", goal)
        self.assertEqual((near.x, near.y, near.source), (.51, .20, "game"))
        host.state.x, host.state.y = .60, .08
        other = host.call("GetGoalWaypoint", goal)
        self.assertEqual((other.x, other.y), (.60, .08))
        host.state.x, host.state.y = .51, .20
        self.assertAlmostEqual(host.call("GetGoalWaypoint", goal).x, .51)
        host.state.positionUnavailable = True
        self.assertAlmostEqual(host.call("GetGoalWaypoint", goal).x, .60)
        self.assertEqual(host.state.mapReads, 1)
        host.state.now = 14
        self.assertAlmostEqual(host.call("GetGoalWaypoint", goal).x, .42)
        self.assertEqual(host.state.mapReads, 2)
