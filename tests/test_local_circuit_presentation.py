"""A chosen stop must reach Journey, the map and the actual quest dialog together."""
import unittest

from test_access_navigation import ADDON, AccessHost
from test_guide_singing_shards import GUIDE


class LocalCircuitPresentationTests(unittest.TestCase):
    def real_client(self, x, y, height):
        h = AccessHost(GUIDE, find_goal={"quest": 191, "t": "kill"}, x=x, y=y)
        for name in ("CircuitCreatureData", "CircuitTerrain", "LocalCircuit"):
            h.h.lua.execute((ADDON / (name + ".lua")).read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.h.lua.execute("getmetatable(UIParent).__index.GetTexture = function(frame) return frame.texture end")
        h.h.lua.execute((ADDON / "GuideOriginal.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.ns.char.auto, h.s.level, h.s.height = True, 35, height
        return h

    def test_actual_tuercespina_partial_credit_is_used_by_journey_map_and_arrow(self):
        h = self.real_client(.266, .168, 48.8)
        h.ns.Walking.Toggle(h.ns.Walking, False)
        h.s.quests[194] = h.h.table({"onQuest": True, "complete": False, "objectives": [{
            "text": "Raptor de Tuercespina: 8/10", "numFulfilled": 8, "numRequired": 10, "finished": False,
        }]})
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        before = h.progress()
        h.ns.UpdateNavigation(h.ns)
        row = next(row for row in h.ns.OriginalGuidePresentation.Tasks().values() if row.isCurrent)
        self.assertEqual((row.questID, row.action), (194, "kill"))
        self.assertIn("8/10", row.text)
        self.assertIn("2 bajas", row.text)
        self.assertEqual(h.ns.OriginalGuidePresentation.Waypoint()[-1].goal.quest, 194)
        h.s.waypointAllowed = h.s.waypointSuccess = True
        self.assertTrue(h.ns.Navigate(h.ns))
        self.assertAlmostEqual(h.s.lastWaypoint.x, .266)
        h.s.quests[194].complete = True
        h.s.quests[194].objectives[1].finished = True
        h.s.now += 2
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        h.ns.UpdateNavigation(h.ns)
        self.assertEqual(h.point().goal.quest, 191)
        self.assertEqual(h.progress(), before)

    def test_two_ready_nesingwary_quests_before_the_authored_booty_bay_departure(self):
        h = self.real_client(.3565, .107, 11.2)
        state = h.ns.char.progress[GUIDE]
        state.cursor = 16
        for quest in (188, 195):
            h.s.quests[quest] = h.h.table({"onQuest": True, "complete": True})
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        before = h.progress()
        observed = []
        for _ in range(2):
            h.ns.UpdateNavigation(h.ns)
            _, current_step, _ = h.ns.GetCurrent(h.ns)
            point = h.ns.GetStepWaypoint(h.ns, current_step, None, h.h.table({}))
            self.assertIsNone(h.ns.OriginalGuidePresentation.Waypoint())
            row = next(row for row in h.ns.OriginalGuidePresentation.Tasks().values() if row.isCurrent)
            self.assertEqual((point.goal.quest, point.goal.t), (row.questID, "turnin"))
            self.assertIn(row.questID, (188, 195))
            observed.append(row.questID)
            h.s.quests[row.questID] = h.h.table({"delivered": True})
            h.h.g.EmitAddonEvent("QUEST_TURNED_IN", row.questID)
            h.s.now += 2
        h.ns.UpdateNavigation(h.ns)
        self.assertEqual(set(observed), {188, 195})
        self.assertIsNone(h.ns.GetLocalCircuitStop(h.ns))
        self.assertEqual(h.ns.GetActiveGoal(h.ns)[0].t, "getfp")
        self.assertEqual(h.progress(), before)

    def test_journey_without_compass_updates_on_movement_and_skips_stationary_ticks(self):
        h = self.real_client(.5, .5, 48.8)
        h.ns.char.tracker, h.ns.char.arrow = True, False
        h.ns.window.Hide(h.ns.window)
        h.s.quests[194] = h.h.table({"onQuest": True, "complete": False, "objectives": [{
            "text": "Raptor de Tuercespina: 8/10", "numFulfilled": 8, "numRequired": 10, "finished": False,
        }]})
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        h.h.lua.execute("""
            local choose = ACCESS_NS.LocalCircuit.Choose
            TEST.circuitSamples = 0
            function ACCESS_NS.LocalCircuit:Choose(...)
                TEST.circuitSamples = TEST.circuitSamples + 1
                return choose(self, ...)
            end
        """)
        h.ns.UpdateNavigation(h.ns)
        self.assertIsNone(h.ns.displayedCircuitStop)
        samples = h.s.circuitSamples
        for _ in range(30):
            h.s.now += .1
            h.ns.UpdateNavigation(h.ns)
        self.assertEqual(h.s.circuitSamples, samples)
        h.s.x, h.s.y = .266, .168
        h.s.now += 2
        h.ns.UpdateNavigation(h.ns)
        row = next(row for row in h.ns.OriginalGuidePresentation.Tasks().values() if row.isCurrent)
        self.assertEqual(row.questID, 194)
        self.assertIn("8/10", row.text)
        self.assertFalse(h.ns.navigationFrame.shown)
        self.assertIsNone(h.ns.OriginalGuidePresentation.Waypoint())

    def client(self):
        h = AccessHost(GUIDE, find_goal={"quest": 189, "t": "collect"}, x=.349, y=.11)
        h.s.level, h.ns.char.auto = 35, True
        h.s.quests[188] = h.h.table({"onQuest": True, "complete": True})
        h.h.lua.execute("""
            getmetatable(UIParent).__index.GetTexture = function(frame) return frame.texture end
            ACCESS_NS.LocalCircuit = {
                Choose = function(self, guide, step, state, base)
                    if TEST.deferred or not ACCESS_NS:IsQuestActive(188) or base.quest ~= 189 then return end
                    local visit = guide.steps[19]
                    local goal = visit.goals[2]
                    return {step=visit, goal=goal, stepIndex=19, index=2, key="turnin-188", reason="Entrega de camino.",
                        point=ACCESS_NS:GetGoalWaypoint(goal)}
                end,
                Defer = function(self, guide, state, stop) TEST.deferred=stop.key end,
            }
            function GetQuestID() return 188 end
            function IsQuestCompletable() return true end
            function CompleteQuest() TEST.handIn = true end
            function UnitGUID(unit)
                if unit=="npc" and TEST.contactID then return "Creature-0-1-2-3-"..TEST.contactID.."-A" end
            end
        """)
        h.h.lua.execute((ADDON / "GuideOriginal.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.ns.RefreshUI(h.ns)
        h.ns.UpdateNavigation(h.ns)
        return h

    def test_future_stop_and_verified_npc_dialog_preserve_the_active_chapter(self):
        h = self.client()
        before = h.progress()
        row = next(row for row in h.ns.OriginalGuidePresentation.Tasks().values() if row.isCurrent)
        self.assertEqual((row.questID, row.action), (188, "turnin"))
        self.assertIn("Entrega de camino", row.text)
        self.assertIn("Ajeck", row.text)
        point = h.ns.GetArrowWaypoint(h.ns, h.step)
        self.assertEqual((point.goal.quest, point.stepIndex, point.goalIndex), (188, 19, 2))
        self.assertTrue(point.navigationBlocked)
        self.assertIsNone(h.ns.OriginalGuidePresentation.Waypoint())
        self.assertAlmostEqual(h.point().x, .3562)
        self.assertEqual(h.ns.GetStepWaypoint(h.ns, h.step, None, h.h.table({"index": 1})).goal.quest, 189)
        h.s.contactID = 715
        h.ns.HandleQuestAutomation(h.ns, "QUEST_PROGRESS")
        self.assertIsNone(h.s.handIn)
        h.s.contactID = 717
        h.ns.HandleQuestAutomation(h.ns, "QUEST_PROGRESS")
        self.assertTrue(h.s.handIn)
        self.assertEqual(h.progress(), before)
        h.s.quests[188] = h.h.table({"delivered": True})
        h.h.g.EmitAddonEvent("QUEST_TURNED_IN", 188)
        self.assertEqual(h.point().goal.quest, 189)
        self.assertEqual(h.progress(), before)

    def test_dismissing_only_the_visible_stop_keeps_every_authored_objective(self):
        h = self.client()
        before = h.progress()
        self.assertEqual(h.ns.trackerNext.label.text, "Seguir el paso")
        self.assertFalse(h.ns.trackerSkip.enabled)
        self.assertFalse(h.ns.DeferLocalCircuitStop(h.ns, "an-older-stop"))
        h.h.g.Click(h.ns.trackerNext)
        self.assertEqual(h.s.deferred, "turnin-188")
        self.assertEqual(h.point().goal.quest, 189)
        self.assertEqual(h.progress(), before)

    def test_review_death_and_dungeon_take_priority(self):
        h = self.client()
        state = h.ns.char.progress[GUIDE]
        state.review = True
        self.assertIsNone(h.ns.GetLocalCircuitStop(h.ns))
        state.review = False
        h.h.lua.execute('function UnitIsDeadOrGhost() return true end')
        self.assertIsNone(h.ns.GetLocalCircuitStop(h.ns))
        h.h.lua.execute('function UnitIsDeadOrGhost() return false end; ACCESS_NS.DungeonPlanner={IsDetouring=function() return true end}')
        self.assertIsNone(h.ns.GetLocalCircuitStop(h.ns))

    def test_shared_cursor_and_an_active_approach_keep_their_waypoints(self):
        h = self.client()
        h.h.lua.execute("""
            function ACCESS_NS.DuoAuto:GetSharedView() return {following=true,guideID=ACCESS_NS.char.activeGuide,sharedCursor=14} end
            function ACCESS_NS.DuoAuto:GetNavigationOverride() return {mapID=1434,x=.2,y=.5,source="duo-follow"} end
        """)
        self.assertIsNone(h.ns.GetLocalCircuitStop(h.ns))
        self.assertEqual(h.point().source, "duo-follow")
        h.h.lua.execute("""
            function ACCESS_NS.DuoAuto:GetSharedView() return nil end
            function ACCESS_NS.Waypoints:IsRouting() return true end
        """)
        self.assertIsNone(h.ns.GetLocalCircuitStop(h.ns))
        self.assertEqual(h.point().goal.quest, 189)

    def test_unconfirmed_access_reports_the_chosen_stop_and_position_refreshes_journey(self):
        h = self.client()
        h.h.lua.execute("function ACCESS_NS.Waypoints:ResolveTarget() return nil end")
        h.ns.UpdateNavigation(h.ns)
        frame = h.ns.navigationFrame
        self.assertFalse(frame.arrow.shown)
        self.assertIn("tigre", frame.destinationText.lower())
        self.assertEqual(h.ns.GetStepWaypoint(h.ns, h.step, None, h.h.table({})).goal.quest, 188)
        h.s.deferred = True
        h.ns.UpdateNavigation(h.ns)  # No quest event and no explicit RefreshUI.
        row = next(row for row in h.ns.OriginalGuidePresentation.Tasks().values() if row.isCurrent)
        self.assertEqual(row.questID, 189)


if __name__ == "__main__":
    unittest.main()
