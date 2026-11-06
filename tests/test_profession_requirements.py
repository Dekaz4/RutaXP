"""Profession eligibility is local evidence, never inferred from a partner's journal."""
import unittest

from test_quest_engine import QuestEngineHost
from test_recovery import RecoveryHost
from test_duo import DuoHost
from test_auto_party_integration import AutomaticPartyHost, ROUTE_ID, QUEST_ID
from test_duo_journey import primitive_copy
import test_duo_planner as planner_fixture


SKILL = {"profLine": 202, "profRank": 1, "profName": "Engineering"}
SKILL_API = r"""
TEST.skills = TEST.skills or {}
TEST.skillReads = 0
C_SkillInfo = {GetSkillLineInfoByID=function(id)
    TEST.skillReads=TEST.skillReads+1
    local rank=TEST.skills[id]
    if rank==nil then return {rank=0,maxRank=0} end
    return {skillID=id,rank=rank,maxRank=300}
end}
"""


class ProfessionRequirementTests(unittest.TestCase):
    def host(self, rank=0, api=True):
        h = QuestEngineHost()
        h.guide("skill", steps=[
            {"title": "Accept", "goals": [{"t": "accept", "quest": 100, **SKILL}]},
            {"title": "Work", "goals": [{"t": "collect", "quest": 100, "oi": 1}]},
            {"title": "Return", "goals": [{"t": "turnin", "quest": 100}]},
            {"title": "Common", "goals": [{"t": "accept", "quest": 101}]},
        ])
        if api:
            h.lua.execute(SKILL_API)
            h.state.skills[202] = rank
        h.initialize()
        return h

    def test_missing_profession_skips_whole_unaccepted_chain_without_marking_quests_done(self):
        h = self.host()
        self.assertEqual(h.call("GetProgress", "skill").cursor, 4)
        for index in (1, 2, 3):
            step = h.ns.guides.skill.steps[index]
            self.assertEqual(h.status(step.goals[1], step), "skip")
        self.assertFalse(h.call("IsQuestActive", 100))
        self.assertFalse(h.call("IsQuestDelivered", 100))
        self.assertIsNone(h.call("GetProgress", "skill").skipped)
        self.assertLessEqual(h.state.skillReads, 1)

    def test_unknown_api_blocks_instead_of_fabricating_absence(self):
        h = self.host(api=False)
        self.assertEqual(h.call("GetProgress", "skill").cursor, 1)
        goal, _, status, reason = h.active()
        self.assertEqual(status, "blocked")
        self.assertIn("comprobar Ingeniería", reason)
        self.assertEqual(goal.quest, 100)
        self.assertFalse(h.call("WantsQuest", "accept", 100))

    def test_rank_and_existing_profession_fields_are_normalized(self):
        h = self.host(rank=74)
        goal = h.ns.guides.skill.steps[1].goals[1]
        goal.profRank = 75
        self.assertEqual(h.call("CheckGoalProfession", goal), (False, "Requiere Ingeniería (75)"))
        h.state.skills[202] = 75
        h.call("InvalidateProfessionRequirements")
        self.assertTrue(h.call("CheckGoalProfession", goal))
        alias = h.table({"t": "accept", "quest": 102, "requiresSkill": {"id": 202, "rank": 75}})
        self.assertTrue(h.call("CheckGoalProfession", alias))
        self.assertEqual(h.call("GetGoalProfessionRequirement", alias).name, "Ingeniería")

    def test_current_journal_and_delivery_override_lost_profession(self):
        h = self.host()
        state = h.call("GetProgress", "skill")
        state.cursor = 2
        h.quest(100, onQuest=True, objectives=[{"finished": False, "numFulfilled": 0, "numRequired": 3}])
        self.assertEqual(h.active()[2], "active")
        self.assertTrue(h.call("CheckGoalProfession", h.ns.guides.skill.steps[1].goals[1]))
        h.quest(100, onQuest=True, complete=True)
        self.assertEqual(h.status(h.ns.guides.skill.steps[2].goals[1], h.ns.guides.skill.steps[2]), "done")
        h.quest(100, delivered=True)
        self.assertEqual(h.status(h.ns.guides.skill.steps[3].goals[1], h.ns.guides.skill.steps[3]), "done")

    def test_sparse_profession_slots_use_skill_ids_and_complete_enumeration_for_absence(self):
        h = self.host(api=False)
        h.lua.execute("""
            function GetProfessions() return nil,42,nil,nil,17 end
            function GetProfessionInfo(slot)
                if slot==42 then return 'Ingeniería',nil,50,75,nil,nil,202 end
                return 'Cocina',nil,30,75,nil,nil,185
            end
        """)
        h.call("InvalidateProfessionRequirements")
        self.assertEqual(h.call("GetProfessionRank", 202), 50)
        self.assertEqual(h.call("GetProfessionRank", 333), 0)
        h.lua.execute("function GetProfessionInfo() error('unreadable') end")
        h.call("InvalidateProfessionRequirements")
        self.assertIsNone(h.call("GetProfessionRank", 202))

    def test_collapsed_skills_and_secret_fields_are_unknown(self):
        h = self.host(api=False)
        h.lua.execute("""
            C_SkillInfo={GetNumSkillLines=function() return 1 end,
              GetSkillLineInfo=function() return {isHeader=true,isExpanded=false} end}
        """)
        h.call("InvalidateProfessionRequirements")
        self.assertIsNone(h.call("GetProfessionRank", 202))
        h.lua.execute("""
            local secret={}
            function issecretvalue(v) return v==secret end
            C_SkillInfo.GetSkillLineInfoByID=function() return {rank=secret,maxRank=300} end
        """)
        h.call("InvalidateProfessionRequirements")
        self.assertIsNone(h.call("GetProfessionRank", 202))

    def test_unbound_inventory_gate_does_not_gate_learning_a_skill(self):
        h = self.host()
        collect = h.table({"t": "collect", "item": 255155, **SKILL})
        self.assertEqual(h.status(collect), "skip")
        train = h.table({"t": "train", "skill": 202})
        self.assertEqual(h.status(train), "manual")

    def test_recovery_never_sends_a_non_engineer_into_required_profession_chain(self):
        for rank, expected in ((0, False), (1, True)):
            with self.subTest(rank=rank):
                h = RecoveryHost()
                h.load_recovery()
                h.group([{"t": "accept", "quest": 900, "preAll": [100]}], id="main")
                h.source([100], prereqs={100: SKILL})
                h.lua.execute(SKILL_API)
                h.state.skills[202] = rank
                h.ready()
                blocker = h.blockers()[1]
                self.assertEqual(blocker.plan is not None, expected)
                if not expected:
                    self.assertIn("Ingeniería", blocker.reason)
                    self.assertFalse(h.start()[0])
                    self.assertEqual(h.ns.char.activeGuide, "main")

    def test_recovery_keeps_work_for_an_already_active_profession_quest(self):
        h = RecoveryHost()
        h.load_recovery()
        h.group([{"t": "accept", "quest": 900, "preAll": [100]}], id="main")
        h.source([100], prereqs={100: SKILL})
        h.quest(100, onQuest=True)
        h.lua.execute(SKILL_API)
        h.ready()
        self.assertIsNotNone(h.blockers()[1].plan)
        self.assertEqual(h.blockers()[1].plan.steps[1].goals[1].t, "kill")

    def test_unknown_target_profession_does_not_offer_unrelated_prerequisite_recovery(self):
        h = RecoveryHost()
        h.load_recovery()
        h.group([{"t": "accept", "quest": 900, "preAll": [100], **SKILL}], id="main")
        h.source([100])
        h.ready()
        blocker = h.blockers()[1]
        self.assertIsNone(blocker.plan)
        self.assertIn("comprobar Ingeniería", blocker.reason)


