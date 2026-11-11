"""Observed/authored movement points never stand in for quest completion."""

import json
import unittest

import test_quest_engine as fixtures

ADDON = fixtures.ADDON


class WaypointTests(unittest.TestCase):
    def setUp(self):
        fixtures.NavigationAndFullTocTests.setUp(self)
        self.host.load((ADDON / "Waypoints.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.host.ns)
        self.host.lua.execute("""
        TEST.height, TEST.instance = 10, 0
        function UnitPosition() return 0,0,TEST.height,TEST.instance end
        function IsIndoors() return TEST.indoors == true end
        """)

    def control(self, name, *args):
        w = self.host.ns.Waypoints
        return w[name](w, *args)

    def route(self, points, **fields):
        route = {"id": "test-bridge", "title": "Authored fixture crossing", "kind": "observed",
                 "match": {"quests": [501]}, "points": points, **fields}
        self.host.ns.Waypoints.routes = self.host.table([route])
        return route

    def select(self, goal=None, guide_id="waypoint-test"):
        h = self.host
        goal = goal or {"t": "complete", "quest": 501, "map": 1436, "x": 90, "y": 90}
        h.state.mapID, h.state.x, h.state.y = 1436, .5, .5
        if goal.get("quest"):
            h.quest(goal["quest"], onQuest=True, complete=False)
        h.guide(guide_id, steps=[{"title": "Current quest", "goals": [goal]}])
        h.initialize()
        h.call("SelectGuide", guide_id)
        return h.ns.guides[guide_id].steps[1]

    def point(self, step):
        return self.host.call("GetStepWaypoint", step)

    def walk_route(self):
        return self.route([
            {"map": 1436, "x": 40, "y": 50, "z": 10, "mode": "walk", "label": "Near bank"},
            {"map": 1436, "x": 60, "y": 50, "z": 10, "mode": "walk", "label": "Far bank"},
        ])

    def test_bridge_points_advance_once_then_release_the_actual_quest_target(self):
        h = self.host
        self.walk_route()
        step = self.select()
        self.assertEqual(self.point(step).pointIndex, 1)
        h.state.x = .4
        self.assertEqual(self.point(step).pointIndex, 2)
        self.assertEqual(self.point(step).pointIndex, 2)
        h.state.x = .6
        base = self.point(step)
        self.assertFalse(bool(base.intermediate))
        self.assertAlmostEqual(base.x, .9)
        for _ in range(5):
            self.assertFalse(bool(self.point(step).intermediate))
        self.assertTrue(self.control("GetStatus").finished)
        self.assertFalse(self.control("IsRouting"))
        self.assertEqual(h.cursor("waypoint-test"), 1)
        self.assertFalse(h.call("IsQuestDelivered", 501))
        self.assertIsNone(h.call("GetProgress", "waypoint-test").confirmed["1:1"])

    def test_same_xy_on_a_different_floor_and_unknown_height_do_not_advance(self):
        h = self.host
        self.route([{"map": 1436, "x": 40, "y": 50, "z": 40, "mode": "walk"}])
        step = self.select()
        h.state.x = .4
        self.assertEqual(self.point(step).pointIndex, 1)
        self.assertIn("arriba", self.control("GetStatus").waiting)
        h.state.height = None
        self.assertEqual(self.point(step).pointIndex, 1)
        h.state.height = 40
        self.assertFalse(bool(self.point(step).intermediate))

    def test_reaching_an_intermediate_cannot_complete_a_goto_goal(self):
        h = self.host
        self.walk_route()
        h.ns.Waypoints.routes[1].match = h.table({"actions": ["goto"]})
        step = self.select({"t": "goto", "map": 1436, "x": 90, "y": 90, "z": 10})
        h.state.x = .4
        self.assertEqual(self.point(step).pointIndex, 2)
        self.assertFalse(h.call("IsAtWaypoint", step.goals[1]))
        h.call("OnNavigationTick")
        self.assertEqual(h.cursor("waypoint-test"), 1)

    def test_pause_skip_and_reset_preserve_progress_and_require_explicit_reset_after_done(self):
        h = self.host
        self.walk_route()
        step = self.select()
        self.control("Pause", True)
        h.state.x = .4
        self.assertFalse(bool(self.point(step).intermediate))
        self.control("Pause", False)
        self.assertEqual(self.control("GetStatus").index, 2)
        self.control("Skip")
        self.assertTrue(self.control("GetStatus").finished)
        self.control("Toggle", False)
        self.control("Toggle", True)
        self.assertFalse(bool(self.point(step).intermediate))
        h.state.x = .5
        self.control("Reset")
        self.assertEqual(self.point(step).pointIndex, 1)

    def test_route_progress_survives_a_fresh_module_load(self):
        h = self.host
        routes = self.walk_route()
        step = self.select()
        h.state.x = .4
        self.assertEqual(self.point(step).pointIndex, 2)
        saved_char = h.ns.char
        h.load((ADDON / "Waypoints.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.ns.Waypoints.routes = h.table([routes])
        self.assertTrue(h.lua.eval("function(a,b) return a==b end")(h.ns.char, saved_char))
        self.assertEqual(self.point(step).pointIndex, 2)

    def test_new_goal_gets_its_own_sequence(self):
        h = self.host
        self.walk_route()
        second = {"id": "next-entrance", "kind": "observed", "title": "Next entrance",
                  "match": {"quests": [502]}, "points": [{"map": 1436, "x": 20, "y": 20, "z": 10}]}
        h.ns.Waypoints.routes[2] = h.table(second)
        step = self.select()
        step.goals[2] = h.table({"t": "complete", "quest": 502, "map": 1436, "x": 90, "y": 80})
        h.quest(502, onQuest=True)
        h.state.x = .4
        self.assertEqual(self.point(step).pointIndex, 2)
        h.quest(501, onQuest=True, complete=True)
        h.call("Sync")
        point = self.point(step)
        self.assertEqual(point.routeID, "next-entrance")
        self.assertEqual(point.pointIndex, 1)

    def test_unknown_cave_altitude_requires_confirmation_and_never_claims_the_quest_done(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1429, .35, .9
        h.quest(87, onQuest=True)
        h.guide("cave", steps=[{"title": "Goldtooth", "goals": [
            {"t": "collect", "quest": 87, "item": 981, "map": 1429, "x": 41.71, "y": 78.03, "f": "e"}
        ]}])
        h.initialize()
        h.call("SelectGuide", "cave")
        _, step, _ = h.call("GetCurrent")
        point = self.point(step)
        self.assertEqual(point.routeID, "fargodeep")
        self.assertAlmostEqual(point.x, .395)
        h.state.x, h.state.y = .395, .824
        self.assertTrue(self.point(step).intermediate)
        self.assertIn("confirma", self.control("GetStatus").waiting.lower())
        self.control("Skip")
        self.assertFalse(bool(self.point(step).intermediate))
        self.assertEqual(h.cursor("cave"), 1)

    def test_already_inside_is_not_sent_to_the_entrance_unless_explicitly_reset(self):
        h = self.host
        h.state.indoors = True
        self.route([{"map": 1436, "x": 40, "y": 50, "mode": "confirm"}], kind="cave")
        step = self.select({"t": "complete", "quest": 501, "map": 1436, "x": 50, "y": 50})
        self.assertFalse(bool(self.point(step).intermediate))
        self.assertTrue(self.control("GetStatus").bypassed)
        self.control("Reset")
        self.assertTrue(self.point(step).intermediate)

    def test_transport_dock_arrival_never_claims_boarding_or_a_completed_ride(self):
        h = self.host
        self.route([
            {"map": 1436, "x": 50, "y": 50, "z": 10, "mode": "transport", "label": "Board here"},
            {"map": 1411, "x": 50, "y": 50, "z": 10, "mode": "walk", "label": "Disembark here"},
        ])
        step = self.select({"t": "complete", "quest": 501, "map": 1411, "x": 90, "y": 90})
        self.assertEqual(self.point(step).pointIndex, 1)
        self.assertIn("transporte", self.control("GetStatus").waiting)
        h.call("UpdateNavigation")
        frame = h.ns.navigationFrame
        self.assertEqual(frame.distance.text, "0.0 m")
        self.assertTrue(frame.hint.shown)
        self.assertEqual(frame.hint.text, "Confirma al embarcar")
        self.assertIn("transporte", frame.statusText)
        self.control("Skip")
        self.assertEqual(self.point(step).pointIndex, 2)
        self.assertEqual(self.point(step).pointIndex, 2)
        self.assertFalse(bool(self.control("GetStatus").finished))
        h.state.mapID, h.state.instance = 1411, 1
        self.assertFalse(bool(self.point(step).intermediate))
        self.assertFalse(h.call("IsQuestDelivered", 501))

    def test_capture_uses_the_observed_map_position_and_height_and_starts_paused(self):
        h = self.host
        self.select()
        h.state.x, h.state.y, h.state.height = .31, .42, 37
        ok, _ = self.control("Capture", "Bridge approach")
        self.assertTrue(ok)
        self.assertTrue(self.control("GetStatus").paused)
        context = self.control("GetStatus").goalKey
        route = h.ns.char.waypoints.ownRoutes[context]
        self.assertAlmostEqual(route.points[1].x, 31)
        self.assertAlmostEqual(route.points[1].y, 42)
        self.assertEqual(route.points[1].z, 37)
        self.assertEqual(route.points[1].mode, "walk")

    def test_recovery_override_precedes_and_does_not_advance_the_itinerary(self):
        h = self.host
        self.walk_route()
        step = self.select()
        h.ns.Recovery = h.table({})
        h.ns.Recovery.GetNavigationOverride = h.lua.eval("function() return {mapID=1436,x=.1,y=.1,recovery=true} end")
        h.state.x = .4
        self.assertTrue(self.point(step).recovery)
        self.assertEqual(self.control("GetStatus").index, 1)
        self.assertFalse(h.call("IsAtWaypoint", step.goals[1]))

    def test_original_route_entrance_already_visited_is_not_reimposed_for_the_next_goal(self):
        h = self.host
        self.route([{"map": 1436, "x": 40, "y": 50, "mode": "confirm"}], kind="cave")
        h.quest(501, onQuest=True)
        h.state.mapID, h.state.x, h.state.y = 1436, .41, .5
        h.guide("already-entered", steps=[{"title": "Inside", "goals": [
            {"t": "goto", "map": 1436, "x": 40, "y": 50},
            {"t": "complete", "quest": 501, "map": 1436, "x": 90, "y": 90},
        ]}])
        h.initialize()
        h.call("SelectGuide", "already-entered")
        h.call("GetProgress", "already-entered").confirmed["1:1"] = True
        _, step, _ = h.call("GetCurrent")
        self.assertFalse(bool(self.point(step).intermediate))
        self.assertIn("ya pasó", self.control("GetStatus").reason)

    def test_published_boat_uses_both_real_docks_and_requires_two_explicit_confirmations(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y, h.state.instance = 1413, .6335, .3845, 1
        h.quest(501, onQuest=True)
        h.guide("boat", steps=[{"title": "Across the sea", "goals": [
            {"t": "complete", "quest": 501, "map": 1434, "x": 30, "y": 75, "f": "e"}
        ]}])
        h.initialize()
        h.call("SelectGuide", "boat")
        _, step, _ = h.call("GetCurrent")
        point = self.point(step)
        self.assertEqual(point.routeID, "boat-bootybay-ratchet-return")
        self.assertEqual(point.mapID, 1413)
        self.assertAlmostEqual(point.x, .6335)
        self.assertEqual(point.pointIndex, 1)
        for _ in range(4):
            self.assertEqual(self.point(step).pointIndex, 1)
        self.control("Skip")
        point = self.point(step)
        self.assertEqual(point.mapID, 1434)
        self.assertAlmostEqual(point.x, .2635)
        self.assertEqual(point.pointIndex, 2)
        h.state.mapID, h.state.x, h.state.y, h.state.instance = 1434, .2635, .7356, 0
        self.assertEqual(self.point(step).pointIndex, 2)
        self.assertIn("confirma", self.control("GetStatus").waiting.lower())
        self.control("Skip")
        self.assertFalse(bool(self.point(step).intermediate))
        self.assertFalse(h.call("IsQuestDelivered", 501))
        self.assertEqual(h.cursor("boat"), 1)

    def test_published_zeppelin_and_portal_respect_faction_and_origin(self):
        h = self.host
        for faction, origin, destination, expected in [
            ("Alliance", 1411, 1420, None),
            ("Horde", 1411, 1420, "zeppelin-orgrimmar-undercity-out"),
            ("Horde", 1457, 1438, None),
            ("Alliance", 1457, 1438, "portal-ruttheran"),
        ]:
            with self.subTest(faction=faction, origin=origin):
                h.state.faction, h.state.mapID = faction, origin
                h.quest(501, onQuest=True)
                guide_id = "faction-travel-" + faction + str(origin)
                h.guide(guide_id, steps=[{"title": "Travel", "goals": [
                    {"t": "complete", "quest": 501, "map": destination, "x": 50, "y": 50}
                ]}])
                h.initialize()
                h.call("SelectGuide", guide_id)
                h.ns.char.waypoints = None
                status = self.control("GetStatus")
                self.assertEqual(status.routeID, expected)

    def test_capture_limits_reject_new_data_without_deleting_saved_positions(self):
        h = self.host
        self.select()
        w = h.ns.Waypoints
        w.limits.pointsPerRoute, w.limits.ownRoutes = 2, 1
        self.assertTrue(self.control("Capture", "First")[0])
        self.assertTrue(self.control("Capture", "Second")[0])
        self.assertFalse(self.control("Capture", "Third")[0])
        original = self.control("GetStatus").goalKey
        self.assertEqual(len(h.ns.char.waypoints.ownRoutes[original].points), 2)
        self.select({"t": "complete", "quest": 502, "map": 1436, "x": 90, "y": 90}, "next-quest")
        self.assertFalse(self.control("Capture", "Other route")[0])
        self.assertEqual(len(h.ns.char.waypoints.ownRoutes[original].points), 2)

    def test_total_capture_limit_and_history_limit_leave_existing_progress_intact(self):
        h = self.host
        self.select()
        w = h.ns.Waypoints
        w.limits.ownPoints, w.limits.entries = 1, 1
        self.assertTrue(self.control("Capture", "Saved")[0])
        original = self.control("GetStatus").goalKey
        self.assertFalse(self.control("Capture", "Over total")[0])
        w.limits.ownPoints = 10
        self.select({"t": "complete", "quest": 502, "map": 1436, "x": 90, "y": 90}, "next-quest")
        self.assertFalse(self.control("Capture", "Over history")[0])
        saved = h.ns.char.waypoints.ownRoutes[original]
        self.assertEqual(saved.points[1].label, "Saved")
        self.assertEqual(len(saved.points), 1)

    def test_full_history_still_runs_the_current_route_without_restarting_it(self):
        h = self.host
        self.walk_route()
        step = self.select()
        h.ns.Waypoints.limits.entries = 1
        h.state.x = .4
        self.assertEqual(self.point(step).pointIndex, 2)
        key = self.control("GetStatus").goalKey
        self.assertEqual(self.point(step).pointIndex, 2)
        h.ns.Waypoints.routes[2] = h.table({"id": "other", "kind": "cave", "match": {"quests": [502]},
            "points": [{"map": 1436, "x": 30, "y": 30, "mode": "confirm"}]})
        next_step = self.select({"t": "complete", "quest": 502, "map": 1436, "x": 90, "y": 90}, "next-quest")
        self.assertFalse(bool(self.point(next_step).intermediate))
        self.assertIn("lleno", self.control("GetStatus").reason)
        self.assertEqual(h.ns.char.waypoints.entries[key + ":test-bridge"].index, 2)

    def test_catalog_coordinates_and_provenance_equal_the_auditable_snapshot(self):
        data = json.loads((ADDON / "Source" / "waypoints.json").read_text(encoding="utf-8"))
        catalog = self.host.ns.Waypoints.catalog
        self.assertEqual(catalog.commit, data["commit"])
        self.assertEqual(len(catalog.routes), 15)
        self.assertEqual(sum(r["kind"] == "cave" for r in data["routes"]), 7)
        self.assertEqual(sum(r["kind"] == "transport" for r in data["routes"]), 4)
        self.assertEqual(sum(r["kind"] == "portal" for r in data["routes"]), 2)
        for index, route in enumerate(data["routes"], 1):
            actual = catalog.routes[index]
            self.assertEqual(actual.id, route["id"])
            self.assertEqual(actual.provenance.commit, data["commit"])
            self.assertIn(data["commit"], actual.provenance.url)
            for i, point in enumerate(route["points"], 1):
                self.assertEqual(actual.points[i].map, point["map"])
                self.assertEqual(actual.points[i].x, point["x"])
                self.assertEqual(actual.points[i].y, point["y"])
                self.assertEqual(actual.points[i].mode, point["mode"])


if __name__ == "__main__":
    unittest.main()
