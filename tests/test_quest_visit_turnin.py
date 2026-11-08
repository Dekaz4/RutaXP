import unittest

from test_duo_journey import primitive_copy
from test_quest_engine import ADDON, QuestEngineHost


WESTFALL = "forever/alliance/02-westfall"


class QuestVisitTurninTests(unittest.TestCase):
    def setUp(self):
        h = self.h = QuestEngineHost(catalog=True)
        h.load((ADDON / "QuestVisitTurnin.lua").read_text(encoding="utf-8"), "RutaXP", h.ns)
        h.ns.earlyQuestOffers = h.table({109: True, 65: True})
        h.state.level = 12
        h.state.classToken = "ROGUE"
        h.initialize()
        h.call("SelectGuide", WESTFALL)
        h.quest(109, onQuest=True, complete=True)

    def permits(self, quest=109, npc=234, ready=None):
        return self.h.call("CanHandInDuringVisit", quest, npc, ready)

    def test_early_westfall_delivery_at_gryans_first_visit_is_read_only(self):
        h = self.h
        self.assertEqual(h.cursor(WESTFALL), 1)
        before = primitive_copy(h.ns.char)
        self.assertFalse(self.permits(npc=233))  # Saldean offers the letter.
        self.assertFalse(self.permits(npc=821))  # Another NPC on this step.
        self.assertFalse(self.permits(npc=None))
        self.assertTrue(self.permits())
        self.assertEqual(primitive_copy(h.ns.char), before)
        h.quest(12, onQuest=True)  # Accepted Gryan's scheduled quest first.
        self.assertTrue(self.permits())
        self.assertTrue(h.call("IsQuestActive", 109))
        self.assertEqual(h.cursor(WESTFALL), 1)

    def test_requires_active_quest_and_evidence_of_readiness_at_recipient(self):
        h = self.h
        self.assertFalse(self.permits(ready=False))  # Negative live NPC evidence wins.
        h.quest(109, onQuest=True, complete=False)
        self.assertFalse(self.permits())
        self.assertTrue(self.permits(ready=True))  # Matching completed gossip row.
        h.lua.execute("C_QuestLog.IsComplete = function() error('unavailable') end")
        self.assertFalse(self.permits())
        h.quest(109, onQuest=False, delivered=True)
        self.assertFalse(self.permits(ready=True))

    def test_requires_reviewed_recipient_and_an_applicable_current_visit(self):
        h = self.h
        h.ns.earlyQuestOffers[109] = None
        self.assertFalse(self.permits())
        h.ns.earlyQuestOffers[109] = True
        h.quest(65, onQuest=True, complete=True)
        self.assertFalse(self.permits(quest=65))
        h.ns.char.progress[WESTFALL].review = True
        self.assertFalse(self.permits())
        h.ns.char.progress[WESTFALL].review = None
        h.state.level = 1  # Gryan's other first-step quest is for Skyborne only.
        self.assertFalse(self.permits())
        h.state.level = 12
        h.ns.char.progress[WESTFALL].cursor = 2  # Planned visit to Saldean.
        self.assertFalse(self.permits())
        h.ns.char.progress[WESTFALL].cursor = 13  # Ordinary scheduled hand-in.
        self.assertFalse(self.permits())

    def test_waits_at_gryans_visit_if_manual_duo_wait_is_active(self):
        h = self.h
        h.ns.char.duo = h.table({"enabled": True, "wait": True})
        h.ns.Duo = h.lua.eval("{ShouldWaitForStep = function() return true end}")
        self.assertFalse(self.permits())
        h.ns.char.duo.wait = False
        self.assertTrue(self.permits())

    def test_respects_future_row_omission_character_and_guides_without_a_destination(self):
        h = self.h
        state = h.ns.char.progress[WESTFALL]
        state.skipped = h.table({"13:1": True})
        self.assertFalse(self.permits())
        state.skipped = None
        goal = h.ns.guides[WESTFALL].steps[13].goals[1]
        self.assertEqual(goal.quest, 109)
        goal.only = h.table({"classes": ["HUNTER"]})
        self.assertFalse(self.permits())
        goal.only = None
        goal.npc = 821
        self.assertFalse(self.permits())
        h.ns.char.progress[WESTFALL] = None
        self.assertFalse(self.permits())
        self.assertIsNone(h.ns.char.progress[WESTFALL])
