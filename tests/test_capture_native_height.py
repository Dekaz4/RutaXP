"""Native zero height is unknown when capturing a player's location."""

import unittest

import test_duo_enhanced as duo_fixtures
import test_waypoints as waypoint_fixtures


class CapturedNativeHeightTests(unittest.TestCase):
    def test_personal_waypoint_drops_zero_height_but_preserves_nonzero_observations(self):
        fixture = waypoint_fixtures.WaypointTests()
        fixture.setUp()
        fixture.select()
        h = fixture.host
        saved_cursor = h.cursor("waypoint-test")
        h.call("GetProgress", "waypoint-test").confirmed["17:4"] = True

        h.state.height = 0
        self.assertTrue(fixture.control("Capture", "Position without native altitude")[0])
        route = next(iter(h.ns.char.waypoints.ownRoutes.values()))
        point = route.points[1]
        self.assertIsNone(point.z, "UnitPosition's placeholder zero must not become a fixed floor")
        self.assertEqual(point.mode, "confirm")
        self.assertEqual(point.map, h.state.mapID)
        self.assertAlmostEqual(point.x, h.state.x * 100)
        self.assertAlmostEqual(point.y, h.state.y * 100)

        h.state.height = 398.9
        self.assertTrue(fixture.control("Capture", "Observed nonzero altitude")[0])
        self.assertAlmostEqual(route.points[2].z, 398.9)
        self.assertEqual(route.points[2].mode, "walk")
        h.state.height = -12.5
        self.assertTrue(fixture.control("Capture", "Observed underground altitude")[0])
        self.assertEqual(route.points[3].z, -12.5)
        self.assertEqual(route.points[3].mode, "walk")
        self.assertTrue(h.ns.char.waypoints.paused)
        self.assertEqual(h.cursor("waypoint-test"), saved_cursor)
        self.assertIsNone(h.call("GetProgress", "waypoint-test").confirmed["1:1"])
        self.assertTrue(h.call("GetProgress", "waypoint-test").confirmed["17:4"])

    def test_duo_meeting_drops_zero_height_but_preserves_nonzero_observations(self):
        h = duo_fixtures.EnhancedHost()
        saved_cursor = h.position()
        progress = h.call("GetProgress", "forever/alliance/test")
        progress.confirmed["17:4"] = True
        h.state.height = 0
        self.assertTrue(h.dcall("SetMeetingPoint")[0])
        point = h.dcall("GetMeetingStatus")
        self.assertIsNone(point.z, "A meeting must not publish the native placeholder zero as a floor")
        self.assertEqual(point.mapID, h.state.mapID)
        self.assertAlmostEqual(point.x, h.state.x)
        self.assertAlmostEqual(point.y, h.state.y)

        h.state.height = 398.9
        self.assertTrue(h.dcall("SetMeetingPoint")[0])
        self.assertAlmostEqual(h.dcall("GetMeetingStatus").z, 398.9)
        h.state.height = -12.5
        self.assertTrue(h.dcall("SetMeetingPoint")[0])
        self.assertEqual(h.dcall("GetMeetingStatus").z, -12.5)
        self.assertEqual(h.position(), saved_cursor)
        self.assertFalse(h.call("IsQuestDelivered", 100))
        self.assertTrue(progress.confirmed["17:4"])

    def test_navigation_hides_a_false_height_indicator_but_keeps_a_real_zero_floor(self):
        fixture = waypoint_fixtures.WaypointTests()
        fixture.setUp()
        fixture.select({"t": "goto", "map": 1436, "x": 50, "y": 50, "z": 0})
        h = fixture.host
        saved_cursor = h.cursor("waypoint-test")
        point = h.table({"mapID": 1436, "x": .5, "y": .5, "z": 0})

        h.state.height = 0
        self.assertIsNone(h.call("GetWaypointHeightDifference", point))
        h.call("UpdateNavigation")
        self.assertNotIn("más arriba", h.ns.navigationFrame.statusText or "")
        self.assertNotIn("más abajo", h.ns.navigationFrame.statusText or "")
        _, step, _ = h.call("GetCurrent")
        self.assertFalse(h.call("IsAtWaypoint", step.goals[1]))
        self.assertEqual(h.cursor("waypoint-test"), saved_cursor)

        h.state.height = -12.5
        self.assertEqual(h.call("GetWaypointHeightDifference", point), 12.5)
        h.call("UpdateNavigation")
        self.assertIn("más arriba", h.ns.navigationFrame.statusText)
        self.assertRegex(h.ns.navigationFrame.distance.text, r"^\d+(\.\d+)? m$")
        h.state.height = 7
        self.assertEqual(h.call("GetWaypointHeightDifference", point), -7)
        self.assertTrue(h.call("IsAtWaypoint", step.goals[1]))
        self.assertEqual(step.goals[1].z, 0)
        self.assertEqual(h.cursor("waypoint-test"), saved_cursor)


if __name__ == "__main__":
    unittest.main()
