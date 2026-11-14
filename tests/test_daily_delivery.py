"""The Wetlands breadcrumb must not block an already-started Halloran chain."""
import unittest

from test_quest_engine import QuestEngineHost


GUIDE = "forever/alliance/06-ashenvale"


class DailyDeliveryTests(unittest.TestCase):
    def host(self, cursor=48):
        h = QuestEngineHost(catalog=True)
        h.initialize()
        h.state.level = 30
        h.ns.char.auto = False
        h.ns.char.activeGuide = GUIDE
        state = h.call("GetProgress", GUIDE)
        state.cursor, state.placed = cursor, True
        return h, state, h.ns.guides[GUIDE].steps[cursor]

    def test_downstream_quest_closes_both_absent_breadcrumb_visits(self):
        for quest in (484, 471):
            for delivered in (False, True):
                for cursor, index in ((48, 1), (57, 3)):
                    with self.subTest(quest=quest, delivered=delivered, cursor=cursor):
                        h, state, step = self.host(cursor)
                        h.quest(quest, onQuest=not delivered, delivered=delivered)
                        goal = step.goals[index]
                        self.assertEqual(goal.quest, 469)
                        self.assertEqual(h.status(goal, step, state, index), "skip")
                        self.assertFalse(h.call("IsQuestDelivered", 469))
                        self.assertIsNone(h.ns.turnedIn[469])
                        self.assertIsNone(state.confirmed[f"{cursor}:{index}"])
                        self.assertEqual(state.cursor, cursor)

    def test_the_remaining_greenwarden_work_stays_actionable(self):
        h, state, step = self.host()
        h.quest(484, delivered=True)
        h.quest(471, onQuest=True)
        h.quest(463, onQuest=True, complete=True)
        self.assertEqual(h.active()[0].quest, 463)
        self.assertEqual(h.active()[1], 2)
        h.quest(463, onQuest=False, delivered=True)
        self.assertEqual(h.active()[0].quest, 276)
        self.assertEqual(h.active()[1], 3)
        self.assertEqual(h.status(step.goals[3], step, state, 3), "active")
        self.assertEqual(state.cursor, 48)

    def test_an_actual_breadcrumb_in_the_journal_still_needs_delivery(self):
        for quest in (484, 471):
            with self.subTest(quest=quest):
                h, state, step = self.host(57)
                h.quest(quest, onQuest=True)
                h.quest(469, onQuest=True, complete=True)
                self.assertEqual(h.status(step.goals[3], step, state, 3), "active")
                self.assertFalse(h.call("IsQuestDelivered", 469))
                accept = h.ns.guides[GUIDE].steps[48]
                self.assertEqual(h.status(accept.goals[1], accept, state, 1), "done")

    def test_no_downstream_evidence_keeps_the_breadcrumb_available(self):
        h, state, step = self.host()
        self.assertEqual(h.status(step.goals[1], step, state, 1), "active")
        self.assertEqual(h.active()[0].quest, 469)
        self.assertFalse(h.call("IsQuestDelivered", 469))

    def test_a_delivered_breadcrumb_is_still_recorded_as_done(self):
        h, state, step = self.host()
        h.quest(469, delivered=True)
        h.quest(484, onQuest=True)
        self.assertEqual(h.status(step.goals[1], step, state, 1), "done")
        self.assertTrue(h.call("IsQuestDelivered", 469))


if __name__ == "__main__":
    unittest.main()
