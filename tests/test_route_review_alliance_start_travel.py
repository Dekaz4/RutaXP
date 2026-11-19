import unittest

from test_boat_navigation import BoatHost, GUIDE
from test_duo_journey import primitive_copy


class MenethilAlternativeTests(unittest.TestCase):
    def setUp(self):
        self.host = BoatHost()
        self.host.s.level = 29
        self.host.h.lua.execute("""
            C_QuestLine = {GetAvailableQuestLines=function(map)
                if map == 1437 then return TEST.offers end
            end}
        """)

    def refresh(self):
        self.host.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        self.host.ns.RefreshUI(self.host.ns)
        self.host.ns.UpdateNavigation(self.host.ns)

    def offer(self, hidden=False):
        self.host.s.offers = self.host.h.table([{"questID": 98208, "isHidden": hidden}])
        self.refresh()

    def test_fresh_character_can_take_work_in_town_then_resume_original_departure(self):
        h = self.host
        before = h.progress()
        self.offer()
        choice = h.ns.GetTravelComparison(h.ns)
        self.assertTrue(choice.preferLocal)
        self.assertEqual([(e.quest, e.goal.t) for e in choice.localGoals.values()], [(98208, "accept")])
        self.assertIn("recoger", choice.summary)
        self.assertTrue(h.ns.ChooseLocalQuests(h.ns, choice.key))
        self.assertEqual((h.point().goal.t, h.point().goal.quest), ("accept", 98208))
        h.s.offers = None
        h.s.level = 32
        self.refresh()
        self.assertEqual(h.point().goal.t, "accept")
        h.s.quests[98208] = h.h.table({"onQuest": True, "complete": False, "objectives": [{"finished": False}]})
        self.refresh()
        self.assertEqual((h.point().goal.t, h.point().goal.item), ("collect", 279915))
        h.s.quests[98208].complete = True
        self.refresh()
        self.assertEqual(h.point().goal.t, "turnin")
        h.s.quests[98208] = h.h.table({"onQuest": False, "delivered": True})
        h.h.g.EmitAddonEvent("QUEST_TURNED_IN", 98208)
        self.refresh()
        self.assertTrue(h.point().boatNavigation)
        self.assertEqual(h.progress(), before)
        self.assertEqual(h.ns.char.progress[GUIDE].cursor, 31)

    def test_no_speculative_pickup_or_pickup_while_boarding(self):
        h = self.host
        for hidden, level, position in [(True, 29, (1437, .10, .59)), (False, 32, (1437, .10, .59)),
                                         (False, 29, (1437, .0474, .6376))]:
            with self.subTest(hidden=hidden, level=level):
                h.s.level = level
                h.move(position)
                self.offer(hidden)
                choice = h.ns.GetTravelComparison(h.ns)
                self.assertFalse(choice and any(e.quest == 98208 for e in choice.localGoals.values()))
        h.move((1437, .10, .59))
        h.ns.char.duo.enabled = True
        self.offer()
        choice = h.ns.GetTravelComparison(h.ns)
        self.assertFalse(choice and any(e.quest == 98208 for e in choice.localGoals.values()))

    def test_ready_work_across_the_water_is_considered_without_changing_it(self):
        h = self.host
        h.s.quests[1175] = h.h.table({"onQuest": True, "complete": True})
        self.offer()
        journal = primitive_copy(h.s.quests)
        view = h.ns.GetTravelComparison(h.ns)
        self.assertTrue(any(row.id == 1175 and row.ready for row in view.destinationGoals.values()))
        self.assertFalse(view.preferLocal)
        self.assertEqual(primitive_copy(h.s.quests), journal)

    def test_npc_offer_works_on_a_client_without_map_quest_lines(self):
        h = self.host
        h.h.lua.execute("""
            C_QuestLine = nil
            C_GossipInfo = {GetAvailableQuests=function() return {{questID=98208}} end}
        """)
        self.refresh()
        self.assertEqual(h.ns.GetTravelComparison(h.ns).localGoals[1].quest, 98208)
        h.s.quests[98208] = h.h.table({"onQuest": False, "delivered": True})
        self.refresh()
        view = h.ns.GetTravelComparison(h.ns)
        self.assertFalse(view and view.localCount)
