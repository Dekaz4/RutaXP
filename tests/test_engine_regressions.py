"""Regressions for route placement, bounded quest automation and service proof."""

import unittest

from test_quest_engine import QuestEngineHost


AUTOMATION = r"""
TEST.choices, TEST.cost, TEST.dialogQuestID = 1, 0, 501
TEST.accepted, TEST.completed, TEST.rewarded = 0, 0, nil
function GetQuestID() return TEST.dialogQuestID end
function AcceptQuest() TEST.accepted = TEST.accepted + 1 end
function IsQuestCompletable() return true end
function CompleteQuest() TEST.completed = TEST.completed + 1 end
function GetNumQuestChoices() return TEST.choices end
function GetQuestMoneyToGet() return TEST.cost end
function GetQuestReward(choice) TEST.rewarded = choice end
function GetNumActiveQuests() return #(TEST.activeDialog or {}) end
function GetActiveTitle(i) local q=TEST.activeDialog[i]; return q.title, q.complete end
function GetActiveQuestID(i) return TEST.activeDialog[i].id end
function SelectActiveQuest(i) TEST.selectedActive = i end
function GetNumAvailableQuests() return #(TEST.availableDialog or {}) end
function GetAvailableQuestInfo(i) return false, 0, false, false, TEST.availableDialog[i], false, false, 0 end
function SelectAvailableQuest(i) TEST.selectedAvailable = i end
"""


class PlacementRegressionTests(unittest.TestCase):
    def test_unrelated_delivery_does_not_jump_over_an_active_prerequisite(self):
        h = QuestEngineHost()
        h.guide("chain", status="beta", steps=[
            {"title": "Accept A", "goals": [{"t": "accept", "quest": 100}]},
            {"title": "Do A", "goals": [{"t": "complete", "quest": 100}]},
            {"title": "Deliver A", "goals": [{"t": "turnin", "quest": 100}]},
            {"title": "Independent B", "goals": [{"t": "turnin", "quest": 200}]},
            {"title": "Requires A", "goals": [{"t": "accept", "quest": 300, "preAll": [100]}]},
        ])
        h.quest(100, onQuest=True, complete=False)
        h.quest(200, delivered=True)
        h.initialize()
        self.assertEqual(h.cursor("chain"), 2)
        g = h.ns.guides.chain
        self.assertEqual(h.status(g.steps[5].goals[1], g.steps[5]), "blocked")

    def test_shipping_elwynn_preserves_fargodeep_work_after_bundle_of_trouble(self):
        h = QuestEngineHost(catalog=True)
        h.state.level, h.state.mapID = 10, 1429
        h.quest(62, onQuest=True, complete=False)
        h.quest(5545, delivered=True)
        h.initialize()
        guide = h.ns.guides["forever/alliance/human/01-elwynn-forest"]
        h.call("SelectGuide", guide.id)
        state = h.call("GetProgress", guide.id)
        state.cursor = 24
        h.call("PlaceInGuide", guide, state)
        self.assertEqual(state.cursor, 24)
        self.assertFalse(h.call("IsStepComplete", guide.steps[24], state))

    def test_zone_event_keeps_the_route_that_intentionally_visits_the_next_zone(self):
        h = QuestEngineHost(catalog=True)
        h.lua.execute(r"""
        TEST.frames = {}
        local create = CreateFrame
        function CreateFrame(...) local f=create(...); TEST.frames[#TEST.frames+1]=f; return f end
        """)
        h.new_namespace()
        h.state.faction, h.state.raceToken, h.state.classToken = "Horde", "Orc", "WARRIOR"
        h.state.level, h.state.mapID = 12, 1411
        h.quest(840, onQuest=True, complete=True)
        h.initialize()
        old = "forever/horde/orc-troll/01-durotar"
        h.call("SelectGuide", old)
        state = h.call("GetProgress", old)
        state.cursor, state.placed, state.review = 64, True, None
        h.state.mapID = 1413
        self.assertEqual(h.call("GetRecommendedGuide").id, "forever/horde/orc-troll/02-the-barrens")
        for _, frame in h.state.frames.items():
            if frame.events["ZONE_CHANGED_NEW_AREA"]:
                frame.scripts.OnEvent(frame, "ZONE_CHANGED_NEW_AREA")
        self.assertEqual(h.ns.char.activeGuide, old)
        self.assertEqual(state.cursor, 64)

    def test_grey_quest_is_not_skipped_by_default(self):
        h = QuestEngineHost()
        h.state.level = 60
        h.group([{"t": "accept", "quest": 100, "qlvl": 1}])
        h.initialize()
        self.assertEqual(h.active()[2], "active")

    def test_shipping_durotar_warrior_chain_continues_through_crossroads(self):
        h = QuestEngineHost(catalog=True)
        h.state.faction, h.state.raceToken, h.state.classToken = "Horde", "Orc", "WARRIOR"
        h.state.level, h.state.mapID = 12, 1413
        for qid in (840, 1505):
            h.quest(qid, onQuest=True, complete=True)
        h.initialize()
        guide_id = "forever/horde/orc-troll/01-durotar"
        h.call("SelectGuide", guide_id)
        state = h.call("GetProgress", guide_id)
        state.cursor, state.placed, state.review = 64, True, None
        for qid, event, fields, cursor in [
            (840, "QUEST_TURNED_IN", {"delivered": True}, 64),
            (842, "QUEST_ACCEPTED", {"onQuest": True}, 64),
            (1505, "QUEST_TURNED_IN", {"delivered": True}, 64),
            (1498, "QUEST_ACCEPTED", {"onQuest": True}, 65),
            (1498, "QUEST_LOG_UPDATE", {"onQuest": True, "complete": True}, 66),
            (1498, "QUEST_TURNED_IN", {"delivered": True}, 66),
            (1502, "QUEST_ACCEPTED", {"onQuest": True}, 67),
        ]:
            h.quest(qid, **fields)
            h.fire(event, qid)
            self.assertEqual(state.cursor, cursor)
            self.assertEqual(h.ns.char.activeGuide, guide_id)

    def test_opt_in_grey_policy_preserves_cross_guide_chains_and_class_quests(self):
        h = QuestEngineHost()
        h.state.level = 60
        h.group([{"t": "accept", "quest": 100, "qlvl": 1}], id="early")
        h.group([{"t": "accept", "quest": 200, "qlvl": 10, "preAll": [100]}], id="later")
        h.initialize()
        h.ns.char.skipTrivial = True
        h.call("SelectGuide", "early")
        self.assertEqual(h.active()[2], "active")
        self.assertEqual(h.status({"t": "accept", "quest": 400, "qlvl": 1,
                                   "only": {"classes": ["WARRIOR"]}}), "active")


