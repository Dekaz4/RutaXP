"""Check actual navigation and journal transitions for reviewed goal types."""
import unittest

from test_quest_engine import ADDON, QuestEngineHost


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
