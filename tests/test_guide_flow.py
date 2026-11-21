"""Private-package integration: parse actual stock guides and display them in actual Journey."""
from pathlib import Path
import os
import re
import unittest
from zipfile import ZipFile

from lupa.lua51 import LuaRuntime

from test_guide_journey import MOCK, NATIVE, ROOT
from tools import suite_journey, suite_rested


ARCHIVE = Path(os.environ.get("RUTAXP_RESTED_ARCHIVE", ROOT / ".sources/suite" /
               f"RXPGuides-{suite_rested.COMMIT}.zip"))


CLIENT = r"""
local f=getmetatable(UIParent)
function f:UnregisterEvent(k) self.events[k]=nil end
function f:GetText() return self.text or "" end
function f:GetParent() return self.parent end
function f:SetParent(p) self.parent=p end
function f:LockHighlight() self.highlight=true end
function f:UnlockHighlight() self.highlight=false end
for _,k in ipairs({"SetAutoFocus","SetWordWrap","SetClipsChildren","StartMoving","StopMovingOrSizing"}) do
    f[k]=function() end
end
local frame=CreateFrame
function CreateFrame(kind,name,parent,template)
    local result=frame(kind,name,parent,template)
    if template=="BasicFrameTemplateWithInset" then result.TitleText=result:CreateFontString() end
    return result
end
local timers={}
C_Timer={After=function(_,cb) timers[#timers+1]=cb end}
function flush()
    local iterations=0
    while #timers>0 do iterations=iterations+1; assert(iterations<80); table.remove(timers,1)() end
    tick()
end
function hooksecurefunc(obj,key,cb)
    local previous=assert(obj[key])
    obj[key]=function(...) local result=previous(...); cb(...); return result end
end
ns={}; SlashCmdList={}; UISpecialFrames={}; C_DateAndTime={}
StaticPopupDialogs={}; C_GossipInfo={}
C_Spell={IsSpellDataCached=function() return true end, GetSpellTexture=function() return 134400 end}
QUEST_MONSTERS_KILLED="%s: %d/%d"; QUEST_ITEMS_NEEDED=QUEST_MONSTERS_KILLED
ACCEPT="Acepta"; TURN_IN_QUEST="Entrega"
local legacy="forever/alliance/dwarf-gnome/01-dun-morogh"
RutaXPCharDB={activeGuide=legacy,progress={[legacy]={cursor=2,routeRevision=4}}}
UnitFactionGroup=function() return "Alliance" end
UnitClass=function() return "Brujo","WARLOCK" end
GetBuildInfo=function() return nil,nil,nil,16001 end
UnitLevel=function() return 2 end
UnitSex=function() return 2 end
GetTime=function() return 1 end
GetItemInfo=function(id) return "Objeto "..tostring(id) end
function CreateVector2D(x,y) return {x=x,y=y,GetXY=function(v) return v.x,v.y end} end
C_Map.GetMapInfo=function(id) return {name="Dun Morogh",mapID=id,mapType=3} end
C_Map.GetAreaInfo=function(id) return tostring(id) end
C_Map.GetBestMapForUnit=function() return 1426 end
C_Map.GetPlayerMapPosition=function() return CreateVector2D(.28,.72) end
C_QuestLog={IsOnQuest=function(id) return id==179 end, IsQuestFlaggedCompleted=function() return false end,
    GetNumQuestLogEntries=function() return 1 end}
strupper,strlower,strmatch,strtrim,tinsert,tremove=string.upper,string.lower,string.match,
    function(s) return s:match("^%s*(.-)%s*$") end,table.insert,table.remove
table.wipe=function(t) for k in pairs(t) do t[k]=nil end return t end
function strsplit(sep,s) local a={}; for part in s:gmatch("[^"..sep.."]+") do a[#a+1]=part end return unpack(a) end
local dragon={}
function dragon:GetZoneCoordinatesFromWorld(x,y,map) return .5+x/100000,.5+y/100000 end
function dragon:GetWorldCoordinatesFromZone(x,y,map) return (x-.5)*100000,(y-.5)*100000,0 end
function LibStub(name) if name=="HereBeDragons-2.0" then return dragon end end
"""


