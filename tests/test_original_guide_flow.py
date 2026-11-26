"""Resume 0.7.36 character saves through the original quest engine and Journey UI."""
import unittest

from lupa.lua51 import LuaRuntime

from test_addon import UI_STUBS, WOW_STUBS
from test_access_navigation import WORLD_STUBS
from test_guide_journey import MOCK, NATIVE, ROOT
from tools import suite_journey


CLIENT = """
-- Supply the WoW frame APIs used by both trackers on the same frames.
local methods=getmetatable(UIParent)
for name,func in pairs(legacyFrameMethods) do
    if not methods[name] then methods[name]=func end
end
for name,func in pairs(legacyMap) do if not C_Map[name] then C_Map[name]=func end end
function methods:GetText() return self.text or "" end
function methods:SetTexture(id) self.texture=id end
function methods:SetShadowColor() end
function methods:SetResizable() end
function methods:SetResizeBounds() end
function UnitClass() return TEST.classToken,TEST.classToken,2 end
function UnitRace() return TEST.raceToken,TEST.raceToken,3 end
function UnitName() return TEST.player end
function GetTime() return 1 end
function GetRealZoneText() return "Prueba" end
function hooksecurefunc(t,k,after)
    local f=t[k]
    t[k]=function(...) local result={f(...)}; after(...); return unpack(result) end
end
"""


