"""Authored access points and real terrain searches preserve quest progress."""

import base64
import math
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import zlib

from test_duo import DUO_STUBS
from test_duo_journey import primitive_copy
import test_talent_trainer_regressions as full


ADDON = Path(__file__).resolve().parents[1] / "RutaXP"
HUMAN = "forever/alliance/human/01-elwynn-forest"
DWARF = "forever/alliance/dwarf-gnome/01-dun-morogh"
ORC = "forever/horde/orc-troll/01-durotar"

WORLD_STUBS = r'''
function CreateVector2D(x,y) return {GetXY=function() return x,y end} end
function C_Map.GetWorldPosFromMapPos(mapID,p)
    if TEST.positionUnavailable then return nil end
    local b=ACCESS_NS.mapFrames.era[mapID]
    if not b then return nil end
    local x,y=p:GetXY()
    return b.c,CreateVector2D(b.top+(b.bottom-b.top)*y,b.left+(b.right-b.left)*x)
end
function C_Map.GetMapPosFromWorldPos(continent,p,mapID)
    local b=ACCESS_NS.mapFrames.era[mapID]
    if not b or b.c~=continent then return nil end
    local north,west=p:GetXY()
    return mapID,CreateVector2D((west-b.left)/(b.right-b.left),(north-b.top)/(b.bottom-b.top))
end
function UnitPosition()
    if TEST.positionUnavailable then return nil end
    local c,p=C_Map.GetWorldPosFromMapPos(TEST.mapID,CreateVector2D(TEST.x,TEST.y))
    if not p then return nil end
    local north,west=p:GetXY();return north,west,TEST.height,c
end
function GetPlayerFacing() return 0 end
function IsInInstance() return false end
function IsIndoors() return TEST.indoors==true end
'''


def load_pathing(host, missing_part=None):
    """Load the real XML, providing the exact decoded terrain through Python.

    Lua's UTF-8 bridge cannot marshal arbitrary compressed bytes. The opaque
    DecodeBase64 result crosses as hex; DecompressString reverses that conduit.
    The resulting data consumed by the unmodified Lua engine is byte-exact.
    """
    g, lua = host.g, host.lua
    g.ACCESS_DECODE = lambda value: base64.b64decode(value).hex()
    g.ACCESS_INFLATE = lambda value: zlib.decompress(bytes.fromhex(value)).decode("ascii")
    lua.execute(r'''
        C_EncodingUtil={
          DecodeBase64=function(s) return ACCESS_DECODE(s) end,
          DecompressString=function(s) return ACCESS_INFLATE(s) end}
        Enum.CompressionMethod={Zlib=0}
        ACCESS_CALLBACKS={}
        C_Timer=C_Timer or {}
        function C_Timer.After(_,fn) ACCESS_CALLBACKS[#ACCESS_CALLBACKS+1]=fn end
        function AccessPump()
          local fn=table.remove(ACCESS_CALLBACKS,1)
          if not fn then return false end
          fn();return true
        end
    ''')
    load = lua.eval('function(s,ns) assert(loadstring(s))("RutaXP",ns) end')

    def visit(path):
        if path.name == missing_part:
            return
        if path.suffix == ".xml":
            for node in ET.parse(path).getroot():
                if node.tag.rsplit("}", 1)[-1] in ("Script", "Include"):
                    visit(path.parent / node.attrib["file"].replace("\\", "/"))
        else:
            load(path.read_text(encoding="utf-8-sig"), host.ns)

    visit(ADDON / "Pathing" / "Pathing.xml")
    return g.RutaXPPathEngine


