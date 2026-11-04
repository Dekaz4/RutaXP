"""Terrain steering keeps native player and path coordinates in the same frame."""
import math
import unittest

import test_quest_engine as fixtures


class NavigationWorldConsistencyTests(unittest.TestCase):
    def setUp(self):
        fixtures.NavigationAndFullTocTests.setUp(self)
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, .5, .5
        bounds = h.ns.mapFrames.era[1436]
        self.continent = bounds.c
        self.north = (bounds.top + bounds.bottom) / 2
        self.west = (bounds.left + bounds.right) / 2
        h.lua.execute("""
        function UnitPosition()
            return TEST.nativeNorth, TEST.nativeWest, TEST.nativeHeight, TEST.nativeInstance
        end
        """)
        self.native(self.north, self.west)

    def native(self, north, west, instance=None, height=10):
        s = self.host.state
        s.nativeNorth, s.nativeWest = north, west
        s.nativeInstance = self.continent if instance is None else instance
        s.nativeHeight = height

    def point(self, north, west, walking=True):
        h = self.host
        point = h.call("WorldToWaypoint", self.continent, north, west, 1436)
        point.walking = walking
        point.walkingWorld = h.table({"continent": self.continent, "north": north, "west": west})
        point.walkingFinal = True
        point.walkingIndex, point.walkingCount = 2, 2
        return point

    def arrow(self, point):
        h = self.host
        h.guide("world-consistency", steps=[{"title": "Terrain destination", "goals": [
            {"t": "accept", "quest": 501, "map": 1436, "x": 60, "y": 50}]}])
        h.initialize()
        h.call("SelectGuide", "world-consistency")
        h.state.arrowPoint = point
        h.ns.GetArrowWaypoint = h.lua.eval("function() return TEST.arrowPoint end")
        for texture in (h.ns.navigationFrame.body, h.ns.navigationFrame.facet, h.ns.navigationFrame.glow):
            texture.SetRotation = h.lua.eval("function(self,a) self.lastRotation=a end")
        h.call("UpdateNavigation")
        return h.ns.navigationFrame

    def tick(self):
        updater = self.host.ns.navigationUpdater
        updater.scripts.OnUpdate(updater, .00001)

    def assert_angle(self, actual, expected):
        self.assertLess(abs((actual - expected + math.pi) % (2 * math.pi) - math.pi), 1e-9)

    def test_small_ui_origin_offset_cannot_point_backwards_at_a_near_terrain_turn(self):
        h = self.host
        for offset in (2, 5):
            with self.subTest(offset=offset):
                self.native(self.north + offset, self.west)
                point = self.point(self.north + offset - 1, self.west)
                distance, right, forward, north, west = h.call("GetWaypointVector", point)
                self.assertAlmostEqual(distance, 1)
                self.assertAlmostEqual(forward, -1)
                self.assertAlmostEqual(north, -1)
                self.assertAlmostEqual(west, 0)
                self.assertAlmostEqual(right, 0)
                # The ordinary guide destination still uses C_Map's frame.
                point.walking = False
                guide_vector = h.call("GetWaypointVector", point)
                self.assertAlmostEqual(guide_vector[0], offset - 1)
                self.assertAlmostEqual(guide_vector[2], 1)

    def test_native_target_is_not_round_tripped_through_a_biased_map_conversion(self):
        h = self.host
        point = self.point(self.north + 10, self.west)
        # A map projection may differ from the terrain's exact node coordinate.
        point.x, point.y = .9, .9
        c, north, west = h.call("GetWaypointWorldPosition", point)
        self.assertEqual(c, self.continent)
        self.assertAlmostEqual(north, self.north + 10)
        self.assertAlmostEqual(west, self.west)
        self.assertAlmostEqual(h.call("GetWaypointVector", point)[0], 10)

    def test_all_cardinal_headings_match_between_initial_and_live_native_rotation(self):
        h = self.host
        self.native(self.north + 5, self.west + 2)
        frame = self.arrow(self.point(self.north + 25, self.west + 2))
        directions = ((20, 0, 0), (0, 20, math.pi / 2), (-20, 0, math.pi), (0, -20, 3 * math.pi / 2))
        for facing in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
            for dn, dw, bearing in directions:
                with self.subTest(facing=facing, bearing=bearing):
                    h.state.facing = facing
                    h.state.arrowPoint = self.point(self.north + 5 + dn, self.west + 2 + dw)
                    h.call("UpdateNavigation")
                    expected = (bearing - facing) % (2 * math.pi)
                    self.assert_angle(frame.body.lastRotation, expected)
                    self.tick()
                    for texture in (frame.body, frame.facet, frame.glow):
                        self.assert_angle(texture.lastRotation, expected)
        self.assertTrue(frame.useNativePosition)

    def test_live_rotation_uses_moving_native_origin_before_map_origin(self):
        h = self.host
        frame = self.arrow(self.point(self.north + 20, self.west))
        self.assert_angle(frame.body.lastRotation, 0)
        self.native(self.north + 20, self.west + 10)
        self.tick()
        self.assert_angle(frame.body.lastRotation, 3 * math.pi / 2)

    def test_other_instance_or_unreadable_native_xy_falls_back_to_map_origin(self):
        h = self.host
        point = self.point(self.north + 20, self.west)
        frame = self.arrow(point)
        for north, west, instance in ((self.north + 30, self.west, self.continent + 1),
                                      (None, self.west, self.continent),
                                      (math.inf, self.west, self.continent)):
            with self.subTest(north=north, instance=instance):
                self.native(north, west, instance=instance)
                self.assertAlmostEqual(h.call("GetWaypointVector", point)[0], 20)
                h.call("UpdateNavigation")
                self.tick()
                self.assert_angle(frame.body.lastRotation, 0)

    def test_secret_native_xy_is_not_used_for_arithmetic(self):
        h = self.host
        h.lua.execute("function issecretvalue(value) return value==123456789 end")
        self.native(123456789, self.west)
        self.assertAlmostEqual(h.call("GetWaypointVector", self.point(self.north + 20, self.west))[0], 20)

    def test_height_matches_the_native_target_continent(self):
        h = self.host
        point = self.point(self.north + 20, self.west)
        point.z = 40
        self.native(self.north, self.west, height=25)
        self.assertEqual(h.call("GetWaypointHeightDifference", point), 15)
        self.native(self.north, self.west, instance=self.continent + 1, height=25)
        self.assertIsNone(h.call("GetWaypointHeightDifference", point))


if __name__ == "__main__":
    unittest.main()
