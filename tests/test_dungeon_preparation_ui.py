"""Exercise the dungeon preparation launcher's login, browsing and activation paths."""
import unittest

from lupa.lua51 import LuaRuntime

from test_addon import ADDON, TOOLTIP_STUBS, UI_STUBS


HOST = """
local baseCreate = CreateFrame
local methods = getmetatable(UIParent).__index
frames, namedCounts = {}, {}
function CreateFrame(kind, name, parent, template)
    local frame = baseCreate()
    frame.parent, frame.frameName, frame.template = parent, name, template
    frame.kind = kind
    table.insert(frames, frame)
    if name then
        namedCounts[name] = (namedCounts[name] or 0) + 1
        _G[name] = frame
    end
    if template == "BasicFrameTemplateWithInset" then frame.TitleText = frame:CreateFontString() end
    return frame
end
function methods:GetParent() return self.parent end
function methods:SetPoint(...) self.point = {...} end
function methods:GetPoint() return unpack(self.point or {}) end
function methods:GetCenter() return self.cx or 200, self.cy or 200 end
function methods:GetEffectiveScale() return 1 end
function methods:IsMouseOver() return self == hover end
function methods:EnableMouseWheel(value) self.wheel = value end
function methods:GetName() return self.frameName end
function methods:SetScrollChild(child) self.scrollChild = child end
function methods:GetScript(name) return self.scripts[name] end
function methods:HookScript(name, callback)
    local previous = self.scripts[name]
    self.scripts[name] = function(...)
        if previous then previous(...) end
        callback(...)
    end
end
function methods:SetTexture(texture) self.texture = texture end
function methods:IsEnabled() return self.enabled ~= false end
function methods:Enable() self.enabled = true end
function methods:Disable() self.enabled = false end
for _,name in ipairs({"SetHighlightTexture", "SetNormalTexture", "SetTexCoord", "SetDrawLayer",
                       "SetVertexColor", "SetFontObject", "SetPushedTexture", "SetAlpha"}) do
    methods[name] = function() end
end
function methods:Show()
    local change = not self.shown
    self.shown = true
    if change and self.scripts.OnShow then self.scripts.OnShow(self) end
end
function methods:Hide()
    local change = self.shown
    self.shown = false
    if change and self.scripts.OnHide then self.scripts.OnHide(self) end
end
function methods:SetShown(shown) if shown then self:Show() else self:Hide() end end
function methods:CreateFontString() return CreateFrame("FontString", nil, self) end
function methods:CreateTexture() return CreateFrame("Texture", nil, self) end
Minimap = CreateFrame("Frame", nil, UIParent)
Minimap:SetSize(140, 140)
UISpecialFrames = {}
function GameTooltip_Hide() GameTooltip:Hide() end
function GetCursorPosition() return cursorX or 200, cursorY or 200 end
function login()
    for _,frame in ipairs(frames) do
        if frame.events.PLAYER_LOGIN then frame.scripts.OnEvent(frame, "PLAYER_LOGIN") end
    end
end
function leftClick(frame)
    assert(frame:IsShown() and frame:IsEnabled())
    frame.scripts.OnClick(frame, "LeftButton")
end
function globalMouseDown(target)
    hover = target
    for _,frame in ipairs(frames) do
        if frame.events.GLOBAL_MOUSE_DOWN then frame.scripts.OnEvent(frame, "GLOBAL_MOUSE_DOWN", "LeftButton") end
    end
    hover = nil
end
function escape()
    for _, name in ipairs(UISpecialFrames) do
        if _G[name] and _G[name]:IsShown() then _G[name]:Hide() end
    end
end
function visibleText(needle)
    for _, frame in ipairs(frames) do
        if frame.text and string.find(frame.text, needle, 1, true) then
            local current = frame
            while current and current:IsShown() do current = current.parent end
            if not current then return true end
        end
    end
    return false
end
reads, starts, repeats = 0, {}, {}
options = {
    {key="Mines", name="Minas de la Muerte", tasks={"Recoge la carta antes de entrar"}, available=true, deferred=true},
    {key="Gnomer", name="Gnomeregan", tasks={"Entrega tu tarjeta en el taller"}, available=true},
}
RutaXPDB, RutaXPCharDB = {}, {}
ns = {db=RutaXPDB, char=RutaXPCharDB, DungeonPlanner={}}
ns.char.activeGuide, ns.char.cursor = "route", 12
function ns.DungeonPlanner:PreparationOptions() reads = reads + 1; return options end
function ns.DungeonPlanner:CatalogOptions() reads = reads + 1; return options end
function ns.DungeonPlanner:StartPreparation(key)
    table.insert(starts, key)
    return true
end
function ns.DungeonPlanner:Resume() error("Browsing must not reactivate deferred visits") end
function ns.DungeonPlanner:Repeat(key) table.insert(repeats, key); return true end
"""


