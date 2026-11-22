"""Resume 0.7.36 character saves through the original quest engine and Journey UI."""
import unittest

from lupa.lua51 import LuaRuntime

from test_addon import UI_STUBS, WOW_STUBS
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
    def client(self, player, faction, chapter, cursor, level=30, map_id=37):
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
        for name in ("Core", "MapFrames", "Leveling", "QuestEngine", "GuideMigrations",
                     "Navigation", "WestfallTravelData", "AllianceTravel", "HordeTravel", "TravelConnections",
                     "TravelRouting", "TravelDetour", "GuideTravel", "TrackerLayout", "TrackerPreview", "UI",
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
            assert(g.id==chapter and g.faction==TEST.faction and state.cursor==cursor)
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
            assert(widgets[1].text:GetText():find(ns.trackerRows[1].goalTitle,1,true))
        """)
        return lua

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

    def test_horde_character_resumes_its_own_chapter_and_rendered_step(self):
        self.client("Horda", "Horde", "forever/horde/06-hillsbrad-foothills", 12)

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
            local later=visibleAction("later"); assert(later)
            later.scripts.OnClick(later,"LeftButton"); tick()
            assert(not planner:IsDetouring() and ns.char.dungeonTrips.deferred[offer.dungeon])
            assert(env.HeaderService.GetHeaderTitles():find(g.title,1,true))
            assert(ns:GetCurrent()==g and ns.char.progress[chapter].cursor==before)
        """)