class ProfessionDuoTests(unittest.TestCase):
    def test_automatic_pair_handles_personal_engineering_and_rejoins_shared_delivery(self):
        a = AutomaticPartyHost(cursor=1, auto=False, review=False)
        b = AutomaticPartyHost("Dos", "Uno", cursor=1, auto=False, review=False)
        for host, rank in ((a, 10), (b, 0)):
            host.h.lua.execute(SKILL_API)
            host.s.skills[202] = rank
            host.ns.guides[ROUTE_ID].steps = host.h.table([
                {"title": "Common work", "goals": [{"t": "complete", "quest": QUEST_ID, "oi": 1}]},
                {"title": "Engineering acceptance", "goals": [{"t": "accept", "quest": 100, **SKILL}]},
                {"title": "Engineering work", "goals": [{"t": "complete", "quest": 100, "oi": 1, **SKILL}]},
                {"title": "Engineering delivery", "goals": [{"t": "turnin", "quest": 100, **SKILL}]},
                {"title": "Common delivery", "goals": [{"t": "turnin", "quest": QUEST_ID}]},
            ])
            host.ns.DuoPlanner.catalog = None
            host.roster()

        def exchange(ticks=40):
            for _ in range(ticks):
                a.tick(); b.tick(); a.deliver(b); b.deliver(a)

        exchange(75)
        self.assertTrue(a.status().active)
        self.assertTrue(b.status().active)
        for host in (a, b):
            host.quest(count=8)
            host.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        exchange()
        self.assertEqual(a.ns.char.progress[ROUTE_ID].cursor, 2)
        self.assertEqual(b.ns.char.progress[ROUTE_ID].cursor, 5)
        self.assertFalse(a.ns.DuoAuto.ShouldPauseAutomation(a.ns.DuoAuto))
        a.s.quests[100] = a.h.table({"onQuest": True, "complete": False, "objectives": [
            {"numFulfilled": 0, "numRequired": 3, "finished": False}]})
        a.h.g.EmitAddonEvent("QUEST_ACCEPTED", 100)
        exchange()
        self.assertEqual(a.ns.char.progress[ROUTE_ID].cursor, 3)
        a.s.quests[100].complete = True
        a.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        exchange()
        self.assertEqual(a.ns.char.progress[ROUTE_ID].cursor, 4)
        a.s.quests[100].onQuest, a.s.quests[100].delivered = False, True
        a.h.g.EmitAddonEvent("QUEST_TURNED_IN", 100)
        exchange()
        self.assertEqual(a.ns.char.progress[ROUTE_ID].cursor, 5)
        self.assertEqual(b.ns.char.progress[ROUTE_ID].cursor, 5)
        self.assertTrue(a.status().active)
        self.assertTrue(b.status().active)
        self.assertFalse(b.ns.IsQuestActive(b.ns, 100))
        self.assertFalse(b.ns.IsQuestDelivered(b.ns, 100))
        self.assertFalse(a.ns.IsQuestDelivered(a.ns, QUEST_ID))
        self.assertFalse(b.ns.IsQuestDelivered(b.ns, QUEST_ID))

    def test_manual_duo_waits_for_common_quest_but_not_partners_profession(self):
        goals = [{"t": "accept", "quest": 100, **SKILL}, {"t": "accept", "quest": 200}]
        a, b = DuoHost(goals=goals), DuoHost("Dos", "Uno", goals=goals)
        for host in (a, b):
            host.ns.char.auto = False
            host.lua.execute(SKILL_API)
            host.dcall("SetWait", True)
        a.state.skills[202] = 10
        a.quest(100, onQuest=True)
        a.quest(200, onQuest=True)
        for _ in range(15):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        step = a.ns.guides['forever/alliance/test'].steps[1]
        wait = a.dcall("GetStepWaitStatus", step)
        self.assertTrue(wait.waiting)
        self.assertEqual(wait.questID, 200)
        b.quest(200, onQuest=True)
        for _ in range(15):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        self.assertFalse(a.dcall("GetStepWaitStatus", step).waiting)
        self.assertFalse(b.call("IsQuestActive", 100))
        self.assertFalse(b.call("IsQuestDelivered", 100))

    def test_skill_event_refreshes_eligibility_and_preserves_saved_progress(self):
        host = AutomaticPartyHost(cursor=1, auto=False, review=False)
        goal = host.ns.guides[ROUTE_ID].steps[1].goals[1]
        goal.profLine, goal.profRank = 202, 1
        host.h.lua.execute(SKILL_API)
        host.s.quests[QUEST_ID].onQuest = False
        self.assertEqual(host.ns.CheckGoalProfession(host.ns, goal)[0], False)
        before = primitive_copy(host.ns.char.progress)
        host.s.skills[202] = 1
        host.h.g.EmitAddonEvent("SKILL_LINES_CHANGED")
        self.assertTrue(host.ns.CheckGoalProfession(host.ns, goal))
        self.assertEqual(primitive_copy(host.ns.char.progress), before)


