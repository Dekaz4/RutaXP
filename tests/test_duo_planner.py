"""Duo planning uses each observed journal, never another player's progress."""
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
STUBS = r'''
TEST={now=0,level=12,race="Human",class="WARRIOR",faction="Alliance",map=1429,
  mine={},partner={},objectives={},requests={},reads=0,meeting=true,ctx={enabled=true,known=true,
  online=true,sameParty=true,partnerLevel=10,partnerRace="NightElf",partnerClass="PRIEST",
  partnerFaction="Alliance",partnerMapID=1429,guideID="current",cursor=1}}
function GetTime() return TEST.now end
function UnitLevel() return TEST.level end
function UnitRace() return TEST.race,TEST.race end
function UnitClass() return TEST.class,TEST.class end
function UnitFactionGroup() return TEST.faction end
C_Map={GetBestMapForUnit=function() return TEST.map end}
C_QuestLog={}
function C_QuestLog.GetTitleForQuestID(id) return "Misión "..id end
function C_QuestLog.GetQuestObjectives(id) return TEST.objectives[id] end
function Fingerprint(t)
 if type(t)~="table" then return tostring(t) end
 local keys={};for k in pairs(t) do keys[#keys+1]=k end
 table.sort(keys,function(a,b) return tostring(a)<tostring(b) end)
 local out={};for _,k in ipairs(keys) do out[#out+1]=tostring(k).."="..Fingerprint(t[k]) end
 return "{"..table.concat(out,";").."}"
end
NS={guides={},order={},char={activeGuide="current",progress={current={cursor=1,review=true,confirmed={["1:1"]=true}}}},Duo={}}
function NS:Sync() error("Planner must not sync or advance guide progress") end
function NS:GetCurrent() error("Read-only planner must not initialize or clamp progress") end
function NS:SelectGuide() error("Planner must preserve guide cursors") end
function NS.Duo:GetContext() return TEST.ctx end
function NS.Duo:LocalQuest(q) TEST.reads=TEST.reads+1; return {state=TEST.mine[q] or 0} end
function NS.Duo:GetPartnerQuest(q) TEST.reads=TEST.reads+1; return TEST.partner[q] end
function NS.Duo:RequestQuest(q) TEST.requests[#TEST.requests+1]=q end
function NS.Duo:FollowMeeting(value) TEST.meeting=value end
function NS.Duo:GetObjectiveProgress(q,i)
 local localData=(TEST.objectives[q] or {})[i]
 local partnerData=(TEST.partner[q] and TEST.partner[q].objectives or {})[i]
 return {mine=localData and {known=true,current=localData.numFulfilled,total=localData.numRequired,finished=localData.finished},
   partner=partnerData or {known=false}}
end
function NS:GetGoalWaypoint(goal)
 if TEST.noWaypoint then return nil end
 if not goal.map or not goal.x then return nil end
 return {mapID=goal.map,x=goal.x/100,y=goal.y/100,source="guide",goal=goal,z=goal.z}
end
function AddGuide(id,q,low,high,races,classes)
 local g={id=id,title="Ruta "..id,faction="Alliance",minLevel=low or 1,maxLevel=high or 20,
   races=races,classes=classes,zone=1429,steps={{title="Inicio",goals={
     {t="accept",quest=q,npc=100+q,npcName="NPC "..q,map=1429,x=30,y=40},
     {t="kill",quest=q,oi=1,npc=200+q,count=5},
     {t="turnin",quest=q,npc=100+q,npcName="NPC "..q,map=1429,x=30,y=40}}}}}
 NS.guides[id]=g; NS.order[#NS.order+1]=id;return g
end
function Known(q,state) TEST.partner[q]={state=state} end
function Both(q,a,b) TEST.mine[q]=a;Known(q,b) end
AddGuide("current",101)
Both(101,0,0)
'''


class DuoPlannerTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(STUBS)
        loader = self.lua.execute("return function(...)\n" + (ROOT / "RutaXP" / "DuoPlanner.lua").read_text(encoding="utf-8") + "\nend")
        loader("RutaXP", self.lua.globals().NS)

    def check(self, code):
        self.lua.execute(code)

    def test_common_route_checks_both_levels_classes_races_factions(self):
        self.check('''
        AddGuide("human",102,1,20,{"Human"});Both(102,0,0)
        AddGuide("warrior",103,1,20,nil,{"WARRIOR"});Both(103,0,0)
        AddGuide("tooHigh",104,11,20);Both(104,0,0)
        local routes=NS.DuoPlanner:GetCommonRoutes()
        assert(#routes==1 and routes[1].guideID=="current" and routes[1].referenceLevel==10)
        assert(routes[1].text:find("razas y las clases",1,true))
        TEST.ctx.partnerFaction="Horde";assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        TEST.ctx.partnerFaction="Alliance";TEST.ctx.known=false
        assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        TEST.ctx.known=true;TEST.ctx.partnerClass=nil
        assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        ''')

    def test_requires_real_journal_or_both_confirmed_in_route_zone(self):
        self.check('''
        TEST.partner[101]=nil;assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        assert(TEST.requests[1]==101)
        Known(101,0);NS.DuoPlanner:Invalidate();TEST.ctx.partnerMapID=1438
        assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        Both(101,1,1);NS.DuoPlanner:Invalidate()
        local routes=NS.DuoPlanner:GetCommonRoutes()
        assert(#routes==1 and routes[1].sharedActive and not routes[1].sameZone)
        assert(routes[1].text:find("mapas distintos",1,true))
        ''')

    def test_prerequisites_keep_or_and_and_unknown_semantics_for_each_player(self):
        self.check('''
        local a=NS.guides.current.steps[1].goals[1]
        a.pre={10,11};a.preAll={20,21};a.closedBy={30}
        Both(10,0,0);Both(11,3,3);Both(20,3,3);Both(21,3,3);Both(30,0,0)
        assert(#NS.DuoPlanner:GetCommonRoutes()==1)
        Known(10,3);TEST.partner[11]=nil;NS.DuoPlanner:Invalidate()
        assert(#NS.DuoPlanner:GetCommonRoutes()==1) -- one OR branch is enough
        Known(20,0);NS.DuoPlanner:Invalidate();assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        Known(20,3);Known(10,0);NS.DuoPlanner:Invalidate();assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        Known(11,3);TEST.partner[30]=nil;NS.DuoPlanner:Invalidate();assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        Known(30,1);NS.DuoPlanner:Invalidate();assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        ''')

    def test_does_not_jump_over_blocked_or_unknown_first_shared_quest(self):
        self.check('''
        local goals=NS.guides.current.steps[1].goals
        goals[1].preAll={10};Both(10,0,0)
        goals[#goals+1]={t="accept",quest=202};Both(202,0,0)
        assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        Both(101,3,3);NS.DuoPlanner:Invalidate()
        assert(NS.DuoPlanner:GetCommonRoutes()[1].questID==202)
        ''')

    def test_advanced_common_journal_does_not_require_unknown_entire_past_history(self):
        self.check('''
        TEST.mine[101]=3;TEST.partner[101]=nil
        NS.guides.current.steps[2]={title="Paso actual",goals={{t="kill",quest=202,oi=1}}}
        NS.char.progress.current.cursor=2;Both(202,1,1)
        C_QuestLog.GetNumQuestLogEntries=function() return 1 end
        C_QuestLog.GetInfo=function() return {questID=202,isHeader=false} end
        local route=NS.DuoPlanner:GetCommonRoutes()[1]
        assert(route and route.questID==202 and route.sharedActive)
        assert(route.text:find("No confirma misiones anteriores",1,true))
        ''')

    def test_route_selection_revalidates_and_bookmarks_without_progress_changes(self):
        self.check('''
        AddGuide("second",202,9,20);Both(202,1,1)
        NS.char.progress.second={cursor=3,review=true,skipped={["2:1"]=true}}
        local before=Fingerprint(NS.char.progress)
        local routes=NS.DuoPlanner:GetCommonRoutes();assert(routes[2].guideID=="second")
        TEST.ctx.partnerLevel=8
        assert(not NS.DuoPlanner:ApplyCommonRoute(2));assert(NS.char.activeGuide=="current")
        TEST.ctx.partnerLevel=10;NS.DuoPlanner:Invalidate();NS.DuoPlanner:GetCommonRoutes()
        assert(NS.DuoPlanner:ApplyCommonRoute(2));assert(NS.char.activeGuide=="second")
        assert(NS.char.adaptation.bookmarks[1].guideID=="current" and NS.char.adaptation.bookmarks[1].review)
        assert(Fingerprint(NS.char.progress)==before and TEST.ctx.guideID=="current")
        ''')

    def test_local_pickup_focus_is_explicit_temporary_and_keeps_both_routes(self):
        self.check('''
        Both(101,0,1);local before=Fingerprint(NS.char.progress)
        local d=NS.DuoPlanner:GetDifferences();assert(#d==1)
        assert(d[1].owner=="mine" and d[1].action=="pickup" and d[1].npcName=="NPC 101")
        assert(NS.DuoPlanner:GetNavigationOverride()==nil)
        local ok,point=NS.DuoPlanner:FocusDifference(1)
        assert(ok and point.mapID==1429 and point.x==.3 and point.source=="duo-difference")
        assert(TEST.meeting==false and NS.DuoPlanner:GetNavigationOverride()==point)
        assert(NS.char.activeGuide=="current" and TEST.ctx.guideID=="current" and Fingerprint(NS.char.progress)==before)
        TEST.now=100;assert(NS.DuoPlanner:GetNavigationOverride()==point)
        assert(NS.DuoPlanner:ClearFocus());assert(NS.DuoPlanner:GetNavigationOverride()==nil)
        assert(Fingerprint(NS.char.progress)==before)
        ''')

    def test_partner_missing_quest_is_not_a_local_pickup_and_unknown_is_not_absent(self):
        self.check('''
        Both(101,1,0)
        local d=NS.DuoPlanner:GetDifferences();assert(d[1].owner=="partner" and not d[1].action)
        assert(d[1].text:find("NPC 101",1,true));assert(not NS.DuoPlanner:FocusDifference(1))
        TEST.partner[101]=nil;NS.DuoPlanner:Invalidate();d=NS.DuoPlanner:GetDifferences()
        assert(d[1].kind=="unknown" and not d[1].action)
        assert(d[1].text:find("No se interpreta como ausente",1,true))
        TEST.partner[101]={state=1,basic=true};NS.DuoPlanner:Invalidate();d=NS.DuoPlanner:GetDifferences()
        assert(d[1].kind=="unknown" and d[1].text:find("confirma que tu amigo la lleva",1,true))
        ''')

    def test_pickup_explains_actual_and_or_prerequisites_without_guessing_peer_journal(self):
        self.check('''
        Both(101,0,1);local a=NS.guides.current.steps[1].goals[1]
        a.preAll={10,11};a.pre={20,21};Both(10,0,3);Both(11,3,3);Both(20,0,3);Both(21,0,3)
        local d=NS.DuoPlanner:GetDifferences()[1]
        assert(d.text:find("todas estas previas: Misión 10",1,true))
        assert(d.text:find("una de estas previas alternativas: Misión 20, Misión 21",1,true))
        assert(d.npcID==201 and not d.action and not d.recoveryPossible)
        Both(101,1,0);Known(10,3);Known(11,3);Known(20,0);TEST.partner[21]=nil
        NS.DuoPlanner:Invalidate();d=NS.DuoPlanner:GetDifferences()[1]
        assert(d.owner=="partner" and d.text:find("Sin confirmar requisitos",1,true))
        assert(#d.unknownQuestIDs==1 and not d.action)
        ''')

    def test_recovery_possibility_requires_complete_published_source(self):
        self.check('''
        Both(101,0,1);NS.guides.current.steps[1].goals[1].preAll={10}
        Both(10,0,0)
        assert(not NS.DuoPlanner:GetDifferences()[1].recoveryPossible)
        AddGuide("prerequisite",10,1,5);NS.DuoPlanner:Invalidate()
        assert(NS.DuoPlanner:GetDifferences()[1].recoveryPossible)
        NS.guides.prerequisite.steps[1].goals[1].preAll={11};Both(11,0,0)
        NS.DuoPlanner:Invalidate();assert(not NS.DuoPlanner:GetDifferences()[1].recoveryPossible)
        ''')

    def test_objective_difference_uses_fresh_individual_counts_and_reports_unknown(self):
        self.check('''
        Both(101,1,1)
        TEST.objectives[101]={{numFulfilled=4,numRequired=5,finished=false},{numFulfilled=1,numRequired=1,finished=true}}
        TEST.partner[101].objectives={[1]={known=true,current=2,total=5,finished=false}}
        local d=NS.DuoPlanner:GetDifferences();assert(#d==2)
        assert(d[1].kind=="objective" and d[1].objectiveIndex==1 and d[1].owner=="partner")
        assert(d[1].text:find("4/5",1,true) and d[1].text:find("2/5",1,true) and not d[1].action)
        assert(d[2].kind=="unknown" and d[2].objectiveIndex==2)
        assert(not NS.DuoPlanner:FocusDifference(1))
        ''')

    def test_class_race_branches_remain_individual_and_header_exclusions_apply(self):
        self.check('''
        local goals=NS.guides.current.steps[1].goals
        for _,g in ipairs(goals) do g.only={classes={"WARRIOR"}} end
        Both(101,1,0)
        local d=NS.DuoPlanner:GetDifferences()[1]
        assert(d.kind=="individual" and not d.action and #NS.DuoPlanner:GetCommonRoutes()==0)
        for _,g in ipairs(goals) do g.only={races={"!NightElf"}} end
        NS.DuoPlanner:Invalidate();assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        TEST.race="Undead";TEST.ctx.partnerRace="Scourge"
        NS.guides.current.races={"Scourge"};for _,g in ipairs(goals) do g.only=nil end
        Both(101,1,1);NS.DuoPlanner:Invalidate();assert(#NS.DuoPlanner:GetCommonRoutes()==1)
        ''')

    def test_incomplete_source_unresolved_position_and_stale_acceptance_disable_focus(self):
        self.check('''
        Both(101,0,1);local goals=NS.guides.current.steps[1].goals
        goals[3]=nil
        local d=NS.DuoPlanner:GetDifferences()[1];assert(not d.action)
        goals[3]={t="turnin",quest=101};NS.DuoPlanner.catalog=nil;TEST.noWaypoint=true
        NS.DuoPlanner:Invalidate();assert(not NS.DuoPlanner:GetDifferences()[1].action)
        TEST.noWaypoint=false;NS.DuoPlanner:Invalidate();assert(NS.DuoPlanner:GetDifferences()[1].action=="pickup")
        TEST.mine[101]=1;assert(not NS.DuoPlanner:FocusDifference(1))
        assert(NS.DuoPlanner:GetNavigationOverride()==nil)
        ''')

    def test_caches_results_and_catalog_but_refreshes_after_ttl_and_bounds_requests(self):
        self.check('''
        for i=1,20 do AddGuide("extra"..i,200+i);TEST.partner[200+i]=nil end
        local r=NS.DuoPlanner:GetCommonRoutes();local reads=TEST.reads;local catalog=NS.DuoPlanner.catalog
        assert(#TEST.requests<=12 and #r<=3)
        TEST.now=1;assert(NS.DuoPlanner:GetCommonRoutes()==r and TEST.reads==reads)
        TEST.now=6;NS.DuoPlanner:GetCommonRoutes();assert(TEST.reads>reads and NS.DuoPlanner.catalog==catalog)
        AddGuide("new",999);NS.DuoPlanner:Invalidate();NS.DuoPlanner:GetCommonRoutes()
        assert(NS.DuoPlanner.catalog~=catalog)
        ''')

    def test_difference_cap_and_reports_do_not_claim_full_journal_comparison(self):
        self.check('''
        local goals=NS.guides.current.steps[1].goals
        for i=1,20 do goals[#goals+1]={t="kill",quest=300+i,oi=1};Both(300+i,1,0) end
        assert(#NS.DuoPlanner:GetDifferences()==12)
        local report=NS.DuoPlanner:GetReport()
        assert(report:find("solo a tu personaje",1,true))
        TEST.ctx.online=false;assert(NS.DuoPlanner:GetReport():find("Hace falta",1,true))
        ''')

    def test_unknown_local_journal_is_labeled_local_and_never_a_pickup(self):
        self.check('''
        function NS.Duo:LocalQuest() return {state=0,known=false} end
        local d=NS.DuoPlanner:GetDifferences()[1]
        assert(d.kind=="unknown" and d.owner=="mine" and not d.action)
        assert(d.text:find("tu registro actual",1,true))
        assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        ''')

    def test_unknown_local_objective_is_reported_with_known_partner_counter(self):
        self.check('''
        Both(101,1,1)
        TEST.partner[101].objectives={[1]={known=true,current=2,total=5,finished=false}}
        TEST.objectives[101]=nil
        local d=NS.DuoPlanner:GetDifferences()
        assert(#d==1 and d[1].owner=="mine" and d[1].kind=="unknown" and d[1].objectiveIndex==1)
        assert(d[1].text:find("contador local",1,true) and not d[1].action)
        ''')

    def test_older_partner_can_follow_lower_players_range_with_same_strict_minimum(self):
        self.check('''
        NS.guides.current.minLevel=10;NS.guides.current.maxLevel=15
        TEST.level=25;TEST.ctx.partnerLevel=10
        local route=NS.DuoPlanner:GetCommonRoutes()[1]
        assert(route and route.referenceLevel==10)
        assert(route.text:find("menos XP",1,true))
        TEST.level=10;TEST.ctx.partnerLevel=25;NS.DuoPlanner:Invalidate()
        assert(NS.DuoPlanner:GetCommonRoutes()[1].referenceLevel==10)
        TEST.ctx.partnerLevel=9;assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        TEST.level=25;TEST.ctx.partnerLevel=25;Both(101,1,1);NS.DuoPlanner:Invalidate()
        assert(NS.DuoPlanner:GetCommonRoutes()[1].sharedActive)
        ''')

    def test_focus_is_cleared_when_guide_step_or_recovery_context_changes(self):
        self.check('''
        Both(101,0,1);assert(NS.DuoPlanner:FocusDifference(1))
        local before=Fingerprint(NS.char.progress)
        NS.char.recovery={active=true};assert(NS.DuoPlanner:GetNavigationOverride()==nil and NS.DuoPlanner.focus==nil)
        assert(Fingerprint(NS.char.progress)==before)
        NS.char.recovery=nil;assert(NS.DuoPlanner:FocusDifference(1))
        NS.char.progress.current.cursor=2;before=Fingerprint(NS.char.progress)
        assert(NS.DuoPlanner:GetNavigationOverride()==nil and NS.DuoPlanner.focus==nil)
        assert(Fingerprint(NS.char.progress)==before)
        NS.char.progress.current.cursor=1;NS.DuoPlanner:Invalidate();assert(NS.DuoPlanner:FocusDifference(1))
        AddGuide("other",202);NS.char.activeGuide="other";before=Fingerprint(NS.char.progress)
        assert(NS.DuoPlanner:GetNavigationOverride()==nil and NS.DuoPlanner.focus==nil)
        assert(Fingerprint(NS.char.progress)==before)
        ''')

    def test_acceptance_delivery_or_hidden_local_state_cancels_pickup_focus(self):
        self.check('''
        Both(101,0,1);assert(NS.DuoPlanner:FocusDifference(1))
        local before=Fingerprint(NS.char.progress)
        TEST.mine[101]=1;assert(NS.DuoPlanner:GetNavigationOverride()==nil)
        TEST.mine[101]=0;assert(NS.DuoPlanner:FocusDifference(1))
        TEST.mine[101]=3;assert(NS.DuoPlanner:GetNavigationOverride()==nil)
        TEST.mine[101]=0;assert(NS.DuoPlanner:FocusDifference(1))
        function NS.Duo:LocalQuest() return {known=false} end
        assert(NS.DuoPlanner:GetNavigationOverride()==nil)
        assert(Fingerprint(NS.char.progress)==before)
        ''')

    def test_three_route_limit_profession_uncertainty_and_one_recoverable_or_branch(self):
        self.check('''
        for i=1,5 do AddGuide("extra"..i,200+i);Both(200+i,0,0) end
        assert(#NS.DuoPlanner:GetCommonRoutes()==3)
        Both(101,0,1);local a=NS.guides.current.steps[1].goals[1]
        a.profLine=185;a.profRank=1;NS.DuoPlanner:Invalidate()
        local d=NS.DuoPlanner:GetDifferences()[1]
        assert(not d.action and d.text:find("profesión",1,true))
        a.profLine=nil;a.profRank=nil;a.pre={10,11};Both(10,0,0);Both(11,0,0)
        AddGuide("one-possible-branch",10)
        NS.DuoPlanner:Invalidate();d=NS.DuoPlanner:GetDifferences()[1]
        assert(d.recoveryPossible and not d.action)
        ''')