@unittest.skipUnless((NATIVE / "Journey.toc").is_file(), "requires the owner's original Journey UI")
class OriginalGuideFlowTests(unittest.TestCase):
    def client(self, player, faction, chapter, cursor, level=30, map_id=37, *, travel=False):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(WOW_STUBS + UI_STUBS)
        lua.execute("legacyFrameMethods=getmetatable(UIParent).__index; legacyMap=C_Map")
        lua.execute(MOCK)
        lua.execute(CLIENT)
        # The other mock suite has its own engine; this test boots with a new namespace.
        lua.execute("ns={}; TEST.player,TEST.faction,chapter,cursor,TEST.level,TEST.mapID=...",
                    player, faction, chapter, cursor, level, map_id)
        lua.execute("""
            TEST.classToken=TEST.faction=="Alliance" and "PALADIN" or "WARRIOR"
            TEST.raceToken=TEST.faction=="Alliance" and "Dwarf" or "Orc"
            RutaXPDB={}
            RutaXPCharDB={activeGuide=chapter,seen=true,auto=false,tracker=false,arrow=true,
                journeyDisplay={hidden=false},duo={enabled=true,wait=true},
                progress={[chapter]={cursor=cursor,placed=true,confirmed={["2:1"]=true},skipped={}}}}
            TEST.quests[1070]={title="Estar de guardia en Espolón",onQuest=true}
        """)
        if travel:
            lua.execute("ACCESS_NS=ns; localVector=CreateVector2D")
            lua.execute(WORLD_STUBS)
            lua.execute("""
                CreateVector2D=localVector
                function UnitOnTaxi() return TEST.onTaxi or false end
                function UnitIsDeadOrGhost() return false end
                function GetTime() return TEST.time or 1 end
                TEST.quests[1459]={onQuest=true}
                TEST.quests[5561]={onQuest=true}
                RutaXPCharDB.progress[chapter].routeRevision=3
            """)
        transport = ("FlightNavigation", "BoatNavigation", "DestinationTravel") if travel else ()
        for name in ("Core", "MapFrames", "Leveling", "QuestEngine", "GuideMigrations",
                     "ArrowStyles", "Navigation", "CorpseNavigation", "WestfallTravelData", "AllianceTravel", "HordeTravel", "TravelConnections",
                     "TravelRouting", "TravelDetour", "GuideTravel", *transport, "TrackerLayout", "TrackerPreview", "UI",
                     "Suite", "DungeonQuestData", "RestedQuestState", "QuestFocus", "DungeonPlanner",
                     "GuideRestore", "GuideOriginal", "GuideJourney"):
            lua.execute((ROOT / f"RutaXP/{name}.lua").read_text(encoding="utf-8-sig"), "RutaXP", lua.globals().ns,
                        name=f"@{name}.lua")
        for filename,data in suite_journey.contents(NATIVE):
            if filename.endswith(".lua"):
                lua.execute(data, "RutaXP", lua.globals().ns)
        lua.execute('event("ADDON_LOADED","RutaXP"); event("PLAYER_LOGIN"); tick()')
        lua.execute("""
            local g,s,state=ns:GetCurrent()
            assert(g.id==chapter and g.faction==TEST.faction and state.cursor==cursor,
                tostring(g.id).." at step "..tostring(state.cursor).." (expected "..tostring(cursor)..")")
            assert(ns.char==RutaXPCharDB and state.confirmed["2:1"] and ns.char.duo.wait)
            assert(#ns.order==57 and ns.char.tracker and ns.GuideJourney:IsShown())
            assert(not ns.GetEmbeddedModule("RXPGuides") and not ns.GuideEngine and not RXPGuides)
            for _,guide in ipairs(ns:GetVisibleGuides("",false)) do
                assert(guide.faction==TEST.faction or guide.faction=="Both")
            end
            local env=RutaXPJourneyEnvironment()
            local title,place=env.HeaderService.GetHeaderTitles()
            assert(title:find(g.title,1,true) and place==s.title)
            assert(env.HeaderService.GetStepText()==("Paso %d/%d"):format(cursor,#g.steps))
            local widgets=env.UI.GetComponent("TaskGroupContainers").Get(1).contents.taskContainers
            local visible=widgets[1].text:GetText():gsub("|c%x%x%x%x%x%x%x%x",""):gsub("|r","")
            assert(visible:find(ns.trackerRows[1].goalTitle,1,true),visible)
        """)
        return lua

    def test_journey_rows_keep_live_hunt_targets_counts_and_future_quest_actions(self):
        lua = self.client("Pícara", "Alliance", "forever/alliance/30-40/04-stranglethorn-vale", 13,
                          level=36, map_id=1434)
        lua.execute("""
            ns.char.trackerSize={width=380,height=600}
            TEST.quests[191]={onQuest=true,complete=true,title="Domina la pantera"}
            TEST.quests[194]={onQuest=true,title="Título del cliente para el raptor",objectives={
                {text="Raptor de Tuercespina: 7/10",numFulfilled=7,numRequired=10,finished=false}}}
            TEST.quests[187]={onQuest=true,title="Domina el tigre",objectives={
                {text="Tigre de Tuercespina mayor: 0/10",numFulfilled=0,numRequired=10,finished=false}}}
            ns:RefreshUI()
            local function snapshot()
                local old=C_QuestLog.GetQuestObjectives
                C_QuestLog.GetQuestObjectives=function() error("renderer queried the journal twice") end
                local rows={}
                for _,r in ipairs(ns.OriginalGuidePresentation.Tasks()) do
                    if r.questID then rows[r.questID..":"..r.action..":"..tostring(r.preview)]=r end
                end
                C_QuestLog.GetQuestObjectives=old
                return rows
            end
            local rows=snapshot()
            local r,t=rows["194:kill:false"],rows["187:kill:false"]
            assert(r and r.isCurrent and r.status=="active" and r.questTitle==TEST.quests[194].title)
            assert(r.targetName=="Raptor de Tuercespina" and r.objectives[1].have==7 and r.objectives[1].total==10)
            assert(t and not t.isCurrent and t.targetName=="Tigre de Tuercespina mayor" and t.objectives[1].have==0)
            local nextRaptor=rows["195:accept:true"]
            assert(nextRaptor and nextRaptor.npcName=="Hemet Decautela" and nextRaptor.stepIndex==14)
            assert(not nextRaptor.frame and not nextRaptor.isCurrent and nextRaptor.status=="upcoming")
            TEST.quests[194].objectives[1].numFulfilled=8
            TEST.quests[194].objectives[1].text="Raptor de Tuercespina: 8/10"
            ns:RefreshUI()
            assert(snapshot()["194:kill:false"].objectives[1].have==8)
            assert(ns.char.progress[chapter].cursor==13)
        """)

    def test_alliance_paladins_two_steps_apart_resume_independent_saves(self):
        chapter = "forever/alliance/06-ashenvale"
        player = self.client("Paladín", "Alliance", chapter, 27)
        friend = self.client("Compañero", "Alliance", chapter, 29)
        player.execute("""
            assert(ns:IsQuestActive(1070))
            TEST.quests[1070].onQuest=false; TEST.quests[1070].delivered=true
            event("QUEST_TURNED_IN",1070); tick()
            assert(ns:IsQuestDelivered(1070))
            assert(ns.char.progress[chapter].cursor==27)
        """)
        friend.execute("""
            assert(ns:IsQuestActive(1070) and not ns:IsQuestDelivered(1070))
            assert(ns.char.progress[chapter].cursor==29 and ns.char.progress[chapter].confirmed["2:1"])
            assert(RutaXPJourneyEnvironment().HeaderService.GetHeaderTitles():find(ns.guides[chapter].title,1,true))
        """)

    def test_journal_tracking_and_kills_keep_current_panther_hunt_until_guide_turnin(self):
        lua = self.client("Cazadora", "Alliance", "forever/alliance/30-40/04-stranglethorn-vale", 5,
                          level=34, map_id=1434, travel=True)
        lua.execute("""
            local env=RutaXPJourneyEnvironment()
            local function hunt(name,creature,n)
                return {title=name,onQuest=true,objectives={{text=creature..": "..n.."/10",
                    numFulfilled=n,numRequired=10,finished=n==10}},complete=n==10}
            end
            TEST.quests[185]={delivered=true}
            TEST.quests[190]=hunt("Domina la pantera","Pantera joven",4)
            TEST.quests[186]=hunt("Domina el tigre","Tigre de Tuercespina",0)
            TEST.quests[194]=hunt("Domina el raptor","Raptor de Tuercespina",6)
            TEST.entries={{questID=190},{questID=186},{questID=194}}
            local tracked=0
            C_SuperTrack.GetSuperTrackedQuestID=function() return tracked end
            local function update(e,...)
                TEST.time=(TEST.time or 1)+1
                event(e,...); tick(); tick()
            end
            local function assertGuide(step,id,kind)
                local guide,current,state=ns:GetCurrent()
                assert(state.cursor==step,"Unexpected guide step "..state.cursor)
                local heading,place=env.HeaderService.GetHeaderTitles()
                assert(heading:find(guide.title,1,true) and place==current.title,heading.." / "..tostring(place))
                assert(not ns.DungeonPlanner:IsDetouring())
                for _,group in ipairs(env.GuideNavigationService.GetStep()) do
                    for _,task in ipairs(group) do
                        assert(task.row.text~="Volver al paso de RutaXP" and
                            not (task.row.activity and task.row.activity.action=="world"))
                    end
                end
                local goal=ns:GetActiveGoal()
                assert(goal and goal.quest==id and goal.t==kind,tostring(goal and goal.quest))
                local expected=ns:GetGoalWaypoint(goal)
                local map,x,y=ns.OriginalGuidePresentation.Waypoint()
                assert(map==expected.mapID and math.abs(x-expected.x)<.0001 and math.abs(y-expected.y)<.0001,
                    "The HUD sample must still be the chapter's current quest")
                local meters=env.FormatJourneyDistance(ns:GetWaypointVector(expected))
                local hud=RutaXPJourneyScreenArrow
                assert(hud.container:IsShown() and hud.distLabel:GetText()==meters)
            end
            ns.char.auto=true
            update("QUEST_LOG_UPDATE")
            assertGuide(5,190,"kill")
            tracked=186
            update("SUPER_TRACKING_CHANGED")
            assertGuide(5,190,"kill")
            TEST.quests[194]=hunt("Domina el raptor","Raptor de Tuercespina",7)
            update("QUEST_WATCH_UPDATE",194)
            update("QUEST_LOG_UPDATE")
            assertGuide(5,190,"kill")

            UnitIsGhost=function() return TEST.ghost end
            UnitIsDeadOrGhost=function() return TEST.dead or TEST.ghost or false end
            C_DeathInfo={GetCorpseMapPosition=function() return CreateVector2D(.36,.12) end}
            TEST.dead=true; update("PLAYER_DEAD")
            TEST.ghost=true; update("PLAYER_ALIVE")
            local hud=RutaXPJourneyScreenArrow
            assert(hud.container:IsShown() and (hud.label:GetText() or "")=="")
            assert(hud.distLabel:GetText():match("^%d+ m$"))
            assert(ns:GetArrowWaypoint().source=="corpse")
            TEST.ghost=false; TEST.dead=false; update("PLAYER_UNGHOST")
            assertGuide(5,190,"kill")

            TEST.quests[190]=hunt("Domina la pantera","Pantera joven",10)
            update("QUEST_LOG_UPDATE")
            assertGuide(6,190,"turnin")
            TEST.quests[190].onQuest=false; TEST.quests[190].delivered=true
            update("QUEST_TURNED_IN",190)
            assertGuide(6,191,"accept")
            TEST.quests[191]=hunt("Domina la pantera","Pantera",0)
            update("QUEST_ACCEPTED",191); update("QUEST_LOG_UPDATE")
            assertGuide(7,186,"kill")
        """)

    def test_horde_character_resumes_its_own_chapter_and_rendered_step(self):
        self.client("Horda", "Horde", "forever/horde/06-hillsbrad-foothills", 12)

    def test_guide_crossing_from_menethil_via_southshore_to_thundris_in_the_journey_hud(self):
        lua = self.client("Viajera", "Alliance", "forever/alliance/30-40/02-desolace", 2,
                          level=33, map_id=1437, travel=True)
        lua.execute("""
            local journalID=98209
            TEST.quests[journalID]={title="Flor de los cielos",onQuest=true,complete=true}
            TEST.entries={{questID=journalID}}
            local function move(map,x,y)
                TEST.mapID,TEST.x,TEST.y=map,x,y
                TEST.time=(TEST.time or 1)+15
                event("ZONE_CHANGED_NEW_AREA"); event("QUEST_LOG_UPDATE")
                for i=1,4 do tick() end
            end
            local function panelText()
                local env=RutaXPJourneyEnvironment()
                local lines={env.HeaderService.GetHeaderTitles()}
                for _,group in ipairs(env.GuideNavigationService.GetStep()) do
                    for _,task in ipairs(group) do lines[#lines+1]=task.row.text end
                end
                return table.concat(lines," ")
            end
            move(1437,.093,.578)
            assert(not ns.DungeonPlanner:IsDetouring() and panelText():find("Auberdine",1,true),panelText())
            local dock=RutaXPJourneyScreenArrow
            assert(dock and dock.container:IsShown(),"The native Journey HUD must point at the departure dock")
            local dockMap,dockX,dockY=ns.OriginalGuidePresentation.Waypoint()
            assert(dockMap==1437 and math.abs(dockX-.0449)<.002 and math.abs(dockY-.5666)<.002,
                "The compass selected the wrong Menethil pier")
            move(1437,.0449,.5666)
            move(1424,.5067,.7044)
            local stop=panelText():lower()
            assert(stop:find("mismo barco",1,true) and stop:find("costasur",1,true)
                and stop:find("auberdine",1,true),stop)
            assert(not dock.container:IsShown(),"The waypoint must stay suspended at the intermediate port")
            move(1439,.3234,.4413)
            move(1439,.3704,.4413)
            local map,x,y=ns.OriginalGuidePresentation.Waypoint()
            assert(map==1439 and math.abs(x-.374)<.01 and math.abs(y-.4013)<.01,
                "After docking the compass must return to Thundris")
            assert(dock.container:IsShown() and panelText():find("Flor de los cielos",1,true),panelText())
            assert(ns.char.progress[chapter].cursor==2,"The boat journey changed the saved chapter")
        """)

    def test_deadmines_prepare_and_return_from_journey_preserve_world_guide(self):
        lua = self.client("Paladín", "Alliance", "forever/alliance/02-westfall", 4, level=19, map_id=1436)
        lua.execute("""
            local planner,env=ns.DungeonPlanner,RutaXPJourneyEnvironment()
            local groups=env.UI.GetComponent("TaskGroupContainers")
            local function visibleAction(key)
                for i,group in ipairs(env.GuideNavigationService.GetStep()) do
                    local widgets=groups.Get(i).contents.taskContainers
                    for j,task in ipairs(group) do
                        local row=task.row
                        if row.activity and row.activity.action==key then
                            local widget=widgets[j]
                            local button=widget.button:IsShown() and widget.button or widget.icon
                            return button, row.activity
                        end
                    end
                end
            end
            local g,s,state=ns:GetCurrent()
            local before=state.cursor
            assert(not planner:IsDetouring())
            local button,offer=visibleAction("prepare")
            assert(button and offer.dungeon=="The Deadmines")
            button.scripts.OnClick(button,"LeftButton"); tick()
            assert(planner:IsDetouring() and ns.char.dungeonTrips.selected==offer.dungeon)
            assert(env.HeaderService.GetHeaderTitles()==ns.DungeonQuestData.dungeons[offer.dungeon].name)
            local tasks=env.GuideNavigationService.GetStep()
            assert(tasks[1][1].row.activity and not tasks[2][1].row.activity)
            assert(tasks[2][1].row.text:find(ns.trackerRows[1].goalTitle,1,true))
            TEST.quests[36]={onQuest=true,title="Estofado de los Páramos de Poniente"}
            TEST.entries={{questID=36}}
            C_SuperTrack.GetSuperTrackedQuestID=function() return 36 end
            event("SUPER_TRACKING_CHANGED"); event("QUEST_LOG_UPDATE"); tick()
            assert(planner:IsDetouring() and ns.char.dungeonTrips.selected==offer.dungeon)
            assert(env.HeaderService.GetHeaderTitles()==ns.DungeonQuestData.dungeons[offer.dungeon].name)
            local later=visibleAction("later"); assert(later)
            later.scripts.OnClick(later,"LeftButton"); tick()
            assert(not planner:IsDetouring() and ns.char.dungeonTrips.deferred[offer.dungeon])
            assert(env.HeaderService.GetHeaderTitles():find(g.title,1,true))
            assert(ns:GetCurrent()==g and ns.char.progress[chapter].cursor==before)
        """)
