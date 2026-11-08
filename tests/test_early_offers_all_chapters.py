"""Run a real questgiver visit before its scheduled pickup in every shipped chapter."""
import unittest

from test_quest_engine import ADDON, QuestEngineHost


def future_pickup(host, guide):
    seen = set()
    for si in range(1, len(guide.steps) + 1):
        step = guide.steps[si]
        for gi in range(1, len(step.goals) + 1):
            goal = step.goals[gi]
            if goal.t != "accept" or goal.quest in seen:
                continue
            seen.add(goal.quest)
            if (si > 1 and goal.npc and host.ns.earlyQuestOffers[goal.quest]
                    and not host.ns.earlyQuestAlternatives[goal.quest]
                    and not any((step.only, goal.only, goal.optional, goal.profLine, goal.parent,
                                 goal.requiresSkill, step.requiresSkill, goal.closedBy))):
                return si, step, gi, goal


class AllChapterPickupTests(unittest.TestCase):
    def setUp(self):
        h = self.host = QuestEngineHost(catalog=True)
        for name in ("EarlyQuestData.lua", "QuestOfferAdvice.lua"):
            h.load((ADDON / name).read_text(encoding="utf-8"), "RutaXP", h.ns)
        h.initialize()
        h.lua.execute("""
            function GetNumAvailableQuests() return 1 end
            function GetAvailableQuestInfo() return false, 1, false, false, TEST.offer end
            function SelectAvailableQuest(i) if i == 1 then TEST.selected = TEST.offer end end
            function GetQuestID() return TEST.selected end
            function UnitGUID(unit)
                if unit == "npc" then return "Creature-0-1-2-3-" .. TEST.giver .. "-0123" end
            end
            function AcceptQuest() TEST.quests[TEST.selected] = {onQuest=true} end
            function C_QuestLog.GetNumQuestLogEntries() return 2, 1 end
            function C_QuestLog.GetMaxNumQuestsCanAccept() return 40 end
        """)

    def test_offered_future_pickup_is_accepted_and_recognized_later_in_each_guide(self):
        h = self.host
        guides = sorted(h.ns.guides.keys())
        self.assertEqual(len(guides), 57)
        for guide_id in guides:
            with self.subTest(chapter=guide_id):
                guide = h.ns.guides[guide_id]
                h.state.quests = h.table({})
                h.state.faction = guide.faction
                h.state.raceToken = guide.races[1] if guide.races else ("Human" if guide.faction == "Alliance" else "Orc")
                h.state.level = 60
                h.call("SelectGuide", guide_id)
                state = h.ns.char.progress[guide_id]
                state.cursor, state.review = 1, False
                choice = future_pickup(h, guide)
                self.assertIsNotNone(choice, "No ordinary future questgiver visit exercised")
                si, step, gi, goal = choice
                for requirements in (goal.preAll, goal.pre):
                    if requirements:
                        for pre in requirements.values():
                            h.quest(abs(pre), delivered=True)
                h.state.offer, h.state.giver, h.state.selected = goal.quest, goal.npc, None
                h.call("HandleQuestAutomation", "QUEST_GREETING")
                self.assertEqual(h.state.selected, goal.quest)
                h.call("HandleQuestAutomation", "QUEST_DETAIL")
                self.assertTrue(h.call("IsQuestActive", goal.quest))
                self.assertEqual(state.cursor, 1)
                state.cursor = si
                self.assertEqual(h.status(goal, step, state, gi), "done")

    def test_earlier_visits_to_remy_and_baine(self):
        h = self.host
        for guide_id, faction, race, npc, quest, level in (
            ("forever/alliance/human/01-elwynn-forest", "Alliance", "Human", 241, 40, 7),
            ("forever/horde/tauren/01-mulgore", "Horde", "Tauren", 2993, 746, 6),
        ):
            with self.subTest(guide=guide_id):
                h.state.faction, h.state.raceToken, h.state.level = faction, race, level
                h.call("SelectGuide", guide_id)
                state = h.ns.char.progress[guide_id]
                state.cursor, state.review = 16, False
                h.state.giver, h.state.offer, h.state.selected = npc, quest, None
                h.call("HandleQuestAutomation", "QUEST_GREETING")
                self.assertEqual(h.state.selected, quest)
                h.call("HandleQuestAutomation", "QUEST_DETAIL")
                self.assertTrue(h.call("IsQuestActive", quest))
                self.assertEqual(state.cursor, 16)

    def test_durotar_pickup_preserves_then_recognizes_the_finished_intro(self):
        h = self.host
        guide_id = "forever/horde/orc-troll/01-durotar"
        h.state.faction, h.state.raceToken, h.state.level = "Horde", "Orc", 2
        h.call("SelectGuide", guide_id)
        state = h.ns.char.progress[guide_id]
        state.cursor, state.review = 1, False
        h.state.offer, h.state.giver, h.state.selected = 788, 3143, None
        h.call("HandleQuestAutomation", "QUEST_GREETING")
        self.assertIsNone(h.state.selected, "Accepting 788 would close the planned introduction 4641")
        h.quest(4641, delivered=True)
        h.call("HandleQuestAutomation", "QUEST_GREETING")
        self.assertEqual(h.state.selected, 788)

    def test_elwynn_skips_a_whole_visit_when_the_only_pickup_is_already_in_the_log(self):
        h = self.host
        guide_id = "forever/alliance/human/01-elwynn-forest"
        h.state.level = 10
        h.call("SelectGuide", guide_id)
        state = h.ns.char.progress[guide_id]
        state.cursor, state.review = 16, False
        h.state.giver, h.state.offer = 251, 106  # Maybell Maclure, «Jóvenes enamorados».
        h.call("HandleQuestAutomation", "QUEST_GREETING")
        self.assertEqual(h.state.selected, 106)
        h.call("HandleQuestAutomation", "QUEST_DETAIL")
        state.cursor = 23
        h.call("Sync")
        self.assertGreater(state.cursor, 23)
        self.assertTrue(h.call("IsQuestActive", 106))
        self.assertFalse(h.call("IsQuestDelivered", 106))
