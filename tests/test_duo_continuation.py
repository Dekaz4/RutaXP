"""Two shipping TOCs negotiate linked routes without sharing saved progress."""
import unittest

from test_auto_party_integration import AutomaticPartyHost, ROUTE_ID, QUEST_ID
from test_duo_journey import primitive_copy


NEXT = "auto-review/successor"
DWARF = "forever/alliance/dwarf-gnome/01-dun-morogh"


class ContinuationHost(AutomaticPartyHost):
    def __init__(self, name="Uno", friend="Dos", automatic=True, pairing=False):
        super().__init__(name, friend, cursor=2, review=False, auto=False)
        self.register_route(NEXT, quest_id=QUEST_ID + 20)
        self.ns.guides[ROUTE_ID].next = NEXT
        self.ns.char.duo.enabled = self.ns.char.duo.wait = True
        self.ns.char.duo.autoPair = pairing
        self.ns.char.auto = automatic

    def finish(self):
        self.quest(delivered=True, count=8)
        self.ns.char.progress[ROUTE_ID].cursor = 4
        self.ns.Duo.lastSentHeader = None

    def target_progress(self, cursor=2, review=True):
        self.ns.char.progress[NEXT] = self.h.table({
            "cursor": cursor, "review": review, "placed": True,
            "confirmed": {"old-confirmation": True}, "skipped": {"old-omission": True},
        })


