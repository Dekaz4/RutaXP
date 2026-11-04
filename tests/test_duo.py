"""Two isolated Lua clients exchange only the shipping opt-in PARTY protocol."""
import unittest
import copy

import test_quest_engine as engine
import test_talent_trainer_regressions as full


DUO_STUBS = r'''
TEST.now, TEST.members, TEST.outgoing = 0, 2, {}
TEST.playerName, TEST.friendName = "Uno", "Dos"
TEST.friendLevel, TEST.friendClass, TEST.friendRace = 1, "MAGE", "Human"
TEST.friendOnline, TEST.friendFaction = true, "Alliance"
function GetTime() return TEST.now end
function GetNormalizedRealmName() return "Forever" end
function UnitFullName(unit) return unit == "party1" and TEST.friendName or TEST.playerName, "Forever" end
function UnitFactionGroup(unit) return unit == "party1" and TEST.friendFaction or TEST.faction end
function UnitClass(unit) return "Clase", unit == "party1" and TEST.friendClass or TEST.classToken end
function UnitRace(unit) return "Raza", unit == "party1" and TEST.friendRace or TEST.raceToken end
function UnitLevel(unit) return unit == "party1" and TEST.friendLevel or TEST.level end
function GetNumGroupMembers() return TEST.members end
function IsInRaid() return TEST.raid == true end
function UnitIsConnected() return TEST.friendOnline end
function UnitIsDeadOrGhost() return false end
C_ChatInfo = {
    RegisterAddonMessagePrefix = function() TEST.registered = true; return 0 end,
    IsAddonMessagePrefixRegistered = function() return TEST.registered end,
    AreOutgoingAddonChatMessagesRestricted = function() return TEST.restricted == true end,
    InChatMessagingLockdown = function() return TEST.lockdown == true end,
    SendAddonMessage = function(prefix, message, channel)
        TEST.outgoing[#TEST.outgoing + 1] = {prefix=prefix, message=message, channel=channel}
        return 0
    end,
}
function C_QuestLog.IsUnitOnQuest(unit, id)
    TEST.queryUnit, TEST.queryQuest = unit, id
    return TEST.basicQuest == id
end
'''


