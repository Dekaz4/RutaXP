"""Exercise per-character transport planning with Forever's map frames and real crossings."""
import unittest
from pathlib import Path

from test_duo_journey import primitive_copy
from test_flight_navigation import FLIGHT_STUBS
from test_westfall_travel import TravelHost, old_save


class Destinations(TravelHost):
    def __init__(self, position=(1437, .093, .578), faction="Alliance", save=None):
        super().__init__(position, save or old_save(), faction=faction)
        # TravelHost deliberately loads the old tracker TOC for its migration cases.
        if not self.ns.RouteDestination:
            source = Path(__file__).resolve().parents[1] / "RutaXP" / "DestinationTravel.lua"
            self.h.lua.execute(source.read_text(encoding="utf8"), "RutaXP", self.ns)
        self.h.lua.execute(FLIGHT_STUBS)

    def route(self, destination, channel="activity"):
        point = self.h.table(dict(zip(("mapID","x","y"), destination)))
        result = self.ns.RouteDestination(self.ns, point, "quest", channel)
        return result if isinstance(result, tuple) else (result, None)

    def locate(self, pos):
        self.s.mapID, self.s.x, self.s.y = pos


class DestinationTravelTests(unittest.TestCase):
    def test_menethil_auberdine_boat_stopover_reload_and_arrival(self):
        h = Destinations()
        goal = (1439, .373, .402)
        pin, view = h.route(goal)
        self.assertEqual((pin.mapID, round(pin.x,4), round(pin.y,4)), (1437,.0449,.5666))
        self.assertIn("Costasur", view.text)
        h.locate((1437,pin.x,pin.y))
        pin,view=h.route(goal)
        self.assertIsNone(pin)
        self.assertEqual(view.state, "boarding")
        h.locate((None,None,None))
        self.assertIsNone(h.route(goal)[0])
        save = primitive_copy(h.ns.char)
        h=Destinations((1424,.5067,.7044),save=save)
        pin,view=h.route(goal)
        self.assertIsNone(pin)
        self.assertEqual(view.shortText, "Quédate a bordo en Costasur")
        # A zone transition at sea cannot prove arrival, even far from port.
        h.locate((1439,.01,.4413))
        self.assertEqual(h.route(goal)[1].state,"crossing")
        h.locate((1439,.3234,.4413))
        pin,view=h.route(goal)
        self.assertEqual((pin.mapID,pin.x,pin.y),goal)
        self.assertEqual(view.state,"arrived")
        self.assertEqual(h.route(goal)[1].state,"arrived")
        h.h.lua.execute("local now=GetTime(); function GetTime() return now+9 end")
        self.assertIsNone(h.route(goal)[1])

    def test_real_taxi_observation_changes_plan_before_clock_advances(self):
        h=Destinations((1437,.0952,.5966))
        goal=(1453,.663,.6267)
        self.assertNotEqual(h.route(goal)[1].kind,"flight")
        h.s.flights=h.h.table([
            {"nodeID":7,"state":0,"slotIndex":1,"kind":"CURRENT","routes":0},
            {"nodeID":2,"state":1,"slotIndex":2,"kind":"REACHABLE","routes":2},
        ])
        h.h.g.EmitAddonEvent("TAXIMAP_OPENED")
        pin,view=h.route(goal)
        self.assertIsNone(pin)
        self.assertEqual(view.shortText,"Vuela a Ventormenta")
        h.s.flying=True
        self.assertEqual(h.route(goal)[1].state,"flying")
        h.s.flying=False
        h.s.flights[2].kind,h.s.flights[2].routes,h.s.flights[2].state="UNREACHABLE",0,2
        h.h.g.EmitAddonEvent("TAXIMAP_OPENED")
        self.assertNotEqual(h.route(goal)[1].kind,"flight")

    def test_horde_zeppelin_and_neutral_road_have_departure_on_this_map(self):
        h=Destinations((1411,.49,.11),"Horde")
        pin,view=h.route((1420,.60,.58),"chapter")
        self.assertEqual((pin.mapID,view.kind),(1411,"zeppelin"))
        self.assertIn("Entrañas",view.text)
        h=Destinations((1439,.43,.90))
        pin,view=h.route((1440,.29,.15))
        self.assertEqual((pin.mapID,view.kind),(1439,"road"))

    def test_unknown_destination_and_tram_have_no_remote_arrow(self):
        h=Destinations((1455,.78,.5137))
        self.assertEqual(h.route((1453,.69,.30))[1].kind,"tram")
        h.s.instance=369
        h.locate((None,None,None))
        pin,view=h.route((1453,.69,.30))
        self.assertIsNone(pin)
        self.assertIn("Ventormenta",view.text)
        h.s.instance=0
        h.locate((1453,.69,.30))
        self.assertEqual(h.route((1453,.69,.30))[0].mapID,1453)
        pin,view=h.route((999999,.2,.3))
        self.assertIsNone(pin)
        self.assertEqual(view.state,"unavailable")

    def test_focus_and_chapter_do_not_cancel_each_others_crossing(self):
        h=Destinations((1437,.0449,.5666))
        goal=(1439,.373,.402)
        self.assertEqual(h.route(goal,"chapter")[1].state,"boarding")
        h.route((1437,.09,.57),"activity")
        h.locate((1424,.5067,.7044))
        self.assertEqual(h.route(goal,"chapter")[1].state,"stopover")

    def test_native_chapter_arrow_never_passes_remote_waypoint_to_walking(self):
        h=Destinations()
        h.h.lua.execute("""
            local ns = ...
            function ns:GetStepWaypoint() return {mapID=1439,x=.37,y=.40} end
            local walking = ns.Walking
            ns.Walking = {Resolve=function(_,p) assert(p.mapID==1437); return p end}
            local point=ns:GetArrowWaypoint({},false)
            assert(point.mapID==1437 and ns:GetDestinationTravelView().kind=="boat")
            ns.Walking=walking
        """, h.ns)


if __name__ == "__main__":
    unittest.main()
