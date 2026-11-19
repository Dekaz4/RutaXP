"""Updated Forever routes must let a saved character move past the missing Villards."""
import unittest

from test_addon import ADDON
from test_duo_journey import primitive_copy
from test_westfall_migration import MigrationHost


GUIDE = "forever/alliance/30-40/01-hillsbrad-foothills"
RETIRED = (87318, 88757, 88758)
# Real saved cursor positions for 0.7.24 and 0.7.28, before the visit was removed.
OLD_VISITS = ((4, 16, 41), (5, 19, 44))


class VillardRetirementTests(unittest.TestCase):
    def test_saved_villard_visit_resumes_with_whelgar_and_preserves_neighboring_marks(self):
        for revision, visit, _ in OLD_VISITS:
            with self.subTest(revision=revision):
                progress = {"cursor": visit, "routeRevision": revision, "placed": True,
                            "skipped": {f"{visit-1}:2": True, f"{visit}:1": True},
                            "confirmed": {f"{visit}:4": True, f"{visit+1}:2": True}}
                # This character has already finished the Howin and book repair from 0.7.27.
                quests = {q: {"delivered": True} for q in (98223, 98230, 98245, 98246, 98291, 98297, 98300)}
                quests[98310] = {"onQuest": True, "complete": True}
                h = MigrationHost({"seen": True, "auto": False, "activeGuide": GUIDE,
                                   "progress": {GUIDE: progress}}, quests)
                journal = primitive_copy(h.state.quests)
                h.initialize()
                _, step, saved = h.call("GetCurrent")
                self.assertEqual((step.goals[1].npc, step.goals[1].quest, step.goals[1].t),
                                 (1077, 98310, "turnin"))
                self.assertEqual(saved.routeRevision, h.ns.guides[GUIDE].routeRevision)
                self.assertEqual(primitive_copy(saved.skipped), {f"{saved.cursor-1}:2": True})
                self.assertEqual(primitive_copy(saved.confirmed), {f"{saved.cursor}:2": True})
                self.assertEqual(primitive_copy(h.state.quests), journal)
                for q in RETIRED:
                    self.assertFalse(h.call("IsQuestDelivered", q))

    def test_completed_chapter_stays_complete_in_both_revisions(self):
        for revision, _, count in OLD_VISITS:
            with self.subTest(revision=revision):
                h = MigrationHost({"seen": True, "auto": True, "activeGuide": GUIDE, "progress": {
                    GUIDE: {"cursor": count+1, "routeRevision": revision, "placed": True}}})
                h.initialize()
                guide, saved = h.ns.guides[GUIDE], h.ns.char.progress[GUIDE]
                self.assertEqual(saved.routeRevision, guide.routeRevision)
                self.assertEqual(saved.cursor, len(guide.steps)+1)

    def test_no_global_route_or_early_npc_offer_in_solo_or_group_mode(self):
        h = MigrationHost()
        for module in ("EarlyQuestData.lua", "QuestOfferAdvice.lua"):
            h.load((ADDON / module).read_text(encoding="utf8"), "RutaXP", h.ns)
        h.initialize()
        h.state.level = 33
        h.ns.char.activeGuide = GUIDE
        h.ns.char.optional, h.ns.char.auto = True, True
        state = h.call("GetProgress", GUIDE)
        state.cursor, state.placed, state.review = 1, True, False
        h.lua.execute("""
            function C_QuestLog.GetNumQuestLogEntries() return 2, 1 end
            function C_QuestLog.GetMaxNumQuestsCanAccept() return 40 end
        """)
        # An unrelated verified Menethil pickup must still be suggested before its visit.
        h.quest(471, delivered=True)
        self.assertTrue(h.call("GetEarlyQuestOffer", 98072))
        routed = {goal.quest for guide in h.ns.guides.values() for step in guide.steps.values()
                  for goal in step.goals.values() if goal.quest}
        self.assertTrue(routed.isdisjoint(RETIRED))
        for include_group in (False, True):
            h.ns.char.includeGroupQuests = include_group
            for q, npc in zip(RETIRED, (5683, 271322, 271322)):
                with self.subTest(group=include_group, quest=q):
                    self.assertIsNone(h.ns.earlyQuestOffers[q])
                    self.assertIsNone(h.call("GetEarlyQuestOffer", q))
                    self.assertIsNone(h.call("GetPlannedPickupAtNPC", q, npc, 1437))
                    self.assertFalse(h.call("WantsQuest", "accept", q))