class DuoContinuationTests(unittest.TestCase):
    def pair(self, **options):
        a, b = ContinuationHost(**options), ContinuationHost("Dos", "Uno", **options)
        a.roster(); b.roster()
        return a, b

    def exchange(self, a, b, ticks=45, drop=None):
        for _ in range(ticks):
            a.tick(); b.tick()
            for sender, receiver in ((a, b), (b, a)):
                self.assertLessEqual(len(sender.s.outgoing), 1)
                if drop:
                    for index, packet in list(sender.s.outgoing.items()):
                        if drop(sender, receiver, packet.message.split("|")):
                            sender.s.outgoing[index] = None
                sender.deliver(receiver)
            self.assertLessEqual(a.s.maxSyncDepth, 2)
            self.assertLessEqual(b.s.maxSyncDepth, 2)

    def state(self, host):
        return host.ns.DuoAuto.GetContinuationState(host.ns.DuoAuto, host.ns.guides[ROUTE_ID])

    def request(self, host):
        return host.ns.DuoAuto.RequestContinuation(host.ns.DuoAuto, host.ns.guides[ROUTE_ID])

    def test_manual_wait_advances_only_after_both_finish_and_preserves_destination(self):
        a, b = self.pair()
        a.target_progress(2); b.target_progress(1)
        before = [primitive_copy(h.ns.char.progress[NEXT]) for h in (a, b)]
        a.finish()
        self.exchange(a, b, 30)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (ROUTE_ID, ROUTE_ID))
        managed, reason, can_request = self.state(a)
        self.assertTrue(managed); self.assertFalse(can_request)
        self.assertIn("compañero", reason)
        b.finish(); self.exchange(a, b)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (NEXT, NEXT))
        for h, expected in zip((a, b), before):
            self.assertEqual(primitive_copy(h.ns.char.progress[NEXT]), expected)
            self.assertEqual(h.ns.char.progress[ROUTE_ID].cursor, 4)
            self.assertTrue(h.ns.char.progress[ROUTE_ID].confirmed["user-confirmed"])
            self.assertTrue(h.ns.char.progress[ROUTE_ID].skipped["user-skipped"])
            self.assertFalse(h.ns.char.duo.autoPair)
            self.assertIsNone(h.ns.char.duo.autoSession)
        self.assertTrue(any(p["kind"] == "N" for h in (a, b) for p in h.packets))

    def test_grouped_autopair_holds_finished_save_before_first_handshake(self):
        a, b = self.pair(pairing=True)
        a.ns.char.duo.enabled = False
        a.finish()
        a.ns.Sync(a.ns)
        self.assertEqual(a.ns.char.activeGuide, ROUTE_ID)
        managed, reason, can_request = self.state(a)
        self.assertTrue(managed)
        self.assertIn("cabecera reciente", reason)
        self.assertFalse(can_request)

    def test_manual_auto_off_requires_each_local_consent_without_changing_settings(self):
        a, b = self.pair(automatic=False)
        a.finish(); b.finish()
        self.exchange(a, b, 25)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (ROUTE_ID, ROUTE_ID))
        self.assertEqual(self.state(a)[::2], (True, True))
        self.assertTrue(self.request(a)[0])
        self.exchange(a, b, 12)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (ROUTE_ID, ROUTE_ID))
        self.assertTrue(self.request(b)[0])
        self.exchange(a, b)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (NEXT, NEXT))
        for h in (a, b):
            self.assertFalse(h.ns.char.auto)
            self.assertFalse(h.ns.char.duo.autoPair)
            self.assertTrue(h.ns.char.duo.wait)
            self.assertEqual(h.ns.char.progress[NEXT].cursor, 1)
            self.assertEqual(primitive_copy(h.ns.char.progress[NEXT].confirmed), {})

    def test_automatic_pair_changes_agreement_without_rewinding_saved_successor(self):
        a, b = self.pair(pairing=True)
        self.exchange(a, b, 65)
        self.assertTrue(a.status().active); self.assertTrue(b.status().active)
        a.target_progress(3, review=False); b.target_progress(2, review=False)
        before = [primitive_copy(h.ns.char.progress[NEXT]) for h in (a, b)]
        a.finish(); self.exchange(a, b, 12)
        self.assertEqual(a.ns.char.activeGuide, ROUTE_ID)
        self.assertTrue(a.view().following)
        b.finish(); self.exchange(a, b, 55)
        for h, expected in zip((a, b), before):
            self.assertEqual(h.ns.char.activeGuide, NEXT)
            self.assertEqual(primitive_copy(h.ns.char.progress[NEXT]), expected)
            self.assertTrue(h.ns.char.duo.autoPair)
            self.assertEqual(h.view().guideID, NEXT)
        self.assertTrue(a.view().following)
        self.assertEqual((a.view().ownCursor, a.view().sharedCursor), (3, 2))

    def test_simultaneous_manual_requests_choose_one_transaction_and_converge(self):
        a, b = self.pair(automatic=False)
        a.finish(); b.finish(); self.exchange(a, b, 12)
        self.assertTrue(self.request(a)[0]); self.assertTrue(self.request(b)[0])
        # Separate clients may generate the same nonce/counter. Ownership,
        # rather than a transaction string alone, must break that tie.
        self.assertEqual(a.ns.DuoAuto.continuation.packet.transaction, b.ns.DuoAuto.continuation.packet.transaction)
        self.exchange(a, b, 35)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (NEXT, NEXT))
        self.assertIsNone(a.ns.DuoAuto.continuation)
        self.assertIsNone(b.ns.DuoAuto.continuation)
        self.assertFalse(a.ns.char.auto); self.assertFalse(b.ns.char.auto)

    def test_peer_already_in_successor_does_not_leave_finished_manual_player_blocked(self):
        a, b = self.pair()
        a.target_progress(2); b.target_progress(1)
        a.ns.char.activeGuide = NEXT
        a.ns.Duo.lastSentHeader = None
        b.finish()
        before = primitive_copy(a.ns.char.progress[NEXT])
        self.exchange(a, b, 55)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (NEXT, NEXT))
        self.assertEqual(primitive_copy(a.ns.char.progress[NEXT]), before)

    def test_old_receiver_ignoring_new_packets_cannot_trigger_unilateral_change(self):
        a, b = self.pair()
        a.finish(); b.finish()
        self.exchange(a, b, 75, drop=lambda s, r, f: f[1] in ("N", "K"))
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (ROUTE_ID, ROUTE_ID))
        self.assertTrue(self.state(a)[0])
        self.assertTrue(self.state(a)[1])

    def test_review_race_mismatch_and_disabled_duo_never_auto_commit(self):
        for mode in ("review", "race", "duo"):
            with self.subTest(mode=mode):
                a, b = self.pair()
                a.finish(); b.finish()
                if mode == "review":
                    b.ns.char.progress[ROUTE_ID].review = True
                elif mode == "race":
                    a.ns.guides[NEXT].races = a.h.table(["Human"])
                    b.ns.guides[NEXT].races = b.h.table(["Human"])
                    a.s.friendRace = b.s.raceToken = "Dwarf"
                else:
                    a.ns.char.duo.enabled = b.ns.char.duo.enabled = False
                self.exchange(a, b, 35)
                if mode != "duo":
                    self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (ROUTE_ID, ROUTE_ID))
                self.assertFalse(any(p["kind"] in ("N", "K") for h in (a, b) for p in h.packets))

    def test_terminal_route_names_pending_partner_then_finishes_without_an_agreement(self):
        a, b = self.pair()
        for h in (a, b):
            h.ns.guides[ROUTE_ID].next = None
        a.finish(); self.exchange(a, b, 15)
        managed, reason, can_request = self.state(a)
        self.assertTrue(managed); self.assertFalse(can_request)
        self.assertIn("Objetivo del compañero", reason)
        self.assertIn("2/3", reason)
        b.finish(); self.exchange(a, b, 15)
        for h in (a, b):
            self.assertFalse(self.state(h)[0])
            self.assertFalse(self.state(h)[2])
            self.assertEqual(h.ns.char.activeGuide, ROUTE_ID)
            self.assertEqual(h.ns.char.progress[ROUTE_ID].cursor, 4)
            self.assertFalse(any(p["kind"] in ("N", "K") for p in h.packets))

    def test_lost_commit_ack_retries_after_first_player_changed_guide(self):
        a, b = self.pair()
        a.finish(); b.finish()
        dropped = []
        def drop(sender, receiver, fields):
            if fields[1] == "K" and fields[8] == "2" and not dropped:
                dropped.append(True)
                return True
            return False
        self.exchange(a, b, 25, drop=drop)
        self.assertTrue(dropped)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (NEXT, NEXT))
        self.assertIsNone(a.ns.DuoAuto.continuation)
        self.assertIsNone(b.ns.DuoAuto.continuation)
        self.assertIsNone(a.ns.DuoAuto.continuationRetryAt)
        self.assertIsNone(b.ns.DuoAuto.continuationRetryAt)

    def test_departure_discards_manual_consent_before_another_partner_joins(self):
        a, b = self.pair(automatic=False)
        a.finish(); b.finish(); self.exchange(a, b, 12)
        before = [h.progress() for h in (a, b)]
        self.assertTrue(self.request(a)[0])
        self.exchange(a, b, 8)  # The other player has not consented.
        a.roster(0); b.roster(0); self.exchange(a, b, 2)
        a.s.friendName, b.s.playerName = "Tres", "Tres"
        a.roster(); b.roster(); self.exchange(a, b, 35)
        self.assertEqual((a.ns.char.activeGuide, b.ns.char.activeGuide), (ROUTE_ID, ROUTE_ID))
        for h, expected in zip((a, b), before):
            self.assertEqual(h.progress(), expected)
            self.assertIsNone(h.ns.DuoAuto.continuationConsent)

    def test_real_paladin69_hunter81_waits_at_zone_end_even_when_quest_wait_is_off(self):
        hosts = []
        for name, friend, cls, other, cursor in (
            ("Paladin", "Cazador", "PALADIN", "HUNTER", 69),
            ("Cazador", "Paladin", "HUNTER", "PALADIN", 81),
        ):
            saved = {"seen": True, "activeGuide": DWARF, "auto": False,
                     "progress": {DWARF: {"cursor": cursor, "placed": True,
                         "confirmed": {"my-mark": True}, "skipped": {"my-skip": True}}},
                     "duo": {"enabled": True, "wait": False, "autoPair": False}}
            h = AutomaticPartyHost(name, friend, cls=cls, race="Dwarf", active_guide=DWARF, saved=saved)
            h.s.friendClass = other
            h.roster(); hosts.append(h)
        paladin, hunter = hosts
        hunter.ns.char.auto = True
        before = hunter.progress()
        self.exchange(paladin, hunter, 30)
        self.assertEqual(hunter.ns.char.activeGuide, DWARF)
        self.assertEqual(hunter.ns.char.progress[DWARF].cursor, 81)
        status = hunter.ns.DuoAuto.GetContinuationState(hunter.ns.DuoAuto, hunter.ns.guides[DWARF])
        self.assertEqual((status[0], status[2]), (True, False))
        self.assertIn("El Libro de la Divinidad", status[1])
        self.assertIn("69/80", status[1])
        self.assertEqual(hunter.progress(), before)
        self.assertFalse(hunter.ns.char.duo.wait)
        self.assertFalse(hunter.ns.char.duo.autoPair)
        # Only a fresh source header may name the pending class step.
        self.exchange(paladin, hunter, 18, drop=lambda s, r, f: s is paladin and f[1] == "H")
        unknown = hunter.ns.DuoAuto.GetContinuationState(hunter.ns.DuoAuto, hunter.ns.guides[DWARF])
        self.assertTrue(unknown[0]); self.assertFalse(unknown[2])
        self.assertNotIn("El Libro de la Divinidad", unknown[1])
        self.assertIn("cabecera reciente", unknown[1])
        self.assertEqual(hunter.ns.char.activeGuide, DWARF)


if __name__ == "__main__":
    unittest.main()
