"""Registration, send results and exact Forever regional-name identities."""
import unittest

from test_auto_party_integration import AutomaticPartyHost, QUEST_ID
from test_duo import DUO_STUBS
from test_duo_journey import primitive_copy
from test_quest_engine import QuestEngineHost, ADDON


TRANSPORT_STUBS = r'''
Enum=Enum or {}
Enum.RegisterAddonMessagePrefixResult={Success=0,DuplicatePrefix=1,InvalidPrefix=2,MaxPrefixes=3}
Enum.SendAddonMessageResult={Success=0,InvalidPrefix=1,InvalidMessage=2,AddonMessageThrottle=3,
  InvalidChatType=4,NotInGroup=5,TargetRequired=6,InvalidChannel=7,ChannelThrottle=8,
  GeneralError=9,NotInGuild=10,AddOnMessageLockdown=11,TargetOffline=12}
TEST.registerCalls,TEST.sendCalls,TEST.attempts=0,0,{}
TEST.registerResult,TEST.sendResult=0,0
C_ChatInfo.RegisterAddonMessagePrefix=function()
  TEST.registerCalls=TEST.registerCalls+1
  local result=TEST.registerResult
  TEST.registered=result==0 or result==1 or result==nil or result==true
  return result
end
C_ChatInfo.SendAddonMessage=function(prefix,message,channel)
  TEST.sendCalls=TEST.sendCalls+1;TEST.attempts[#TEST.attempts+1]=GetTime()
  if TEST.sendError then error("simulated native API error") end
  local result=TEST.sendResult
  if result==nil or result==true or result==Enum.SendAddonMessageResult.Success then
    TEST.outgoing[#TEST.outgoing+1]={prefix=prefix,message=message,channel=channel}
  end
  return result
end
'''

REGIONAL_NAMES = r'''
NameUtil={GetUnmodifiedUnitFullName=function(unit)
  return unit=='party1' and TEST.friendName or TEST.playerName
end}
C_NameUtil={ReplaceSurnameSeparatorWithLinkSeparator=function(name) return name:gsub(' ','-') end}
Constants=Constants or {};Constants.CharacterNameSeparatorConsts={CHARACTERNAME_SURNAME_SEPARATOR=' '}
function RegionalUniqueNamesEnabled() return true end
'''


