"""Engine regressions against the actual addon, executed in LuaJIT 2.1.

Run from the project directory with ``python -m unittest discover -s tests -v``.
Only the WoW host APIs and visual window are mocked; addon logic is loaded from
the shipping Lua files with WoW's (addonName, namespace) loader convention.
"""

from pathlib import Path
import unittest

from lupa.luajit21 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "RutaXP"

WOW_STUBS = r"""
TEST = {
    level = 1, faction = "Alliance", quests = {}, entries = {},
    messages = {}, waypointAllowed = true, waypointSuccess = true,
    waypointCalls = 0, superTrackCalls = 0, mapID = 37, x = .42, y = .63
}
WOW_PROJECT_CAMELOT = 18
WOW_PROJECT_ID = 18
SlashCmdList = {}
function UnitFactionGroup() return TEST.faction end
function UnitLevel() return TEST.level end
function GetBuildInfo() return "12.0.1", "67708", "test", 120001 end
function date() return "19/10 18:00" end
DEFAULT_CHAT_FRAME = {}
function DEFAULT_CHAT_FRAME:AddMessage(message)
    TEST.messages[#TEST.messages + 1] = message
end
function CreateFrame()
    local frame = { events = {}, scripts = {} }
    function frame:RegisterEvent(event) self.events[event] = true end
    function frame:SetScript(event, handler) self.scripts[event] = handler end
    return frame
end
C_QuestLog = {}
local function quest(id) return TEST.quests[id] or {} end
function C_QuestLog.GetTitleForQuestID(id) return quest(id).title end
function C_QuestLog.IsQuestFlaggedCompleted(id) return quest(id).delivered == true end
function C_QuestLog.IsOnQuest(id) return quest(id).onQuest == true end
function C_QuestLog.IsComplete(id) return quest(id).complete == true end
function C_QuestLog.GetQuestObjectives(id) return quest(id).objectives end
function C_QuestLog.GetNumQuestLogEntries() return #TEST.entries end
function C_QuestLog.GetInfo(index) return TEST.entries[index] end
function IsQuestFlaggedCompleted(id) return quest(id).legacyDelivered == true end
C_Map = {}
function C_Map.GetBestMapForUnit() return TEST.mapID end
function C_Map.GetPlayerMapPosition()
    if not TEST.positionUnavailable then
        return { GetXY = function() return TEST.x, TEST.y end }
    end
end
function C_Map.CanSetUserWaypointOnMap() return TEST.waypointAllowed end
function C_Map.SetUserWaypoint(point)
    TEST.waypointCalls = TEST.waypointCalls + 1
    TEST.lastWaypoint = point
    return TEST.waypointSuccess
end
UiMapPoint = {}
function UiMapPoint.CreateFromCoordinates(mapID, x, y)
    return { mapID = mapID, x = x, y = y }
end
C_SuperTrack = {}
function C_SuperTrack.SetSuperTrackedUserWaypoint(enabled)
    TEST.superTrackCalls = TEST.superTrackCalls + 1
    TEST.superTracked = enabled
end
function InstallFakeUI(ns)
    function ns:CreateUI()
        self.window = { shown = false }
        function self.window:Show() self.shown = true end
        function self.window:Hide() self.shown = false end
        function self.window:IsShown() return self.shown end
    end
    function ns:RefreshUI() TEST.refreshes = (TEST.refreshes or 0) + 1 end
    function ns:ToggleWindow()
        if self.window:IsShown() then self.window:Hide() else self.window:Show() end
    end
end
function FireEvent(ns, event, ...)
    ns.events.scripts.OnEvent(ns.events, event, ...)
end
"""

