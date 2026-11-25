"""Exercise map selection, the Blizzard quest pane, and minimap toggles together."""

import unittest
from pathlib import Path

from lupa.lua51 import LuaRuntime


ADDON = Path(__file__).resolve().parents[1] / "RutaXP"

# Model only the MapCanvas, frame, and tracking APIs used by this integration.
# Opening another map never changes the position or class of the test character.
CLIENT = """
ns, frames, timers = {}, {}, {}
local function noop() end
local Frame = {}
function Frame:RegisterEvent(event) self.events[event] = true end
function Frame:SetScript(which, callback) self.scripts[which] = callback end
function Frame:GetScript(which) return self.scripts[which] end
function Frame:HookScript(which, callback)
    local old = self.scripts[which]
    self.scripts[which] = function(...) if old then old(...) end; callback(...) end
end
function Frame:IsShown() return self.shown end
function Frame:IsVisible() return self.shown and (not self.parent or self.parent:IsVisible()) end
function Frame:Show() self.shown = true end
function Frame:Hide() self.shown = false end
function Frame:SetShown(on) self.shown = on end
function Frame:SetSize(w, h) self.width, self.height = w, h end
function Frame:GetWidth() return self.width end
function Frame:GetHeight() return self.height end
function Frame:GetSize() return self.width, self.height end
function Frame:GetScale() return self.scale or 1 end
function Frame:SetScale(scale) self.scale = scale end
function Frame:GetEffectiveScale() return self:GetScale() end
function Frame:GetFrameLevel() return self.level or 1 end
function Frame:SetFrameLevel(n) self.level = n end
function Frame:SetPoint(...) self.anchor = {...} end
function Frame:ClearAllPoints() self.anchor = nil end
function Frame:CreateTexture()
    return {SetAllPoints = noop, SetTexture = function(self, tex) self.texture = tex end,
        SetAtlas = function(self, atlas) self.atlas = atlas end, SetTexCoord = noop}
end
Frame.EnableMouse, Frame.SetMouseClickEnabled, Frame.SetMouseMotionEnabled = noop, noop, noop
function CreateFrame(kind, name, parent)
    local frame = setmetatable({kind=kind, parent=parent, events={}, scripts={},
        shown=true, width=1000, height=700}, {__index=Frame})
    frames[#frames+1] = frame
    return frame
end
C_Timer = {After=function(_, callback) timers[#timers+1] = callback end}
function settle()
    local runs = 0
    while #timers > 0 do
        runs = runs + 1; assert(runs < 1000, "refresh did not settle")
        table.remove(timers, 1)()
    end
end
function fire(event, ...)
    for _, f in ipairs(frames) do
        if f.events[event] and f.scripts.OnEvent then f.scripts.OnEvent(f, event, ...) end
    end
    settle()
end
function UnitFactionGroup() return "Alliance" end
function UnitClass() return "Brujo", "WARLOCK" end
function UnitPosition() error("Services on M must not depend on player proximity") end
function CreateVector2D(x, y)
    return {x=x, y=y, GetXY=function(self) return self.x, self.y end}
end
function Mixin(dst, ...)
    for i=1, select("#", ...) do
        for k,v in pairs((select(i, ...))) do dst[k] = v end
    end
    return dst
end
function CreateFromMixins(...) return Mixin({}, ...) end
MapCanvasDataProviderMixin = {
    OnAdded=function(self, map) self.owningMap = map end,
    GetMap=function(self) return self.owningMap end,
    OnShow=noop, OnHide=noop, OnMapChanged=noop, RefreshAllData=noop,
}
WorldMapFrame = CreateFrame("Frame")
local map = WorldMapFrame
map:Hide()
map.dataProviders = {}
map.mapID = 1426
map.canvas = CreateFrame("Frame", nil, map)
map.QuestLog = CreateFrame("Frame", nil, map)
map.detailLayer = CreateFrame("Frame", nil, map.canvas)
map.detailLayer:SetFrameLevel(1975)
local levelManager = {}
function levelManager:GetValidFrameLevel(kind, index)
    assert(kind == "PIN_FRAME_LEVEL_AREA_POI" and (index == nil or index == 1))
    return 2013
end
function map:GetPinFrameLevelsManager() return levelManager end
function map:AddDataProvider(p) self.dataProviders[p] = true; p:OnAdded(self) end
function map:GetCanvas() return self.canvas end
function map:GetMapID() return self.mapID end
function map:GetCanvasScale() return 1 end
function map:GetCanvasZoomPercent() return 0 end
function map:EnumeratePinsByTemplate() return function() end end
function openMap(id)
    map.mapID = id
    map:Show()
    if map.scripts.OnShow then map.scripts.OnShow(map) end
    for p in pairs(map.dataProviders) do
        p:OnMapChanged(); p:RefreshAllData(true); p:OnShow()
    end
    settle()
end
Enum = {
    UIMapType={Cosmic=0, World=1, Continent=2, Zone=3, Dungeon=4, Micro=5, Orphan=6},
    MinimapTrackingFilter={Auctioneer=1, Banker=2, Battlemaster=4, TaxiNode=8,
        Innkeeper=32, Mailbox=64, TrainerProfession=128, Repair=512, TrivialQuests=1024,
        Stablemaster=2048, TrainerClass=8388608},
}
local parents = {[1426]=1415, [1453]=1429, [1455]=1426, [1457]=1438, [1414]=947, [1415]=947}
C_Map = {
    GetBestMapForUnit=function() return 1426 end,
    GetMapInfo=function(id)
        if not ns.worldMapServiceEra[id] and not parents[id] then return end
        local cont = ns.worldMapServiceEra[id] and ns.worldMapServiceEra[id][1]
        return {mapID=id, parentMapID=parents[id] or (cont==0 and 1415 or 1414),
            mapType=(id == 1414 or id == 1415) and Enum.UIMapType.Continent or Enum.UIMapType.Zone}
    end,
    GetWorldPosFromMapPos=function(id, pos)
        local area = ns.worldMapServiceEra[id]
        if area then
            return area[1], CreateVector2D(area[2]+pos.y*(area[4]-area[2]), area[3]+pos.x*(area[5]-area[3]))
        end
    end,
    GetMapPosFromWorldPos=function(cont, pos, id)
        local area = ns.worldMapServiceEra[id]
        if area and area[1]==cont then
            return id, CreateVector2D((pos.y-area[3])/(area[5]-area[3]), (pos.x-area[2])/(area[4]-area[2]))
        end
    end,
}
local options = {}
for field, id in pairs(Enum.MinimapTrackingFilter) do
    options[#options+1] = {filterID=id, name=field, active=field ~= "TrivialQuests", texture=10000+id}
end
C_Minimap = {
    GetNumTrackingTypes=function() return #options end,
    GetTrackingFilter=function(i) return {filterID=options[i].filterID} end,
    GetTrackingInfo=function(i) return options[i] end,
}
function setFilter(field, on)
    for _, info in ipairs(options) do if info.name == field then info.active=on end end
    fire("MINIMAP_UPDATE_TRACKING")
end
function visible(name)
    local count, pin = 0
    for _, f in ipairs(frames) do
        if f.name == name and f:IsVisible() then count, pin = count+1, f end
    end
    return count, pin
end
function service(name)
    for _, f in ipairs(frames) do
        if f:IsVisible() then
            if f.name == name then return f, f end
            for _, member in ipairs(f.serviceMembers or {}) do
                if member.name == name then return f, member.pin end
            end
        end
    end
end
GameTooltip = {lines={}, SetOwner=function(self) self.lines={} end,
    AddLine=function(self,text) self.lines[#self.lines+1]=text end, Show=noop}
"""


class NativeServiceMapTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(CLIENT)
        self.g = self.lua.globals()
        for source in ("WorldMapTracking", "WorldMapServiceData", "WorldMapServices", "WorldMapAreaPins", "WorldMapNative"):
            self.lua.execute((ADDON / f"{source}.lua").read_bytes(), "RutaXP", self.g.ns)
        self.g.fire("ADDON_LOADED", "RutaXP")
        self.g.fire("PLAYER_LOGIN")
        self.g.fire("PLAYER_ENTERING_WORLD")

    def test_windowed_quest_map_shows_nearby_and_distant_services_with_game_icons(self):
        self.g.openMap(1426)
        self.assertTrue(self.g.WorldMapFrame.QuestLog.IsVisible(self.g.WorldMapFrame.QuestLog))
        for name, (x, y, filter_id) in {
            "Alamar Grimm": (.2865, .6614, 8388608),
            "Durnan Cortapieles": (.288, .664, 512),
            "Tabernero Belm": (.4738, .5252, 32),
        }.items():
            with self.subTest(name=name):
                rep, pin = self.g.service(name)
                self.assertAlmostEqual(pin.x, x, places=4)
                self.assertAlmostEqual(pin.y, y, places=4)
                self.assertEqual(pin.icon.texture, 10000 + filter_id)
                self.assertEqual(pin.level, 2013)
                self.assertGreater(pin.level, self.g.WorldMapFrame.detailLayer.level)
                self.assertEqual((rep.anchor[1], rep.anchor[3]), ("CENTER", "TOPLEFT"))
                self.assertLess(abs(rep.anchor[4] - x * 1000), 70)
                self.assertLess(abs(rep.anchor[5] + y * 700), 70)

    def test_era_coordinates_use_the_displayed_map_bounds(self):
        # Simulate a different art rectangle using the same world-yard units.
        self.lua.execute("""
            local project = C_Map.GetWorldPosFromMapPos
            function C_Map.GetWorldPosFromMapPos(id, pos)
                if id == 1426 then
                    return project(id, CreateVector2D(pos.x+.10, pos.y-.05))
                end
                return project(id, pos)
            end
        """)
        self.g.openMap(1426)
        count, pin = self.g.visible("Alamar Grimm")
        self.assertEqual(count, 1)
        self.assertAlmostEqual(pin.x, .1865, places=4)
        self.assertAlmostEqual(pin.y, .7114, places=4)

    def test_remote_map_and_native_toggles_refresh_an_already_open_map(self):
        self.g.openMap(1426)
        self.g.openMap(1457)
        self.assertEqual(self.g.visible("Tabernero Belm")[0], 0)
        self.assertIsNotNone(self.g.service("Garryeth"))
        self.g.setFilter("Banker", False)
        self.assertIsNone(self.g.service("Garryeth"))
        self.assertIsNotNone(self.g.service("Subastador Cazarez"))
        self.g.setFilter("Banker", True)
        self.g.openMap(1457)
        self.assertIsNotNone(self.g.service("Garryeth"))

    def test_kharanos_and_theramore_categories_have_separate_visible_native_icons(self):
        self.lua.execute("""
            function checkTown(mapID, names)
                openMap(mapID)
                local reps = {}
                for index, name in ipairs(names) do
                    local pin = assert(service(name), name)
                    assert(pin.icon.texture == C_Minimap.GetTrackingInfo(
                        RutaXPWorldMapTracking.Info(pin.key).index).texture, name)
                    for _, other in ipairs(reps) do
                        assert(math.abs(other.anchor[4]-pin.anchor[4]) >= 18 or
                            math.abs(other.anchor[5]-pin.anchor[5]) >= 18, name)
                    end
                    reps[#reps+1] = pin
                end
            end
            checkTown(1426, {"Tabernero Belm", "Shelby Petrepiedra", "Gremlock Pilsnor",
                "Boran Tintiyerro", "Gimrizz Molaro"})
            local boran = service("Boran Tintiyerro")
            assert(boran == service("Gamili Escardida"))
            boran.scripts.OnEnter(boran)
            local names = table.concat(GameTooltip.lines, " ")
            assert(names:find("Boran Tintiyerro") and names:find("Gamili Escardida"))
            setFilter("Repair", false)
            assert(not service("Boran Tintiyerro") and service("Tabernero Belm"))
            setFilter("Repair", true)
            checkTown(1445, {"Tabernero Janene", "Michael", "Buzón", "Timoteo Valión", "Hans Weston"})
            assert(service("Tabernero Belm") == nil)
        """)

    def test_stitched_mode_uses_one_service_layer_in_both_installations(self):
        self.lua.execute("""
            callbacks, sets, stitched = {}, {}, false
            OpenMapAPI = {RegisterCallback=function(_, event, cb) callbacks[event] = cb end}
            local layer = CreateFrame("Frame", nil, WorldMapFrame:GetCanvas())
            layer:Hide()
            local s = {IsBuilt=function() return true end, Rect=function() return 0, 1, 0, 1 end}
            function s.FromYards(cont, north, west) return .5+west/100000, .5-north/100000 end
            function s.PinSet(key)
                assert(not sets[key], "duplicate stitched set")
                local set = {frame=CreateFrame("Frame", nil, layer), on=true, pins={}}
                sets[key] = set
                return set
            end
            function s.AddPin(set, x, y, look, data)
                local pin = CreateFrame("Button", nil, set.frame)
                pin.x, pin.y, pin.name, pin.data = x, y, data[5], data
                set.pins[#set.pins+1] = pin
                return pin
            end
            function s.SetPinSetOn(set, on) set.on=on; set.frame:SetShown(on) end
            function s.GetPinSet(key) return sets[key] end
            local m = {IsStitched=function() return stitched end, Refresh=function() end}
            OpenMap = {MapStitch=s, GetModule=function() return m end}
            fire("ADDON_LOADED", "OpenMap")
            function selectView(on)
                stitched = on
                layer:SetShown(on)
                callbacks.OpenMap_StitchedChanged("OpenMap_StitchedChanged", on)
                settle()
            end
            function useEmbedded()
                ns.GetEmbeddedModule = function(name) if name == "OpenMap" then return OpenMap end end
            end
        """)
        self.g.openMap(1426)
        self.assertEqual(self.g.visible("Alamar Grimm")[0], 1)
        self.g.selectView(True)
        self.assertEqual(self.g.visible("Alamar Grimm")[0], 1)
        self.assertIsNotNone(self.g.sets.rutaxp_service_classTrainer)
        self.g.setFilter("TrainerClass", False)
        self.assertEqual(self.g.visible("Alamar Grimm")[0], 0)
        self.g.selectView(False)
        self.g.setFilter("TrainerClass", True)
        self.assertEqual(self.g.visible("Alamar Grimm")[0], 1)
        self.g.useEmbedded()
        self.g.selectView(True)
        self.assertEqual(self.g.visible("Alamar Grimm")[0], 1)
        self.g.selectView(False)
        self.assertEqual(self.g.visible("Alamar Grimm")[0], 1)

    def test_embedded_openmap_prebuilt_while_closed_populates_on_first_m_and_reopen(self):
        self.lua.execute("""
            sets, callbacks = {}, {}
            OpenMapAPI = {RegisterCallback=function(_, event, cb) callbacks[event] = cb end}
            local stitched = CreateFrame("Frame", nil, WorldMapFrame)
            local scale = 1
            local root = {GetEffectiveScale=function() return scale end}
            local s = {IsBuilt=function() return true end, Root=function() return root end,
                Size=function() return 20000, 14000 end, Rect=function() return 0, 1, 0, 1 end}
            function s.FromYards(c,n,w) return .3*c+w/50000, .3*c-n/50000 end
            function s.PinSet(key)
                assert(not sets[key], "created duplicate layer")
                local set = {on=true, pins={}, frame=CreateFrame("Frame",nil,stitched)}
                sets[key]=set
                return set
            end
            function s.GetPinSet(key) return sets[key] end
            function s.SetPinSetOn(set,on) set.on=on; set.frame:SetShown(on) end
            function s.AddPin(set,u,v,look,data)
                local pin=CreateFrame("Button",nil,set.frame)
                pin.u,pin.v,pin.texture,pin.data,pin.name=u,v,look.texture,data,data[5]
                pin.anchorRegion = {}
                -- OpenMap stores its immutable world-position anchor in pin.anchor.
                function pin:ClearAllPoints() self.placement=nil end
                function pin:SetPoint(...) self.placement={...} end
                pin.anchor=pin.anchorRegion
                set.pins[#set.pins+1]=pin
                return pin
            end
            local m={IsStitched=function() return true end, Refresh=function() end}
            local om={MapStitch=s,GetModule=function() return m end}
            ns.GetEmbeddedModule=function() return om end
            fire("ADDON_LOADED","RutaXP")
            RutaXPWorldMapTracking.Refresh(om)
            assert(not next(sets))
            openMap(1426)
            local inn=assert(service("Tabernero Belm"))
            assert(inn.texture==10032 and inn.placement[2]==inn.anchorRegion)
            local repair=assert(service("Boran Tintiyerro"))
            local function center(pin)
                return pin.u*20000*scale+pin.placement[4], pin.v*14000*scale-pin.placement[5]
            end
            local box=assert(service("Shelby Petrepiedra"))
            local ix,iy=center(inn)
            local bx,by=center(box)
            assert(math.abs(ix-bx)>=18 or math.abs(iy-by)>=18)
            assert(repair==service("Gamili Escardida"))
            scale=180
            callbacks.OpenMap_ViewChanged()
            assert(service("Boran Tintiyerro")~=service("Gamili Escardida"))
            local count=#sets.rutaxp_service_repair.pins
            WorldMapFrame:Hide()
            setFilter("Repair",false)
            openMap(1445)
            assert(not service("Boran Tintiyerro") and service("Tabernero Janene"))
            setFilter("Repair",true)
            assert(service("Boran Tintiyerro") and #sets.rutaxp_service_repair.pins==count)
        """)

    def test_native_flight_pin_remains_interactive_without_a_second_marker(self):
        self.lua.execute("""
            local existing = CreateFrame("Button", nil, WorldMapFrame:GetCanvas())
            existing.poiInfo = {nodeID=6}
            function WorldMapFrame:EnumeratePinsByTemplate(template)
                local result = template == "FlightPointPinTemplate" and existing
                return function() local pin=result; result=nil; return pin or nil end
            end
            Enum.FlightPathFaction = {Neutral=0, Horde=1, Alliance=2}
            C_TaxiMap = {GetTaxiNodesForMap=function(id)
                if id == 1426 then return {
                    {nodeID=6, name="Forjaz", position=CreateVector2D(.6,.3), faction=2},
                    {nodeID=99, name="Otro vuelo", position=CreateVector2D(.5,.35), faction=0},
                    {nodeID=88, name="Solo Horda", position=CreateVector2D(.52,.33), faction=1},
                } end
            end}
            nativeFlight = existing
        """)
        self.g.openMap(1426)
        self.assertTrue(self.g.nativeFlight.IsShown(self.g.nativeFlight))
        self.assertEqual(self.g.visible("Forjaz")[0], 0)
        self.assertEqual(self.g.visible("Otro vuelo")[0], 1)
        self.assertEqual(self.g.visible("Solo Horda")[0], 0)
        self.g.setFilter("TaxiNode", False)
        self.assertFalse(self.g.nativeFlight.IsShown(self.g.nativeFlight))
        self.assertEqual(self.g.visible("Otro vuelo")[0], 0)
        self.g.setFilter("TaxiNode", True)
        self.assertTrue(self.g.nativeFlight.IsShown(self.g.nativeFlight))
        self.assertEqual(self.g.visible("Forjaz")[0], 0)

    def test_embedded_flight_pins_track_player_zone_without_replacing_openmap_pins(self):
        self.lua.execute("""
            ns.char = {mapOnlyMyZone=true}
            local zone = 1426
            function C_Map.GetBestMapForUnit() return zone end
            function hooksecurefunc(object, method, callback)
                local previous = object[method]
                object[method] = function(...) previous(...); callback(...) end
            end
            local tracking = RutaXPWorldMapTracking
            tracking.Refresh = function() end
            local set = {pins={}, frame=CreateFrame("Frame", nil, WorldMapFrame)}
            local nodes = {}
            local function pin(id, zoneMap, known)
                local continent, point = C_Map.GetWorldPosFromMapPos(zoneMap, CreateVector2D(.5, .5))
                nodes[id] = {"Flight master", continent, point.x, point.y, 1}
                local p = CreateFrame("Button", nil, set.frame)
                p.node, p.known = id, known
                set.pins[id] = p
                return p
            end
            local dunMorogh, stranglethorn, undiscovered =
                pin(1, 1426, true), pin(2, 1434, true), pin(3, 1434, false)
            local mod = {IsStitched=function() return true end}
            function mod.RefreshFlightsFound()
                for _, marker in ipairs(set.pins) do marker:SetShown(marker.known) end
            end
            local open = {GetModule=function() return mod end, MapFlights={nodes=nodes},
                MapStitch={GetPinSet=function(key) if key == "flight" then return set end end}}
            ns.GetEmbeddedModule = function(name) if name == "OpenMap" then return open end end
            mod.RefreshFlightsFound()
            openMap(1415)
            assert(dunMorogh:IsShown() and not stranglethorn:IsShown())
            mod.RefreshFlightsFound()
            assert(not stranglethorn:IsShown(), "OpenMap refresh must not reveal filtered pins")
            zone = 1434
            fire("ZONE_CHANGED_NEW_AREA")
            assert(not dunMorogh:IsShown() and stranglethorn:IsShown() and not undiscovered:IsShown())
            ns.char.mapOnlyMyZone = nil
            fire("ZONE_CHANGED_NEW_AREA")
            assert(dunMorogh:IsShown() and stranglethorn:IsShown() and not undiscovered:IsShown())
        """)


if __name__ == "__main__":
    unittest.main()