class AccessHost:
    def __init__(self, guide_id=HUMAN, step=24, goal_index=1, x=.1, y=.1, terrain=False, *, find_goal=None):
        self.h = full.TalentTrainerHost(full_toc=True)
        self.h.lua.execute(DUO_STUBS)
        self.ns, self.s = self.h.ns, self.h.state
        self.h.g.ACCESS_NS = self.ns
        self.h.lua.execute(WORLD_STUBS)
        self.s.members, self.s.level, self.s.height = 0, 10, 410
        self.s.x, self.s.y = x, y
        self.s.faction, self.s.raceToken = ("Horde", "Orc") if guide_id == ORC else ("Alliance", "Dwarf" if guide_id == DWARF else "Human")
        self.s.classToken = "WARRIOR"
        self.guide = self.ns.guides[guide_id]
        if find_goal:
            matches = [(si, gi) for si, visit in self.guide.steps.items() for gi, goal in visit.goals.items()
                       if all(goal[k] == v for k, v in find_goal.items())]
            if len(matches) != 1:
                raise AssertionError(f"Expected one {find_goal} in {guide_id}, got {matches}")
            step, goal_index = matches[0]
        self.step_index = step
        self.step = self.guide.steps[step]
        self.goal = self.step.goals[goal_index]
        self.s.mapID = self.goal.map
        self.s.quests[self.goal.quest] = self.h.table({"onQuest": self.goal.t != "accept", "complete": False,
            "objectives": [{"text": "Progreso observado", "numFulfilled": 0, "numRequired": 1, "finished": False}]})
        self.s.entries = self.h.table([{"questID": self.goal.quest, "isHeader": False}])
        marks = {f"{step}:{i}": True for i in range(1, goal_index)}
        marks["user-confirmed"] = True
        self.h.g.RutaXPCharDB = self.h.table({"seen": True, "activeGuide": guide_id, "auto": False,
            "duo": {"enabled": False, "autoPair": False}, "progress": {guide_id: {
                "cursor": step, "routeRevision": self.guide.routeRevision, "placed": True, "review": True,
                "confirmed": marks, "skipped": {"user-skipped": True}}}})
        self.engine = load_pathing(self.h) if terrain else None
        self.h.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        self.h.g.EmitAddonEvent("PLAYER_LOGIN")
        self.ns.char.progress[guide_id].review = False

    def point(self):
        return self.ns.GetStepWaypoint(self.ns, self.step)

    def progress(self):
        return primitive_copy(self.ns.char.progress)

    def waypoint_control(self, method):
        return self.ns.Waypoints[method](self.ns.Waypoints)

    def pump(self, limit=10000):
        for _ in range(limit):
            if not self.h.g.AccessPump():
                return
        raise AssertionError("Terrain search did not finish within its frame budget")