UI_STUBS = r"""
StaticPopupDialogs = {}
BackdropTemplateMixin = {}
local methods = {}
local noopMethods = {
    "SetBackdrop", "SetBackdropColor", "SetBackdropBorderColor", "SetPoint",
    "SetJustifyH", "SetJustifyV", "SetTextColor", "SetMovable",
    "SetClampedToScreen", "EnableMouse", "RegisterForDrag", "SetFrameStrata",
    "SetScale", "SetAutoFocus", "SetMaxLetters", "SetScrollChild",
    "SetStatusBarTexture", "SetStatusBarColor", "SetMinMaxValues", "SetAllPoints",
    "SetColorTexture", "SetSpacing", "ClearAllPoints", "ClearFocus",
    "StartMoving", "StopMovingOrSizing", "SetThickness", "SetStartPoint", "SetEndPoint",
    "SetToplevel", "SetWordWrap", "RegisterForClicks", "SetClipsChildren", "SetFrameLevel"
}
for _, name in ipairs(noopMethods) do methods[name] = function() end end
function methods:GetFrameLevel() return 1 end
function methods:GetRight() return 600 end
function methods:RegisterEvent(event) self.events[event] = true end
function methods:SetScript(name, callback) self.scripts[name] = callback end
function methods:SetSize(width, height) self.width, self.height = width, height end
function methods:SetWidth(width) self.width = width end
function methods:SetHeight(height) self.height = height end
function methods:GetWidth() return self.width or 1920 end
function methods:GetHeight() return self.height or 1080 end
function methods:SetText(text) self.text = text end
function methods:GetText() return self.text or "" end
function methods:Show() self.shown = true end
function methods:Hide() self.shown = false end
function methods:SetShown(value) self.shown = not not value end
function methods:IsShown() return self.shown end
function methods:SetChecked(value) self.checked = value end
function methods:GetChecked() return self.checked end
function methods:SetEnabled(value) self.enabled = value end
function methods:SetValue(value) self.value = value end
function methods:SetVerticalScroll(value) self.scroll = value end
function methods:GetVerticalScroll() return self.scroll or 0 end
function methods:GetVerticalScrollRange() return 10000 end
function methods:GetStringHeight() return math.ceil(#(self.text or "") / 55) * 15 end
function methods:GetPoint() return "CENTER", UIParent, "CENTER", 0, 0 end
function CreateFrame()
    return setmetatable({ events = {}, scripts = {}, shown = true }, { __index = methods })
end
function methods:CreateFontString() return CreateFrame() end
function methods:CreateTexture() return CreateFrame() end
function methods:CreateLine() return CreateFrame() end
UIParent = CreateFrame()
function Click(frame) frame.scripts.OnClick(frame) end
function ChangeText(frame, text)
    frame:SetText(text)
    if frame.scripts.OnTextChanged then frame.scripts.OnTextChanged(frame) end
end
"""


