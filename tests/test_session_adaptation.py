"""Local session observations and explained recommendations in real Lua 5.1.

No game client, external service, quest automation or persistent user files are
used; only WoW's host API is simulated.
"""
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]

STUBS = r'''
TEST={now=0,server=1000,level=10,xp=900,maximum=1000,afk=false,taxi=false,
    dead=false,map=1429,continent=0,wx=0,wy=0,race="Human",class="WARRIOR",faction="Alliance",quests={},frames=0}
function GetTime() return TEST.now end
function GetServerTime() return TEST.server end
function UnitLevel() return TEST.level end
function UnitXP() return TEST.xp end
function UnitXPMax() return TEST.maximum end
function UnitIsAFK() return TEST.afk end
function UnitOnTaxi() return TEST.taxi end
function UnitIsDeadOrGhost() return TEST.dead end
function UnitRace() return TEST.race,TEST.race end
function UnitClass() return TEST.class,TEST.class end
function UnitFactionGroup() return TEST.faction end
function UnitName() return "PRIVATE_CHARACTER_NAME" end
function SendAddonMessage() error("No external communication is permitted") end
function CreateVector2D(x,y) return {GetXY=function() return x,y end} end
function CreateFrame()
 TEST.frames=TEST.frames+1
 local f={events={},scripts={}}
 function f:RegisterEvent(e) self.events[e]=true end
 function f:SetScript(e,fn) self.scripts[e]=fn end
 return f
end
C_Map={}
function C_Map.GetBestMapForUnit() return TEST.map end
function C_Map.GetPlayerMapPosition() return CreateVector2D(.5,.5) end
function C_Map.GetWorldPosFromMapPos() return TEST.continent,CreateVector2D(TEST.wx,TEST.wy) end
C_QuestLog={}
function C_QuestLog.IsOnQuest(id) return TEST.quests[id] and TEST.quests[id].active or false end
function C_QuestLog.IsQuestFlaggedCompleted(id) return TEST.quests[id] and TEST.quests[id].done or false end
function C_QuestLog.GetQuestObjectives(id) return TEST.quests[id] and TEST.quests[id].objectives end
function MakeNS(saved)
 local n={char=saved or {activeGuide="current",progress={current={cursor=1,confirmed={}}}},guides={},order={},turnedIn={}}
 n.guides.current={id="current",title="Ruta actual",minLevel=10,maxLevel=20,faction="Alliance",zone=1429,
   steps={{title="Paso actual",goals={{t="kill",quest=101,npc=1,count=5}}},{title="Siguiente",goals={{t="turnin",quest=101}}}}}
 n.order={"current"}
 function n:Sync() error("Session/Adaptation must not sync progress") end
 function n:SelectGuide() error("Session/Adaptation must not call SelectGuide") end
 function n:GetCurrent() error("Session/Adaptation must read progress without creating state") end
 return n
end
function Advance(n,seconds,dx)
 for i=1,seconds do TEST.now=TEST.now+1; TEST.server=TEST.server+1; TEST.wx=TEST.wx+(dx or 0); n.Session:Tick(1) end
end
function Fingerprint(t)
 if type(t)~="table" then return tostring(t) end
 local keys={}; for k in pairs(t) do keys[#keys+1]=k end
 table.sort(keys,function(a,b) return tostring(a)<tostring(b) end)
 local out={}; for _,k in ipairs(keys) do out[#out+1]=tostring(k).."="..Fingerprint(t[k]) end
 return "{"..table.concat(out,";").."}"
end
function AddGuide(n,id,low,high,zone,race,quest)
 n.guides[id]={id=id,title=id,minLevel=low,maxLevel=high,zone=zone,faction="Alliance",races=race,
  steps={{title="Inicio",goals={{t="accept",quest=quest or 202}}}}}
 n.order[#n.order+1]=id
end
'''


class SessionAdaptationTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(STUBS)
        self.ns = self.lua.globals().MakeNS()
        self.load("Session.lua", self.ns)
        self.load("Adaptation.lua", self.ns)
        self.lua.globals().NS = self.ns

    def load(self, name, namespace):
        chunk = self.lua.execute("return function(...)\n" + (ROOT / "RutaXP" / name).read_text(encoding="utf-8") + "\nend")
        chunk("RutaXP", namespace)

    def run_lua(self, code):
        self.lua.execute(code)

    def test_active_afk_pause_xp_level_up_deaths_and_event_registration(self):
        self.run_lua('''
        assert(NS.Session:Initialize()); NS.Session:Initialize(); assert(TEST.frames==1)
        Advance(NS,10,7)
        NS.Session:SetPaused(true); Advance(NS,5)
        TEST.xp=950; NS.Session:OnEvent("PLAYER_XP_UPDATE","player")
        NS.Session:SetPaused(false); Advance(NS,10,7)
        TEST.level=11; TEST.xp=50; TEST.maximum=1100
        NS.Session:OnEvent("PLAYER_LEVEL_UP",11); NS.Session:OnEvent("PLAYER_XP_UPDATE","player")
        TEST.afk=true; NS.Session:OnEvent("PLAYER_FLAGS_CHANGED","player"); Advance(NS,8)
        TEST.afk=false; NS.Session:OnEvent("PLAYER_FLAGS_CHANGED","player")
        TEST.dead=true; NS.Session:OnEvent("PLAYER_DEAD"); NS.Session:OnEvent("PLAYER_DEAD")
        TEST.dead=false; NS.Session:OnEvent("PLAYER_UNGHOST")
        TEST.dead=true; NS.Session:OnEvent("PLAYER_DEAD")
        local s=NS.Session:GetSummary()
        assert(s.activeSeconds==20 and s.pausedSeconds==5 and s.afkSeconds==8)
        assert(s.xp==150 and s.activeXP==100 and s.xpPerHour==18000)
        assert(s.deaths==2 and s.byGuide.current.xp==150)
        assert(not NS.Session:GetReport():find("PRIVATE_CHARACTER_NAME",1,true))
        ''')

    def test_distance_uses_world_points_and_discards_taxi_cast_ports_and_continent_changes(self):
        self.run_lua('''
        NS.Session:Initialize(); Advance(NS,3,7)
        assert(NS.Session:GetSummary().distanceYards==14)
        TEST.wx=TEST.wx+1000; NS.Session:OnEvent("UNIT_SPELLCAST_SUCCEEDED","player")
        Advance(NS,3,0); assert(NS.Session:GetSummary().distanceYards==14)
        TEST.taxi=true; Advance(NS,5,150)
        TEST.taxi=false; Advance(NS,3,0)
        assert(NS.Session:GetSummary().distanceYards==14)
        TEST.continent=1; TEST.wx=50000; Advance(NS,1)
        TEST.wx=TEST.wx+1000; Advance(NS,1)
        assert(NS.Session:GetSummary().distanceYards==14)
        Advance(NS,2,7); assert(NS.Session:GetSummary().distanceYards==28)
        assert(NS.Session:GetSummary().taxiSeconds==5)
        ''')

    def test_reload_excludes_offline_time_and_retains_known_quest_active_timer(self):
        self.run_lua('''NS.Session:Initialize(); NS.Session:OnEvent("QUEST_ACCEPTED",1,101); Advance(NS,20)
        SAVED=NS.char; TEST.now=0; TEST.server=TEST.server+86400''')
        other = self.lua.globals().MakeNS(self.lua.globals().SAVED)
        self.load("Session.lua", other)
        self.lua.globals().RELOADED = other
        self.run_lua('''
        RELOADED.Session:Initialize(); Advance(RELOADED,10)
        RELOADED.Session:OnEvent("QUEST_REMOVED",101)
        RELOADED.Session:OnEvent("QUEST_TURNED_IN",101)
        local s=RELOADED.Session:GetSummary()
        assert(s.activeSeconds==10 and s.historyCount==1)
        assert(RELOADED.char.sessions.history[1].totals.activeSeconds==20)
        assert(s.questTimings[1].known and s.questTimings[1].activeSeconds==30)
        RELOADED.Session:OnEvent("QUEST_TURNED_IN",999)
        assert(not RELOADED.Session:GetSummary().questTimings[2].known)
        ''')

    def test_observations_are_bounded_do_not_mutate_progress_and_detect_only_sufficient_samples(self):
        self.run_lua('''
        NS.Session:Initialize(); local before=Fingerprint(NS.char.progress)
        Advance(NS,599); assert(#NS.Session:GetSummary().flags==0)
        Advance(NS,1); assert(NS.Session:GetSummary().flags[1].code=="stuck")
        TEST.quests[101]={objectives={{numFulfilled=1,finished=false}}}
        NS.Session:OnEvent("QUEST_WATCH_UPDATE",101)
        assert(#NS.Session:GetSummary().flags==0)
        assert(Fingerprint(NS.char.progress)==before)
        for i=1,130 do NS.Session:OnEvent("QUEST_ACCEPTED",i,i) end
        local count=0; for _ in pairs(NS.char.sessions.questStarts) do count=count+1 end
        assert(count<=100)
        for i=1,30 do NS.Session:Reset(false) end
        assert(#NS.char.sessions.history==20)
        NS.Session:Reset(true); assert(#NS.char.sessions.history==0)
        ''')

    def test_long_gaps_are_unobserved_and_low_xp_travel_is_explained(self):
        self.run_lua('''
        NS.Session:Initialize(); TEST.now=100; TEST.xp=950; NS.Session:Tick(100)
        assert(NS.Session:GetSummary().activeSeconds==0 and NS.Session:GetSummary().unobservedSeconds==100)
        assert(NS.Session:GetSummary().unobservedXP==50 and NS.Session:GetSummary().activeXP==0)
        Advance(NS,900,7)
        local found=false; for _,f in ipairs(NS.Session:GetSummary().flags) do if f.code=="travel_low_xp" then found=true end end
        assert(found)
        assert(NS.Session:GetReport():find("estimad"))
        ''')

    def test_two_level_gap_is_uncertain_and_does_not_invent_intermediate_xp(self):
        self.run_lua('''
        NS.Session:Initialize(); Advance(NS,5)
        TEST.level=12; TEST.xp=100; TEST.maximum=1200
        NS.Session:OnEvent("PLAYER_LEVEL_UP",12)
        local s=NS.Session:GetSummary()
        assert(s.xp==0 and s.xpUncertain==1)
        TEST.xp=150; NS.Session:OnEvent("PLAYER_XP_UPDATE","player")
        assert(NS.Session:GetSummary().xp==50)
        TEST.maximum=0; NS.Session:OnEvent("PLAYER_XP_UPDATE","player")
        Advance(NS,900,7)
        for _,f in ipairs(NS.Session:GetSummary().flags) do assert(f.code~="travel_low_xp") end
        ''')

    def test_corrupt_saved_session_is_sanitized_without_touching_route_progress(self):
        self.run_lua('''
        local before=Fingerprint(NS.char.progress)
        NS.char.sessions={activeClock="broken",history="bad",paused="not a boolean",
          current={totals={activeSeconds=-50,xp="broken"},steps=false,quests={false},byGuide="bad"},
          questStarts={bad=false,[12]={clock="broken"},[13]={clock=100000}}}
        assert(NS.Session:Initialize()); Advance(NS,2)
        local s=NS.Session:GetSummary()
        assert(s.activeSeconds==2 and s.recovered and s.xp==0)
        assert(Fingerprint(NS.char.progress)==before and next(NS.char.sessions.questStarts)==nil)
        assert(NS.Session:GetReport():find("inválidas",1,true))
        ''')

    def test_per_guide_step_and_quest_telemetry_remains_bounded(self):
        self.run_lua('''
        NS.Session:Initialize()
        for i=1,400 do
          local id="guide"..i
          NS.guides[id]={id=id,title=id,steps={{title="one",goals={}}}}
          NS.char.activeGuide=id; NS.char.progress[id]={cursor=1}
          Advance(NS,1)
          NS.Session:OnEvent("QUEST_TURNED_IN",1000+i)
        end
        local s=NS.Session:GetSummary(); local guides,steps=0,0
        for _ in pairs(s.byGuide) do guides=guides+1 end
        for _ in pairs(s.stepTimings) do steps=steps+1 end
        assert(guides<=33 and steps<=257 and #s.questTimings==100)
        assert(s.quests==400)
        ''')

    def test_manual_pause_survives_reload_without_counting_offline_or_afk_as_active(self):
        self.run_lua('''NS.Session:Initialize(); Advance(NS,4); NS.Session:SetPaused(true); Advance(NS,3)
        SAVED=NS.char; TEST.now=0; TEST.server=TEST.server+86400''')
        other = self.lua.globals().MakeNS(self.lua.globals().SAVED)
        self.load("Session.lua", other)
        self.lua.globals().RELOADED = other
        self.run_lua('''
        RELOADED.Session:Initialize(); Advance(RELOADED,6)
        local s=RELOADED.Session:GetSummary(); assert(s.paused and s.pausedSeconds==6 and s.activeSeconds==0)
        RELOADED.Session:SetPaused(false); TEST.afk=true
        RELOADED.Session:OnEvent("PLAYER_FLAGS_CHANGED","player"); Advance(RELOADED,4)
        assert(RELOADED.Session:GetSummary().afkSeconds==4)
        assert(RELOADED.Session:GetSummary().activeSeconds==0)
        ''')

    def test_suggestions_use_own_level_until_duo_presence_is_confirmed(self):
        self.run_lua('''
        TEST.level=20; TEST.map=2000
        AddGuide(NS,"adult",18,25,2000,nil,202)
        AddGuide(NS,"child",1,5,1000,nil,203)
        NS.Duo={GetContext=function() return {enabled=true,known=false,partnerLevel=1,online=false,sameParty=false} end}
        local items=NS.Adaptation:GetSuggestions(); assert(#items<=5 and items[1].title=="Compañero sin confirmar")
        local adult=false; for _,s in ipairs(items) do if s.guideID=="adult" then adult=true end; assert(s.guideID~="child") end
        assert(adult and NS.char.activeGuide=="current")
        ''')

    def test_live_duo_lower_level_and_different_races_never_remove_class_or_group_requirements(self):
        self.run_lua('''
        TEST.level=20
        NS.guides.current.steps[1].goals={{t="kill",quest=101,only={classes={"WARRIOR"}},group={kind="group",size=5}}}
        AddGuide(NS,"meet",10,15,1429,nil,202)
        NS.Duo={GetContext=function() return {enabled=true,known=true,online=true,sameParty=true,partnerLevel=10,partnerRace="Dwarf",partnerClass="PRIEST"} end}
        local before=Fingerprint(NS.char.progress)
        local items=NS.Adaptation:GetSuggestions(); local seen={}
        for _,s in ipairs(items) do seen[s.title]=true; if s.guideID then assert(s.guideID=="meet") end end
        assert(#items<=5 and seen["El menor nivel marca el ritmo"] and seen["Inicios distintos: acordad un encuentro"])
        assert(seen["Conserva las misiones de tu clase"] and seen["Revisad el objetivo de grupo"])
        assert(Fingerprint(NS.char.progress)==before and NS.guides.current.steps[1].goals[1].group.size==5)
        ''')

    def test_explicit_choice_preserves_bookmark_and_all_progress_then_rejects_stale_duo_level(self):
        self.run_lua('''
        TEST.map=2000; AddGuide(NS,"target",10,20,2000,nil,202)
        NS.char.progress.current.cursor=2; NS.char.progress.current.review=true
        local before=Fingerprint(NS.char.progress)
        local items=NS.Adaptation:GetSuggestions(); local chosen
        for i,s in ipairs(items) do if s.guideID=="target" then chosen=i end end
        assert(chosen and NS.char.activeGuide=="current")
        local ok,id=NS.Adaptation:ApplySuggestion(chosen)
        assert(ok and id=="target" and NS.char.activeGuide=="target")
        assert(Fingerprint(NS.char.progress)==before and NS.char.progress.target==nil)
        assert(NS.char.adaptation.bookmarks[1].guideID=="current" and NS.char.adaptation.bookmarks[1].cursor==2)
        TEST.level=20; AddGuide(NS,"high",18,25,3000,nil,203); TEST.map=3000
        items=NS.Adaptation:GetSuggestions(); chosen=nil
        for i,s in ipairs(items) do if s.guideID=="high" then chosen=i end end
        assert(chosen)
        NS.Duo={GetContext=function() return {enabled=true,known=true,online=true,sameParty=true,partnerLevel=2} end}
        assert(not NS.Adaptation:ApplySuggestion(chosen))
        assert(NS.char.activeGuide=="target" and Fingerprint(NS.char.progress)==before)
        ''')

    def test_return_to_previous_restores_only_the_selected_guide(self):
        self.run_lua('''
        TEST.map=2000; AddGuide(NS,"target",10,20,2000,nil,202)
        local before=Fingerprint(NS.char.progress)
        local items=NS.Adaptation:GetSuggestions()
        for i,s in ipairs(items) do if s.guideID=="target" then assert(NS.Adaptation:ApplySuggestion(i)) end end
        assert(NS.char.activeGuide=="target")
        assert(NS.Adaptation:ReturnToPrevious())
        assert(NS.char.activeGuide=="current" and Fingerprint(NS.char.progress)==before)
        assert(not NS.Adaptation:ReturnToPrevious())
        ''')

    def test_race_and_class_restrictions_are_respected_for_starting_route_suggestions(self):
        self.run_lua('''
        TEST.level=5; TEST.race="Gnome"
        AddGuide(NS,"human",1,13,1429,{"Human"},202)
        AddGuide(NS,"gnome",1,13,1426,{"Gnome","Dwarf"},203)
        AddGuide(NS,"mage",1,13,1429,nil,204); NS.guides.mage.classes={"MAGE"}
        local target
        for _,s in ipairs(NS.Adaptation:GetSuggestions()) do
          assert(s.guideID~="human" and s.guideID~="mage")
          if s.guideID then target=s.guideID end
        end
        assert(target=="gnome")
        ''')

    def test_report_explains_per_guide_slow_quest_step_and_history_observations(self):
        self.run_lua('''
        NS.Session:Initialize()
        for id=1,12 do NS.Session:OnEvent("QUEST_ACCEPTED",id,id) end
        Advance(NS,12)
        for id=1,12 do NS.Session:OnEvent("QUEST_TURNED_IN",id); Advance(NS,1) end
        local report=NS.Session:GetReport()
        assert(report:find("Por guía",1,true) and report:find("Ruta actual",1,true))
        assert(report:find("no tiempo exclusivo ni XP por misión",1,true))
        assert(report:find("%[12%]") < report:find("%[11%]"))
        assert(not report:find("[1]",1,true) and not report:find("[2]",1,true))
        assert(report:find("Paso actual",1,true) and report:find("visitas",1,true))
        NS.Session:Reset(false)
        assert(NS.Session:GetReport():find("Partida 1",1,true))
        assert(NS.Session:GetReport():find("[12]",1,true))
        ''')


if __name__ == "__main__":
    unittest.main()