class DuoHost(engine.QuestEngineHost):
    def __init__(self, player="Uno", friend="Dos", goals=None):
        super().__init__()
        self.lua.execute(DUO_STUBS)
        self.state.playerName, self.state.friendName = player, friend
        for name in ["Duo.lua", "Extensions.lua"]:
            self.load((engine.ADDON / name).read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        goals = goals or [{"t": "complete", "quest": 100}]
        accepts = [{"t": "accept", "quest": goal["quest"], **({"only": copy.deepcopy(goal["only"])} if "only" in goal else {})}
                   for goal in goals if goal.get("quest") and goal.get("t") != "accept"]
        self.group(accepts + goals, id="forever/alliance/test",
                   next_goals=[{"t": "note", "text": "Next"}])
        self.initialize()
        self.duo = self.ns.Duo
        self.dcall("SetEnabled", True)

    def dcall(self, name, *args):
        return self.duo[name](self.duo, *args)

    def tick(self, seconds=1):
        self.state.now += seconds
        self.dcall("Tick", seconds)

    def deliver_to(self, other):
        for packet in self.state.outgoing.values():
            other.dcall("Receive", packet.prefix, packet.message, packet.channel,
                        self.state.playerName + "-Forever")
        self.state.outgoing = self.lua.table()

    def position(self):
        return self.cursor("forever/alliance/test")


class DuoTests(unittest.TestCase):
    def pair(self):
        a, b = DuoHost(), DuoHost("Dos", "Uno")
        for _ in range(2):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        return a, b

    def test_two_real_lua_namespaces_exchange_current_quest_and_profile(self):
        a, b = self.pair()
        self.assertTrue(a.dcall("GetContext").known)
        self.assertEqual(a.dcall("GetContext").guideID, "forever/alliance/test")
        self.assertEqual(a.dcall("GetPartnerQuest", 100).state, 0)
        b.quest(100, onQuest=True, complete=True,
                objectives=[{"text": "Kill", "finished": True}])
        for _ in range(4):
            b.tick(); b.deliver_to(a)
        self.assertEqual(a.dcall("GetPartnerQuest", 100).state, 2)
        self.assertEqual(a.dcall("GetPartnerQuest", 100).done, 1)
        self.assertIn("Lista para entregar", a.dcall("GetReport"))

    def test_wait_is_opt_in_and_peer_data_never_completes_our_objectives(self):
        a, b = self.pair()
        b.quest(100, onQuest=True, complete=True)
        b.tick(); b.deliver_to(a)
        a.call("Sync")
        self.assertEqual(a.position(), 1)
        self.assertFalse(a.call("IsQuestDelivered", 100))
        a.quest(100, onQuest=True, complete=True)
        a.call("Sync")
        self.assertEqual(a.position(), 2)

    def test_wait_holds_completed_local_step_until_peer_ready_for_turnin(self):
        a, b = self.pair()
        a.dcall("SetWait", True)
        a.quest(100, onQuest=True, complete=True)
        a.call("Sync")
        self.assertEqual(a.position(), 1)
        b.quest(100, onQuest=True, complete=True)
        for _ in range(4):
            b.tick(); b.deliver_to(a)
        self.assertEqual(a.position(), 2)

    def test_turnin_wait_does_not_deadlock_until_both_have_delivered(self):
        a = DuoHost(goals=[{"t": "turnin", "quest": 100}])
        b = DuoHost("Dos", "Uno", goals=[{"t": "turnin", "quest": 100}])
        a.dcall("SetWait", True)
        b.quest(100, onQuest=True, complete=True)
        for _ in range(2):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        a.quest(100, delivered=True)
        a.call("Sync")
        self.assertEqual(a.position(), 2)

    def test_class_quest_does_not_wait_for_a_different_class(self):
        a = DuoHost(goals=[{"t": "complete", "quest": 100, "only": {"classes": ["WARRIOR"]}}])
        b = DuoHost("Dos", "Uno")
        b.state.classToken = "MAGE"
        b.state.friendClass = "WARRIOR"
        a.dcall("SetWait", True)
        for _ in range(2):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        a.quest(100, onQuest=True, complete=True)
        a.call("Sync")
        self.assertEqual(a.position(), 2)

    def test_stale_offline_and_party_changes_invalidate_remote_completion(self):
        a, b = self.pair()
        a.state.now += 40
        self.assertFalse(a.dcall("GetContext").known)
        self.assertIsNone(a.dcall("GetPartnerQuest", 100))
        a.state.friendOnline = False
        self.assertFalse(a.dcall("GetContext").online)
        a.state.friendOnline = True
        a.state.friendName = "Tres"
        self.assertFalse(a.dcall("GetContext").known)
        self.assertIsNone(a.duo.remoteQuests[100])

    def test_rejects_unrelated_senders_channels_versions_and_replay(self):
        a = DuoHost()
        message = "2|H|nonce|1|5|MAGE|Human|forever/alliance/test|1|1|Alliance"
        for sender, channel, packet in [("Extra-Forever", "PARTY", message),
                                         ("Dos-Forever", "GUILD", message),
                                         ("Dos-Forever", "PARTY", "1" + message[1:]),
                                         ("Dos-Forever", "PARTY", "x" * 256),
                                         ("Dos-Forever", "PARTY", message.replace("|5|", "|999|")),
                                         ("Dos-Forever", "PARTY", message.replace("Alliance", "Horde"))]:
            self.assertFalse(a.dcall("Receive", a.duo.prefix, packet, channel, sender))
        self.assertTrue(a.dcall("Receive", a.duo.prefix, message, "PARTY", "Dos-Forever"))
        self.assertFalse(a.dcall("Receive", a.duo.prefix, message, "PARTY", "Dos-Forever"))

    def test_suspends_in_raid_three_player_and_cross_faction_groups(self):
        for field, value in [("members", 3), ("raid", True), ("friendFaction", "Horde")]:
            a = DuoHost(); setattr(a.state, field, value)
            a.tick()
            self.assertFalse(a.dcall("GetContext").sameParty)
            self.assertEqual(len(a.state.outgoing), 0)

    def test_restrictions_and_rate_limit_never_fall_back_to_chat(self):
        a = DuoHost()
        for _ in range(9):
            a.tick(.1)
        self.assertEqual(len(a.state.outgoing), 0)
        a.tick(.2)
        self.assertEqual(len(a.state.outgoing), 1)
        self.assertEqual(a.state.outgoing[1].channel, "PARTY")
        a.state.restricted = True
        a.tick(2)
        self.assertEqual(len(a.state.outgoing), 1)
        self.assertIn("restringe", a.dcall("GetReport"))
        a.state.restricted = False; a.state.lockdown = True
        a.tick(2)
        self.assertEqual(len(a.state.outgoing), 1)

    def test_without_peer_addon_native_query_has_correct_unit_first_signature(self):
        a = DuoHost(); a.state.basicQuest = 100
        q = a.dcall("GetPartnerQuest", 100)
        self.assertTrue(q.basic)
        self.assertEqual(a.state.queryUnit, "party1")
        self.assertEqual(a.state.queryQuest, 100)
        a.dcall("SetWait", True)
        a.quest(100, onQuest=True, complete=True); a.call("Sync")
        self.assertEqual(a.position(), 1)
        a.dcall("SetWait", False)
        self.assertEqual(a.position(), 2)

    def test_adopting_guide_keeps_local_cursor_and_marks_independent(self):
        a, b = self.pair()
        a.guide("other", steps=[{"title": "Other"}])
        a.call("GetProgress", "other").cursor = 1
        a.duo.peer.guideID, a.duo.peer.cursor = "other", 99
        self.assertTrue(a.dcall("AdoptPartnerGuide"))
        self.assertEqual(a.ns.char.activeGuide, "other")
        self.assertEqual(a.cursor("other"), 1)
        self.assertIsNone(a.call("GetProgress", "other").skipped)


class FeaturePanelTests(unittest.TestCase):
    def test_every_panel_and_command_loads_with_shipping_toc(self):
        h = full.TalentTrainerHost(full_toc=True)
        h.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        h.g.EmitAddonEvent("PLAYER_LOGIN")
        original = h.ns.char.activeGuide
        for tab in ["duo", "session", "recovery", "adaptation", "waypoints"]:
            h.ns.ToggleFeatures(h.ns, tab)
            self.assertTrue(h.ns.featuresPanel.shown)
            self.assertTrue(h.ns.featuresPanel.body.text)
        for command in ["sesion", "herramientas", "adaptar", "puntos", "recuperar"]:
            h.ns.Command(h.ns, command)
        self.assertEqual(h.ns.char.activeGuide, original)
        h.ns.ShowFeatureText(h.ns, "Export", "session data")
        self.assertEqual(h.ns.featureExport.edit.text, "session data")

    def test_tracker_duo_row_never_grows_on_repeated_refresh(self):
        h = full.TalentTrainerHost(full_toc=True)
        h.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        h.g.EmitAddonEvent("PLAYER_LOGIN")
        h.ns.Duo.SetEnabled(h.ns.Duo, True)
        height = h.ns.tracker.height
        for _ in range(5):
            h.ns.RefreshUI(h.ns)
            self.assertEqual(h.ns.tracker.height, height)
        h.ns.Duo.SetEnabled(h.ns.Duo, False)
        self.assertEqual(h.ns.tracker.height, height - 30)


if __name__ == "__main__":
    unittest.main()
