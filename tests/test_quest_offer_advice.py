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

    def enable_early(self, *quest_ids):
        self.h.ns.earlyQuestOffers = self.h.table({qid: True for qid in quest_ids})
        self.h.ns.GetEarlyQuestSpace = self.h.lua.eval("function() return TEST.hasSpace end")
        self.h.state.hasSpace = True
        self.h.ns.char.auto = True

    def early(self, quest_id):
        return self.h.call("GetEarlyQuestOffer", quest_id)

    def test_profitable_future_accept_requires_capacity_auto_and_a_later_acceptance(self):
        self.enable_early(1, 6, 7, 8, 10, 11)
        self.assertEqual(self.early(6), ("Puedes cogerla ahora para el paso 2.", "ahora"))
        self.assertEqual(self.advice(6), self.early(6))
        for qid in (1, 7, 8, 9, 10, 11, None, "6"):
            self.assertIsNone(self.early(qid))
        self.h.ns.char.optional = True
        self.assertEqual(self.early(7)[1], "ahora")
        self.h.ns.char.auto = False
        self.assertIsNone(self.early(6))
        self.assertEqual(self.advice(6)[1], "después")
        self.h.ns.char.auto = True
        for room in (False, None):
            self.h.state.hasSpace = room
            self.assertIsNone(self.early(6))
        self.h.ns.GetEarlyQuestSpace = None
        self.assertIsNone(self.early(6))

    def test_future_accept_checks_the_actual_row_character_and_quest_state(self):
        self.enable_early(9)
        step = self.h.ns.guides["offers"].steps[3]
        goal = step.goals[3]
        self.progress.skipped = self.h.table({"1:3": True})
        self.assertIsNotNone(self.early(9))
        self.progress.skipped["3:3"] = True
        self.assertIsNone(self.early(9))
        self.progress.skipped["3:3"] = None
        self.progress.confirmed = self.h.table({"3:3": True})
        self.assertIsNone(self.early(9))
        self.progress.confirmed["3:3"] = None
        goal.pre = self.h.table([90, 91])
        goal.preAll = self.h.table([92])
        self.h.quest(91, delivered=True)
        self.assertIsNone(self.early(9))
        self.h.quest(92, delivered=True)
        self.assertIsNotNone(self.early(9))
        goal.parent = 93
        self.assertIsNone(self.early(9))
        self.h.quest(93, onQuest=True)
        goal.minLevel = 11
        self.assertIsNone(self.early(9))
        self.h.state.level = 11
        self.assertIsNotNone(self.early(9))
        goal.closedBy = self.h.table([94])
        self.h.quest(94, onQuest=True)
        self.assertIsNone(self.early(9))
        self.h.quest(94)
        step.only = self.h.table({"classes": ["WARRIOR"]})
        self.assertIsNone(self.early(9))
        step.only = None
        step.requiresSkill = self.h.table({"id": 202, "rank": 25})
        self.h.ns.GetProfessionRank = self.h.lua.eval("function() return TEST.rank end")
        for rank in (None, 0, 24):
            self.h.state.rank = rank
            self.assertIsNone(self.early(9))
        self.h.state.rank = 25
        self.assertIsNotNone(self.early(9))
        for mark in ("onQuest", "delivered"):
            self.h.quest(9, **{mark: True})
            self.assertIsNone(self.early(9))

    def test_early_accept_is_paused_while_reviewing_travelling_or_waiting_for_partner(self):
        self.enable_early(6)
        self.progress.review = True
        self.assertIsNone(self.early(6))
        self.progress.review = None
        self.h.ns.GetGuideTravel = self.h.lua.eval("function() return {waiting=true} end")
        self.assertIsNone(self.early(6))
        self.h.ns.GetGuideTravel = None
        self.h.ns.char.duo = self.h.table({"enabled": True, "wait": True, "autoSession": {}})
        self.h.ns.DuoAuto = self.h.lua.eval("{ShouldPauseAutomation=function() return TEST.pause end}")
        self.h.ns.Duo = self.h.lua.eval("{ShouldWaitForStep=function() return TEST.wait end}")
        self.h.state.pause = True
        self.assertIsNone(self.early(6))
        self.h.state.pause = False
        self.h.state.wait = True
        self.assertIsNone(self.early(6))
        self.h.state.wait = False
        self.assertIsNotNone(self.early(6))

    def test_only_the_unique_compatible_immediate_successor_can_supply_early_offers(self):
        start = self.h.ns.guides["offers"]
        start.nextChoices = self.h.table(["b", "c"])
        self.h.guide("b", steps=[{"title": "B", "goals": [{"t": "accept", "quest": 20}]}], next="d")
        self.h.guide("c", steps=[{"title": "C", "goals": [{"t": "accept", "quest": 21}]}])
        self.h.guide("d", steps=[{"title": "D", "goals": [{"t": "accept", "quest": 22}]}])
        self.enable_early(20, 21, 22)
        self.assertIsNone(self.early(20))
        self.assertIsNone(self.early(21))
        self.h.ns.guides["c"].classes = self.h.table(["MAGE"])
        self.assertIsNotNone(self.early(20))
        self.assertIsNone(self.early(21))
        self.assertIsNone(self.early(22))

    def test_thomas_can_offer_109_for_the_first_gryan_visit_without_selecting_westfall(self):
        self.h.load((ADDON / "Leveling.lua").read_text(encoding="utf-8"), "RutaXP", self.h.ns)
        elwynn, westfall = "forever/alliance/human/01-elwynn-forest", "forever/alliance/02-westfall"
        self.h.call("SelectGuide", elwynn)
        self.enable_early(109)
        previous_cursor = self.h.ns.char.progress[elwynn].cursor
        self.assertIsNone(self.h.ns.char.progress[westfall])
        for method in ("GetCurrent", "GetProgress", "SelectGuide", "Sync", "HandleQuestAutomation"):
            self.h.ns[method] = self.h.lua.eval("function() error('Offer lookup modified progress') end")
        text, kind = self.early(109)
        self.assertEqual(kind, "ahora")
        self.assertIn("Gryan", text)
        self.assertIn("Poniente", text)
        self.assertEqual(self.advice(109), (text, kind))
        self.h.ns.char.auto = False
        self.assertIsNone(self.early(109))
        self.assertIn("Poniente", self.advice(109)[0])
        self.h.ns.char.auto = True
        self.h.state.hasSpace = False
        self.assertIsNone(self.early(109))
        self.assertEqual(self.advice(109)[1], "después")
        self.assertIn("Poniente", self.advice(109)[0])
        self.assertIsNone(self.h.ns.char.progress[westfall])
        self.assertEqual(self.h.ns.char.progress[elwynn].cursor, previous_cursor)
        self.assertEqual(self.h.ns.char.activeGuide, elwynn)
        self.h.state.hasSpace = True
        for saved in ({"cursor": 3}, {"cursor": 2, "skipped": {"2:1": True}},
                      {"cursor": 2, "confirmed": {"2:1": True}}, {"cursor": 1, "review": True}):
            self.h.ns.char.progress[westfall] = self.h.table(saved)
            self.assertIsNone(self.early(109), saved)
        self.h.ns.char.progress[westfall] = self.h.table({"cursor": 2, "skipped": {"1:1": True}})
        self.assertIsNotNone(self.early(109))

    def test_books_early_accept_requires_optional_group_previous_quest_and_space(self):
        self.h.load((ADDON / "Leveling.lua").read_text(encoding="utf-8"), "RutaXP", self.h.ns)
        self.h.call("SelectGuide", "forever/alliance/human/01-elwynn-forest")
        self.enable_early()
        self.h.lua.execute("function IsInGroup() return TEST.inGroup end")
        self.h.ns.char.optional = False
        self.assertIsNone(self.early(91777))
        self.h.ns.char.optional = True
        self.h.state.inGroup = True
        self.assertIsNone(self.early(91777))
        self.h.quest(91775, delivered=True)
        self.h.state.inGroup = False
        self.assertIsNone(self.early(91777))
        self.h.state.inGroup = True
        self.assertEqual(self.early(91777), self.advice(91777))
        self.h.ns.char.optional = False
        self.assertIsNone(self.early(91777))
        self.h.ns.char.optional = True
        self.h.state.hasSpace = False
        self.assertIsNone(self.early(91777))
        self.h.state.hasSpace = True
        self.h.quest(91777, delivered=True)
        self.assertIsNone(self.early(91777))

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