class AuthoredAccessIntegrationTests(unittest.TestCase):
    def test_distant_real_fargodeep_goal_keeps_its_access_instead_of_the_final_target(self):
        h = AccessHost(x=.1, y=.1)
        before = h.progress()
        point = h.point()
        self.assertTrue(point.intermediate)
        self.assertEqual(point.routeID, "fargodeep")
        self.assertGreater(h.ns.GetWaypointVector(h.ns, point)[0], 1800)
        self.assertEqual(h.progress(), before)

    def test_outdoor_den_npc_does_not_bypass_access_just_because_it_is_nearer_in_xy(self):
        h = AccessHost(ORC, 2, 2, x=.4206, y=.6800)
        before = h.progress()
        direct = h.ns.GetGoalWaypoint(h.ns, h.goal)
        point = h.point()
        self.assertTrue(point.intermediate)
        self.assertEqual(point.routeID, "den")
        self.assertLess(h.ns.GetWaypointVector(h.ns, direct)[0], h.ns.GetWaypointVector(h.ns, point)[0])
        h.waypoint_control("Skip")
        final = h.point()
        self.assertFalse(bool(final.intermediate))
        self.assertAlmostEqual(final.x, h.goal.x / 100)
        self.assertEqual(h.progress(), before)
        self.assertFalse(h.s.quests[788].onQuest)

    def test_temporarily_unreadable_position_does_not_permanently_remove_access(self):
        h = AccessHost(x=.4, y=.7)
        h.s.positionUnavailable = True
        h.point()
        h.s.positionUnavailable = False
        point = h.point()
        self.assertTrue(point.intermediate)
        self.assertEqual(point.routeID, "fargodeep")

    def test_fargodeep_confirmation_changes_navigation_only_and_releases_quest_target(self):
        h = AccessHost(x=.4, y=.7)
        before = h.progress()
        point = h.point()
        self.assertEqual(point.routeID, "fargodeep")
        h.s.x, h.s.y = point.x, point.y
        for _ in range(3):
            self.assertTrue(h.point().intermediate)
        h.waypoint_control("Skip")
        self.assertFalse(bool(h.point().intermediate))
        self.assertEqual(h.progress(), before)
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 62))

    def test_real_jasperlode_source_gate_is_not_imposed_again_on_the_next_step(self):
        h = AccessHost(HUMAN, x=.616, y=.541, find_goal={"t": "complete", "quest": 76})
        entrance = h.guide.steps[h.step_index - 1].goals[1]
        self.assertEqual((entrance.t, entrance.map, entrance.x, entrance.y), ("goto", 1429, 61.6, 54.1))
        before = h.progress()
        self.assertFalse(bool(h.point().intermediate))
        status = h.waypoint_control("GetStatus")
        self.assertEqual(status.routeID, "jasperlode")
        self.assertIn("ya pasó", status.reason)
        self.assertEqual(h.progress(), before)

    def test_helper_uses_the_remote_steps_access_without_changing_the_advanced_cursor(self):
        h = AccessHost(HUMAN, 34, x=.1, y=.1)
        before = h.progress()
        shared_step = h.guide.steps[24]
        follow = h.ns.GetGoalWaypoint(h.ns, shared_step.goals[1])
        follow.source, follow.duoFollow = "duo-follow", True
        follow.guideID, follow.sharedCursor, follow.goalIndex = HUMAN, 24, 1
        h.h.g.ACCESS_FOLLOW = follow
        h.h.g.ACCESS_VIEW = h.h.table({"following": True, "guideID": HUMAN,
                                      "sharedCursor": 24, "ownCursor": 34})
        h.h.g.ACCESS_VIEW.guide, h.h.g.ACCESS_VIEW.step = h.guide, shared_step
        h.ns.DuoAuto.GetSharedView = h.h.lua.eval("function() return ACCESS_VIEW end")
        h.ns.DuoAuto.GetNavigationOverride = h.h.lua.eval("function() return ACCESS_FOLLOW end")
        point = h.point()
        self.assertTrue(point.intermediate)
        self.assertEqual(point.routeID, "fargodeep")
        self.assertTrue(h.waypoint_control("GetStatus").external)
        self.assertFalse(h.waypoint_control("IsRouting"))
        h.waypoint_control("Skip")
        self.assertFalse(bool(h.point().intermediate))
        self.assertEqual(h.point().source, "duo-follow")
        self.assertEqual(h.progress(), before)
        self.assertEqual(h.ns.char.progress[HUMAN].cursor, 34)

        # Stale peer data must not reveal the advanced player's future pin.
        h.h.g.ACCESS_FOLLOW = None
        self.assertIsNone(h.point())
        self.assertEqual(h.progress(), before)