class DuoPlannerProtocolIntegrationTests(unittest.TestCase):
    def test_real_peer_counts_and_local_focus_never_call_sync(self):
        from test_duo import DuoHost

        goals = [{"t": "complete", "quest": 100, "oi": 1}, {"t": "turnin", "quest": 100}]
        a, b = DuoHost(goals=goals), DuoHost("Dos", "Uno", goals=goals)
        for h in (a, b):
            h.state.level = h.state.friendLevel = 10
            h.state.entries = h.table([{"questID": 100, "isHeader": False}])
            h.load((ROOT / "RutaXP" / "DuoPlanner.lua").read_text(encoding="utf-8"), "RutaXP", h.ns)
            h.lua.globals().NS = h.ns
            h.lua.execute('''
            local g=NS.guides[NS.char.activeGuide];g.zone=37
            for _,goal in ipairs(g.steps[1].goals) do
              if goal.t=="accept" then goal.npc=123;goal.npcName="Instructor";goal.map=37;goal.x=42;goal.y=63 end
            end
            function NS:GetGoalWaypoint(g) return {mapID=g.map,x=g.x/100,y=g.y/100} end
            ''')
        a.quest(100, onQuest=True, objectives=[{"numFulfilled": 4, "numRequired": 8, "finished": False}])
        b.quest(100, onQuest=True, objectives=[{"numFulfilled": 2, "numRequired": 8, "finished": False}])
        for _ in range(20):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        planner = a.ns.DuoPlanner
        routes = planner.GetCommonRoutes(planner)
        self.assertEqual(routes[1].guideID, "forever/alliance/test")
        self.assertTrue(routes[1].sharedActive)
        differences = planner.GetDifferences(planner)
        self.assertEqual(differences[1].kind, "objective")
        self.assertIn("4/8", differences[1].text)
        self.assertIn("2/8", differences[1].text)

        a.quest(100, onQuest=False)
        planner.Invalidate(planner)
        differences = planner.GetDifferences(planner)
        self.assertEqual(differences[1].action, "pickup")
        a.lua.execute('''
        TEST.unwantedSync=0
        function NS:Sync() TEST.unwantedSync=TEST.unwantedSync+1 end
        BEFORE={cursor=NS.char.progress[NS.char.activeGuide].cursor,
          confirmed=NS.char.progress[NS.char.activeGuide].confirmed}
        ''')
        result = planner.FocusDifference(planner, 1)
        self.assertTrue(result[0])
        self.assertEqual(a.state.unwantedSync, 0)
        self.assertEqual(a.ns.char.progress[a.ns.char.activeGuide].cursor, a.lua.globals().BEFORE.cursor)
        self.assertEqual(b.ns.char.activeGuide, "forever/alliance/test")


