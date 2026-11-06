"""Existing Westfall characters keep their bookmarks and recover Alba's chain."""
import unittest

from test_addon import ADDON
from test_duo_journey import primitive_copy
from test_quest_engine import QuestEngineHost


WEST = "forever/alliance/02-westfall"
ELWYNN = "forever/alliance/human/01-elwynn-forest"
BACKUP = WEST + ":2"


class MigrationHost(QuestEngineHost):
    def __init__(self, saved=None, quests=None):
        super().__init__(catalog=True)
        self.state.level = 14
        self.state.raceToken = "Dwarf"
        factory = self.globals.CreateFrame
        self.lua.execute("""
            local original = CreateFrame
            function CreateFrame(...)
                local frame = original(...)
                TEST.migrationFrame = frame
                return frame
            end
        """)
        self.load((ADDON / "GuideMigrations.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        self.migration_frame = self.state.migrationFrame
        self.globals.CreateFrame = factory
        self.load((ADDON / "Recovery.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        self.ns.RestoreFeatures = self.lua.eval("function(self) self.Recovery:RestoreSaved() end")
        self.globals.RutaXPCharDB = self.table(saved or {
            "seen": True, "auto": False, "activeGuide": WEST,
            "progress": {WEST: {"cursor": 6, "review": True, "placed": True}},
        })
        for quest, data in (quests or {}).items():
            self.quest(quest, **data)

    @property
    def progress(self):
        return self.ns.char.progress[WEST]

    def saved(self):
        return primitive_copy(self.ns.char)

    def update_log(self):
        self.migration_frame.scripts.OnEvent(self.migration_frame, "QUEST_LOG_UPDATE")


class WestfallMigrationTests(unittest.TestCase):
    def pending_gills(self, complete=False):
        return {92742: {"delivered": True}, 92744: {
            "onQuest": True, "complete": complete,
            "objectives": [{"numFulfilled": 7 if complete else 3, "numRequired": 7, "finished": complete}],
        }}

    def saved_state(self, cursor=6, **extra):
        saved = {"seen": True, "auto": False, "activeGuide": WEST,
                 "progress": {WEST: {"cursor": cursor, "review": True, "placed": True,
                    "confirmed": {"1:3": True, "12:9": True, "1:11": True, "5:1": True},
                    "skipped": {"1:11": True, "6:1": True, "8:1": True, "12:6": True, "13:1": True}}},
                 "duo": {"enabled": True, "wait": True, "autoPair": True, "partner": "MyFriend"}}
        saved.update(extra)
        return saved

    def test_mine_blocker_rejoins_real_gills_and_keeps_other_progress(self):
        saved = self.saved_state()
        original = primitive_copy(saved)
        host = MigrationHost(saved, self.pending_gills())
        journal = primitive_copy(host.state.quests)
        host.initialize()
        state = host.progress
        self.assertEqual(state.cursor, 6)  # Coast, not the old mine step.
        self.assertIsNone(state.review)
        self.assertEqual(state.routeRevision, 2)
        self.assertFalse(host.ns.char.auto)
        self.assertEqual(primitive_copy(host.ns.char.duo), saved["duo"])
        self.assertTrue(state.confirmed["1:3"])
        self.assertTrue(state.confirmed["13:7"])
        self.assertTrue(state.confirmed["5:1"])  # Real delivered objective is retained.
        self.assertTrue(state.skipped["14:1"])
        for key in ("7:3", "8:1", "6:1", "7:2"):
            self.assertIsNone(state.confirmed[key])
            self.assertIsNone(state.skipped[key])
        self.assertEqual(host.active()[0].quest, 92744)
        backup = host.ns.char.guideMigrationBackups[BACKUP]
        self.assertEqual(primitive_copy(backup.progress), original["progress"][WEST])
        self.assertEqual(primitive_copy(host.state.quests), journal)

    def test_old_bookmarks_and_marks_stay_with_their_actual_action(self):
        cases = {1: 1, 5: 5, 6: 8, 7: 9, 8: 6, 9: 10, 12: 13, 13: 14, 21: 22, 22: 23}
        for before, after in cases.items():
            with self.subTest(before=before):
                host = MigrationHost(self.saved_state(before), {92745: {"delivered": True}})
                host.initialize()
                state = host.progress
                self.assertEqual(state.cursor, after)
                self.assertTrue(state.review)
                self.assertTrue(state.confirmed["7:3"])
                self.assertTrue(state.skipped["8:1"])
                self.assertTrue(state.skipped["6:1"])
                self.assertTrue(state.skipped["7:2"])
                self.assertTrue(state.confirmed["13:7"])
                self.assertEqual(state.routeRevision, 2)

    def test_live_objectives_select_wells_coast_or_return_not_completed_work(self):
        cases = [
            ({92742: {"onQuest": True, "complete": False, "objectives": [
                {"finished": False}, {"finished": False}]}, 92744: {"onQuest": True}}, 3),
            ({92742: {"onQuest": True, "complete": False, "objectives": [
                {"finished": True}, {"finished": False}]}, 92744: {"onQuest": True}}, 5),
            (self.pending_gills(), 6),
            (self.pending_gills(complete=True), 7),
            ({92742: {"delivered": True}, 92744: {"delivered": True}}, 7),
            ({92742: {"delivered": True}}, 1),
        ]
        for quests, expected in cases:
            with self.subTest(expected=expected, quests=quests):
                host = MigrationHost(self.saved_state(), quests)
                host.initialize()
                self.assertEqual(host.progress.cursor, expected)

    def test_holding_mines_does_not_reopen_missing_prerequisite_history(self):
        host = MigrationHost(self.saved_state(), {92745: {"onQuest": True}})
        host.initialize()
        self.assertEqual(host.progress.cursor, 8)
        self.assertTrue(host.progress.skipped["8:1"])

    def test_end_and_outgoing_journey_are_not_reset(self):
        trips = {WEST: {"ready": True, "localStart": True, "cursor": 2}}
        host = MigrationHost(self.saved_state(22, guideTrips=trips, travelOrigins={"next": WEST}), self.pending_gills())
        host.initialize()
        self.assertEqual(host.progress.cursor, 23)
        self.assertIsNone(host.progress.routeRepairPending)
        self.assertEqual(primitive_copy(host.ns.char.guideTrips), trips)
        self.assertEqual(primitive_copy(host.ns.char.travelOrigins), {"next": WEST})

    def test_inactive_guide_waits_until_selected_without_changing_other_guide(self):
        saved = self.saved_state(activeGuide=ELWYNN)
        saved["progress"][ELWYNN] = {"cursor": 4, "review": True, "confirmed": {"1:1": True}}
        host = MigrationHost(saved, self.pending_gills())
        host.initialize()
        self.assertEqual(host.ns.char.activeGuide, ELWYNN)
        self.assertEqual(host.progress.cursor, 8)
        self.assertTrue(host.progress.routeRepairPending)
        host.update_log()
        self.assertEqual(host.ns.char.activeGuide, ELWYNN)
        self.assertEqual(host.progress.cursor, 8)
        self.assertEqual(primitive_copy(host.ns.char.progress[ELWYNN]), saved["progress"][ELWYNN])
        host.ns.char.activeGuide = WEST
        host.update_log()
        self.assertEqual(host.progress.cursor, 6)

    def test_reload_is_idempotent_and_does_not_reopen_new_manual_choices(self):
        host = MigrationHost(self.saved_state(), self.pending_gills())
        host.initialize()
        host.progress.skipped["6:1"] = True
        host.progress.cursor, host.progress.review = 8, True
        saved = host.saved()
        restored = MigrationHost(saved, self.pending_gills())
        restored.initialize()
        self.assertEqual(restored.saved(), saved)

    def test_fresh_progress_records_current_revision(self):
        host = MigrationHost({"seen": True, "activeGuide": WEST, "auto": False, "progress": {}})
        host.initialize()
        self.assertEqual(host.progress.routeRevision, 2)
        self.assertIsNone(host.ns.char.guideMigrationBackups)
        host.progress.cursor, host.progress.review = 6, True
        saved = host.saved()
        restored = MigrationHost(saved, self.pending_gills())
        restored.initialize()
        self.assertEqual(restored.saved(), saved)

    def test_unknown_quest_api_defers_only_live_repair_and_preserves_skips(self):
        host = MigrationHost(self.saved_state(), self.pending_gills())
        query = host.globals.C_QuestLog.IsOnQuest
        host.globals.C_QuestLog.IsOnQuest = host.lua.eval("function() return nil end")
        host.initialize()
        self.assertEqual(host.progress.cursor, 8)
        self.assertTrue(host.progress.routeRepairPending)
        self.assertTrue(host.progress.skipped["8:1"])
        self.assertTrue(host.progress.confirmed["7:3"])
        host.globals.C_QuestLog.IsOnQuest = query
        host.update_log()
        self.assertEqual(host.progress.cursor, 6)
        self.assertIsNone(host.progress.routeRepairPending)
        self.assertTrue(host.progress.confirmed["1:3"])

    def old_recovery(self, quest=92745):
        return {"version": 1, "active": True, "status": "active", "requestedQuestID": quest,
                "requiredQuestIDs": [quest], "bookmark": {"guideID": WEST, "cursor": 6, "review": True},
                "guide": {"id": "_recovery", "title": "Old recovery", "steps": [
                    {"title": "Acceptance", "goals": [{"t": "accept", "quest": quest}]},
                    {"title": "Delivery", "goals": [{"t": "turnin", "quest": quest}]}]}}

    def test_old_mine_recovery_is_archived_before_restore_and_uses_corrected_chain(self):
        saved = self.saved_state(activeGuide="_recovery", recovery=self.old_recovery())
        saved["progress"]["_recovery"] = {"cursor": 1, "confirmed": {"1:1": True}}
        host = MigrationHost(saved, self.pending_gills())
        host.initialize()
        self.assertEqual(host.ns.char.activeGuide, WEST)
        self.assertIsNone(host.ns.char.recovery)
        self.assertIsNone(host.ns.guides._recovery)
        self.assertEqual(host.progress.cursor, 6)
        backup = host.ns.char.guideMigrationBackups[BACKUP]
        self.assertEqual(primitive_copy(backup.recovery), primitive_copy(host.table(saved["recovery"])))
        self.assertEqual(primitive_copy(backup.recoveryProgress), saved["progress"]["_recovery"])

    def test_other_recovery_remains_active_with_its_return_bookmark_remapped(self):
        saved = self.saved_state(activeGuide="_recovery", recovery=self.old_recovery(100))
        saved["progress"]["_recovery"] = {"cursor": 1, "confirmed": {}}
        host = MigrationHost(saved, self.pending_gills())
        host.initialize()
        self.assertEqual(host.ns.char.activeGuide, "_recovery")
        self.assertEqual(host.ns.char.recovery.requestedQuestID, 100)
        self.assertEqual(host.ns.char.recovery.bookmark.cursor, 8)
        self.assertEqual(host.progress.cursor, 8)
        self.assertEqual(primitive_copy(host.ns.char.recovery.guide), primitive_copy(host.table(saved["recovery"]["guide"])))
        self.assertEqual(host.ns.char.guideMigrationBackups[BACKUP].recovery.bookmark.cursor, 6)

    def test_personal_waypoints_stay_on_same_action_and_preserve_coordinates(self):
        old = WEST + ":6:1:kill:92745"
        new = WEST + ":8:1:kill:92745"
        route_id = "observed:" + old
        points = [{"map": 1436, "x": 30.5, "y": 46.5, "label": "Entrada personal"}]
        waypoints = {"ownRoutes": {old: {"id": route_id, "points": points}},
                     "entries": {old + ":" + route_id: {"index": 1, "force": True, "targetKey": old},
                                 "access:cave": {"done": True, "targetKey": old}},
                     "active": {"key": old, "route": route_id, "entryKey": old + ":" + route_id}}
        saved = self.saved_state(waypoints=waypoints)
        host = MigrationHost(saved, {92745: {"delivered": True}})
        host.initialize()
        w = host.ns.char.waypoints
        self.assertIsNone(w.ownRoutes[old])
        self.assertEqual(w.ownRoutes[new].id, "observed:" + new)
        self.assertEqual(primitive_copy(w.ownRoutes[new].points), {1: points[0]})
        self.assertTrue(w.entries[new + ":observed:" + new].force)
        self.assertEqual(w.entries["access:cave"].targetKey, new)
        self.assertEqual(w.active.entryKey, new + ":observed:" + new)
        self.assertEqual(primitive_copy(host.ns.char.guideMigrationBackups[BACKUP].waypoints),
                         primitive_copy(host.table(waypoints)))

    def test_reset_then_reload_keeps_new_revision_and_new_step_identity(self):
        host = MigrationHost(self.saved_state(), self.pending_gills())
        host.initialize()
        host.call("ResetGuide", WEST)
        self.assertEqual(host.progress.routeRevision, 2)
        self.assertEqual(host.progress.cursor, 1)
        host.progress.cursor = 6
        host.progress.skipped = host.table({"6:1": True})
        saved = host.saved()
        restored = MigrationHost(saved, self.pending_gills())
        restored.initialize()
        self.assertEqual(restored.saved(), saved)

    def test_old_and_new_checkpoints_restore_only_own_cursor_and_save_revision(self):
        for revision, expected in ((None, 8), (1, 8), (2, 6)):
            with self.subTest(revision=revision):
                host = MigrationHost({"seen": True, "auto": False, "activeGuide": WEST, "progress": {}})
                host.initialize()
                own = {"guideID": WEST, "cursor": 6, "known": True, "quests": {}, "trackedQuestIDs": []}
                if revision is not None:
                    own["routeRevision"] = revision
                peer = {"guideID": WEST, "cursor": 21, "known": True, "quests": {}, "trackedQuestIDs": []}
                host.ns.char.duoJourney = host.table({"history": [{"id": 1, "partnerName": "friend-forever",
                    "localSnapshot": own, "partnerSnapshot": peer}]})
                host.load((ADDON / "DuoJourney.lua").read_text(encoding="utf-8-sig"), "RutaXP", host.ns)
                journey = host.ns.DuoJourney
                host.ns.char.progress[WEST] = None
                ok, message = journey.ResumeCheckpoint(journey, 1)
                self.assertTrue(ok, message)
                self.assertEqual(host.progress.cursor, expected)
                self.assertEqual(host.progress.routeRevision, 2)
                self.assertEqual(primitive_copy(host.progress.confirmed), {})
                self.assertEqual(host.ns.char.duoJourney.history[1].localSnapshot.routeRevision, revision)
                self.assertEqual(host.ns.char.duoJourney.history[1].localSnapshot.cursor, 6)
                self.assertEqual(host.ns.char.duoJourney.history[1].partnerSnapshot.cursor, 21)
                saved = host.saved()
                restored = MigrationHost(saved)
                restored.initialize()
                self.assertEqual(restored.saved(), saved)
                # A newly observed local checkpoint must stamp the current
                # revision instead of copying the older saved checkpoint's.
                host.ns.Duo = host.lua.eval("""{
                    GetContext = function() return {enabled=true, known=true, online=true, sameParty=true,
                        partnerName='friend-forever', guideID='forever/alliance/02-westfall', cursor=21} end,
                    GetQuestIDs = function() return {} end
                }""")
                ok, checkpoint = journey.SaveCheckpoint(journey, False)
                self.assertTrue(ok, checkpoint)
                self.assertEqual(checkpoint.localSnapshot.routeRevision, 2)
                self.assertEqual(checkpoint.localSnapshot.cursor, expected)
                self.assertEqual(checkpoint.partnerSnapshot.cursor, 21)


if __name__ == "__main__":
    unittest.main()
