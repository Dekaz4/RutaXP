"""A missing flight path must leave a physical route and the shared cursor intact."""

import unittest

from test_duo_journey import primitive_copy
from test_westfall_travel import TravelHost


def host(source, destination, location, faction="Horde", saved=None):
    save = saved or {
        "seen": True, "activeGuide": destination, "auto": True,
        "travelOrigins": {destination: source}, "duo": {"autoPair": False, "enabled": False},
        "progress": {
            source: {"placed": True, "cursor": 999, "confirmed": {"personal": True}},
            destination: {"placed": True, "cursor": 1},
        },
    }
    return TravelHost(location, save, faction=faction, race="Orc" if faction == "Horde" else "Dwarf")


class GroundDetourTests(unittest.TestCase):
    def test_cross_zone_button_reload_and_resume_after_reaching_master(self):
        source, dest = "forever/horde/03-silverpine-forest", "forever/horde/04-the-barrens"
        h = host(source, dest, (1454, .56, .35))
        self.assertIsNone(h.travel().groundOption)
        h.move((1454, .4528, .6375))
        self.assertEqual(h.ns.trackerNext.GetText(h.ns.trackerNext), "Ir sin vuelo")
        h.h.g.Click(h.ns.trackerNext)
        self.assertEqual(h.pin().mapID, 1454)
        self.assertTrue(h.travel().id.endswith("rejoin-1454-1413"))
        checkpoint = h.ns.char.guideTrips[source].reached

        h = host(source, dest, (1413, .64, .19), saved=primitive_copy(h.ns.char))
        self.assertEqual(h.pin().mapID, 1413)
        self.assertEqual(h.travel().title, "Trinquete")
        self.assertEqual(h.ns.char.guideTrips[source].reached, checkpoint)
        self.assertEqual(h.ns.char.progress[dest].cursor, 1)
        h.move((1413, .6312, .3711))
        self.assertIsNone(h.ns.char.guideTrips[source].groundDetour)
        self.assertTrue(h.ns.char.progress[source].confirmed["personal"])

    def test_same_map_booking_is_replaced_with_actual_road(self):
        source = "forever/horde/30-40/03-arathi-highlands"
        dest = "forever/horde/30-40/04-dustwallow-marsh"
        h = host(source, dest, (1413, .6312, .3711))
        h.h.g.Click(h.ns.nextButton)
        self.assertIn("gold-road", h.travel().id)
        h.move((1413, .515, .3041))
        self.assertEqual(h.travel().title, "Campamento Taurajo")
        self.assertTrue(h.ns.char.guideTrips[source].groundDetour)
        h.move((1413, .4446, .591))
        self.assertIsNone(h.ns.char.guideTrips[source].groundDetour)
        self.assertEqual(h.travel().id, "dustwallow-road")
        self.assertEqual(h.ns.char.progress[dest].cursor, 1)

    def test_feathermoon_island_requires_the_ferry_before_the_inland_road(self):
        source = "forever/alliance/40-50/03-feralas"
        dest = "forever/alliance/40-50/04-tanaris"
        h = host(source, dest, (1444, .3026, .4332), "Alliance")
        self.assertTrue(h.ns.BeginGroundDetour(h.ns))
        self.assertIn("island-ferry", h.travel().id)
        h.move((1444, .3101, .3951))
        self.assertIsNone(h.travel().point)
        self.assertIn("Embarca", h.travel().text)
        h.move((1444, .4313, .4276))
        self.assertEqual(h.travel().title, "Thalanaar")
        self.assertTrue(h.ns.char.guideTrips[source].groundDetour)
        h.move((1444, .8946, .4587))
        self.assertIsNone(h.ns.char.guideTrips[source].groundDetour)
        self.assertEqual(h.ns.char.progress[dest].cursor, 1)

    def test_unknown_same_map_flight_and_normal_boat_never_offer_land_route(self):
        source, dest = "forever/horde/03-silverpine-forest", "forever/horde/04-the-barrens"
        h = host(source, dest, (1454, .4528, .6375))
        unknown = h.h.table({"id": "unknown-island", "map": 1454, "x": 45.28, "y": 63.75,
                             "f": "e", "radius": 32, "taxiLanding": {"map": 1454}})
        sample = h.ns.TravelRouting.Sample(1454)
        self.assertFalse(h.ns.CanGroundDetour(h.ns, unknown, 1454, sample))
        unknown.taxiLanding = None
        self.assertFalse(h.ns.CanGroundDetour(h.ns, unknown, 1454, sample))
