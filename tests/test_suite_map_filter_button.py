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
"""


class WorldMapFilterButtonTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime()
        self.lua.execute(CLIENT + MENU)
        for name in ("WorldMapTracking", "WorldMapServiceData", "WorldMapServices", "WorldMapNative"):
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
            assert(n==12 and b.rows["Desmarcar todo"] and not b.rows["Buscar minerales"])
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
            local sets, stitched = {}, true
            local s = {IsBuilt=function() return true end,
                FromYards=function(_,n,w) return .4+w/100000,.4+n/100000 end,
                Rect=function() return .1,.3,.4,.6 end}
            function s.PinSet(key)
                assert(not sets[key]); sets[key]={on=true,pins={}}
                return sets[key]
            end
            function s.AddPin(set,x,y,look,row)
                local pin={SetScript=function() end, name=row[5], texture=look.texture}
                set.pins[#set.pins+1]=pin
                return pin
            end
            function s.SetPinSetOn(set,on) set.on=on end
            local mod = {IsStitched=function() return stitched end}
            local om = {MapStitch=s,GetModule=function() return mod end}
            function mod:Refresh() RutaXPWorldMapTracking.Refresh(om) end
            ns.GetEmbeddedModule=function() return om end
            openMap(1445)
            local inn=assert(sets.rutaxp_service_innkeeper)
            local count=#inn.pins
            assert(inn.on and count>0)
            b:OpenMenu(); b.rows.Innkeeper.click(); settle()
            assert(not inn.on and not b.rows.Innkeeper.checked())
            setFilter("Innkeeper",true); assert(inn.on and #inn.pins==count)
            b.rows["Desmarcar todo"].click(); settle()
            assert(not inn.on)
            stitched=false; openMap(1426)
            assert(not service("Tabernero Belm") and RutaXPWorldMapFiltersButton==b)
            b.rows.Innkeeper.click(); settle(); assert(service("Tabernero Belm"))
            stitched=true; openMap(1445); assert(inn.on)
        """)
