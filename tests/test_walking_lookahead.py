"""The visible heading may look ahead while the route cursor still approaches its bend."""

import math
import unittest

from test_walking_history import WalkingHistoryHost


class WalkingLookaheadTests(unittest.TestCase):
    def follow(self, nodes, mesh=True):
        host = WalkingHistoryHost()
        if mesh:
            host.ns.PathingNamespace = host.table({"PathGrid": {"TILE": 512}})
            host.lua.globals().RutaXPPathData = host.table({0: {"cells": 128}})
        host.s.x, host.s.y, host.s.z = nodes[0]
        goal = host.point(nodes[-1][0])
        goal.y, goal.z = nodes[-1][1] / 1000, nodes[-1][2]
        host.w.Resolve(host.w, goal)
        path = host.table([{"map": 0, "x": x, "y": y, "z": z} for x, y, z in nodes])
        host.s.jobs[1].callback(path, 100)
        return host, goal, host.w.Resolve(host.w, goal)

    def test_seven_yard_segments_aim_ahead_without_marking_arrival_or_losing_distance(self):
        for mesh in (True, False):
            with self.subTest(mesh=mesh):
                h, _, point = self.follow([(0, 0, 0), (7, 0, 0), (14, 0, 0), (21, 0, 0), (80, 0, 0)], mesh)
                self.assertEqual(point.walkingWorld.north, 36)
                self.assertEqual(point.walkingIndex, 2)
                self.assertEqual(h.w.index, 2)
                self.assertEqual(h.w.progress, 0)
                self.assertEqual(point.walkingDistance, 80)
                self.assertFalse(point.walkingFinal)

    def test_gentle_bend_can_share_a_mesh_corridor_but_not_cut_into_another_cell(self):
        for bend_y, expected in ((2.6, 36), (4.1, 10)):
            with self.subTest(bend_y=bend_y):
                _, _, point = self.follow([(0, 3.8, 0), (10, bend_y, 0), (40, 3.8, 0)])
                if expected == 10:
                    self.assertEqual((point.walkingWorld.north, point.walkingWorld.west), (10, bend_y))
                else:
                    self.assertGreater(point.walkingWorld.north, 35)
                self.assertAlmostEqual(point.walkingDistance,
                                       math.hypot(10, bend_y - 3.8) + math.hypot(30, bend_y - 3.8))

    def test_turns_and_height_changes_keep_the_real_bend(self):
        for nodes in ([(0, 0, 0), (7, 0, 0), (7, 40, 0)],
                      [(0, 0, 0), (7, 0, 0), (30, 0, 15)],
                      [(0, 0, 0), (7, 0, -4), (40, 0, 0)]):
            with self.subTest(nodes=nodes):
                _, _, point = self.follow(nodes)
                self.assertEqual((point.walkingWorld.north, point.walkingWorld.west, point.z), nodes[1])

    def test_aiming_at_the_last_node_does_not_consume_the_last_segment(self):
        h, goal, point = self.follow([(0, 0, 0), (7, 0, 0), (25, 0, 0)])
        self.assertEqual(point.walkingWorld.north, 25)
        self.assertFalse(point.walkingFinal)
        h.s.x, h.s.now = 7, 1
        point = h.w.Resolve(h.w, goal)
        self.assertTrue(point.walkingFinal)
        self.assertEqual(point.walkingIndex, 3)
        self.assertEqual(point.walkingDistance, 18)

    def test_npc_with_unknown_height_uses_mapped_nodes_then_the_exact_final_destination(self):
        h, goal, point = self.follow([(0, 0, 12), (7, 0, 12), (21, 0, 12), (46, 0, None)])
        self.assertEqual(point.walkingWorld.north, 21)
        self.assertEqual(point.walkingDistance, 46)
        self.assertEqual(point.walkingIndex, 2)
        self.assertFalse(point.walkingFinal)
        for x in (7, 14, 21):
            h.s.x, h.s.now = x, x / 7
            point = h.w.Resolve(h.w, goal)
        self.assertTrue(point.walkingFinal)
        self.assertEqual(point.walkingWorld.north, 46)
        self.assertIsNone(point.z)
        self.assertEqual(point.walkingGoal.x, goal.x)


if __name__ == "__main__":
    unittest.main()
