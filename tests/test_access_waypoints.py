"""Authored accesses survive goal changes and work for independent help targets."""
import unittest

import test_waypoints as fixtures


class AccessWaypointTests(unittest.TestCase):
    setUp = fixtures.WaypointTests.setUp
    control = fixtures.WaypointTests.control
    route = fixtures.WaypointTests.route
    select = fixtures.WaypointTests.select
    point = fixtures.WaypointTests.point

    def cave(self, **fields):
        return self.route([{"map": 1436, "x": 40, "y": 50, "mode": "confirm", "label": "Verified cave mouth"}],
                          kind="cave", activationRadius=1800, **fields)

    def test_far_verified_access_remains_a_target_outside_the_old_activation_radius(self):
        h = self.host
        self.route([{"map": 1436, "x": 1, "y": 1, "mode": "confirm"}], kind="cave", activationRadius=1800)
        step = self.select()
        point = self.point(step)
        self.assertTrue(point.intermediate)
        self.assertGreater(h.call("GetWaypointVector", point)[0], 1800)
        self.assertFalse(bool(self.control("GetStatus").bypassed))

    def test_horizontal_closeness_to_npc_is_not_proof_that_the_entrance_was_passed(self):
        self.cave()
        step = self.select({"t": "complete", "quest": 501, "map": 1436, "x": 50.1, "y": 50})
        point = self.point(step)
        self.assertTrue(point.intermediate)
        self.assertAlmostEqual(point.x, .4)

    def test_being_in_an_unrelated_inn_does_not_remove_the_required_access(self):
        self.host.state.indoors = True
        self.cave()
        step = self.select()
        self.assertTrue(self.point(step).intermediate)

    def test_unavailable_world_position_is_retryable_without_permanent_bypass(self):
        h = self.host
        self.cave()
        h.lua.execute('TEST.worldMapAPI=C_Map.GetWorldPosFromMapPos; C_Map.GetWorldPosFromMapPos=function() return nil end')
        step = self.select()
        self.assertTrue(self.point(step).intermediate)
        self.assertFalse(bool(self.control("GetStatus").bypassed))
        h.lua.execute('C_Map.GetWorldPosFromMapPos=TEST.worldMapAPI')
        point = self.point(step)
        self.assertTrue(point.intermediate)
        self.assertIsNotNone(h.call("GetWaypointVector", point)[0])

    def test_missing_coordinate_conversion_blocks_the_direct_npc_arrow_until_recovered(self):
        h = self.host
        self.cave()
        conversion = h.ns.ResolveWaypointPoint
        h.ns.ResolveWaypointPoint = h.lua.eval('function() return nil end')
        step = self.select()
        self.assertIsNone(self.point(step))
        self.assertFalse(bool(self.control("GetStatus").bypassed))
        h.ns.ResolveWaypointPoint = conversion
        self.assertTrue(self.point(step).intermediate)

    def test_confirmed_access_is_shared_between_two_objectives_and_survives_reload(self):
        h = self.host
        self.cave(match={"quests": [501, 502]})
        step = self.select()
        step.goals[2] = h.table({"t": "complete", "quest": 502, "map": 1436, "x": 90, "y": 80})
        h.quest(502, onQuest=True)
        self.control("Skip")
        h.quest(501, onQuest=True, complete=True)
        h.call("Sync")
        self.assertFalse(bool(self.point(step).intermediate))
        routes = h.ns.Waypoints.routes
        h.load((fixtures.ADDON / "Waypoints.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.ns.Waypoints.routes = routes
        self.assertFalse(bool(self.point(step).intermediate))
        self.assertTrue(self.control("GetStatus").finished)
        self.assertFalse(h.call("IsQuestDelivered", 501))
        self.assertFalse(h.call("IsQuestDelivered", 502))
        self.assertIsNone(h.call("GetProgress", "waypoint-test").confirmed["1:2"])

    def test_a_new_trip_after_leaving_the_access_area_can_guide_the_entrance_again(self):
        h = self.host
        self.cave(match={"quests": [501, 502]})
        step = self.select()
        step.goals[2] = h.table({"t": "complete", "quest": 502, "map": 1436, "x": 90, "y": 80})
        h.quest(502, onQuest=True)
        self.control("Skip")
        h.state.x, h.state.y = .99, .99
        h.quest(501, onQuest=True, complete=True)
        h.call("Sync")
        self.assertTrue(self.point(step).intermediate)
        self.assertEqual(self.control("GetStatus").index, 1)

    def external(self):
        h = self.host
        goal = {"t": "complete", "quest": 501, "map": 1436, "x": 90, "y": 90}
        return h.table({"goal": goal, "base": {"mapID": 1436, "x": .9, "y": .9, "source": "duo-follow"},
                        "key": "help:their-guide:22:3", "source": "duo-follow", "guideID": "their-guide",
                        "stepIndex": 22, "goalIndex": 3})

    def test_external_target_resolution_does_not_consult_real_progress_or_getcurrent(self):
        h = self.host
        self.cave()
        self.select()
        h.ns.GetCurrent = h.lua.eval('function() error("must not read own current step") end')
        h.ns.GetActiveGoal = h.lua.eval('function() error("must not read own active goal") end')
        point = self.control("ResolveTarget", self.external())
        self.assertTrue(point.intermediate)
        self.assertEqual(point.targetSource, "duo-follow")
        self.assertEqual((point.guideID, point.stepIndex, point.goalIndex), ("their-guide", 22, 3))
        self.assertEqual(point.label, "Verified cave mouth")
        self.assertTrue(self.control("GetStatus").external)
        self.assertFalse(self.control("IsRouting"))

    def test_external_controls_confirm_the_displayed_access_without_completing_own_quest(self):
        h = self.host
        self.cave()
        self.select()
        context = self.external()
        h.state.externalTarget = context
        h.ns.UpdateNavigation = h.lua.eval('function(self) return self.Waypoints:ResolveTarget(TEST.externalTarget) end')
        h.ns.RefreshUI = h.lua.eval('function() end')
        self.control("ResolveTarget", context)
        self.control("Skip")
        self.assertTrue(self.control("GetStatus").finished)
        self.assertFalse(bool(self.control("ResolveTarget", context).intermediate))
        self.assertEqual(h.cursor("waypoint-test"), 1)
        self.assertFalse(h.call("IsQuestDelivered", 501))

    def test_external_targets_respect_pause_and_manual_disable(self):
        h = self.host
        self.cave()
        self.select()
        context = self.external()
        self.control("Pause", True)
        self.assertFalse(bool(self.control("ResolveTarget", context).intermediate))
        self.control("Pause", False)
        self.control("Toggle", False)
        self.assertFalse(bool(self.control("ResolveTarget", context).intermediate))

    def test_old_distance_bypass_is_migrated_without_losing_saved_fields(self):
        h = self.host
        self.cave()
        step = self.select()
        legacy = "waypoint-test:1:1:complete:501:test-bridge"
        h.ns.char.waypoints.entries = h.table({legacy: {"index": 1, "bypassed": True,
            "reason": "Entrada alejada", "legacySaved": True}})
        self.assertTrue(self.point(step).intermediate)
        self.assertTrue(h.ns.char.waypoints.entries["access:test-bridge"].legacySaved)
        self.assertFalse(bool(self.control("GetStatus").bypassed))

    def test_control_context_refreshes_the_players_goal_before_the_next_navigation_tick(self):
        h = self.host
        self.cave(match={"quests": [501, 502]})
        step = self.select()
        self.point(step)
        step.goals[2] = h.table({"t": "complete", "quest": 502, "map": 1436, "x": 90, "y": 80})
        h.quest(502, onQuest=True)
        h.quest(501, onQuest=True, complete=True)
        self.assertIn(":2:complete:502", self.control("GetStatus").goalKey)

    def test_legacy_scan_tolerates_non_string_saved_keys(self):
        h = self.host
        self.cave()
        step = self.select()
        h.ns.char.waypoints.entries = h.table({1: {"done": True, "index": 2}})
        self.assertTrue(self.point(step).intermediate)
        self.assertTrue(h.ns.char.waypoints.entries[1].done)


if __name__ == "__main__":
    unittest.main()
