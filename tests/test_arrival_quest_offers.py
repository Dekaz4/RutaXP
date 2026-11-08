"""Collect an offered roadside quest without completing or skipping the incoming journey."""
import unittest

from test_westfall_travel import DWARF, GOLDSHIRE, WEST, WESTFALL_ENTRY, TravelHost, old_save


class ArrivalQuestTests(unittest.TestCase):
    def setUp(self):
        self.client = TravelHost(WESTFALL_ENTRY, old_save(WEST), race="Human", classes=("ROGUE", "HUNTER"))
        self.ns = self.client.ns
        self.state = self.client.s
        self.client.h.lua.execute("""
            TEST.contact, TEST.used, TEST.offer = 238, 18, 151
            local oldGUID = UnitGUID
            function UnitGUID(unit)
                if unit == "npc" then
                    if TEST.contact then return "Creature-0-1-2-3-" .. TEST.contact .. "-123" end
                elseif oldGUID then return oldGUID(unit) end
            end
            function C_QuestLog.GetMaxNumQuestsCanAccept() return 40 end
            function C_QuestLog.GetNumQuestLogEntries() return TEST.used, TEST.used end
            C_GossipInfo = {
                GetAvailableQuests = function() return {{questID=TEST.offer}} end,
                SelectAvailableQuest = function(id) TEST.selected = id end
            }
            function GetQuestID() return TEST.offer end
            function IsShiftKeyDown() return TEST.shift end
            function AcceptQuest()
                TEST.accepted = TEST.offer
                TEST.quests[TEST.offer] = {onQuest=true}
            end
        """)

    def offer(self, event="QUEST_DETAIL"):
        self.state.accepted = None
        self.client.h.g.EmitAddonEvent(event)
        return self.state.accepted

    def test_roadside_pickups_leave_actual_trip_and_pending_quest_objectives_in_place(self):
        self.assertEqual(self.client.travel().destination, WEST)
        before = self.client.progress()
        for npc, quest in ((237, 64), (238, 36), (238, 151)):
            with self.subTest(quest=quest):
                self.assertTrue(self.ns.earlyQuestOffers[quest])
                self.state.contact, self.state.offer = npc, quest
                self.state.selected = None
                self.offer("GOSSIP_SHOW")
                self.assertEqual(self.state.selected, quest)
                self.assertEqual(self.offer(), quest)
                self.assertTrue(self.ns.IsQuestActive(self.ns, quest))
                self.assertFalse(self.ns.IsQuestDelivered(self.ns, quest))
        self.assertEqual(self.client.progress(), before)
        self.assertIsNotNone(self.client.travel())
        self.assertFalse(self.ns.char.guideTrips[DWARF].ready)
        self.client.arrive()
        self.assertIsNone(self.client.travel())
        self.ns.char.progress[WEST].cursor = 3
        _, step, state = self.ns.GetCurrent(self.ns)
        self.assertEqual([self.ns.GetGoalStatus(self.ns, step.goals[i], step, state, i)[0]
                          for i in range(1, 4)], ["done"] * 3)
        self.assertEqual(self.ns.GetGoalStatus(self.ns, step.goals[7], step, state, 7)[0], "active")

    def test_live_offers_can_come_from_an_intermediate_map_or_an_alternate_giver(self):
        self.client.move(GOLDSHIRE)
        self.assertIsNone(self.ns.GetPlannedPickupAtNPC(self.ns, 151, 238, 1429))
        self.assertEqual(self.offer(), 151)  # The actual NPC dialog is stronger evidence than the map.
        self.state.quests[151] = None
        self.client.move(WESTFALL_ENTRY)
        self.state.contact = 237
        self.assertIsNone(self.ns.GetPlannedPickupAtNPC(self.ns, 151, 237, 1436))
        self.assertEqual(self.offer(), 151)

    def test_requires_actual_contact_space_and_unpaused_visit(self):
        self.state.contact = None
        self.assertIsNone(self.offer())
        self.state.contact, self.state.used = 238, 40
        self.assertIsNone(self.offer())
        self.state.used, self.state.shift = 18, True
        self.assertIsNone(self.offer())
        self.state.shift = False
        self.ns.char.auto = False
        self.assertEqual(self.ns.GetQuestOfferAdvice(self.ns, 151)[1], "ahora")
        self.assertIsNone(self.offer())
        self.ns.char.auto = True
        self.ns.char.activeGuide = DWARF
        self.ns.char.progress[DWARF].cursor = 20
        self.assertIsNone(self.ns.GetEarlyQuestOffer(self.ns, 151))
        self.ns.char.activeGuide = WEST
        self.client.travel().waiting = True
        self.assertIsNone(self.offer())
        self.client.travel().waiting = False
        self.assertEqual(self.offer(), 151)

    def test_travel_does_not_accept_unreviewed_quests_or_hand_in_at_the_destination(self):
        self.state.offer = 184
        self.assertIsNone(self.offer())
        self.client.h.lua.execute("""
            function IsQuestCompletable() return true end
            function CompleteQuest() TEST.completed = true end
            function GetNumQuestChoices() return 0 end
            function GetQuestMoneyToGet() return 0 end
            function GetQuestReward() TEST.rewarded = true end
        """)
        self.state.contact, self.state.offer = 234, 109
        self.client.s.quests[109] = self.client.h.table({"onQuest": True, "complete": True})
        for event in ("QUEST_PROGRESS", "QUEST_COMPLETE"):
            self.offer(event)
        self.assertIsNone(self.state.completed)
        self.assertIsNone(self.state.rewarded)