class ActiveParentRequirementTests(unittest.TestCase):
    def test_trivial_skip_preserves_parent_needed_by_chapters(self):
        h = QuestEngineHost()
        h.state.level = 30
        h.group([{"t": "accept", "quest": 338, "qlvl": 1}], id="parent")
        h.group([{"t": "accept", "quest": 339, "parent": 338}], id="chapter")
        h.initialize()
        h.ns.char.skipTrivial = True
        h.call("SelectGuide", "parent")
        self.assertEqual(h.active()[2], "active")

    def test_active_parent_allows_chapter_but_delivered_parent_is_not_enough(self):
        h = QuestEngineHost()
        h.group([{"t": "accept", "quest": 339, "parent": 338}], id="chapter")
        h.initialize()
        goal = h.ns.guides.chapter.steps[1].goals[1]
        self.assertEqual(h.status(goal), "blocked")
        h.quest(338, delivered=True)
        self.assertEqual(h.status(goal), "blocked")
        h.quest(338, onQuest=True, delivered=False)
        self.assertEqual(h.status(goal), "active")
        h.quest(338, onQuest=True, complete=True)
        self.assertEqual(h.status(goal), "active")
        h.quest(338, onQuest=False, delivered=True)
        h.quest(339, onQuest=True)
        self.assertEqual(h.status(goal), "done")

    def test_recovery_explains_parent_pickup_without_delivering_it_or_creating_cycle(self):
        h = RecoveryHost()
        h.load_recovery()
        h.group([{"t": "accept", "quest": 339, "parent": 338}], id="main")
        h.source([338], prereqs={338: {"preAll": [339]}})
        h.ready()
        blocker = h.blockers()[1]
        self.assertIsNone(blocker.plan)
        self.assertEqual(list(blocker.missingQuestIDs.values()), [338])
        self.assertIn("Acepta primero", blocker.reason)
        self.assertIn("Giver 338", blocker.reason)
        self.assertNotIn("ciclo", blocker.reason)
        self.assertFalse(h.start()[0])
        h.quest(338, onQuest=True)
        self.assertEqual(len(h.blockers()), 0)

    def test_duo_observes_parent_on_each_player_and_never_proposes_its_delivery(self):
        lua = planner_fixture.LuaRuntime(unpack_returned_tuples=True)
        lua.execute(planner_fixture.STUBS)
        loader = lua.execute("return function(...)\n" +
                             (planner_fixture.ROOT / "RutaXP" / "DuoPlanner.lua").read_text(encoding="utf-8") +
                             "\nend")
        loader("RutaXP", lua.globals().NS)
        lua.execute('''
            NS.guides.current.steps[1].goals[1].parent=338
            Both(338,1,1)
            assert(#NS.DuoPlanner:GetCommonRoutes()==1)
            Both(338,2,2);NS.DuoPlanner:Invalidate()
            assert(#NS.DuoPlanner:GetCommonRoutes()==1)
            Both(338,3,1);NS.DuoPlanner:Invalidate()
            assert(#NS.DuoPlanner:GetCommonRoutes()==0)
            Both(101,0,1)
            AddGuide("parent",338)
            local d=NS.DuoPlanner:GetDifferences()[1]
            assert(d.text:find("Acepta primero",1,true) and not d.recoveryPossible)
            assert(not d.action)
            NS.guides.parent=nil;table.remove(NS.order)
            Both(338,1,3);NS.DuoPlanner:Invalidate()
            Both(101,0,0)
            assert(#NS.DuoPlanner:GetCommonRoutes()==0)
            TEST.partner[338]=nil;NS.DuoPlanner:Invalidate()
            assert(#NS.DuoPlanner:GetCommonRoutes()==0)
        ''')


if __name__ == '__main__':
    unittest.main()
