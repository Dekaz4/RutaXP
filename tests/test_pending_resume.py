"""Recover skipped journal objectives without resetting the guide or either player."""
import unittest

from test_quest_engine import QuestEngineHost
from test_duo_journey import primitive_copy


class PendingResumeTests(unittest.TestCase):
    def host(self):
        h = QuestEngineHost()
        h.guide("rejoin", steps=[
            {"title": "Earlier delivery", "goals": [{"t": "turnin", "quest": 9}]},
            {"title": "Farm", "goals": [
                {"t": "collect", "quest": 38, "oi": 1},
                {"t": "collect", "quest": 38, "oi": 2},
                {"t": "train"},
                {"t": "accept", "quest": 70, "only": {"classes": ["MAGE"]}},
            ]},
            {"title": "Hand in", "goals": [{"t": "turnin", "quest": 38}]},
            {"title": "Other tasks", "goals": [{"t": "accept", "quest": 71}]},
        ])
        h.initialize()
        h.quest(9, delivered=True)
        h.quest(38, onQuest=True, objectives=[
            {"numFulfilled": 0, "numRequired": 3, "finished": False},
            {"numFulfilled": 3, "numRequired": 3, "finished": True},
        ])
        state = h.call("GetProgress", "rejoin")
        state.cursor, state.review = 4, True
        state.confirmed = h.table({"1:1": True, "2:1": True, "2:3": True})
        state.skipped = h.table({"2:1": True, "2:2": True, "2:4": True, "3:1": True, "4:1": True})
        h.ns.char.auto = False
        return h, state

    def test_resume_uses_live_pending_goals_and_retains_services_other_choices_and_quests(self):
        h, state = self.host()
        h.ns.char.progress["other"] = h.table({"cursor": 12, "confirmed": {"1:1": True}})
        quests = primitive_copy(h.state.quests)
        ok, message = h.call("ResumePendingQuests")
        self.assertTrue(ok, message)
        self.assertEqual(state.cursor, 2)
        self.assertIsNone(state.review)
        self.assertFalse(h.ns.char.auto)
        self.assertIsNone(state.confirmed["2:1"])
        self.assertIsNone(state.skipped["2:1"])
        self.assertIsNone(state.skipped["3:1"])
        self.assertTrue(state.confirmed["2:3"])
        self.assertTrue(state.skipped["2:4"])
        self.assertTrue(state.skipped["4:1"])
        self.assertEqual(h.ns.char.progress["other"].cursor, 12)
        self.assertEqual(primitive_copy(h.state.quests), quests)
        self.assertEqual(h.active()[1], 1)
        # Retry changes neither the progress nor the remaining choices.
        before = primitive_copy(state)
        h.call("ResumePendingQuests")
        self.assertEqual(primitive_copy(state), before)

    def test_actual_objective_credit_takes_priority_over_old_manual_skips(self):
        h, state = self.host()
        step = h.ns.guides["rejoin"].steps[2]
        self.assertEqual(h.status(step.goals[2], step, state, 2), "done")
        self.assertEqual(h.status(step.goals[1], step, state, 1), "skip")
        h.quest(38, onQuest=True, complete=True)
        h.call("ResumePendingQuests")
        self.assertEqual(state.cursor, 3)
        self.assertEqual(h.active()[2], "active")

    def test_no_pending_journal_quest_and_travel_leave_the_bookmark_untouched(self):
        h, state = self.host()
        h.quest(38, delivered=True)
        before = primitive_copy(state)
        self.assertFalse(h.call("ResumePendingQuests")[0])
        self.assertEqual(primitive_copy(state), before)
        h.quest(38, onQuest=True)
        h.ns.GetGuideTravel = h.lua.eval("function() return {title='Viaje'} end")
        self.assertFalse(h.call("ResumePendingQuests")[0])
        self.assertEqual(primitive_copy(state), before)

    def test_numeric_flags_and_zero_objectives_never_complete_pending_work(self):
        h, state = self.host()
        h.lua.execute("""
            function C_QuestLog.IsQuestFlaggedCompleted() return 0 end
            function C_QuestLog.IsComplete() return 0 end
            function IsQuestFlaggedCompleted() return 0 end
            TEST.quests[38].objectives[1].finished = 0
        """)
        h.call("ResumePendingQuests")
        self.assertFalse(h.call("IsQuestDelivered", 9))
        self.assertFalse(h.call("IsQuestDelivered", 38))
        self.assertEqual(h.active()[2], "active")
        self.assertEqual(state.cursor, 2)

    def test_current_journal_beats_history_but_new_turnin_event_is_immediate(self):
        h, state = self.host()
        h.quest(38, onQuest=True, delivered=True)
        self.assertFalse(h.call("IsQuestDelivered", 38))
        h.fire("QUEST_TURNED_IN", 38)
        self.assertTrue(h.call("IsQuestDelivered", 38))
        h.fire("QUEST_ACCEPTED", 38)
        self.assertFalse(h.call("IsQuestDelivered", 38))

    def test_back_restores_only_that_step_and_keeps_automatic_progress_running(self):
        h, state = self.host()
        state.cursor = 3
        state.skipped["3:1"] = None
        state.skipped["4:1"] = None
        h.ns.char.auto = True
        h.ns.char.progress["other"] = h.table({"cursor": 7, "skipped": {"2:1": True}})
        quests = primitive_copy(h.state.quests)
        h.call("Previous")
        self.assertEqual(state.cursor, 2)
        self.assertIsNone(state.review)
        self.assertIsNone(state.skipped["2:1"])
        self.assertIsNone(state.skipped["2:2"])
        self.assertIsNone(state.confirmed["2:1"])
        self.assertTrue(state.confirmed["2:3"])
        self.assertTrue(state.confirmed["1:1"])
        self.assertTrue(h.ns.char.progress["other"].skipped["2:1"])
        self.assertEqual(primitive_copy(h.state.quests), quests)
        self.assertEqual(h.active()[2], "active")
        # A server completion then advances normally to the delivery visit.
        h.quest(38, onQuest=True, complete=True)
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(state.cursor, 3)
        self.assertEqual(h.active()[0].t, "turnin")
        self.assertFalse(h.call("IsQuestDelivered", 38))

    def test_back_recovers_a_skipped_acceptance_even_when_quest_is_not_in_the_log(self):
        h, state = self.host()
        state.cursor = 5
        h.call("Previous")
        self.assertEqual(state.cursor, 4)
        self.assertIsNone(state.skipped["4:1"])
        self.assertEqual(h.active()[0].quest, 71)
        self.assertEqual(h.active()[2], "active")
        self.assertTrue(state.skipped["2:1"])

    def test_back_does_not_uncomplete_a_real_delivery(self):
        h, state = self.host()
        state.cursor = 2
        h.ns.char.auto = True
        h.call("Previous")
        self.assertEqual(state.cursor, 1)
        self.assertTrue(state.review)
        self.assertTrue(h.call("IsQuestDelivered", 9))
        self.assertEqual(h.status(h.ns.guides["rejoin"].steps[1].goals[1]), "done")


if __name__ == "__main__":
    unittest.main()
