"""A local excursion changes the displayed target, preserving the actual departure."""
import unittest

from test_boat_navigation import BoatHost, GUIDE
from test_duo_journey import primitive_copy


class TravelChoiceUITests(unittest.TestCase):
    def journal(self, h, *ids):
        h.s.entries = h.h.table([{"questID": q, "isHeader": False} for q in ids])
        for q in ids:
            h.s.quests[q] = h.h.table({"onQuest": True, "complete": True})
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        h.ns.RefreshUI(h.ns)
        h.ns.UpdateNavigation(h.ns)

    def test_both_entry_points_offer_real_local_work_and_resume_the_same_boat(self):
        for via_tracker in (True, False):
            with self.subTest(via_tracker=via_tracker):
                h = BoatHost()
                self.journal(h, 270, 288)
                before = h.progress()
                row = h.ns.trackerRows[1]
                self.assertIn("Hacer misiones cercanas", row.goalTitle)
                self.assertIn("2 misiones", row.goalSub)
                self.assertTrue(h.ns.localTravelButton.shown)
                self.assertTrue(h.point().boatNavigation)
                row.scripts.OnClick(row, "RightButton")
                self.assertIsNone(h.ns.char.localTravelChoice)
                if via_tracker:
                    row.scripts.OnClick(row, "LeftButton")
                else:
                    h.h.g.Click(h.ns.localTravelButton)
                self.assertTrue(row.localObjective)
                self.assertIn("Entrega", row.goalTitle)
                self.assertIn("Habla con", row.goalSub)
                self.assertFalse(h.ns.trackerSkip.enabled)
                self.assertFalse(h.ns.trackerPrevious.enabled)
                self.assertEqual(h.ns.trackerNext.label.text, "Retomar viaje")
                point = h.ns.GetStepWaypoint(h.ns, h.step, None, h.h.table({}))
                self.assertEqual((point.source, point.goal.quest), ("local-travel-choice", 288))
                self.assertIn("Mis misiones cercanas", h.ns.navigationFrame.destinationText)
                h.h.g.Click(h.ns.trackerNext if via_tracker else h.ns.nextButton)
                self.assertTrue(h.point().boatNavigation)
                self.assertEqual(h.progress(), before)
                self.assertFalse(h.complete())

    def test_reload_empty_initial_journal_and_turnins_return_to_the_departure(self):
        h = BoatHost()
        self.journal(h, 270, 288)
        before = h.progress()
        h.h.g.Click(h.ns.localTravelButton)
        restored = BoatHost(saved=primitive_copy(h.ns.char))
        self.journal(restored, 270, 288)
        self.assertEqual(restored.point().goal.quest, 288)
        for quest, remaining in ((288, 270), (270, None)):
            restored.s.quests[quest] = restored.h.table({"delivered": True, "onQuest": False})
            restored.h.g.EmitAddonEvent("QUEST_TURNED_IN", quest)
            self.journal(restored, *([remaining] if remaining else []))
            if remaining:
                self.assertEqual(restored.point().goal.quest, remaining)
        self.assertIsNone(restored.ns.char.localTravelChoice)
        self.assertTrue(restored.point().boatNavigation)
        self.assertEqual(restored.progress(), before)
        self.assertFalse(restored.complete())

    def test_stale_row_manual_review_and_duo_navigation_are_respected(self):
        h = BoatHost()
        self.journal(h, 270)
        key = h.ns.localTravelButton.choiceKey
        before = h.progress()
        self.assertFalse(h.ns.ChooseLocalQuests(h.ns, "otro viaje"))
        state = h.ns.char.progress[GUIDE]
        state.review = True
        self.assertFalse(h.ns.ChooseLocalQuests(h.ns, key))
        state.review = None
        h.ns.DuoAuto.GetSharedView = h.h.lua.eval("function() return {following=true} end")
        self.assertFalse(h.ns.ChooseLocalQuests(h.ns, key))
        h.ns.DuoAuto.GetSharedView = h.h.lua.eval("function() return nil end")
        h.ns.Duo.GetMeetingWaypoint = h.h.lua.eval("function() return {mapID=1437,x=.1,y=.6} end")
        self.assertFalse(h.ns.ChooseLocalQuests(h.ns, key))
        self.assertIsNone(h.ns.char.localTravelChoice)
        self.assertEqual(h.progress(), before)

    def test_lower_level_duo_follows_only_the_shared_action_and_keeps_each_journal_intact(self):
        h = BoatHost()
        h.s.members, h.s.friendLevel = 2, 26
        h.ns.char.duo.enabled, h.ns.char.duo.wait = True, False
        h.ns.Duo.RefreshRoster(h.ns.Duo)
        h.ns.Duo.peer = h.h.table({"seen": h.s.now, "headerSeen": h.s.now, "nonce": "peer",
                                   "level": 26, "mapID": 1437, "guideID": GUIDE, "cursor": 31})
        h.ns.Duo.remoteQuests[270] = h.h.table({"state": 2, "known": True, "seen": h.s.now, "objectives": {}})
        self.journal(h, 270, 288)
        before, peer = h.progress(), primitive_copy(h.ns.Duo.remoteQuests)
        row = h.ns.trackerRows[1]
        self.assertIn("ambos diarios", row.goalSub)
        self.assertIn("26", row.goalSub)
        row.scripts.OnClick(row, "LeftButton")
        self.assertEqual(h.point().goal.quest, 270)
        self.assertIsNone(h.ns.char.localTravelChoice.quests[288])
        h.h.g.Click(h.ns.trackerNext)
        self.assertTrue(h.point().boatNavigation)
        self.assertEqual(h.progress(), before)
        self.assertEqual(primitive_copy(h.ns.Duo.remoteQuests), peer)

    def test_selected_work_survives_walking_far_from_the_initial_block(self):
        h = BoatHost()
        self.journal(h, 270)
        h.h.g.Click(h.ns.localTravelButton)
        h.s.now += 3
        h.move((1437, .68, .28))
        h.ns.RefreshUI(h.ns)
        self.assertEqual(h.point().goal.quest, 270)
        self.assertGreater(h.ns.GetWaypointVector(h.ns, h.point())[0], 1800)
        h.h.g.Click(h.ns.trackerNext)
        self.assertTrue(h.point().boatNavigation)

    def test_missing_access_path_keeps_the_local_objective_and_its_map_destination(self):
        h = BoatHost()
        self.journal(h, 270)
        h.h.g.Click(h.ns.localTravelButton)
        h.h.lua.execute("function ACCESS_NS.Waypoints:ResolveTarget() return nil end")
        h.ns.UpdateNavigation(h.ns)
        frame = h.ns.navigationFrame
        self.assertFalse(frame.arrow.shown)
        self.assertIn("local", frame.statusText)
        self.assertIn("La flota maldita", frame.destinationText)
        self.assertEqual(h.ns.GetStepWaypoint(h.ns, h.step, None, h.h.table({})).goal.quest, 270)

    def test_withdrawing_group_work_only_clears_the_pin_still_owned_by_the_guide(self):
        h = BoatHost(position=(1437, .1335, .5472))
        # Model the client's group tag on a real, nearby three-step collect quest.
        h.h.lua.execute("function C_QuestLog.GetQuestTagInfo(id) if id==484 then return {tagID=1} end end")
        h.ns.SetIncludeGroupQuests(h.ns, True)
        self.journal(h, 270, 484)
        h.s.quests[484].complete = False
        h.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        h.ns.RefreshUI(h.ns)
        h.h.g.Click(h.ns.localTravelButton)
        self.assertEqual(h.point().goal.quest, 484)
        h.s.waypointAllowed = h.s.waypointSuccess = True
        h.h.lua.execute("""
            function C_Map.GetUserWaypoint()
                return TEST.nativePin or {uiMapID=TEST.lastWaypoint.mapID,
                    position=CreateVector2D(TEST.lastWaypoint.x, TEST.lastWaypoint.y)}
            end
            function C_Map.ClearUserWaypoint() TEST.clears = (TEST.clears or 0) + 1 end
        """)
        self.assertTrue(h.ns.Navigate(h.ns))
        h.ns.ClearDeferredGroupMapPin(h.ns)
        self.assertIsNone(h.s.clears)
        h.ns.SetIncludeGroupQuests(h.ns, False)
        self.assertEqual(h.s.clears, 1)
        self.assertEqual(h.point().goal.quest, 270)
        self.assertIn("La flota maldita", h.ns.trackerRows[1].goalTitle)
        h.ns.SetIncludeGroupQuests(h.ns, True)
        self.assertTrue(h.ns.Navigate(h.ns))
        h.h.lua.execute("TEST.nativePin = {uiMapID=1437, position=CreateVector2D(.35,.46)}")
        h.ns.SetIncludeGroupQuests(h.ns, False)
        self.assertEqual(h.s.clears, 1)
