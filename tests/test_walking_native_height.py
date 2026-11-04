"""Forever's unread native height must not invalidate real walking routes."""

import itertools
import unittest

from test_walking_async_live import LiveAsyncHost
from test_walking_follow import FollowHost, samples
from test_walking_live_catalog import HuntingCatalogHost, reference_walk


class NativeHeightWalkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gozwin_route = FollowHost().route
        cls.hunting_walk = reference_walk((.47, .54))[0]

    def run_moving(self, mode, fps=30, hunting=False):
        h = HuntingCatalogHost(start=(.47, .54), fps=fps) if hunting else LiveAsyncHost(fps=fps)
        trajectory = self.hunting_walk[::60 // fps] if hunting else samples(self.gozwin_route, interval=1 / fps)
        for frame, (position, _) in enumerate(itertools.islice(trajectory, 12 * fps)):
            choice = (frame // max(1, fps // 4)) % 3 if mode == "alternating" else None
            native_height = 0 if mode == "zero" or choice == 0 else None if mode == "unknown" or choice == 1 else position[2]
            h.frame((position[0], position[1], native_height))
        return h

    def assert_moving_route(self, h):
        status = h.w.GetStatus(h.w)
        evidence = {**h.stats, "phases": dict(h.phases), "accepted": status.accepted,
                    "rejected": status.rejected, "lastReason": status.lastReason}
        self.assertGreaterEqual(status.accepted or 0, 1, evidence)
        self.assertEqual(status.rejected or 0, 0, evidence)
        self.assertEqual(h.stats["find"], 1, evidence)
        self.assertEqual(h.stats["cancel"], 0, evidence)
        self.assertGreater(h.phases["walking"], 8 * h.fps, evidence)
        self.assertTrue(h.ns.navigationFrame.arrow.shown, evidence)
        self.assertEqual(h.reported_counts, {key: h.stats[key] for key in ("find", "cancel")})
        self.assertEqual(h.host.progress(), h.before)

    def test_zero_native_height_allows_real_gozwin_and_ribs_routes_while_running(self):
        for fps in (30, 60):
            for hunting in (False, True):
                with self.subTest(fps=fps, quest=384 if hunting else 97277):
                    self.assert_moving_route(self.run_moving("zero", fps, hunting))

    def test_missing_native_height_remains_unknown_instead_of_becoming_zero(self):
        for fps in (30, 60):
            with self.subTest(fps=fps):
                self.assert_moving_route(self.run_moving("unknown", fps))

    def test_zero_real_and_missing_native_samples_can_alternate_during_the_same_search(self):
        for fps in (30, 60):
            with self.subTest(fps=fps):
                self.assert_moving_route(self.run_moving("alternating", fps))

    def test_a_real_nonzero_height_on_the_wrong_floor_still_blocks_the_arrow(self):
        h = self.run_moving("real")
        self.assert_moving_route(h)
        wrong_height = h.s.height + 40
        h.s.height = wrong_height
        h.s.now += .11
        h.ns.UpdateNavigation(h.ns)
        self.assertFalse(h.ns.navigationFrame.arrow.shown)
        self.assertEqual(h.w.GetStatus(h.w).phase, "pending")
        self.assertEqual(h.w.GetStatus(h.w).lastReason, "floor")
        self.assertIsNotNone(h.w.job)
        self.assertEqual(h.w.job["from"].z, wrong_height)
        self.assertEqual(h.host.progress(), h.before)

    def test_zero_in_a_destination_is_preserved_when_dispatching_to_the_real_engine(self):
        h = LiveAsyncHost()
        point = h.ns.ResolveWaypointPoint(h.ns, h.h.table({
            "mapID": 1426, "x": h.host.point().x, "y": h.host.point().y, "z": 0,
        }))
        point.goal = h.host.goal
        self.assertEqual(point.z, 0)
        self.assertEqual(h.ns.GetWaypointHeightDifference(h.ns, point), -h.s.height)
        h.w.Resolve(h.w, point)
        self.assertEqual(h.w.target.z, 0)
        self.assertIsNotNone(h.w.job)
        self.assertEqual(h.w.job.to.z, 0)
        self.assertEqual(h.host.progress(), h.before)

    def test_actual_sea_level_mesh_nodes_keep_their_legitimate_zero_height(self):
        h = LiveAsyncHost()
        # Adjacent walkable sea-surface cells in the shipping Kalimdor mesh.
        # Zero is valid terrain data here, unlike the native API placeholder.
        north, west, cell_size = -1064.5833333333321, -5864.583333333334, 1600 / 3 / 128
        h.h.g.HEIGHT_GRID = h.ns.PathingNamespace.PathGrid
        height_at = h.h.lua.eval('''function(x,y)
            local G=HEIGHT_GRID;G.Deadline(math.huge)
            local st=G.State(1);local k,cell=G.locate(st,x,y)
            local flags=G.grid(st,k)
            return flags[cell+1],st.z[k][cell+1]
        end''')
        for position in ((north, west), (north, west + cell_size)):
            flags, height = height_at(*position)
            self.assertNotEqual(flags, 0)
            self.assertEqual(height, 0)
        result = h.host.engine.FindSync(1,
            h.h.table({"x": north, "y": west, "z": 0}),
            h.h.table({"x": north, "y": west + cell_size, "z": 0}))
        points = result[0]
        self.assertIsNotNone(points, result[1])
        self.assertGreaterEqual(len(points), 2)
        self.assertTrue(all(points[i].z == 0 for i in range(1, len(points) + 1)))
        self.assertEqual(h.host.progress(), h.before)


if __name__ == "__main__":
    unittest.main()