class TransportHost(QuestEngineHost):
    def __init__(self, registration=0, query=True):
        super().__init__()
        self.lua.execute(DUO_STUBS + TRANSPORT_STUBS)
        self.state.registerResult = registration
        if not query:
            self.globals.C_ChatInfo.IsAddonMessagePrefixRegistered = None
        for name in ("Duo.lua", "Extensions.lua"):
            self.load((ADDON / name).read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        self.group([{"t": "accept", "quest": 100}, {"t": "complete", "quest": 100}], id="connection")
        self.initialize()
        self.duo = self.ns.Duo
        self.dcall("SetEnabled", True)

    def dcall(self, method, *args):
        return self.duo[method](self.duo, *args)

    def tick(self, seconds=1):
        self.state.now += seconds
        self.dcall("Tick", seconds)


class DuoConnectionTests(unittest.TestCase):
    def test_rejected_send_does_not_mark_header_sent_and_retries_with_one_second_backoff(self):
        h = TransportHost(); h.state.sendResult = 3
        self.assertFalse(h.dcall("Send", "H", "5|WARRIOR|Human|connection|1|0|Alliance"))
        self.assertEqual(h.state.sendCalls, 1)
        h.state.now += .2
        self.assertFalse(h.dcall("Send", "H", "5|WARRIOR|Human|connection|1|0|Alliance"))
        self.assertEqual(h.state.sendCalls, 1)
        self.assertIsNone(h.duo.lastSentHeader)
        h.state.sendResult = 0
        h.tick(1)
        self.assertIsNotNone(h.duo.lastSentHeader)
        status = h.dcall("GetTransportStatus")
        self.assertEqual((status.attempts, status.accepted, status.failed), (2, 1, 1))
        self.assertIsNone(status.lastError)
        self.assertGreaterEqual(h.state.attempts[2] - h.state.attempts[1], 1)

    def test_api_exception_and_rejected_auto_packet_are_not_reported_as_success(self):
        h = TransportHost(); h.state.sendError = True
        self.assertFalse(h.dcall("Send", "H", "values"))
        status = h.dcall("GetTransportStatus")
        self.assertEqual((status.accepted, status.failed), (0, 1))
        self.assertTrue(status.lastError)
        h.state.sendError = False; h.state.sendResult = 11
        h.tick()
        self.assertIsNone(h.duo.lastSentHeader)
        self.assertTrue(h.dcall("GetTransportStatus").lastError)

    def test_legacy_nil_true_and_documented_success_result_remain_compatible(self):
        for result in (None, True, 0):
            with self.subTest(result=result):
                h = TransportHost(); h.state.sendResult = result
                self.assertTrue(h.dcall("Send", "H", "values"))
                self.assertEqual(h.dcall("GetTransportStatus").accepted, 1)

    def test_registration_failure_is_checked_and_real_roster_event_can_recover(self):
        h = TransportHost(registration=3)
        self.assertFalse(h.dcall("GetTransportStatus").registered)
        self.assertFalse(h.dcall("CanCommunicate")[0])
        attempts = h.state.registerCalls
        for _ in range(10): h.dcall("CanCommunicate")
        self.assertEqual(h.state.registerCalls, attempts)
        h.state.registerResult = 0; h.state.now += 1
        self.assertTrue(h.duo.frame.events.PLAYER_ENTERING_WORLD)
        h.duo.frame.scripts.OnEvent(h.duo.frame, "PLAYER_ENTERING_WORLD")
        self.assertTrue(h.dcall("GetTransportStatus").registered)
        h.tick()
        self.assertEqual(h.dcall("GetTransportStatus").accepted, 1)

    def test_rejected_registration_is_not_success_when_status_query_is_unavailable(self):
        h = TransportHost(registration=False, query=False)
        self.assertFalse(h.dcall("GetTransportStatus").registered)
        self.assertEqual(h.state.sendCalls, 0)
        duplicate = TransportHost(registration=1, query=False)
        self.assertTrue(duplicate.dcall("GetTransportStatus").registered)

    def test_foreign_header_counter_excludes_self_echo_and_never_stores_sender_identity(self):
        h = TransportHost()
        header = "2|H|n|1|5|MAGE|Human|connection|1|0|Alliance"
        self.assertFalse(h.dcall("Receive", h.duo.prefix, header, "PARTY", "Uno-Forever"))
        self.assertEqual(h.dcall("GetTransportStatus").unmatchedHeaders, 0)
        self.assertFalse(h.dcall("Receive", h.duo.prefix, header, "PARTY", "Otro-Forever"))
        self.assertEqual(h.dcall("GetTransportStatus").unmatchedHeaders, 1)
        self.assertTrue(h.dcall("Receive", h.duo.prefix, header, "PARTY", "Dos-Forever"))
        status = h.dcall("GetTransportStatus")
        self.assertEqual(status.receivedHeaders, 1)
        self.assertNotIn("Otro", repr(primitive_copy(status)))
        h.state.friendName = "Tres"; h.dcall("RefreshRoster")
        self.assertEqual(h.dcall("GetTransportStatus").unmatchedHeaders, 0)

    def test_unknown_or_secret_roster_names_never_authorize_a_sender(self):
        h = TransportHost(); h.globals.UNKNOWNOBJECT = "UNKNOWN"
        h.state.friendName = "UNKNOWN"
        self.assertFalse(h.dcall("GetContext").sameParty)
        h.state.friendName = "Hidden"
        h.lua.execute("function issecretvalue(v) return v=='Hidden' end")
        self.assertFalse(h.dcall("GetContext").sameParty)
        h = TransportHost(); h.lua.execute(REGIONAL_NAMES)
        h.state.friendName = "Dos Martillo"
        h.lua.execute('''
            function UnitFullName(unit) return unit=='party1' and 'Dos' or 'Uno','Forever' end
            function issecretvalue(value) return value=='Dos Martillo' end
        ''')
        self.assertFalse(h.dcall("GetContext").sameParty)

    def test_missing_unitfullname_uses_official_full_helper_without_nil_unknown_sentinel(self):
        h = TransportHost(); h.lua.execute(REGIONAL_NAMES)
        h.state.friendName = "Dos Martillo"
        h.globals.UnitFullName = None; h.globals.UNKNOWNOBJECT = None
        self.assertTrue(h.dcall("GetContext").sameParty)
        self.assertTrue(h.dcall("Receive", h.duo.prefix,
            "2|H|n|1|5|MAGE|Human|connection|1|0|Alliance", "PARTY", "Dos-Martillo"))

    def test_regional_full_alias_works_without_assuming_shard_is_the_local_realm(self):
        for sender in ("Dos Martillo", "Dos-Martillo"):
            with self.subTest(sender=sender):
                h = TransportHost(); h.lua.execute(REGIONAL_NAMES)
                h.state.friendName = "Dos Martillo"
                h.lua.execute('''
                    function UnitFullName(unit) return unit=='party1' and TEST.friendName or TEST.playerName,'93' end
                    function GetNormalizedRealmName() return 'ForeverLaunch' end
                ''')
                self.assertTrue(h.dcall("Receive", h.duo.prefix,
                    "2|H|n|1|5|MAGE|Human|connection|1|0|Alliance", "PARTY", sender))

    def test_classic_cross_realm_name_keeps_realm_validation_with_a_spaced_display(self):
        h = TransportHost()
        h.lua.execute('''
            WOW_PROJECT_ID=1
            function RegionalUniqueNamesEnabled() return false end
            NameUtil={GetUnmodifiedUnitFullName=function() return 'Dos Other Realm' end}
            function UnitFullName(unit) return unit=='party1' and 'Dos' or 'Uno','Other Realm' end
            function GetNormalizedRealmName() return 'LocalRealm' end
        ''')
        header = "2|H|n|1|5|MAGE|Human|connection|1|0|Alliance"
        for sender in ("Dos", "Dos Other Realm", "Dos-WrongRealm"):
            self.assertFalse(h.dcall("Receive", h.duo.prefix, header, "PARTY", sender))
        self.assertTrue(h.dcall("Receive", h.duo.prefix, header, "PARTY", "Dos-OtherRealm"))

    def test_name_boundary_collision_still_invalidates_old_peer_observations(self):
        h = TransportHost(); h.lua.execute(REGIONAL_NAMES)
        h.state.friendName = "Aren River"
        self.assertTrue(h.dcall("Receive", h.duo.prefix,
            "2|H|old_peer|1|5|MAGE|Human|connection|1|0|Alliance", "PARTY", "Aren River"))
        saved_key = h.duo.partnerName
        h.state.friendName = "Are Nriver"
        h.dcall("RefreshRoster")
        self.assertEqual(h.duo.partnerName, saved_key, "Historical key format is preserved")
        self.assertFalse(h.dcall("GetContext").known)
        self.assertIsNone(h.duo.peer)

    def test_exact_realm_alias_normalizes_only_explicit_server_not_character_surname(self):
        h = TransportHost()
        h.lua.execute('''
          function UnitFullName(unit) return unit=='party1' and 'Dos' or 'Uno','Forever-Launch' end
          function GetNormalizedRealmName() return 'ForeverLaunch' end
        ''')
        primary = h.dcall("GetContext").partnerName
        header = "2|H|n|1|5|MAGE|Human|connection|1|0|Alliance"
        self.assertTrue(h.dcall("Receive", h.duo.prefix, header, "PARTY", "Dos-ForeverLaunch"))
        self.assertEqual(h.dcall("GetContext").partnerName, primary)

    def test_two_shipping_tocs_accept_complete_regional_aliases_and_reject_same_first_name_third(self):
        for linked in (False, True):
            with self.subTest(linked_names=linked):
                a = AutomaticPartyHost("Aren Stone", "Aren River")
                b = AutomaticPartyHost("Aren River", "Aren Stone")
                for h in (a, b): h.h.lua.execute(REGIONAL_NAMES); h.roster()
                identities = (a.ns.Duo.GetContext(a.ns.Duo).partnerName,
                              b.ns.Duo.GetContext(b.ns.Duo).partnerName)
                before = a.progress(False), b.progress(False)
                def deliver(sender, receiver):
                    identity = sender.s.playerName.replace(" ", "-") if linked else sender.s.playerName
                    for packet in sender.s.outgoing.values():
                        receiver.h.g.EmitAddonEvent("CHAT_MSG_ADDON", packet.prefix, packet.message, packet.channel, identity)
                    sender.s.outgoing = sender.h.lua.table()
                for _ in range(75):
                    a.tick(); b.tick(); deliver(a, b); deliver(b, a)
                self.assertTrue(a.status().active)
                self.assertTrue(b.status().active)
                self.assertEqual((a.progress(False), b.progress(False)), before)
                self.assertEqual((a.ns.Duo.GetContext(a.ns.Duo).partnerName,
                                  b.ns.Duo.GetContext(b.ns.Duo).partnerName), identities)
                header = "2|H|attacker|999|10|WARRIOR|Human|auto-review/common|2|0|Alliance"
                for third in ("Aren", "Aren Other", "Aren-Other", "Aren Other-Forever",
                              "Are Nriver", "Are-Nriver", "Are Nriver-Forever", "Arenriver", "Arenriver-Forever"):
                    self.assertFalse(a.ns.Duo.Receive(a.ns.Duo, a.ns.Duo.prefix, header, "PARTY", third))
                b.quest(QUEST_ID, count=6)
                for _ in range(12):
                    a.tick(); b.tick(); deliver(a, b); deliver(b, a)
                self.assertEqual(a.ns.Duo.GetObjectiveProgress(a.ns.Duo, QUEST_ID, 1).partner.current, 6)


if __name__ == "__main__":
    unittest.main()
