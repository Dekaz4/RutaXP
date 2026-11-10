"""Navigation causality, map transforms and arrival safety against actual Lua."""
import math
import unittest

import test_quest_engine as engine_fixtures
from test_addon import TOOLTIP_STUBS


class NavigationRegressions(unittest.TestCase):
    def setUp(self):
        engine_fixtures.NavigationAndFullTocTests.setUp(self)

    def select_goal(self, goal):
        h = self.host
        h.guide("navigation-regression", steps=[{"title": "Current action", "goals": [goal]}])
        h.initialize()
        h.call("SelectGuide", "navigation-regression")

    def test_missing_current_coordinates_never_use_a_later_npc(self):
        h = self.host
        h.guide("current-action", steps=[{"title": "Village", "goals": [
            {"t": "sethome", "location": "Village inn"},
            {"t": "accept", "quest": 999, "map": 1436, "x": 10, "y": 20, "f": "e"},
        ]}])
        h.initialize()
        h.call("SelectGuide", "current-action")
        _, step, _ = h.call("GetCurrent")
        self.assertIsNone(h.call("GetStepWaypoint", step))
        frame = h.ns.navigationFrame
        self.assertFalse(frame.arrow.shown)
        self.assertIn("Sin coordenadas", frame.statusText)
        self.assertEqual(frame.distance.text, "")
        h.call("Next")
        point = h.call("GetStepWaypoint", step)
        self.assertEqual(point.goal.quest, 999)

    def test_nearby_quest_contact_is_named_only_on_the_final_personal_approach(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1439, .4371, .7649
        self.select_goal({"t": "accept", "quest": 5321, "title": "El despertar", "npcName": "Kerlonian Semprumbrío",
                          "map": 1439, "x": 44.4, "y": 76.43})
        _, step, _ = h.call("GetCurrent")
        point = h.call("GetStepWaypoint", step)
        h.state.arrowPoint = point
        h.ns.GetArrowWaypoint = h.lua.eval("function() return TEST.arrowPoint end")
        h.state.x = point.x - .001
        point.walking, point.walkingFinal = True, True
        point.walkingCount, point.walkingIndex = 2, 2
        h.call("UpdateNavigation")
        frame = h.ns.navigationFrame
        self.assertIn("Habla con Kerlonian Semprumbrío", frame.destinationText)
        self.assertIn("Acepta: El despertar", frame.destinationText)
        self.assertNotIn("tramo", frame.destinationText)

        h.state.x = point.x - .1
        h.call("UpdateNavigation")
        self.assertIn("Camino por terreno", frame.destinationText)
        h.state.x = point.x - .001
        point.walkingFinal = False
        h.call("UpdateNavigation")
        self.assertIn("Camino por terreno", frame.destinationText)

        point.walking, point.source = False, "duo-follow"
        h.call("UpdateNavigation")
        self.assertIn("Acompaña al compañero", frame.destinationText)
        self.assertNotIn("Kerlonian", frame.destinationText)
        point.source, point.goal.t = "game", "turnin"
        point.navigationNotice = "Dirección orientativa"
        h.call("UpdateNavigation")
        self.assertIn("Habla con Kerlonian Semprumbrío", frame.destinationText)
        self.assertIn("Entrega: El despertar", frame.destinationText)
        self.assertIn("Dirección orientativa", frame.destinationText)

    def test_walk_to_bashal_aran_only_displays_distance_and_explains_the_route_on_hover(self):
        h = self.host
        h.lua.execute(TOOLTIP_STUBS + """
            local methods = getmetatable(UIParent).__index
            local createFontString = methods.CreateFontString
            function methods:CreateFontString(...)
                local label = createFontString(self, ...)
                self.fontStrings = self.fontStrings or {}
                table.insert(self.fontStrings, label)
                return label
            end
        """)
        h.state.mapID, h.state.x, h.state.y = 1439, .40, .40
        self.select_goal({"t": "accept", "quest": 954, "title": "Bashal'Aran",
                          "map": 1439, "x": 45, "y": 45})
        _, step, _ = h.call("GetCurrent")
        point = h.call("GetStepWaypoint", step)
        point.walking, point.walkingDistance = True, 119.2
        point.walkingIndex, point.walkingCount = 3, 5
        h.state.arrowPoint = point
        h.ns.GetArrowWaypoint = h.lua.eval("function() return TEST.arrowPoint end")
        h.call("UpdateNavigation")

        frame, tooltip = h.ns.navigationFrame, h.globals.GameTooltip
        self.assertTrue(frame.arrow.shown)
        self.assertEqual([label.text for label in frame.fontStrings.values() if label.shown and label.text],
                         ["109 m"])
        self.assertFalse(tooltip.shown)
        frame.scripts.OnEnter(frame)
        self.assertTrue(tooltip.shown)
        details = "\n".join(tooltip.lines.values())
        self.assertIn("Camino por terreno · tramo 2/4", details)
        self.assertIn("Acepta: Bashal'Aran", details)
        point.walking, point.walkingDistance = False, None
        h.state.x, h.state.y = point.x, point.y
        updater = h.ns.navigationUpdater
        updater.scripts.OnUpdate(updater, 1)
        self.assertTrue(frame.arrived)
        self.assertEqual(frame.distance.text, "0.0 m")
        details = "\n".join(tooltip.lines.values())
        self.assertIn("¡Has llegado!", details)
        self.assertNotIn("tramo", details)
        frame.scripts.OnLeave(frame)
        self.assertFalse(tooltip.shown)

    def test_nearest_compatible_candidate_wins_over_the_first_in_catalog(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, .5, .5
        h.state.classToken = "MAGE"
        goal = h.table({"t": "train", "candidates": [
            {"npcName": "Wrong class", "faction": "A", "classes": ["WARRIOR"], "map": 1436, "x": 50, "y": 50},
            {"npcName": "Far mage", "faction": "A", "classes": ["MAGE"], "map": 1436, "x": 10, "y": 10},
            {"npcName": "Near mage", "faction": "A", "classes": ["MAGE"], "map": 1436, "x": 51, "y": 50},
        ]})
        point = h.call("GetGoalWaypoint", goal)
        self.assertEqual(point.candidateName, "Near mage")
        self.assertAlmostEqual(point.x, .51)

    def test_reverse_map_transform_is_used_instead_of_era_percentages(self):
        h = self.host
        h.lua.execute("""
        function C_Map.GetMapPosFromWorldPos(c, p, preferredMap)
            return preferredMap, CreateVector2D(.25,.75)
        end
        """)
        point = h.call("GetGoalWaypoint", h.table({"t": "goto", "map": 1436, "x": 50, "y": 50, "f": "e"}))
        self.assertAlmostEqual(point.x, .25)
        self.assertAlmostEqual(point.y, .75)

    def test_cardinal_directions_and_player_rotation_use_radians(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, .5, .5
        samples = [(.5, .4, 0, 1), (.6, .5, 1, 0), (.5, .6, 0, -1), (.4, .5, -1, 0)]
        for x, y, right, forward in samples:
            with self.subTest(x=x, y=y):
                vector = h.call("GetWaypointVector", h.table({"mapID": 1436, "x": x, "y": y}))
                self.assertGreater(vector[0], 0)
                self.assertAlmostEqual(vector[1], right, places=5)
                self.assertAlmostEqual(vector[2], forward, places=5)
        h.state.facing = math.pi / 2
        vector = h.call("GetWaypointVector", h.table({"mapID": 1436, "x": .5, "y": .4}))
        self.assertAlmostEqual(vector[1], 1)
        self.assertAlmostEqual(vector[2], 0, places=5)

    def test_another_continent_never_counts_as_arrival(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, .5, .5
        result = h.call("GetWaypointVector", h.table({"mapID": 1411, "x": .5, "y": .5}))
        self.assertIsNone(result[0])
        self.assertIn("continente", result[1])
        self.assertFalse(h.call("IsAtWaypoint", h.table({"waypoint": {"mapID": 1411, "x": .5, "y": .5}})))

    def test_same_xy_on_another_floor_does_not_finish_travel(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, .5, .5
        h.lua.execute("function UnitPosition() return 0,0,10,0 end")
        goal = h.table({"t": "goto", "map": 1436, "x": 50, "y": 50, "z": 40})
        self.assertFalse(h.call("IsAtWaypoint", goal))
        h.lua.execute("function UnitPosition() return 0,0,40,0 end")
        self.assertTrue(h.call("IsAtWaypoint", goal))

    def test_legacy_unverified_npc_cache_is_preserved_but_not_trusted(self):
        h = self.host
        h.initialize()
        h.ns.db.npcSpots = h.table({10: {"map": 1436, "x": .9, "y": .9}})
        point = h.call("GetGoalWaypoint", h.table({"t": "accept", "quest": 50, "npc": 10, "map": 1436, "x": 10, "y": 20}))
        self.assertEqual(point.source, "guide")
        self.assertAlmostEqual(point.x, .1)
        self.assertAlmostEqual(h.ns.db.npcSpots[10].x, .9)

    def test_a_live_turnin_marker_beats_an_older_learned_position(self):
        h = self.host
        h.initialize()
        h.state.mapID = 1436
        h.call("LearnNpcPosition", 10)
        h.quest(50, onQuest=True, complete=True)
        h.lua.execute("function C_QuestLog.GetNextWaypoint() return 1436,.61,.52 end")
        point = h.call("GetGoalWaypoint", h.table({"t": "turnin", "quest": 50, "npc": 10}))
        self.assertEqual(point.source, "game")
        self.assertAlmostEqual(point.x, .61)

    def test_a_selected_remote_target_does_not_teach_an_npc_position(self):
        h = self.host
        h.lua.execute("""
        TEST.navigationFrames = {}
        local old = CreateFrame
        function CreateFrame(...)
            local frame = old(...)
            table.insert(TEST.navigationFrames, frame)
            return frame
        end
        function UnitGUID(unit)
            if unit == 'target' then return 'Creature-0-1-0-1-2079-000001' end
        end
        """)
        from test_addon import ADDON
        h.load((ADDON / "Navigation.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.initialize()
        h.globals.NAV_REVIEW_NS = h.ns
        h.lua.execute("""
        for _,frame in ipairs(TEST.navigationFrames) do
            if frame.events.GOSSIP_SHOW then frame.scripts.OnEvent(frame,'GOSSIP_SHOW') end
        end
        """)
        self.assertIsNone(h.ns.db.npcSpots)

    def test_changed_game_build_does_not_reuse_an_old_npc_position(self):
        h = self.host
        h.initialize()
        h.state.mapID = 1436
        h.call("LearnNpcPosition", 10)
        h.lua.execute("function GetBuildInfo() return '1.60.1','newbuild','today',16001 end")
        point = h.call("GetGoalWaypoint", h.table({"t": "accept", "quest": 50, "npc": 10, "map": 1436, "x": 10, "y": 20}))
        self.assertEqual(point.source, "guide")
        self.assertIsNotNone(h.ns.db.npcSpots[10])

    def test_a_verified_cache_without_build_is_not_used(self):
        h = self.host
        h.initialize()
        h.ns.db.npcSpots = h.table({10: {"map": 1436, "x": .9, "y": .9, "verified": True}})
        point = h.call("GetGoalWaypoint", h.table({"t": "accept", "quest": 50, "npc": 10, "map": 1436, "x": 10, "y": 20}))
        self.assertEqual(point.source, "guide")

    def test_an_unreachable_floor_is_not_preferred_over_a_local_trainer(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, .5, .5
        h.state.inInstance = True
        h.globals.RUTAXP_TEST_BOUNDS[999] = h.ns.mapFrames.era[1436]
        goal = h.table({"t": "train", "candidates": [
            {"npcName": "Other floor", "faction": "A", "map": 999, "x": 50, "y": 50},
            {"npcName": "On this floor", "faction": "A", "map": 1436, "x": 55, "y": 50},
        ]})
        point = h.call("GetGoalWaypoint", goal)
        self.assertEqual(point.candidateName, "On this floor")
        self.assertEqual(point.mapID, 1436)

    def test_native_marker_failure_is_reported_without_a_lua_error(self):
        h = self.host
        self.select_goal({"t": "accept", "quest": 50, "map": 1436, "x": 10, "y": 20})
        h.lua.execute("function C_Map.SetUserWaypoint() error('API unavailable in this map') end")
        self.assertFalse(h.call("Navigate"))
        self.assertIn("no ha podido", h.state.messages[len(h.state.messages)])


if __name__ == "__main__":
    unittest.main()