class AutomaticPlannerTests(unittest.TestCase):
    # Use the same real Lua module with a small multi-step shared route.
    check = DuoPlannerTests.check

    def setUp(self):
        DuoPlannerTests.setUp(self)
        self.check('''
        TEST.playerName="Uno";TEST.ctx.partnerName="dos-forever"
        function UnitFullName() return TEST.playerName,"Forever" end
        function GetNormalizedRealmName() return "Forever" end
        NS.guides.current.steps={
          {title="Inicio",goals={{t="accept",quest=101,npc=1,npcName="Inicio",map=1429,x=10,y=10}}},
          {title="Ayuda pendiente",goals={{t="kill",quest=202,oi=1,map=1429,x=25,y=35,title="Lobos"}}},
          {title="Entrega",goals={{t="turnin",quest=202,npc=2,npcName="Guardia",map=1429,x=40,y=50}}},
          {title="Después",goals={{t="accept",quest=303,npc=3,npcName="Otro",map=1429,x=50,y=50}}},
          {title="Mi posición",goals={{t="complete",quest=404,map=1429,x=80,y=80}}}}
        NS.char.progress.current.cursor=5
        TEST.ctx.cursor=2
        Both(101,3,3);Both(202,3,1);Both(303,0,0);Both(404,1,0)
        TEST.partner[202].objectives={[1]={known=true,current=2,total=5,finished=false}}
        function NS:GetActiveGoal() error("Shared view must not use my active quest goal") end
        ''')

    def test_ahead_player_uses_buddys_observed_step_without_rewinding_saved_progress(self):
        self.check('''
        local before=Fingerprint(NS.char)
        local plan=NS.DuoPlanner:GetAutomaticPlan()
        assert(plan and plan.verified and plan.guideID=="current")
        assert(plan.ownCursor==5 and plan.partnerCursor==2 and plan.sharedCursor==2)
        assert(plan.referenceName=="dos-forever")
        local status=NS.DuoPlanner:GetSharedStepStatus("current",2)
        assert(status.known and not status.complete and status.status=="active")
        local item=status.items[1]
        assert(item.status=="active" and item.mine.done and not item.partner.done and item.isCurrent)
        assert(item.action=="kill" and item.index==1 and item.subtitle:find("2/5",1,true))
        local point=NS.DuoPlanner:GetSharedWaypoint("current",2)
        assert(point and point.source=="duo-follow" and point.x==.25 and point.y==.35)
        assert(point.referenceName=="dos-forever" and point.label:find("Lobos",1,true))
        assert(Fingerprint(NS.char)==before)
        ''')

    def test_own_delivery_never_claims_unknown_partner_completion(self):
        self.check('''
        TEST.partner[202]=nil
        local status=NS.DuoPlanner:GetSharedStepStatus("current",2)
        assert(not status.known and not status.complete and status.status=="unknown")
        assert(status.items[1].mine.done and not status.items[1].partner.done)
        assert(not NS.DuoPlanner:ValidateAutomaticGuide("current"))
        assert(NS.DuoPlanner:GetSharedWaypoint("current",2)==nil)
        ''')

    def test_individual_class_quests_are_visible_without_becoming_shared_requirements(self):
        self.check('''
        NS.guides.current.steps[2].goals={
          {t="complete",quest=501,only={classes={"WARRIOR"}},title="Cadena guerrero",map=1429,x=10,y=10},
          {t="complete",quest=502,only={classes={"PRIEST"}},title="Cadena sacerdote",map=1429,x=70,y=60}}
        Both(501,3,0);Both(502,0,1)
        local status=NS.DuoPlanner:GetSharedStepStatus("current",2)
        assert(status.individualOnly and not status.complete and status.status=="individual")
        assert(status.items[1].status=="skip" and status.items[2].status=="skip")
        assert(NS.DuoPlanner:ValidateAutomaticGuide("current"))
        local point=NS.DuoPlanner:GetSharedWaypoint("current",2)
        assert(point and point.x==.7 and point.individual and point.referenceName=="dos-forever")
        assert(NS.char.progress.current.cursor==5)
        TEST.partner[502]=nil
        assert(not NS.DuoPlanner:ValidateAutomaticGuide("current"))
        status=NS.DuoPlanner:GetSharedStepStatus("current",2)
        assert(not status.known and not status.complete and status.status=="unknown")
        ''')

    def test_trainer_candidates_use_partner_class_and_never_our_quest_waypoint(self):
        self.check('''
        NS.guides.current.steps[2].goals={{t="train",title="Habilidades",candidates={
          {npc=1,npcName="Guerrero",classes={"WARRIOR"},map=1429,x=10,y=20},
          {npc=2,npcName="Sacerdote",classes={"PRIEST"},map=1429,x=70,y=80}}}}
        local point=NS.DuoPlanner:GetSharedWaypoint("current",2)
        assert(point and point.x==.7 and point.y==.8 and point.requiresConfirmation)
        assert(point.label:find("Sacerdote",1,true) and point.referenceName=="dos-forever")
        ''')

    def test_new_guide_cursor_requires_a_fully_observed_local_prefix(self):
        self.check('''
        AddGuide("new",600)
        NS.guides.new.steps={
          {title="Primera requerida",goals={{t="accept",quest=600}}},
          {title="Siguiente entregada",goals={{t="turnin",quest=601}}},
          {title="Tercera",goals={{t="accept",quest=602}}}}
        TEST.ctx.guideID="new";TEST.ctx.cursor=3
        Both(600,0,3);Both(601,3,3);Both(602,0,0)
        local ok,reason,plan=NS.DuoPlanner:ValidateAutomaticGuide("new")
        assert(ok and plan.ownCursor==1 and plan.ownCursorObserved)
        assert(NS.char.progress.new==nil) -- A later delivered quest cannot poison the prefix.
        TEST.mine[600]=3
        ok,reason,plan=NS.DuoPlanner:ValidateAutomaticGuide("new")
        assert(ok and plan.ownCursor==3 and plan.ownCursorObserved)
        NS.guides.new.steps[1]={title="Nota manual requerida",goals={{t="note",note="Leer"}}}
        ok,reason,plan=NS.DuoPlanner:ValidateAutomaticGuide("new")
        assert(ok and plan.ownCursor==1 and not plan.ownCursorObserved)
        assert(plan.sharedCursor==3 and NS.char.progress.new==nil)
        ''')

    def test_validation_accepts_safe_non_first_manual_suggestion_and_rechecks_both_prerequisites(self):
        self.check('''
        for i=1,5 do AddGuide("alternative"..i,600+i);Both(600+i,0,0) end
        local ok,reason,plan=NS.DuoPlanner:ValidateAutomaticGuide("alternative5")
        assert(ok and plan.guideID=="alternative5")
        local a=NS.guides.alternative5.steps[1].goals[1]
        a.preAll={700};a.pre={701,702}
        Both(700,3,3);Both(701,0,0);Both(702,3,3)
        assert(NS.DuoPlanner:ValidateAutomaticGuide("alternative5"))
        Known(700,0);assert(not NS.DuoPlanner:ValidateAutomaticGuide("alternative5"))
        Known(700,3);TEST.partner[702]=nil;assert(not NS.DuoPlanner:ValidateAutomaticGuide("alternative5"))
        ''')

    def test_initial_race_incompatibility_stops_auto_plan_without_invented_travel(self):
        self.check('''
        NS.guides.current.races={"Human"}
        assert(NS.DuoPlanner:GetAutomaticPlan()==nil)
        assert(not NS.DuoPlanner:ValidateAutomaticGuide("current"))
        assert(NS.DuoPlanner:GetSharedWaypoint("current",2)==nil)
        ''')

    def test_lower_level_reference_accepts_higher_helper_and_strict_minimum(self):
        self.check('''
        TEST.level=25;TEST.ctx.partnerLevel=10
        NS.guides.current.minLevel=10;NS.guides.current.maxLevel=15
        local plan=NS.DuoPlanner:GetAutomaticPlan()
        assert(plan and plan.referenceLevel==10 and plan.sharedCursor==2)
        TEST.ctx.partnerLevel=9;assert(not NS.DuoPlanner:ValidateAutomaticGuide("current"))
        ''')

    def test_plan_reference_is_symmetric_when_local_and_remote_are_swapped(self):
        self.check('''
        local left=NS.DuoPlanner:GetAutomaticPlan()
        TEST.playerName="Dos";TEST.ctx.partnerName="uno-forever"
        TEST.level=10;TEST.ctx.partnerLevel=12
        TEST.class="PRIEST";TEST.ctx.partnerClass="WARRIOR"
        TEST.race="NightElf";TEST.ctx.partnerRace="Human"
        NS.char.progress.current.cursor=2;TEST.ctx.cursor=5
        Both(202,1,3);TEST.objectives[202]={{numFulfilled=2,numRequired=5,finished=false}}
        NS.DuoPlanner:Invalidate()
        local right=NS.DuoPlanner:GetAutomaticPlan()
        assert(left.guideID==right.guideID and left.referenceName==right.referenceName)
        assert(left.referenceCursor==right.referenceCursor and right.sharedCursor==2)
        assert(right.ownCursor==2 and right.partnerCursor==5)
        ''')

    def test_waypoint_never_uses_our_completed_quests_live_handoff(self):
        self.check('''
        function NS:GetGoalWaypoint(goal)
          if goal.quest or goal.questID then return {mapID=1429,x=.99,y=.99} end
          return {mapID=goal.map,x=goal.x/100,y=goal.y/100}
        end
        local point=NS.DuoPlanner:GetSharedWaypoint("current",2)
        assert(point and point.x==.25 and point.y==.35)
        ''')

    def test_automatic_scan_bounds_remote_requests_and_retains_five_second_cache(self):
        self.check('''
        for i=1,30 do AddGuide("extra"..i,1000+i) end
        local first=NS.DuoPlanner:GetAutomaticPlan();local requests=#TEST.requests
        assert(requests<=12)
        assert(NS.DuoPlanner:GetAutomaticPlan()==first and #TEST.requests==requests)
        ''')


if __name__ == "__main__":
    unittest.main()
