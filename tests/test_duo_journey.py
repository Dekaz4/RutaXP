"""Real Core/QuestEngine/Journey Lua; only peer observations and supplies are mocked."""

import unittest

from test_addon import ADDON
from test_duo import DuoHost


CONTRACT_STUBS = r'''
TEST.localSnapshots = {}
TEST.localSupplies = {known=true,freeSlots=10,totalSlots=20,durabilityPercent=100,manaPercent=100,level=TEST.level}
TEST.partnerSupplies = {known=true,freeSlots=10,totalSlots=20,durabilityPercent=100,manaPercent=100,level=TEST.friendLevel}
TEST.checkpointKnown, TEST.peerStopKind, TEST.peerStopReady = true, "none", false
function InstallJourneyContract(ns)
    function ns.Duo:RegisterCheckpointProvider(provider)
        TEST.providerRegistrations = (TEST.providerRegistrations or 0) + 1
        self.checkpointProvider = provider
    end
    function ns.Duo:GetPartnerCheckpoint()
        local peer = self.peer
        if not peer or not TEST.checkpointKnown then return {known=false} end
        return {known=true,checkpointID="remote",guideID=peer.guideID,cursor=peer.cursor,level=peer.level,
            mapID=37,stopKind=TEST.peerStopKind,stopReady=TEST.peerStopReady,quests=self.remoteQuests}
    end
    function ns.Duo:GetLocalSupplies() return TEST.localSupplies end
    function ns.Duo:GetPartnerSupplies() return TEST.partnerSupplies end
    function ns.Duo:GetLocalQuest(id) return TEST.localSnapshots[id] or self:LocalQuest(id) end
end
function GetServerTime() return 1800000000 + TEST.now end
'''


def primitive_copy(value):
    if hasattr(value, "items"):
        return {primitive_copy(k): primitive_copy(v) for k, v in value.items()}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise AssertionError(f"SavedVariables contains non-primitive {type(value)}")


