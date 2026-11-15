"""Real boat arrivals travel over existing checkpoints, never inferred cursors."""
import unittest

from test_boat_navigation import BoatHost, GUIDE
from test_duo_journey import primitive_copy


LAND = (1445, .6746, .512)
DOCK = (1445, .7173, .5666)


class BoatDuoHost(BoatHost):
    def __init__(self, player="Uno", friend="Dos"):
        super().__init__()
        self.s.playerName, self.s.friendName = player, friend
        self.s.members = 2
        self.s.friendLevel, self.s.friendClass, self.s.friendRace = 30, "ROGUE", "Human"
        self.duo = self.ns.Duo
        self.ns.char.duo.wait = True
        self.duo.SetEnabled(self.duo, True)

    def run(self):
        self.s.now += 1
        self.tick()
        self.duo.Tick(self.duo, 1)

    def deliver(self, other):
        for packet in self.s.outgoing.values():
            other.duo.Receive(other.duo, packet.prefix, packet.message, packet.channel,
                              self.s.playerName + "-Forever")
        self.s.outgoing = self.h.lua.table()

    def wait(self):
        return self.duo.GetStepWaitStatus(self.duo, self.step)

    def cursor(self):
        return self.ns.char.progress[GUIDE].cursor


class BoatDuoTests(unittest.TestCase):
    def pair(self):
        a, b = BoatDuoHost(), BoatDuoHost("Dos", "Uno")
        self.exchange(a, b)
        return a, b

    def exchange(self, a, b, ticks=15):
        for _ in range(ticks):
            a.run(); b.run(); a.deliver(b); b.deliver(a)

    def test_waits_for_real_disembarkation_then_both_advance_without_deadlock(self):
        a, b = self.pair()
        a.move(LAND)
        self.exchange(a, b)
        self.assertTrue(a.complete())
        self.assertFalse(b.complete())
        self.assertEqual(a.cursor(), 31)
        self.assertTrue(a.wait().waiting)
        b.move(DOCK)
        self.exchange(a, b)
        self.assertFalse(b.complete())
        self.assertEqual((a.cursor(), b.cursor()), (31, 31))
        b.move(LAND)
        self.exchange(a, b, 25)
        self.assertEqual((a.cursor(), b.cursor()), (33, 33))
        self.assertTrue(a.complete() and b.complete())
        self.assertFalse(a.ns.IsQuestDelivered(a.ns, 474))

    def test_advanced_client_repeats_durable_arrival_for_lagging_peer(self):
        a, b = self.pair()
        a.ns.char.duo.wait = False
        a.move(LAND)
        a.run()
        self.assertEqual(a.cursor(), 33)
        a.ns.char.duo.wait = True
        self.exchange(a, b)
        checkpoint = a.duo.GetBoatCheckpoint(a.duo)
        self.assertEqual(checkpoint.cursor, 31)
        self.assertTrue(checkpoint.stopReady)
        b.move(LAND)
        self.exchange(a, b, 25)
        self.assertEqual((a.cursor(), b.cursor()), (33, 33))

    def test_cursor_or_same_map_alone_never_confirms_partner_arrival(self):
        a, b = self.pair()
        a.ns.char.progress[GUIDE].cursor = 33  # Deliberate manual omission.
        a.move(DOCK)
        b.move(LAND)
        self.exchange(a, b, 25)
        self.assertFalse(a.complete())
        self.assertTrue(b.complete())
        self.assertEqual(b.cursor(), 31)
        self.assertTrue(b.wait().waiting)
        self.assertFalse(b.wait().unknown)

    def test_restricted_stale_or_wrong_checkpoint_stays_unknown(self):
        a, b = self.pair()
        a.s.restricted = True
        b.move(LAND)
        self.exchange(a, b, 25)
        self.assertTrue(b.wait().waiting)
        self.assertTrue(b.wait().unknown)
        self.assertEqual(b.cursor(), 31)
        a.s.restricted = False
        self.exchange(a, b)
        checkpoint = a.duo.GetBoatCheckpoint(a.duo)
        peer = b.duo.peer
        wrong_frame = checkpoint.checkpointID.replace(".e.", ".l.", 1)
        self.assertNotEqual(wrong_frame, checkpoint.checkpointID)
        for key in (checkpoint.checkpointID + ".wrong", wrong_frame):
            message = "|".join(map(str, ["2", "C", peer.nonce, peer.sequence + 1, GUIDE, 31,
                                             key, "boat", 1, 1445, 30]))
            self.assertFalse(b.duo.Receive(b.duo, "RXPDUO3", message, "PARTY", "Uno-Forever"))
        self.assertTrue(b.wait().waiting)

    def test_shared_boat_preview_never_records_arrival_or_routes_arrived_player_back(self):
        a, b = self.pair()
        planner = a.ns.DuoPlanner
        point = planner.GetSharedWaypoint(planner, GUIDE, 31)
        if isinstance(point, tuple):
            point = point[0]
        self.assertEqual(point.mapID, 1437)
        a.move(LAND)
        before = primitive_copy(a.ns.char)
        planner.GetSharedWaypoint(planner, GUIDE, 31)
        self.assertEqual(primitive_copy(a.ns.char), before)
        self.assertFalse(a.complete())
        a.run()
        point, reason = planner.GetSharedWaypoint(planner, GUIDE, 31)
        self.assertIsNone(point)
        self.assertIn("Espera", reason)


if __name__ == "__main__":
    unittest.main()
