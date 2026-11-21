import unittest

from test_quest_engine import ADDON, QuestEngineHost


class DesolaceCemeteryTests(unittest.TestCase):
    chapter = "forever/alliance/30-40/02-desolace"

    def setUp(self):
        h = self.h = QuestEngineHost(catalog=True)
        h.load((ADDON / "GuideMigrations.lua").read_text(encoding="utf-8"), "RutaXP", h.ns)
        h.state.level, h.state.classToken = 33, "ROGUE"
        h.initialize()
        h.call("SelectGuide", self.chapter)
        self.guide, _, self.progress = h.call("GetCurrent")
        h.ns.char.auto = False

    def test_both_materials_at_first_visit_in_any_journal_order(self):
        step = self.guide.steps[14]
        self.assertEqual([(g.quest, g.item, g.oi, g["count"]) for g in step.goals.values()],
                         [(1459, 6248, 1, 7), (1459, 6249, 2, 3)])
        self.progress.cursor = 14
        for done, left in ((1, 2), (2, 1)):
            self.h.quest(1459, onQuest=True, complete=False,
                         objectives=[{"finished": i == done} for i in (1, 2)])
            self.assertEqual(self.h.active()[1], left)

    def test_old_cursor_rechecks_pending_hides_and_translates_explicit_skips(self):
        self.progress.routeRevision, self.progress.cursor = 3, 17
        self.progress.skipped = self.h.table({"18:2": True})
        self.h.call("MigrateGuideProgress")
        self.assertEqual(self.progress.cursor, 14)
        self.assertTrue(self.progress.skipped["14:2"])
        self.assertIsNone(self.progress.skipped["18:2"])
        self.assertEqual(self.h.call("GetGuideCursorForRevision", self.chapter, 22, 3), 22)

    def test_roundup_is_optional_with_ready_turnin_preserved(self):
        h = self.h
        pickup = self.guide.steps[17].goals[2]
        work = self.guide.steps[18].goals[1]
        handin = self.guide.steps[19].goals[1]
        self.assertEqual([g.quest for g in (pickup, work, handin)], [5561] * 3)
        self.assertEqual(h.status(pickup), "skip")
        h.quest(5561, onQuest=True, complete=False)
        self.assertEqual(h.status(work), "skip")
        h.ns.char.optional = True
        self.assertEqual(h.status(work), "active")
        h.ns.char.optional = False
        h.ns.char.duo = h.table({"enabled": True})
        self.assertEqual(h.status(work), "active")
        h.ns.char.duo.enabled = False
        h.quest(5561, onQuest=True, complete=True)
        self.assertEqual(h.status(handin), "active")
