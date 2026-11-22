"""Drive the planner through its event, button, guide and navigation interfaces."""
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime


ADDON = Path(__file__).resolve().parents[1] / "RutaXP"


class DungeonPlannerTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.run_lua = self.lua.execute
        self.run_lua("""
            ns, frames, SlashCmdList = {}, {}, {}
            w = {map=12, x=.05, y=.05, time=100, level=23, faction="Alliance", race="Human",
                raceID=1, class="ROGUE", classID=4, active={}, ready={}, done={}, tracked=0,
                journal={}, objectives={}, waypoints={}, skills={}}
            function CreateFrame()
                local f = {owner=owner, events={}}
                function f:RegisterEvent(e) self.events[e]=true end
                function f:SetScript(s, fn) self[s]=fn end
                table.insert(frames,f)
                return f
            end
            function fire(e,...)
                for _,f in ipairs(frames) do
                    if (f.owner=="RestedQuestState" or f.owner=="DungeonPlanner") and f.events[e] then
                        f:OnEvent(e,...)
                    end
                end
            end
            function UnitRace() return w.race,w.race,w.raceID end
            function UnitClass() return w.class,w.class,w.classID end
            function UnitFactionGroup() return w.faction end
            function UnitLevel() return w.level end
            function GetTime() return w.time end
            function IsInGroup() return w.group or false end
            function GetNumGroupMembers() return w.size or 0 end
            function IsInInstance() return w.instance~=nil, w.instance and "party" or "none" end
            function GetInstanceInfo() return w.instance,nil,nil,nil,nil,nil,nil,w.instanceID end
            C_Map = {GetBestMapForUnit=function() return w.map end,
                GetPlayerMapPosition=function() if w.x then return {GetXY=function() return w.x,w.y end} end end}
            C_QuestLog = {IsOnQuest=function(id) return w.active[id] end,
                IsComplete=function(id) return w.ready[id] end,
                IsQuestFlaggedCompleted=function(id) return w.done[id] or false end,
                GetNumQuestLogEntries=function() return #w.journal end,
                GetInfo=function(i) return {questID=w.journal[i],isHeader=false} end,
                GetQuestObjectives=function(id) return w.objectives[id] end,
                GetNextWaypoint=function(id) if w.waypoints[id] then return unpack(w.waypoints[id]) end end}
            C_SuperTrack={GetSuperTrackedQuestID=function() return w.tracked end}
            C_SkillInfo={GetSkillLineInfoByID=function(id)
                if w.skills[id]~=nil then return {rank=w.skills[id],maxRank=300} end
            end}
            function point(map,x,y) return {map=map,x=x,y=y,f="l"} end
            function click(action)
                for _,r in ipairs(ns.DungeonPlanner:Rows()) do
                    if r.action==action then return ns.DungeonPlanner:Click(r) end
                end
                error("Missing planner action: "..action)
            end
            function contains(s)
                for _,r in ipairs(ns.DungeonPlanner:Rows()) do
                    if r.text:find(s, 1, true) then return true end
                end
                return false
            end
            function checkPoint(map,x,y)
                local a,b,c=ns.DungeonPlanner:Waypoint()
                assert(a==map and math.abs(b-x)<0.00001 and math.abs(c-y)<0.00001,
                    ("wanted %s/%s/%s; got %s/%s/%s"):format(map,x,y,tostring(a),tostring(b),tostring(c)))
            end
            function update() fire("QUEST_LOG_UPDATE") end
        """)
        for chunk in ("Core", "QuestEngine", "Navigation", "DungeonQuestData"):
            self.load(chunk)
        self.run_lua("""
            ns.char={progress={}}; ns.initialized=true
            function ns.GetEmbeddedModule() return {CurrentDungeon=function() return w.instance end} end
            production=ns.DungeonQuestData
            function useFixture(quests, ids)
                ns.DungeonQuestData={quests=quests, restedWorld={},
                    dungeons={Crypt={name="Cripta",entrance=point(12,75,80),quests=ids,minLevel=17,maxLevel=30,instanceID=101}}}
            end
        """)

    def load(self, name):
        self.lua.globals().owner = name
        self.run_lua((ADDON / (name + ".lua")).read_text(encoding="utf-8-sig"), "RutaXP", self.lua.globals().ns)

    def login(self):
        self.run_lua('frames={}')
        for name in ("RestedQuestState", "QuestFocus", "DungeonPlanner"):
            self.load(name)
        self.run_lua('fire("PLAYER_ENTERING_WORLD")')

    def test_outdoor_pickup_uses_actual_player_position_and_valid_distance(self):
        self.run_lua("""
            useFixture({
                [10]={title="Lejana",pickup=point(12,80,80)},
                [11]={title="Cercana",pickup=point(12,40,45)},
            },{10,11})
        """)
        self.login()
        self.run_lua("""
            p=ns.DungeonPlanner
            assert(ns:PlayerPoint().mapID==12)
            assert(not p:IsDetouring(),"Far quest on same map stole the route")
            w.x=nil; update()
            assert(not p:IsDetouring(),"Unknown position counts as nearby")
            w.x,w.y=.401,.45
            for _,f in ipairs(frames) do if f.OnUpdate then f:OnUpdate(3.1) end end
            assert(p:IsDetouring() and p:Hint():find("Cercana",1,true))
            checkPoint(12,.4,.45)
            click("later"); assert(not p:IsDetouring())
        """)
        self.login()
        self.run_lua('assert(not ns.DungeonPlanner:IsDetouring())')

    def test_prerequisite_preparation_then_entrance_inside_and_handins_across_relog(self):
        self.run_lua("""
            useFixture({
                [21]={title="Encargo previo",pickup=point(12,80,70),work=point(12,65,50),turnin=point(12,67,52)},
                [22]={title="Asalto",preAll={21},pickup=point(12,55,50),workInside=true,turnin=point(12,51,48)},
                [23]={title="Rescate",pickup={inside=true,npc=5},turnin=point(12,53,48),workInside=true}
            },{22,23})
        """)
        self.login()
        self.run_lua("""
            click("prepare"); p=ns.DungeonPlanner
            assert(p:Wants("accept",21) and not p:Wants("accept",22))
            checkPoint(12,.80,.70)
            w.active[21]=true; update(); assert(p:Hint():find("Encargo previo",1,true))
            w.ready[21]=true; update(); assert(p:Wants("turnin",21)); checkPoint(12,.67,.52)
            w.done[21]=true; w.active[21]=nil; update()
            assert(p:Wants("accept",22)); checkPoint(12,.55,.50)
            w.active[22]=true; update(); checkPoint(12,.75,.80)
            w.instance="Crypt"; w.map=401; fire("PLAYER_ENTERING_WORLD")
            assert(p:Wants("accept",23))
            w.active[23]=true; update()
            assert(not p:Wants("turnin",22))
            assert(ns.char.dungeonTrips.runs.Crypt[22] and ns.char.dungeonTrips.runs.Crypt[23])
        """)
        self.login()
        self.run_lua("""
            p=ns.DungeonPlanner; assert(p:IsDetouring())
            w.ready[22]=true; w.ready[23]=1; update()
            w.map=12; w.instance=nil; fire("PLAYER_ENTERING_WORLD")
            assert(p:Wants("turnin",22) and p:Wants("turnin",23))
            assert(ns.char.dungeonTrips.finished.Crypt)
            w.done[22]=true; w.done[23]=true; w.active={}; update()
            assert(not p:IsDetouring() and not contains("Cripta"))
        """)
        self.login()
        self.run_lua('assert(not ns.DungeonPlanner:IsDetouring() and #ns.DungeonPlanner:Rows()==0)')

    def test_masked_quests_and_unmet_all_or_alternatives(self):
        self.run_lua("""
            q={}
            for id=10,30 do q[id]={title="quest-"..id,pickup=point(12,80,80)} end
            q[10].faction="Horde"; q[11].classes=1; q[12].races=2; q[13].minLevel=24
            q[14].excl={55}; w.done[55]=true
            q[15].preAll={16,17}; q[18].pre={19,20}; q[19].faction="Horde"
            q[21].preAll={-70}; q[22].skill=164
            q[23].unavailable=true; q[24].unavailableRaces={"Human"}; q[25].classToken="PRIEST"
            q[26].reputation={{faction=123, standing=6}}
            C_Reputation={GetFactionDataByID=function() return {reaction=w.standing or 4} end}
            q[27].pre={28}; q[28].unavailable=true
            useFixture(q,{10,11,12,13,14,15,18,21,22,23,24,25,26,27})
        """)
        self.login()
        self.run_lua("""
            p=ns.DungeonPlanner; click("prepare")
            for _,id in ipairs({10,11,12,13,14,15,18,19,21,22,23,24,25,26,27,28}) do
                assert(not p:Wants("accept",id),"Ineligible pickup "..id)
            end
            for _,id in ipairs({16,17,20}) do assert(p:Wants("accept",id),"Missing prerequisite "..id) end
            w.done[16]=true; w.done[20]=true; w.active[70]=true; update()
            assert(not p:Wants("accept",15) and p:Wants("accept",18) and p:Wants("accept",21))
            w.done[17]=true; w.skills[164]=100; w.standing=6; w.time=w.time+10; update()
            assert(p:Wants("accept",15) and p:Wants("accept",22) and p:Wants("accept",26))
        """)

    def test_inaccessible_prerequisite_alone_cannot_start_a_detour(self):
        self.run_lua("""
            useFixture({
                [71]={title="Fase oculta",unavailable=true},
                [72]={title="Misión bloqueada",preAll={71},pickup=point(12,5,5)},
            },{72})
        """)
        self.login()
        self.run_lua("""
            local planner=ns.DungeonPlanner
            assert(not planner:IsDetouring() and not contains("Preparar mazmorra"),
                "Dungeon preparation was suggested without an achievable task")
            assert(not planner:Wants("accept",71) and not planner:Wants("accept",72))
            w.done[71]=true; update(); assert(planner:Wants("accept",72))
        """)

    def test_partial_visit_is_not_finished_and_repeat_is_explicit(self):
        self.run_lua("""
            useFixture({
                [81]={title="Primera",pickup=point(12,70,80),turnin=point(12,30,30)},
                [82]={title="Posterior",pre={81},pickup=point(12,80,80),turnin=point(12,30,30)},
            },{81,82})
            w.active[81]=true; w.instance="Crypt"; w.map=401
        """)
        self.login()
        self.run_lua("""
            p=ns.DungeonPlanner; assert(p:IsDetouring())
            w.instance=nil; w.map=12; fire("ZONE_CHANGED_NEW_AREA"); p:Rows()
            assert(not ns.char.dungeonTrips.finished.Crypt)
            w.instance="Crypt"; w.map=401; update(); p:Rows()
            w.ready[81]=true; update(); p:Rows()
            w.instance=nil; w.map=12; fire("ZONE_CHANGED_NEW_AREA"); p:Rows()
            w.done[81]=true; w.active[81]=nil; update()
            assert(not contains("Posterior") and not contains("Preparar mazmorra"))
            p:Resume(); assert(not p:Wants("accept",82))
            p:Repeat("Cripta"); assert(p:Wants("accept",82) and ns.char.dungeonTrips.finished.Crypt)
            click("later"); assert(not p:IsDetouring())
        """)
        self.login()
        self.run_lua('assert(not ns.DungeonPlanner:IsDetouring())')

    def test_world_quest_objective_progress_and_live_waypoint_preserve_the_route(self):
        self.run_lua("""
            useFixture({},{}); ns.DungeonQuestData.restedWorld[333]=true
            local ordinary={id="outdoor", title="Guía", faction="Alliance", steps={
                {title="De camino",goals={{t="kill",quest=200}}},
                {title="Encargo",goals={{t="kill",quest=333,oi=1,waypoint={mapID=12,x=.3,y=.32}},
                    {t="turnin",quest=333,waypoint={mapID=12,x=.71,y=.4}}}}}}
            ns:RegisterGuide(ordinary); ns.char.activeGuide=ordinary.id
            ns.GetActiveGoal=function(_,step) return step.goals[1] end
            w.active[333]=true; w.journal={333}
            w.objectives[333]={{numFulfilled=0,text="0/2"},{numFulfilled=0,text="0/5"}}
        """)
        self.login()
        self.run_lua("""
            p=ns.DungeonPlanner; update()
            assert(not p:IsDetouring(),"Login data was mistaken for objective progress")
            w.objectives[333][1].numFulfilled=1; w.objectives[333][1].text="1/2"; update()
            assert(p:IsDetouring() and contains("1/2")); checkPoint(12,.3,.32)
            assert(ns:GetProgress("outdoor").cursor==1)
            w.waypoints[333]={56,.41,.57}; update(); checkPoint(56,.41,.57)
            click("world"); assert(not p:IsDetouring())
            w.objectives[333][2].numFulfilled=1; update(); assert(p:IsDetouring())
            w.waypoints={}; w.ready[333]=true; update(); checkPoint(12,.71,.4)
            w.done[333]=true; w.active[333]=nil; update()
            assert(not p:IsDetouring() and ns:GetProgress("outdoor").cursor==1)
        """)

    def test_real_deadmines_chain_and_event_windows(self):
        self.run_lua('w.map=1436; w.level=20; w.instance="The Deadmines"')
        self.login()
        self.run_lua("""
            p=ns.DungeonPlanner; r=ns.RestedQuestState
            assert(p:Heading()==production.dungeons["The Deadmines"].name)
            assert(not p:Wants("accept",166),"Final Defias quest offered before the previous tasks")
            w.instance=nil; fire("ZONE_CHANGED_NEW_AREA")
            fire("QUEST_ACCEPTED",2,166); assert(r.Active(166))
            w.time=w.time+3; assert(not r.Active(166))
            fire("QUEST_ACCEPTED",166); fire("QUEST_REMOVED",166); assert(not r.Active(166))
            fire("QUEST_TURNED_IN",166); assert(r.Delivered(166))
            w.time=w.time+6; assert(not r.Delivered(166))
            w.done[166]=true; assert(r.Delivered(166))
        """)

    def test_accepted_instance_quest_does_not_take_over_a_solo_or_duo_route(self):
        self.run_lua("""
            useFixture({[501]={title="Objetivo interior",pickup=point(12,80,80),workInside=true}}, {501})
            w.active[501]=true
        """)
        self.login()
        self.run_lua("""
            p=ns.DungeonPlanner
            assert(not p:IsDetouring() and contains("Cripta"))
            w.group=true; w.size=2; fire("GROUP_ROSTER_UPDATE")
            assert(not p:IsDetouring())
            w.size=5; fire("GROUP_ROSTER_UPDATE")
            assert(p:IsDetouring()); checkPoint(12,.75,.80)
            click("later"); assert(not p:IsDetouring())
            w.size=4; fire("GROUP_ROSTER_UPDATE")
            w.size=5; fire("GROUP_ROSTER_UPDATE"); assert(not p:IsDetouring())
        """)