NATIVE_CONTEXT = """
_,r=RutaXPModuleContext("RXPGuides")
local noop=function() end
r.player={name="Test",race="Gnome",class="WARLOCK",faction="Alliance",season=1}
r.game,r.gameVersion,r.locale="FOREVER",16001,{Get=function(s) return s end}
r.settings={profile={showEnabled=true},ReplaceColors=function(s) return s end}
r.functions,r.separators,r.mapConversion,r.db,r.guideCache={},{},{},{},{}
r.questConversion,r.stepLogic,r.dungeonOverride={},{},{}
r.IsFreshAccount=function() return false end
r.settings.profile.dungeons={}
r.NewModule=function() return {} end
r.ScheduleTask=noop
RXPGuides={}; r.RXPGuides=RXPGuides
RXPCData={guideDisabled={},guideMetaData={},guideProgress={}}; RXPData={}
r.comms={PrettyDebug=function(msg,...) error(select("#",...)>0 and string.format(msg,...) or msg) end}
local mapNames={["Dun Morogh"]=1426,["Loch Modan"]=1432,["Elwynn Forest"]=1429,["Ironforge"]=1455,
    ["Stormwind City"]=1453,["Redridge Mountains"]=1433,["Westfall"]=1436,["Wetlands"]=1437}
r.GetMapId=function(zone) return tonumber(zone) or mapNames[zone] end
r.GetMapInfo=function(zone,x,y,i) return r.GetMapId(zone),tonumber(x),tonumber(y),i end
r.RXPFrame=CreateFrame("Frame",nil,UIParent); r.RXPFrame.activeSteps={}
r.arrowFrame=CreateFrame("Frame",nil,UIParent)
r.emptyGuide={name="",group="",empty=true,steps={{hidewindow=true,text=""}}}
function r.ReplaceNpcIds(s) return s end
local messages={}
function r:RegisterMessage(key,cb) messages[key]=cb end
function r.UpdateGotoSteps() end
function r.UpdateMap() end
-- The client scheduler supplies the live steps and chooses a waypoint.
-- All elements, class filters, quest IDs, localized texts and coordinates
-- below are the real parser's output from the embedded official file.
function r.SetStep(n)
    local g=r.currentGuide
    if not g or not g.steps[n] then return end
    for _,s in ipairs(r.RXPFrame.activeSteps) do s.active=false end
    local step=g.steps[n]; step.index,step.active=n,true
    r.SaveGuideProgress(g,n); r.RXPFrame.activeSteps={step}; r.rutaXPWaypoint=nil
    for _,e in ipairs(step.elements or {}) do if e.arrow and e.zone then r.rutaXPWaypoint=e; break end end
    r.UpdateMap()
end
function r:LoadGuide(g)
    self.currentGuide=self.ProcessGuideTable(g)
    self.SetStep(self.GetGuideProgress(g))
    if messages.RXP_GUIDE_LOADED then messages.RXP_GUIDE_LOADED() end
end
"""


@unittest.skipUnless(ARCHIVE.is_file() and (NATIVE / "Journey.toc").is_file(),
                     "requires owner's Journey presentation and pinned official RestedXP package")