class ManualSkipRegressionTests(unittest.TestCase):
    def test_skipping_a_quest_does_not_complete_it_or_unlock_its_followup(self):
        h = QuestEngineHost()
        h.group([{"t": "accept", "quest": 100}], next_goals=[
            {"t": "accept", "quest": 200, "preAll": [100]}
        ])
        h.initialize()
        h.call("Next")
        state = h.call("GetProgress", "grouped")
        self.assertTrue(state.skipped["1:1"])
        self.assertIsNone(state.confirmed["1:1"])
        self.assertFalse(h.call("IsQuestDelivered", 100))
        self.assertEqual(h.active()[2], "blocked")

    def test_missing_required_quest_is_blocked_after_skipping_its_accept(self):
        h = QuestEngineHost()
        h.group([{"t": "accept", "quest": 100}], next_goals=[{"t": "complete", "quest": 100}])
        h.initialize()
        h.call("Next")
        self.assertEqual(h.cursor("grouped"), 2)
        self.assertEqual(h.active()[2], "blocked")

    def test_legacy_quest_confirmation_is_an_omission_not_delivery(self):
        h = QuestEngineHost()
        h.group([{"t": "accept", "quest": 100}])
        h.initialize()
        state = h.call("GetProgress", "grouped")
        state.confirmed["1:1"] = True
        goal = h.ns.guides.grouped.steps[1].goals[1]
        self.assertEqual(h.status(goal), "skip")
        self.assertFalse(h.call("IsQuestDelivered", 100))
        self.assertTrue(state.confirmed["1:1"])
        h.quest(100, delivered=True)
        self.assertEqual(h.status(goal), "done")
        self.assertTrue(state.confirmed["1:1"])

    def test_toggling_officially_done_goal_does_not_create_a_fake_manual_override(self):
        h = QuestEngineHost()
        h.group([{"t": "turnin", "quest": 100}, {"t": "train"}])
        h.quest(100, delivered=True)
        h.initialize()
        h.call("ToggleGoalConfirm", 1)
        state = h.call("GetProgress", "grouped")
        self.assertIsNone(state.skipped["1:1"])
        self.assertIsNone(state.confirmed["1:1"])
        state.confirmed["1:1"], state.skipped["1:1"] = True, True
        h.call("ToggleGoalConfirm", 1)
        self.assertIsNone(state.skipped["1:1"])
        self.assertIsNone(state.confirmed["1:1"])
        self.assertTrue(h.call("IsQuestDelivered", 100))


