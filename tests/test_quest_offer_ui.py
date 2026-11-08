"""Exercise the offer parchment and the shipped advice provider in Lua."""
import unittest

from test_addon import ADDON, UI_STUBS
from test_quest_engine import QuestEngineHost


PARCHMENT = """
local frame = CreateFrame
UIParent:SetWidth(1000)
function UIParent:GetEffectiveScale() return 1 end
function MakeParchment()
    QuestFrame = frame()
    function QuestFrame:GetEffectiveScale() return 1 end
    function QuestFrame:GetRight() return TEST.parchmentLeft + 330 end
    function QuestFrame:GetLeft() return TEST.parchmentLeft end
    QuestFrameDetailPanel = frame()
    local detail = QuestFrameDetailPanel
    function detail:HookScript(name, callback) self.scripts[name] = callback end
    function detail:IsVisible() return TEST.parchmentShown end
end
function CreateFrame(kind, name, parent)
    local f = frame()
    if parent and parent == QuestFrameDetailPanel then
        TEST.advice = f
        function f:EnableMouse(enable) self.mouse = enable end
        function f:SetClampedToScreen(value) self.clamped = value end
        function f:SetPoint(point, target, anchor) self.point, self.anchor = point, anchor end
        function f:CreateFontString() self.label = frame(); return self.label end
    else
        TEST.events = f
    end
    return f
end
function hooksecurefunc(owner, name, callback)
    local old = owner[name]
    owner[name] = function(...) old(...); callback(...) end
end
function GetQuestID() return TEST.offeredID end
function issecretvalue(value) return value == TEST.secret end
TEST.secret = {}
TEST.parchmentLeft = 20
"""


class QuestOfferUITests(unittest.TestCase):
    def setUp(self):
        h = self.h = QuestEngineHost()
        h.group([{"t": "accept", "quest": 100}], next_goals=[{"t": "accept", "quest": 101}])
        h.initialize()
        h.lua.execute(UI_STUBS + PARCHMENT)
        for module in ("QuestOfferAdvice.lua", "QuestOfferUI.lua"):
            h.load((ADDON / module).read_text(encoding="utf8"), "RutaXP", h.ns)
        self.events = h.state.events

    def event(self, name, *args):
        self.assertTrue(self.events.events[name])
        self.events.scripts.OnEvent(self.events, name, *args)

    def tick(self):
        if self.events.scripts.OnUpdate:
            self.events.scripts.OnUpdate(self.events)
        self.assertIsNone(self.events.scripts.OnUpdate)

    def offer(self, qid):
        self.h.state.parchmentShown = True
        self.h.state.offeredID = qid
        self.event("QUEST_DETAIL")

    def test_parchment_follows_manual_progress_and_quest_changes_without_polling(self):
        h = self.h
        h.globals.MakeParchment()
        self.offer(101)
        self.tick()
        card = h.state.advice
        def check(qid):
            self.assertTrue(card.shown)
            self.assertIn(h.call("GetQuestOfferAdvice", qid)[0], card.label.text)
        check(101)
        self.assertTrue(card.clamped)
        self.assertFalse(card.mouse)
        self.assertEqual((card.point, card.anchor), ("TOPLEFT", "TOPRIGHT"))
        before = card.label.text
        h.call("Next")
        self.tick()
        check(101)
        self.assertNotEqual(before, card.label.text)
        self.offer(404)
        self.assertFalse(card.shown)
        h.state.parchmentLeft = 660
        self.tick()
        check(404)
        self.assertEqual((card.point, card.anchor), ("TOPRIGHT", "TOPLEFT"))
        self.event("QUEST_PROGRESS")
        h.call("RefreshUI")
        self.tick()
        self.assertFalse(card.shown)

    def test_waits_for_load_and_visible_detail_with_a_matching_readable_id(self):
        h = self.h
        self.offer(100)
        self.tick()
        self.assertIsNone(h.state.advice)
        h.globals.MakeParchment()
        h.state.parchmentShown = False
        self.event("ADDON_LOADED", "Blizzard_UIPanels_Game")
        self.tick()
        self.assertIsNone(h.state.advice)
        h.state.parchmentShown = True
        h.globals.QuestFrameDetailPanel.scripts.OnShow()
        h.state.offeredID = 101  # Another quest has already taken over.
        self.tick()
        self.assertIsNone(h.state.advice)
        for value in [0, -1, "100", h.state.secret]:
            self.offer(value)
            self.tick()
            self.assertIsNone(h.state.advice)
        self.offer(101)
        self.tick()
        self.assertTrue(h.state.advice.shown)

    def test_autoaccept_or_closing_before_redraw_never_reopens_old_advice(self):
        h = self.h
        h.globals.MakeParchment()
        self.offer(100)
        self.event("QUEST_ACCEPTED", 1, 100)
        self.tick()
        self.assertIsNone(h.state.advice)
        self.offer(101)
        self.event("QUEST_FINISHED")
        self.tick()
        self.assertIsNone(h.state.advice)
        self.offer(101)
        self.tick()
        detail, card = h.globals.QuestFrameDetailPanel, h.state.advice
        self.event("QUEST_ACCEPTED", 999)
        self.assertTrue(card.shown)
        h.state.parchmentShown = False
        detail.scripts.OnHide()
        self.assertFalse(card.shown)
        self.tick()
        h.state.parchmentShown = True
        detail.scripts.OnShow()
        self.tick()
        self.assertFalse(card.shown)
