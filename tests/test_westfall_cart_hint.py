"""Nearby pickups for either faction leave the arrow on its current route."""
import unittest

import test_quest_engine as engine
from test_addon import TOOLTIP_STUBS


ELWYNN = "forever/alliance/human/01-elwynn-forest"
WESTFALL = "forever/alliance/02-westfall"


class WestfallCartHintTests(unittest.TestCase):
    def setUp(self):
        engine.NavigationAndFullTocTests.setUp(self)
        h = self.host
        for name in ["Leveling.lua", "WestfallTravelData.lua", "AllianceTravel.lua", "HordeTravel.lua",
                     "TravelConnections.lua", "TravelRouting.lua", "EarlyQuestData.lua", "QuestOfferAdvice.lua",
                     "NearbyQuestOffers.lua"]:
            h.load((engine.ADDON / name).read_text(encoding="utf-8"), "RutaXP", h.ns)
        h.lua.execute(TOOLTIP_STUBS + """
            TEST.now, TEST.filled = 10, 12
            function GetTime() return TEST.now end
            function C_QuestLog.GetNumQuestLogEntries() return 12, TEST.filled end
            function C_QuestLog.GetMaxNumQuestsCanAccept() return 40 end
        """)
        h.state.classToken, h.state.level = "ROGUE", 12
        h.state.mapID, h.state.x, h.state.y = 1436, .5995, .1936
        h.initialize()
        h.call("SelectGuide", ELWYNN)
        self.state = h.ns.char.progress[ELWYNN]
        self.state.cursor = len(h.ns.guides[ELWYNN].steps)

    def refresh(self):
        h = self.host
        h.state.now += 1
        h.call("UpdateNavigation")
        frame = h.ns.navigationFrame
        frame.scripts.OnEnter(frame)
        lines = list(h.globals.GameTooltip.lines.values())
        frame.scripts.OnLeave(frame)
        return next((line for line in lines if line.startswith("Habla con ") and " · " in line), "")

    def test_actual_flight_target_remains_while_hint_lists_only_pending_quests(self):
        h = self.host
        _, step, _ = h.call("GetCurrent")
        target = h.call("GetArrowWaypoint", step)
        self.assertEqual(target.goal.node, 4)
        self.assertEqual(self.refresh(), "Habla con los Cejade · estofado, avena, reloj")
        self.assertIn("Colina del Centinela", h.ns.navigationFrame.destinationText)
        h.quest(64, onQuest=True)
        h.quest(36, delivered=True)
        self.assertEqual(self.refresh(), "Habla con los Cejade · avena")
        h.quest(151, onQuest=True)
        self.assertEqual(self.refresh(), "")
        after = h.call("GetArrowWaypoint", step)
        self.assertEqual((target.x, target.y, 72), (after.x, after.y, self.state.cursor))

    def test_leaving_cart_does_not_prompt_to_return_even_when_quests_are_ahead(self):
        h = self.host
        self.assertIn("reloj", self.refresh())
        h.state.x, h.state.y = .5625, .3473  # Farther down the road at Saldean's Farm.
        self.assertEqual(self.refresh(), "")
        h.state.x, h.state.y, h.state.mapID = .5995, .1936, 1429
        self.assertEqual(self.refresh(), "")
        h.state.mapID, self.state.cursor = 1436, 10
        self.assertIn("reloj", self.refresh())

    def test_local_checks_are_throttled_and_unreadable_positions_suppress_hint(self):
        h = self.host
        h.lua.execute("""
            local zone = C_Map.GetBestMapForUnit
            function C_Map.GetBestMapForUnit(unit)
                if TEST.noZone then error("unavailable") end
                return zone(unit)
            end
        """)
        h.ns.GetPlayerWorldPosition = h.lua.eval("""
            function(position) return function()
                TEST.samples = (TEST.samples or 0) + 1
                return position()
            end end
        """)(h.ns.GetPlayerWorldPosition)
        h.call("UpdateNavigation")
        self.assertIsNone(h.state.samples)
        self.assertIn("reloj", self.refresh())
        count = h.state.samples
        for _ in range(10):
            h.call("UpdateNavigation")
        self.assertEqual(h.state.samples, count)
        h.state.positionUnavailable = True
        self.assertEqual(self.refresh(), "")
        h.state.positionUnavailable, h.state.noZone = False, True
        self.assertEqual(self.refresh(), "")

    def test_destination_arrival_and_personal_skips_review_space_and_duo_wait(self):
        h = self.host
        h.call("SelectGuide", WESTFALL)
        dest = h.ns.char.progress[WESTFALL]
        dest.cursor, dest.skipped = 1, h.table({"3:1": True})
        self.assertEqual(self.refresh(), "Habla con los Cejade · avena, reloj")
        travel = h.table({"title": "Carretera de la Finca de Saldean", "destination": WESTFALL, "arrivalMap": 1436,
                          "point": {"mapID": 1436, "x": .5625, "y": .3473}})
        h.state.travel = travel
        h.ns.GetGuideTravel = h.lua.eval("function() return TEST.travel end")
        self.assertIn("avena", self.refresh())
        travel.waiting = True
        self.assertEqual(self.refresh(), "")
        travel.waiting = False
        dest.review = True
        self.assertEqual(self.refresh(), "")
        dest.review, h.state.filled = False, 40
        self.assertEqual(self.refresh(), "")
        h.state.filled = 10
        h.ns.DuoAuto = h.lua.eval("{ShouldPauseAutomation=function() return true end}")
        self.assertEqual(self.refresh(), "")
        h.ns.DuoAuto, h.state.travel = None, None
        h.ns.char.duo = h.table({"enabled": True, "wait": True})
        h.ns.Duo = h.lua.eval("{ShouldWaitForStep=function() return true end}")
        # Both players can take future quests while still doing this step.
        self.assertIn("avena", self.refresh())
        self.assertEqual(dest.cursor, 1)

    def test_horde_route_and_known_giver_are_independent_of_the_cart(self):
        h = self.host
        h.state.faction, h.state.raceToken = "Horde", "Orc"
        h.state.mapID, h.state.x, h.state.y = 1411, .4285, .6915
        h.call("SelectGuide", "forever/horde/orc-troll/01-durotar")
        self.assertTrue(h.call("IsKnownQuestGiverLocation", 792, 3145, 1411))
        self.assertFalse(h.call("IsKnownQuestGiverLocation", 792, 237, 1411))
        self.assertIn("Habla con Zureetha Vistalonga", self.refresh())
        h.quest(792, onQuest=True)
        self.assertNotIn("Familiares viles", self.refresh())

    def test_bad_target_conversion_recovers_and_another_floor_is_suppressed(self):
        h = self.host
        conversion = h.ns.GetWaypointWorldPosition
        h.call("IsKnownQuestGiverLocation", 792, 3145, 1411)  # Rebuild on returning to Westfall.
        h.ns.GetWaypointWorldPosition = h.lua.eval("function() return nil end")
        self.assertEqual(self.refresh(), "")
        h.ns.GetWaypointWorldPosition = conversion
        self.assertIn("reloj", self.refresh())
        h.ns.GetWaypointHeightDifference = h.lua.eval("function() return 35 end")
        self.assertEqual(self.refresh(), "")

    def test_same_giver_with_two_future_offers_displays_the_earlier_route_stop(self):
        h = self.host
        h.ns.earlyQuestOffers[910001], h.ns.earlyQuestOffers[910002] = True, True
        location = {"t": "accept", "map": 1436, "x": 82, "y": 45,
                    "npc": 910100, "npcName": "Guía de prueba"}
        h.guide("visit", steps=[
            {"title": "Primer paso", "goals": [{"t": "note", "text": "Empieza el recorrido"}]},
            {"title": "Primera parada", "goals": [dict(location, quest=910002, title="Primera misión")]},
            {"title": "Segunda parada", "goals": [dict(location, quest=910001, title="Segunda misión")]},
        ])
        h.call("SelectGuide", "visit")
        h.state.x, h.state.y = .82, .45
        self.assertEqual(self.refresh(), "Habla con Guía de prueba · Primera misión (+1)")
        h.quest(910002, onQuest=True)
        self.assertEqual(self.refresh(), "Habla con Guía de prueba · Segunda misión")
