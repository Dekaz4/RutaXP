"""Check every published journey against the real guides loaded from the TOC."""

import math
import unittest

from test_talent_trainer_regressions import TalentTrainerHost
from test_westfall_travel import TravelHost


class TravelCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = TalentTrainerHost(full_toc=True)
        cls.ns = cls.host.ns

    def journeys(self):
        for source, route in self.ns.GuideTravelRoutes.items():
            yield source, route.destination, route
            for variant in (route.variants or {}).values():
                with self.subTest(source=source, variant=True):
                    self.assertTrue(variant.only)
                    self.assertTrue(any(variant.only[k] and len(variant.only[k])
                                        for k in ("classes", "races", "factions")))
                yield source, route.destination, variant

    def test_every_published_next_and_only_those_have_a_trip(self):
        expected = {key: guide.next for key, guide in self.ns.guides.items() if guide.next}
        actual = {key: trip.destination for key, trip in self.ns.GuideTravelRoutes.items()}
        self.assertGreaterEqual(len(expected), 55)
        self.assertEqual(actual, expected)
        for source, destination in actual.items():
            self.assertEqual(self.ns.guides[source].faction, self.ns.guides[destination].faction)

    def assert_pin(self, pin):
        self.assertIsInstance(pin.map, int)
        self.assertGreater(pin.map, 0)
        self.assertIn(pin.f, ("e", "f"))
        if pin.f == "e":
            self.assertIsNotNone(self.ns.mapFrames.era[pin.map])
        self.assertTrue(all(math.isfinite(x) and 0 <= x <= 100 for x in (pin.x, pin.y)))
        self.assertGreater(pin.radius, 0)

    def test_all_stages_have_a_stable_id_an_instruction_and_a_real_arrival(self):
        for source, _, journey in self.journeys():
            with self.subTest(source=source):
                stages = list(journey.legs.values())
                self.assertGreaterEqual(len(stages), 2)
                self.assertEqual(len(stages), len({s.id for s in stages}))
                self.assertTrue(stages[-1].map)
                self.assertFalse(stages[-1].boundary)
                for stage in stages:
                    with self.subTest(stage=stage.id):
                        self.assertTrue(stage.id and stage.title.strip() and stage.text.strip())
                        if stage.instanceID is not None:
                            self.assertEqual(stage.instanceID, 369)
                            self.assertTrue(stage.boundary)
                            self.assertIsNone(stage.map)
                            self.assertIsNone(stage.x)
                            self.assertIsNone(stage.y)
                        else:
                            self.assert_pin(stage)
                        if stage.transport:
                            self.assertTrue(stage.boundary)
                        if stage.taxiLanding:
                            self.assertTrue(stage.transport)
                            self.assert_pin(stage.taxiLanding)
                            self.assertTrue(stage.taxiLanding.title)
                            self.assertNotEqual((stage.map, stage.x, stage.y),
                                                (stage.taxiLanding.map, stage.taxiLanding.x, stage.taxiLanding.y))

    def test_only_supported_travel_services_proved_by_the_itinerary_can_be_satisfied(self):
        for source, destination, journey in self.journeys():
            guide = self.ns.guides[destination]
            services = dict((journey.arrivalGoalsByStep or {}).items())
            if journey.arrivalGoals:
                self.assertNotIn(1, services)
                services[1] = journey.arrivalGoals
            stages = list(journey.legs.values())
            for step, indices in services.items():
                for index in indices.values():
                    with self.subTest(source=source, step=step, goal=index):
                        goal = guide.steps[step].goals[index]
                        self.assertIsNotNone(goal)
                        self.assertIsNone(goal.quest)
                        self.assertIn(goal.t, ("fly", "goto", "hearth"))
                        if goal.t == "fly":
                            self.assertTrue(any(s.taxiLanding and s.taxiLanding.title == goal.location
                                                for s in stages), goal.location)
                        elif goal.t == "goto":
                            # Imported goto labels sometimes round the boarding pin to one decimal.
                            self.assertTrue(any(s.map == goal.map and s.f == (goal.f or "f") and
                                                abs(s.x - goal.x) <= .11 and abs(s.y - goal.y) <= .11
                                                for s in stages))
                        else:
                            # A hearth needs a known destination inn, like a flight needs a landing.
                            self.assertTrue(any(s.title == goal.location for s in stages))

    def trip(self, source, departure, player_class="PALADIN"):
        destination = self.ns.guides[source].next
        saved = {"activeGuide": destination, "seen": True, "auto": False,
                 "duo": {"autoPair": False, "enabled": False},
                 "progress": {source: {"cursor": len(self.ns.guides[source].steps) + 1, "placed": True},
                              destination: {"cursor": 1, "placed": True, "confirmed": {"my-mark": True}}}}
        return TravelHost((departure.map, departure.x / 100, departure.y / 100), saved,
                          classes=(player_class, "HUNTER"))

    def test_duskwood_class_trainers_converge_at_the_same_boat(self):
        source = "forever/alliance/05-duskwood"
        stages = self.ns.GuideTravelRoutes[source].legs
        by_id = {leg.id: leg for leg in stages.values()}
        traveler = self.trip(source, by_id["tinker-town"], "SHAMAN")
        self.assertEqual(traveler.travel().id, "tinker-town")
        traveler.move((None, None, None), instance=369)
        self.assertEqual(traveler.travel().id, "tram")
        pier = by_id["sw-auber"]
        traveler.move((pier.map, pier.x / 100, pier.y / 100))
        hunter = self.trip(source, pier, "HUNTER")
        self.assertEqual(traveler.travel().id, hunter.travel().id)
        self.assertEqual(traveler.travel().id, "sw-auber")

    def test_dolanaar_and_ruttheran_share_a_map_but_require_different_departures(self):
        source = "forever/alliance/nightelf/01-teldrassil"
        inn = self.host.table({"map": 1438, "x": 55.62, "y": 59.79})
        traveler = self.trip(source, inn)
        upper = traveler.travel()
        self.assertEqual(upper.id, "rejoin-1438-1457")
        self.assertAlmostEqual(upper.point.x, .3632)
        self.assertAlmostEqual(upper.point.y, .5438)
        self.assertIn("Darnassus", upper.text)
        traveler.move((1457, .50, .52))
        self.assertEqual(traveler.travel().id, "darn-portal")
        traveler.move((1438, .5593, .8974))  # Actual portal landing below the tree.
        self.assertEqual(traveler.travel().id, "rut-auber")
        self.assertEqual(traveler.travel().point.mapID, 1438)

    def test_ground_recovery_via_darnassus_uses_portal_and_localized_area_evidence(self):
        source = "forever/alliance/nightelf/01-teldrassil"
        inn = self.host.table({"map": 1438, "x": 55.62, "y": 59.79})
        traveler = self.trip(source, inn)
        finder = traveler.ns.TravelRouting
        target = traveler.h.table([{"map": 1439}])
        def recovery():
            return finder.Rejoin(target, traveler.s.mapID, finder.Sample(traveler.s.mapID))

        self.assertEqual(recovery().id, "rejoin-1438-1457")
        traveler.move((1457, .85, .36))  # Closer to the road gate than the necessary portal.
        leg = recovery()
        self.assertEqual((leg.f, leg.x, leg.y), ("e", 29.13, 41.21))
        traveler.move((1438, .5587, .8934))
        self.assertEqual(recovery().id, "rejoin-1438-1439")
        traveler.h.lua.execute("""
            function GetSubZoneText() return TEST.localArea end
            function C_Map.GetAreaInfo(id)
                return ({ [702] = "Localized Rut'theran", [186] = "Localized Dolanaar" })[id]
            end
        """)
        # No altitude and outside known pins. A loading map alone cannot tell
        # us to walk across the cliff; the localized subzone can.
        traveler.s.height = None
        traveler.move((1438, .48, .69))
        self.assertIsNone(traveler.travel().point)
        traveler.s.localArea = "Localized Dolanaar"
        traveler.tick()
        self.assertEqual(traveler.travel().id, "rejoin-1438-1457")
        traveler.s.localArea = "Localized Rut'theran"
        traveler.tick()
        self.assertEqual(traveler.travel().id, "rut-auber")

    def test_flight_crossing_zone_does_not_satisfy_delivery_or_inn(self):
        source = "forever/alliance/06-ashenvale"
        route = self.ns.GuideTravelRoutes[source]
        player = self.trip(source, route.legs[1])
        guide = player.ns.guides[route.destination]
        end = route.legs[len(route.legs)]
        before = player.progress()
        def flight_complete():
            return player.ns.IsTravelServiceComplete(player.ns, guide, 1, 1)

        self.assertFalse(flight_complete())
        player.move((end.map, .20, .30))
        self.assertFalse(flight_complete(), "Crossing into Duskwood is not landing in Darkshire")
        player.h.lua.execute("function UnitOnTaxi() return TEST.inFlight end")
        player.s.inFlight = True
        player.move((end.map, end.x / 100, end.y / 100))
        self.assertFalse(flight_complete(), "The gryphon is still in the air over the destination")
        player.s.inFlight = False
        player.tick()
        self.assertTrue(flight_complete())
        for index in range(2, len(guide.steps[1].goals) + 1):
            self.assertFalse(player.ns.IsTravelServiceComplete(player.ns, guide, 1, index))
        self.assertEqual(player.progress(), before)

    def test_feralas_ferry_and_flight_wait_at_distinct_landings_on_the_same_map(self):
        source = "forever/alliance/40-50/03-feralas"
        route = self.ns.GuideTravelRoutes[source]
        departure, pier, master, landing = (route.legs[i] for i in range(1, 5))
        self.assertEqual(len({leg.map for leg in (departure, pier, master, landing)}), 1)

        def position(leg):
            return leg.map, leg.x / 100, leg.y / 100

        player = self.trip(source, departure)
        progress = player.progress()
        for _ in range(5):
            player.tick()
            self.assertEqual(player.travel().id, departure.id)
        midpoint = (departure.map, (departure.x + pier.x) / 200, (departure.y + pier.y) / 200)
        player.move(midpoint)
        self.assertEqual(player.travel().id, departure.id)
        self.assertIsNone(player.pin(), "The ferry must not point back to its departure pier while crossing")
        player.move(position(pier))
        self.assertEqual(player.travel().id, master.id)
        player.move(position(master))
        for _ in range(5):
            player.tick()
            self.assertEqual(player.travel().id, master.id)
        player.h.lua.execute("function UnitOnTaxi() return TEST.inFlight end")
        player.s.inFlight = True
        player.move(position(landing))
        self.assertEqual(player.travel().id, "in-flight")
        player.s.inFlight = False
        player.tick()
        self.assertEqual(player.travel().id, route.legs[5].id)
        self.assertEqual(player.progress(), progress)


if __name__ == "__main__":
    unittest.main()
