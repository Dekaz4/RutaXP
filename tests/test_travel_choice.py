"""Long journeys are compared to actionable work from the current journal."""
import unittest

from test_boat_navigation import BoatHost, GUIDE
from test_flight_navigation import FLIGHT_STUBS


class TravelDecisionTests(unittest.TestCase):
    def setUp(self):
        self.host = BoatHost()
        self.host.s.level = 29
        self.host.h.lua.execute("""
            C_Map.GetMapInfo = function(id)
                if id == 1441 then return {name="Las Mil Agujas"} end
                if id == 1437 then return {name="Los Humedales"} end
            end
        """)

    def quest(self, quest_id, complete, **fields):
        self.host.s.quests[quest_id] = self.host.h.table(
            {"onQuest": True, "complete": complete, **fields})

    def view(self, active_key=None, travel=None):
        h = self.host
        choice = h.ns.TravelChoice
        choice.at = None
        return choice.GetRecommendation(choice, h.guide, h.step, h.ns.char.progress[GUIDE], travel, active_key)

    def test_real_salt_flats_excursion_counts_quests_not_objectives_or_pickups(self):
        self.quest(288, True)
        self.quest(270, True)
        before = self.host.progress()
        v = self.view()
        self.assertEqual([r.quest for r in v.localGoals.values()], [288, 270])
        self.assertEqual({r.id for r in v.destinationGoals.values()}, {1110, 1104, 1105, 1176})
        self.assertIsNone(v.hardLevel)
        self.host.ns.char.optional = True
        full = self.view()
        self.assertIn(1175, {r.id for r in full.destinationGoals.values()})
        self.assertEqual(full.hardLevel, 34)
        self.assertIn("34–35", full.summary)
        self.host.ns.char.optional = False
        self.assertIn("Las Mil Agujas", v.summary)
        self.assertTrue(v.preferLocal)
        self.host.s.level = 35
        self.assertFalse(self.view().preferLocal)
        self.assertEqual(self.host.progress(), before)

    def test_finished_objectives_and_ready_deliveries_have_no_combat_penalty(self):
        self.host.ns.char.optional = True  # Include the southern basilisks in the comparison.
        self.quest(288, True)
        self.quest(1175, False, objectives=[{"finished": False}, {"finished": False}, {"finished": True}])
        self.assertEqual(self.view().hardLevel, 32)
        self.quest(1175, True)
        v = self.view()
        self.assertIsNone(v.hardTitle)
        self.assertFalse(v.preferLocal)
        self.assertIn(1175, {r.id for r in v.destinationGoals.values()})

    def test_group_filter_excludes_fights_but_preserves_ready_handins(self):
        self.host.ns.char.optional = True  # Exercise the independent group filter.
        self.host.move((1437, .4936, .4205))
        self.quest(98291, False)
        self.assertEqual(self.view().hardLevel, 34)
        self.host.h.lua.execute("""
            C_QuestLog.GetQuestTagInfo = function(id)
                if id == 1175 or id == 98291 then return {tagID=1} end
            end
        """)
        self.host.h.g.EmitAddonEvent("QUEST_DATA_LOAD_RESULT", 1175, True)
        choice = self.host.ns.TravelChoice
        self.assertIsNone(choice.GetRecommendation(choice, self.host.guide, self.host.step,
                                                   self.host.ns.char.progress[GUIDE]))
        self.quest(98291, True)
        v = self.view()
        self.assertEqual([r.quest for r in v.localGoals.values()], [98291])
        self.assertNotIn(1175, {r.id for r in v.destinationGoals.values()})
        self.host.ns.char.includeGroupQuests = True
        self.assertIn(1175, {r.id for r in self.view().destinationGoals.values()})

    def test_duo_lower_level_and_only_confirmed_shared_work(self):
        h = self.host
        h.s.level = 35
        self.quest(288, True)
        self.quest(270, True)
        h.h.lua.execute("""
            ACCESS_NS.Duo.GetContext = function()
                return {enabled=true, known=true, online=true, sameParty=true, groupSize=2,
                    partnerLevel=29, partnerHeaderFresh=true}
            end
            ACCESS_NS.Duo.GetPartnerQuest = function(_,id)
                if id == 288 then return {state=2} end
            end
        """)
        v = self.view()
        self.assertEqual(v.level, 29)
        self.assertEqual([r.quest for r in v.localGoals.values()], [288])
        self.assertTrue(v.preferLocal)
        self.assertIn("ambos diarios", v.summary)
        h.ns.Duo.GetPartnerQuest = h.h.lua.eval("function() return {basic=true,state=1} end")
        self.assertEqual(self.view().localCount, 0)

    def test_boarding_wrong_zone_unknown_journal_and_review(self):
        h = self.host
        self.quest(288, True)
        h.h.lua.execute("C_QuestLog.IsComplete=function() return nil end")
        self.assertIsNone(self.view())
        h.move((1437, .0474, .6376))
        self.assertEqual(h.view().state, "boarding")
        self.assertIsNone(self.view())
        h.move((1445, .67, .51))
        self.assertIsNone(self.view())
        h.move((1437, .10, .59))
        h.ns.char.progress[GUIDE].review = True
        self.assertIsNone(self.view())

    def test_authored_southshore_crossing_matches_both_ends_not_ordinary_walks(self):
        h = self.host
        self.quest(288, True)
        guide = h.ns.guides["forever/alliance/30-40/01-hillsbrad-foothills"]
        departure, step = next((i, s) for i, s in guide.steps.items() if s.title == "Boat a Costasur")
        state = h.h.table({"cursor": departure, "confirmed": {}, "skipped": {}})
        h.ns.char.activeGuide = guide.id
        h.ns.char.progress[guide.id] = state
        choice = h.ns.TravelChoice
        v = choice.GetRecommendation(choice, guide, step, state)
        self.assertEqual(v.destinationTitle, "Costasur")
        self.assertEqual(v.localGoals[1].quest, 288)
        self.assertTrue(all(row.map == 1424 for row in v.destinationGoals.values()))
        self.assertGreater(v.destinationCount, 0)
        self.assertEqual(state.cursor, departure)
        goal = step.goals[1]
        goal.text = "Camina hasta el muelle"
        self.assertIsNone(choice.GetRecommendation(choice, guide, step, state))
        goal.text = "Boat a Costasur"
        goal.x, goal.y = 4.74, 63.76  # The other pier goes to Theramore.
        self.assertIsNone(choice.GetRecommendation(choice, guide, step, state))

    def test_linked_chapter_only_at_origin_and_before_embarking(self):
        h = self.host
        self.quest(288, True)
        source = "forever/alliance/30-40/03-ashenvale"
        route = h.ns.GuideTravelRoutes[source]
        travel = h.h.table({"source": source, "destination": route.destination,
                            "arrivalMap": 1455, "point": {"mapID": 1437}})
        self.assertEqual(self.view(travel=travel).localGoals[1].quest, 288)
        travel.point = None
        self.assertIsNone(self.view(travel=travel))

    def test_observed_flight_direction_legacy_and_rejection(self):
        h = self.host
        self.quest(288, True)
        h.h.lua.execute(FLIGHT_STUBS)
        h.h.g.EmitAddonEvent("PLAYER_LOGIN")
        h.s.flights = h.h.table([
            {"nodeID": 31, "state": 0, "slotIndex": 1, "kind": "CURRENT", "routes": 0},
            {"nodeID": 32, "state": 1, "slotIndex": 2, "kind": "REACHABLE", "routes": 1},
        ])
        h.h.g.EmitAddonEvent("TAXIMAP_OPENED")
        self.assertFalse(self.view().flightConfirmed)
        h.s.flights[1].nodeID, h.s.flights[2].nodeID = 32, 31
        h.h.g.EmitAddonEvent("TAXIMAP_OPENED")
        self.assertTrue(self.view().flightConfirmed)
        self.assertIn("Thalanaar", self.view().summary)
        h.h.g.TakeTaxiNode(2)
        h.h.g.EmitAddonEvent("UI_ERROR_MESSAGE", 1, h.h.g.ERR_TAXINOSUCHPATH)
        h.h.g.PumpFlightCallbacks()
        self.assertFalse(self.view().flightConfirmed)

    def test_theramore_shortcut_requires_both_characters_when_planning_together(self):
        h = self.host
        self.quest(288, True)
        h.ns.char.observedTaxiRoutes = h.h.table({32:{31:True}})
        h.h.lua.execute("""
            ACCESS_NS.Duo.GetContext = function()
                return {enabled=true, known=true, online=true, sameParty=true, groupSize=2,
                    partnerLevel=29, partnerHeaderFresh=true}
            end
            ACCESS_NS.Duo.GetPartnerQuest = function() return {state=2} end
        """)
        self.assertFalse(self.view().flightConfirmed)
        h.ns.Duo.taxiOffers = h.h.table({31:{"seen":h.s.now,"nodes":{32:True}}})
        self.assertFalse(self.view().flightConfirmed)
        h.ns.Duo.taxiOffers[32] = h.h.table({"seen":h.s.now,"nodes":{31:True}})
        self.assertTrue(self.view().flightConfirmed)


if __name__ == "__main__":
    unittest.main()
