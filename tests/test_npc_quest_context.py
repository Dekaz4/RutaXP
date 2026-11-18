"""Play through the actual NPC menu, offer parchment, and map button for both Wetlands visits."""
import unittest

from test_addon import ADDON, UI_STUBS
from test_duo_journey import primitive_copy
from test_quest_engine import QuestEngineHost

GUIDE = "forever/alliance/30-40/01-hillsbrad-foothills"

UI = r"""
local make = CreateFrame
UIParent:SetWidth(1400)
function UIParent:GetEffectiveScale() return 1 end
local function panel()
    local f=make()
    function f:IsVisible() return self.shown end
    function f:GetEffectiveScale() return 1 end
    function f:GetLeft() return 10 end
    function f:HookScript(key, fn) self.scripts[key]=fn end
    return f
end
QuestFrame=panel()
GossipFrame=panel()
QuestFrameGreetingPanel=panel()
QuestFrameDetailPanel=panel()
function CreateFrame(kind, name, parent, template)
    local f=make()
    if parent==QuestFrameDetailPanel or parent==QuestFrameGreetingPanel or parent==GossipFrame then
        TEST.card=f
    elseif kind=="Frame" and not parent then
        TEST.listener=f
    end
    return f
end
function GetQuestID() return TEST.openQuest end
function UnitGUID(unit)
    if unit == "npc" and TEST.npc then return "Creature-0-1-2-3-" .. TEST.npc .. "-AA" end
end
function GetNumAvailableQuests() return #TEST.offers end
function GetAvailableQuestInfo(i) return false, 30, false, false, TEST.offers[i] end
C_GossipInfo = {GetAvailableQuests=function()
    local result = {}
    for _, id in ipairs(TEST.offers) do result[#result+1]={questID=id} end
    return result
end}
TEST.offers={}
"""

