"""Exercise the Journey renderer with WoW frames and (when available) the owner's UI."""
import os
from pathlib import Path
import tempfile
import unittest

from lupa.lua51 import LuaRuntime
from tools import suite_journey

ROOT = Path(__file__).resolve().parents[1]
NATIVE = Path(os.environ.get("RUTAXP_JOURNEY", "E:/WOW/World of Warcraft/_forever_/Interface/AddOns/Journey"))
EMBEDDED = NATIVE.parent / "RutaXP/Modules/Journey"
HAS_JOURNEY = (NATIVE / "Journey.toc").is_file() or (EMBEDDED / "lib/TomCats/Arrows.lua").is_file()


def journey_sources():
    if (NATIVE / "Journey.toc").is_file():
        return suite_journey.contents(NATIVE)
    return ((name, (EMBEDDED / name).read_bytes()) for name in suite_journey.SCRIPTS)


class JourneyContentsTests(unittest.TestCase):
    def test_personal_art_and_load_list_are_explicit_and_exclude_other_content(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in suite_journey.SCRIPTS:
                file = root / name
                file.parent.mkdir(exist_ok=True, parents=True)
                source = "select(2, ...).SetupGlobalFacade()\n"
                if name == "lib/TomCats/Arrows.lua":
                    source += ("ArrowMixin={}\n"
                               "function ArrowMixin:SetTarget(targetX, targetY, mapID, disablePingAnimation)\n"
                               "local _, coordinate = C_Map.GetWorldPosFromMapPos(mapID, { x = targetX, y = targetY })\n"
                               "return coordinate\nend\n")
                if name == "Tools.lua":
                    source += "--[[ Texture Functions ]]\nfunction AddTexture() end\n--[[ Text Manipulation Functions ]]"
                file.write_text(source)
            (root / "images").mkdir()
            for name in suite_journey.IMAGES:
                (root / "images" / name).write_bytes(b"fixture")
            (root / "license.txt").write_text("owner notice")
            for name in ("Main.lua", "metadata.lua", "images/unused.png", "signed-guide.xml"):
                (root / name).write_text("EXCLUDE")
            files = dict(suite_journey.contents(root))
            self.assertEqual([p for p in files if p.endswith(".lua")], suite_journey.entries(root))
            self.assertFalse(any(b"EXCLUDE" in data for data in files.values()))
            self.assertTrue(all(b"RutaXPJourneyEnvironment" in files[p] for p in suite_journey.entries(root)))
            self.assertEqual(files["Modules/Journey/license.txt"], b"owner notice")
            lua = LuaRuntime(unpack_returned_tuples=True)
            lua.execute(MOCK)
            lua.execute("function RutaXPJourneyEnvironment() return _G end")
            lua.execute(files["Modules/Journey/lib/TomCats/Arrows.lua"])
            lua.execute("""
                local _,v=C_Map.GetWorldPosFromMapPos(1443,CreateVector2D(.5,.25))
                assert(v.x==650 and v.y==325 and ArrowMixin:SetTarget(.5,.25,1443,false,v)==v)
            """)
            self.assertEqual(dict(suite_journey.embedded_contents(files.__getitem__)), files)


MOCK = """
ns={char={}, OpenGuideLibrary=function() opened=true end}
module={}
function RutaXPModuleContext() return "Journey",module end
function GetLocale() return "esES" end
local noop=function() end
function Mixin(target, source) for k,v in pairs(source) do target[k]=v end return target end
function CreateFromMixins(source) return Mixin({},source) end
function CreateColor(r,g,b) return {r=r,g=g,b=b} end
local eventFrames,all={},{}
local frame={}
frame.__index=frame
function frame:SetScript(k,fn) self.scripts[k]=fn end
function frame:GetScript(k) return self.scripts[k] end
function frame:HookScript(k,fn)
    local previous=self.scripts[k]
    self:SetScript(k,function(...) if previous then previous(...) end; fn(...) end)
end
function frame:RegisterEvent(k) self.events[k]=true end
function frame:Show() self.shown=true end
function frame:Hide() self.shown=false end
function frame:IsShown() return self.shown~=false end
function frame:IsVisible() return self:IsShown() and (not self.parent or self.parent:IsVisible()) end
function frame:SetShown(b) self.shown=b end
function frame:SetChecked(b) self.checked=b end
function frame:GetChecked() return self.checked end
function frame:SetHitRectInsets(...) self.hitRectInsets={...} end
function frame:SetToplevel(v) self.topLevel=v end
function frame:SetScale(v) self.scale=v end
function frame:SetText(t) self.text=t end
function frame:GetText() return self.text end
function frame:GetTexture() return self.texture end
function frame:SetTexture(value) self.texture=value end
function frame:SetRotation(angle) self.drawCount=(self.drawCount or 0)+1; self.angle=angle end
function frame:GetParent() return self.parent end
function frame:SetParent(p) self.parent=p end
function frame:GetStringHeight() return 14 end
function frame:GetStringWidth() return 80 end
function frame:EnableMouse(b) self.mouse=b end
function frame:SetOwner(owner) self.owner=owner end
function frame:SetSize(w,h) self.w,self.h=w,h end
function frame:SetWidth(w) self.w=w end
function frame:SetHeight(h) self.h=h end
function frame:GetHeight() return self.h or 30 end
function frame:GetWidth() return self.w or 200 end
function frame:GetSize() return self:GetWidth(), self:GetHeight() end
function frame:GetVerticalScrollRange() return 0 end
function frame:GetVerticalScroll() return 0 end
function frame:GetPoint() return "CENTER",UIParent,"CENTER",0,0 end
function frame:GetFrameLevel() return self.level or 1 end
function frame:GetDrawLayer() return "ARTWORK",1 end
function frame:GetTexCoord() return 0,1,0,1 end
function frame:SetFrameLevel(n) self.level=n end
function frame:IsEnabled() return true end
function frame:IsPlaying() return false end
function frame:GetFont() return "test-font",12 end
function frame:CreateTexture() return CreateFrame("texture",nil,self) end
frame.CreateMaskTexture,frame.CreateFontString,frame.CreateAnimationGroup=frame.CreateTexture,frame.CreateTexture,frame.CreateTexture
frame.CreateAnimation=frame.CreateTexture
function frame:GetHighlightTexture() return self:CreateTexture() end
for _,name in ipairs({"SetPoint","SetScale","SetAllPoints","SetAtlas","SetTexture","SetAlpha","SetTextColor",
    "SetMovable","SetClampedToScreen","SetTextScale","ClearAllPoints","SetSize","SetFrameStrata","Disable",
    "SetEnabled","SetDisabledTexture","SetNormalTexture","SetPushedTexture","SetHighlightTexture","SetParent",
    "OnBackdropLoaded","SetScrollChild","EnableMouseWheel","SetVerticalScroll","EnableMouse","SetHyperlinksEnabled",
    "SetColorTexture","AddMaskTexture","SetFromScale","SetToScale","SetTarget","SetDuration","SetOrder","SetDegrees",
    "SetLooping","RegisterForDrag","RegisterForClicks","SetJustifyH","SetIndentedWordWrap","SetTexCoord","SetDrawLayer",
    "SetDesaturated","SetBlendMode","SetFontObject","CopyFontObject","SetTarget","SetFromAlpha","SetToAlpha",
    "SetStartDelay","SetToFinalAlpha","Stop","Play","SetShadowOffset","SetVertexColor","SetFont","SetRotation"}) do
    frame[name]=frame[name] or noop
end
function CreateFrame(kind,name,parent,template)
    local f=setmetatable({kind=kind,scripts={},events={},parent=parent},frame)
    if name then _G[name]=f end
    if template=="UIPanelButtonTemplate" then
        f.Middle,f.Left,f.Right=f:CreateTexture(),f:CreateTexture(),f:CreateTexture()
    end
    all[#all+1]=f
    return f
end
function CreateFont(name) return CreateFrame("font",name) end
function event(e,...) for _,f in ipairs(all) do if f.events[e] then f.scripts.OnEvent(f,e,...) end end end
function tick(dt) for _,f in ipairs(all) do if f:IsShown() and f.scripts.OnUpdate then f.scripts.OnUpdate(f,dt or .3) end end end
UIParent=CreateFrame(); UIParent:SetHeight(900); Minimap=CreateFrame(); GameFontWhiteSmall=CreateFrame()
GameTooltip=CreateFrame(); GameTooltip_Hide=noop
IsInInstance=function() return false end; InCombatLockdown=IsInInstance; IsShiftKeyDown=IsInInstance
function UnitPosition() return 500,500,0,0 end
function GetPlayerFacing() return .5 end
function GetCVar() return "0" end
C_Minimap={GetViewRadius=function() return 150 end}
local currentWorld=0
function CreateVector2D(x,y)
    return {x=x,y=y,GetXY=function(self) return self.x,self.y end}
end
C_Map={GetWorldPosFromMapPos=function(map,p)
    assert(getfenv(2)==_G, "unable to find mixin or metatable (Vector2DMixin) in a private environment")
    assert(type(p.GetXY)=="function", "GetWorldPosFromMapPos requires a Vector2DMixin")
    local x,y=p:GetXY()
    return currentWorld,CreateVector2D(x*1300,y*1300)
end}
function remote() currentWorld=1 end
function GetTime() return 0 end
local task={text="Usa el objeto",manual=true,checked=false,step=2}
guide={name="Elwynn",group="Alianza",steps={{},{},{}}}
local mark=true
ns.GuideEngine={
    Ready=function() return true end,
    Current=function() return guide,2 end,
    Tasks=function() return {task} end,
    ToggleTask=function(t) assert(t==task); t.checked=not t.checked; notified() end,
    Advance=function(d) moved=d end, Subscribe=function(fn) notified=fn end,
    PresentWithJourney=function(b) presenting=b end,
    Waypoint=function() if mark then return 1429,.6,.7,"Villadorada" end end,
}
function loseWaypoint() mark=false end
function assertVisibleCompassCount(expected)
    local hud=RutaXPJourneyScreenArrow
    local count=hud and hud.container:IsVisible() and 1 or 0
    if ns.navigationFrame and ns.navigationFrame.arrow:IsVisible() then count=count+1 end
    for _,f in ipairs(all) do
        if f.ClearTarget and f.ping then
            if f:IsVisible() then count=count+1 end
            if f.ping:IsVisible() then count=count+1 end
        end
    end
    assert(count==expected, ("expected %d visible directions, got %d"):format(expected,count))
end
function assertHudDistances(expected)
    local hud=RutaXPJourneyScreenArrow
    assert(hud.container:IsShown(), "compass should be visible")
    assert((hud.label:GetText() or "")=="", "unexpected instruction under the compass")
    local actual=hud.distLabel:GetText() or ""
    assert(actual==expected, ("expected '%s', got '%s'"):format(expected,actual))
end
ns.GuideResume={Status=function() return status,statusText end}
function getTaskIcon()
    return RutaXPJourneyEnvironment().UI.GetComponent("TaskGroupContainers").Get(1).contents.taskContainers[1].icon
end
"""


@unittest.skipUnless(HAS_JOURNEY, "the owner's Journey copy is required")
class NativeJourneyTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(MOCK)
        g = self.lua.globals()
        for name in ("ArrowStyles", "GuideJourney"):
            self.lua.execute((ROOT / f"RutaXP/{name}.lua").read_text(encoding="utf8"), "RutaXP", g.ns)
        self.assertFalse(self.lua.eval("ns.GuideJourney:Available()"))
        for filename, data in journey_sources():
            if filename.endswith(".lua"):
                self.lua.execute(data, "RutaXP", g.ns)
        self.lua.execute('event("PLAYER_LOGIN"); tick()')

    def test_real_journey_components_render_steps_and_preserve_interactions(self):
        self.lua.execute("""
            local scope=RutaXPJourneyEnvironment()
            assert(ns.GuideJourney:Available() and ns.GuideJourney:IsShown() and presenting)
            local panel=scope.UI.GetComponent("TaskGroupContainers").Get(1)
            assert(panel.contents.taskContainers[1].text.text=="Usa el objeto")
            local icon=getTaskIcon()
            icon.scripts.OnClick(icon)
            tick()
            assert(getTaskIcon().row.checked)
            local next=scope.UI.GetComponent("HeaderNextButton").frame
            next.scripts.OnClick(); assert(moved==1)
            scope.UI.GetComponent("HeaderSettingsButton").frame.scripts.OnClick()
            assert(opened)
            assertHudDistances("454 m")
            loseWaypoint(); tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
        """)

    def test_one_visible_compass_across_minimap_range_target_changes_and_toggle(self):
        self.lua.execute("""
            local goalX,playerX=800,500
            ns.GuideEngine.Waypoint=function() return 1429,goalX/1300,500/1300,"Destino" end
            UnitPosition=function() return playerX,500,0,0 end
            local function check(distanceText)
                tick()
                assertHudDistances(distanceText)
                assertVisibleCompassCount(1)
            end
            check("274 m")              -- Beyond the minimap: Journey's directional marker.
            playerX=750; check("46 m")  -- Inside the minimap: Journey switches to its ping.
            goalX=1050; check("274 m")
            ns.GuideJourney:Hide(); tick()
            assertVisibleCompassCount(0)
            ns.GuideJourney:Show(); check("274 m")
        """)

    def test_live_hud_filters_small_rotations_and_reserves_arrival_for_the_destination(self):
        self.lua.execute("""
            local view, hud = ns.GuideJourney, RutaXPJourneyScreenArrow
            local texture = hud.arrowTexture
            local facing, yards = 1, 5
            GetPlayerFacing = function() return math.rad(facing) end
            UnitPosition = function() return .6*1300-yards,.7*1300,0,0 end
            tick()
            view:SetCompassTarget("muelle", false, 110)
            tick(0)
            local count = texture.drawCount
            assert(math.abs(texture.angle - math.rad(-1)) < 1e-8)
            facing=359; tick(0)
            assert(texture.drawCount == count) -- Two degrees through north.
            facing=358.1; tick(0)
            assert(texture.drawCount == count+1) -- Movement accumulates since the last draw.
            facing=358; view:SetCompassTarget("cadaver",false,110); tick(0)
            assert(texture.drawCount == count+2)
            yards=.25; tick(0)
            assert(texture:IsShown() and not hud.pingFrame:IsShown() and hud.distLabel:GetText()=="101 m")
            view:SetCompassTarget("cadaver",false,nil); tick(0)
            assert(texture:IsShown() and hud.distLabel:GetText()=="0 m")
            view:SetCompassTarget("cadaver",true,nil); tick(0)
            assert(not texture:IsShown() and hud.pingFrame:IsShown())
            ns.char.arrowAppearance={style="forge",size=150,showText=false}
            ns.ArrowStyles:Refresh()
            assert(texture:GetTexture()==ns.ArrowStyles:GetTexture() and math.abs(hud.scale-.9)<1e-8)
            assert(not hud.label:IsShown() and not hud.distLabel:IsShown() and not hud.shadowContainer:IsShown())
            ns.char.arrowAppearance.showText=true; ns.ArrowStyles:Refresh()
            assert(hud.distLabel:IsShown())
            yards=5; tick(0)
            assert(texture:IsShown() and not hud.pingFrame:IsShown())
            local before=texture.drawCount
            loseWaypoint(); tick()
            assert(not hud.container:IsShown())
            ns.GuideEngine.Waypoint=function() return 1429,.6,.7,"Otra misión" end
            tick(); assert(hud.container:IsShown() and texture.drawCount==before+1)
        """)

    def test_walking_arrow_eases_anchor_changes_but_follows_facing_immediately(self):
        self.lua.execute("""
            local time, facing = 0, 0
            function GetTime() return time end
            function GetPlayerFacing() return facing end
            local key, north, west = "misma ruta", 570, 500
            ns.GuideEngine.Waypoint = function()
                return 1429, north/1300, west/1300, "Camino",
                    {continent=0, north=north, west=west},
                    {walking=true, walkingRouteKey=key, walkingDistance=100}
            end
            local texture = RutaXPJourneyScreenArrow.arrowTexture
            local function heading(expected)
                local diff = (texture.angle - math.rad(expected) + math.pi) % (2*math.pi) - math.pi
                assert(math.abs(diff) < 1e-5, "heading: " .. math.deg(texture.angle))
            end
            tick()
            heading(0)
            north, west = 500, 570
            tick() -- A new reference for the same walking route.
            heading(0)
            time = .09; tick(.09)
            heading(45)
            facing = math.rad(30); tick(0)
            heading(15)
            time = .18; tick(.09)
            heading(60)
            key, north, west = "otro objetivo", 430, 500
            tick()
            heading(150) -- New destinations do not interpolate.
        """)

    def test_task_names_use_journey_colors_and_recycled_icons_use_the_current_action(self):
        self.lua.execute("""
            local scope=RutaXPJourneyEnvironment()
            local proto=getmetatable(getTaskIcon().texture)
            function proto:SetAtlas(id) self.atlas=id; self.path=nil end
            function proto:SetTexture(id) self.path=id; self.atlas=nil end
            function proto:SetVertexColor(r,g,b) self.r,self.g,self.b=r,g,b end
            function proto:SetDesaturated(value) self.gray=value end
            local available=true
            C_Texture={GetAtlasInfo=function(id)
                if available then return {width=14,height=28} end
            end}
            local currentRow
            ns.GuideEngine.Tasks=function() return {currentRow} end
            local function render(row)
                currentRow=row
                ns.GuideJourney:Refresh(); tick()
                local r=scope.UI.GetComponent("TaskGroupContainers").Get(1).contents.taskContainers[1]
                return r.text:GetText(),r.icon.texture
            end
            local title="El trébol de O'Brien"
            local text,icon=render({action="accept",text="Acepta "..title.." de Ana. Anabel sigue aquí.",
                questTitle=title,npcName="Ana",status="active",texture="legacy-accept"})
            assert(text=="Acepta |cffffff00"..title.."|r de |cff9dff9dAna|r. Anabel sigue aquí.")
            assert(icon.atlas=="QuestNormal" and icon:GetWidth()<icon:GetHeight())
            text,icon=render({action="turnin",text="Entrega "..title,questTitle=title,status="ready"})
            assert(text=="Entrega |cffffa500"..title.."|r" and icon.atlas=="QuestTurnin")
            text,icon=render({action="kill",text="Derrota a Ogrón (0/3)",npcName="Ogrón"})
            assert(text=="Derrota a |cffff6363Ogrón|r (0/3)" and icon.atlas=="VignetteKill")
            text,icon=render({action="collect",text="Recoge el Cáliz; habla con Aris.",
                itemName="Cáliz",npcName="Aris",npcReaction="neutral"})
            assert(text=="Recoge el |cffe36ee4Cáliz|r; habla con |cffffd100Aris|r.")
            assert(icon.atlas=="VignetteLoot")
            text,icon=render({action="goto", text="Ve a Bahía del Botín", placeName="Bahía del Botín"})
            assert(text=="Ve a |cffffd100Bahía del Botín|r")
            text,icon=render({action="turnin",text="Ya entregada",status="done"})
            assert(icon.atlas=="Capacitance-General-WorkOrderCheckmark")
            text,icon=render({action="turnin",text="Todavía no",status="blocked"})
            assert(icon.atlas=="services-icon-warning")
            available=false
            text,icon=render({action="kill",text="Omitido",status="skip",texture="own-sword",iconColor={.9,.4,.3}})
            assert(not icon.atlas and icon.path=="own-sword" and icon.gray and icon.r==.9)
            text,icon=render({text="|cff00ff00Texto previo|r",texture="plain"})
            assert(text=="|cff00ff00Texto previo|r" and icon.path=="plain" and icon.r==1 and not icon.gray)
        """)

    def test_pending_zone_hides_provisional_target_and_renders_resume_message(self):
        self.lua.execute("""
            status,statusText="pending","¿Continuar por Desolace?"
            ns.GuideJourney:Refresh(); tick()
            local row=RutaXPJourneyEnvironment().UI.GetComponent("TaskGroupContainers").Get(1).contents.taskContainers[1]
            assert(row.text.text==statusText)
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            status=nil; ns.GuideJourney:Refresh(); tick()
            assert(RutaXPJourneyScreenArrow.container:IsShown())
            remote(); tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            ns.GuideJourney:Hide(); assert(not ns.GuideJourney:IsShown() and ns.char.journeyDisplay.hidden)
            ns.GuideJourney:Show(); assert(ns.GuideJourney:IsShown())
        """)

    def test_journal_shows_live_quests_without_moving_the_restored_character_or_their_friend(self):
        self.lua.execute("""
            local scope=RutaXPJourneyEnvironment()
            local ui=scope.UI
            local next=ui.GetComponent("HeaderNextButton").frame
            local back=ui.GetComponent("HeaderBackButton").frame
            local function row(n) return ui.GetComponent("TaskGroupContainers").Get(1).contents.taskContainers[n] end
            local stale=row(1).icon
            local party="Con tu compañero"
            local count="1/3"
            local pin=nil
            ns.GuideCarryover={
                Rows=function() return {{text="La caída de Dun Modr · "..party,questID=472},{text=count}} end,
                OpenQuest=function(id) openedQuest=id end,
                Waypoint=function() if pin then return 1437,pin,.27,"La caída de Dun Modr" end end,
            }
            status="journal"
            ns.GuideJourney:Refresh(); tick()
            local heading,sub=scope.HeaderService.GetHeaderTitles()
            assert(heading=="Misiones en curso" and sub=="Continuar con tu diario")
            assert(row(1).text.text:find(party,1,true) and row(2).text.text==count)
            assert(not next:IsShown() and not back:IsShown() and not scope.HeaderService.GetStepText())
            assert(not RutaXPJourneyScreenArrow.container:IsShown() and not scope.State.IsScreenArrowEnabled())
            next.scripts.OnClick(next); back.scripts.OnClick(back); stale.scripts.OnClick(stale)
            assert(not moved and not ns.GuideEngine.Tasks()[1].checked)
            local questIcon,countIcon=row(1).icon,row(2).icon
            assert(questIcon.mouse and not countIcon.mouse)
            countIcon.scripts.OnClick(countIcon); assert(not openedQuest)
            questIcon.scripts.OnEnter(questIcon); assert(GameTooltip.text=="Ver esta misión en el diario")
            questIcon.scripts.OnClick(questIcon); assert(openedQuest==472)
            pin=.49; tick(); assert(RutaXPJourneyScreenArrow.container:IsShown())
            assertHudDistances("185 m")
            local available=false
            ns.Walking={
                IsEnabled=function() return true end,
                Resolve=function(_,p)
                    assert(p.mapID==1437 and p.x==pin and p.y==.27)
                    p.navigationBlocked=not available
                    p.navigationNotice="Esperando al camino del diario"
                    if available then
                        p.walking=true
                        p.walkingDistance,p.walkingSegmentDistance=230,45
                    end
                    return p
                end,
            }
            tick(); tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            assert(row(3).text.text=="Esperando al camino del diario")
            available=true; tick(); tick()
            assertHudDistances("41 m / 210 m")
            ns.Walking=nil
            pin=1.2; tick(); assert(not RutaXPJourneyScreenArrow.container:IsShown())
            party="En tu diario"; event("GROUP_ROSTER_UPDATE"); tick()
            assert(row(1).text.text:find(party,1,true))
            count="2/3"; notified(); tick(); assert(row(2).text.text==count)
            ui.GetComponent("HeaderSettingsButton").frame.scripts.OnClick(); assert(opened)
            status="auto"; ns.GuideJourney:Refresh(); tick()
            assert(next:IsShown() and back:IsShown() and scope.HeaderService.GetHeaderTitles()=="Elwynn")
            assert(row(1).text.text=="Usa el objeto" and RutaXPJourneyScreenArrow.container:IsShown())
        """)


@unittest.skipUnless(HAS_JOURNEY, "the owner's Journey copy is required")
class OriginalGuideJourneyTests(unittest.TestCase):
    def test_original_tracker_duo_controls_and_walking_compass_in_native_journey(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(MOCK)
        lua.execute("""
            ns.GuideEngine=nil
            ns.char={tracker=true,arrow=true,arrowPosition={point="TOP",relativePoint="TOP",x=-76,y=-24}}
            ns.window=CreateFrame(); ns.window:Hide()
            ns.tracker=CreateFrame("Frame", nil, UIParent)
            local function label(text)
                local f=CreateFrame(); f:SetText(text); return f
            end
            ns.trackerTitle=label("Desolace (31–34)")
            ns.trackerStep=label("Tu amigo · Escolta a Dalinda")
            ns.trackerProgress=label("Juntos 12 · Tú 14")
            ns.trackerUpcomingLabel=label("En tu diario")
            ns.trackerText=label("Toma el barco en Menethil")
            ns.trackerCurrentCount=1
            local row=CreateFrame(); row.goalIndex=1; row.goalTitle="Busca a Dalinda"
            row.goalSub="Espera a tu compañero"; row.icon={GetTexture=function() return 73 end}
            row:SetScript("OnClick", function(self, button) clicked=self.goalIndex .. button end)
            ns.trackerRows={row}
            ns.trackerNext=CreateFrame(); ns.trackerNext.isEnabled=false
            ns.trackerNext:SetScript("OnClick", function() moved=true end)
            ns.trackerPrevious=CreateFrame(); ns.trackerPrevious.isEnabled=true
            ns.trackerPrevious:SetScript("OnClick", function() back=true end)
            function ns:GetGuideTravel() return nil end
            local g={title="Desolace",steps={}}
            function ns:GetDisplayedCurrent() return g,{}, {cursor=12} end
            function ns:GetCurrent() return g,{}, {cursor=14} end
            function ns:RefreshUI() end
            samples=0
            function ns:GetArrowWaypoint()
                samples=samples+1
                if sampledTurn then return sampledTurn end
                if not waiting then
                    return {mapID=1443, x=.549, y=.263, navigationBlocked=blocked,
                            navigationBearing=bearing, navigationBearingText=bearing and "Rumbo orientativo · calculando camino",
                            navigationNotice=blocked and "Recalculando desde tu posición"}
                end
            end
            function ns:CreateNavigation()
                local f=CreateFrame("Frame",nil,UIParent)
                f.arrow=CreateFrame("Frame",nil,f); f.hint=label("Tramo 8/8"); ns.navigationFrame=f
                ns.navigationUpdater=CreateFrame("Frame",nil,UIParent)
            end
            function hooksecurefunc(table, k, hook)
                local previous=table[k]
                table[k]=function(...) previous(...); hook(...) end
            end
        """)
        for name in ("ArrowStyles", "GuideOriginal", "GuideJourney"):
            lua.execute((ROOT / f"RutaXP/{name}.lua").read_text(encoding="utf8"), "RutaXP", lua.globals().ns)
        for filename, data in journey_sources():
            if filename.endswith(".lua"):
                lua.execute(data, "RutaXP", lua.globals().ns)
        lua.execute("""
            event("PLAYER_LOGIN"); tick()
            ns:CreateNavigation(); ns:GetArrowWaypoint(); tick()
            local env=RutaXPJourneyEnvironment()
            assert(ns.GuideJourney:IsShown() and not ns.tracker:GetParent():IsShown())
            local anchor=ns.char.journeyDisplay.HUDArrowLocation
            assert(anchor[1]=="TOP" and anchor[3]=="TOP" and anchor[5]==-80)
            assert(not ns.navigationFrame:GetParent():IsShown() and ns.navigationUpdater:GetParent()==UIParent)
            assert(env.HeaderService.GetStepText()=="Juntos 12 · Tú 14")
            local text=getTaskIcon().row.text
            assert(text:find("Busca a Dalinda",1,true) and text:find("Espera a tu compañero",1,true))
            assert(not env.GuideNavigationService.HasNextStep()); env.GuideNavigationService.SetStepToNext(); assert(not moved)
            env.GuideNavigationService.SetStepToPrevious(); assert(back)
            local icon=getTaskIcon(); icon.scripts.OnClick(icon, "RightButton"); assert(clicked=="1RightButton")
            local function directDistance(x,y)
                return ("%d m"):format(math.floor(math.sqrt((1300*x-500)^2+(1300*y-500)^2)*.9144+.5))
            end
            assertHudDistances(directDistance(.549,.263))
            assertVisibleCompassCount(1)
            for i=1,12 do tick() end; assert(samples==1)
            ns.GuideJourney:Hide(); tick()
            assert(not ns.char.tracker and not ns.GuideJourney:IsShown() and RutaXPJourneyScreenArrow.container:IsShown())
            assertVisibleCompassCount(1)
            ns.char.arrow=false; tick(); assert(not RutaXPJourneyScreenArrow.container:IsShown())
            assertVisibleCompassCount(0)
            ns.GuideJourney:Show(); tick()
            assert(ns.char.tracker and not ns.char.arrow and ns.GuideJourney:IsShown())
            ns.window:Show(); ns:RefreshUI(); tick(); assert(not ns.GuideJourney:IsShown())
            ns.window:Hide(); ns:RefreshUI(); tick(); assert(ns.GuideJourney:IsShown())
            ns.char.arrow=true
            waiting=true; ns:GetArrowWaypoint()
            ns.navigationFrame.arrow:Hide(); ns.navigationFrame.hint:SetText("Quédate en el barco")
            local newLabel=UIParent.CreateFontString
            floatingLabels={}
            UIParent.CreateFontString=function(self, ...)
                local label=newLabel(self, ...)
                floatingLabels[#floatingLabels+1]=label
                return label
            end
            function assertNoFloatingHint()
                for _,label in ipairs(floatingLabels) do
                    assert(not label:IsShown() or (label:GetText() or "")=="")
                end
            end
            tick()
            assertNoFloatingHint()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            waiting=false; ns:GetArrowWaypoint()
            ns.navigationFrame.hint:SetText("Tramo 8/8"); ns.navigationFrame.arrow:Show(); tick()
            assertHudDistances(directDistance(.549,.263))
            local active=false
            local marker=false
            local offer={action="prepare", text="Preparar mazmorra"}
            local resume={action="world", text="Volver a la guía"}
            ns.DungeonPlanner={
                IsDetouring=function() return active end,
                Heading=function() return "Minas de la Muerte","Preparación" end,
                Rows=function() return {active and resume or offer,{text="Habla con el tabernero en la posada"}} end,
                Waypoint=function()
                    if marker then return 1443,.52,.24,"Posada" end
                end,
                Hint=function() return "Haz la misión dentro de la mazmorra" end,
                Click=function(self, item)
                    assert(item==offer or item==resume)
                    active=item==offer; ns:RefreshUI()
                end,
            }
            local function contents(n)
                return env.UI.GetComponent("TaskGroupContainers").Get(n).contents.taskContainers
            end
            ns:RefreshUI(); tick()
            assert(getTaskIcon().row.text:find("Busca a Dalinda",1,true))
            local activity=contents(2)
            local prepare=activity[1].button
            assert(prepare:IsShown() and prepare:GetText()==offer.text)
            assert(not activity[2].button:IsShown() and not activity[2].icon.mouse)
            marker=true; tick()
            assertHudDistances(directDistance(.549,.263))
            prepare.scripts.OnClick(prepare, "LeftButton"); tick()
            assert(active and contents(2)[1].text.text:find("Busca a Dalinda",1,true))
            local title,subtitle=env.HeaderService.GetHeaderTitles()
            assert(title=="Minas de la Muerte" and subtitle=="Preparación")
            assert(env.HeaderService.GetStepText()=="Ruta · Juntos 12 · Tú 14")
            assertHudDistances(directDistance(.52,.24))
            marker=false; tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            assertNoFloatingHint()
            local leave=contents(1)[1].button
            leave.scripts.OnClick(leave, "LeftButton"); tick()
            assert(not active and getTaskIcon().row.text:find("Busca a Dalinda",1,true))
            assert(env.HeaderService.GetHeaderTitles()=="Desolace (31–34)")
            assertHudDistances(directDistance(.549,.263))
        """)
        lua.execute("""
            ns.DungeonPlanner=nil
            local zone=1443
            local unitWorld=2001
            function UnitPosition() return nil,nil,nil,unitWorld end
            function C_Map.GetBestMapForUnit() return zone end
            function C_Map.GetPlayerMapPosition() return CreateVector2D(.4,.5) end
            function C_Map.GetWorldPosFromMapPos(map,pos)
                local x,y=pos:GetXY()
                return map==1443 and 1 or 0,CreateVector2D(1000*x,1000*y)
            end
            local scope=RutaXPJourneyEnvironment()
            ns.navigationFrame:Hide(); ns.navigationFrame.arrow:Hide()
            tick(); tick()
            assert(RutaXPJourneyScreenArrow.container:IsShown())
            local x,y,_,world=scope.UnitPosition("player")
            assert(x==400 and y==500 and world==1)
            zone=1436; tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            assertNoFloatingHint()
            zone=1443; blocked=true; ns:GetArrowWaypoint()
            ns.navigationFrame.hint:SetText(""); tick(); tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            assertNoFloatingHint()
            assert(getTaskIcon().row.text=="Recalculando desde tu posición")
            bearing=true; ns:GetArrowWaypoint(); tick(); tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            assert(getTaskIcon().row.text=="Recalculando desde tu posición")
            bearing=false
            blocked=false; ns:GetArrowWaypoint(); tick()
            assertHudDistances("256 m")
            local previousFacing=GetPlayerFacing
            function issecretvalue(n) return n==-999 end
            function GetPlayerFacing() return -999 end
            tick(); assert(not RutaXPJourneyScreenArrow.container:IsShown())
            assertNoFloatingHint()
            GetPlayerFacing=previousFacing; tick(); assert(RutaXPJourneyScreenArrow.container:IsShown())
            local key="dungeon:pickup"
            local directQueries=0
            ns.DungeonPlanner={
                RouteKey=function() return key end, IsDetouring=function() return true end,
                Rows=function() return {} end, Heading=function() return "Preparación","Habla con el instructor" end,
                Hint=function() return "Habla con el instructor" end,
                Waypoint=function() directQueries=directQueries+1; return 1443,.8,.8,"Instructor" end,
            }
            sampledTurn={mapID=1443,x=.3,y=.2,activityDestination=true,activityKey=key,
                navigationBlocked=true,navigationHint="Sal de combate",navigationNotice="Esperando al camino"}
            ns:GetArrowWaypoint(); tick(); tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown() and directQueries==0)
            assertNoFloatingHint()
            assert(getTaskIcon().row.text=="Esperando al camino")
            sampledTurn.navigationBlocked=false; ns.navigationFrame.hint:SetText("Tramo 2/3")
            ns:GetArrowWaypoint(); tick(); tick()
            assert(RutaXPJourneyScreenArrow.container:IsShown() and directQueries==0)
            assertHudDistances("289 m")
            local hud=RutaXPJourneyScreenArrow
            local hides=0
            local hide=hud.container.Hide
            function hud.container:Hide() hides=hides+1; hide(self) end
            sampledTurn.walking=true
            sampledTurn.walkingWorld={continent=1,north=417,west=500}
            ns:GetArrowWaypoint(); tick(); tick()
            assertHudDistances("16 m")
            sampledTurn.walkingWorld={continent=1,north=447,west=500}
            ns:GetArrowWaypoint(); tick(); tick()
            assertHudDistances("43 m")
            assert(hides==0)

            -- A steering point may be 47 yards away while the next real turn
            -- is 65 yards down the road. Show the maneuver's path distance.
            ns.DungeonPlanner=nil
            sampledTurn.activityDestination=false
            sampledTurn.navigationNotice=nil
            sampledTurn.walkingDistance=350
            sampledTurn.walkingTurn,sampledTurn.walkingTurnDistance="right",65
            sampledTurn.walkingRouteKey="same objective"
            ns:GetArrowWaypoint(); tick(); tick()
            assertHudDistances("59 m / 320 m")
            sampledTurn.walkingTurnDistance=288
            ns.navigationFrame.hint:SetText("Ve al muelle")
            ns:GetArrowWaypoint(); tick(); tick()
            assertHudDistances("263 m / 320 m")
            assert(hides==0)
            local savedLocale=GetLocale
            GetLocale=function() return "enUS" end
            ns.navigationFrame.hint:SetText("")
            sampledTurn.walkingTurn="left"
            ns:GetArrowWaypoint(); tick(); tick()
            assertHudDistances("263 m / 320 m")
            sampledTurn.walkingTurnDistance=70
            ns:GetArrowWaypoint(); tick(); tick()
            assertHudDistances("64 m / 320 m")
            GetLocale=savedLocale
            sampledTurn.walkingTurn,sampledTurn.walkingTurnDistance="left",32
            ns.navigationFrame.hint:SetText("Ve al muelle")
            ns:GetArrowWaypoint(); tick(); tick()
            assertHudDistances("29 m / 320 m")
            sampledTurn.walkingTurn,sampledTurn.walkingTurnDistance=nil,nil
            ns.navigationFrame.hint:SetText("Tramo 3/12")
            ns:GetArrowWaypoint(); tick(); tick()
            assertHudDistances("320 m")
            assert(hides==0)
            sampledTurn.walkingSegmentDistance=100
            sampledTurn.walkingDistance=1600
            ns:GetArrowWaypoint(); tick(); tick()
            assertHudDistances("91 m / 1463 m")
            sampledTurn.walkingSegmentDistance=1600
            ns:GetArrowWaypoint(); tick(); tick()
            assertHudDistances("1463 m")
            sampledTurn.navigationBlocked=true; sampledTurn.navigationBearing=true
            sampledTurn.navigationBearingText="Rumbo orientativo"
            sampledTurn.walking=false
            ns:GetArrowWaypoint(); tick(); tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            assertNoFloatingHint()
        """)
