"""Advice at a quest giver reads the character's own route and journal."""
import unittest

from test_quest_engine import ADDON, QuestEngineHost


class QuestOfferAdviceTests(unittest.TestCase):
    def setUp(self):
        self.h = QuestEngineHost()
        self.h.load((ADDON / "QuestOfferAdvice.lua").read_text(encoding="utf-8"), "RutaXP", self.h.ns)
        self.h.state.classToken = "ROGUE"
        self.h.state.level = 10
        self.h.guide("offers", steps=[
            {"title": "Plaza", "goals": [
                {"t": "accept", "quest": 1}, {"t": "accept", "quest": 2, "pre": [99]},
                {"t": "accept", "quest": 3, "optional": True},
                {"t": "accept", "quest": 4, "only": {"classes": ["MAGE"]}},
                {"t": "accept", "quest": 5, "closedBy": [98]},
            ]},
            {"title": "Camino", "goals": [{"t": "accept", "quest": 6}]},
            {"title": "Al llegar", "goals": [
                {"t": "accept", "quest": 7, "optional": True}, {"t": "turnin", "quest": 8},
                {"t": "accept", "quest": 9},
            ]},
            {"title": "Elfos", "only": {"races": ["NightElf"]}, "goals": [{"t": "accept", "quest": 10}]},
        ])
        self.h.initialize()
        self.progress = self.h.ns.char.progress["offers"]

    def advice(self, quest_id):
        return self.h.call("GetQuestOfferAdvice", quest_id)

    def test_current_accept_uses_its_own_goal_index_and_real_requirements(self):
        self.assertEqual(self.advice(1)[1], "ahora")
        self.assertIn("99", self.advice(2)[0])
        self.assertEqual(self.advice(2)[1], "estado")
        self.h.quest(99, delivered=True)
        self.assertEqual(self.advice(2)[1], "ahora")
        self.h.quest(98, onQuest=True)
        self.assertIn("alternativa", self.advice(5)[0])
        self.progress.skipped = self.h.table({"1:2": True})
        self.assertIn("Omitido", self.advice(2)[0])
        self.assertEqual(self.advice(1)[1], "ahora")

    def test_optional_later_personal_and_off_chapter(self):
        self.assertEqual(self.advice(3)[1], "opcional")
        self.h.ns.char.optional = True
        self.assertEqual(self.advice(3)[1], "opcional")
        self.assertEqual(self.advice(6), ("Espera al paso 2 para aceptarla.", "después"))
        self.assertEqual(self.advice(7), ("Opcional en el paso 3.", "opcional"))
        self.assertEqual(self.advice(8), ("La guía cuenta con esta misión en el paso 3.", "estado"))
        for quest_id in (4, 10, 88):
            self.assertEqual(self.advice(quest_id), ("Fuera de este capítulo. Puedes seguir sin aceptarla.", "fuera"))

    def test_progress_and_journal_are_not_changed_when_examining_future_or_past(self):
        self.progress.cursor = 2
        self.progress.confirmed = self.h.table({"1:1": True})
        self.progress.skipped = self.h.table({"3:3": True})
        self.h.lua.execute("function TEST.forbid() error('Offer advice must be read-only') end")
        for method in ("GetProgress", "GetCurrent", "Next", "Sync", "HandleQuestAutomation"):
            self.h.ns[method] = self.h.state.forbid
        self.assertIn("omitiste", self.advice(1)[0])
        self.assertIn("omitiste", self.advice(9)[0])
        self.assertIn("paso 1", self.advice(2)[0])
        self.h.quest(1, onQuest=True, delivered=True)
        self.assertIn("diario", self.advice(1)[0])
        self.h.quest(9, delivered=True)
        self.assertIn("entregado", self.advice(9)[0])
        self.assertEqual((self.progress.cursor, dict(self.progress.skipped.items())), (2, {"3:3": True}))
        self.h.ns.char.progress["offers"] = None
        self.assertEqual(self.advice(6)[1], "estado")
        self.assertIsNone(self.h.ns.char.progress["offers"])

    def test_travel_review_and_helping_partner_are_not_current_acceptances(self):
        self.progress.review = True
        self.assertIn("revisando", self.advice(1)[0])
        self.progress.review = None
        self.h.ns.GetGuideTravel = self.h.lua.eval("function() return {waiting=true} end")
        self.assertIn("viaje", self.advice(1)[0])
        self.h.ns.GetGuideTravel = None
        self.h.ns.DuoAuto = self.h.lua.eval("{agreement={}, GetSharedView=function() return {following=true} end}")
        self.assertIn("acompañando", self.advice(1)[0])

    def test_later_acceptance_can_unblock_a_current_prerequisite(self):
        goal = self.h.ns.guides["offers"].steps[1].goals[2]
        goal.pre = self.h.table([6, 55])
        self.assertEqual(self.advice(6), ("Acéptala para desbloquear el paso 1.", "ahora"))
        self.h.quest(55, delivered=True)
        self.assertEqual(self.advice(6)[1], "después")
        goal.preAll = self.h.table([6])
        self.assertEqual(self.advice(6)[1], "ahora")
        self.progress.review = True
        self.assertEqual(self.advice(6), ("Esta misión es una previa del paso 1.", "estado"))
        self.progress.review = None
        self.progress.skipped = self.h.table({"1:2": True})
        self.assertEqual(self.advice(6)[1], "después")

    def test_real_elwynn_books_are_a_personal_detour(self):
        self.h.load((ADDON / "Leveling.lua").read_text(encoding="utf-8"), "RutaXP", self.h.ns)
        self.h.call("SelectGuide", "forever/alliance/human/01-elwynn-forest")
        text, kind = self.advice(91777)
        self.assertEqual(kind, "opcional")
        for term in ("Jaspe", "Paxton", "daga"):
            self.assertIn(term, text)
        self.h.ns.DuoAuto = self.h.lua.eval("{agreement={}, GetSharedView=function() return {following=true} end}")
        self.h.quest(91777, delivered=True)
        self.assertEqual(self.advice(91777), (text, kind))
        self.h.ns.GetGuideTravel = self.h.lua.eval("function() return {waiting=true} end")
        self.assertEqual(self.advice(91777), (text, kind))
        self.h.ns.char.progress["forever/alliance/human/01-elwynn-forest"].review = True
        self.assertEqual(self.advice(91777), (text, kind))
        self.h.state.classToken = "WARRIOR"
        self.assertNotIn("daga", self.advice(91777)[0])
        self.h.quest(91777)
        self.h.ns.DuoAuto = None
        self.h.ns.GetGuideTravel = None
        self.h.call("SelectGuide", "offers")
        self.assertEqual(self.advice(91777)[1], "fuera")

    def test_unknown_id_does_not_guess_from_title_or_create_progress(self):
        for quest_id in (None, 0, -2, 1.5, "91777"):
            self.assertIsNone(self.advice(quest_id))
        self.h.ns.char.activeGuide = None
        self.assertEqual(self.advice(77)[1], "estado")
