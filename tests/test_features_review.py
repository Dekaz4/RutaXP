"""Independent regressions for opt-in group features and guide preservation."""

import unittest

from test_duo import DUO_STUBS, DuoHost
import test_talent_trainer_regressions as full


class IndependentDuoReviewTests(unittest.TestCase):
    def receive_header(self, host, nonce="review", sequence=1, cls="MAGE", race="Human"):
        return host.dcall("Receive", host.duo.prefix,
                          f"2|H|{nonce}|{sequence}|5|{cls}|{race}|forever/alliance/test|1|0|Alliance",
                          "PARTY", "Dos-Forever")

    def receive_quest(self, host, sequence, quest=100, state=1, done=0, total=1, mask=0, request=1, nonce="review"):
        return host.dcall("Receive", host.duo.prefix,
                          f"2|Q|{nonce}|{sequence}|{quest}|{state}|{done}|{total}|{mask}|{request}",
                          "PARTY", "Dos-Forever")

    def test_partial_objective_step_can_finish_when_both_finish_that_objective(self):
        goals = [{"t": "complete", "quest": 100, "oi": 1}]
        a = DuoHost(goals=goals)
        b = DuoHost("Dos", "Uno", goals=goals)
        a.dcall("SetWait", True)
        for h in (a, b):
            h.quest(100, onQuest=True, complete=False, objectives=[
                {"text": "Current route objective", "finished": True},
                {"text": "Objective for a later route step", "finished": False},
            ])
        for _ in range(3):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        self.assertEqual(a.dcall("GetPartnerQuest", 100).state, 1)
        a.call("Sync")
        self.assertEqual(a.position(), 2)

    def test_twenty_fifth_quest_is_synced_after_rotating_through_previous_quests(self):
        a = DuoHost()
        self.assertTrue(a.dcall("Receive", a.duo.prefix,
                               "2|H|longsession|1|5|MAGE|Human|forever/alliance/test|1|0|Alliance",
                               "PARTY", "Dos-Forever"))
        for n in range(1, 26):
            accepted = a.dcall("Receive", a.duo.prefix,
                              f"2|Q|longsession|{n + 1}|{1000 + n}|1|0|1|0|1",
                              "PARTY", "Dos-Forever")
            self.assertTrue(accepted, f"A new active quest must not be rejected after {n - 1} previous quests")
        self.assertEqual(a.dcall("GetPartnerQuest", 1025).state, 1)

    def test_adopting_exclusive_friend_guide_rejects_wrong_class_and_race(self):
        for condition in ({"classes": ["MAGE"]}, {"races": ["Dwarf"]}):
            with self.subTest(condition=condition):
                a = DuoHost()
                a.guide("exclusive", steps=[{"title": "Other character route"}], **condition)
                a.dcall("Receive", a.duo.prefix,
                        "2|H|n|1|5|MAGE|Dwarf|exclusive|1|0|Alliance", "PARTY", "Dos-Forever")
                original = a.ns.char.activeGuide
                result = a.dcall("AdoptPartnerGuide")
                ok = result[0] if isinstance(result, tuple) else result
                self.assertFalse(ok)
                self.assertEqual(a.ns.char.activeGuide, original)

    def test_same_finished_count_for_a_different_objective_still_waits(self):
        a = DuoHost(goals=[{"t": "complete", "quest": 100, "oi": 1}])
        a.dcall("SetWait", True)
        a.quest(100, onQuest=True, objectives=[{"finished": True}, {"finished": False}])
        self.assertTrue(self.receive_header(a))
        self.assertTrue(self.receive_quest(a, 2, done=1, total=2, mask=2))
        self.assertEqual(a.position(), 1)
        self.assertTrue(self.receive_quest(a, 3, done=1, total=2, mask=1))
        self.assertEqual(a.position(), 2)

    def test_multiple_objectives_for_one_quest_wait_for_each_required_index(self):
        a = DuoHost(goals=[{"t": "complete", "quest": 100, "oi": 1},
                           {"t": "complete", "quest": 100, "oi": 2}])
        a.dcall("SetWait", True)
        a.quest(100, onQuest=True, objectives=[{"finished": True}, {"finished": True}, {"finished": False}])
        self.receive_header(a)
        self.receive_quest(a, 2, done=1, total=3, mask=1)
        self.assertEqual(a.position(), 1)
        self.receive_quest(a, 3, done=2, total=3, mask=3)
        self.assertEqual(a.position(), 2)

    def test_objective_32_is_serialized_without_signed_integer_overflow(self):
        a = DuoHost(goals=[{"t": "complete", "quest": 100, "oi": 32}])
        b = DuoHost("Dos", "Uno", goals=[{"t": "complete", "quest": 100, "oi": 32}])
        a.dcall("SetWait", True)
        for h in (a, b):
            h.quest(100, onQuest=True, objectives=[{"finished": i == 32} for i in range(1, 33)])
        self.assertEqual(b.dcall("LocalQuest", 100).mask, 2147483648)
        for _ in range(3):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        self.assertEqual(a.dcall("GetPartnerQuest", 100).mask, 2147483648)
        self.assertEqual(a.position(), 2)

    def test_replies_do_not_renew_a_request_and_new_request_can_renew_it(self):
        a = DuoHost()
        self.receive_header(a)
        self.receive_quest(a, 2, quest=200)
        a.state.now = 20
        self.receive_quest(a, 3, quest=200, request=0)
        self.assertEqual(a.duo.requested[200], 0)
        a.state.now = 36
        self.receive_quest(a, 4, quest=200, request=0)
        self.assertIsNone(a.duo.requested[200])
        self.assertEqual(a.dcall("GetPartnerQuest", 200).state, 1)
        self.receive_quest(a, 5, quest=200, request=1)
        self.assertEqual(a.duo.requested[200], 36)

    def test_two_clients_do_not_keep_old_quests_alive_by_echoing_replies(self):
        a = DuoHost()
        b = DuoHost("Dos", "Uno", goals=[{"t": "complete", "quest": 200}])
        for _ in range(5):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        self.assertIsNotNone(a.duo.requested[200])
        self.assertIsNotNone(b.duo.requested[100])
        self.assertIsNone(a.duo.requested[100])
        self.assertIsNone(b.duo.requested[200])
        for h in (a, b):
            h.group([{"t": "note", "text": "No quests in this step"}], id="noquests")
            h.call("SelectGuide", "noquests")
        for _ in range(85):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        for h in (a, b):
            self.assertEqual(len(list(h.duo.requested.items())), 0)
            self.assertEqual(len(list(h.duo.remoteQuests.items())), 0)
            self.assertEqual(len(h.dcall("GetQuestIDs")), 0)

    def test_shared_starter_guide_waits_when_both_races_match(self):
        a = DuoHost()
        a.ns.guides[a.ns.char.activeGuide].races = a.table(["Human"])
        a.dcall("SetWait", True)
        a.quest(100, onQuest=True, complete=True)
        self.receive_header(a)
        self.receive_quest(a, 2, state=0)
        self.assertEqual(a.position(), 1)
        self.receive_quest(a, 3, state=2)
        self.assertEqual(a.position(), 2)

    def test_shared_class_goal_waits_when_both_classes_match(self):
        a = DuoHost(goals=[{"t": "complete", "quest": 100, "only": {"classes": ["WARRIOR"]}}])
        a.state.friendClass = "WARRIOR"
        a.ns.guides[a.ns.char.activeGuide].classes = a.table(["WARRIOR"])
        a.dcall("SetWait", True)
        a.quest(100, onQuest=True, complete=True)
        self.receive_header(a, cls="WARRIOR")
        self.receive_quest(a, 2, state=0)
        self.assertEqual(a.position(), 1)
        self.receive_quest(a, 3, state=2)
        self.assertEqual(a.position(), 2)

    def test_different_race_branch_does_not_wait_for_inapplicable_companion(self):
        for where in ("guide", "step", "goal"):
            with self.subTest(where=where):
                a = DuoHost()
                a.state.friendRace = "Dwarf"
                guide, step, _ = a.call("GetCurrent")
                if where == "guide":
                    guide.races = a.table(["Human"])
                elif where == "step":
                    step.only = a.table({"races": ["Human"]})
                else:
                    step.goals[1].only = a.table({"races": ["Human"]})
                    step.goals[2].only = a.table({"races": ["Human"]})
                a.dcall("SetWait", True)
                a.quest(100, onQuest=True, complete=True)
                a.call("Sync")
                self.assertEqual(a.position(), 2)

    def test_race_alias_and_exclusion_conditions_match_partner(self):
        for conditions, partner, should_wait in [(["Undead"], "Scourge", True),
                                                (["Scourge"], "Undead", True),
                                                (["Skyborne"], "SkyborneHuman", True),
                                                (["!Human"], "Dwarf", True),
                                                (["!Human"], "Human", False)]:
            with self.subTest(conditions=conditions, partner=partner):
                a = DuoHost()
                guide, step, _ = a.call("GetCurrent")
                guide.races = a.table(conditions)
                a.state.friendRace = partner
                self.receive_header(a, race=partner)
                a.dcall("SetWait", True)
                waiting = a.dcall("ShouldWaitForStep", step)
                self.assertEqual(waiting[0] if isinstance(waiting, tuple) else waiting, should_wait)

    def test_bounded_caches_evict_oldest_and_keep_recent_quests(self):
        a = DuoHost()
        self.receive_header(a)
        for n in range(80):
            a.state.now = n / 10
            self.assertTrue(self.receive_quest(a, n + 2, quest=1000 + n))
        self.assertEqual(len(list(a.duo.requested.items())), 24)
        self.assertEqual(len(list(a.duo.remoteQuests.items())), 48)
        self.assertIsNone(a.duo.requested[1055])
        self.assertEqual(a.duo.requested[1056], 5.6)
        self.assertIsNone(a.duo.remoteQuests[1031])
        self.assertIsNotNone(a.duo.remoteQuests[1032])
        self.assertIsNotNone(a.duo.remoteQuests[1079])

    def test_impossible_masks_and_legacy_payloads_are_rejected(self):
        a = DuoHost()
        self.receive_header(a)
        for packet in ["1|Q|review|2|100|1|1|1", "2|Q|review|2|100|1|1|1",
                       "2|Q|review|2|100|1|1|1|2|1", "2|Q|review|2|100|1|1|1|1|2",
                       "2|Q|review|2|100|1|0|1|1|1", "2|Q|review|2|100|1|2|2|1|1",
                       "2|Q|review|2|100|1|1|32|4294967296|1"]:
            self.assertFalse(a.dcall("Receive", a.duo.prefix, packet, "PARTY", "Dos-Forever"))
        self.assertTrue(self.receive_quest(a, 2, done=1, mask=1))

    def test_shipping_event_frame_handles_messages_and_invalidates_on_roster_events(self):
        h = full.TalentTrainerHost(full_toc=True)
        h.lua.execute(DUO_STUBS)
        h.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        h.g.EmitAddonEvent("PLAYER_LOGIN")
        duo = h.ns.Duo
        duo.SetEnabled(duo, True)
        h.g.EmitAddonEvent("CHAT_MSG_ADDON", duo.prefix,
                         "2|H|events|1|5|MAGE|Human|forever/alliance/test|1|0|Alliance", "PARTY", "Dos-Forever")
        self.assertTrue(duo.GetContext(duo).known)
        h.state.friendOnline = False
        h.g.EmitAddonEvent("UNIT_CONNECTION", "party1")
        self.assertFalse(duo.GetContext(duo).known)
        h.state.friendOnline = True
        h.g.EmitAddonEvent("PLAYER_ENTERING_WORLD")
        self.assertTrue(duo.GetContext(duo).sameParty)
        h.state.members = 3
        h.g.EmitAddonEvent("GROUP_ROSTER_UPDATE")
        self.assertFalse(duo.GetContext(duo).sameParty)


if __name__ == "__main__":
    unittest.main()