class InstalledGuideFlowTests(unittest.TestCase):
    def load_flow(self, character=""):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(MOCK.split("local task=")[0])
        lua.execute(CLIENT)
        g = lua.globals()
        g.bit = lua.table(band=lambda a,b: int(a) & int(b), bxor=lambda a,b: int(a) ^ int(b))
        def load_local(name):
            lua.execute((ROOT / "RutaXP" / (name + ".lua")).read_text(encoding="utf8"), "RutaXP", g.ns)
        for name in ("TalentCore", "Suite", "GuideEngine", "GuideLegacyAnchors", "GuideCarryover", "GuideResume",
                     "GuideJourney", "GuideLibrary"):
            load_local(name)
        lua.execute(NATIVE_CONTEXT)
        lua.execute(character)
        with ZipFile(ARCHIVE) as archive:
            prefix = next(p for p in archive.namelist() if p.endswith("/GuideLoader.lua")).rsplit("/",1)[0]
            # Run the upstream model/progress routines without building its legacy
            # Blizzard windows. Class filtering and guide inclusions remain real.
            def native_routines(name, pattern, extra=""):
                source = archive.read(f"{prefix}/{name}").decode("utf-8-sig").replace("\r\n", "\n")
                functions = re.findall("^(" + pattern + r"\([^\n]*\).*?^end)$", source, re.S | re.M)
                self.assertTrue(functions)
                lua.execute("local _,addon=...; local L=addon.locale.Get; local fmt=string.format\n" +
                            "\n".join(functions) + "\n" + extra, "RXPGuides", g.r, name=name)
            native_routines("RXPGuides.lua", r"function addon\.(?:stepLogic\.\w+|IsStepShown|GetGuideTable|GetGuideProgress|SaveGuideProgress)")
            native_routines("GuideWindow.lua", r"(?:function addon\.ProcessGuideTable|function addon:FetchGuide|local function IsGuideActive)",
                            "addon.IsGuideActive=IsGuideActive")
            for name in ("DB/forever/flightData.lua", "functions.lua", "GuideLoader.lua",
                         "lang/Guides-esES/forever/Alliance-1-14_DwarfGnome.lua"):
                source = archive.read(f"{prefix}/{name}").decode("utf-8-sig")
                lua.execute(suite_rested.transform_lua("RXPGuides", name, source), "RXPGuides", g.r, name=name)
        for filename, data in suite_journey.contents(NATIVE):
            if filename.endswith(".lua"):
                lua.execute(data, "RutaXP", g.ns, name=filename)
        return lua

    def test_spanish_gnome_migration_navigation_library_and_compass(self):
        lua = self.load_flow()
        lua.execute("""
            event("ADDON_LOADED","RutaXP"); event("PLAYER_LOGIN"); event("PLAYER_ENTERING_WORLD")
            flush(); assert(not ns.GuideEngine.Ready())
            r.addonLoaded=true; r.LoadEmbeddedGuides(); event("QUEST_LOG_UPDATE"); flush()
            local first,initial=ns.GuideEngine.Current()
            assert(first and first.displayname=="1-5 Valle de Crestanevada")
            assert(ns.GuideResume.Status()=="auto" and ns.char.guideLink.key==first.key)
            assert(initial>1 and ns.char.progress[ns.char.activeGuide].cursor==2)
            local ui=RutaXPJourneyEnvironment().UI
            local function row() return ui.GetComponent("TaskGroupContainers").Get(1).contents.taskContainers[1] end
            local function checkRows()
                assert(row().text.text==ns.GuideEngine.Tasks()[1].text)
                assert(row().icon.row.step==select(2,ns.GuideEngine.Current()))
            end
            checkRows()
            local next=ui.GetComponent("HeaderNextButton").frame
            next.scripts.OnClick(next); flush()
            assert(select(2,ns.GuideEngine.Current())==initial+1); checkRows()
            local sawPoint,sawClear=false,false
            for i=1,#first.steps do
                ns.GuideEngine.SetStep(i); flush()
                if ns.GuideEngine.Waypoint() then
                    sawPoint=true
                    assert(RutaXPJourneyScreenArrow.container:IsShown())
                elseif sawPoint then
                    sawClear=true
                    assert(not RutaXPJourneyScreenArrow.container:IsShown())
                    break
                end
            end
            assert(sawPoint and sawClear and r.rutaXPJourney)
            ui.GetComponent("HeaderSettingsButton").frame.scripts.OnClick()
            assert(RutaXPGuideLibrary:IsShown())
            RutaXPGuideLibrary.search:SetText("5-11 dun morogh")
            RutaXPGuideLibrary.search.scripts.OnTextChanged()
            local choice=RutaXPGuideLibrary.rows[1]
            assert(choice.guide and choice.guide.displayname=="5-11 Dun Morogh")
            choice.scripts.OnClick(choice); flush()
            assert(ns.GuideResume.Status()=="manual" and ns.GuideEngine.Current().key==choice.guide.key)
            assert(not RutaXPGuideLibrary:IsShown() and ns.GuideJourney:IsShown()); checkRows()
        """)

    def test_paladin_and_partner_in_ironforge_finish_their_independent_journals(self):
        lua = self.load_flow("""
            chapter="forever/alliance/06-ashenvale"
            RutaXPCharDB={activeGuide=chapter,progress={[chapter]={cursor=58,routeRevision=6}},
                duo={enabled=true,wait=false}}
            UnitLevel=function() return 30 end
            UnitClass=function() return "Paladín","PALADIN" end
            r.player.race,r.player.class="Dwarf","PALADIN"
            C_Map.GetBestMapForUnit=function() return 1455 end
            C_Map.GetMapInfo=function(id) return {mapID=id,name="Forjaz",mapType=3} end
            GetNumGroupMembers=function() return 2 end
            UnitIsConnected=function() return true end
            log={{questID=968,title="Los Poderes Subyacentes"},{questID=1072,title="Un viejo colega"}}
            -- Only the partner has 1274 and 343. A change to their journal
            -- must never select a different chapter or change the player's cursor.
            party={[968]=true,[1274]=true,[343]=true}; delivered={}
            C_QuestLog.GetNumQuestLogEntries=function() return #log,#log end
            C_QuestLog.GetInfo=function(n) return log[n] end
            C_QuestLog.GetQuestObjectives=function() return {} end
            C_QuestLog.IsUnitOnQuest=function(unit,id) assert(unit=="party1"); return party[id] or false end
            C_QuestLog.IsOnQuest=function(id)
                for _,q in ipairs(log) do if q.questID==id then return true end end
                return false
            end
            C_QuestLog.ReadyForTurnIn=C_QuestLog.IsOnQuest
            C_QuestLog.IsQuestFlaggedCompleted=function(id) return delivered[id] or false end
            C_QuestLog.GetNextWaypoint=function(id) if id==1072 then return 1455,.35,.47 end end
        """)
        lua.execute("""
            event("ADDON_LOADED","RutaXP"); event("PLAYER_LOGIN"); event("PLAYER_ENTERING_WORLD"); flush()
            r.addonLoaded=true; r.LoadEmbeddedGuides(); event("QUEST_LOG_UPDATE"); flush()
            local ui=RutaXPJourneyEnvironment().UI
            local function rows() return ui.GetComponent("TaskGroupContainers").Get(1).contents.taskContainers end
            local function expectJournal()
                assert(ns.GuideResume.Status()=="journal" and RutaXPJourneyEnvironment().HeaderService.GetHeaderTitles()=="Misiones en curso")
                assert(ns.char.progress[chapter].cursor==58 and not ns.char.duo.wait)
                assert(#ns.char.guideJournal.ids==2 and ns.char.guideJournal.ids[1]==1072 and ns.char.guideJournal.ids[2]==968)
            end
            expectJournal()
            assert(rows()[1].icon.row.questID==1072 and not rows()[1].text.text:find("ambos",1,true))
            assert(rows()[2].icon.row.questID==968 and rows()[2].text.text:find("Activa para ambos",1,true))
            assert(RutaXPJourneyScreenArrow.container:IsShown() and RutaXPJourneyScreenArrow.label.text=="Un viejo colega")
            ui.GetComponent("HeaderSettingsButton").frame.scripts.OnClick()
            assert(RutaXPGuideLibrary:IsShown() and RutaXPGuideLibrary.status.text:find("Misiones en curso",1,true))
            RutaXPGuideLibrary:Hide()
            local provisional=ns.GuideEngine.Catalog()[1]
            r:LoadGuide(provisional); r.SetStep(2); flush()
            expectJournal(); assert(not ns.GuideEngine.Current())
            party[968]=nil; event("GROUP_ROSTER_UPDATE"); flush()
            assert(not rows()[2].text.text:find("ambos",1,true))
            table.remove(log,2); delivered[1072]=true
            event("QUEST_TURNED_IN",1072); event("QUEST_LOG_UPDATE"); flush()
            expectJournal(); assert(rows()[1].icon.row.questID==968 and not RutaXPJourneyScreenArrow.container:IsShown())
            table.remove(log,1); delivered[968]=true
            event("QUEST_TURNED_IN",968); event("QUEST_LOG_UPDATE"); flush()
            local status,detail=ns.GuideResume.Status()
            assert(status=="unavailable" and detail:find("Forjaz",1,true) and detail:find("30",1,true))
            assert(rows()[1].text.text==detail and not ns.GuideEngine.Current())
            assert(ns.char.guideJournal.done and ns.char.progress[chapter].cursor==58)
            assert(party[1274] and party[343])
            ui.GetComponent("HeaderSettingsButton").frame.scripts.OnClick()
            assert(RutaXPGuideLibrary:IsShown() and RutaXPGuideLibrary.status.text==detail)
        """)
