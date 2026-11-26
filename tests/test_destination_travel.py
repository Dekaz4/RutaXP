"""Exercise per-character transport planning with Forever's map frames and real crossings."""
import math
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
    def test_long_adjacent_chapter_uses_a_known_shortcut_but_keeps_small_savings_local(self):
        for goal, expected in (((1440,.343,.48), "flight"), ((1440,.87,.57), None)):
            h = Destinations((1439,.364,.4562))
            self.assertIsNone(h.route(goal,"chapter")[1])
            h.ns.char.observedTaxiRoutes = h.h.table({26:{28:True}})
            h.ns.FlightNavigation.routeRevision = 1
            _, view = h.route(goal,"chapter")
            self.assertEqual(view and view.kind, expected)

    def test_door_to_door_uses_physical_walks_and_a_directed_usable_flight(self):
        h = Destinations((1437, .0952, .5966))
        routing = h.ns.TravelRouting
        goal = h.h.table({"mapID":1453, "x":.663, "y":.6267})
        other = h.h.table({"mapID":1453, "x":.90, "y":.80})
        def plan(point=goal):
            return routing.EstimateJourney(point,1437,None)
        # An observed connection from Stormwind does not prove a Menethil departure.
        h.ns.char.observedTaxiRoutes = h.h.table({2:{7:True}})
        original = plan()
        self.assertFalse(original.usesFlight)
        h.ns.char.observedTaxiRoutes[7] = h.h.table({2:True})
        h.ns.FlightNavigation.routeRevision = 1
        faster = plan()
        self.assertTrue(faster.usesFlight)
        self.assertLess(faster.seconds, faster.groundSeconds)
        self.assertAlmostEqual(faster.groundSeconds,original.seconds)
        self.assertGreater(plan(other).seconds,faster.seconds)
        h.locate((1437,.19,.50))
        self.assertGreater(plan().seconds,faster.seconds)

    def test_from_theramore_pier_to_desolace_the_chapter_starts_with_a_local_leg(self):
        h = Destinations((1445,.711,.564))
        goal = (1443,.5776,.7105)
        pin,view = h.route(goal,"chapter")
        self.assertIsNotNone(view)
        self.assertEqual(pin.mapID,1445)
        self.assertNotEqual(view.kind,"flight")
        h.ns.char.observedTaxiRoutes=h.h.table({32:{37:True}})
        h.ns.FlightNavigation.routeRevision=1
        pin,view=h.route(goal,"chapter")
        self.assertEqual((pin.mapID,view.kind),(1445,"flight"))
        self.assertIn("Punta de Nijel",view.text)
        self.assertAlmostEqual(pin.x,.6746,places=3)

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

    def test_road_across_duskwood_and_stranglethorn_points_forward_until_map_changes(self):
        duskwood, stranglethorn = (1431,.445,.8751), (1434,.4081,.0419)
        for entry, exit in ((duskwood,stranglethorn),(stranglethorn,duskwood)):
            with self.subTest(departure=entry[0]):
                h = Destinations(entry)
                def world(pos):
                    p = h.h.table(dict(zip(("mapID","x","y"),pos)))
                    return h.ns.GetWaypointWorldPosition(h.ns,p)
                c,n,w = world(entry)
                _,en,ew = world(exit)
                length = math.hypot(en-n,ew-w)
                def move(yards):
                    p = h.ns.WorldToWaypoint(h.ns,c,n+(en-n)*yards/length,w+(ew-w)*yards/length,entry[0])
                    h.locate((entry[0],p.x,p.y))
                goal = (exit[0],.4,.5)
                move(-60)
                approach,v = h.route(goal)
                self.assertEqual((v.kind,v.state,approach.mapID),("road","approach",entry[0]))
                self.assertAlmostEqual(approach.x,entry[1])
                move(-26)
                forward,v = h.route(goal)
                self.assertEqual((v.kind,v.state,forward.mapID),("road","crossing",entry[0]))
                self.assertNotEqual(approach.targetKey,forward.targetKey)
                self.assertAlmostEqual(world((forward.mapID,forward.x,forward.y))[1],en)
                self.assertAlmostEqual(world((forward.mapID,forward.x,forward.y))[2],ew)
                # Leaving the small approach circle, pausing and reloading all keep the forward target.
                for d in (-38,33):
                    move(d)
                    self.assertEqual(h.route(goal)[0].targetKey,forward.targetKey)
                h = Destinations((h.s.mapID,h.s.x,h.s.y),save=primitive_copy(h.ns.char))
                self.assertEqual(h.route(goal)[0].targetKey,forward.targetKey)
                for d in (length-2,length+17,length-9):
                    move(d)
                    pin,v = h.route(goal)
                    self.assertIsNone(pin)
                    self.assertEqual(v.state,"crossing")
                    self.assertIn("carretera",v.text)
                # Deliberately return well behind the entry and the approach may be shown again.
                move(-115)
                self.assertEqual(h.route(goal)[0].targetKey,approach.targetKey)
                move(0)
                self.assertEqual(h.route(goal)[0].targetKey,forward.targetKey)
                h.locate(exit)
                pin,v = h.route(goal)
                self.assertEqual((pin.mapID,pin.x,pin.y),goal)
                self.assertIsNone(v)

    def test_adjacent_chapter_walk_crosses_road_at_the_actual_border(self):
        h = Destinations((1431,.445,.8751))
        goal = (1434,.4,.1)
        pin,v = h.route(goal,"chapter")
        self.assertEqual((v.state,pin.mapID),("crossing",1431))
        self.assertGreater(pin.y,.8751)
        h.locate((1434,.4081,.0419))
        pin,v = h.route(goal,"chapter")
        self.assertEqual((pin.mapID,pin.x,pin.y),goal)
        self.assertIsNone(v)

    def test_biggs_chapter_arrow_crosses_deadwind_before_pointing_to_the_npc(self):
        guide_id = "forever/alliance/30-40/05-arathi-highlands"
        save = old_save(guide_id, auto=False)
        save["progress"][guide_id] = {"cursor": 2, "placed": True}
        h = Destinations((1431, .784, .451), save=save)
        h.s.level = 38
        h.h.lua.execute("""
            local original = C_Map.GetMapInfo
            local names = {[1430]="Paso de la Muerte", [1435]="Pantano de las Penas"}
            function C_Map.GetMapInfo(id)
                if names[id] then return {mapID=id, name=names[id]} end
                if original then return original(id) end
            end
        """)
        _, step, _ = h.ns.GetCurrent(h.ns)
        before = primitive_copy(h.ns.char.progress[guide_id])

        for origin, entry, next_zone in (
            ((1431, .784, .451), (1431, .8988, .4125), "Paso de la Muerte"),
            ((1430, .3305, .3596), (1430, .5829, .4144), "Pantano de las Penas"),
        ):
            with self.subTest(origin=origin):
                h.locate(origin)
                point = h.ns.GetArrowWaypoint(h.ns, step, False)
                view = h.ns.GetDestinationTravelView(h.ns)
                self.assertEqual((view.kind, view.state), ("road", "approach"))
                self.assertIn(next_zone, view.shortText)
                self.assertEqual(point.mapID, entry[0])
                self.assertAlmostEqual(point.x, entry[1])
                self.assertAlmostEqual(point.y, entry[2])

                h.locate(entry)
                forward = h.ns.GetArrowWaypoint(h.ns, step, False)
                view = h.ns.GetDestinationTravelView(h.ns)
                self.assertEqual((view.kind, view.state, forward.mapID), ("road", "crossing", entry[0]))
                self.assertGreater(forward.x, point.x)

        h.locate((1435, .0584, .6078))
        point = h.ns.GetArrowWaypoint(h.ns, step, False)
        self.assertEqual((point.mapID, point.goal.quest, point.goal.npc), (1435, 1396, 5476))
        self.assertAlmostEqual(point.x, .2674)
        self.assertAlmostEqual(point.y, .5983)
        self.assertEqual(primitive_copy(h.ns.char.progress[guide_id]), before)

    def test_road_uses_live_origin_map_even_when_reverse_api_prefers_next_zone(self):
        h = Destinations((1431,.445,.8751))
        h.h.lua.execute("""
            local reverse = C_Map.GetMapPosFromWorldPos
            function C_Map.GetMapPosFromWorldPos(c, p, map)
                return reverse(c,p,map==1431 and 1434 or map)
            end
        """)
        pin,v = h.route((1434,.4,.5))
        self.assertEqual((v.kind,v.state,pin.mapID),("road","crossing",1431))
        self.assertAlmostEqual(pin.x,.450625,places=5)
        self.assertAlmostEqual(pin.y,.905741,places=5)

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
