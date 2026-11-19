"""Check actual navigation and journal transitions for reviewed goal types."""
import unittest

from test_quest_engine import ADDON, QuestEngineHost
from test_access_navigation import WORLD_STUBS


class HillsbradRequestTests(unittest.TestCase):
    chapter = "forever/alliance/30-40/01-hillsbrad-foothills"

    def setUp(self):
        self.h = h = QuestEngineHost(catalog=True)
        for module in ("GuideMigrations", "TrackerPreview", "Navigation"):
            h.load((ADDON / (module + ".lua")).read_text(encoding="utf8"), "RutaXP", h.ns)
        h.globals.ACCESS_NS = h.ns
        h.lua.execute(WORLD_STUBS)
        h.ns.UpdateNavigation = None
        h.state.level = 32
        h.initialize()
        h.call("SelectGuide", self.chapter)
        self.guide, _, self.progress = h.call("GetCurrent")
        self.work, self.turnin = (next(si for si, step in self.guide.steps.items() for goal in step.goals.values()
                                       if goal.quest == 98059 and goal.t == action) for action in ("use", "turnin"))
        h.quest(98059, onQuest=True, complete=False)
        h.quest(562, onQuest=True, complete=True)

    def test_old_arrival_and_cursor_at_captain_recover_table_and_tracker_until_credited(self):
        h, state = self.h, self.progress
        state.routeRevision, state.cursor = 7, self.turnin
        state.confirmed[f"{self.work}:1"] = True  # A manual service confirmation in the old guide.
        h.call("MigrateGuideProgress")
        h.call("Sync")
        self.assertEqual(state.routeRevision, self.guide.routeRevision)
        self.assertEqual(state.cursor, self.work)
        step = self.guide.steps[self.work]
        active = h.active()[0]
        self.assertEqual((active.t, active.quest, active.item), ("use", 98059, 279386))
        pin = h.call("GetBaseStepWaypoint", step)
        self.assertEqual(pin.mapID, 1424)
        self.assertAlmostEqual(pin.x, .297)
        self.assertAlmostEqual(pin.y, .416)
        rows, _ = h.call("GetStepGoalItems", step)
        self.assertTrue(rows[1].isCurrent)
        self.assertIn("Solicitud sellada", rows[1].title)
        self.assertIn("/use item:279386", rows[1].subtitle)
        h.ns.IsAtWaypoint = h.lua.eval("function() return true end")
        h.call("OnNavigationTick")
        self.assertEqual(state.cursor, self.work)
        h.quest(98059, onQuest=True, complete=True)
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(state.cursor, self.turnin)
        self.assertEqual(h.active()[0].npc, 251493)
        pin = h.call("GetBaseStepWaypoint", self.guide.steps[self.turnin])
        self.assertAlmostEqual(pin.x, .4647)
        self.assertAlmostEqual(pin.y, .5013)
        h.fire("QUEST_TURNED_IN", 98059)
        self.assertEqual(h.active()[0].quest, 562)

    def test_missing_login_credit_waits_for_a_readable_journal(self):
        h, state = self.h, self.progress
        state.cursor = self.turnin
        h.globals.C_QuestLog.IsComplete = None
        h.call("Sync")
        self.assertEqual(state.cursor, self.turnin)
        self.assertEqual(h.active()[2], "blocked")
        self.assertIsNone(h.call("GetBaseStepWaypoint", self.guide.steps[self.turnin]))
        h.quest(98059, onQuest=True, objectives=[{"finished": False}])
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(state.cursor, self.work)

    def test_skip_keeps_other_handins_and_real_credit_can_unlock_the_captain_later(self):
        h, state = self.h, self.progress
        state.cursor = self.work
        h.call("SkipStep")
        h.call("Sync")
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(state.cursor, self.turnin)
        self.assertEqual(h.active()[0].quest, 562)
        self.assertEqual(h.status(self.guide.steps[self.turnin].goals[1]), "skip")
        h.quest(98059, onQuest=True, complete=False, objectives=[{"finished": True}])
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual((state.cursor, h.active()[0].npc), (self.turnin, 251493))

    def test_revision_six_rejoins_from_the_former_coast_return_step(self):
        h, state = self.h, self.progress
        state.routeRevision, state.cursor = 6, 33
        h.call("MigrateGuideProgress")
        h.call("Sync")
        self.assertEqual((state.cursor, h.active()[0].item), (self.work, 279386))

    def test_manual_progress_and_a_paused_duo_keep_the_saved_step(self):
        h, state = self.h, self.progress
        state.cursor, h.ns.char.auto = self.turnin, False
        h.call("Sync")
        self.assertEqual(state.cursor, self.turnin)
        self.assertIn(f"paso {self.work}", h.active()[3])
        h.ns.char.auto = True
        h.ns.DuoAuto = h.lua.eval("{ ShouldPauseAutomation=function() return true end }")
        h.call("Sync")
        self.assertEqual(state.cursor, self.turnin)
        h.ns.DuoAuto, h.ns.char.auto = None, False
        h.call("Previous")
        self.assertEqual((state.cursor, h.active()[0].item), (self.work, 279386))

    def test_character_with_no_request_or_finished_chapter_does_not_travel_back(self):
        h, state = self.h, self.progress
        h.quest(98059, onQuest=False)
        state.cursor = self.turnin
        h.call("Sync")
        self.assertEqual(state.cursor, self.turnin)
        self.assertIsNone(h.call("GetBaseStepWaypoint", self.guide.steps[self.turnin]))
        state.cursor, h.ns.char.auto = len(self.guide.steps) + 1, False
        h.quest(98059, onQuest=True, complete=False)
        h.call("Sync")
        self.assertEqual(state.cursor, len(self.guide.steps) + 1)