class RealTerrainEngineTests(unittest.TestCase):
    def test_gozwin_async_search_uses_real_mesh_and_bends_around_the_slope(self):
        h = full.TalentTrainerHost(full_toc=True)
        path = load_pathing(h)
        self.assertTrue(path.Available(0))
        bounds = h.ns.mapFrames.era[1426]

        def world(x, y):
            return h.table({"x": bounds.top + (bounds.bottom - bounds.top) * y / 100,
                            "y": bounds.left + (bounds.right - bounds.left) * x / 100})

        start, target = world(31.2, 67.9), world(27.27, 62.86)
        result = []
        path.Find(0, start, target, lambda points, cost, job: result.append((points, cost)))
        self.assertEqual(result, [], "The engine must leave the search to later frames")
        for _ in range(10000):
            if not h.g.AccessPump():
                break
        else:
            self.fail("Terrain search did not complete")
        self.assertEqual(len(result), 1)
        points, cost = result[0]
        self.assertGreater(len(points), 2)
        direct = math.hypot(target.x - start.x, target.y - start.y)
        self.assertGreater(cost, direct * 1.4)
        # A line to the object intersects the slope. The published collision
        # grid must produce a material detour, rather than merely subdividing it.
        max_deviation = max(abs((target.y - start.y) * (p.x - start.x)
            - (target.x - start.x) * (p.y - start.y)) / direct
            for key, p in points.items() if isinstance(key, int))
        self.assertGreater(max_deviation, 75)
        self.assertAlmostEqual(points[1].x, start.x)
        self.assertAlmostEqual(points[len(points)].y, target.y)

    def test_missing_mesh_part_and_unavailable_continent_report_no_data(self):
        h = full.TalentTrainerHost(full_toc=True)
        path = load_pathing(h, missing_part="Nav0_1.lua")
        self.assertFalse(path.Available(0))
        self.assertFalse(path.Available(99999))
        result = []
        path.Find(0, h.table({"x": -6106, "y": 265}), h.table({"x": -5941, "y": 459}),
                  lambda points, reason, job: result.append((points, reason)))
        for _ in range(100):
            if not h.g.AccessPump():
                break
        self.assertEqual(result, [(None, "nodata")])


