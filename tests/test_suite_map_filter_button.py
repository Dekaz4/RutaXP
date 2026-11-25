import unittest

from lupa.lua51 import LuaRuntime

from test_suite_native_map import ADDON, CLIENT


MENU = """
WorldMapFrame.ScrollContainer = CreateFrame("Frame",nil,WorldMapFrame)
MenuUtil, MenuResponse = {}, {Refresh=2}
AnchorUtil = {CreateAnchor=function(...) return {...} end}
UNCHECK_ALL = "Desmarcar todo"
local baseCreate = CreateFrame
function CreateFrame(kind,name,parent,template)
    local f = baseCreate(kind,name,parent)
    if kind ~= "DropdownButton" then return f end
    assert(template=="UIPanelButtonTemplate" and _G[name]==nil)
    _G[name]=f
    function f:SetText(label) self.label=label end
    function f:SetMenuAnchor(anchor) self.menuAnchor=anchor end
    function f:SetupMenu(fn) self.generator=fn end
    function f:IsMenuOpen() return self.open end
    function f:CloseMenu() self.open=false end
    function f:GenerateMenu()
        local rows={}
        local menu={}
        function menu:CreateButton(label,fn) rows[label]={click=fn} end
        function menu:CreateCheckbox(label,checked,click,data)
            local row={checked=function() return checked(data) end, click=function() return click(data) end}
            function row:AddInitializer(init)
                local frame=baseCreate("Button")
                function frame:AttachTexture()
                    self.icon=baseCreate("Texture")
                    function self.icon:SetTexture(t) self.texture=t end
                    return self.icon
                end
                frame.fontString=baseCreate("FontString")
                function frame.fontString:GetUnboundedStringWidth() return 50 end
                init(frame)
                row.texture=frame.icon.texture
            end
            rows[label]=row
            return row
        end
        self.generator(self,menu)
        self.rows=rows
    end
    function f:OpenMenu() self.open=true; self:GenerateMenu() end
    return f
end
local count, info, filter = C_Minimap.GetNumTrackingTypes, C_Minimap.GetTrackingInfo, C_Minimap.GetTrackingFilter
local spell = {name="Buscar minerales",texture=999,type="spell",active=true}
function C_Minimap.GetNumTrackingTypes() return count()+1 end
function C_Minimap.GetTrackingInfo(i) if i<=count() then return info(i) else return spell end end
function C_Minimap.GetTrackingFilter(i) if i<=count() then return filter(i) else return {spellID=2580} end end
writes = 0
function C_Minimap.SetTracking(i,on)
    assert(i<=count(), "changing the service filters must leave profession tracking alone")
    info(i).active=on
    writes=writes+1
    fire("MINIMAP_UPDATE_TRACKING")
end

function mockStitchedMap()
    local state = {stitched=true, sets={}}
    local layer = CreateFrame("Frame", nil, WorldMapFrame)
    local stitch = {IsBuilt=function() return true end,
        FromYards=function(_,north,west) return .5+west/100000,.5-north/100000 end,
        Rect=function() return 0,1,0,1 end, Root=function() return layer end,
        Size=function() return 20000,14000 end}
    function stitch.PinSet(key)
        if state.sets[key] then return state.sets[key] end
        local set = {on=true, pins={}, frame=CreateFrame("Frame",nil,layer)}
        state.sets[key] = set
        return set
    end
    function stitch.GetPinSet(key) return state.sets[key] end
    function stitch.ClearPinSet(set)
        for _, pin in ipairs(set.pins) do pin:Hide() end
        set.pins = {}
    end
    function stitch.SetPinSetOn(set, on) set.on=on; set.frame:SetShown(on) end
    function stitch.AddPin(set, u, v, look, row)
        local pin = CreateFrame("Button", nil, set.frame)
        pin.u, pin.v, pin.name, pin.data, pin.texture = u, v, row[5], row, look.texture
        set.pins[#set.pins+1] = pin
        return pin
    end
    local mod = {IsStitched=function() return state.stitched end}
    local om = {MapStitch=stitch,GetModule=function() return mod end}
    function mod:Refresh() RutaXPWorldMapTracking.Refresh(om) end
    function state:SelectStitched(on) self.stitched=on; layer:SetShown(on) end
    ns.GetEmbeddedModule=function() return om end
    return state
end
"""


class WorldMapFilterButtonTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime()
        self.lua.execute(CLIENT + MENU + "\nns.char = {}")
        for name in ("WorldMapTracking", "WorldMapServiceData", "WorldMapServices", "WorldMapAreaPins", "WorldMapNative"):
            self.lua.execute((ADDON / (name + ".lua")).read_bytes(), "RutaXP", self.lua.globals().ns)
        self.lua.execute('fire("PLAYER_LOGIN"); openMap(1426); b=RutaXPWorldMapFiltersButton')

    def test_windowed_and_maximized_maps_share_one_control_anchored_to_viewport(self):
        self.lua.execute("""
            for _,width in ipairs({550,1200,550}) do
                WorldMapFrame.ScrollContainer:SetSize(width,400)
                fire("ADDON_LOADED","Blizzard_WorldMap")
                assert(b==RutaXPWorldMapFiltersButton and b:IsVisible() and b.label=="Filtros")
                assert(b.parent==WorldMapFrame and b.anchor[1]=="TOPRIGHT" and b.anchor[3]=="TOPRIGHT")
                assert(b.anchor[2]==WorldMapFrame.ScrollContainer and b.anchor[4]<0 and b.anchor[5]<0)
                assert(b.menuAnchor[1]=="TOPRIGHT" and b.menuAnchor[2]==b and b.menuAnchor[3]=="BOTTOMRIGHT")
            end
            assert(writes==0)
        """)

    def test_native_icons_toggle_both_ways_and_clear_all_persists_on_reopen(self):
        self.lua.execute("""
            b:OpenMenu()
            local n=0; for _ in pairs(b.rows) do n=n+1 end
            assert(n==13 and b.rows["Desmarcar todo"] and not b.rows["Buscar minerales"])
            assert(b.rows.Innkeeper.checked() and b.rows.Innkeeper.texture==10032)
            assert(b.rows.Innkeeper.click()==MenuResponse.Refresh)
            settle()
            assert(not b.rows.Innkeeper.checked() and not service("Tabernero Belm"))
            local index=RutaXPWorldMapTracking.Info("innkeeper").index
            assert(not C_Minimap.GetTrackingInfo(index).active)
            -- Change the actual minimap while the map menu remains open.
            setFilter("Innkeeper",true)
            assert(b:IsMenuOpen() and b.rows.Innkeeper.checked() and service("Tabernero Belm"))
            assert(b.rows["Desmarcar todo"].click()==MenuResponse.Refresh)
            settle()
            for key in pairs(RutaXPWorldMapTracking.Read()) do assert(not RutaXPWorldMapTracking.Get(key)) end
            assert(C_Minimap.GetTrackingInfo(C_Minimap.GetNumTrackingTypes()).active)
            assert(not service("Tabernero Belm") and not service("Boran Tintiyerro"))
            WorldMapFrame:Hide(); b.scripts.OnHide(b); assert(not b:IsMenuOpen())
            openMap(1426); b:OpenMenu()
            assert(not b.rows.Repair.checked() and not b.rows.Innkeeper.checked())
            b.rows.Repair.click(); settle()
            assert(service("Boran Tintiyerro") and not service("Tabernero Belm"))
        """)

    def test_stitched_filters_control_actual_service_sets_when_switching_renderers(self):
        self.lua.execute("""
            local world = mockStitchedMap()
            openMap(1445)
            local inn=assert(world.sets.rutaxp_service_innkeeper)
            local count=#inn.pins
            assert(inn.on and count>0)
            b:OpenMenu(); b.rows.Innkeeper.click(); settle()
            assert(not inn.on and not b.rows.Innkeeper.checked())
            setFilter("Innkeeper",true); assert(inn.on and #inn.pins==count)
            b.rows["Desmarcar todo"].click(); settle()
            assert(not inn.on)
            world:SelectStitched(false); openMap(1426)
            assert(not service("Tabernero Belm") and RutaXPWorldMapFiltersButton==b)
            b.rows.Innkeeper.click(); settle(); assert(service("Tabernero Belm"))
            world:SelectStitched(true); openMap(1445); assert(inn.on)
        """)

    def test_only_my_zone_follows_the_character_even_on_the_continent_map(self):
        self.lua.execute("""
            local continent, stranglethorn, duskwood = 1415, 1434, 1431
            ns.worldMapServiceEra[continent] = {0, 10000, 10000, -20000, -10000}
            local actualZone = stranglethorn
            function C_Map.GetBestMapForUnit() return actualZone end
            local getMapInfo = C_Map.GetMapInfo
            function C_Map.GetMapInfo(id)
                if id == 9910 then
                    return {mapID=id, parentMapID=stranglethorn, mapType=Enum.UIMapType.Micro}
                end
                return getMapInfo(id)
            end
            local bootyBay, darkshire = "Tabernero Skindle", "Tabernera Trelayne"
            local nativePins, taxiNodes = {}, {}
            local function continentPosition(zone)
                local world, position = C_Map.GetWorldPosFromMapPos(zone, CreateVector2D(.6, .6))
                local _, point = C_Map.GetMapPosFromWorldPos(world, position, continent)
                return point
            end
            local function addPin(template, point)
                local pins = nativePins[template] or {}
                nativePins[template] = pins
                local pin = CreateFrame("Button", nil, WorldMapFrame:GetCanvas())
                function pin:GetPosition() return point:GetXY() end
                pins[#pins+1] = pin
                return pin
            end
            local function addFlight(zone, id, name, native)
                local point = continentPosition(zone)
                taxiNodes[#taxiNodes+1] = {nodeID=id, name=name, position=point}
                if native then
                    local pin = addPin("FlightPointPinTemplate", point)
                    pin.poiInfo = {nodeID=id}
                    return pin
                end
            end
            C_TaxiMap = {GetTaxiNodesForMap=function(id) return id == continent and taxiNodes or {} end}
            function WorldMapFrame:EnumeratePinsByTemplate(template)
                local pins = nativePins[template] or {}
                local i = 0
                return function() i = i+1; return pins[i] end
            end
            local northFlight = addFlight(duskwood, 97, "Vuelo de Villa Oscura", true)
            local southFlight = addFlight(stranglethorn, 98, "Vuelo de Bahía del Botín", true)
            addFlight(stranglethorn, 99, "Otro vuelo de Tuercespina")
            addFlight(duskwood, 100, "Otro vuelo de Bosque del Ocaso")
            local function checkFlights(north, south)
                assert(northFlight:IsShown() == north and southFlight:IsShown() == south)
                assert((service("Otro vuelo de Bosque del Ocaso") ~= nil) == north)
                assert((service("Otro vuelo de Tuercespina") ~= nil) == south)
            end
            local far = continentPosition(duskwood)
            local farOffer = addPin("QuestOfferPinTemplate", far)
            local tracked = addPin("StorylineQuestPinTemplate", far)
            local waypoint = addPin("UserWaypointPinTemplate", far)
            farOffer.questID, tracked.questID = 201, 202
            C_SuperTrack = {GetSuperTrackedQuestID=function() return tracked.questID end}

            openMap(continent)
            assert(service(bootyBay) and service(darkshire))
            checkFlights(true, true)
            b:OpenMenu()
            local function areaFilter() return assert(b.rows["Solo mi zona"]) end
            assert(not areaFilter().checked())
            assert(areaFilter().click() == MenuResponse.Refresh)
            settle()
            assert(areaFilter().checked() and ns.char.mapOnlyMyZone == true)
            assert(service(bootyBay) and not service(darkshire))
            checkFlights(false, true)
            assert(not farOffer:IsShown() and tracked:IsShown() and waypoint:IsShown())
            assert(writes == 0, "scope must not change the native minimap settings")

            actualZone = 9910
            fire("ZONE_CHANGED")
            assert(service(bootyBay) and not service(darkshire))
            actualZone = duskwood
            fire("ZONE_CHANGED_NEW_AREA")
            assert(service(darkshire) and not service(bootyBay))
            checkFlights(true, false)
            assert(farOffer:IsShown() and tracked:IsShown() and waypoint:IsShown())
            assert(WorldMapFrame:GetMapID() == continent)

            setFilter("Repair", false)
            assert(not service("Avette Bosquevil"))
            areaFilter().click()
            settle()
            assert(not areaFilter().checked())
            assert(service(bootyBay) and service(darkshire))
            checkFlights(true, true)
            assert(not service("Avette Bosquevil") and not service("Fargon Mortalak"))
        """)

    def test_only_my_zone_filters_stitched_pins_with_character_setting_on_reopen(self):
        self.lua.execute("""
            local actualZone = 1434
            function C_Map.GetBestMapForUnit() return actualZone end
            mockStitchedMap()

            local bootyBay, darkshire = "Tabernero Skindle", "Tabernera Trelayne"
            ns.char.mapOnlyMyZone = true
            openMap(1415)
            b:OpenMenu()
            assert(b.rows["Solo mi zona"].checked() and service(bootyBay) and not service(darkshire))

            WorldMapFrame:Hide()
            b.scripts.OnHide(b)
            actualZone = 1431
            fire("ZONE_CHANGED_NEW_AREA")
            openMap(1415)
            assert(service(darkshire) and not service(bootyBay))
            b:OpenMenu()
            b.rows["Solo mi zona"].click()
            settle()
            assert(service(bootyBay) and service(darkshire))
        """)
