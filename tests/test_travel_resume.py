"""Exercise saved handoffs and physical waypoint selection through the installed TOC."""
import unittest

from test_westfall_travel import DWARF, WEST, IRONFORGE, TravelHost, old_save


class TravelResumeTests(unittest.TestCase):
    def test_all_itineraries_reach_their_endpoint_without_setting_quest_flags(self):
        player = TravelHost(IRONFORGE, old_save(auto=False))
        ns = player.ns
        # The usual test client uses Era rectangles. Forever-only Skyborne
        # supplies live coordinates and has no Era rectangle to look up.
        player.h.lua.execute("""
            local world = C_Map.GetWorldPosFromMapPos
            function C_Map.GetWorldPosFromMapPos(map, p)
                if map ~= 2521 then return world(map, p) end
                local x,y = p:GetXY()
                return 711,CreateVector2D(-5000*y,-5000*x)
            end
        """)
        for source, route in ns.GuideTravelRoutes.items():
            dest = route.destination
            with self.subTest(source=source):
                player.s.faction = ns.guides[source].faction
                ns.char.activeGuide = source
                ns.char.guideTrips = player.h.table({})
                ns.char.progress = player.h.table({source: {"cursor": len(ns.guides[source].steps) + 1, "placed": True}})
                player.s.mapID, player.s.instance = None, None
                ns.ApplyGuideContinuation(ns, ns.guides[dest])
                self.assertEqual(ns.char.travelOrigins[dest], source)
                for i in range(1, len(route.legs) + 1):
                    leg = route.legs[i]
                    if leg.instanceID:
                        player.move((None, None, None), instance=leg.instanceID)
                    else:
                        player.move((leg.map, leg.x / 100, leg.y / 100))
                    if i < len(route.legs):
                        self.assertIsNotNone(player.travel(), leg.id)
                        self.assertFalse(ns.GetGuideTravelSignal(ns)[2], leg.id)
                        if player.pin():
                            self.assertEqual(player.pin().mapID, leg.map, leg.id)
                self.assertIsNone(player.travel())
                signal = ns.GetGuideTravelSignal(ns)
                self.assertEqual(signal[:4], (dest, len(route.legs), True, source))
                self.assertEqual(ns.char.progress[dest].cursor, 1)
                self.assertEqual(dict(ns.char.progress[dest].confirmed), {})

    def test_legacy_skip_is_migrated_without_claiming_arrival(self):
        saved = old_save(WEST)
        saved["westfallTravel"] = {"leg": "tinker-town", "skipped": True}
        h = TravelHost(IRONFORGE, saved)
        self.assertIsNone(h.travel())
        self.assertFalse(h.ns.GetGuideTravelSignal(h.ns)[2])
        self.assertTrue(h.ns.char.guideTrips[DWARF].skipped)
        h.arrive()
        self.assertTrue(h.ns.GetGuideTravelSignal(h.ns)[2])
        self.assertEqual(h.ns.char.progress[WEST].cursor, 1)

    def test_wrong_zone_points_to_a_local_exit_and_loading_preserves_progress(self):
        h = TravelHost((1432, .34, .51), old_save(WEST))
        self.assertTrue(h.travel().id.startswith("rejoin-1432-"))
        self.assertEqual(h.pin().mapID, 1432)
        self.assertEqual(h.ns.GetGuideTravelSignal(h.ns)[1:3], (0, False))
        h.s.positionUnavailable = True
        h.move((None, None, None))
        self.assertIsNone(h.pin())
        self.assertFalse(h.ns.GetGuideTravelSignal(h.ns)[2])
        h.s.positionUnavailable = False
        h.move(IRONFORGE)
        self.assertEqual(h.pin().mapID, 1455)
        self.assertEqual(h.ns.char.progress[WEST].cursor, 1)

    def test_real_position_withdraws_unpaired_arrival_if_early_player_leaves(self):
        save = old_save(WEST)
        save["duo"] = {"enabled": True, "autoPair": True, "wait": True}
        h = TravelHost(IRONFORGE, save, members=2)
        h.arrive()
        self.assertTrue(h.ns.GetGuideTravelSignal(h.ns)[2])
        h.move((None, None, None), instance=369)
        self.assertFalse(h.ns.GetGuideTravelSignal(h.ns)[2])
        self.assertEqual(h.travel().id, "tram")
        h.move(IRONFORGE)
        self.assertFalse(h.ns.GetGuideTravelSignal(h.ns)[2])
        self.assertEqual(h.pin().mapID, 1455)

    def test_explicit_guide_restart_clears_the_old_trip_receipt(self):
        h = TravelHost(IRONFORGE, old_save(WEST))
        h.arrive()
        h.ns.ResetGuide(h.ns, WEST)
        self.assertIsNone(h.ns.char.guideTrips[DWARF])
        self.assertIsNone(h.travel(), "Reviewing a guide does not start a trip")
        h.ns.char.progress[WEST].review = False
        h.move(IRONFORGE)
        self.assertEqual(h.pin().mapID, 1455)
        self.assertFalse(h.ns.GetGuideTravelSignal(h.ns)[2])


if __name__ == "__main__":
    unittest.main()
