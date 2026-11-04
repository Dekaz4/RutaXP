"""Resolved visits show why they wait; ready turn-ins retain the real NPC."""

import unittest

from test_access_navigation import AccessHost, DWARF


class TurninNavigationTests(unittest.TestCase):
    def done_visit(self):
        h = AccessHost(DWARF, step=6, x=.26, y=.71)
        h.s.height = 385
        h.s.friendRace, h.s.friendClass, h.s.members = "Dwarf", "WARRIOR", 2
        h.s.quests[233] = h.h.table({"delivered": True})
        h.s.quests[183] = h.h.table({"onQuest": True})
        h.s.quests[234] = h.h.table({"onQuest": True})
        h.ns.char.auto, h.ns.char.duo.wait, h.ns.char.duo.autoPair = True, True, False
        h.ns.Duo.SetEnabled(h.ns.Duo, True)
        self.assertTrue(h.ns.Duo.Receive(h.ns.Duo, h.ns.Duo.prefix,
            "2|H|friend|1|10|WARRIOR|Dwarf|" + DWARF + "|6|0|Alliance", "PARTY", "Dos-Forever"))
        return h

    def test_real_dun_morogh6_all_three_goals_done_shows_the_actual_duo_wait_reason(self):
        h = self.done_visit()
        before = h.progress()
        self.assertIsNone(h.ns.GetActiveGoal(h.ns, h.step))
        for index, goal in h.step.goals.items():
            self.assertEqual(h.ns.GetGoalStatus(h.ns, goal, h.step, h.ns.char.progress[DWARF], index)[0], "done")
        waiting, reason = h.ns.Duo.ShouldWaitForStep(h.ns.Duo, h.step)
        self.assertTrue(waiting)
        self.assertIsNone(h.point())  # No remaining local action should resurrect an old NPC pin.
        h.ns.UpdateNavigation(h.ns)
        frame = h.ns.navigationFrame
        self.assertEqual(frame.navigationState, "waiting")
        self.assertIn("Sincronizando misiones", frame.distance.text)
        self.assertNotIn(reason, frame.distance.text)
        self.assertEqual(frame.navigationReason, reason)
        self.assertNotIn("Sin coordenadas", frame.distance.text)
        self.assertFalse(frame.arrow.shown)
        self.assertEqual(h.ns.char.progress[DWARF].cursor, 6)
        self.assertEqual(h.progress(), before)

    def test_wait_explanation_is_in_the_arrow_tooltip_and_sync_state_has_a_short_label(self):
        h = self.done_visit()
        h.h.lua.execute('''
            GameTooltip={lines={}}
            function GameTooltip:SetOwner() self.lines={} end
            function GameTooltip:SetText(text) self.lines[#self.lines+1]=text end
            function GameTooltip:AddLine(text) self.lines[#self.lines+1]=text end
            function GameTooltip:Show() self.shown=true end
            function GameTooltip:Hide() self.shown=false end
        ''')
        before = h.progress()
        h.ns.UpdateNavigation(h.ns)
        frame = h.ns.navigationFrame
        reason = frame.navigationReason
        frame.scripts.OnEnter(frame)
        tooltip = "\n".join(h.h.g.GameTooltip.lines.values())
        self.assertIn(reason, tooltip)
        self.assertIn("Arrastra", tooltip)
        self.assertNotIn(reason, frame.distance.text)
        frame.scripts.OnLeave(frame)
        self.assertFalse(h.h.g.GameTooltip.shown)
        h.ns.Duo.ClearPeer(h.ns.Duo)
        h.ns.UpdateNavigation(h.ns)
        self.assertIn("Sincronizando misiones", frame.distance.text)
        self.assertIn("Sin sincronización", frame.navigationReason)
        self.assertNotIn("desactiva", frame.distance.text)
        self.assertEqual(h.progress(), before)

    def test_resolved_visit_distinguishes_manual_review_manual_advance_and_completion(self):
        h = self.done_visit()
        h.ns.Duo.SetEnabled(h.ns.Duo, False)
        state = h.ns.char.progress[DWARF]
        state.cursor, state.review = 6, True
        h.ns.char.auto = True
        h.ns.UpdateNavigation(h.ns)
        self.assertEqual(h.ns.navigationFrame.navigationState, "review")
        self.assertIn("revisión", h.ns.navigationFrame.distance.text)
        state.review, h.ns.char.auto = False, False
        h.ns.UpdateNavigation(h.ns)
        self.assertEqual(h.ns.navigationFrame.navigationState, "manual")
        self.assertIn("Siguiente", h.ns.navigationFrame.distance.text)
        h.ns.char.auto = True
        before = h.progress()
        h.ns.UpdateNavigation(h.ns)
        self.assertEqual(h.ns.navigationFrame.navigationState, "complete")
        self.assertIn("Paso completado", h.ns.navigationFrame.distance.text)
        self.assertEqual(h.progress(), before)  # Rendering must never call Sync.

    def test_recovery_meeting_and_follow_destinations_survive_an_all_done_local_visit(self):
        for source in ("recovery", "duo-meeting", "duo-follow"):
            with self.subTest(source=source):
                h = self.done_visit()
                h.h.g.TEST_OVERRIDE = h.h.table({"mapID": 1426, "x": .25, "y": .70, "source": source})
                getter = h.h.lua.eval("function() return TEST_OVERRIDE end")
                if source == "recovery":
                    h.ns.Recovery.GetNavigationOverride = getter
                elif source == "duo-meeting":
                    h.ns.Duo.GetMeetingWaypoint = getter
                else:
                    h.h.g.TEST_VIEW = h.h.table({"following": True, "guideID": DWARF, "sharedCursor": 1})
                    h.ns.DuoAuto.GetSharedView = h.h.lua.eval("function() return TEST_VIEW end")
                    h.ns.DuoAuto.GetNavigationOverride = getter
                before = h.progress()
                self.assertEqual(h.point().source, source)
                h.ns.UpdateNavigation(h.ns)
                self.assertTrue(h.ns.navigationFrame.arrow.shown)
                self.assertNotEqual(h.ns.navigationFrame.navigationState, "waiting")
                self.assertEqual(h.progress(), before)

    def test_ready183_turnin_retains_talin_coordinates_when_live_waypoint_is_absent(self):
        h = AccessHost(DWARF, step=8, x=.26, y=.71)
        h.s.quests[183] = h.h.table({"onQuest": True, "complete": True,
            "objectives": [{"finished": True, "numFulfilled": 12, "numRequired": 12}]})
        before = h.progress()
        point = h.point()
        self.assertIsNotNone(point)
        self.assertEqual((point.goal.quest, point.goal.npc), (183, 714))
        self.assertAlmostEqual(point.x, .226)
        self.assertAlmostEqual(point.y, .7143)
        self.assertEqual(point.z, 385)
        self.assertEqual(point.source, "guide")
        self.assertEqual(h.progress(), before)

    def test_ready183_turnin_can_compute_a_real_terrain_route_to_talin(self):
        # Grelin's authored position/altitude is a known origin in this valley.
        h = AccessHost(DWARF, step=8, x=.2508, y=.7571, terrain=True)
        h.s.height = 385.9
        h.s.quests[183] = h.h.table({"onQuest": True, "complete": True,
            "objectives": [{"finished": True, "numFulfilled": 12, "numRequired": 12}]})
        before = h.progress()
        walking = h.ns.Walking
        walking.Clear(walking)  # Discard the fixture's login query at its generic height 410.
        walking.Resolve(walking, h.point())
        h.pump()
        arrow = walking.Resolve(walking, h.point())
        self.assertTrue(arrow.walking, walking.GetStatus(walking).text)
        self.assertEqual(arrow.walkingGoal.goal.npc, 714)
        self.assertGreater(arrow.walkingCount, 1)
        self.assertEqual(h.progress(), before)


if __name__ == "__main__":
    unittest.main()
