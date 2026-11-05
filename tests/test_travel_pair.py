"""Two full addon clients exchange physically observed trip checkpoints on PARTY."""

import unittest

from test_auto_party_integration import AutomaticPartyHost, ROUTE_ID
from test_westfall_travel import DWARF, GOLDSHIRE, IRONFORGE, WEST, TravelHost


SOURCE = "travel-test/source"
SECOND_SOURCE = "travel-test/other-source"
SECOND_DEST = "travel-test/other-destination"
HUB = "1436:55.9:49.8"


class TravelPairTests(unittest.TestCase):
    def pair(self, source=SOURCE, destination=ROUTE_ID):
        a, b = AutomaticPartyHost(), AutomaticPartyHost("Dos", "Uno")
        for h in (a, b):
            for route_id in (SOURCE, SECOND_SOURCE, SECOND_DEST):
                h.register_route(route_id)
            h.ns.guides[SOURCE].next = ROUTE_ID
            h.ns.guides[SECOND_SOURCE].nextChoices = h.h.table([ROUTE_ID, SECOND_DEST])
            self.position(h, destination)
            h.ns.char.duo.autoPair, h.ns.char.duo.enabled, h.ns.char.duo.wait = False, True, True
            h.ns.char.auto = False
            # Isolate the comparison with explicit location observations. The
            # route engine has its own tests with actual map positions.
            h.h.lua.execute("""
                function NS:GetGuideTravelSignal()
                    return TEST.dest, TEST.reached, TEST.arrived, TEST.origin, TEST.hub
                end
            """)
            h.s.dest, h.s.origin, h.s.reached, h.s.arrived, h.s.hub = destination, source, 0, False, HUB
            h.roster()
        return a, b

    def position(self, h, guide, cursor=1):
        h.ns.char.activeGuide = guide
        h.ns.char.progress[guide] = h.h.table({"cursor": cursor, "placed": True,
            "confirmed": {"mine": True}, "skipped": {"mine-too": True}})
        h.ns.Duo.lastSentHeader = None

    def exchange(self, a, b, ticks=14):
        for _ in range(ticks):
            a.tick(); b.tick()
            self.assertLessEqual(len(a.s.outgoing), 1)
            self.assertLessEqual(len(b.s.outgoing), 1)
            a.deliver(b); b.deliver(a)

    def wait(self, h, done=False):
        return h.ns.Duo.GetTravelWait(h.ns.Duo, h.s.dest, h.s.origin, h.s.reached, done, h.s.hub)

    def ctx(self, h):
        return h.ns.Duo.GetContext(h.ns.Duo)

    def receive(self, h, *fields, nonce=None, kind="T"):
        peer = h.ns.Duo.peer
        message = "|".join(map(str, ("2", kind, nonce or peer.nonce, peer.sequence + 1, *fields)))
        return h.ns.Duo.Receive(h.ns.Duo, h.ns.Duo.prefix, message, "PARTY", h.s.friendName + "-Forever")

    def test_only_observed_checkpoint_or_arrival_releases_leader(self):
        a, b = self.pair()
        for h in (a, b):
            h.s.mapID = 1436
        a.s.reached, b.s.reached = 4, 1
        before = [h.progress() for h in (a, b)]
        self.exchange(a, b)
        self.assertTrue(self.wait(a))
        self.assertIsNone(self.wait(b))
        self.assertEqual(self.ctx(a).partnerTravel.legIndex, 1)
        self.assertTrue(any(p["kind"] == "T" and len(p["message"].split("|")) == 9 for p in a.packets))
        b.s.reached = 4
        self.exchange(a, b)
        self.assertIsNone(self.wait(a))
        a.s.arrived = True
        self.exchange(a, b)
        self.assertTrue(self.wait(a, done=True))
        b.s.arrived = True
        self.exchange(a, b)
        self.assertIsNone(self.wait(a, done=True))
        self.assertIsNone(self.wait(b, done=True))
        self.assertEqual([h.progress() for h in (a, b)], before)

    def test_class_variants_and_different_starters_compare_only_meaningful_milestones(self):
        a, b = self.pair()
        a.s.reached, b.s.reached = 4, 1
        b.s.origin = SECOND_SOURCE
        self.exchange(a, b)
        self.assertIsNone(self.wait(a))
        self.assertTrue(self.wait(a, done=True))
        b.s.arrived = True
        self.exchange(a, b)
        self.assertIsNone(self.wait(a, done=True))  # Different path, same actual hub.
        b.s.hub = "1436:42:31"
        self.exchange(a, b)
        self.assertTrue(self.wait(a, done=True))
        b.s.origin = SOURCE
        self.exchange(a, b)
        self.assertIsNone(self.wait(a, done=True))  # Partner finished their own class variant.
        b.s.arrived = False
        self.exchange(a, b)
        self.assertIsNone(self.wait(a))  # Different variant leg numbers are incomparable.
        self.assertTrue(self.wait(a, done=True))

    def test_wrong_destination_sender_session_unfinished_origin_or_stale_header_cannot_ack(self):
        a, b = self.pair()
        self.exchange(a, b)
        self.assertFalse(self.receive(a, SOURCE, SECOND_DEST, 1, 1, HUB))  # Not a real edge.
        self.assertFalse(self.receive(a, SECOND_SOURCE, SECOND_DEST, 1, 1, HUB))  # Other active route.
        self.assertFalse(self.receive(a, SOURCE, ROUTE_ID, "999999", 1, HUB))
        self.assertFalse(self.receive(a, SOURCE, ROUTE_ID, 1, "?", HUB))
        self.assertFalse(self.receive(a, SOURCE, ROUTE_ID, 1, 1, HUB, nonce="old-session"))
        self.assertTrue(self.wait(a, done=True))
        self.position(b, SOURCE, 2)  # Three quest steps. The source still has quests.
        self.exchange(a, b)
        self.assertFalse(self.receive(a, SOURCE, ROUTE_ID, 1, 1, HUB))
        self.position(b, SOURCE, 4)
        self.exchange(a, b)
        self.assertTrue(self.receive(a, SOURCE, ROUTE_ID, 1, 1, HUB))
        self.assertIsNone(self.wait(a, done=True))
        a.s.now += 20
        self.assertIsNone(self.ctx(a).partnerTravel)
        self.assertFalse(self.receive(a, SOURCE, ROUTE_ID, 1, 1, HUB))
        self.assertTrue(self.wait(a, done=True))

    def test_review_and_nonce_rotation_drop_an_old_ready_signal_even_on_the_same_guide(self):
        a, b = self.pair()
        b.s.arrived = True
        self.exchange(a, b)
        self.assertIsNone(self.wait(a, done=True))
        old_nonce = b.ns.Duo.nonce
        b.ns.Duo.nonce, b.ns.Duo.lastSentHeader, b.s.arrived = "fresh-session", None, False
        self.exchange(a, b, 1)
        self.assertTrue(self.wait(a, done=True))
        self.assertFalse(self.receive(a, SOURCE, ROUTE_ID, 2, 1, HUB, nonce=old_nonce))
        b.s.arrived = True
        self.exchange(a, b)
        b.ns.char.progress[ROUTE_ID].review = True
        b.ns.Duo.lastSentHeader = None
        self.exchange(a, b, 1)
        self.assertTrue(self.wait(a, done=True))
        self.assertIsNone(self.ctx(a).partnerTravel)

    def test_old_westfall_protocol_acknowledges_the_hill_only(self):
        a, b = self.pair(DWARF, WEST)
        b.ns.GetGuideTravelSignal = None
        b.ns.GetWestfallTravelSignal = b.h.lua.eval("function() return 1 end")
        self.exchange(a, b, 20)
        self.assertTrue(self.ctx(a).partnerTravel.legacy)
        self.assertIsNone(self.wait(a, done=True))
        self.assertTrue(any(p["kind"] == "T" and len(p["message"].split("|")) == 6 for p in a.packets))
        self.position(b, SECOND_DEST)
        self.exchange(a, b)
        self.assertFalse(self.receive(a, SECOND_DEST, 1))
        self.assertTrue(self.wait(a, done=True))

    def test_stopping_quest_wait_or_leaving_the_party_releases_personal_wait(self):
        a, b = self.pair()
        a.s.reached = 3
        self.exchange(a, b)
        self.assertTrue(self.wait(a))
        a.ns.char.duo.wait = False
        self.assertIsNone(self.wait(a, done=True))
        a.ns.char.duo.autoPair = True
        self.assertTrue(self.wait(a, done=True))
        a.roster(0)
        self.assertIsNone(self.wait(a, done=True))
        self.assertIsNone(self.ctx(a).partnerTravel)

    def test_real_alliance_and_horde_handoffs_regroup_at_border_then_at_quest_hub(self):
        cases = (
            ("Alliance", "Human", ("PALADIN", "WARRIOR"),
             "forever/alliance/human/01-elwynn-forest", 73, WEST,
             (1429, .42, .66), (1429, .2230, .7820), (1436, .609, .19), (1436, .559, .498)),
            ("Horde", "Tauren", ("SHAMAN", "HUNTER"),
             "forever/horde/tauren/01-mulgore", 59, "forever/horde/02-the-barrens",
             (1412, .4593, .6416), (1412, .6859, .6059), (1413, .457, .61), (1413, .515, .3034)),
        )
        for faction, race, classes, source, finished, destination, start, border, road, hub in cases:
            with self.subTest(source=source):
                def member(name, friend):
                    saved = {"seen": True, "activeGuide": source, "auto": True,
                             "duo": {"enabled": True, "autoPair": True, "wait": True},
                             "progress": {
                                 source: {"cursor": finished, "placed": True, "confirmed": {name: True}},
                                 destination: {"cursor": 1, "placed": True, "skipped": {name: True}},
                             }}
                    return TravelHost(start, saved, name, friend, members=2,
                                      race=race, faction=faction, classes=classes)

                a, b = member("Uno", "Dos"), member("Dos", "Uno")
                self.exchange(a, b, 70)
                for h in (a, b):
                    self.assertEqual(h.ns.char.activeGuide, destination)
                    self.assertEqual(h.pin().mapID, start[0])
                    self.assertEqual(self.ctx(h).partnerTravel.destinationID, destination)

                a.move(border)
                a.deliver(b)
                self.exchange(a, b)
                self.assertTrue(a.travel().waiting, "The other player is still on the road to the border")
                self.assertFalse(bool(b.travel().waiting))

                b.move(border)
                b.deliver(a)
                self.exchange(a, b)
                self.assertFalse(bool(a.travel().waiting))
                self.assertFalse(bool(b.travel().waiting))
                a.move(hub)
                a.deliver(b)
                b.move(road)
                b.deliver(a)
                self.exchange(a, b)
                self.assertTrue(a.travel().waiting, "Entering the destination map does not reach its quest hub")
                self.assertIsNotNone(b.pin())

                b.move(hub)
                b.deliver(a)
                self.exchange(a, b, 35)
                for h in (a, b):
                    self.assertIsNone(h.travel())
                    self.assertEqual(h.ns.char.progress[source].cursor, finished)
                    self.assertEqual(h.ns.char.progress[destination].cursor, 1)
                    self.assertEqual(dict(h.ns.char.progress[source].confirmed), {h.s.playerName: True})
                    self.assertEqual(dict(h.ns.char.progress[destination].skipped), {h.s.playerName: True})

    def test_different_starters_agree_after_each_finishes_and_release_at_same_hub(self):
        human = "forever/alliance/human/01-elwynn-forest"

        def member(name, friend, race, friend_race, location, source, cursor):
            saved = {"seen": True, "activeGuide": source, "auto": True,
                     "duo": {"enabled": True, "autoPair": True, "wait": True},
                     "progress": {source: {"cursor": cursor, "placed": True, "confirmed": {name: True}},
                                  WEST: {"cursor": 1, "placed": True}}}
            h = TravelHost(location, saved, name, friend, members=2, race=race, classes=("WARRIOR", "PALADIN"))
            h.s.friendRace = friend_race
            return h

        a = member("Uno", "Dos", "Human", "Dwarf", GOLDSHIRE, human, 73)
        b = member("Dos", "Uno", "Dwarf", "Human", IRONFORGE, DWARF, 70)
        self.exchange(a, b, 30)
        self.assertEqual(a.ns.char.activeGuide, human)
        self.assertEqual((b.ns.char.activeGuide, b.ns.char.progress[DWARF].cursor), (DWARF, 70))
        self.assertTrue(a.travel().waiting, "The paladin still has class quests in their own starter")
        self.assertIsNone(a.pin())
        b.ns.char.progress[DWARF].cursor = 81
        b.ns.Duo.lastSentHeader = None
        b.ns.Sync(b.ns)
        self.exchange(a, b, 70)
        for h, source, start in ((a, human, GOLDSHIRE), (b, DWARF, IRONFORGE)):
            self.assertEqual((h.ns.char.activeGuide, h.ns.char.travelOrigins[WEST]), (WEST, source))
            self.assertEqual(h.pin().mapID, start[0])
        self.assertTrue(any(p["kind"] == "N" and p["message"].split("|")[6:8] == ["1", "1"]
                            for h in (a, b) for p in h.packets))
        a.arrive()
        a.deliver(b)
        self.exchange(a, b)
        self.assertTrue(a.travel().waiting)
        self.assertEqual(self.ctx(a).partnerTravel.sourceID, DWARF)
        self.assertEqual(self.ctx(b).partnerTravel.sourceID, human)
        self.assertEqual(b.pin().mapID, IRONFORGE[0])
        for h in (a, b):
            self.assertEqual(h.ns.char.progress[WEST].cursor, 1)
            self.assertFalse(h.ns.WantsQuest(h.ns, "accept", 6181), "First quest is inactive while travelling")
        b.arrive()
        b.deliver(a)
        self.exchange(a, b, 40)
        for h, origin in ((a, human), (b, DWARF)):
            self.assertIsNone(h.travel())
            self.assertEqual(h.ns.char.progress[WEST].cursor, 1)
            self.assertEqual(dict(h.ns.char.progress[origin].confirmed), {h.s.playerName: True})
        self.assertTrue(a.ns.WantsQuest(a.ns, "accept", 6181), "Human opener is now active")
        self.assertFalse(b.ns.WantsQuest(b.ns, "accept", 6181), "The dwarf keeps their applicable goals")

    def test_orc_finishes_private_barrens_chapter_before_joining_tauren_at_the_crossroads(self):
        orc = "forever/horde/orc-troll/01-durotar"
        tauren = "forever/horde/tauren/01-mulgore"
        private = "forever/horde/orc-troll/02-the-barrens"
        common = "forever/horde/02-the-barrens"
        crossroads = (1413, .515, .3034)

        def member(name, friend, race, other_race, source, start):
            saved = {"seen": True, "activeGuide": source, "auto": True,
                     "duo": {"enabled": True, "autoPair": True, "wait": True},
                     "progress": {source: {"cursor": 2, "placed": True, "confirmed": {name: True}},
                                  common: {"cursor": 1, "placed": True},
                                  private: {"cursor": 1, "placed": True, "skipped": {name: True}}}}
            h = TravelHost(start, saved, name, friend, members=2, faction="Horde",
                           race=race, classes=("WARRIOR", "HUNTER"))
            h.s.friendRace = other_race
            return h

        def finish(h, source):
            h.ns.char.progress[source].cursor = len(h.ns.guides[source].steps) + 1
            h.ns.Duo.lastSentHeader = None
            h.ns.Sync(h.ns)

        a = member("Uno", "Dos", "Orc", "Tauren", orc, (1411, .51, .42))
        b = member("Dos", "Uno", "Tauren", "Orc", tauren, crossroads)
        finish(a, orc)
        self.exchange(a, b, 30)
        self.assertEqual(a.ns.char.activeGuide, orc)
        self.assertTrue(a.travel().waiting)
        finish(b, tauren)
        self.exchange(a, b, 55)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (private, tauren))
        self.assertEqual(a.pin().mapID, 1411)
        a.move((1413, .5223, .3101))  # Sergra, the orc/troll opener.
        a.deliver(b)
        self.exchange(a, b, 25)
        self.assertIsNone(a.travel(), "Sergra's personal chapter never requires a tauren to visit her")
        self.assertEqual(a.ns.char.activeGuide, private)
        self.assertEqual(b.ns.char.progress[private].cursor, 1)
        self.assertEqual(dict(b.ns.char.progress[private].skipped), {"Dos": True})
        self.assertEqual(b.ns.char.progress[common].cursor, 1)
        self.assertTrue(b.travel().waiting)
        self.assertEqual(b.ns.char.activeGuide, tauren)
        a.move((1413, .45, .55))
        a.deliver(b)
        finish(a, private)
        self.exchange(a, b, 55)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (common, common))
        self.assertEqual(a.ns.char.travelOrigins[common], private)
        self.assertEqual(b.ns.char.travelOrigins[common], tauren)
        self.assertTrue(b.travel().waiting)
        self.assertEqual(b.ns.char.progress[common].cursor, 1)
        a.move(crossroads)
        a.deliver(b)
        self.exchange(a, b, 35)
        for h, source in ((a, orc), (b, tauren)):
            self.assertIsNone(h.travel())
            self.assertEqual(h.ns.char.progress[common].cursor, 1)
            self.assertEqual(dict(h.ns.char.progress[source].confirmed), {h.s.playerName: True})


if __name__ == "__main__":
    unittest.main()
