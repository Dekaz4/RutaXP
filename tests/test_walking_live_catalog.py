"""Moving Dun Morogh hunting objectives with the actual enriched spawn catalog."""

import itertools
import unittest

from test_walking_async_live import LiveAsyncHost
from test_walking_follow import samples


class HuntingCatalogHost(LiveAsyncHost):
    def __init__(self, start=(.44, .50), fps=30, budget=.2):
        super().__init__(fps=fps, step=21, goal_index=1, budget=budget)
        self.s.mapID, self.s.x, self.s.y, self.s.height = 1426, start[0], start[1], None
        self.s.quests[384] = self.h.table({"onQuest": True, "complete": False, "objectives": [
            {"text": "Costillas de jabalí: 4/6", "numFulfilled": 4, "numRequired": 6, "finished": False},
            {"text": "Malta rapsódica: 1/1", "numFulfilled": 1, "numRequired": 1, "finished": True},
        ]})
        self.h.g.HUNT_W, self.h.g.HUNT_ENGINE = self.w, self.host.engine
        self.h.lua.execute('''
            TEST.hunt={events={},visible=0,inputs=0}
            local hunt=TEST.hunt
            local follow=HUNT_W._Follow
            HUNT_W._Follow=function(self,...)
              local i,off,floor,behind=follow(self,...)
              hunt.lastFollow={index=i,off=off,floor=floor,behind=behind,time=GetTime()}
              return i,off,floor,behind
            end
            local resolve=HUNT_W.Resolve
            HUNT_W.Resolve=function(self,point)
              hunt.inputs=hunt.inputs+1
              hunt.input=point and {source=point.source,npc=point.candidate and point.candidate.npc,
                objective=point.candidate and point.candidate.objectiveIndex,map=point.mapID,x=point.x,y=point.y}
              return resolve(self,point)
            end
            local function log(kind,from,to,reason)
              hunt.events[#hunt.events+1]={kind=kind,time=GetTime(),key=HUNT_W.key,serial=HUNT_W.serial,
                from=from,to=to,reason=reason,input=hunt.input,follow=hunt.lastFollow}
            end
            local find,cancel=HUNT_ENGINE.Find,HUNT_ENGINE.Cancel
            HUNT_ENGINE.Find=function(map,from,to,callback,water)
              log("find",from,to)
              return find(map,from,to,function(points,reason,job)
                log("answer",nil,nil,type(reason)=="string" and reason or nil)
                callback(points,reason,job)
              end,water)
            end
            HUNT_ENGINE.Cancel=function(job) log("cancel",job.from,job.to);return cancel(job) end
        ''')

    def frame(self, world=None):
        phase = super().frame(world)
        if self.ns.navigationFrame.arrow.shown:
            self.s.hunt.visible += 1
        return phase

    def summary(self):
        return {**self.stats, "phases": dict(self.phases), "visibleFrames": self.s.hunt.visible,
                "requests": self.w.GetStatus(self.w).requests - self.initial_requests,
                "cancellations": self.w.GetStatus(self.w).cancellations - self.initial_cancellations}


def reference_walk(start):
    """Compute a legal corridor and sample its ground in a separate Lua VM.

    This VM never pumps the live walk. Reading ground heights here therefore
    cannot prewarm or finish the search whose frame scheduling is under test.
    """
    h = HuntingCatalogHost(start=start)
    point = h.host.point()
    continent, north, west = h.ns.GetWaypointWorldPosition(h.ns, h.ns.PlayerPoint(h.ns))
    _, target_north, target_west = h.ns.GetWaypointWorldPosition(h.ns, point)
    result = h.host.engine.FindSync(continent, h.h.table({"x": north, "y": west}),
                                    h.h.table({"x": target_north, "y": target_west}))
    path, reason = result[:2]
    if path is None:
        raise AssertionError(f"No real terrain corridor from {start}: {reason}")
    h.h.g.HUNT_GRID = h.ns.PathingNamespace.PathGrid
    ground = h.h.lua.eval('''function(x,y,previous)
        local G=HUNT_GRID;G.Deadline(math.huge)
        local st=G.State(0);local k,cell=G.locate(st,x,y)
        if not k then return nil end
        local node=G.standing(st,k,cell,previous)
        return node and st.z[k][node+1]
    end''')
    route = [(path[i].x, path[i].y, path[i].z or 0) for i in range(1, len(path) + 1)]
    poses, previous = [], None
    for position, motion in samples(route, interval=1 / 60):
        height = ground(position[0], position[1], previous)
        if height is None:
            raise AssertionError("The reference corridor crossed an unwalkable sampled cell")
        previous = height
        poses.append(((position[0], position[1], height), motion))
    return poses, point.candidate.npc, (point.x, point.y)


class MovingHuntingCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.walks = {start: reference_walk(start) for start in ((.44, .50), (.47, .54))}

    def run_walk(self, start, fps=30, budget=.2, seconds=30):
        h = HuntingCatalogHost(start=start, fps=fps, budget=budget)
        stride = 60 // fps
        poses = self.walks[start][0][::stride]
        for position, _ in itertools.islice(poses, seconds * fps):
            h.frame(position)
        self.assertEqual(h.reported_counts, {key: h.stats[key] for key in ("find", "cancel")})
        return h

    def test_actual_ribs_objective_filters_the_finished_malt_and_produces_an_arrow_while_running(self):
        for fps in (30, 60):
            with self.subTest(fps=fps):
                h = self.run_walk((.47, .54), fps=fps, seconds=12)
                self.assertEqual(h.host.goal.quest, 384)
                self.assertEqual(h.host.point().candidate.objectiveIndex, 1)
                self.assertNotEqual(h.host.point().candidate.npc, 1247)
                self.assertGreaterEqual(h.stats["successes"], 1, h.summary())
                self.assertGreater(h.s.hunt.visible, 8 * fps, h.summary())
                self.assertEqual(h.host.progress(), h.before)

    def test_valid_hunting_corridor_does_not_stay_blank_when_another_boar_spawn_becomes_nearer(self):
        for fps in (30, 60):
            with self.subTest(fps=fps):
                h = self.run_walk((.44, .50), fps=fps, seconds=30)
                # The real path bends near another source of the same ribs.
                # Continuing that valid corridor must not blank the arrow.
                self.assertGreater(h.s.hunt.visible, 24 * h.fps, h.summary())
                self.assertLessEqual(h.stats["find"], 4, h.summary())
                self.assertEqual(h.host.progress(), h.before)

    def test_pending_hunting_search_is_not_cancelled_only_for_an_alternative_source_of_the_same_ribs(self):
        # This deliberately tiny deterministic budget takes about 15 s to
        # search the real grid, spanning several corners of observed walking.
        h = self.run_walk((.44, .50), budget=.05, seconds=18)
        events = list(h.s.hunt.events.values())
        first_answer = next((index for index, event in enumerate(events) if event.kind == "answer"), len(events))
        cancelled_before_answer = [e for e in events[:first_answer] if e.kind == "cancel"]
        self.assertEqual(cancelled_before_answer, [], h.summary())
        self.assertGreaterEqual(h.stats["successes"], 1, h.summary())
        self.assertGreater(h.s.hunt.visible, 0, h.summary())
        self.assertEqual(h.host.progress(), h.before)

    def test_a_real_objective_change_to_malt_invalidates_the_old_hunting_job(self):
        h = HuntingCatalogHost(start=(.47, .54), budget=.05)
        initial_pose = self.walks[(.47, .54)][0][0][0]
        for _ in range(8):
            h.frame(initial_pose)
            if h.w.job is not None:
                break
        old_job = h.w.job
        self.assertIsNotNone(old_job)
        objectives = h.s.quests[384].objectives
        objectives[1].numFulfilled, objectives[1].finished = 6, True
        objectives[2].numFulfilled, objectives[2].finished = 0, False
        for _ in range(12):
            h.frame(initial_pose)
        target = h.host.point()
        self.assertEqual(target.candidate.objectiveIndex, 2)
        self.assertEqual(target.candidate.npc, 1247)
        self.assertTrue(old_job.cancelled)
        self.assertGreaterEqual(h.stats["find"], 2)
        self.assertEqual(h.host.progress(), h.before)


if __name__ == "__main__":
    unittest.main()