class AutomationRegressionTests(unittest.TestCase):
    def host(self, goals, next_goals=None):
        h = QuestEngineHost()
        h.lua.execute(AUTOMATION)
        h.group(goals, next_goals=next_goals)
        return h

    def test_conditions_and_current_visit_bound_automatic_acceptance(self):
        h = self.host([
            {"t": "accept", "quest": 501, "optional": True},
            {"t": "accept", "quest": 502, "closedBy": [90]},
            {"t": "accept", "quest": 503, "minLevel": 20},
            {"t": "accept", "quest": 504, "preAll": [91]},
            {"t": "accept", "quest": 505},
        ], next_goals=[{"t": "accept", "quest": 999}])
        h.quest(90, delivered=True)
        h.initialize()
        for qid in (501, 502, 503, 504, 999):
            h.state.dialogQuestID = qid
            self.assertFalse(h.call("WantsQuest", "accept", qid))
            h.call("HandleQuestAutomation", "QUEST_DETAIL")
        self.assertEqual(h.state.accepted, 0)
        h.state.dialogQuestID = 505
        h.call("HandleQuestAutomation", "QUEST_DETAIL")
        self.assertEqual(h.state.accepted, 1)

    def test_review_pauses_accept_progress_and_reward(self):
        h = self.host([{"t": "accept", "quest": 501}, {"t": "turnin", "quest": 501}])
        h.initialize()
        h.call("GetProgress", "grouped").review = True
        for event in ("QUEST_DETAIL", "QUEST_PROGRESS", "QUEST_COMPLETE"):
            h.call("HandleQuestAutomation", event)
        self.assertEqual(h.state.accepted, 0)
        self.assertEqual(h.state.completed, 0)
        self.assertIsNone(h.state.rewarded)

    def test_unrelated_active_quest_is_never_automatically_delivered(self):
        h = self.host([{"t": "turnin", "quest": 501}])
        h.quest(501, onQuest=True, complete=True)
        h.quest(999, onQuest=True, complete=True)
        h.initialize()
        h.state.dialogQuestID = 999
        h.call("HandleQuestAutomation", "QUEST_PROGRESS")
        h.call("HandleQuestAutomation", "QUEST_COMPLETE")
        self.assertEqual(h.state.completed, 0)
        self.assertIsNone(h.state.rewarded)
        h.state.dialogQuestID = 501
        h.call("HandleQuestAutomation", "QUEST_PROGRESS")
        h.call("HandleQuestAutomation", "QUEST_COMPLETE")
        self.assertEqual(h.state.completed, 1)
        self.assertEqual(h.state.rewarded, 1)

    def test_classic_greeting_reads_the_second_return_and_filters_unrelated_quests(self):
        h = self.host([{"t": "turnin", "quest": 501}])
        h.quest(501, onQuest=True, complete=True)
        h.quest(999, onQuest=True, complete=True)
        h.initialize()
        h.state.activeDialog = h.table([
            {"id": 999, "title": "Unrelated", "complete": True},
            {"id": 501, "title": "Route", "complete": True},
        ])
        h.call("HandleQuestAutomation", "QUEST_GREETING")
        self.assertEqual(h.state.selectedActive, 2)

    def test_classic_greeting_reads_the_fifth_quest_info_return(self):
        h = self.host([{"t": "accept", "quest": 501}])
        h.initialize()
        h.state.availableDialog = h.table([999, 501])
        h.call("HandleQuestAutomation", "QUEST_GREETING")
        self.assertEqual(h.state.selectedAvailable, 2)

    def test_reward_choices_cost_and_unknown_metadata_stay_manual(self):
        h = self.host([{"t": "turnin", "quest": 501}])
        h.quest(501, onQuest=True, complete=True)
        h.initialize()
        for choices, cost in ((2, 0), (1, 100), (None, 0), (1, None)):
            h.state.choices, h.state.cost = choices, cost
            h.call("HandleQuestAutomation", "QUEST_COMPLETE")
            self.assertIsNone(h.state.rewarded)