class NPCContextTests(unittest.TestCase):
    def setUp(self):
        self.h = h = QuestEngineHost(catalog=True)
        h.load((ADDON / "GroupQuestData.lua").read_text(encoding="utf8"), "RutaXP", h.ns)
        h.initialize()
        h.state.level = 30
        h.ns.char.auto = False
        h.ns.char.includeGroupQuests = True
        h.call("SelectGuide", GUIDE)
        self.state = h.call("GetProgress", GUIDE)
        self.state.cursor, self.state.placed = 8, True
        h.lua.execute(UI_STUBS + UI)
        for file in ("QuestOfferAdvice", "NPCQuestContext", "QuestOfferUI"):
            h.load((ADDON / (file + ".lua")).read_text(encoding="utf8"), "RutaXP", h.ns)
        self.listener = h.state.listener

    def event(self, event, tick=True):
        self.listener.scripts.OnEvent(self.listener, event)
        if tick and self.listener.scripts.OnUpdate:
            self.listener.scripts.OnUpdate(self.listener)

    def howin(self):
        h = self.h
        h.state.npc, h.state.offers = 270637, h.table([98246])
        h.quest(98230, delivered=True)
        h.quest(98245, onQuest=True, complete=False)
        h.quest(98246, title="Tiempos difíciles")

    def captain(self):
        h = self.h
        self.state.cursor = 1
        h.state.npc = 2104
        h.quest(474, delivered=True)
        h.quest(98230, title="Esta era su tierra")
        h.ns.ResolveWaypointPoint = h.lua.eval("function(self, g) TEST.markedObject=g.object; TEST.frame=g.f; return {mapID=g.map,x=g.x/100,y=g.y/100} end")

    def test_both_menu_types_and_related_parchment_give_concrete_actions(self):
        self.howin()
        h = self.h
        journal, progress = primitive_copy(h.state.quests), primitive_copy(self.state)
        h.state.openQuest = 98246
        for event in ("GOSSIP_SHOW", "QUEST_GREETING", "QUEST_DETAIL"):
            with self.subTest(event=event):
                self.event(event)
                self.assertTrue(h.state.card.shown)
                text = h.state.card.label.text
                for instruction in ("Acepta «Tiempos difíciles»", "Ya llevas «Agujas de tajobuche»",
                                    "Hazlas juntas", "Muerte a los Faucedraco"):
                    self.assertIn(instruction, text)
                self.assertIsNone(h.state.card.marker)
        self.assertEqual(primitive_copy(h.state.quests), journal)
        self.assertEqual(primitive_copy(self.state), progress)

    def test_book_button_marks_confirmed_object_and_does_not_advance(self):
        self.captain()
        h = self.h
        before = primitive_copy(self.state)
        self.event("QUEST_GREETING")
        card = h.state.card
        self.assertEqual(card.button.text, "Marcar el libro")
        self.assertIn("Libro de hechizos andrajoso", card.label.text)
        h.globals.Click(card.button)
        self.assertEqual((h.state.waypointCalls,h.state.markedObject,h.state.frame), (1,671518,"e"))
        self.assertEqual(h.state.lastWaypoint.mapID, 1437)
        self.assertEqual(primitive_copy(self.state), before)
        # The player has accepted since the last draw. Re-check on click.
        h.quest(98223, onQuest=True, complete=True)
        h.globals.Click(card.button)
        self.assertEqual(h.state.waypointCalls, 1)
        self.event("QUEST_LOG_UPDATE")
        self.assertIn("Entrega «Viejas costumbres» aquí", card.label.text)
        self.assertFalse(card.button.shown)

    def test_solo_howin_still_combines_available_errands_without_promising_elite(self):
        self.howin()
        self.h.ns.char.includeGroupQuests = False
        self.event("GOSSIP_SHOW")
        text = self.h.state.card.label.text
        self.assertIn("Tiempos difíciles", text)
        self.assertIn("Agujas de tajobuche", text)
        self.assertIn("Hazlas juntas", text)
        self.assertNotIn("Muerte a los Faucedraco", text)

    def test_closing_or_switching_npc_cannot_mark_stale_destination(self):
        self.captain()
        h = self.h
        self.event("GOSSIP_SHOW")
        button = h.state.card.button
        h.state.npc = 999
        h.globals.Click(button)
        h.state.npc = 2104
        self.event("GOSSIP_CLOSED")
        h.globals.Click(button)
        self.assertEqual(h.state.waypointCalls, 0)
        self.assertFalse(h.state.card.shown)

    def test_unreadable_menu_unknown_journal_and_review_give_no_book_pin(self):
        self.captain()
        h = self.h
        self.state.review = True
        self.event("GOSSIP_SHOW")
        self.assertIsNone(h.state.card)
        self.state.review = False
        h.lua.execute("C_GossipInfo.GetAvailableQuests=function() error('unavailable') end")
        self.event("GOSSIP_SHOW")
        self.assertIsNone(h.state.card)
        h.lua.execute("C_QuestLog.IsOnQuest=function(id) if id~=98223 then return false end end")
        self.event("QUEST_GREETING")
        self.assertIsNone(h.state.card)
        self.state.cursor = 2
        self.event("QUEST_GREETING")
        self.assertIsNone(h.state.card.marker)
        self.assertNotIn("Busca", h.state.card.label.text)

    def test_two_distinct_book_sources_keep_the_advice_without_a_speculative_marker(self):
        self.captain()
        h = self.h
        for si, step in h.ns.guides[GUIDE].steps.items():
            if si > 1:
                for goal in step.goals.values():
                    if goal.quest == 98223 and goal.t == "accept":
                        goal.x = 75
        self.event("QUEST_GREETING")
        self.assertIn("Te falta «Viejas costumbres»", h.state.card.label.text)
        self.assertIsNone(h.state.card.marker)

    def test_unrelated_parchment_keeps_ordinary_offer_advice(self):
        self.howin()
        h = self.h
        h.state.openQuest = 404
        self.event("QUEST_DETAIL")
        self.assertIn("Fuera de este capítulo", h.state.card.label.text)
        self.assertNotIn("Faucedraco", h.state.card.label.text)

    def test_offered_followup_and_real_deliveries_win_over_old_schedule(self):
        self.howin()
        h = self.h
        h.state.offers = h.table([98246,98291])
        self.event("GOSSIP_SHOW")
        self.assertIsNone(h.state.card)
        h.state.offers = h.table([98291])
        h.quest(98245, delivered=True)
        h.quest(98246, delivered=True)
        self.state.cursor = 10
        self.event("GOSSIP_SHOW")
        self.assertIn("Acepta «Muerte a los Faucedraco»", h.state.card.label.text)
        self.assertNotIn("Agujas de tajobuche", h.state.card.label.text)
        self.assertNotIn("Tiempos difíciles", h.state.card.label.text)

    def test_second_outstanding_requirement_still_offers_the_book_marker(self):
        self.captain()
        h = self.h
        h.quest(474, delivered=False)
        self.event("QUEST_GREETING")
        card = h.state.card
        self.assertEqual(card.button.text, "Marcar el libro")
        self.assertIn("Derrotar a Nek'rosh", card.label.text)
        self.assertIn("Viejas costumbres", card.label.text)
        self.assertEqual(card.marker.object, 671518)

    def test_unexplained_missing_current_offer_does_not_guess_a_location(self):
        self.howin()
        h = self.h
        h.state.offers = h.table([])
        h.quest(98291, delivered=True)
        self.event("GOSSIP_SHOW")
        self.assertIn("El NPC aún no ofrece «Tiempos difíciles»", h.state.card.label.text)
        self.assertIsNone(h.state.card.marker)

if __name__ == "__main__":
    unittest.main()