class WalkingIntegrationTests(unittest.TestCase):
    def test_real_gozwin_route_steers_the_arrow_while_map_pin_and_quests_keep_the_semantic_target(self):
        h = AccessHost(DWARF, 13, 2, x=.312, y=.679, terrain=True)
        before = h.progress()
        semantic = h.point()
        w = h.ns.Walking
        pending = h.ns.GetArrowWaypoint(h.ns, h.step)
        self.assertTrue(pending.navigationBlocked)
        self.assertEqual(w.GetStatus(w).phase, "pending")
        h.ns.UpdateNavigation(h.ns)
        self.assertFalse(h.ns.navigationFrame.arrow.shown)
        self.assertIn("Calculando", h.ns.navigationFrame.distance.text)
        h.pump()
        arrow = h.ns.GetArrowWaypoint(h.ns, h.step)
        self.assertTrue(arrow.walking)
        self.assertGreater(arrow.walkingCount, 2)
        self.assertFalse(arrow.walkingFinal)
        self.assertGreater(arrow.walkingDistance, h.ns.GetWaypointVector(h.ns, semantic)[0] * 1.4)
        self.assertGreater(math.hypot(arrow.x - semantic.x, arrow.y - semantic.y), .001)
        self.assertTrue(h.ns.Navigate(h.ns))
        self.assertAlmostEqual(h.s.lastWaypoint.x, semantic.x)
        self.assertAlmostEqual(h.s.lastWaypoint.y, semantic.y)
        h.ns.UpdateNavigation(h.ns)
        self.assertTrue(h.ns.navigationFrame.arrow.shown)
        self.assertIn("Camino por terreno", h.ns.navigationFrame.destination.text)
        self.assertFalse(h.ns.navigationFrame.arrived)
        h.s.x, h.s.y, h.s.height = arrow.x, arrow.y, arrow.z
        self.assertFalse(h.ns.IsAtWaypoint(h.ns, h.goal))
        self.assertEqual(h.progress(), before)
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 97277))

    def test_changed_semantic_target_cancels_search_and_rejects_a_late_old_callback(self):
        h = AccessHost(DWARF, 13, 2, x=.312, y=.679, terrain=True)
        before = h.progress()
        w = h.ns.Walking
        first = h.point()
        w.Resolve(w, first)
        old_job = w.job
        second = h.ns.GetGoalWaypoint(h.ns, h.step.goals[3])
        w.Resolve(w, second)
        self.assertTrue(old_job.cancelled)
        h.pump()
        arrow = w.Resolve(w, second)
        self.assertTrue(arrow.walking)
        expected_points = primitive_copy(w.points)
        old_job.callback(h.h.table([{"map": 0, "x": -6000, "y": 100},
                                  {"map": 0, "x": -6001, "y": 101}]), 5)
        self.assertEqual(primitive_copy(w.points), expected_points)
        self.assertEqual(arrow.walkingGoal.goal.t, "kill")
        self.assertEqual(h.progress(), before)

    def test_missing_terrain_and_disabled_routing_explain_the_direct_direction(self):
        h = AccessHost(DWARF, 13, 2, x=.312, y=.679)
        before = h.progress()
        semantic = h.point()
        w = h.ns.Walking
        fallback = w.Resolve(w, semantic)
        self.assertEqual((fallback.x, fallback.y), (semantic.x, semantic.y))
        self.assertEqual(w.GetStatus(w).phase, "unavailable")
        self.assertIn("orientativa", fallback.navigationNotice)
        self.assertFalse(bool(fallback.walking))
        h.ns.char.walking.enabled = False
        disabled = w.Resolve(w, semantic)
        self.assertEqual(w.GetStatus(w).phase, "disabled")
        self.assertIn("desactivado", disabled.navigationNotice)
        self.assertFalse(bool(disabled.navigationBlocked))
        self.assertEqual(h.progress(), before)

    def test_leaving_the_current_segment_recalculates_before_showing_another_direction(self):
        h = AccessHost(DWARF, 13, 2, x=.312, y=.679, terrain=True)
        before = h.progress()
        h.ns.GetArrowWaypoint(h.ns, h.step)
        h.pump()
        self.assertTrue(h.ns.GetArrowWaypoint(h.ns, h.step).walking)
        h.h.g.ACCESS_PATH = h.engine
        h.h.lua.execute('''
            local find=ACCESS_PATH.Find
            ACCESS_PATH.Find=function(...)
              TEST.replans=(TEST.replans or 0)+1;return find(...)
            end
        ''')
        h.s.now += 3
        h.s.x, h.s.y = h.s.x + .02, h.s.y - .02
        h.ns.UpdateNavigation(h.ns)
        self.assertEqual(h.s.replans, 1)
        self.assertEqual(h.ns.Walking.GetStatus(h.ns.Walking).phase, "pending")
        self.assertFalse(h.ns.navigationFrame.arrow.shown)
        self.assertIsNotNone(h.ns.Walking.job)
        self.assertEqual(h.progress(), before)

    def test_unreachable_async_answer_blocks_the_arrow_instead_of_using_a_direct_line(self):
        h = AccessHost(DWARF, 13, 2, x=.312, y=.679, terrain=True)
        before = h.progress()
        h.ns.Walking.Clear(h.ns.Walking)
        h.h.g.ACCESS_PATH = h.engine
        h.h.lua.execute('''
            ACCESS_PATH.Find=function(map,from,to,callback)
              C_Timer.After(0,function() callback(nil,"unreachable") end)
              return {}
            end
        ''')
        h.ns.UpdateNavigation(h.ns)
        h.pump()
        h.ns.UpdateNavigation(h.ns)
        point = h.ns.GetArrowWaypoint(h.ns, h.step)
        self.assertTrue(point.navigationBlocked)
        self.assertFalse(bool(point.walking))
        self.assertEqual(h.ns.Walking.GetStatus(h.ns.Walking).phase, "failed")
        self.assertFalse(h.ns.navigationFrame.arrow.shown)
        self.assertIn("No hay un camino comprobado", h.ns.navigationFrame.distance.text)
        self.assertEqual(h.progress(), before)


if __name__ == "__main__":
    unittest.main()