class ServiceRegressionTests(unittest.TestCase):
    def service(self, goal):
        h = QuestEngineHost()
        h.group([goal], next_goals=[{"t": "note", "text": "Next"}])
        h.initialize()
        h.lua.execute(r"""
        TEST.npcID = 123
        function UnitGUID() return "Creature-0-1-0-1-"..TEST.npcID.."-0000000001" end
        """)
        return h

    def test_opening_trainer_or_merchant_does_not_finish_the_service(self):
        for action, event in (("train", "TRAINER_SHOW"), ("vendor", "MERCHANT_SHOW")):
            with self.subTest(action=action):
                h = self.service({"t": action, "npc": 123})
                h.call("ObserveService", event)
                h.call("Sync")
                self.assertEqual(h.cursor("grouped"), 1)
                self.assertEqual(h.active()[2], "manual")
                h.call("Next")
                self.assertEqual(h.cursor("grouped"), 2)

    def test_talk_requires_the_correct_npc(self):
        h = self.service({"t": "talk", "npc": 456})
        h.call("ObserveService", "GOSSIP_SHOW")
        self.assertEqual(h.active()[2], "manual")
        h.state.npcID = 456
        h.call("ObserveService", "GOSSIP_SHOW")
        self.assertEqual(h.status(h.ns.guides.grouped.steps[1].goals[1]), "done")

    def test_goal_text_and_service_proof_use_the_same_navigation_candidate(self):
        h = self.service({"t": "talk", "candidates": [
            {"npc": 123, "npcName": "Far NPC"}, {"npc": 456, "npcName": "Nearby NPC"}
        ]})
        h.ns.GetGoalWaypoint = h.lua.eval("function(self,goal) return {candidate=goal.candidates[2]} end")
        goal = h.ns.guides.grouped.steps[1].goals[1]
        self.assertIn("Nearby NPC", h.call("GetGoalTitle", goal))
        h.call("ObserveService", "GOSSIP_SHOW")
        self.assertEqual(h.active()[2], "manual")
        h.state.npcID = 456
        h.call("ObserveService", "GOSSIP_SHOW")
        self.assertEqual(h.status(goal), "done")

    def test_flight_path_requires_learning_at_the_matching_npc(self):
        h = self.service({"t": "getfp", "npc": 456})
        h.call("ObserveService", "TAXIMAP_OPENED")
        h.call("ObserveService", "NEW_TAXI_PATH")
        self.assertEqual(h.active()[2], "manual")
        h.state.npcID = 456
        h.call("ObserveService", "NEW_TAXI_PATH")
        self.assertEqual(h.status(h.ns.guides.grouped.steps[1].goals[1]), "done")

    def test_home_binding_at_a_different_inn_does_not_finish_the_goal(self):
        h = self.service({"t": "sethome", "npc": 456, "location": "Target inn"})
        h.lua.execute('function GetBindLocation() return TEST.bound or "Other inn" end')
        h.call("ObserveService", "HEARTHSTONE_BOUND")
        self.assertEqual(h.active()[2], "manual")
        h.state.bound = "Target inn"
        h.call("ObserveService", "HEARTHSTONE_BOUND")
        self.assertEqual(h.status(h.ns.guides.grouped.steps[1].goals[1]), "done")


if __name__ == "__main__":
    unittest.main()
