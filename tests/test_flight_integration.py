"""Actual flight steps, tracker controls and map ownership stay consistent."""
import unittest

from test_duo_journey import primitive_copy
from test_westfall_travel import TravelHost


GUIDE = "forever/alliance/07-thousand-needles"


class FlightIntegrationHost(TravelHost):
    def __init__(self):
        super().__init__((1431, .7759, .4438), {
            "seen": True, "activeGuide": GUIDE, "auto": False,
            "duo": {"enabled": False, "autoPair": False},
            "progress": {GUIDE: {"cursor": 18, "placed": True,
                "confirmed": {"personal-mark": True}, "skipped": {"personal-skip": True}}},
        }, race="Human", classes=("ROGUE", "HUNTER"))
        self.s.level = 28
        self.step = self.ns.guides[GUIDE].steps[18]
        self.goal = self.step.goals[1]
        self.h.lua.execute('''
            TEST.taxiNodes = {}
            TEST.taxiOpen, TEST.onTaxi = false, false
            Enum.FlightPathState = {Current=0,Reachable=1,Unreachable=2}
            function UnitOnTaxi() return TEST.onTaxi end
            function GetTaxiMapID() return TEST.taxiOpen and 1415 or nil end
            C_TaxiMap = {
                GetAllTaxiNodes = function() return TEST.taxiNodes end,
                GetTaxiNodesForMap = function() error("Map discovery is not reachability") end,
            }
            function NumTaxiNodes() return #TEST.taxiNodes end
            function TaxiNodeGetType(slot)
                local node=TEST.taxiNodes[slot]
                return node and ({[0]="CURRENT",[1]="REACHABLE",[2]="UNREACHABLE"})[node.state]
            end
            function GetNumRoutes(slot)
                return TaxiNodeGetType(slot)=="REACHABLE" and 1 or 0
            end
            function TaxiNodeName(slot) return TEST.taxiNodes[slot].name end
            function C_Map.GetMapInfo(id)
                local names={[1431]="Bosque del Ocaso",[1453]="Ventormenta",[1455]="Forjaz",[1437]="Los Humedales"}
                return {name=names[id] or "Zona "..id}
            end
        ''')

    def open_taxi(self, menethil=2):
        self.s.taxiNodes = self.h.table([
            {"nodeID": 12, "state": 0, "slotIndex": 1, "name": "Villa Oscura"},
            {"nodeID": 2, "state": 1, "slotIndex": 2, "name": "Ventormenta"},
            {"nodeID": 6, "state": 2, "slotIndex": 3, "name": "Forjaz"},
            {"nodeID": 7, "state": menethil, "slotIndex": 4, "name": "Puerto de Menethil"},
        ])
        self.s.taxiOpen = True
        self.h.g.EmitAddonEvent("TAXIMAP_OPENED", 0)
        self.ns.Sync(self.ns)

    def marks(self):
        return primitive_copy(self.ns.char.progress[GUIDE])

    def arrow(self):
        self.ns.UpdateNavigation(self.ns)
        return self.ns.navigationFrame


class FlightIntegrationTests(unittest.TestCase):
    def test_unreachable_menethil_keeps_the_step_and_guides_a_reachable_hub(self):
        h = FlightIntegrationHost()
        before = h.marks()
        h.open_taxi()
        view = h.ns.FlightNavigation.CurrentView(h.ns.FlightNavigation)
        self.assertIn("Ventormenta", view.text)
        self.assertNotIn("selecciona «Puerto de Menethil»", view.text)
        point = h.pin()
        self.assertEqual(point.mapID, 1431)
        self.assertTrue(point.flightNavigation)
        frame = h.arrow()
        self.assertIn("Ventormenta", frame.destinationText)
        self.assertEqual(h.marks(), before)

    def test_ground_button_keeps_flight_pending_and_uses_a_local_exit(self):
        h = FlightIntegrationHost()
        h.open_taxi()
        before = h.marks()
        button = h.ns.trackerNext
        self.assertEqual(button.GetText(button), "Ir sin vuelo")
        self.h_click(h, button)
        point = h.pin()
        self.assertEqual(point.mapID, 1431)
        self.assertTrue(point.flightNavigation)
        self.assertGreater(abs(point.x - .7759) + abs(point.y - .4438), .01)
        self.assertEqual(h.marks(), before)
        self.assertNotEqual(h.ns.GetGoalStatus(h.ns, h.goal, h.step, h.ns.char.progress[GUIDE], 1)[0], "done")

    @staticmethod
    def h_click(host, button):
        host.h.g.Click(button)

    def test_map_click_on_future_quest_does_not_select_its_flight_or_change_progress(self):
        h = FlightIntegrationHost()
        h.open_taxi()
        before = h.marks()
        index, future = next((index, goal) for index, goal in h.step.goals.items() if goal.t == "accept")
        expected = h.ns.GetGoalWaypoint(h.ns, future)
        self.assertIsNotNone(expected)
        h.ns.Navigate(h.ns, index)
        self.assertEqual(h.s.lastWaypoint.mapID, expected.mapID)
        self.assertAlmostEqual(h.s.lastWaypoint.x, expected.x)
        self.assertAlmostEqual(h.s.lastWaypoint.y, expected.y)
        self.assertIn("Ventormenta", h.ns.FlightNavigation.CurrentView(h.ns.FlightNavigation).text)
        self.assertEqual(h.marks(), before)

    def test_recovery_and_meeting_waypoints_keep_their_own_arrow_instructions(self):
        for owner in ("Recovery", "Duo"):
            with self.subTest(owner=owner):
                h = FlightIntegrationHost()
                h.open_taxi()
                h.h.g.FLIGHT_TEST_POINT = h.h.table({"mapID": 1431, "x": .7759, "y": .4438,
                    "label": "Reunión local", "source": "duo-meeting"})
                method = "GetNavigationOverride" if owner == "Recovery" else "GetMeetingWaypoint"
                getattr(h.ns, owner)[method] = h.h.lua.eval("function() return FLIGHT_TEST_POINT end")
                before = h.marks()
                h.ns.RefreshUI(h.ns)
                self.assertFalse(bool(h.ns.trackerNext.flightGround))
                frame = h.arrow()
                self.assertNotIn("Ventormenta", frame.destinationText or "")
                self.assertFalse(bool(h.pin().flightNavigation))
                self.assertEqual(h.marks(), before)

    def test_being_over_the_landing_point_in_flight_does_not_complete_the_service(self):
        h = FlightIntegrationHost()
        h.open_taxi(menethil=1)
        h.s.onTaxi = True
        h.move((1437, .0952, .5966))
        status = h.ns.GetGoalStatus(h.ns, h.goal, h.step, h.ns.char.progress[GUIDE], 1)[0]
        self.assertNotEqual(status, "done")
        self.assertEqual(h.ns.char.progress[GUIDE].cursor, 18)
        frame = h.arrow()
        self.assertFalse(bool(frame.arrived))


if __name__ == "__main__":
    unittest.main()
