"""Exercise the NPC menus, offer window and reward window used on Forever."""
import unittest

from test_quest_engine import ADDON, QuestEngineHost


ELWYNN = "forever/alliance/human/01-elwynn-forest"
WESTFALL = "forever/alliance/02-westfall"


class EarlyQuestAutomationTests(unittest.TestCase):
    def setUp(self):
        h = self.h = QuestEngineHost(catalog=True)
        for name in ("EarlyQuestData.lua", "QuestOfferAdvice.lua", "QuestVisitTurnin.lua"):
            h.load((ADDON / name).read_text(encoding="utf8"), "RutaXP", h.ns)
        h.state.classToken, h.state.level = "ROGUE", 10
        h.initialize()
        h.call("SelectGuide", ELWYNN)
        h.ns.char.progress[ELWYNN].cursor = 37
        h.ns.char.auto = True
        h.lua.execute("""
            TEST.used, TEST.offers, TEST.npc = 15, {109}, 261
            function C_QuestLog.GetMaxNumQuestsCanAccept() return 40 end
            function C_QuestLog.GetNumQuestLogEntries() return 0, TEST.used end
            function UnitGUID(unit)
                if unit == "npc" then return "Creature-0-1-2-3-"..TEST.npc.."-ABC" end
            end
            function GetNumAvailableQuests() return #TEST.offers end
            function GetAvailableQuestInfo(i) return false, 1, false, false, TEST.offers[i] end
            function SelectAvailableQuest(i) TEST.selected = TEST.offers[i] end
            C_GossipInfo = {
                GetAvailableQuests = function()
                    local out = {}
                    for _, id in ipairs(TEST.offers) do out[#out+1] = {questID=id} end
                    return out
                end,
                SelectAvailableQuest = function(id) TEST.selected = id end
            }
            function GetQuestID() return TEST.selected end
            function AcceptQuest() TEST.accepted = TEST.selected end
            function IsShiftKeyDown() return TEST.shift end
            function QuestFlagsPVP() return TEST.pvp end
        """)

    def automate(self, event):
        self.h.call("HandleQuestAutomation", event)

    def test_thomas_offers_gryan_in_both_menu_types_and_accepts_the_actual_detail(self):
        h = self.h
        for event in ("GOSSIP_SHOW", "QUEST_GREETING"):
            h.state.selected, h.state.accepted = None, None
            self.automate(event)
            self.assertEqual(h.state.selected, 109)
            self.automate("QUEST_DETAIL")
            self.assertEqual(h.state.accepted, 109)
        self.assertEqual(h.ns.char.progress[ELWYNN].cursor, 37)

    def test_current_pickup_goes_first_and_manual_safeguards_still_work(self):
        h = self.h
        h.state.offers = h.table([109, 52])
        for event in ("GOSSIP_SHOW", "QUEST_GREETING"):
            self.automate(event)
            self.assertEqual(h.state.selected, 52)
        h.state.selected = 109
        for key in ("shift", "pvp"):
            h.state[key] = True
            self.automate("QUEST_DETAIL")
            self.assertIsNone(h.state.accepted)
            h.state[key] = False
        h.ns.char.auto = False
        self.automate("QUEST_DETAIL")
        self.assertIsNone(h.state.accepted)

    def test_same_visit_accepts_remaining_route_offer_when_game_redisplays_thomas(self):
        h = self.h
        h.state.offers = h.table([109, 52])
        for expected in (52, 109):
            self.automate("GOSSIP_SHOW")
            self.assertEqual(h.state.selected, expected)
            self.automate("QUEST_DETAIL")
            self.assertEqual(h.state.accepted, expected)
            h.quest(expected, onQuest=True, complete=False)
            h.state.accepted, h.state.selected = None, None
        self.automate("GOSSIP_SHOW")
        self.assertIsNone(h.state.selected)
        self.assertEqual(h.ns.char.progress[ELWYNN].cursor, 37)

    def test_pick_up_furlbrow_quests_while_the_arrow_points_to_sentinel_hill(self):
        for guide, cursor in ((ELWYNN, 72), (WESTFALL, 1)):
            h = self.h
            h.call("SelectGuide", guide)
            h.ns.char.progress[guide].cursor = cursor
            h.state.level = 12
            for quest in (64, 36, 151):
                h.quest(quest, onQuest=False)
            for npc, offers in ((237, [64]), (238, [36, 151])):
                h.state.npc = npc
                h.state.offers = h.table(offers)
                for i, quest in enumerate(offers):
                    with self.subTest(guide=guide, quest=quest):
                        h.state.selected, h.state.accepted = None, None
                        self.automate("GOSSIP_SHOW" if i == 0 else "QUEST_GREETING")
                        self.assertEqual(h.state.selected, quest)
                        self.automate("QUEST_DETAIL")
                        self.assertEqual(h.state.accepted, quest)
                        h.quest(quest, onQuest=True)
            self.assertEqual(h.ns.char.progress[guide].cursor, cursor)
        h.ns.char.progress[WESTFALL].cursor = 3
        step = h.ns.guides[WESTFALL].steps[3]
        state = h.ns.char.progress[WESTFALL]
        for index in (1, 2, 3):
            self.assertEqual(h.call("GetGoalStatus", step.goals[index], step, state, index)[0], "done")
        self.assertNotEqual(h.call("GetGoalStatus", step.goals[7], step, state, 7)[0], "done")
        h.quest(184, delivered=True)  # The screenshot shows the deed already turned in.
        h.quest(92742, onQuest=True)
        next_goal = h.call("GetActiveGoal", step, state)[0]
        self.assertEqual((next_goal.t, next_goal.quest), ("collect", 92742))

    def test_space_uses_quest_count_and_keeps_the_last_slot_for_the_current_step(self):
        h = self.h
        for used, allowed in [(38, True), (39, False), (40, False), (None, False)]:
            h.state.used, h.state.selected, h.state.accepted = used, 109, None
            self.assertEqual(h.call("GetEarlyQuestSpace"), allowed)
            self.automate("QUEST_DETAIL")
            self.assertEqual(h.state.accepted, 109 if allowed else None)
        h.state.used, h.state.selected = 39, 52
        self.automate("QUEST_DETAIL")
        self.assertEqual(h.state.accepted, 52)
        h.lua.execute("""
            C_QuestLog.GetNumQuestLogEntries = nil
            C_QuestLog.GetMaxNumQuestsCanAccept = nil
            MAX_QUESTLOG_QUESTS = 25
            function GetNumQuestLogEntries() return 0, 20 end
        """)
        self.assertTrue(h.call("GetEarlyQuestSpace"))

    def test_give_gryan_the_courier_on_first_visit_and_leave_multiple_rewards_to_player(self):
        h = self.h
        h.call("SelectGuide", WESTFALL)
        h.ns.char.progress[WESTFALL].cursor = 1
        h.quest(109, onQuest=True, complete=True)
        h.state.npc = 234
        h.lua.execute("""
            function GetNumActiveQuests() return 1 end
            function GetActiveTitle(i) return "Habla con Gryan Mantorrecio", true end
            function GetActiveQuestID(i) return 109 end
            function SelectActiveQuest(i) TEST.selected = 109 end
            function IsQuestCompletable() return true end
            function CompleteQuest() TEST.completed = TEST.selected end
            function GetNumQuestChoices() return TEST.choices end
            function GetQuestMoneyToGet() return 0 end
            function GetQuestReward(choice) TEST.rewarded = choice end
        """)
        self.automate("QUEST_GREETING")
        self.assertEqual(h.state.selected, 109)
        self.automate("QUEST_PROGRESS")
        self.assertEqual(h.state.completed, 109)
        h.state.choices = 2
        self.automate("QUEST_COMPLETE")
        self.assertIsNone(h.state.rewarded)
        h.state.choices = 0
        self.automate("QUEST_COMPLETE")
        self.assertEqual(h.state.rewarded, 0)
        self.assertEqual(h.ns.char.progress[WESTFALL].cursor, 1)
