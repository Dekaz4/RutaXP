"""Two shipping Lua clients exchange exact progress and observed duo telemetry."""
import unittest

import test_duo as fixtures


ENHANCED_STUBS = r'''
TEST.mapID, TEST.x, TEST.y, TEST.height, TEST.instance = 1429, .4, .6, 25, 0
TEST.bags = { [0]={slots=16,free=2,family=0}, [1]={slots=8,free=3,family=0} }
TEST.durability = { [1]={current=20,total=100}, [5]={current=40,total=100} }
TEST.mana, TEST.maximumMana = 0, 100
function C_Container_GetSlots(bag) return TEST.bags[bag] and TEST.bags[bag].slots or 0 end
C_Container = {
    GetContainerNumSlots=C_Container_GetSlots,
    GetContainerNumFreeSlots=function(bag)
        local b=TEST.bags[bag]; if b then return b.free,b.family end
        return 0,0
    end,
}
function GetInventoryItemDurability(slot)
    local d=TEST.durability[slot]; if d then return d.current,d.total end
end
function UnitPower(unit,power) TEST.powerUnit,TEST.powerType=unit,power; return TEST.mana end
function UnitPowerMax(unit,power) return TEST.maximumMana end
function UnitPosition() return 0,0,TEST.height,TEST.instance end
function UnitInRange() return TEST.friendInRange,TEST.rangeChecked end
function UnitIsDeadOrGhost(unit) return unit=='player' and TEST.playerDead==true or unit=='party1' and TEST.friendDead==true end
function InstallDuoNavigation(ns)
    function ns:PlayerPoint()
        if TEST.positionUnavailable then return nil end
        return {mapID=TEST.mapID,x=TEST.x,y=TEST.y}
    end
    function ns:GetWaypointWorldPosition() return 0,0,0 end
    function ns:GetWaypointVector(point)
        if point.mapID~=TEST.mapID then return nil,'Destino en otro mapa' end
        return math.sqrt((point.x-TEST.x)^2+(point.y-TEST.y)^2)*1000
    end
end
'''


class EnhancedHost(fixtures.DuoHost):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lua.execute(ENHANCED_STUBS)
        self.globals.InstallDuoNavigation(self.ns)


