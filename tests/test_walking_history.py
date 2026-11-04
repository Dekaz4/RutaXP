"""Delayed path answers use bounded observed motion, not a future nearest edge."""

from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]


class WalkingHistoryHost:
    def __init__(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.ns = self.lua.table()
        self.ns.char = self.table({"walking": {"enabled": True}, "progress": {"g": {"cursor": 21}}})
        self.lua.globals().AUDIT_NS = self.ns
        self.lua.execute('''
            TEST={now=0,x=0,y=0,z=0,finds=0,cancels=0,jobs={}}
            function GetTime() return TEST.now end
            function UnitPosition() return TEST.x,TEST.y,TEST.z,0 end
            function AUDIT_NS:GetWaypointWorldPosition(p) return 0,p.x*1000,p.y*1000 end
            function AUDIT_NS:PlayerPoint() return {mapID=1,x=TEST.x/1000,y=TEST.y/1000} end
            function AUDIT_NS:WorldToWaypoint(c,x,y,map) return {mapID=map,x=x/1000,y=y/1000} end
            RutaXPPathEngine={Available=function() return true end,
                Find=function(c,from,to,callback)
                    TEST.finds=TEST.finds+1
                    local job={map=c,from=from,to=to,callback=callback}
                    TEST.jobs[#TEST.jobs+1]=job;return job
                end,
                Cancel=function(job) TEST.cancels=TEST.cancels+1;job.cancelled=true end}
        ''')
        self.load = self.lua.eval('function(s,ns) assert(loadstring(s))("RutaXP",ns) end')
        self.load((ROOT / "RutaXP/Walking.lua").read_text(encoding="utf-8-sig"), self.ns)
        self.w, self.s = self.ns.Walking, self.lua.globals().TEST

    def table(self, value):
        if isinstance(value, dict):
            return self.lua.table_from({k: self.table(v) for k, v in value.items()})
        if isinstance(value, list):
            return self.lua.table_from([self.table(v) for v in value])
        return value

    def point(self, x, quest=10, objective=1, npc=None, dynamic=False):
        point = {"mapID": 1, "x": x / 1000, "y": 0, "z": 0,
                 "goal": {"t": "complete", "quest": quest}, "source": "game"}
        if not dynamic:
            point["candidate"] = {"npc": npc or 1, "objectiveIndex": objective}
        return self.table(point)

    def answer(self, index=1, failure=False):
        job = self.s.jobs[index]
        if failure:
            job.callback(None, "unreachable")
        else:
            job.callback(self.table([
                {"map": 0, "x": job["from"].x, "y": job["from"].y, "z": job["from"].z},
                {"map": 0, "x": job.to.x, "y": job.to.y, "z": job.to.z}]), 100)


class WalkingMotionHistoryTests(unittest.TestCase):
    def test_late_answer_replays_two_already_walked_corners_in_order(self):
        h = WalkingHistoryHost()
        h.w.travel, h.w.seenX, h.w.seenY, h.w.seenZ = 55, 20, 35, 0
        samples = [(0, 0, 0), (0, 10, 10), (0, 20, 20), (10, 20, 30),
                   (20, 20, 40), (20, 30, 50), (20, 35, 55)]
        h.w.trace = h.table([{"x": x, "y": y, "z": 0, "travel": d, "time": d / 7} for x, y, d in samples])
        h.w.traceValid = True
        points = h.table([{"x": 0, "y": 0, "z": 0}, {"x": 0, "y": 20, "z": 0},
                          {"x": 20, "y": 20, "z": 0}, {"x": 20, "y": 40, "z": 0}])
        self.assertTrue(h.w._Adopt(h.w, points, 0, 0))
        self.assertEqual(h.w.index, 4)
        self.assertEqual(h.w.points[h.w.index].y, 40)
        self.assertIsNone(h.w.trace)
        self.assertEqual(h.ns.char.progress.g.cursor, 21)

    def test_invalid_motion_trace_cannot_acquire_a_nearby_corridor(self):
        h = WalkingHistoryHost()
        h.w.traceValid = False
        h.w.travel, h.w.seenX, h.w.seenY, h.w.seenZ = 20, 20, 0, 0
        points = h.table([{"x": 0, "y": 0, "z": 0}, {"x": 100, "y": 0, "z": 0}])
        self.assertFalse(h.w._Adopt(h.w, points, 0, 0))
        self.assertIsNone(h.w.points)
        self.assertTrue(h.w.refreshWanted)
        self.assertEqual(h.ns.char.walking.diagnostics.lastReason, "trace-invalid")

    def test_trace_is_bounded_and_overflow_cannot_be_used_as_a_connector(self):
        h = WalkingHistoryHost()
        h.w.pending, h.w.traceValid = True, True
        h.w.trace = h.table([{"x": 0, "y": 0, "z": 0, "travel": 0, "time": 0}])
        for i in range(1, 601):
            h.s.now, h.w.travel = i * .1, i * .5
            h.w._RecordMotion(h.w, i * .5, 0, 0)
        self.assertEqual(len(h.w.trace), 512)
        self.assertFalse(h.w.traceValid)
        diagnostics = h.ns.char.walking.diagnostics
        self.assertEqual(diagnostics.reasons["trace-limit"], 1)
        self.assertEqual(set(diagnostics.keys()), {"requests", "cancellations", "accepted", "rejected", "lastReason", "reasons"})

    def test_background_query_origin_does_not_change_old_path_budget_or_floor(self):
        h = WalkingHistoryHost()
        h.w.points = h.table([{"x": 0, "y": 0}, {"x": 0, "y": 20, "z": 100}, {"x": 20, "y": 20, "z": 100}])
        h.w.arc, h.w.index, h.w.progress = h.table([0, 20, 40]), 2, 0
        h.w.travel, h.w.pathTravel, h.w.pathZ = 30, 0, 100
        h.w.requestTravel, h.w.requestZ = 999, 500
        index, off, floor, behind = h.w._Follow(h.w, 10, 20, 100)
        self.assertEqual(index, 3)
        self.assertEqual(off, 0)
        self.assertTrue(floor)
        self.assertFalse(behind)

    def test_same_resource_camp_is_committed_but_a_new_real_objective_cancels(self):
        h = WalkingHistoryHost()
        h.w.Resolve(h.w, h.point(100, npc=1125))
        h.s.now = 3
        h.w.Resolve(h.w, h.point(300, npc=1126))
        self.assertEqual((h.s.finds, h.s.cancels), (1, 0))
        self.assertEqual(h.w.target.x, 100)
        h.w.Resolve(h.w, h.point(500, objective=2, npc=1247))
        self.assertEqual((h.s.finds, h.s.cancels), (2, 1))
        old = h.s.jobs[1]
        old.callback(h.table([{"map": 0, "x": 0, "y": 0}, {"map": 0, "x": 100, "y": 0}]), 100)
        self.assertIsNone(h.w.points, "A late callback from the finished objective is discarded")

    def test_dynamic_endpoint_updates_keep_pending_job_and_failed_refresh_does_not_fake_arrival(self):
        h = WalkingHistoryHost()
        h.w.Resolve(h.w, h.point(100, dynamic=True))
        h.s.now = 1
        h.w.Resolve(h.w, h.point(200, dynamic=True))
        self.assertEqual((h.s.finds, h.s.cancels), (1, 0))
        self.assertEqual(h.s.jobs[1].to.x, 100)
        h.answer()
        h.s.now = 3
        point = h.w.Resolve(h.w, h.point(200, dynamic=True))
        self.assertTrue(point.walking)
        self.assertTrue(h.w.pending)
        self.assertEqual(h.s.finds, 2)
        h.answer(2, failure=True)
        self.assertIsNotNone(h.w.points)
        for x in (40, 80, 100):
            h.s.x, h.s.now = x, h.s.now + .1
            point = h.w.Resolve(h.w, h.point(200, dynamic=True))
        self.assertTrue(point.navigationBlocked)
        self.assertFalse(bool(point.walkingFinal))
        self.assertEqual(h.s.finds, 2, "Same-endpoint failures use a retry backoff")
        h.s.now = 19
        h.w.Resolve(h.w, h.point(200, dynamic=True))
        self.assertEqual(h.s.finds, 3)


if __name__ == "__main__":
    unittest.main()
