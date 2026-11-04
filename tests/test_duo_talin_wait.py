"""Real TOCs and PARTY traffic for the manually enabled Talin step wait."""
import unittest

from test_auto_party_integration import AutomaticPartyHost
from test_duo_journey import primitive_copy


DWARF = "forever/alliance/dwarf-gnome/01-dun-morogh"


class ManualTalinHost(AutomaticPartyHost):
    def __init__(self, name="Uno", friend="Dos", cursor=6):
        saved = {"seen": True, "activeGuide": DWARF, "auto": False,
                 "progress": {DWARF: {"cursor": cursor, "review": False, "placed": True,
                                        "confirmed": {"user-confirmed": True}, "skipped": {"user-skipped": True}}},
                 "duo": {"enabled": True, "wait": True, "autoPair": False, "autoEpoch": 3}}
        super().__init__(name, friend, active_guide=DWARF, saved=saved, race="Dwarf")
        self.set_talin()

    @property
    def cursor(self):
        return self.ns.char.progress[DWARF].cursor

    def set_talin(self, accepted=True, delivered=True):
        self.s.quests[233] = self.h.table({"onQuest": not delivered, "delivered": delivered,
                                          "complete": not delivered, "objectives": []})
        self.ns.turnedIn[233] = True if delivered else None
        for quest, active in ((183, True), (234, accepted), (3361, True)):
            self.s.quests[quest] = self.h.table({"onQuest": active, "complete": False,
                "objectives": [{"text": "Pendiente", "finished": False, "numFulfilled": 0, "numRequired": 1}]})


