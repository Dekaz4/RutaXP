"""Corpse recovery temporarily owns both compasses and cannot prove guide travel."""
import unittest

from lupa.lua51 import LuaRuntime

import test_guide_journey as journey
import test_quest_engine as engine


class CorpseNavigationTests(unittest.TestCase):
    def setUp(self):
        engine.NavigationAndFullTocTests.setUp(self)
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, .41, .62
        h.lua.execute("""
            function UnitIsGhost() return TEST.ghost end
            function UnitIsDeadOrGhost() return TEST.dead or TEST.ghost end
            function GetTime() return TEST.now or 0 end
            local create=CreateFrame
            function CreateFrame(...) local f=create(...); TEST.lastFrame=f; return f end
        """)
        h.load((engine.ADDON / "CorpseNavigation.lua").read_text(encoding="utf8"), "RutaXP", h.ns)
        self.events = h.state.lastFrame
        h.guide("corpse-test", steps=[{"title": "Viaje", "goals": [
            {"t": "goto", "map": 1436, "x": 20, "y": 24}]}])
        h.initialize()
        h.call("SelectGuide", "corpse-test")

    def event(self, name):
        self.events.scripts.OnEvent(self.events, name)

    def test_release_detour_replacement_and_resurrection_do_not_advance_travel(self):
        h = self.host
        _, step, state = h.call("GetCurrent")
        h.state.dead = True
        self.event("PLAYER_DEAD")
        h.call("UpdateNavigation")
        nav = h.ns.navigationFrame
        self.assertFalse(nav.arrow.shown)
        self.assertIn("Libera el espíritu", nav.hint.text)
        h.state.ghost, h.state.x, h.state.y = True, .2, .24
        self.event("PLAYER_ALIVE")
        h.ns.DungeonPlanner = h.lua.eval("""{IsDetouring=function() return true end,
            RoutePoint=function() error("ghost incorrectly evaluated the detour") end}""")
        h.call("UpdateNavigation")
        self.assertTrue(nav.arrow.shown)
        self.assertEqual(nav.hint.text, "Tu cadáver")
        self.assertEqual(nav.destinationText, "Tu cadáver")
        self.assertTrue(nav.distance.text)
        body = h.call("GetArrowWaypoint", step, False)
        self.assertEqual((body.source, body.x, body.y), ("corpse", .41, .62))
        self.assertFalse(h.call("IsAtWaypoint", step.goals[1]))
        h.call("OnNavigationTick")
        self.assertEqual(state.cursor, 1)
        h.ns.DungeonPlanner = None
        h.state.ghost, h.state.dead = False, False
        self.event("PLAYER_UNGHOST")
        h.state.x, h.state.y = .41, .62
        h.call("UpdateNavigation")
        normal = h.call("GetArrowWaypoint", step, False)
        self.assertAlmostEqual(normal.x, .2)
        self.assertNotIn("cadáver", nav.hint.text)

    def test_ghost_login_retries_missing_pin_queries_parent_and_resets_on_new_death(self):
        h = self.host
        h.state.ghost = True
        h.lua.execute("""
            TEST.requests=0
            function C_Map.GetMapInfo(map) return {parentMapID=map==1436 and 1415 or 0} end
            C_DeathInfo={GetCorpseMapPosition=function(map)
                TEST.requests=TEST.requests+1
                if map==1415 and TEST.bodyAvailable then return CreateVector2D(.67,.36) end
                return CreateVector2D(0,0)
            end}
        """)
        self.event("PLAYER_ENTERING_WORLD")
        h.call("UpdateNavigation")
        self.assertIn("Esperando la ubicación", h.ns.navigationFrame.hint.text)
        self.assertFalse(h.ns.navigationFrame.arrow.shown)
        requests = h.state.requests
        h.state.bodyAvailable = True
        h.call("UpdateNavigation")
        self.assertEqual(h.state.requests, requests)
        h.state.now = 2
        point, label = h.call("GetDeathNavigation")
        self.assertEqual((point.mapID, point.x, point.y, label), (1415, .67, .36, "Tu cadáver"))
        h.state.ghost = False
        self.event("PLAYER_UNGHOST")
        h.state.dead, h.state.positionUnavailable = True, True
        self.event("PLAYER_DEAD")
        h.state.ghost, h.state.bodyAvailable = True, False
        point, label = h.call("GetDeathNavigation")
        self.assertIsNone(point)
        self.assertIn("Esperando", label)


@unittest.skipUnless((journey.NATIVE / "Journey.toc").is_file(), "the owner's Journey copy is required")
class JourneyCorpseTests(unittest.TestCase):
    def test_native_hud_tracks_exact_game_pin_through_zone_journal_and_resurrection(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(journey.MOCK)
        lua.execute("""
            function UnitIsGhost() return ghost end
            function UnitIsDeadOrGhost() return dead or ghost end
            function C_Map.GetBestMapForUnit() return 1434 end
            C_DeathInfo={GetCorpseMapPosition=function() return CreateVector2D(.12,.56) end}
        """)
        for name in ["CorpseNavigation.lua", "GuideJourney.lua"]:
            lua.execute((journey.ROOT / "RutaXP" / name).read_text(encoding="utf8"), "RutaXP", lua.globals().ns)
        for filename, data in journey.suite_journey.contents(journey.NATIVE):
            if filename.endswith(".lua"):
                lua.execute(data, "RutaXP", lua.globals().ns)
        lua.execute("""
            event("PLAYER_LOGIN"); tick()
            local hud=RutaXPJourneyScreenArrow
            assert(hud.label.text=="Villadorada")
            dead=true; event("PLAYER_DEAD"); tick()
            assert(not hud.container:IsShown())
            -- Even with no selected guide, the character still has a corpse.
            status="pending"; ghost=true; event("PLAYER_ALIVE"); tick()
            assert(hud.label.text=="Tu cadáver" and hud.container:IsShown())
            local dx,dy=.12*1300-500,.56*1300-500
            assert(hud.distLabel:GetText()==RutaXPJourneyEnvironment().FormatJourneyDistance(math.sqrt(dx*dx+dy*dy)))
            status=nil; ghost=false; dead=false; event("PLAYER_UNGHOST"); tick()
            assert(hud.container:IsShown() and hud.label.text=="Villadorada")
        """)
