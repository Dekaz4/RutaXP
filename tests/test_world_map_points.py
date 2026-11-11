"""Open the native world map, change its filters and redraw it with the shipping Lua."""

import unittest

from lupa.luajit21 import LuaRuntime

from test_addon import ADDON, TOOLTIP_STUBS, UI_STUBS


MAP_STUBS = """
local methods = getmetatable(UIParent).__index
local makeFrame = CreateFrame
PinFrames, EventFrames = {}, {}
function CreateFrame(kind, name, parent, template)
    local f = makeFrame()
    f.parent = parent
    table.insert(EventFrames, f)
    if parent == Canvas then table.insert(PinFrames, f) end
    return f
end
function methods:CreateTexture()
    local t = makeFrame()
    self.textures = self.textures or {}
    table.insert(self.textures, t)
    return t
end
function methods:SetMouseClickEnabled(v) self.capturesClicks = v end
function methods:SetMouseMotionEnabled(v) self.acceptsMotion = v end
function methods:EnableMouse(v) self.capturesClicks = v end
function methods:SetFrameLevel(v) self.level = v end
function methods:SetScale(v) self.scale = v end
function methods:SetPoint(point, parent, relativePoint, x, y) self.offsetX, self.offsetY = x, y end
function methods:SetAtlas(atlas) self.atlas, self.file = atlas, nil end
function methods:SetTexture(file) self.file, self.atlas = file, nil end
function methods:SetTexCoord(...) end
function methods:IsVisible() return self:IsShown() end
function methods:HookScript(key, callback)
    local old = self.scripts[key]
    self.scripts[key] = function(...) if old then old(...) end; callback(...) end
end

function CreateFromMixins(base)
    local result = {}
    for k, v in pairs(base) do result[k] = v end
    return result
end
MapCanvasDataProviderMixin = {
    OnAdded = function(self, map) self.map = map end,
    GetMap = function(self) return self.map end,
}
Canvas = CreateFrame("Frame", nil, UIParent)
Canvas:SetSize(1000, 600)
WorldMapFrame = CreateFrame("Frame", nil, UIParent)
WorldMapFrame.ScrollContainer = Canvas
WorldMapFrame.mapID, WorldMapFrame.adds = 1436, 0
WorldMapFrame.dataProviders = {}
function WorldMapFrame:GetMapID() return self.mapID end
function WorldMapFrame:GetCanvas() return Canvas end
function WorldMapFrame:GetCanvasContainer() return Canvas end
function WorldMapFrame:GetCanvasScale() return self.canvasScale or 1 end
local levels = {PIN_FRAME_LEVEL_MAP_EXPLORATION=2002, PIN_FRAME_LEVEL_FLIGHT_POINT=2020,
                PIN_FRAME_LEVEL_AREA_POI=2022, PIN_FRAME_LEVEL_GROUP_MEMBER=2650}
function WorldMapFrame:GetPinFrameLevelsManager()
    return {
        GetValidFrameLevel = function(_, key) return levels[key] or 2000 end,
        GetFrameLevelStart = function(_, key) return levels[key] or 2000 end,
    }
end
function WorldMapFrame:AddDataProvider(provider)
    self.adds = self.adds + 1
    self.provider = self.provider or provider
    self.dataProviders[provider] = true
    provider:OnAdded(self)
end
function WorldMapFrame:RemoveDataProvider(provider)
    provider:RemoveAllData()
    self.dataProviders[provider] = nil
    provider:OnRemoved(self)
end
NativePins = {}
function WorldMapFrame:EnumeratePinsByTemplate(template)
    local pins, i = NativePins[template] or {}, 0
    return function() i = i + 1; return pins[i] end
end
local menuCallbacks = {}
Menu = {ModifyMenu = function(tag, callback)
    assert(not menuCallbacks[tag], "map filter was registered twice")
    menuCallbacks[tag] = callback
end}
local function menuDescription()
    local menu = {children={}}
    function menu:CreateButton(label)
        local item = menuDescription()
        self.children[label] = item
        return item
    end
    function menu:CreateCheckbox(label, isChecked, toggle, data)
        local item = self:CreateButton(label)
        item.checked = function() return isChecked(data) end
        item.toggle = function() toggle(data) end
        return item
    end
    return menu
end
function OpenFilters()
    local root = menuDescription()
    menuCallbacks.MENU_WORLD_MAP_TRACKING(WorldMapFrame, root)
    return root.children["Puntos de interés de RutaXP"].children
end
local timers = {}
C_Timer = {After = function(_, callback) table.insert(timers, callback) end}
function Flush()
    local budget = 20
    while #timers > 0 do
        assert(budget > 0, "map refreshes forever")
        budget = budget - 1
        table.remove(timers, 1)()
    end
end
function SendEvent(event)
    for _, f in ipairs(EventFrames) do
        if f.events[event] then f.scripts.OnEvent(f, event) end
    end
    Flush()
end
C_Texture = {GetAtlasInfo = function(atlas) return {name=atlas} end}
Enum = {MinimapTrackingFilter = {Innkeeper=32, TaxiNode=8}}
C_Minimap = {
    GetNumTrackingTypes = function() return 2 end,
    GetTrackingFilter = function(i) return {filterID=({32,8})[i]} end,
    GetTrackingInfo = function(i) return {texture=({1001,1002})[i], active=false} end,
}
Services = {
    [1436] = {{category="inn", name="Posada", x=.24, y=.41},
              {category="flight", name="Vuelo", x=.56, y=.32}},
}
Quests = {[1436] = {{category="accept", name="Una misión", x=.76, y=.58, questID=401}}}
NS = {char={},
    GetMapServicePoints=function(self, id) return Services[id] or {} end,
    GetMapQuestPoints=function(self, id) return Quests[id] or {} end,
}
function Redraw()
    WorldMapFrame.provider:RefreshAllData()
    Flush()
end
function VisibleCount()
    local n = 0
    for _, f in ipairs(PinFrames) do if f:IsShown() then n = n + 1 end end
    return n
end
"""


class WorldMapPointsTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(UI_STUBS + TOOLTIP_STUBS + MAP_STUBS)
        self.g = self.lua.globals()
        self.source = (ADDON / "WorldMapPoints.lua").read_text(encoding="utf-8-sig")
        self.lua.execute(self.source, "RutaXP", self.g.NS)

    def show_map(self):
        self.g.NS.InitializeMapPoints(self.g.NS)
        self.g.Redraw()

    def test_default_filters_show_service_and_quest_pins_once_on_first_open(self):
        self.show_map()
        self.g.NS.InitializeMapPoints(self.g.NS)
        self.assertEqual(self.g.WorldMapFrame.adds, 1)
        filters = self.g.OpenFilters()
        for expected in ("posada", "vuelo", "banco", "subasta", "repara", "buz", "vendedor"):
            checkbox = next(box for label, box in filters.items() if expected in label.lower())
            self.assertEqual(checkbox.checked(), expected != "vendedor")
        self.assertEqual(self.g.VisibleCount(), 3)
        visible = [f for f in self.g.PinFrames.values() if f.shown]
        self.assertTrue(all(f.capturesClicks is False and f.acceptsMotion for f in visible))
        textures = {t.file or t.atlas for f in visible for t in f.textures.values()}
        self.assertIn(1001, textures)
        self.assertIn("QuestNormal", textures)

    def test_icons_stay_above_explored_map_art_and_at_the_same_site_when_zooming(self):
        self.show_map()
        inn = next(f for f in self.g.PinFrames.values()
                   if any(t.file == 1001 for t in f.textures.values()))
        self.assertGreater(inn.level or 0, 2002)
        self.assertLess(inn.level, 2650)
        self.g.WorldMapFrame.canvasScale = 2
        self.lua.execute("WorldMapFrame.provider:OnCanvasScaleChanged(); Flush()")
        self.assertEqual(inn.scale, .5)
        self.assertAlmostEqual(inn.offsetX * inn.scale, .24 * self.g.Canvas.width)
        self.assertAlmostEqual(inn.offsetY * inn.scale, -.41 * self.g.Canvas.height)

    def test_dungeon_filter_toggles_the_native_provider_preference(self):
        self.lua.execute("""
            DungeonEntranceDataProviderMixin = {}
            CVars = {showDungeonEntrancesOnMap="0"}
            C_CVar = {
                GetCVar = function(name) return CVars[name] end,
                SetCVar = function(name, value) CVars[name] = value end,
            }
        """)
        self.show_map()
        dungeon = self.g.OpenFilters()["Entradas de mazmorras"]
        self.assertFalse(dungeon.checked())
        dungeon.toggle()
        self.assertEqual(self.g.CVars.showDungeonEntrancesOnMap, "1")
        self.assertTrue(dungeon.checked())
        dungeon.toggle()
        self.assertEqual(self.g.CVars.showDungeonEntrancesOnMap, "0")

    def test_checkbox_redraws_and_restores_previously_saved_choice(self):
        self.g.NS.char.mapPointFilters = self.lua.table(inn=False)
        self.show_map()
        filters = self.g.OpenFilters()
        inn = next(box for name, box in filters.items() if "posada" in name.lower())
        self.assertFalse(inn.checked())
        self.assertEqual(self.g.VisibleCount(), 2)
        inn.toggle()
        self.g.Flush()
        self.assertEqual(self.g.VisibleCount(), 3)
        inn.toggle()
        self.g.Flush()
        self.assertEqual(self.g.VisibleCount(), 2)
        self.assertIs(self.g.NS.char.mapPointFilters.inn, False)
        reopened = self.g.OpenFilters()
        self.assertFalse(next(box for name, box in reopened.items() if "posada" in name.lower()).checked())

    def test_switching_maps_removes_stale_pins_and_preserves_blizzard_flight_pin(self):
        self.lua.execute("""
            NativeFlight = CreateFrame("Frame", nil, UIParent)
            function NativeFlight:GetPosition() return .56, .32 end
            NativePins.FlightPointPinTemplate = {NativeFlight}
        """)
        self.show_map()
        self.assertTrue(self.g.NativeFlight.shown)
        self.assertEqual(self.g.VisibleCount(), 2)
        self.g.WorldMapFrame.mapID = 1429
        self.lua.execute("WorldMapFrame.provider:OnMapChanged(); Flush()")
        self.assertEqual(self.g.VisibleCount(), 0)
        self.assertTrue(self.g.NativeFlight.shown)
        self.g.WorldMapFrame.mapID = 1436
        self.lua.execute("WorldMapFrame.provider:OnMapChanged(); Flush()")
        self.assertEqual(self.g.VisibleCount(), 2)

    def test_flight_filter_removes_and_restores_original_provider_and_its_events(self):
        self.lua.execute("""
            local flight = CreateFrame("Frame", nil, UIParent)
            function flight:GetPosition() return .56, .32 end
            FlightPointDataProviderMixin = CreateFromMixins(MapCanvasDataProviderMixin)
            function FlightPointDataProviderMixin:RefreshAllData()
                NativePins.FlightPointPinTemplate = {flight}
                flight:Show()
            end
            function FlightPointDataProviderMixin:RemoveAllData()
                NativePins.FlightPointPinTemplate = {}
                flight:Hide()
            end
            function FlightPointDataProviderMixin:OnShow() self.watching = true end
            function FlightPointDataProviderMixin:OnHide() self.watching = false end
            function FlightPointDataProviderMixin:OnRemoved(map) self.map = nil end
            NativeProvider = CreateFromMixins(FlightPointDataProviderMixin)
            WorldMapFrame.dataProviders[NativeProvider] = true
            NativeProvider:OnAdded(WorldMapFrame)
            NativeProvider:OnShow()
            NativeProvider:RefreshAllData()
            OtherProvider = {RefreshAllData=function() end}
            WorldMapFrame.dataProviders[OtherProvider] = true
        """)
        self.show_map()
        checkbox = self.g.OpenFilters()["Maestros de vuelo"]
        for on in (False, True):
            checkbox.toggle()
            self.g.Flush()
            self.assertEqual(checkbox.checked(), on)
            self.assertEqual(self.g.NativeProvider.watching, on)
            self.assertEqual(len(self.g.NativePins.FlightPointPinTemplate), int(on))
            self.assertEqual(self.lua.eval("WorldMapFrame.dataProviders[NativeProvider] == true"), on)
            self.assertEqual(self.lua.eval("NativeProvider.map == WorldMapFrame"), on)
            self.assertTrue(self.lua.eval("WorldMapFrame.dataProviders[OtherProvider]"))
            self.assertEqual(self.g.VisibleCount(), 2)  # Inn and quest remain; native flight is never doubled.

    def test_quest_poi_event_reconciles_a_new_native_marker_while_map_is_open(self):
        self.show_map()
        self.lua.execute("""
            local pin = CreateFrame("Frame", nil, UIParent)
            pin.questID = 401
            function pin:GetPosition() return .76, .58 end
            NativePins.QuestOfferPinTemplate = {pin}
            SendEvent("QUEST_POI_UPDATE")
        """)
        self.assertEqual(self.g.VisibleCount(), 2)
        self.assertTrue(self.g.NativePins.QuestOfferPinTemplate[1].shown)
        self.lua.execute('NativePins.QuestOfferPinTemplate = {}; SendEvent("QUEST_POI_UPDATE")')
        self.assertEqual(self.g.VisibleCount(), 3)
