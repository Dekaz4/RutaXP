"""Exercise the Journey renderer with WoW frames and (when available) the owner's UI."""
import os
from pathlib import Path
import tempfile
import unittest

from lupa.lua51 import LuaRuntime
from tools import suite_journey

ROOT = Path(__file__).resolve().parents[1]
NATIVE = Path(os.environ.get("RUTAXP_JOURNEY", "E:/WOW/World of Warcraft/_forever_/Interface/AddOns/Journey"))


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
function frame:HookScript(k,fn) self:SetScript(k,fn) end
function frame:RegisterEvent(k) self.events[k]=true end
function frame:Show() self.shown=true end
function frame:Hide() self.shown=false end
function frame:IsShown() return self.shown~=false end
function frame:SetShown(b) self.shown=b end
function frame:SetText(t) self.text=t end
function frame:GetText() return self.text end
function frame:GetTexture() return self.texture end
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
function tick() for _,f in ipairs(all) do if f:IsShown() and f.scripts.OnUpdate then f.scripts.OnUpdate(f,.3) end end end
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
function clock() return 0 end
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
ns.GuideResume={Status=function() return status,statusText end}
function getTaskIcon()
    return RutaXPJourneyEnvironment().UI.GetComponent("TaskGroupContainers").Get(1).contents.taskContainers[1].icon
end
"""


@unittest.skipUnless((NATIVE / "Journey.toc").is_file(), "the owner's Journey copy is required")
class NativeJourneyTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(MOCK)
        g = self.lua.globals()
        self.lua.execute((ROOT / "RutaXP/GuideJourney.lua").read_text(encoding="utf8"), "RutaXP", g.ns)
        self.assertFalse(self.lua.eval("ns.GuideJourney:Available()"))
        for filename, data in suite_journey.contents(NATIVE):
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
            assert(RutaXPJourneyScreenArrow.label.text=="Villadorada")
            loseWaypoint(); tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
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
            assert(RutaXPJourneyScreenArrow.label.text=="La caída de Dun Modr")
            pin=1.2; tick(); assert(not RutaXPJourneyScreenArrow.container:IsShown())
            party="En tu diario"; event("GROUP_ROSTER_UPDATE"); tick()
            assert(row(1).text.text:find(party,1,true))
            count="2/3"; notified(); tick(); assert(row(2).text.text==count)
            ui.GetComponent("HeaderSettingsButton").frame.scripts.OnClick(); assert(opened)
            status="auto"; ns.GuideJourney:Refresh(); tick()
            assert(next:IsShown() and back:IsShown() and scope.HeaderService.GetHeaderTitles()=="Elwynn")
            assert(row(1).text.text=="Usa el objeto" and RutaXPJourneyScreenArrow.container:IsShown())
        """)