class JourneyHost(DuoHost):
    def __init__(self, saved=None):
        super().__init__()
        self.lua.execute(CONTRACT_STUBS)
        self.globals.InstallJourneyContract(self.ns)
        if saved is not None:
            self.ns.char = self.table(saved)
        self.peer()
        self.load((ADDON / "DuoJourney.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        self.journey = self.ns.DuoJourney
        self.jcall("Initialize")

    def peer(self, name="Dos", cursor=1):
        self.state.friendName = name
        self.dcall("RefreshRoster")
        self.duo.peer = self.table({"seen": self.state.now, "nonce": "journey", "sequence": 1,
                                    "level": self.state.friendLevel, "class": "MAGE", "race": "Human",
                                    "guideID": "forever/alliance/test", "cursor": cursor})

    def remote(self, id=100, state=1, objectives=None):
        objectives = objectives or []
        observed = {i: {**o, "seen": self.state.now} for i, o in enumerate(objectives, 1)}
        self.duo.remoteQuests[id] = self.table({"state": state, "done": sum(bool(o.get("finished")) for o in objectives),
                                               "total": len(objectives), "seen": self.state.now,
                                               "objectives": observed})

    def jcall(self, method, *args):
        return self.journey[method](self.journey, *args)

    def save(self):
        result = self.jcall("SaveCheckpoint")
        if not result[0]:
            raise AssertionError(result)
        return result[1]

    def refresh_time(self, seconds):
        self.state.now += seconds
        if self.duo.peer is not None:
            self.duo.peer.seen = self.state.now
        for _, q in self.duo.remoteQuests.items():
            q.seen = self.state.now

    def progress_snapshot(self):
        return primitive_copy(self.ns.char.progress)


class DuoJourneyTests(unittest.TestCase):
    def test_save_snapshots_own_and_peer_independently_without_changing_progress(self):
        h = JourneyHost()
        h.peer(cursor=99)
        state = h.call("GetProgress", h.ns.char.activeGuide)
        state.review = True
        state.confirmed["4:1"] = True
        h.quest(100, onQuest=True)
        h.remote(state=2)
        before = h.progress_snapshot()
        record = h.save()
        self.assertEqual(record.partnerName, "dos-forever")
        self.assertEqual(record.localSnapshot.cursor, 1)
        self.assertEqual(record.partnerSnapshot.cursor, 99)
        self.assertEqual(record.localSnapshot.quests[100].state, 1)
        self.assertEqual(record.partnerSnapshot.quests[100].state, 2)
        self.assertEqual(h.progress_snapshot(), before)
        self.assertFalse(h.call("IsQuestDelivered", 100))

    def test_unknown_disabled_offline_or_larger_party_cannot_create_joint_checkpoint(self):
        for field, value in [("peer", None), ("disabled", True), ("friendOnline", False), ("members", 3)]:
            with self.subTest(field=field):
                h = JourneyHost()
                if field == "peer":
                    h.duo.peer = None
                elif field == "disabled":
                    h.ns.char.duo.enabled = False
                else:
                    setattr(h.state, field, value)
                before = h.progress_snapshot()
                self.assertFalse(h.jcall("SaveCheckpoint")[0])
                self.assertEqual(len(h.ns.char.duoJourney.history), 0)
                self.assertEqual(h.progress_snapshot(), before)

    def test_resume_selects_own_route_preserving_newer_cursor_and_every_mark(self):
        h = JourneyHost()
        h.peer(cursor=99)
        h.save()
        state = h.call("GetProgress", "forever/alliance/test")
        state.cursor, state.review = 2, True
        state.confirmed["1:3"] = True
        state.skipped = h.table({"2:4": True})
        h.guide("solo", steps=[{"title": "Solo work"}])
        h.call("SelectGuide", "solo")
        before = h.progress_snapshot()
        self.assertTrue(h.jcall("ResumeCheckpoint")[0])
        self.assertEqual(h.ns.char.activeGuide, "forever/alliance/test")
        self.assertEqual(h.progress_snapshot(), before)
        self.assertEqual(state.cursor, 2)
        self.assertTrue(state.review)

    def test_missing_progress_uses_only_own_saved_cursor_not_peer_cursor(self):
        h = JourneyHost()
        own = h.call("GetProgress", h.ns.char.activeGuide)
        own.cursor, own.review = 2, True
        h.peer(cursor=99)
        h.save()
        h.ns.char.progress["forever/alliance/test"] = None
        self.assertTrue(h.jcall("ResumeCheckpoint")[0])
        state = h.ns.char.progress["forever/alliance/test"]
        self.assertEqual(state.cursor, 2)
        self.assertTrue(state.review)
        self.assertEqual(len(list(state.confirmed.items())), 0)

    def test_resume_rejects_missing_temporary_wrong_faction_and_wrong_class_guide(self):
        for field, value in [("missing", True), ("temporary", True), ("faction", "Horde"), ("classes", ["MAGE"])]:
            with self.subTest(field=field):
                h = JourneyHost()
                h.save()
                route = h.ns.guides["forever/alliance/test"]
                if field == "missing":
                    h.ns.guides[route.id] = None
                else:
                    route[field] = h.table(value) if isinstance(value, list) else value
                h.guide("other", steps=[{"title": "Safe"}])
                h.ns.char.activeGuide = "other"
                before = h.progress_snapshot()
                self.assertFalse(h.jcall("ResumeCheckpoint")[0])
                self.assertEqual(h.ns.char.activeGuide, "other")
                self.assertEqual(h.progress_snapshot(), before)

    def test_checkpoint_identity_is_per_pair_and_wrong_pair_cannot_resume_explicit_index(self):
        h = JourneyHost()
        first = h.save()
        h.peer("Tres")
        second = h.save()
        self.assertEqual(first.partnerName, "dos-forever")
        self.assertEqual(second.partnerName, "tres-forever")
        self.assertEqual(h.jcall("GetCheckpoint").partnerName, "tres-forever")
        self.assertFalse(h.jcall("ResumeCheckpoint", 1)[0])
        h.peer("Dos")
        self.assertEqual(h.jcall("GetCheckpoint").partnerName, "dos-forever")

    def test_history_is_bounded_and_serializable_and_snapshots_do_not_alias_live_data(self):
        h = JourneyHost()
        h.remote(objectives=[{"known": True, "current": 3, "total": 10, "finished": False}])
        first = h.save()
        h.duo.remoteQuests[100].objectives[1].current = 8
        self.assertEqual(first.partnerSnapshot.quests[100].objectives[1].current, 3)
        for _ in range(24):
            h.save()
        self.assertEqual(len(h.ns.char.duoJourney.history), 20)
        self.assertEqual(h.ns.char.duoJourney.history[1].id, 6)
        primitive_copy(h.ns.char.duoJourney)

    def test_reload_offline_preserves_history_and_does_not_claim_peer_is_current(self):
        h = JourneyHost()
        h.remote(state=2)
        h.save()
        saved = primitive_copy(h.ns.char)
        other = JourneyHost(saved=saved)
        other.state.friendOnline = False
        self.assertEqual(len(other.ns.char.duoJourney.history), 1)
        catch = other.jcall("GetCatchUp")
        self.assertTrue(catch.available)
        self.assertFalse(catch.known)
        self.assertEqual(catch.status, "offline")
        self.assertEqual(len(catch.missing), 0)
        self.assertIn("fotografía guardada", other.jcall("GetCheckpointReport"))

    def test_corrupt_saved_records_are_ignored_without_touching_guide_progress(self):
        h = JourneyHost()
        valid = primitive_copy(h.save())
        saved = primitive_copy(h.ns.char)
        saved["duoJourney"] = {"history": {1: "broken", 2: {"id": 2, "localSnapshot": {}}, 3: valid},
                               "stop": {"kind": "evil", "ready": True}, "sequence": -4}
        other = JourneyHost(saved=saved)
        self.assertEqual(len(other.ns.char.duoJourney.history), 1)
        self.assertTrue(other.ns.char.duoJourney.recovered)
        self.assertIsNone(other.ns.char.duoJourney.stop)
        self.assertEqual(other.progress_snapshot(), saved["progress"])
        self.assertIsInstance(other.jcall("GetReport"), str)

    def test_catch_up_reports_solo_changes_without_copying_remote_completion(self):
        h = JourneyHost()
        h.quest(100, onQuest=True)
        h.remote(state=1)
        h.save()
        h.remote(state=3)
        catch = h.jcall("GetCatchUp")
        self.assertEqual(catch.status, "different")
        self.assertEqual(catch.missing[1].owner, "local")
        self.assertEqual(catch.partnerChanges[1].kind, "quest")
        self.assertFalse(h.call("IsQuestDelivered", 100))
        self.assertEqual(h.position(), 1)
        self.assertIn("amigo entregada", h.jcall("GetCheckpointReport"))

    def test_exact_objective_counters_are_compared_only_when_known_and_compatible(self):
        h = JourneyHost()
        h.state.localSnapshots[100] = h.table({"state": 1, "objectives": {1: {"known": True, "current": 3, "total": 10, "finished": False}}})
        h.remote(objectives=[{"known": True, "current": 3, "total": 10, "finished": False}])
        h.save()
        h.duo.remoteQuests[100].objectives[1].current = 7
        catch = h.jcall("GetCatchUp")
        self.assertEqual(catch.missing[1].kind, "objective")
        self.assertEqual(catch.missing[1].objective, 1)
        self.assertEqual(catch.missing[1].owner, "local")
        h.duo.remoteQuests[100].objectives[1].known = False
        self.assertEqual(len(h.jcall("GetCatchUp").missing), 0)
        self.assertEqual(h.jcall("GetCatchUp").status, "unknown")
        h.duo.remoteQuests[100].objectives[1].known = True
        h.duo.remoteQuests[100].objectives[1].total = 15
        self.assertEqual(len(h.jcall("GetCatchUp").missing), 0)
        self.assertEqual(h.jcall("GetCatchUp").status, "unknown")

    def test_abandonment_and_unknown_friend_are_not_reported_as_completed(self):
        h = JourneyHost()
        h.quest(100, onQuest=True)
        h.remote(state=1)
        h.save()
        h.quest(100)
        self.assertEqual(h.jcall("GetCatchUp").quests[1].localState, 0)
        self.assertFalse(h.call("IsQuestDelivered", 100))
        h.duo.remoteQuests[100] = None
        catch = h.jcall("GetCatchUp")
        self.assertEqual(catch.status, "unknown")
        self.assertEqual(len(catch.missing), 0)
        self.assertGreater(catch.unknownCount, 0)

    def test_unreadable_local_quest_is_not_saved_as_absent_or_completed(self):
        h = JourneyHost()
        h.state.localSnapshots[100] = h.table({"known": False})
        h.remote(state=1)
        record = h.save()
        self.assertIsNone(record.localSnapshot.quests[100])
        catch = h.jcall("GetCatchUp")
        self.assertFalse(catch.quests[1].localKnown)
        self.assertIsNone(catch.quests[1].localState)
        self.assertEqual(catch.status, "unknown")
        self.assertEqual(len(catch.missing), 0)

    def test_both_unknown_quests_retain_identity_and_remain_unknown_after_reload(self):
        h = JourneyHost()
        h.state.localSnapshots[100] = h.table({"known": False})
        h.duo.remoteQuests[100] = h.table({"known": False, "seen": h.state.now})
        record = h.save()
        self.assertIsNone(record.localSnapshot.quests[100])
        self.assertIsNone(record.partnerSnapshot.quests[100])
        self.assertEqual(list(record.localSnapshot.trackedQuestIDs.values()), [100])
        self.assertEqual(list(record.partnerSnapshot.trackedQuestIDs.values()), [100])
        catch = h.jcall("GetCatchUp")
        self.assertEqual(catch.status, "unknown")
        self.assertEqual(catch.unknownCount, 1)
        self.assertIsNone(catch.quests[1].localState)
        self.assertIsNone(catch.quests[1].partnerState)
        other = JourneyHost(saved=primitive_copy(h.ns.char))
        other.state.localSnapshots[100] = other.table({"known": False})
        other.duo.remoteQuests[100] = other.table({"known": False, "seen": other.state.now})
        self.assertEqual(list(other.jcall("GetCheckpoint").localSnapshot.trackedQuestIDs.values()), [100])
        self.assertEqual(other.jcall("GetCatchUp").status, "unknown")
        self.assertEqual(other.jcall("GetCatchUp").unknownCount, 1)
        self.assertNotIn("No hay diferencias", other.jcall("GetCheckpointReport"))

    def test_corrupt_tracking_ids_are_bounded_deduplicated_and_never_become_state_zero(self):
        h = JourneyHost()
        record = primitive_copy(h.save())
        record["localSnapshot"]["quests"] = {}
        record["partnerSnapshot"]["quests"] = {}
        record["localSnapshot"]["trackedQuestIDs"] = {i: q for i, q in enumerate(
            [100, 100, -1, 0, False, "100", "bad", {}, 10000001] + list(range(101, 180)), 1)}
        record["partnerSnapshot"]["trackedQuestIDs"] = "broken"
        saved = primitive_copy(h.ns.char)
        saved["duoJourney"]["history"] = {1: record}
        other = JourneyHost(saved=saved)
        snapshot = other.jcall("GetCheckpoint").localSnapshot
        ids = list(snapshot.trackedQuestIDs.values())
        self.assertEqual(len(ids), 48)
        self.assertEqual(len(set(ids)), 48)
        self.assertEqual(ids[:3], [100, 101, 102])
        self.assertEqual(len(other.jcall("GetCheckpoint").partnerSnapshot.trackedQuestIDs), 0)
        other.state.localSnapshots[100] = other.table({"known": False})
        catch = other.jcall("GetCatchUp")
        self.assertEqual(catch.status, "unknown")
        self.assertGreater(catch.unknownCount, 0)
        self.assertIsNone(catch.quests[1].localState)
        self.assertIsNone(catch.quests[1].partnerState)
        primitive_copy(other.ns.char.duoJourney)

    def test_legacy_empty_observation_snapshot_does_not_announce_equal_journals(self):
        h = JourneyHost()
        h.duo.GetQuestIDs = h.lua.eval("function() return {} end")
        h.save()
        self.assertEqual(h.jcall("GetCatchUp").status, "unknown")
        self.assertNotIn("No hay diferencias", h.jcall("GetCheckpointReport"))
        self.assertIn("no conserva observaciones", h.jcall("GetCheckpointReport"))

    def test_auto_save_waits_five_minutes_and_never_runs_without_confirmed_partner(self):
        h = JourneyHost()
        h.jcall("Tick", 1)
        self.assertEqual(len(h.ns.char.duoJourney.history), 1)
        for _ in range(4):
            h.refresh_time(60); h.jcall("Tick", 60)
        self.assertEqual(len(h.ns.char.duoJourney.history), 1)
        h.refresh_time(60); h.jcall("Tick", 60)
        self.assertEqual(len(h.ns.char.duoJourney.history), 2)
        h.duo.peer = None
        for _ in range(10):
            h.jcall("Tick", 60)
        self.assertEqual(len(h.ns.char.duoJourney.history), 2)

    def test_rejoining_does_not_immediately_overwrite_catch_up_checkpoint(self):
        h = JourneyHost()
        h.save()
        saved = primitive_copy(h.ns.char)
        other = JourneyHost(saved=saved)
        other.quest(100, delivered=True)
        other.jcall("Tick", 1)
        self.assertEqual(len(other.ns.char.duoJourney.history), 1)
        self.assertEqual(other.ns.char.duoJourney.history[1].localSnapshot.quests[100].state, 0)
        other.journey.frame.scripts.OnEvent(other.journey.frame, "PLAYER_LOGOUT")
        self.assertEqual(len(other.ns.char.duoJourney.history), 2)
        self.assertEqual(other.ns.char.duoJourney.history[2].localSnapshot.quests[100].state, 3)

    def test_supply_stops_are_factual_and_level_proposals_compare_checkpoint_level(self):
        h = JourneyHost()
        h.save()
        h.state.localSupplies = h.table({"known": True, "freeSlots": 0, "durabilityPercent": 20, "manaPercent": 10, "level": 2})
        h.state.partnerSupplies = h.table({"known": True, "freeSlots": 1, "durabilityPercent": 100, "manaPercent": 100, "level": 2})
        stops = list(h.jcall("GetStops").values())
        kinds = {(x.kind, x.owner) for x in stops}
        self.assertEqual(kinds, {("vendor", "local"), ("repair", "local"), ("rest", "local"),
                                 ("trainer", "local"), ("vendor", "partner"), ("trainer", "partner")})
        self.assertIn("bolsas llenas", stops[0].text)

    def test_missing_supply_data_and_non_mana_classes_do_not_invent_needs(self):
        h = JourneyHost()
        h.state.localSupplies = h.table({"known": True, "freeSlots": 10, "durabilityPercent": 100, "level": 1})
        h.state.partnerSupplies = h.table({"known": False, "freeSlots": 0, "durabilityPercent": 0, "manaPercent": 0})
        self.assertEqual(len(h.jcall("GetStops")), 0)
        h.state.localSupplies = None
        self.assertEqual(len(h.jcall("GetStops")), 0)
        self.assertIsInstance(h.jcall("GetStopReport"), str)

    def test_stop_ready_agreement_is_separate_from_progress_and_never_forces_actions(self):
        h = JourneyHost()
        h.state.localSupplies.freeSlots = 0
        before = h.progress_snapshot()
        self.assertTrue(h.jcall("BeginStop", 1))
        self.assertFalse(h.jcall("GetStopStatus").bothReady)
        self.assertTrue(h.jcall("SetStopReady", True))
        h.state.peerStopKind, h.state.peerStopReady = "vendor", True
        status = h.jcall("GetStopStatus")
        self.assertTrue(status.localReady)
        self.assertTrue(status.partnerReady)
        self.assertTrue(status.bothReady)
        self.assertEqual(h.progress_snapshot(), before)
        self.assertTrue(h.jcall("EndStop"))
        self.assertEqual(h.progress_snapshot(), before)
        self.assertFalse(h.jcall("GetStopStatus").localActive)

    def test_different_or_stale_partner_stop_is_never_both_ready(self):
        h = JourneyHost()
        h.jcall("SetStop", "repair")
        h.jcall("SetStopReady", True)
        h.state.peerStopKind, h.state.peerStopReady = "rest", True
        self.assertFalse(h.jcall("GetStopStatus").bothReady)
        h.state.checkpointKnown = False
        self.assertFalse(h.jcall("GetStopStatus").known)
        self.assertFalse(h.jcall("GetStopStatus").bothReady)
        h.state.friendOnline = False
        self.assertFalse(h.jcall("SetStopReady", True)[0])

    def test_unknown_offline_or_disabled_partner_does_not_invent_an_active_stop(self):
        for field, value in [("peer", None), ("friendOnline", False), ("members", 1), ("disabled", True)]:
            with self.subTest(field=field):
                h = JourneyHost()
                if field == "peer":
                    h.duo.peer = None
                elif field == "disabled":
                    h.ns.char.duo.enabled = False
                else:
                    setattr(h.state, field, value)
                status = h.jcall("GetStopStatus")
                self.assertFalse(status.active)
                self.assertIsNone(status.kind)
                self.assertIsNone(status.partnerKind)
                self.assertFalse(status.bothReady)

    def test_peer_stop_can_be_joined_without_inventing_supply_information(self):
        h = JourneyHost()
        h.state.localSupplies, h.state.partnerSupplies = None, None
        h.state.peerStopKind = "rest"
        stops = h.jcall("GetStops")
        self.assertEqual(stops[1].owner, "partner")
        self.assertTrue(stops[1].coordinated)
        self.assertTrue(h.jcall("BeginStop", 1))
        self.assertEqual(h.jcall("GetStopStatus").kind, "rest")

    def test_reload_clears_ready_and_provider_reports_only_local_checkpoint(self):
        h = JourneyHost()
        h.peer(cursor=99)
        record = h.save()
        h.jcall("SetStop", "repair")
        h.jcall("SetStopReady", True)
        packet = h.duo.checkpointProvider()
        self.assertEqual(packet.checkpointID, str(record.id))
        self.assertEqual(packet.cursor, 1)
        self.assertEqual(packet.stopKind, "repair")
        self.assertTrue(packet.stopReady)
        other = JourneyHost(saved=primitive_copy(h.ns.char))
        self.assertFalse(other.jcall("GetStopStatus").localReady)
        other.jcall("Initialize")
        self.assertEqual(other.state.providerRegistrations, 1)


class RealDuoJourneyIntegrationTests(unittest.TestCase):
    def test_two_clients_with_hidden_quest_apis_cannot_save_false_agreement(self):
        from test_duo_enhanced import EnhancedHost

        a, b = EnhancedHost(), EnhancedHost("Dos", "Uno")
        for h in (a, b):
            h.load((ADDON / "DuoJourney.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
            h.journey = h.ns.DuoJourney
            h.journey.Initialize(h.journey)
            h.lua.execute('''
                C_QuestLog.IsOnQuest = function() return nil end
                C_QuestLog.IsQuestFlaggedCompleted = function() return nil end
                IsQuestFlaggedCompleted = nil
            ''')
        for _ in range(3):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        for h in (a, b):
            self.assertTrue(h.duo.GetContext(h.duo).known)
            self.assertFalse(h.duo.LocalQuest(h.duo, 100).known)
            result = h.journey.SaveCheckpoint(h.journey)
            self.assertTrue(result[0])
            self.assertEqual(list(result[1].localSnapshot.trackedQuestIDs.values()), [100])
            catch = h.journey.GetCatchUp(h.journey)
            self.assertEqual(catch.status, "unknown")
            self.assertEqual(catch.unknownCount, 1)
            self.assertNotIn("No hay diferencias", h.journey.GetCheckpointReport(h.journey))

    def test_two_shipping_duo_clients_exchange_checkpoint_stop_and_objective_data(self):
        a, b = DuoHost(), DuoHost("Dos", "Uno")
        for h in (a, b):
            h.load((ADDON / "DuoJourney.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
            h.journey = h.ns.DuoJourney
            h.journey.Initialize(h.journey)
            h.quest(100, onQuest=True, objectives=[{
                "finished": False, "numFulfilled": 3, "numRequired": 10,
            }])
        for _ in range(8):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        self.assertTrue(a.duo.GetContext(a.duo).known)
        self.assertTrue(a.journey.SaveCheckpoint(a.journey)[0])
        self.assertTrue(b.journey.SaveCheckpoint(b.journey)[0])
        for h in (a, b):
            self.assertTrue(h.journey.SetStop(h.journey, "repair"))
            self.assertTrue(h.journey.SetStopReady(h.journey, True))
        for _ in range(20):
            a.tick(); b.tick(); a.deliver_to(b); b.deliver_to(a)
        for h in (a, b):
            self.assertTrue(h.journey.GetStopStatus(h.journey).bothReady)
            remote = h.duo.GetPartnerCheckpoint(h.duo)
            self.assertTrue(remote.known)
            self.assertEqual(remote.stopKind, "repair")
            self.assertEqual(remote.quests[100].objectives[1].current, 3)
            catch = h.journey.GetCatchUp(h.journey)
            self.assertEqual(catch.status, "aligned")
            self.assertEqual(h.position(), 1)


if __name__ == "__main__":
    unittest.main()
