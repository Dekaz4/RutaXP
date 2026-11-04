"""Real Path.Find competes with movement, navigation sampling and frame timers."""

from collections import Counter
import math
import unittest

from test_access_navigation import AccessHost, DWARF
from test_walking_follow import FollowHost, samples


class LiveAsyncHost:
    def __init__(self, fps=30, step=13, goal_index=2, budget=.2):
        self.fps = fps
        self.host = AccessHost(DWARF, step, goal_index, x=.312 if step == 13 else .44,
                               y=.679 if step == 13 else .54, terrain=True)
        self.h, self.ns, self.s = self.host.h, self.host.ns, self.host.s
        self.w = self.ns.Walking
        self.w.Clear(self.w)
        initial = self.w.GetStatus(self.w)
        self.initial_requests, self.initial_cancellations = initial.requests, initial.cancellations
        self.s.height = 410 if step == 13 else 400
        self.before = self.host.progress()
        self.h.g.LIVE_NS, self.h.g.LIVE_ENGINE = self.ns, self.host.engine
        self.h.lua.execute(r'''
            TEST.live={find=0,cancel=0,answers=0,successes=0,clock=0,log={}}
            local stats=TEST.live
            local function record(kind,reason)
              stats.log[#stats.log+1]={kind=kind,time=GetTime(),reason=reason,serial=LIVE_NS.Walking.serial}
            end
            local find,cancel=LIVE_ENGINE.Find,LIVE_ENGINE.Cancel
            -- Deterministic profiling samples keep the actual path coroutine
            -- sliced over frames even on a fast test machine. GetTime remains
            -- the player's clock; Path's budget is still measured in ms.
            LIVE_ENGINE.clock=function() stats.clock=stats.clock+.02;return stats.clock end
            LIVE_ENGINE.Find=function(map,from,to,callback,water)
              stats.find=stats.find+1;record("find")
              return find(map,from,to,function(points,reason,job)
                stats.answers=stats.answers+1
                if type(points)=="table" then stats.successes=stats.successes+1 end
                record("answer",type(reason)=="string" and reason or nil)
                callback(points,reason,job)
              end,water)
            end
            LIVE_ENGINE.Cancel=function(job)
              stats.cancel=stats.cancel+1;record("cancel");return cancel(job)
            end
        ''')
        self.host.engine.budget = budget
        self.phases = Counter()

    @property
    def stats(self):
        return {key: self.s.live[key] for key in ("find", "cancel", "answers", "successes")}

    @property
    def reported_counts(self):
        status = self.w.GetStatus(self.w)
        return {"find": status.requests - self.initial_requests,
                "cancel": status.cancellations - self.initial_cancellations}

    def place(self, world):
        point = self.ns.WorldToWaypoint(self.ns, 0, world[0], world[1], 1426)
        self.s.x, self.s.y, self.s.height = point.x, point.y, world[2]

    def frame(self, world=None):
        if world is not None:
            self.place(world)
        self.s.now += 1 / self.fps
        driver = self.ns.navigationUpdater
        driver.scripts.OnUpdate(driver, 1 / self.fps)
        self.h.g.AccessPump()  # Exactly one queued timer callback per frame.
        phase = self.w.GetStatus(self.w).phase
        self.phases[phase] += 1
        return phase

    def turnin_marker(self):
        self.h.g.LIVE_MARKER = self.ns.GetGoalWaypoint(self.ns, self.host.goal)
        self.s.quests[self.host.goal.quest].complete = True
        self.s.markerDelta = 0
        self.h.lua.execute(r'''
            function C_QuestLog.GetNextWaypoint(id)
              if TEST.markerAvailable==false or (id~=420 and not (id==2160 and TEST.secondMarker)) then return nil end
              local b=LIVE_NS.mapFrames.era[1426]
              return 1426,LIVE_MARKER.x+TEST.markerDelta/(b.right-b.left),LIVE_MARKER.y
            end
        ''')


class LiveWalkingAsyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gozwin_route = FollowHost().route

    def test_actual_gozwin_collect_and_kill_finish_calculating_while_running_at_30_and_60_fps(self):
        for fps in (30, 60):
            for goal_index in (2, 3):
                with self.subTest(fps=fps, action="collect" if goal_index == 2 else "kill"):
                    h = LiveAsyncHost(fps=fps, goal_index=goal_index)
                    for frame, (position, _) in enumerate(samples(self.gozwin_route, interval=1 / fps)):
                        h.frame(position)
                        if frame >= 12 * fps:
                            break
                    self.assertGreaterEqual(h.stats["successes"], 1, h.stats)
                    self.assertEqual(h.stats["find"], 1, h.stats)
                    self.assertEqual(h.stats["cancel"], 0, h.stats)
                    self.assertGreater(h.phases["walking"], 8 * fps, h.phases)
                    self.assertEqual(h.host.progress(), h.before)

    def test_subyard_live_turnin_marker_jitter_does_not_require_stopping_to_finish(self):
        for fps in (30, 60):
            with self.subTest(fps=fps):
                h = LiveAsyncHost(fps=fps, step=18, goal_index=1)
                h.turnin_marker()
                bounds = h.ns.mapFrames.era[1426]
                for frame in range(6 * fps):
                    # Run seven yards per second. The same live NPC marker
                    # varies by at most 0.2 yd, well below meaningful relocation.
                    h.s.x += 7 / fps / abs(bounds.right - bounds.left)
                    h.s.markerDelta = math.sin(frame * .3) * .2
                    h.frame()
                moving = h.stats
                for _ in range(6 * fps):
                    h.frame()  # Freeze both movement and the last marker sample.
                self.assertGreaterEqual(moving["successes"], 1, moving)
                self.assertLessEqual(moving["find"], 2, moving)
                self.assertLessEqual(moving["cancel"], 1, moving)
                self.assertEqual(h.w.GetStatus(h.w).phase, "walking", h.stats)
                self.assertEqual(h.host.progress(), h.before)

    def test_a_material_live_target_move_still_replans_without_altering_quest_progress(self):
        h = LiveAsyncHost(step=18, goal_index=1)
        h.turnin_marker()
        for _ in range(6 * h.fps):
            h.frame()
        initial = h.stats
        self.assertGreaterEqual(initial["successes"], 1, initial)
        h.s.markerDelta = 20
        for _ in range(6 * h.fps):
            h.frame()
        self.assertGreater(h.stats["find"], initial["find"], h.stats)
        self.assertGreater(h.stats["successes"], initial["successes"], h.stats)
        self.assertEqual(h.w.GetStatus(h.w).phase, "walking")
        self.assertEqual(h.host.progress(), h.before)

    def test_same_turnin_can_alternate_live_and_authored_provider_while_the_player_runs(self):
        h = LiveAsyncHost(step=18, goal_index=1)
        h.turnin_marker()
        bounds = h.ns.mapFrames.era[1426]
        for frame in range(6 * h.fps):
            h.s.x += 7 / h.fps / abs(bounds.right - bounds.left)
            h.s.markerDelta = .2 * math.sin(frame * .3)
            h.s.markerAvailable = (frame // 12) % 2 == 0
            h.frame()
        moving = h.stats
        self.assertGreaterEqual(moving["successes"], 1, moving)
        self.assertLessEqual(moving["find"], 2, moving)
        self.assertLessEqual(moving["cancel"], 1, moving)
        self.assertEqual(h.host.progress(), h.before)

    def test_changing_the_actual_quest_at_identical_marker_xy_still_starts_a_new_search(self):
        h = LiveAsyncHost(step=18, goal_index=1)
        h.turnin_marker()
        for _ in range(6 * h.fps):
            h.frame()
        first = h.host.point()
        first_stats = h.stats
        h.s.quests[2160] = h.h.table({"onQuest": True, "complete": True})
        h.s.secondMarker = True
        h.ns.Next(h.ns)  # Explicitly confirm goal 420; select the real next goal.
        second = h.host.point()
        self.assertEqual((first.x, first.y), (second.x, second.y))
        self.assertEqual((first.goal.quest, second.goal.quest), (420, 2160))
        after_user_action = h.host.progress()
        for _ in range(6 * h.fps):
            h.frame()
        self.assertEqual(h.stats["find"], first_stats["find"] + 1, h.stats)
        self.assertGreater(h.stats["successes"], first_stats["successes"], h.stats)
        self.assertEqual(h.host.progress(), after_user_action)

    def test_slow_accumulated_marker_drift_eventually_exceeds_the_anchored_tolerance(self):
        h = LiveAsyncHost(step=18, goal_index=1)
        h.turnin_marker()
        origin = h.ns.GetWaypointWorldPosition(h.ns, h.host.point())
        for frame in range(6 * h.fps):
            h.s.markerDelta = (frame + 1) / h.fps * .75
            h.frame()
        moving = h.stats
        for _ in range(6 * h.fps):
            h.frame()
        self.assertGreaterEqual(moving["find"], 2, moving)
        self.assertLessEqual(moving["find"], 3, moving)
        self.assertGreaterEqual(abs(h.w.target.y - origin[2]), 4)
        self.assertEqual(h.w.GetStatus(h.w).phase, "walking", h.stats)
        self.assertEqual(h.host.point().goal.quest, 420)
        self.assertEqual(h.host.progress(), h.before)

    def test_pending_job_pauses_in_combat_and_resumes_on_the_real_regen_event_while_running(self):
        h = LiveAsyncHost(fps=30)
        h.h.lua.execute('''
            function InCombatLockdown() return TEST.combat==true end
            local create=CreateFrame
            CreateFrame=function(...)
              local frame=create(...)
              function frame:UnregisterEvent(event) self.events[event]=nil end
              return frame
            end
        ''')
        trajectory = iter(samples(self.gozwin_route, interval=1 / h.fps))
        for _ in range(12):
            h.frame(next(trajectory)[0])
            if h.w.job is not None:
                break
        job, serial = h.w.job, h.w.serial
        self.assertIsNotNone(job)
        h.s.combat = True
        h.h.g.EmitAddonEvent("PLAYER_REGEN_DISABLED")
        for _ in range(2 * h.fps):
            h.frame(next(trajectory)[0])
        self.assertTrue(h.h.lua.eval("rawequal")(h.w.job, job))
        self.assertEqual(h.w.serial, serial)
        self.assertEqual(h.stats, {"find": 1, "cancel": 0, "answers": 0, "successes": 0})
        self.assertEqual(h.reported_counts, {"find": 1, "cancel": 0})
        self.assertIn("combate", h.w.GetStatus(h.w).text)
        self.assertTrue(any(frame.events.PLAYER_REGEN_ENABLED for frame in h.s.eventFrames.values()))

        h.s.combat = False
        h.h.g.EmitAddonEvent("PLAYER_REGEN_ENABLED")
        for _ in range(8 * h.fps):
            h.frame(next(trajectory)[0])
        self.assertEqual(h.stats, {"find": 1, "cancel": 0, "answers": 1, "successes": 1})
        self.assertEqual(h.reported_counts, {"find": 1, "cancel": 0})
        self.assertEqual(h.w.GetStatus(h.w).phase, "walking")
        self.assertEqual(h.host.progress(), h.before)


if __name__ == "__main__":
    unittest.main()