class AddonHost:
    def __init__(self, catalog=False, real_ui=False):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(WOW_STUBS)
        if real_ui:
            self.lua.execute(UI_STUBS)
        self.globals = self.lua.globals()
        self.load = self.lua.eval(
            "function(source, name, ns) "
            "local chunk, err = loadstring(source); "
            "if not chunk then error(err) end; chunk(name, ns) end"
        )
        self.catalog = catalog
        self.real_ui = real_ui
        self.new_namespace()

    def table(self, value):
        return self.lua.table_from(value, recursive=True)

    @property
    def state(self):
        return self.globals.TEST

    def new_namespace(self):
        self.ns = self.lua.table()
        self.load((ADDON / "Core.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        if self.catalog:
            self.load((ADDON / "Guides.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        if self.real_ui:
            self.load((ADDON / "UI.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        else:
            self.globals.InstallFakeUI(self.ns)
        return self.ns

    def call(self, name, *args):
        return self.ns[name](self.ns, *args)

    def fire(self, event, *args):
        self.globals.FireEvent(self.ns, event, *args)

    def initialize(self):
        self.fire("ADDON_LOADED", "RutaXP")
        self.fire("PLAYER_LOGIN")

    def guide(self, id="test", steps=None, **fields):
        fields.update(id=id, title=fields.pop("title", id), steps=steps or [
            {"title": "First manual step"}, {"title": "Second manual step"}
        ])
        result = self.call("RegisterGuide", self.table(fields))
        if result is not True:
            raise AssertionError(f"Cannot register fixture: {result}")
        return self.ns.guides[id]

    def cursor(self, id="test"):
        return self.call("GetProgress", id).cursor

    def quest(self, id, **fields):
        self.state.quests[id] = self.table(fields)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.host = AddonHost()
        self.host.guide()
        self.host.initialize()

    def test_loader_initializes_once_after_correct_addon_load(self):
        host = AddonHost()
        host.guide()
        host.fire("ADDON_LOADED", "OtherAddon")
        host.fire("PLAYER_LOGIN")
        self.assertIsNone(host.ns.initialized)
        host.initialize()
        first_char = host.ns.char
        host.fire("PLAYER_LOGIN")
        self.assertTrue(host.ns.initialized)
        self.assertTrue(host.lua.eval("function(a,b) return a == b end")(first_char, host.ns.char))
        self.assertTrue(host.ns.window.shown)

    def test_manual_progress_is_independent_for_each_guide(self):
        h = self.host
        h.guide("other")
        h.call("Next")
        h.call("SelectGuide", "other")
        self.assertEqual(h.cursor("other"), 1)
        h.call("Next")
        h.call("Next")
        h.call("SelectGuide", "test")
        self.assertEqual(h.cursor("test"), 2)
        self.assertEqual(h.cursor("other"), 3)

    def test_saved_progress_is_per_character_and_survives_reload(self):
        h = self.host
        h.call("Next")
        first_char = h.ns.char
        h.globals.RutaXPCharDB = h.lua.table()
        h.new_namespace()
        h.guide()
        h.initialize()
        self.assertEqual(h.cursor(), 1)
        h.call("Next")
        h.call("Next")
        h.globals.RutaXPCharDB = first_char
        h.new_namespace()
        h.guide()
        h.initialize()
        self.assertEqual(h.cursor(), 2)

    def test_accept_complete_and_turnin_are_distinct(self):
        h = self.host
        h.guide("quests", steps=[
            {"title": "Accept", "action": "accept", "questID": 42},
            {"title": "Complete", "action": "complete", "questID": 42},
            {"title": "Turn in", "action": "turnin", "questID": 42},
        ])
        h.call("SelectGuide", "quests")
        self.assertEqual(h.cursor("quests"), 1)
        h.quest(42, onQuest=True)
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(h.cursor("quests"), 2)
        h.quest(42, onQuest=True, complete=True)
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(h.cursor("quests"), 3)
        h.fire("QUEST_TURNED_IN", 42)
        self.assertEqual(h.cursor("quests"), 4)

    def test_already_delivered_quests_skip_all_quest_actions(self):
        h = self.host
        for quest_id, field in [(77, "delivered"), (78, "legacyDelivered")]:
            h.quest(quest_id, **{field: True})
            for action in ["accept", "complete", "turnin", "objective"]:
                with self.subTest(quest_id=quest_id, action=action):
                    self.assertTrue(h.call("IsStepComplete", h.table({
                        "title": action, "questID": quest_id, "action": action, "objective": 1
                    })))

    def test_abandoning_a_quest_never_counts_as_turning_it_in(self):
        h = self.host
        h.guide("delivery", steps=[{"title": "Deliver", "action": "turnin", "questID": 42}])
        h.call("SelectGuide", "delivery")
        h.quest(42, onQuest=True, complete=True)
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(h.cursor("delivery"), 1)
        h.quest(42)
        h.fire("QUEST_REMOVED", 42)
        self.assertEqual(h.cursor("delivery"), 1)
        self.assertIsNone(h.ns.turnedIn[42])

    def test_reaccepting_a_repeatable_clears_cached_delivery(self):
        for acceptance_args in [(42,), (7, 42)]:
            with self.subTest(acceptance_args=acceptance_args):
                h = AddonHost()
                h.guide("rep", steps=[
                    {"title": "Complete", "action": "complete", "questID": 42},
                    {"title": "Turn in", "action": "turnin", "questID": 42},
                ])
                h.initialize()
                h.call("SelectGuide", "rep")
                h.fire("QUEST_TURNED_IN", 42)
                self.assertTrue(h.ns.turnedIn[42])
                h.quest(42, onQuest=True, complete=False, delivered=False)
                h.fire("QUEST_ACCEPTED", *acceptance_args)
                self.assertIsNone(h.ns.turnedIn[42])
                h.call("ResetGuide", "rep")
                h.ns.char.progress["rep"].review = nil = None
                h.call("Sync")
                self.assertEqual(h.cursor("rep"), 1)

    def test_previous_allows_review_without_automatic_skip(self):
        h = self.host
        h.guide("review", steps=[
            {"title": "Accepted", "action": "accept", "questID": 42},
            {"title": "Delivered", "action": "turnin", "questID": 42},
        ])
        h.quest(42, delivered=True)
        h.call("SelectGuide", "review")
        self.assertEqual(h.cursor("review"), 3)
        h.call("Previous")
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(h.cursor("review"), 2)
        self.assertTrue(h.call("GetProgress", "review").review)
        h.call("Next")
        self.assertEqual(h.cursor("review"), 3)
        self.assertIsNone(h.call("GetProgress", "review").review)

    def test_manual_last_step_completes_and_stays_at_end(self):
        h = self.host
        h.call("Next")
        h.call("Next")
        guide, step, state = h.call("GetCurrent")
        self.assertEqual(state.cursor, len(guide.steps) + 1)
        self.assertIsNone(step)
        h.call("Next")
        self.assertEqual(h.cursor(), 3)
        h.call("Previous")
        self.assertEqual(h.cursor(), 2)
        h.call("ResetGuide", "test")
        self.assertEqual(h.cursor(), 1)

    def test_level_and_specific_quest_objective_completion(self):
        h = self.host
        level_step = h.table({"title": "Level", "action": "level", "level": 10})
        self.assertFalse(h.call("IsStepComplete", level_step))
        h.state.level = 10
        self.assertTrue(h.call("IsStepComplete", level_step))
        h.quest(42, objectives=[{"text": "First", "finished": True}, {"text": "Second", "finished": False}])
        for index, expected in [(1, True), (2, False), (3, None)]:
            step = h.table({"title": "Objective", "action": "objective", "questID": 42, "objective": index})
            self.assertEqual(bool(h.call("IsStepComplete", step)), bool(expected))
        rendered = h.call("GetObjectives", h.table({"questID": 42}))
        self.assertIn("First", rendered)
        self.assertIn("Second", rendered)

    def test_faction_and_search_filter_title_kind_and_summary(self):
        h = self.host
        h.guide("alliance", title="Elwynn Forest", faction="Alliance", kind="Leveling", summary="Starter route")
        h.guide("horde", title="Durotar", faction="Horde", kind="Leveling")
        h.guide("neutral", title="Cooking", summary="Practice recipes")
        def ids(search="", all_factions=False):
            return [guide.id for _, guide in h.call("GetVisibleGuides", search, all_factions).items()]
        self.assertEqual(ids("  eLwYnN  "), ["alliance"])
        self.assertEqual(ids("leveling"), ["alliance"])
        self.assertEqual(ids("recipes"), ["neutral"])
        self.assertEqual(ids("durotar"), [])
        self.assertEqual(ids("durotar", True), ["horde"])
        self.assertEqual(ids("%"), [])
        h.state.faction = "Horde"
        self.assertIn("horde", ids())
        self.assertNotIn("alliance", ids())

    def test_waypoint_permission_denial_does_not_set_or_supertrack(self):
        h = self.host
        h.guide("point", steps=[{"title": "Go", "waypoint": {"mapID": 37, "x": .1, "y": .2}}])
        h.call("SelectGuide", "point")
        h.state.waypointAllowed = False
        self.assertFalse(h.call("Navigate"))
        self.assertEqual(h.state.waypointCalls, 0)
        self.assertEqual(h.state.superTrackCalls, 0)

    def test_waypoint_failure_does_not_supertrack_and_success_does(self):
        h = self.host
        h.guide("point", steps=[{"title": "Go", "waypoint": {"mapID": 37, "x": .1, "y": .2}}])
        h.call("SelectGuide", "point")
        h.state.waypointSuccess = False
        self.assertFalse(h.call("Navigate"))
        self.assertEqual(h.state.superTrackCalls, 0)
        h.state.waypointSuccess = True
        self.assertTrue(h.call("Navigate"))
        self.assertEqual(h.state.superTrackCalls, 1)
        self.assertEqual(h.state.lastWaypoint.mapID, 37)

    def test_missing_waypoint_api_fails_without_supertrack(self):
        h = self.host
        h.guide("point", steps=[{"title": "Go", "waypoint": {"mapID": 37, "x": .1, "y": .2}}])
        h.call("SelectGuide", "point")
        h.globals.C_Map.SetUserWaypoint = None
        self.assertFalse(h.call("Navigate"))
        self.assertEqual(h.state.superTrackCalls, 0)

    def test_validation_rejects_invalid_or_duplicate_guide_without_insertion(self):
        h = self.host
        invalid = [
            {}, {"id": "", "title": "Bad", "steps": [{"title": "Step"}]},
            {"id": "bad", "steps": [{"title": "Step"}]},
            {"id": "bad", "title": "Bad", "steps": []},
            {"id": "bad", "title": "Bad", "steps": [{}]},
            {"id": "test", "title": "Duplicate", "steps": [{"title": "Step"}]},
        ]
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                ok, message = h.call("RegisterGuide", h.table(candidate))
                self.assertFalse(ok)
                self.assertIsInstance(message, str)
        self.assertEqual(len(h.ns.order), 1)

    def test_corrupt_saved_database_fields_are_recovered(self):
        h = self.host
        h.globals.RutaXPDB = h.table({"customGuides": "invalid", "recording": "missing"})
        h.globals.RutaXPCharDB = h.table({"progress": "invalid", "activeGuide": "missing", "recording": "old"})
        h.new_namespace()
        h.guide()
        h.initialize()
        self.assertEqual(h.cursor(), 1)
        self.assertEqual(h.ns.db.customGuides, "invalid")
        self.assertEqual(h.ns.char.recording, "old")


class CatalogTests(unittest.TestCase):
    def test_shipping_catalog_loads_with_unique_valid_nonempty_guides(self):
        self.assertTrue((ADDON / "Guides.lua").is_file(), "Shipping Guides.lua is missing")
        h = AddonHost(catalog=True)
        ids = [guide_id for _, guide_id in h.ns.order.items()]
        self.assertGreater(len(ids), 1, "The requested library must offer multiple choices")
        self.assertEqual(len(ids), len(set(ids)))
        for guide_id in ids:
            with self.subTest(guide=guide_id):
                guide = h.ns.guides[guide_id]
                self.assertTrue(guide.title.strip())
                self.assertGreater(len(guide.steps), 0)
                self.assertIn(guide.faction, (None, "Alliance", "Horde"))
                for _, step in guide.steps.items():
                    self.assertTrue(step.title.strip())
                    if step.waypoint:
                        self.assertGreater(step.waypoint.mapID, 0)
                        self.assertGreaterEqual(step.waypoint.x, 0)
                        self.assertLessEqual(step.waypoint.x, 1)
                        self.assertGreaterEqual(step.waypoint.y, 0)
                        self.assertLessEqual(step.waypoint.y, 1)
                    if step.action in ("accept", "complete", "turnin", "objective"):
                        self.assertGreater(step.questID, 0)
        h.initialize()
        self.assertIsNotNone(h.ns.guides[h.ns.char.activeGuide])
        self.assertGreater(len(h.call("GetVisibleGuides", "", False)), 0)


class UISmokeTests(unittest.TestCase):
    def test_real_ui_initializes_filters_and_tracks_actual_engine_state(self):
        h = AddonHost(catalog=True, real_ui=True)
        h.initialize()
        self.assertTrue(h.ns.window.shown)
        self.assertFalse(h.ns.tracker.shown)
        self.assertGreater(len(h.ns.rows), 0)
        active, _, _ = h.call("GetCurrent")
        self.assertEqual(h.ns.guideTitle.text, active.title)
        h.globals.ChangeText(h.ns.search, "No guide has this exact search phrase 193876")
        self.assertTrue(h.ns.noResults.shown)
        self.assertFalse(h.ns.rows[1].shown)
        h.globals.ChangeText(h.ns.search, "")
        self.assertFalse(h.ns.noResults.shown)
        h.call("ToggleWindow")
        self.assertFalse(h.ns.window.shown)
        self.assertTrue(h.ns.tracker.shown)
        h.guide("ui-finish", steps=[{"title": "One step"}])
        h.call("SelectGuide", "ui-finish")
        h.globals.Click(h.ns.trackerNext)
        self.assertEqual(h.cursor("ui-finish"), 2)
        self.assertFalse(h.ns.nextButton.enabled)
        self.assertFalse(h.ns.trackerNext.enabled)
        self.assertEqual(h.ns.trackerProgress.text, "Completada")
        h.globals.Click(h.ns.trackerPrevious)
        self.assertEqual(h.cursor("ui-finish"), 1)
        self.assertTrue(h.ns.nextButton.enabled)


if __name__ == "__main__":
    unittest.main()
