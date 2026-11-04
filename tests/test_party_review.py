"""Independent integration regressions for shared navigation and unknown data."""

import unittest
from types import SimpleNamespace

from lupa.lua51 import LuaRuntime

import test_duo_planner as planner_fixture
import test_quest_engine as engine_fixture
from test_party_features_ui import PartyUIHost


def planner_host():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(planner_fixture.STUBS)
    loader = lua.execute("return function(...)\n" + (planner_fixture.ROOT / "RutaXP" / "DuoPlanner.lua").read_text(encoding="utf-8") + "\nend")
    loader("RutaXP", lua.globals().NS)
    return lua


class IndependentPartyReviewTests(unittest.TestCase):
    def test_unknown_local_counter_is_reported_when_partner_counter_is_known(self):
        lua = planner_host()
        lua.execute('''
            Both(101,1,1)
            TEST.objectives[101] = nil
            TEST.partner[101].objectives = {[1]={known=true,current=2,total=5,finished=false}}
            local entries = NS.DuoPlanner:GetDifferences()
            assert(#entries == 1, "A missing local objective sample must be visible as unknown")
            assert(entries[1].kind == "unknown" and entries[1].owner == "mine")
            assert(not entries[1].action)
        ''')

    def test_recovery_navigation_is_not_masked_by_an_earlier_pickup_focus(self):
        lua = planner_host()
        lua.execute('''
            Both(101,0,1)
            assert(NS.DuoPlanner:FocusDifference(1))
            assert(NS.DuoPlanner:GetNavigationOverride())
            NS.char.recovery = {active=true}
            NS.char.activeGuide = "_recovery"
            NS.guides._recovery = {id="_recovery",recovery=true,steps={{title="Actual prerequisite"}}}
            NS.char.progress._recovery = {cursor=1,confirmed={}}
            assert(NS.DuoPlanner:GetNavigationOverride() == nil,
                "An old pickup focus must not replace the active prerequisite recovery destination")
        ''')

    def test_followed_meeting_remains_navigable_after_guide_is_complete(self):
        h = PartyUIHost()
        progress = h.ns.char.progress["party-route"]
        progress.cursor, progress.review = 4, True
        before = h.h.lua.eval("function(ns) return ns.char.progress['party-route'].cursor end")(h.ns)
        self.assertTrue(h.ns.Duo.SetMeetingPoint(h.ns.Duo)[0])
        self.assertTrue(h.ns.Duo.FollowMeeting(h.ns.Duo, True)[0])
        self.assertIsNotNone(h.ns.Duo.GetMeetingWaypoint(h.ns.Duo))
        h.ns.UpdateNavigation(h.ns)
        self.assertTrue(h.ns.navigationFrame.shown, "A valid meeting has a destination even with no remaining guide step")
        self.assertEqual(progress.cursor, before)

    def navigation_host(self):
        fixture = SimpleNamespace()
        engine_fixture.NavigationAndFullTocTests.setUp(fixture)
        h = fixture.host
        h.state.mapID, h.state.x, h.state.y = 1436, .5, .5
        h.guide("navigation", steps=[{"title": "Real route destination", "goals": [
            {"t": "goto", "map": 1436, "x": 80, "y": 80, "f": "e"},
        ]}])
        h.initialize()
        h.globals.NS = h.ns
        h.lua.execute('''
            TEST.meeting = {mapID=1436,x=.5,y=.5,source="duo-meeting",label="Meeting"}
            TEST.focus = {mapID=1436,x=.6,y=.6,source="duo-difference",label="Pickup"}
            TEST.intermediate = {mapID=1436,x=.7,y=.7,source="itinerary"}
            NS.Recovery = {GetNavigationOverride=function() return TEST.recovery end}
            NS.Duo = {GetMeetingWaypoint=function() return TEST.meeting end}
            NS.DuoPlanner = {GetNavigationOverride=function() return TEST.focus end}
            NS.Waypoints = {Resolve=function() return TEST.intermediate end}
        ''')
        return h

    def test_navigation_override_priority_and_quest_arrival_stay_separate(self):
        h = self.navigation_host()
        _, step, state = h.call("GetCurrent")
        goal = step.goals[1]
        self.assertEqual(h.call("GetStepWaypoint", step).source, "duo-meeting")
        self.assertFalse(h.call("IsAtWaypoint", goal))
        self.assertFalse(h.call("IsStepComplete", step))
        self.assertEqual(state.cursor, 1)
        h.state.meeting = None
        self.assertEqual(h.call("GetStepWaypoint", step).source, "duo-difference")
        self.assertFalse(h.call("IsAtWaypoint", goal))
        h.state.focus = None
        self.assertEqual(h.call("GetStepWaypoint", step).source, "itinerary")
        h.state.recovery = h.table({"mapID": 1436, "x": .4, "y": .4, "source": "recovery"})
        self.assertEqual(h.call("GetStepWaypoint", step).source, "recovery")
        self.assertEqual(state.cursor, 1)
        h.state.x, h.state.y = .8, .8
        self.assertTrue(h.call("IsAtWaypoint", goal))
        self.assertEqual(state.cursor, 1)

    def test_no_active_guide_can_still_show_and_mark_a_followed_meeting(self):
        h = self.navigation_host()
        h.ns.char.activeGuide = None
        self.assertEqual(h.call("GetStepWaypoint", None).source, "duo-meeting")
        h.call("UpdateNavigation")
        self.assertTrue(h.ns.navigationFrame.shown)
        self.assertTrue(h.call("Navigate"))
        self.assertEqual(h.state.lastWaypoint.mapID, 1436)
        self.assertAlmostEqual(h.state.lastWaypoint.x, .5)
        self.assertIsNone(h.ns.char.activeGuide)


if __name__ == "__main__":
    unittest.main()