class ReviewedRouteRuntimeTests(unittest.TestCase):
    def host(self, goals):
        h = QuestEngineHost()
        for module in ("TrackerPreview", "Navigation"):
            h.load((ADDON / (module + ".lua")).read_text(encoding="utf8"), "RutaXP", h.ns)
        h.ns.UpdateNavigation = None
        guide = h.group(goals, next_goals=[{"t": "accept", "quest": 1234}])
        h.quest(98059, onQuest=True, complete=False)
        h.initialize()
        return h, guide

    def test_town_hall_waits_for_the_request_instead_of_arrival_or_travel_confirmation(self):
        h, guide = self.host([{"t":"goto","workForQuest":98059,
                               "waypoint":{"mapID":1424,"x":.297,"y":.416}}])
        h.lua.execute("function ready() return true end")
        h.ns.IsTravelServiceComplete = h.globals.ready
        h.ns.IsAtWaypoint = h.globals.ready
        self.assertEqual(h.active()[0].workForQuest, 98059)
        self.assertEqual(h.call("GetBaseStepWaypoint", guide.steps[1]).mapID, 1424)
        h.call("OnNavigationTick")
        self.assertEqual(h.cursor("grouped"), 1)
        h.quest(98059, onQuest=True, complete=True)
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(h.cursor("grouped"), 2)

    def test_per_objective_and_inactive_auxiliary_rows(self):
        h, guide = self.host([{"t":"accept","quest":9}, {"t":"note","workForQuest":5163,"workForObjective":1},
                              {"t":"use","workForQuest":5163,"workForObjective":2}])
        step = guide.steps[1]
        self.assertEqual(h.status(step.goals[2]), "skip")
        visible, _ = h.call("GetStepGoalItems",step)
        self.assertFalse(any(r.goal and r.goal.workForQuest for r in visible.values()))
        h.quest(5163, onQuest=True, complete=False, objectives=[{"finished":False},{"finished":False}])
        self.assertEqual(h.status(step.goals[2]), "active")
        h.quest(5163, onQuest=True, complete=False, objectives=[{"finished":True},{"finished":False}])
        self.assertEqual(h.status(step.goals[2]), "done")
        self.assertEqual(h.status(step.goals[3]), "active")

    def test_hunt_waypoint_expires_but_other_actions_in_the_step_survive(self):
        h, guide = self.host([{"t":"goto","untilLevel":48}, {"t":"accept","quest":11, "levelingDetour":True,"detourBelowLevel":48}])
        h.state.level = 47
        self.assertEqual(h.status(guide.steps[1].goals[1]), "active")
        self.assertEqual(h.status(guide.steps[1].goals[2]), "skip")
        h.state.level = 48
        self.assertEqual(h.status(guide.steps[1].goals[1]), "done")
        self.assertEqual(h.active()[0].quest, 11)

    def test_group_crater_is_a_visit_and_each_visit_can_finish_on_arrival(self):
        h, guide = self.host([{"t":"accept","quest":9}, {"t":"goto","workForQuest":5156,"workVisit":True}])
        h.load((ADDON / "GroupQuestData.lua").read_text(encoding="utf8"), "RutaXP", h.ns)
        h.quest(5156, onQuest=True, complete=False)
        row = guide.steps[1].goals[2]
        self.assertEqual(h.status(row), "skip")
        h.ns.char.includeGroupQuests = True
        self.assertEqual(h.status(row), "active")
        h.ns.IsAtWaypoint = h.lua.eval("function() return true end")
        self.assertEqual(h.status(row), "done")

    def test_a_solo_horde_player_at_a_contact_can_deliver_before_another_npc(self):
        h = QuestEngineHost()
        ident = "forever/horde/04-the-barrens"
        h.group([{"t":"accept","quest":60,"npc":100}, {"t":"turnin","quest":61,"npc":200}], id=ident)
        h.state.raceToken, h.state.classToken = "Troll", "SHAMAN"
        h.quest(61, onQuest=True, complete=True)
        h.lua.execute("function UnitGUID(unit) if unit=='npc' then return 'Creature-0-1-2-3-200-0000000001' end end")
        h.initialize()
        self.assertEqual(h.active()[0].quest, 61)
        h.lua.execute("function IsInGroup() return true end")
        self.assertEqual(h.active()[0].quest, 60)
