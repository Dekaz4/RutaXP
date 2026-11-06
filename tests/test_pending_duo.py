"""Recovery actions rejoin skipped quests in a real two-client duo."""

import unittest

from test_auto_party_integration import AutomaticPartyHost, QUEST_ID, ROUTE_ID
from test_duo_journey import primitive_copy


class PendingDuoTests(unittest.TestCase):
    def options(self, host):
        settings = primitive_copy(host.ns.char.duo)
        settings.pop("autoEpoch", None)  # Internal agreement generation.
        return settings, host.ns.char.auto

    def exchange(self, a, b, ticks=40):
        for _ in range(ticks):
            a.tick()
            b.tick()
            self.assertLessEqual(len(a.s.outgoing), 1)
            self.assertLessEqual(len(b.s.outgoing), 1)
            a.deliver(b)
            b.deliver(a)

    def test_pending_command_recovers_own_skip_keeps_duo_and_advances_on_both_real_completions(self):
        a = AutomaticPartyHost(cursor=2, review=False, auto=True)
        b = AutomaticPartyHost("Dos", "Uno", cursor=2, review=False, auto=True)
        for h in (a, b):
            step = h.ns.guides[ROUTE_ID].steps[2]
            step.goals[2] = h.h.table({"t": "vendor", "text": "Reparar el equipo"})
            step.goals[3] = h.h.table({"t": "train", "text": "Visitar al instructor"})
            state = h.ns.char.progress[ROUTE_ID]
            state.confirmed["2:2"] = True
            state.skipped["2:3"] = True
            h.roster()
        self.exchange(a, b, 75)
        self.assertTrue(a.status().active)
        self.assertTrue(b.status().active)
        own_state = a.ns.char.progress[ROUTE_ID]
        friend_before = b.progress()
        own_other = {key: value for key, value in a.progress().items() if key != ROUTE_ID}
        options_before = self.options(a)

        a.h.g.Click(a.ns.trackerSkip)
        self.exchange(a, b, 25)
        self.assertEqual((own_state.cursor, b.ns.char.progress[ROUTE_ID].cursor), (3, 2))
        self.assertTrue(a.view().following)
        self.assertTrue(own_state.skipped["2:1"])
        self.assertEqual(b.ns.Duo.GetPartnerQuest(b.ns.Duo, QUEST_ID).state, 1)

        a.ns.Command(a.ns, "pendientes")
        self.assertEqual(own_state.cursor, 2)
        self.assertIsNone(own_state.skipped["2:1"])
        self.assertTrue(own_state.confirmed["2:2"])
        self.assertTrue(own_state.skipped["2:3"])
        self.assertEqual(self.options(a), options_before)
        self.assertEqual({key: value for key, value in a.progress().items() if key != ROUTE_ID}, own_other)
        self.assertEqual(b.progress(), friend_before)
        self.assertTrue(any("Retomadas tus misiones pendientes" in text for text in a.s.messages.values()))

        self.exchange(a, b, 75)
        self.assertTrue(a.status().active)
        self.assertTrue(b.status().active)
        self.assertEqual((a.view().sharedCursor, b.view().sharedCursor), (2, 2))
        self.assertEqual(b.progress(), friend_before)
        self.assertEqual(self.options(a), options_before)
        self.assertEqual(b.ns.Duo.GetPartnerQuest(b.ns.Duo, QUEST_ID).state, 1)
        self.assertEqual(b.ns.Duo.GetObjectiveProgress(b.ns.Duo, QUEST_ID, 1).partner.current, 3)

        a.quest(count=8)
        a.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        self.exchange(a, b, 25)
        self.assertEqual((own_state.cursor, b.ns.char.progress[ROUTE_ID].cursor), (2, 2))
        b.quest(count=8)
        b.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        self.exchange(a, b, 40)
        self.assertEqual((own_state.cursor, b.ns.char.progress[ROUTE_ID].cursor), (3, 3))
        for h in (a, b):
            self.assertFalse(h.ns.IsQuestDelivered(h.ns, QUEST_ID))
            self.assertTrue(h.status().active)
            state = h.ns.char.progress[ROUTE_ID]
            self.assertTrue(state.confirmed["2:2"])
            self.assertTrue(state.skipped["2:3"])
            self.assertIsNone(state.skipped["2:1"])
            self.assertLessEqual(h.s.maxSyncDepth, 2)

    def test_back_button_undoes_own_skip_while_following_buddy_and_keeps_automatic_duo(self):
        a = AutomaticPartyHost(cursor=2, review=False, auto=True)
        b = AutomaticPartyHost("Dos", "Uno", cursor=2, review=False, auto=True)
        for h in (a, b):
            guide = h.ns.guides[ROUTE_ID]
            guide.steps[2].goals[2] = h.h.table({"t": "vendor", "text": "Reparar"})
            guide.steps[4] = h.h.table({"title": "Instructor", "goals": [{"t": "train"}]})
            state = h.ns.char.progress[ROUTE_ID]
            state.confirmed["2:2"] = True
            state.skipped["4:1"] = True
            h.roster()
        self.exchange(a, b, 75)
        options = self.options(a)
        friend_before = b.progress()
        other_guides = {key: value for key, value in a.progress().items() if key != ROUTE_ID}

        a.h.g.Click(a.ns.trackerSkip)
        self.exchange(a, b, 25)
        own = a.ns.char.progress[ROUTE_ID]
        self.assertEqual((own.cursor, a.view().sharedCursor), (3, 2))
        self.assertTrue(a.view().following)
        self.assertTrue(a.ns.trackerPrevious.isEnabled)
        self.assertTrue(a.ns.previousButton.isEnabled)
        self.assertFalse(a.ns.trackerNext.isEnabled)
        self.assertFalse(a.ns.trackerSkip.isEnabled)

        a.h.g.Click(a.ns.trackerPrevious)
        self.assertEqual(own.cursor, 2)
        self.assertFalse(bool(own.review))
        self.assertIsNone(own.skipped["2:1"])
        self.assertTrue(own.confirmed["2:2"])
        self.assertTrue(own.skipped["4:1"])
        self.assertEqual(self.options(a), options)
        self.assertEqual(b.progress(), friend_before)
        self.assertEqual({key: value for key, value in a.progress().items() if key != ROUTE_ID}, other_guides)
        self.exchange(a, b, 75)
        self.assertTrue(a.status().active)
        self.assertTrue(b.status().active)
        self.assertEqual((a.view().sharedCursor, b.view().sharedCursor), (2, 2))
        self.assertEqual(self.options(a), options)
        self.assertEqual(b.progress(), friend_before)

        a.quest(count=8)
        a.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        self.exchange(a, b, 25)
        self.assertEqual((own.cursor, b.ns.char.progress[ROUTE_ID].cursor), (2, 2))
        b.quest(count=8)
        b.h.g.EmitAddonEvent("QUEST_LOG_UPDATE")
        self.exchange(a, b, 40)
        self.assertEqual((own.cursor, b.ns.char.progress[ROUTE_ID].cursor), (3, 3))
        for h in (a, b):
            self.assertTrue(h.status().active)
            self.assertFalse(h.ns.IsQuestDelivered(h.ns, QUEST_ID))
            state = h.ns.char.progress[ROUTE_ID]
            self.assertTrue(state.confirmed["2:2"])
            self.assertTrue(state.skipped["4:1"])
            self.assertLessEqual(h.s.maxSyncDepth, 2)


if __name__ == "__main__":
    unittest.main()
