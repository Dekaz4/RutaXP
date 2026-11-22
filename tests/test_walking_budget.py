"""Bound terrain work at Theramore and keep a usable local compass bearing."""
import unittest

from test_access_navigation import AccessHost, DWARF, load_pathing
from test_destination_travel import Destinations
from test_walking_history import WalkingHistoryHost


class TerrainBudgetTests(unittest.TestCase):
    def test_theramore_dock_to_flight_master_offers_bearing_then_real_turns(self):
        h = AccessHost(DWARF, 13, 2, terrain=True)
        h.s.mapID, h.s.x, h.s.y, h.s.height = 1445, .711, .564, None
        w = h.ns.Walking
        w.Clear(w)
        requests = w.requests
        for tick in range(360):
            h.s.now += 1 / 30
            # The quest and panel can redraw independently of the path queue.
            # The table is fresh on every update. Its endpoint is stable.
            point = h.h.table({"mapID":1445, "x":.6746, "y":.5120, "targetKey":"taxi-32"})
            result = w.Resolve(w, point)
            if tick == 0:
                self.assertTrue(result.navigationBearing)
                self.assertTrue(result.navigationBlocked)
            if tick % 4 == 1:
                self.assertIsNone(w.Resolve(w, None))
            if result.walking:
                self.assertEqual(result.mapID, 1445)
                self.assertLess(result.walkingDistance, 400)
                break
            h.h.g.AccessPump()
        else:
            self.fail(f"Theramore harbour path did not resolve: {w.phase}, {w.failure}")
        self.assertEqual(w.requests - requests, 1)

    def test_stalled_job_retries_once_then_settles_and_late_callbacks_are_ignored(self):
        h = WalkingHistoryHost()
        target = h.point(300)
        for t in range(95):
            h.s.now = t
            out = h.w.Resolve(h.w, target)
            self.assertTrue(out.navigationBearing)
            self.assertIn("orientativo", out.navigationBearingText)
        self.assertEqual((h.s.finds, h.s.cancels), (2, 2))
        self.assertEqual((h.w.phase, h.w.failure), ("failed", "timeout"))
        h.answer(1)
        h.answer(2)
        self.assertIsNone(h.w.points)
        # New physical evidence permits a fresh search without any manual UI.
        h.s.x = 35
        h.w.Resolve(h.w, target)
        self.assertEqual(h.s.finds, 3)

    def test_negative_terrain_answer_is_cached_until_relocation_or_retry(self):
        h = WalkingHistoryHost()
        target = h.point(300)
        h.w.Resolve(h.w, target)
        h.answer(failure=True)
        for t in range(1, 65):
            h.s.now = t
            self.assertTrue(h.w.Resolve(h.w,target).navigationBearing)
        self.assertEqual(h.s.finds, 1)
        self.assertEqual(h.w.phase, "failed")
        h.w.Retry(h.w)
        h.w.Resolve(h.w,target)
        self.assertEqual(h.s.finds, 2)

    def test_cpu_heavy_job_settles_without_repeating_at_high_frame_rate(self):
        h = WalkingHistoryHost()
        target = h.point(300)
        h.w.Resolve(h.w,target)
        h.w.job.cpu, h.w.job.frames = 601, 305
        h.s.now = 4
        self.assertTrue(h.w.Resolve(h.w,target).navigationBearing)
        h.s.now = 100
        h.w.Resolve(h.w,target)
        self.assertEqual((h.w.phase,h.s.finds,h.s.cancels), ("failed",1,1))

    def test_kharanos_cross_continent_leg_is_local_and_hearth_cancels_old_work(self):
        h = Destinations((1426,.467,.501))
        load_pathing(h.h)
        goal = (1443,.5776,.7105)
        pin,view = h.route(goal, "chapter")
        self.assertEqual(pin.mapID, 1426)
        w = h.ns.Walking
        initial = w.Resolve(w,pin)
        self.assertTrue(initial.navigationBearing)
        old = w.job
        h.locate((1437,.09,.57))
        pin,new_view = h.route(goal, "chapter")
        self.assertEqual(pin.mapID,1437)
        self.assertTrue(w.Resolve(w,pin).navigationBearing)
        self.assertTrue(old.cancelled)
        # No remote bearing even if an old input survives during load.
        remote = h.h.table({"mapID":1443,"x":.5776,"y":.7105})
        out = w.Resolve(w,remote)
        self.assertTrue(out.navigationBlocked)
        self.assertFalse(out.navigationBearing)
        self.assertIsNone(w.job)
        self.assertIsNone(w.Resolve(w,None))

    def test_new_activity_and_combat_pause_do_not_reuse_or_expire_wrong_work(self):
        h=WalkingHistoryHost()
        h.lua.execute("function InCombatLockdown() return TEST.combat==true end")
        p=h.point(300)
        p.activityKey=42
        h.w.Resolve(h.w,p)
        h.s.combat=True
        for t in range(1,40):
            h.s.now=t
            out=h.w.Resolve(h.w,p)
            self.assertFalse(out.navigationBearing)
        self.assertEqual((h.s.finds,h.s.cancels),(1,0))
        h.s.combat=False
        h.w.Resolve(h.w,p)
        p.activityKey=43
        h.w.Resolve(h.w,p)
        self.assertEqual((h.s.finds,h.s.cancels),(2,1))


if __name__ == "__main__":
    unittest.main()