@unittest.skipUnless((NATIVE / "Journey.toc").is_file(), "the owner's Journey copy is required")
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
                f.arrow=CreateFrame(); f.hint=label("Tramo 8/8"); ns.navigationFrame=f
                ns.navigationUpdater=CreateFrame("Frame",nil,UIParent)
            end
            function hooksecurefunc(table, k, hook)
                local previous=table[k]
                table[k]=function(...) previous(...); hook(...) end
            end
        """)
        for name in ("GuideOriginal", "GuideJourney"):
            lua.execute((ROOT / f"RutaXP/{name}.lua").read_text(encoding="utf8"), "RutaXP", lua.globals().ns)
        for filename, data in suite_journey.contents(NATIVE):
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
            assert(RutaXPJourneyScreenArrow.label.text=="Tramo 8/8")
            for i=1,12 do tick() end; assert(samples==1)
            ns.GuideJourney:Hide(); tick()
            assert(not ns.char.tracker and not ns.GuideJourney:IsShown() and RutaXPJourneyScreenArrow.container:IsShown())
            ns.char.arrow=false; tick(); assert(not RutaXPJourneyScreenArrow.container:IsShown())
            ns.GuideJourney:Show(); tick()
            assert(ns.char.tracker and not ns.char.arrow and ns.GuideJourney:IsShown())
            ns.window:Show(); ns:RefreshUI(); tick(); assert(not ns.GuideJourney:IsShown())
            ns.window:Hide(); ns:RefreshUI(); tick(); assert(ns.GuideJourney:IsShown())
            ns.char.arrow=true
            waiting=true; ns:GetArrowWaypoint()
            ns.navigationFrame.arrow:Hide(); ns.navigationFrame.hint:SetText("Quédate en el barco")
            local newLabel=UIParent.CreateFontString
            UIParent.CreateFontString=function(self, ...)
                hintLabel=newLabel(self, ...); return hintLabel
            end
            tick()
            assert(hintLabel:IsShown() and hintLabel:GetText()=="Quédate en el barco")
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            waiting=false; ns:GetArrowWaypoint()
            ns.navigationFrame.hint:SetText("Tramo 8/8"); ns.navigationFrame.arrow:Show(); tick()
            assert(not hintLabel:IsShown() and RutaXPJourneyScreenArrow.container:IsShown())
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
            assert(RutaXPJourneyScreenArrow.label.text=="Tramo 8/8")
            prepare.scripts.OnClick(prepare, "LeftButton"); tick()
            assert(active and contents(2)[1].text.text:find("Busca a Dalinda",1,true))
            local title,subtitle=env.HeaderService.GetHeaderTitles()
            assert(title=="Minas de la Muerte" and subtitle=="Preparación")
            assert(env.HeaderService.GetStepText()=="Ruta · Juntos 12 · Tú 14")
            assert(RutaXPJourneyScreenArrow.label.text=="Posada" and not hintLabel:IsShown())
            marker=false; tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            assert(hintLabel:IsShown() and hintLabel:GetText()=="Haz la misión dentro de la mazmorra")
            local leave=contents(1)[1].button
            leave.scripts.OnClick(leave, "LeftButton"); tick()
            assert(not active and getTaskIcon().row.text:find("Busca a Dalinda",1,true))
            assert(env.HeaderService.GetHeaderTitles()=="Desolace (31–34)")
            assert(RutaXPJourneyScreenArrow.label.text=="Tramo 8/8")
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
            assert(not RutaXPJourneyScreenArrow.container:IsShown() and hintLabel:IsShown())
            assert(hintLabel:GetText()=="Destino en otro continente")
            zone=1443; blocked=true; ns:GetArrowWaypoint()
            ns.navigationFrame.hint:SetText(""); tick(); tick()
            assert(not RutaXPJourneyScreenArrow.container:IsShown())
            assert(hintLabel:GetText()=="Recalculando desde tu posición")
            assert(getTaskIcon().row.text=="Recalculando desde tu posición")
            bearing=true; ns:GetArrowWaypoint(); tick(); tick()
            assert(RutaXPJourneyScreenArrow.container:IsShown() and not hintLabel:IsShown())
            assert(RutaXPJourneyScreenArrow.label.text=="Rumbo orientativo · calculando camino")
            bearing=false
            blocked=false; ns:GetArrowWaypoint(); tick()
            assert(RutaXPJourneyScreenArrow.container:IsShown() and not hintLabel:IsShown())
            local previousFacing=GetPlayerFacing
            function issecretvalue(n) return n==-999 end
            function GetPlayerFacing() return -999 end
            tick(); assert(not RutaXPJourneyScreenArrow.container:IsShown())
            assert(hintLabel:GetText()=="Esperando la orientación del personaje")
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
            assert(hintLabel:GetText()=="Sal de combate" and getTaskIcon().row.text=="Esperando al camino")
            sampledTurn.navigationBlocked=false; ns.navigationFrame.hint:SetText("Tramo 2/3")
            ns:GetArrowWaypoint(); tick(); tick()
            assert(RutaXPJourneyScreenArrow.container:IsShown() and directQueries==0)
            assert(RutaXPJourneyScreenArrow.label.text=="Tramo 2/3")
        """)
