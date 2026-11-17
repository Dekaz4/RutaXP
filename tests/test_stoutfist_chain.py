"""The carried spellbook is delivered before the captain offers Howin's errand."""
import unittest

from test_duo_journey import primitive_copy
from test_quest_engine import QuestEngineHost
from test_westfall_migration import MigrationHost


GUIDE = "forever/alliance/30-40/01-hillsbrad-foothills"
PREVIOUS = "forever/alliance/07-thousand-needles"


def matches(h, quest, action, guide=GUIDE):
    return [(si, gi, goal, step) for si, step in h.ns.guides[guide].steps.items()
            for gi, goal in step.goals.items() if goal.quest == quest and goal.t == action]


class StoutfistChainTests(unittest.TestCase):
    def host(self):
        h = QuestEngineHost(catalog=True)
        h.initialize()
        h.state.level = 33
        h.ns.char.auto = False
        h.ns.char.activeGuide = GUIDE
        state = h.call("GetProgress", GUIDE)
        state.cursor, state.placed = matches(h, 98230, "accept")[0][0], True
        return h, state

    def status(self, h, state, quest, action, occurrence=0):
        _, gi, goal, step = matches(h, quest, action)[occurrence]
        return h.status(goal, step, state, gi)

    def test_user_carrying_book_is_sent_to_deliver_it_before_accepting(self):
        h, state = self.host()
        h.quest(474, delivered=True)
        h.quest(98221, onQuest=True)
        h.quest(98223, onQuest=True, complete=True)
        goal, _, status, *_ = h.active()
        self.assertEqual((goal.quest, goal.t, status), (98223, "turnin", "active"))
        self.assertEqual(goal.npc, 2104)
        self.assertEqual(self.status(h, state, 98230, "accept"), "blocked")
        h.quest(98223, onQuest=False, delivered=True)
        self.assertEqual(self.status(h, state, 98230, "accept"), "active")
        self.assertEqual(h.active()[0].quest, 98230)

    def test_missing_book_does_not_claim_delivery_or_offer_locked_errand(self):
        h, state = self.host()
        h.quest(474, delivered=True)
        self.assertEqual(self.status(h, state, 98223, "turnin"), "blocked")
        self.assertEqual(self.status(h, state, 98230, "accept"), "blocked")
        _, gi, goal, step = matches(h, 98230, "accept")[0]
        _, reason = h.call("GetGoalStatus", goal, step, state, gi)
        self.assertIn("Viejas costumbres", reason)
        self.assertFalse(h.call("IsQuestDelivered", 98223))

    def test_missing_book_first_routes_to_its_object_in_wetlands(self):
        h, state = self.host()
        h.quest(474, delivered=True)
        state.cursor = 1
        goal, _, status, *_ = h.active()
        self.assertEqual((goal.quest, goal.t, status), (98223, "accept", "active"))
        self.assertEqual((goal.object, goal.map), (671518, 1437))
        self.assertAlmostEqual(goal.x, 53.46)
        self.assertAlmostEqual(goal.y, 54.52)
        self.assertEqual(goal.f, "e")

    def test_unlocked_followup_does_not_send_player_back_for_a_missing_old_flag(self):
        for child in (98230,):
            with self.subTest(child=child):
                h, state = self.host()
                h.quest(child, onQuest=True)
                self.assertEqual(self.status(h, state, 98223, "accept"), "skip")
                self.assertFalse(h.call("IsQuestDelivered", 98223))
                h.quest(98223, onQuest=True, complete=True)
                self.assertEqual(self.status(h, state, 98223, "turnin"), "active")

    def test_independent_howin_chain_does_not_prove_the_book_was_delivered(self):
        h, state = self.host()
        for quest in (98291, 98297, 98300):
            h.quest(quest, delivered=True)
        self.assertEqual(self.status(h, state, 98223, "accept"), "active")
        self.assertEqual(self.status(h, state, 98230, "accept"), "blocked")

    def test_both_real_deliveries_are_required_and_skip_does_not_unlock(self):
        h, state = self.host()
        h.quest(98223, onQuest=True, complete=True)
        si, gi, _, _ = matches(h, 98223, "turnin")[0]
        state.skipped = h.table({f"{si}:{gi}": True})
        h.quest(474, delivered=True)
        self.assertEqual(self.status(h, state, 98230, "accept"), "blocked")
        h.quest(98223, onQuest=False, delivered=True)
        h.quest(474, delivered=False)
        self.assertEqual(self.status(h, state, 98230, "accept"), "blocked")
        h.quest(474, delivered=True)
        self.assertEqual(self.status(h, state, 98230, "accept"), "active")

    def test_nekrosh_visit_includes_book_before_leaving_for_theramore(self):
        h, _ = self.host()
        pickup = matches(h, 98223, "accept", PREVIOUS)[0]
        delivery = matches(h, 98223, "turnin", PREVIOUS)[0]
        nekrosh = matches(h, 474, "collect", PREVIOUS)[0]
        captain = matches(h, 474, "turnin", PREVIOUS)[0]
        self.assertEqual(pickup[0], nekrosh[0])
        self.assertEqual(delivery[0], captain[0])
        self.assertLess(pickup[:2], delivery[:2])
        self.assertLess(delivery[:2], captain[:2])
        self.assertEqual(pickup[2].object, 671518)
        self.assertIsNone(pickup[2].parent)  # No unverified active-Nek'rosh gate.

    def test_howin_combat_chain_waits_for_both_independent_deliveries(self):
        h, state = self.host()
        h.quest(98230, delivered=True)
        for completed in (None, 98245, 98246):
            h.quest(98245, delivered=completed == 98245)
            h.quest(98246, delivered=completed == 98246)
            self.assertEqual(self.status(h, state, 98291, "accept"), "blocked")
        h.quest(98245, delivered=True)
        h.quest(98246, delivered=True)
        self.assertEqual(self.status(h, state, 98291, "accept"), "active")
        for parent, child in ((98291, 98297), (98297, 98300)):
            self.assertEqual(self.status(h, state, child, "accept"), "blocked")
            h.quest(parent, delivered=True)
            self.assertEqual(self.status(h, state, child, "accept"), "active")

    def test_authored_order_delivers_prerequisites_before_the_next_pickup(self):
        h, _ = self.host()
        for parent, child in ((98245, 98291), (98246, 98291), (98291, 98297), (98297, 98300)):
            with self.subTest(parent=parent, child=child):
                self.assertLess(matches(h, parent, "turnin")[0][:2],
                                matches(h, child, "accept")[0][:2])
        eggs = matches(h, 98246, "collect")[0]
        self.assertLess(matches(h, 98246, "accept")[0][:2], eggs[:2])
        self.assertLess(eggs[:2], matches(h, 98246, "turnin")[0][:2])
        self.assertEqual((eggs[2].item, eggs[2].count), (280132, 12))

    def test_recovery_of_book_already_carried_preserves_unrelated_marks(self):
        saved = {"seen": True, "auto": False, "activeGuide": GUIDE, "progress": {
            GUIDE: {"cursor": 1, "routeRevision": 4, "placed": True,
                    "skipped": {"1:2": True, "1:4": True, "18:2": True}}}}
        h = MigrationHost(saved, {474: {"delivered": True}, 98221: {"onQuest": True},
                                 98223: {"onQuest": True, "complete": True}})
        h.state.level = 33
        journal = primitive_copy(h.state.quests)
        h.initialize()
        state = h.ns.char.progress[GUIDE]
        self.assertEqual(state.routeRevision, h.ns.guides[GUIDE].routeRevision)
        self.assertEqual((h.active()[0].quest, h.active()[0].t), (98223, "turnin"))
        self.assertEqual(state.cursor, matches(h, 98223, "turnin")[0][0])
        si, gi, _, _ = matches(h, 98208, "accept")[0]
        self.assertTrue(state.skipped[f"{si}:{gi}"])
        self.assertEqual(primitive_copy(h.state.quests), journal)
        self.assertFalse(h.call("IsQuestDelivered", 98223))

    def test_completed_chapters_are_not_reopened_by_book_additions(self):
        for guide, previous_revision, previous_count in ((PREVIOUS, 5, 37), (GUIDE, 4, 41)):
            with self.subTest(guide=guide):
                h = MigrationHost({"seen": True, "auto": False, "activeGuide": guide,
                    "progress": {guide: {"cursor": previous_count + 1,
                                         "routeRevision": previous_revision, "placed": True}}})
                h.state.level = 33
                h.initialize()
                self.assertEqual(h.ns.char.progress[guide].cursor, len(h.ns.guides[guide].steps) + 1)
                self.assertFalse(h.call("IsQuestDelivered", 98223))

    def test_missing_book_recovers_old_captain_step_without_claiming_completion(self):
        h = MigrationHost({"seen": True, "auto": False, "activeGuide": GUIDE,
            "progress": {GUIDE: {"cursor": 1, "routeRevision": 4, "placed": True,
                                  "skipped": {"1:2": True}}}}, {474: {"delivered": True}})
        h.state.level = 30
        h.initialize()
        state = h.ns.char.progress[GUIDE]
        self.assertEqual(state.cursor, 1)
        goal, _, status, *_ = h.active()
        self.assertEqual((goal.quest, goal.t, status), (98223, "accept", "active"))
        self.assertFalse(h.call("IsQuestDelivered", 98223))
        self.assertFalse(h.call("IsQuestDelivered", 98230))


if __name__ == "__main__":
    unittest.main()
