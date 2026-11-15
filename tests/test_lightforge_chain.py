"""Menethil follows the carried iron quest before either ingot alternative."""
import unittest

from test_duo_journey import primitive_copy
from test_quest_engine import QuestEngineHost
from test_westfall_migration import MigrationHost


GUIDE = "forever/alliance/07-thousand-needles"


def goal_at(host, quest, action):
    for si, step in host.ns.guides[GUIDE].steps.items():
        for gi, goal in step.goals.items():
            if goal.quest == quest and goal.t == action:
                return si, gi, goal, step
    raise AssertionError((quest, action))


class LightforgeChainTests(unittest.TestCase):
    def host(self, cursor=18):
        h = QuestEngineHost(catalog=True)
        h.initialize()
        h.state.level = 30
        h.ns.char.auto = False
        h.ns.char.activeGuide = GUIDE
        state = h.call("GetProgress", GUIDE)
        state.cursor, state.placed = cursor, True
        return h, state

    def status(self, h, state, quest, action):
        _, gi, goal, step = goal_at(h, quest, action)
        return h.status(goal, step, state, gi)

    def test_unstarted_chain_never_offers_ingots_as_available(self):
        h, state = self.host()
        self.assertEqual(self.status(h, state, 270, "turnin"), "skip")
        for before in (False, True):
            if before:
                h.quest(269, onQuest=True)
            for quest, action in ((321, "accept"), (321, "turnin"), (324, "accept"),
                                  (526, "accept"), (324, "collect"), (526, "collect"),
                                  (324, "turnin"), (526, "turnin")):
                self.assertEqual(self.status(h, state, quest, action), "skip")
                self.assertFalse(h.call("IsQuestDelivered", quest))
        h.quest(270, onQuest=True, complete=True)
        self.assertEqual(self.status(h, state, 270, "turnin"), "active")
        self.assertEqual(self.status(h, state, 321, "accept"), "blocked")
        h.quest(270, onQuest=False, delivered=True)
        self.assertEqual(self.status(h, state, 321, "accept"), "active")

    def test_chest_delivery_unlocks_the_alternative_without_false_quest_credit(self):
        h, state = self.host()
        h.quest(321, onQuest=True, complete=False)
        self.assertEqual(self.status(h, state, 321, "accept"), "done")
        self.assertEqual(self.status(h, state, 321, "turnin"), "active")
        for quest in (324, 526):
            self.assertEqual(self.status(h, state, quest, "accept"), "blocked")
        _, _, chest, _ = goal_at(h, 321, "turnin")
        self.assertEqual((chest.object, chest.map, chest.x, chest.y), (2734, 1437, 12.11, 64.19))
        h.quest(321, onQuest=False, delivered=True)
        self.assertEqual(self.status(h, state, 324, "accept"), "active")
        h.quest(324, onQuest=True)
        self.assertEqual(self.status(h, state, 526, "accept"), "skip")
        self.assertFalse(h.call("IsQuestDelivered", 526))
        self.assertIsNone(h.ns.turnedIn[526])

    def test_each_carried_alternative_keeps_its_work_and_hides_the_other(self):
        for carried, other in ((324, 526), (526, 324)):
            with self.subTest(carried=carried):
                h, state = self.host(19)
                h.quest(carried, onQuest=True, complete=False,
                        objectives=[{"numFulfilled": 2, "numRequired": 5, "finished": False}])
                h.ns.char.optional = True
                self.assertEqual(self.status(h, state, 270, "turnin"), "skip")
                self.assertEqual(self.status(h, state, 321, "turnin"), "skip")
                self.assertEqual(self.status(h, state, carried, "collect"), "active")
                self.assertEqual(self.status(h, state, other, "collect"), "skip")
                state.cursor = 21
                self.assertEqual(self.status(h, state, carried, "turnin"), "active")
                self.assertEqual(self.status(h, state, other, "turnin"), "skip")

    def test_skipping_chest_does_not_unlock_either_ingot_quest(self):
        h, state = self.host()
        h.quest(321, onQuest=True)
        si, gi, _, _ = goal_at(h, 321, "turnin")
        state.skipped = h.table({f"{si}:{gi}": True})
        for quest in (324, 526):
            self.assertEqual(self.status(h, state, quest, "accept"), "blocked")
        self.assertFalse(h.call("IsQuestDelivered", 321))

    def test_ingots_are_grouped_beside_chest_before_independent_northern_work(self):
        h, _ = self.host()
        self.assertEqual(len(h.ns.guides[GUIDE].steps), 37)
        for quest in (324, 526):
            si, _, work, _ = goal_at(h, quest, "collect")
            self.assertEqual(si, 19)
            self.assertEqual(work.map, 1437)
            self.assertGreater(work.y, 60)
        self.assertEqual(goal_at(h, 289, "kill")[0], 20)
        self.assertEqual(goal_at(h, 324, "turnin")[0], 21)

    def test_old_manual_skip_recovers_carried_chest_but_preserves_unrelated_marks(self):
        saved = {"seen": True, "auto": False, "activeGuide": GUIDE, "progress": {GUIDE: {
            "cursor": 20, "routeRevision": 3, "placed": True,
            "confirmed": {f"18:{gi}": True for gi in (1, 2, 3, 4, 5, 6)},
            "skipped": {"18:7": True, "18:8": True, "19:1": True}}}}
        h = MigrationHost(saved, {321: {"onQuest": True, "complete": False}})
        h.state.level = 30
        journal = primitive_copy(h.state.quests)
        h.initialize()
        state = h.ns.char.progress[GUIDE]
        self.assertEqual(state.routeRevision, h.ns.guides[GUIDE].routeRevision)
        self.assertEqual(state.cursor, 18)
        self.assertTrue(state.skipped["18:7"])  # The captain's unchanged errand.
        self.assertTrue(state.skipped["20:1"])  # Crew work moved with its mark.
        self.assertIsNone(state.skipped["18:12"])  # The old impossible ingot acceptance.
        self.assertEqual(h.active()[0].quest, 321)
        self.assertEqual(h.active()[0].t, "turnin")
        self.assertEqual(primitive_copy(h.state.quests), journal)
        self.assertFalse(h.call("IsQuestDelivered", 321))
        self.assertTrue(h.ns.char.guideMigrationBackups[GUIDE + ":4"].progress.skipped["18:7"])

    def test_completed_chapter_stays_complete_after_revision(self):
        saved = {"seen": True, "auto": False, "activeGuide": GUIDE,
                 "progress": {GUIDE: {"cursor": 38, "routeRevision": 3, "placed": True}}}
        h = MigrationHost(saved)
        h.state.level = 30
        h.initialize()
        state = h.ns.char.progress[GUIDE]
        self.assertEqual(state.cursor, 38)
        self.assertEqual(state.routeRevision, h.ns.guides[GUIDE].routeRevision)
        self.assertIsNone(state.requirementsRepair)

    def test_later_chapter_does_not_repeat_the_other_branch(self):
        later = "forever/alliance/30-40/03-ashenvale"
        for data in ({526: {"onQuest": True}}, {526: {"delivered": True}}, {322: {"onQuest": True}}):
            with self.subTest(data=data):
                h, _ = self.host()
                h.ns.char.activeGuide = later
                state = h.call("GetProgress", later)
                for q, values in data.items():
                    h.quest(q, **values)
                for si, step in h.ns.guides[later].steps.items():
                    state.cursor = si
                    for gi, goal in step.goals.items():
                        if goal.quest in (321, 324):
                            self.assertEqual(h.status(goal, step, state, gi), "skip")
                self.assertFalse(h.call("IsQuestDelivered", 324))


if __name__ == "__main__":
    unittest.main()
