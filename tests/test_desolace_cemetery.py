"""Real character saves from the two later Desolace catalogs can return to 0.7.36."""
import hashlib
import unittest

from test_addon import ADDON
from test_westfall_migration import MigrationHost, WEST


DESOLACE = "forever/alliance/30-40/02-desolace"


def restore(cursor, quests=None, active=DESOLACE, **progress):
    state = {"cursor": cursor, "routeRevision": 4, "placed": True, **progress}
    host = MigrationHost({"activeGuide": active, "auto": False, "seen": True,
                          "progress": {DESOLACE: state, WEST: {"routeRevision": 4, "cursor": 9}}},
                         quests=quests)
    host.state.level = 33
    host.initialize()
    return host, host.ns.char.progress[DESOLACE]


class DesolaceCemeteryTests(unittest.TestCase):
    def test_runtime_uses_the_original_57_chapter_catalog(self):
        payload = (ADDON / "Leveling.lua").read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(payload).hexdigest(),
                         "9bf73f8371177107cf2397bb89d3522b3d335eca9eef691f86a86b9e3ef6b4a4")
        host, _ = restore(14)
        self.assertEqual(len(list(host.ns.guides)), 57)
        chapter = host.ns.guides[DESOLACE]
        self.assertEqual((chapter.routeRevision, chapter.steps[14].goals[1].item,
                          chapter.steps[18].goals[2].item), (3, 6248, 6249))

    def test_reassigns_the_moved_mark_once_and_preserves_the_active_chapter(self):
        h, state = restore(17, active=WEST, skipped={"14:2": True}, confirmed={"17:1": True})
        self.assertEqual((state.cursor, state.routeRevision), (17, 3))
        self.assertTrue(state.skipped["18:2"])
        self.assertIsNone(state.skipped["14:2"])
        self.assertTrue(state.confirmed["17:1"])
        self.assertEqual(h.ns.char.activeGuide, WEST)
        self.assertEqual(h.ns.char.progress[WEST].cursor, 9)
        before = h.saved()
        h.call("MigrateGuideProgress")
        self.assertEqual(h.saved(), before)

    def test_saved_waypoint_and_backup_follow_the_material_in_a_manual_review(self):
        old, new = (DESOLACE + suffix for suffix in (":14:2", ":18:2"))
        h = MigrationHost({"activeGuide": DESOLACE, "auto": False, "seen": True,
                           "guideMigrationBackups": {DESOLACE + ":3": {"original": True}},
                           "progress": {DESOLACE: {"cursor": 14, "routeRevision": 4, "placed": True,
                                                   "review": True, "confirmed": {"14:2": True}}},
                           "waypoints": {"active": {"key": old}, "entries": {old: {"targetKey": old}}}})
        h.initialize()
        char = h.ns.char
        self.assertTrue(char.progress[DESOLACE].review)
        self.assertTrue(char.progress[DESOLACE].confirmed["18:2"])
        self.assertTrue(char.guideMigrationBackups[DESOLACE + ":3"].original)
        self.assertEqual(char.guideMigrationBackups[DESOLACE + ":4-to-3"].progress.routeRevision, 4)
        self.assertEqual(char.waypoints.active.key, new)
        self.assertEqual(char.waypoints.entries[new].targetKey, new)

    def test_pending_hides_are_recovered_after_the_journal_is_ready(self):
        h, state = restore(20, {1459: {"onQuest": True, "complete": False}})
        self.assertEqual(state.cursor, 20)
        self.assertTrue(state.checkDesolaceCollections)
        h.quest(1459, onQuest=True, complete=False, objectives=[{"finished": True}, {"finished": False}])
        h.update_log()
        self.assertEqual(state.cursor, 18)
        self.assertIsNone(state.checkDesolaceCollections)

    def test_existing_kodo_work_is_recovered_without_reopening_a_completed_or_reviewed_route(self):
        active_kodo = {5561: {"onQuest": True, "complete": False}}
        _, state = restore(19, active_kodo)
        self.assertEqual(state.cursor, 18)
        for cursor, progress in [(19, {"review": True}), (22, {}), (21, {"skipped": {"18:1": True}})]:
            with self.subTest(cursor=cursor, progress=progress):
                _, state = restore(cursor, active_kodo, **progress)
                self.assertEqual((state.cursor, state.routeRevision), (cursor, 3))
