"""Use the flight master's observed routes, never map discovery as connectivity."""
import unittest

from test_access_navigation import WORLD_STUBS
from test_duo import DUO_STUBS
from test_duo_journey import primitive_copy
from test_talent_trainer_regressions import TalentTrainerHost


GUIDE = "forever/alliance/07-thousand-needles"
FLIGHT_STUBS = r'''
TEST.flights = {
    {nodeID=12, state=0, slotIndex=1, name="Villa Oscura", kind="CURRENT", routes=0},
    {nodeID=7, state=2, slotIndex=2, name="Puerto de Menethil, Los Humedales", kind="UNREACHABLE", routes=0},
    {nodeID=2, state=1, slotIndex=3, name="Ventormenta", kind="REACHABLE", routes=1},
}
TEST.flightCallbacks = {}
Enum.FlightPathState = {Current=0, Reachable=1, Unreachable=2}
C_TaxiMap = {
    GetAllTaxiNodes=function() return TEST.flights end,
    GetTaxiNodesForMap=function() error("Map discovery is not flight connectivity") end,
}
function GetTaxiMapID() return 1415 end
function NumTaxiNodes() return #TEST.flights end
function TaxiNodeGetType(slot) return TEST.flights[slot].kind end
function TaxiNodeName(slot) return TEST.flights[slot].name end
function GetNumRoutes(slot) return TEST.flights[slot].routes end
function UnitOnTaxi() return TEST.flying==true end
function TakeTaxiNode(slot)
    TEST.flightCalls = (TEST.flightCalls or 0) + 1
    if TEST.rejectDuringCall then EmitAddonEvent("UI_INFO_MESSAGE", 1, ERR_TAXINOSUCHPATH) end
end
function hooksecurefunc(name, hook)
    local original = _G[name]
    _G[name] = function(...) original(...); hook(...) end
end
ERR_TAXINOSUCHPATH = "No existe una ruta directa a ese destino"
C_Timer = {After=function(_, fn) table.insert(TEST.flightCallbacks, fn) end}
function PumpFlightCallbacks()
    local calls = TEST.flightCallbacks; TEST.flightCallbacks = {}
    for _, fn in ipairs(calls) do fn() end
end
'''


class FlightHost:
    def __init__(self, saved=None):
        self.h = TalentTrainerHost(full_toc=True)
        self.h.lua.execute(DUO_STUBS)
        self.ns, self.s = self.h.ns, self.h.state
        self.h.g.ACCESS_NS = self.ns
        self.h.lua.execute(WORLD_STUBS + FLIGHT_STUBS)
        self.s.members, self.s.level = 0, 28
        self.s.classToken, self.s.raceToken = "ROGUE", "Human"
        self.s.mapID, self.s.x, self.s.y = 1431, .7759, .4438
        self.guide = self.ns.guides[GUIDE]
        self.step = self.guide.steps[18]
        self.goal = self.step.goals[1]
        self.h.g.RutaXPCharDB = self.h.table(saved or {
            "seen": True, "activeGuide": GUIDE, "auto": False,
            "duo": {"enabled": False, "autoPair": False},
            "progress": {GUIDE: {"cursor": 18, "routeRevision": self.guide.routeRevision,
                                  "placed": True, "confirmed": {}, "skipped": {}}},
        })
        self.h.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        self.h.g.EmitAddonEvent("PLAYER_LOGIN")
        self.f = self.ns.FlightNavigation

    def view(self):
        return self.f.GetView(self.f, self.goal)

    def observe(self):
        self.h.g.EmitAddonEvent("TAXIMAP_OPENED", 0)

    def move(self, map_id, x, y):
        self.s.mapID, self.s.x, self.s.y = map_id, x, y

    def complete(self):
        return self.f.IsComplete(self.f, self.goal, self.guide, 18, 1, self.ns.char.progress[GUIDE])

    def progress(self):
        return primitive_copy(self.ns.char.progress)