class EnhancedDuoTests(unittest.TestCase):
    def pair(self, goals=None):
        return EnhancedHost(goals=goals), EnhancedHost("Dos", "Uno", goals=goals)

    def exchange(self, a, b, ticks=2):
        for _ in range(ticks):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)

    def test_exact_counts_are_per_objective_and_preserve_real_zero(self):
        a, b = self.pair()
        a.quest(100, onQuest=True, objectives=[
            {"finished": False, "numFulfilled": 3, "numRequired": 10},
            {"finished": False, "numFulfilled": 0, "numRequired": 5},
        ])
        b.quest(100, onQuest=True, objectives=[
            {"finished": False, "numFulfilled": 7, "numRequired": 10},
            {"finished": False, "numFulfilled": 2, "numRequired": 5},
        ])
        self.exchange(a, b)
        first = a.dcall("GetObjectiveProgress", 100, 1)
        self.assertEqual((first.mine.current, first.partner.current), (3, 7))
        self.assertEqual((first.mine.total, first.partner.total), (10, 10))
        self.assertTrue(first.partner.known)
        self.assertFalse(first.partner.finished)
        second = a.dcall("GetObjectiveProgress", 100, 2)
        self.assertEqual((second.mine.current, second.partner.current), (0, 2))
        self.assertIn("3/10", a.dcall("GetReport"))
        self.assertIn("7/10", a.dcall("GetReport"))
        self.assertFalse(a.call("IsQuestDelivered", 100))

    def test_missing_counts_remain_unknown_and_never_become_zero_over_zero(self):
        a, b = self.pair()
        for h in (a, b):
            h.quest(100, onQuest=True, objectives=[{"finished": False}])
        self.exchange(a, b)
        result = a.dcall("GetObjectiveProgress", 100, 1)
        self.assertFalse(result.mine.known)
        self.assertFalse(result.partner.known)
        self.assertIsNone(result.partner.current)
        self.assertIsNone(result.partner.total)
        self.assertFalse(result.partner.finished)
        self.assertNotIn("0/0", result.text)
        missing = a.dcall("GetObjectiveProgress", 100, 32)
        self.assertFalse(missing.partner.known)

    def test_delivered_history_has_no_live_zero_counter_for_either_character(self):
        a, b = self.pair()
        for h in (a, b):
            h.ns.char.auto = False
            h.quest(100, onQuest=False, delivered=True, objectives=[{
                "finished": False, "numFulfilled": 0, "numRequired": 20,
            }])
        self.exchange(a, b, ticks=8)
        for h in (a, b):
            progress = h.dcall("GetObjectiveProgress", 100, 1)
            for owner in (progress.mine, progress.partner):
                self.assertTrue(owner.delivered)
                self.assertTrue(owner.finished)
                self.assertFalse(owner.known)
                self.assertIsNone(owner.current)
                self.assertIsNone(owner.total)
            self.assertIn("Entregada", progress.text)
            self.assertNotIn("0/20", progress.text)
            report = h.dcall("GetReport")
            self.assertIn("Entregada", report)
            self.assertNotIn("0/20", report)
            self.assertNotIn("0/1 objetivos", report)

    def test_large_objective_set_rotates_without_breaking_mask_or_packet_limit(self):
        a, b = self.pair()
        objectives = [{"finished": index == 32, "numFulfilled": 10000000 if index == 32 else 9999999,
                       "numRequired": 10000000} for index in range(1, 33)]
        b.quest(100, onQuest=True, objectives=objectives)
        for _ in range(14):
            a.tick(); b.tick()
            for packet in b.state.outgoing.values():
                self.assertLessEqual(len(packet.message.encode("utf-8")), 255)
                self.assertEqual(packet.channel, "PARTY")
            a.deliver_to(b); b.deliver_to(a)
        result = a.dcall("GetObjectiveProgress", 100, 32)
        self.assertTrue(result.partner.known)
        self.assertEqual(result.partner.current, 10000000)
        self.assertEqual(a.dcall("GetPartnerQuest", 100).mask, 2147483648)

    def test_objective_freshness_is_not_extended_by_a_legacy_quest_summary(self):
        a = EnhancedHost()
        prefix = a.duo.prefix
        self.assertTrue(a.dcall("Receive", prefix, "2|H|n|1|5|MAGE|Human|forever/alliance/test|1|0|Alliance", "PARTY", "Dos-Forever"))
        self.assertTrue(a.dcall("Receive", prefix, "2|Q|n|2|100|1|0|1|0|1|1:4:10:0", "PARTY", "Dos-Forever"))
        a.state.now = 20
        self.assertTrue(a.dcall("Receive", prefix, "2|Q|n|3|100|1|0|1|0|0", "PARTY", "Dos-Forever"))
        a.state.now = 36
        self.assertTrue(a.dcall("Receive", prefix, "2|Q|n|4|100|1|0|1|0|0", "PARTY", "Dos-Forever"))
        self.assertFalse(a.dcall("GetObjectiveProgress", 100, 1).partner.known)
        self.assertEqual(a.dcall("GetPartnerQuest", 100).state, 1)

    def test_hidden_quest_capabilities_invalidate_old_state_without_claiming_absence(self):
        a, b = self.pair()
        self.exchange(a, b)
        self.assertEqual(a.dcall("GetPartnerQuest", 100).state, 0)
        b.lua.execute('''
        C_QuestLog.IsOnQuest=function() return nil end
        C_QuestLog.IsQuestFlaggedCompleted=function() return nil end
        IsQuestFlaggedCompleted=nil
        ''')
        self.exchange(a, b, 3)
        self.assertFalse(b.dcall("LocalQuest", 100).known)
        self.assertIsNone(b.dcall("LocalQuest", 100).state)
        self.assertIsNone(a.dcall("GetPartnerQuest", 100))
        self.assertIn("Sin datos", b.dcall("GetReport"))

    def test_supply_snapshot_uses_general_bags_durability_and_real_zero_mana(self):
        a, b = self.pair()
        b.state.bags[2] = b.table({"slots": 20, "free": 20, "family": 32})
        self.exchange(a, b)
        supplies = a.dcall("GetPartnerSupplies")
        self.assertTrue(supplies.known)
        self.assertEqual((supplies.freeSlots, supplies.totalSlots), (5, 24))
        self.assertEqual(supplies.durabilityPercent, 30)
        self.assertEqual(supplies.manaPercent, 0)
        self.assertTrue(supplies.manaLow)
        self.assertEqual(b.state.powerUnit, "player")
        self.assertEqual(b.state.powerType, 0)

    def test_unavailable_supply_apis_and_non_mana_class_are_not_fake_zeros(self):
        a, b = self.pair()
        b.lua.execute('C_Container=nil; GetInventoryItemDurability=nil; TEST.maximumMana=0')
        self.exchange(a, b)
        supplies = a.dcall("GetPartnerSupplies")
        self.assertTrue(supplies.known)
        self.assertIsNone(supplies.freeSlots)
        self.assertIsNone(supplies.totalSlots)
        self.assertIsNone(supplies.durabilityPercent)
        self.assertIsNone(supplies.manaPercent)
        self.assertIsNone(supplies.manaLow)
        a.state.now += 36
        self.assertFalse(a.dcall("GetPartnerSupplies").known)

    def test_secret_numeric_results_are_unknown_before_arithmetic(self):
        h = EnhancedHost()
        h.lua.execute('''
        SECRET={}
        issecretvalue=function(value) return value==SECRET end
        UnitPower=function() return SECRET end
        GetInventoryItemDurability=function() return SECRET,SECRET end
        C_Container.GetContainerNumFreeSlots=function() return SECRET,0 end
        ''')
        supplies = h.dcall("GetLocalSupplies")
        self.assertIsNone(supplies.manaPercent)
        self.assertIsNone(supplies.durabilityPercent)
        self.assertIsNone(supplies.freeSlots)
        h.quest(100, onQuest=True, objectives=[{"finished": False, "numRequired": 10}])
        h.lua.execute('TEST.quests[100].objectives[1].numFulfilled=SECRET')
        self.assertFalse(h.dcall("GetObjectiveProgress", 100, 1).mine.known)

    def test_meeting_is_explicit_shared_and_never_copies_quest_progress(self):
        a, b = self.pair()
        a.state.x, a.state.y, a.state.height = .31, .42, 37
        self.assertTrue(a.dcall("SetMeetingPoint")[0])
        self.exchange(a, b, 4)
        status = b.dcall("GetMeetingStatus")
        self.assertTrue(status.available)
        self.assertEqual(status.owner, "uno-forever")
        self.assertAlmostEqual(status.point.x, .31)
        self.assertAlmostEqual(status.point.y, .42)
        self.assertEqual(status.point.z, 37)
        self.assertIsNotNone(status.distance)
        self.assertIsNone(b.dcall("GetMeetingWaypoint"))
        b.dcall("FollowMeeting", True)
        point = b.dcall("GetMeetingWaypoint")
        self.assertEqual(point.source, "duo-meeting")
        self.assertAlmostEqual(point.x, .31)
        self.assertEqual(b.position(), 1)
        self.assertFalse(b.call("IsQuestDelivered", 100))
        self.assertEqual(b.dcall("GetContext").partnerName, "uno-forever")

    def test_meeting_controls_and_packets_do_not_call_quest_sync(self):
        a, b = self.pair()
        for h in (a, b):
            h.lua.execute('function InstallSyncCounter(ns) ns.Sync=function() TEST.syncCalls=(TEST.syncCalls or 0)+1 end end')
            h.globals.InstallSyncCounter(h.ns)
        a.dcall("SetMeetingPoint")
        a.dcall("FollowMeeting", True)
        a.dcall("FollowMeeting", False)
        a.dcall("ClearMeeting")
        self.assertIsNone(a.state.syncCalls)
        self.assertTrue(b.dcall("Receive", b.duo.prefix, "2|H|n|1|5|WARRIOR|Human|forever/alliance/test|1|0|Alliance", "PARTY", "Uno-Forever"))
        baseline = b.state.syncCalls
        self.assertTrue(b.dcall("Receive", b.duo.prefix, "2|M|n|2|1|1429|300000|400000|250|0", "PARTY", "Uno-Forever"))
        self.assertEqual(b.state.syncCalls, baseline)

    def test_simultaneous_meetings_converge_and_clear_does_not_reappear_when_stale(self):
        a, b = self.pair()
        a.state.x, b.state.x = .2, .8
        a.dcall("SetMeetingPoint"); b.dcall("SetMeetingPoint")
        self.exchange(a, b, 4)
        for h in (a, b):
            self.assertEqual(h.dcall("GetMeetingStatus").owner, "uno-forever")
        b.dcall("ClearMeeting")
        self.exchange(a, b, 4)
        self.assertFalse(a.dcall("GetMeetingStatus").available)
        a.state.now += 70
        self.assertFalse(a.dcall("GetMeetingStatus").available)

    def test_meeting_capture_rejects_missing_position_and_drops_unverified_height(self):
        h = EnhancedHost()
        h.state.positionUnavailable = True
        self.assertFalse(h.dcall("SetMeetingPoint")[0])
        h.state.positionUnavailable, h.state.instance = False, 99
        self.assertTrue(h.dcall("SetMeetingPoint")[0])
        self.assertIsNone(h.dcall("GetMeetingStatus").z)

    def test_zone_death_and_separation_alerts_use_recent_observed_context(self):
        a, b = self.pair()
        b.state.mapID, b.state.playerDead = 1411, True
        a.state.friendInRange, a.state.rangeChecked = False, True
        self.exchange(a, b)
        context = a.dcall("GetContext")
        self.assertEqual(context.partnerMapID, 1411)
        self.assertTrue(context.dead)
        kinds = {alert.kind for alert in a.dcall("GetAlerts").values()}
        self.assertEqual(kinds, {"death", "zone"})
        a.state.now += 16
        self.assertIsNone(a.dcall("GetContext").partnerMapID)
        self.assertNotIn("zone", {alert.kind for alert in a.dcall("GetAlerts").values()})
        self.assertIn("separation", {alert.kind for alert in a.dcall("GetAlerts").values()})

    def test_checkpoint_provider_exchanges_bounded_copies_without_applying_cursor(self):
        a, b = self.pair()
        b.quest(100, onQuest=True, objectives=[{"finished": False, "numFulfilled": 4, "numRequired": 9}])
        b.dcall("RegisterCheckpointProvider", b.lua.eval('function() return {checkpointID="7",guideID="forever/alliance/test",cursor=33,stopKind="repair",stopReady=true} end'))
        self.exchange(a, b, 5)
        checkpoint = a.dcall("GetPartnerCheckpoint")
        self.assertTrue(checkpoint.known)
        self.assertEqual((checkpoint.checkpointID, checkpoint.cursor), ("7", 33))
        self.assertEqual(checkpoint.stopKind, "repair")
        self.assertTrue(checkpoint.stopReady)
        self.assertEqual(checkpoint.quests[100].objectives[1].current, 4)
        checkpoint.quests[100].objectives[1].current = 99
        self.assertEqual(a.dcall("GetPartnerQuest", 100).objectives[1].current, 4)
        self.assertEqual(a.position(), 1)
        a.state.now += 40
        self.assertFalse(a.dcall("GetPartnerCheckpoint").known)

    def test_requested_candidate_quest_gets_observed_reply_without_becoming_subscription_echo(self):
        a, b = self.pair()
        b.quest(777, onQuest=True, objectives=[{"finished": False, "numFulfilled": 2, "numRequired": 6}])
        a.dcall("RequestQuest", 777)
        self.exchange(a, b, 10)
        quest = a.dcall("GetPartnerQuest", 777)
        self.assertIsNotNone(quest)
        self.assertEqual(quest.state, 1)
        self.assertEqual(quest.objectives[1].current, 2)
        self.assertIsNone(a.duo.requested[777])
        self.assertIsNotNone(b.duo.requested[777])
        for quest_id in range(1000, 1040):
            a.dcall("RequestQuest", quest_id)
        self.assertEqual(len(list(a.duo.outboundRequests.items())), 24)

    def test_malformed_new_payloads_are_rejected_without_replacing_good_state(self):
        a = EnhancedHost()
        self.assertTrue(a.dcall("Receive", a.duo.prefix, "2|H|n|1|5|MAGE|Human|forever/alliance/test|1|0|Alliance", "PARTY", "Dos-Forever"))
        payloads = [
            "2|Q|n|2|100|1|0|1|0|1|1:20:10:0",
            "2|Q|n|2|100|1|0|1|0|1|1:?:10:0",
            "2|Q|n|2|100|1|0|1|0|1|2:1:10:0",
            "2|Q|n|2|100|1|0|1|0|1|1:1:10:1",
            "2|S|n|2|21|20|30|50|5",
            "2|M|n|2|1|1429|1000001|400000|25|0",
            "2|M|n|2|1|0|300000|400000|25|0",
            "2|R|n|2|100,100",
            "2|U|n|2|100|3",
        ]
        for packet in payloads:
            with self.subTest(packet=packet):
                self.assertFalse(a.dcall("Receive", a.duo.prefix, packet, "PARTY", "Dos-Forever"))
        self.assertIsNone(a.dcall("GetPartnerQuest", 100))
        self.assertFalse(a.dcall("GetMeetingStatus").available)

    def test_all_new_traffic_is_party_only_at_most_one_per_second_and_bounded(self):
        a = EnhancedHost()
        a.dcall("SetMeetingPoint")
        a.dcall("RequestQuest", 777)
        a.dcall("RegisterCheckpointProvider", a.lua.eval('function() return {checkpointID="1",stopKind="rest",stopReady=false} end'))
        for _ in range(400):
            before = len(a.state.outgoing)
            a.tick(.1)
            self.assertLessEqual(len(a.state.outgoing) - before, 1)
        self.assertLessEqual(len(a.state.outgoing), 40)
        for packet in a.state.outgoing.values():
            self.assertLessEqual(len(packet.message.encode("utf-8")), 255)
            self.assertEqual(packet.channel, "PARTY")

    def test_twenty_four_quests_stay_fresh_under_meeting_checkpoint_and_request_traffic(self):
        a, b = self.pair()
        quest_ids = [100] + list(range(1000, 1023))
        for h in (a, b):
            h.dcall("SetMeetingPoint")
            h.dcall("RegisterCheckpointProvider", h.lua.eval('function() return {checkpointID="1",stopKind="repair",stopReady=true} end'))
            for quest_id in quest_ids:
                h.quest(quest_id, onQuest=True, objectives=[{"finished": False, "numFulfilled": 3, "numRequired": 9}])
        for tick in range(100):
            for h in (a, b):
                for quest_id in quest_ids[1:]:
                    h.dcall("RequestQuest", quest_id)
            a.tick(); b.tick()
            for h in (a, b):
                for packet in h.state.outgoing.values():
                    self.assertLessEqual(len(packet.message.encode("utf-8")), 255)
                    self.assertEqual(packet.channel, "PARTY")
            a.deliver_to(b); b.deliver_to(a)
            if tick >= 39:  # After discovery, exercise a full sixty-tick window.
                for h in (a, b):
                    for quest_id in quest_ids:
                        with self.subTest(tick=tick, quest_id=quest_id):
                            quest = h.dcall("GetPartnerQuest", quest_id)
                            self.assertIsNotNone(quest)
                            self.assertLessEqual(h.state.now - quest.seen, 35)
                    self.assertTrue(h.dcall("GetObjectiveProgress", 100, 1).partner.known)
                    self.assertTrue(h.dcall("GetMeetingStatus").available)
                    self.assertTrue(h.dcall("GetPartnerCheckpoint").known)

    def test_batch_is_atomic_replay_safe_and_incompatible_old_counter_is_dropped(self):
        a = EnhancedHost()
        prefix = a.duo.prefix
        self.assertTrue(a.dcall("Receive", prefix, "2|H|n|1|5|MAGE|Human|forever/alliance/test|1|0|Alliance", "PARTY", "Dos-Forever"))
        invalid = "2|B|n|2|100,1,0,1,0,1,1:3:8:0/200,1,0,1,0,1,1:9:8:0"
        self.assertFalse(a.dcall("Receive", prefix, invalid, "PARTY", "Dos-Forever"))
        self.assertIsNone(a.duo.remoteQuests[100])
        self.assertIsNone(a.duo.requested[100])
        self.assertEqual(a.duo.peer.sequence, 1)
        valid = "2|B|n|2|100,1,0,1,0,1,1:3:8:0/200,1,0,1,0,1,1:2:8:0"
        self.assertTrue(a.dcall("Receive", prefix, valid, "PARTY", "Dos-Forever"))
        self.assertFalse(a.dcall("Receive", prefix, valid, "PARTY", "Dos-Forever"))
        self.assertEqual(a.dcall("GetObjectiveProgress", 100, 1).partner.current, 3)
        self.assertTrue(a.dcall("Receive", prefix, "2|B|n|3|100,2,1,1,1,1,/200,1,0,1,0,1,", "PARTY", "Dos-Forever"))
        updated = a.dcall("GetObjectiveProgress", 100, 1).partner
        self.assertFalse(updated.known)
        self.assertIsNone(updated.current)
        self.assertTrue(updated.finished)


if __name__ == "__main__":
    unittest.main()