class ShippingTalinWaitTests(unittest.TestCase):
    def pair(self, second_cursor=6):
        a, b = ManualTalinHost(), ManualTalinHost("Dos", "Uno", second_cursor)
        a.roster(); b.roster()
        return a, b

    def exchange(self, a, b, ticks=1, flood=False):
        for _ in range(ticks):
            if flood:
                # Legal exploratory requests through the same bounded API as
                # the planner. They must not displace a real current step.
                for quest in range(1, 25):
                    a.ns.Duo.RequestQuest(a.ns.Duo, quest)
            a.tick(); b.tick()
            self.assertLessEqual(len(a.s.outgoing), 1)
            self.assertLessEqual(len(b.s.outgoing), 1)
            a.deliver(b); b.deliver(a)

    def test_exploratory_request_starvation_cannot_require_skipping_a_green_talin_step(self):
        a, b = self.pair(second_cursor=7)
        before = primitive_copy(a.ns.char.progress[DWARF])
        a.set_talin(accepted=False)
        a.ns.char.auto = b.ns.char.auto = True
        a.ns.Sync(a.ns); b.ns.Sync(b.ns)
        self.exchange(a, b, 60, flood=True)
        self.assertEqual(a.cursor, 6)
        self.assertTrue(a.ns.Duo.GetContext(a.ns.Duo).known)
        # The real acceptance event makes the last local row green. Automatic
        # advancement must then work without toggling auto or clicking Skip.
        a.s.quests[234].onQuest = True
        a.h.g.EmitAddonEvent("QUEST_ACCEPTED", 234)
        items = a.ns.GetStepGoalItems(a.ns, a.ns.guides[DWARF].steps[6], a.ns.char.progress[DWARF])
        if isinstance(items, tuple): items = items[0]
        self.assertEqual([item.status for item in items.values()], ["done", "done", "done"])
        self.exchange(a, b, 60, flood=True)
        # No Next/Skip/confirmation action is used anywhere in this scenario.
        self.assertEqual(a.cursor, 7)
        self.assertEqual(b.cursor, 7)
        self.assertEqual(primitive_copy(a.ns.char.progress[DWARF].confirmed), before["confirmed"])
        self.assertEqual(primitive_copy(a.ns.char.progress[DWARF].skipped), before["skipped"])
        self.assertFalse(a.ns.char.duo.autoPair)
        self.assertIsNone(a.ns.char.duo.autoSession)
        self.assertTrue(a.ns.Duo.GetContext(a.ns.Duo).known)
        self.assertTrue(all(len(packet["message"]) <= 255 for host in (a, b) for packet in host.packets))

    def test_missing_acceptance_really_waits_and_acceptance_event_releases_without_skip(self):
        for legacy in (False, True):
            with self.subTest(legacy_event=legacy):
                a, b = self.pair(); b.set_talin(accepted=False)
                self.exchange(a, b, 15)
                a.ns.char.auto = b.ns.char.auto = True
                a.ns.Sync(a.ns); b.ns.Sync(b.ns)
                self.assertEqual(a.cursor, 6)
                detail = a.ns.Duo.GetStepWaitStatus(a.ns.Duo, a.ns.guides[DWARF].steps[6])
                self.assertTrue(detail.waiting)
                self.assertEqual((detail.kind, detail.action, detail.questID, detail.state), ("quest", "accept", 234, 0))
                self.assertFalse(detail.unknown)
                self.assertEqual(len(a.ns.Duo.ShouldWaitForStep(a.ns.Duo, a.ns.guides[DWARF].steps[6])), 2)
                b.s.quests[234].onQuest = True
                args = (4, 234) if legacy else (234,)
                b.h.g.EmitAddonEvent("QUEST_ACCEPTED", *args)
                self.exchange(a, b, 20)
                self.assertEqual((a.cursor, b.cursor), (7, 7))

    def test_unknown_quest_snapshot_requests_refresh_and_never_claims_completion(self):
        a, b = self.pair(); self.exchange(a, b, 12)
        a.ns.Duo.remoteQuests[233] = None
        detail = a.ns.Duo.GetStepWaitStatus(a.ns.Duo, a.ns.guides[DWARF].steps[6])
        self.assertTrue(detail.waiting)
        self.assertTrue(detail.unknown)
        self.assertEqual((detail.kind, detail.action, detail.questID), ("quest", "turnin", 233))
        self.assertIsNotNone(a.ns.Duo.outboundRequests[233])
        a.ns.char.auto = True; a.ns.Sync(a.ns)
        self.assertEqual(a.cursor, 6)

    def test_explicit_resync_preserves_progress_settings_and_eventually_reacquires_states(self):
        a, b = self.pair(); self.exchange(a, b, 12)
        progress, config, automatic = a.progress(), primitive_copy(a.ns.char.duo), a.ns.char.auto
        self.assertIsNotNone(a.ns.Duo.remoteQuests[233])
        result = a.ns.Duo.Resynchronize(a.ns.Duo)
        self.assertTrue(result[0])
        self.assertEqual(len(a.ns.Duo.remoteQuests), 0)
        self.assertEqual(a.progress(), progress)
        self.assertEqual(primitive_copy(a.ns.char.duo), config)
        self.assertEqual(a.ns.char.auto, automatic)
        self.exchange(a, b, 15)
        self.assertEqual(a.ns.Duo.GetPartnerQuest(a.ns.Duo, 233).state, 3)
        self.assertEqual(a.ns.Duo.GetPartnerQuest(a.ns.Duo, 234).state, 1)
        self.assertEqual(a.progress(), progress)

    def test_partner_priority_keeps_our_active_quest_and_honors_partner_class(self):
        a, b = self.pair(second_cursor=7); self.exchange(a, b, 8)
        # A real large published step still fits with the partner's current
        # objectives, and an unrelated class branch is not requested for them.
        b.ns.char.progress[DWARF].cursor = 3
        b.s.classToken = "MAGE"; a.s.friendClass = "MAGE"
        for _ in range(10): self.exchange(a, b)
        ids = list(a.ns.Duo.GetQuestIDs(a.ns.Duo).values())
        self.assertLessEqual(len(ids), 24)
        self.assertIn(3114, ids)
        self.assertNotIn(3106, ids)
        active, *_ = b.ns.GetActiveGoal(b.ns, b.ns.guides[DWARF].steps[3], b.ns.char.progress[DWARF])
        own_ids = list(b.ns.Duo.GetQuestIDs(b.ns.Duo).values())
        self.assertIn(active.quest, own_ids)


if __name__ == "__main__":
    unittest.main()