class FlightNavigationTests(unittest.TestCase):
    def test_unknown_does_not_claim_available_or_missing_from_discovery(self):
        h = FlightHost()
        self.assertEqual(h.view().state, "unknown")
        self.assertIsNotNone(h.view().point)
        self.assertFalse(h.complete())
        self.assertIsNone(h.s.flightCalls)

    def test_rejected_direct_route_uses_a_proven_reachable_closer_hub(self):
        h = FlightHost()
        before = h.progress()
        h.observe()
        view = h.view()
        self.assertEqual(view.state, "connection")
        self.assertEqual(view.intermediate, 2)
        self.assertIn("Ventormenta", view.text)
        self.assertIn("Menethil", view.text)
        self.assertEqual(view.point.mapID, 1431)
        self.assertEqual(h.progress(), before)
        self.assertFalse(h.complete())
        self.assertIsNone(h.s.flightCalls)

    def test_destination_discovery_cannot_override_missing_routes(self):
        for kind, routes in (("UNREACHABLE", 1), ("REACHABLE", 0)):
            with self.subTest(kind=kind, routes=routes):
                h = FlightHost()
                h.s.flights[2].state = 1
                h.s.flights[2].kind, h.s.flights[2].routes = kind, routes
                h.s.flights[3].state, h.s.flights[3].kind = 2, "UNREACHABLE"
                h.observe()
                self.assertEqual(h.view().state, "unavailable")
                self.assertIsNone(h.view().point)
                self.assertTrue(h.view().canGround)
                self.assertFalse(h.complete())

    def test_actual_reachable_destination_beats_an_intermediate_hub(self):
        h = FlightHost()
        h.s.flights[2].state, h.s.flights[2].kind, h.s.flights[2].routes = 1, "REACHABLE", 2
        h.observe()
        self.assertEqual(h.view().state, "available")
        self.assertIsNone(h.view().intermediate)
        self.assertFalse(h.complete())

    def test_absent_or_unreadable_destination_is_unknown(self):
        h = FlightHost()
        h.s.flights[2].state, h.s.flights[2].kind = None, None
        h.observe()
        self.assertEqual(h.view().state, "unknown")
        h.h.lua.execute("C_TaxiMap.GetAllTaxiNodes=function() return {} end")
        h.observe()
        self.assertEqual(h.view().state, "unknown")

    def test_legacy_name_resolution_is_scoped_to_the_current_master(self):
        h = FlightHost()
        h.h.lua.execute("C_TaxiMap.GetAllTaxiNodes=nil")
        h.observe()
        self.assertEqual(h.view().state, "unavailable")
        self.assertIsNone(h.view().intermediate)
        h.s.flights[2].name = "Otro destino"
        h.observe()
        self.assertEqual(h.view().state, "unknown")

    def test_ground_choice_routes_away_from_departure_and_survives_reload(self):
        h = FlightHost()
        before = h.progress()
        h.observe()
        self.assertTrue(h.f.BeginGround(h.f))
        view = h.view()
        self.assertEqual(view.state, "ground")
        self.assertEqual(view.point.mapID, 1431)
        self.assertFalse(view.canGround)
        self.assertNotAlmostEqual(view.point.x, .7759)
        self.assertEqual(h.progress(), before)
        reloaded = FlightHost(saved=primitive_copy(h.ns.char))
        self.assertEqual(reloaded.view().state, "ground")
        self.assertEqual(reloaded.progress(), before)

    def test_ground_route_keeps_the_boat_instruction_at_a_transfer(self):
        h = FlightHost()
        self.assertTrue(h.f.BeginGround(h.f))
        h.move(1453, .66, .62)
        view = h.view()
        self.assertEqual(view.state, "ground")
        self.assertEqual(view.point.mapID, 1453)
        self.assertIn("barco", view.text.lower())
        self.assertFalse(h.complete())

    def test_ground_route_preserves_the_tram_instruction_inside_the_instance(self):
        h = FlightHost()
        for candidate in h.goal.candidates.values():
            candidate.destinationNodes = h.h.table([6])
        h.goal.location = "Forjaz"
        h.move(1453, .66, .62)
        self.assertTrue(h.f.BeginGround(h.f))
        view = h.view()
        self.assertIn("tren", view.text.lower())
        h.move(1453, view.point.x, view.point.y)
        self.assertIsNone(h.view().point)
        h.h.lua.execute('function GetInstanceInfo() return "Tren", "none", nil, nil, nil, nil, nil, 369 end')
        self.assertIn("tren", h.view().text.lower())
        self.assertFalse(h.complete())

    def test_arrival_is_local_and_persists_after_leaving_landing(self):
        h = FlightHost()
        h.move(1437, .0952, .5966)
        h.s.flying = True
        self.assertEqual(h.view().state, "flying")
        self.assertFalse(h.complete())
        h.s.flying = False
        self.assertEqual(h.view().state, "arrived")
        self.assertTrue(h.complete())
        h.move(1437, .107, .6095)
        self.assertTrue(h.complete())
        self.assertIsNone(h.ns.char.progress[GUIDE].confirmed["18:1"])
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 288))
        reloaded = FlightHost(saved=primitive_copy(h.ns.char))
        self.assertTrue(reloaded.complete())
        reloaded.guide.routeRevision = (reloaded.guide.routeRevision or 1) + 1
        self.assertFalse(reloaded.complete())

    def test_review_and_other_rows_cannot_record_a_future_flight(self):
        h = FlightHost()
        h.move(1437, .0952, .5966)
        state = h.ns.char.progress[GUIDE]
        state.review = True
        self.assertIsNone(h.view())
        self.assertFalse(h.complete())
        state.review = False
        state.cursor = 17
        self.assertIsNone(h.view())
        self.assertFalse(h.complete())

    def test_authored_guide_repair_preserves_observed_arrival_after_leaving_the_master(self):
        h = FlightHost()
        self.assertEqual(h.guide.routeRevision, 4)
        # Version 0.7.24 recorded the actual arrival against route revision 3.
        h.guide.routeRevision = 3
        h.ns.char.progress[GUIDE].routeRevision = 3
        h.move(1437, .0952, .5966)
        self.assertEqual(h.view().state, "arrived")
        saved = primitive_copy(h.ns.char)
        self.assertIn(f"{GUIDE}:3:18:1:7", saved["flightNavigation"]["arrivals"])
        repaired = FlightHost(saved=saved)
        repaired.move(1437, .1211, .6419)
        self.assertEqual(repaired.ns.char.progress[GUIDE].routeRevision, 4)
        before = primitive_copy(repaired.ns.char)
        self.assertTrue(repaired.complete())
        self.assertEqual(repaired.ns.GetGoalStatus(repaired.ns, repaired.goal, repaired.step,
            repaired.ns.char.progress[GUIDE], 1, repaired.guide)[0], "done")
        self.assertEqual(primitive_copy(repaired.ns.char), before)
        self.assertIsNone(repaired.view(), "An observed arrival must not request the departure master again")

    def test_old_arrival_does_not_cover_a_retired_action_or_changed_destination(self):
        for change in ("retired", "destination", "unmapped"):
            with self.subTest(change=change):
                h = FlightHost()
                h.ns.char.flightNavigation = h.h.table({"arrivals": {
                    f"{GUIDE}:3:18:1:7": {"destination": 7}}})
                self.assertTrue(h.complete())
                if change == "retired":
                    h.guide.progressMigrations[3].retiredGoalKeys = h.h.table({"18:1": True})
                elif change == "destination":
                    for candidate in h.goal.candidates.values():
                        candidate.destinationNodes = h.h.table([6])
                else:
                    h.guide.progressMigrations = h.h.table([])
                self.assertFalse(h.complete())

    def test_snapshot_expires_on_leaving_origin_or_learning_a_new_path(self):
        h = FlightHost()
        h.observe()
        self.assertEqual(h.view().state, "connection")
        h.move(1453, .663, .6267)
        self.assertEqual(h.view().state, "unknown")
        h.move(1431, .7759, .4438)
        self.assertEqual(h.view().state, "unknown")
        h.observe()
        h.h.g.EmitAddonEvent("NEW_TAXI_PATH")
        self.assertEqual(h.view().state, "unknown")
        h.observe()
        h.s.now = 121
        self.assertEqual(h.view().state, "unknown")

    def test_exact_server_rejection_overrides_a_stale_reachable_snapshot(self):
        h = FlightHost()
        h.s.flights[2].state, h.s.flights[2].kind, h.s.flights[2].routes = 1, "REACHABLE", 1
        h.observe()
        self.assertEqual(h.view().state, "available")
        h.s.rejectDuringCall = True
        h.h.g.TakeTaxiNode(2)
        h.h.g.PumpFlightCallbacks()
        self.assertEqual(h.view().state, "connection")
        self.assertEqual(h.s.flightCalls, 1)

    def test_unrelated_errors_and_other_destinations_do_not_reject_the_goal(self):
        h = FlightHost()
        h.s.flights[2].state, h.s.flights[2].kind, h.s.flights[2].routes = 1, "REACHABLE", 1
        h.observe()
        h.h.g.TakeTaxiNode(2)
        h.h.g.EmitAddonEvent("UI_ERROR_MESSAGE", 1, "No tienes suficiente dinero")
        h.h.g.PumpFlightCallbacks()
        self.assertEqual(h.view().state, "available")

    def test_an_unmapped_click_cannot_blame_a_previous_destination(self):
        h = FlightHost()
        h.s.flights[2].state, h.s.flights[2].kind, h.s.flights[2].routes = 1, "REACHABLE", 1
        h.observe()
        h.h.g.TakeTaxiNode(2)
        h.s.rejectDuringCall = True
        h.h.g.TakeTaxiNode(999)
        h.h.g.PumpFlightCallbacks()
        self.assertEqual(h.view().state, "available")
        h.s.rejectDuringCall = True
        h.h.g.TakeTaxiNode(3)
        h.h.g.PumpFlightCallbacks()
        self.assertEqual(h.view().state, "available")


if __name__ == "__main__":
    unittest.main()