class DungeonPreparationUITests(unittest.TestCase):
    def setUp(self):
        self.start_ui()

    def start_ui(self, saved_angle=None):
        lua = LuaRuntime(unpack_returned_tuples=True)
        self.run_lua = lua.execute
        self.run_lua(UI_STUBS + TOOLTIP_STUBS + HOST)
        lua.globals().ns.char.dungeonPrepMinimapAngle = saved_angle
        self.run_lua((ADDON / "DungeonPreparationUI.lua").read_text(encoding="utf-8-sig"),
                     "RutaXP", lua.globals().ns)
        self.run_lua("""
            login()
            button = assert(RutaXPDungeonPreparationMinimapButton)
            ui = assert(ns.DungeonPreparationUI)
        """)

    def test_login_always_shows_one_separate_button_and_keeps_world_route(self):
        self.run_lua("""
            login()
            assert(button == RutaXPDungeonPreparationMinimapButton)
            assert(namedCounts.RutaXPDungeonPreparationMinimapButton == 1)
            assert(button.parent == Minimap and button:IsShown())
            local keyIcon
            for _,frame in ipairs(frames) do
                if frame.parent == button and frame.texture and frame.texture:find("INV_Misc_Key", 1, true) then
                    keyIcon = frame
                end
            end
            assert(keyIcon and keyIcon:IsShown(), "missing key on the minimap launcher")
            local _, relative, _, x, y = button:GetPoint()
            assert(relative == Minimap and x < 0 and y > 0)
            button.scripts.OnEnter(button)
            assert(GameTooltip.shown and GameTooltip.owner == button)
            assert(string.find(string.lower(table.concat(GameTooltip.lines, " ")), "mazmorra", 1, true))
            button.scripts.OnLeave(button)
            assert(not GameTooltip.shown)
            leftClick(button)
            assert(ui.menu:IsShown() and #ui.menuRows == 2)
            assert(visibleText("Minas de la Muerte") and visibleText("Gnomeregan"))
            assert(not RutaXPDungeonPreparationFrame or not RutaXPDungeonPreparationFrame:IsShown())
            leftClick(ui.menuRows[1])
            local panel = assert(RutaXPDungeonPreparationFrame)
            assert(panel:IsShown() and visibleText("Minas de la Muerte"))
            assert(ui.prepare:GetText() == "Retomar preparación")
            assert(visibleText("Recoge la carta antes de entrar"))
            escape()
            assert(not panel:IsShown() and button:IsShown())
            assert(#starts == 0 and ns.char.activeGuide == "route" and ns.char.cursor == 12)
        """)

    def test_browsing_and_refresh_never_start_a_detour_until_explicit_click(self):
        self.run_lua("""
            leftClick(button)
            -- Pick the second entry immediately, without accepting the suggested first one.
            leftClick(ui.menuRows[2])
            assert(visibleText("Gnomeregan") and visibleText("Entrega tu tarjeta en el taller"))
            leftClick(ui.previous)
            assert(visibleText("Minas de la Muerte"))
            leftClick(ui.selector)
            assert(ui.menu:IsShown())
            leftClick(ui.menuRows[2])
            options[2].tasks = {"La tarjeta ya se puede entregar"}
            ui:RefreshIfShown()
            ui:RefreshIfShown()
            assert(visibleText("La tarjeta ya se puede entregar"))
            assert(#starts == 0 and ns.char.activeGuide == "route" and ns.char.cursor == 12)
            leftClick(ui.prepare)
            assert(#starts == 1 and starts[1] == "Gnomer")
            assert(not RutaXPDungeonPreparationFrame:IsShown() and button:IsShown())
        """)

    def test_empty_state_is_accessible_and_never_allows_preparation(self):
        self.run_lua("""
            options = {}
            ui:RefreshIfShown()
            leftClick(button)
            assert(ui.menu:IsShown() and button:IsShown())
            assert(not ui.menuRows[1] or not ui.menuRows[1]:IsShown())
            globalMouseDown(UIParent)
            assert(not ui.menu:IsShown())
            leftClick(button)
            assert(ui.menu:IsShown())
            assert(#starts == 0)
        """)

    def test_escape_outside_and_second_key_click_dismiss_without_changing_route(self):
        self.run_lua("""
            leftClick(button)
            assert(ui.menu:IsShown())
            leftClick(button)
            assert(not ui.menu:IsShown())
            leftClick(button)
            globalMouseDown(ui.menu)
            assert(ui.menu:IsShown())
            globalMouseDown(UIParent)
            assert(not ui.menu:IsShown())
            leftClick(button)
            escape()
            assert(not ui.menu:IsShown())
            assert(#starts == 0 and ns.char.activeGuide == "route" and ns.char.cursor == 12)
        """)

    def test_catalog_scrolls_to_last_entry_and_refresh_keeps_selected_key(self):
        self.run_lua("""
            options = {}
            for i=1, 27 do
                options[i] = {key="instance"..i, name="Mazmorra "..i, available=true, tasks={"Objetivo "..i}}
            end
            leftClick(button)
            local scroll = assert(ui.menuScroll)
            assert(scroll.scrollChild and scroll.scrollChild.height > ui.menu.height)
            assert(scroll.template == "UIPanelScrollFrameTemplate" or scroll.scripts.OnMouseWheel)
            scroll:SetVerticalScroll(scroll.scrollChild.height - ui.menu.height)
            local last = assert(ui.menuRows[27])
            assert(last.key == "instance27")
            leftClick(last)
            assert(visibleText("Objetivo 27") and not ui.menu:IsShown())
            table.remove(options, 1)
            ui:RefreshIfShown()
            assert(visibleText("Objetivo 27") and #starts == 0)
            escape()
            assert(not RutaXPDungeonPreparationFrame:IsShown())
            assert(ns.char.activeGuide == "route" and ns.char.cursor == 12)
        """)

    def test_finished_dungeon_without_turnins_is_never_started_by_browsing(self):
        self.run_lua("""
            options = {{key="Done", name="Mazmorra completada", finished=true,
                available=false, reason="Ya has terminado las misiones de esta mazmorra.", tasks={}}}
            leftClick(button)
            leftClick(ui.menuRows[1])
            ui:RefreshIfShown()
            assert(ui.prepare:GetText() == "Ir por libre" and visibleText(options[1].reason))
            assert(#starts == 0 and #repeats == 0 and ns.char.activeGuide == "route" and ns.char.cursor == 12)
            leftClick(ui.prepare)
            assert(#starts == 0 and #repeats == 1 and repeats[1] == "Done")
        """)

    def test_unavailable_entry_explains_reason_and_cannot_start(self):
        self.run_lua("""
            options = {{key="High", name="Mazmorra de nivel alto", finished=false, available=false,
                reason="Todavía no tienes misiones disponibles para tu nivel.", tasks={}}}
            leftClick(button)
            leftClick(ui.menuRows[1])
            assert(not ui.prepare:IsEnabled() and visibleText(options[1].reason))
            assert(#starts == 0 and #repeats == 0)
        """)

    def test_finished_dungeon_with_pending_turnins_offers_to_guide_deliveries(self):
        self.run_lua("""
            options = {{key="Mines", name="Minas de la Muerte", finished=true, available=true,
                        tasks={"Entrega la carta al volver a la ciudad"}}}
            leftClick(button)
            leftClick(ui.menuRows[1])
            assert(ui.prepare:GetText() == "Guiar las entregas" and ui.prepare:IsEnabled())
            assert(visibleText("Entrega la carta al volver a la ciudad"))
            assert(#starts == 0)
            leftClick(ui.prepare)
            assert(#starts == 1 and starts[1] == "Mines")
        """)

    def test_drag_persists_angle_across_login_and_does_not_open_the_panel(self):
        angle = self.run_lua("""
            button.scripts.OnMouseDown(button)
            button.scripts.OnDragStart(button)
            cursorX, cursorY = 200, 90
            button.scripts.OnUpdate(button)
            button.scripts.OnDragStop(button)
            assert(not button.scripts.OnUpdate)
            leftClick(button)
            assert((not ui.menu or not ui.menu:IsShown()) and #starts == 0)
            return ns.char.dungeonPrepMinimapAngle
        """)
        self.assertAlmostEqual(angle, -90)
        self.start_ui(angle)
        self.run_lua("""
            local _, _, _, x, y = button:GetPoint()
            assert(math.abs(x) < 0.01 and y < 0)
            button.scripts.OnMouseDown(button)
            leftClick(button)
            assert(ui.menu:IsShown())
        """)
