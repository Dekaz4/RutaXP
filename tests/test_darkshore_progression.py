"""The real Darkshore beach chain, omissions, recovery and two-player progress."""
import json
from pathlib import Path
import unittest

from test_access_navigation import WORLD_STUBS
from test_auto_party_integration import AutomaticPartyHost
from test_duo_journey import primitive_copy


DARK = "forever/alliance/03-darkshore"
SOURCE = Path(__file__).resolve().parents[1] / "RutaXP/Source/leveling.json"
GUIDE = next(g for g in json.loads(SOURCE.read_text(encoding="utf-8"))["guides"] if g["id"] == DARK)
TITLES = {g["quest"]: g["title"] for s in GUIDE["steps"] for g in s["goals"] if g.get("quest") and g.get("title")}


class DarkshoreHost(AutomaticPartyHost):
    def __init__(self, name="Uno", friend="Dos", cls="PALADIN", legs=2, skipped=None, paired=False):
        self.starting_legs = legs
        saved = {"seen": True, "activeGuide": DARK, "auto": True,
                 "progress": {DARK: {"cursor": 2, "placed": True, "review": False,
                                      "routeRevision": GUIDE.get("routeRevision", 1),
                                      "confirmed": {"1:1": True}, "skipped": skipped or {}}},
                 "duo": {"enabled": paired, "wait": paired, "autoPair": paired}}
        super().__init__(name, friend, active_guide=DARK, saved=saved, race="Dwarf", cls=cls)

    def quest(self, *args, **kwargs):
        self.s.level = self.s.friendLevel = 16
        self.s.mapID, self.s.x, self.s.y = 1439, .374, .521
        self.h.g.ACCESS_NS = self.ns
        self.h.lua.execute(WORLD_STUBS)
        self.set_quest(983, counts=[(self.starting_legs, 6)])
        self.set_quest(3524, delivered=True)

    def set_quest(self, qid, *, active=True, delivered=False, counts=()):
        objectives = [{"text": f"Objetivo: {current}/{required}", "numFulfilled": current,
                       "numRequired": required, "finished": current >= required}
                      for current, required in counts]
        self.s.quests[qid] = self.h.table({"title": TITLES.get(qid, f"Misión {qid}"),
            "onQuest": active and not delivered, "delivered": delivered,
            "complete": bool(objectives) and all(o["finished"] for o in objectives) and not delivered,
            "objectives": objectives})
        self.s.entries = self.h.table([{"questID": q, "isHeader": False}
                                      for q, entry in self.s.quests.items() if entry.onQuest])

    def event(self, name="QUEST_LOG_UPDATE", *args):
        self.h.g.EmitAddonEvent(name, *args)

    @property
    def progress_state(self):
        return self.ns.char.progress[DARK]

    @property
    def cursor(self):
        return self.progress_state.cursor

    def active_goal(self):
        result = self.ns.GetActiveGoal(self.ns)
        return result if isinstance(result, tuple) else (result,)

    def point(self):
        _, step, _ = self.ns.GetCurrent(self.ns)
        return self.ns.GetStepWaypoint(self.ns, step)

    def go(self, step):
        self.progress_state.cursor, self.progress_state.review = step, False
        self.ns.Sync(self.ns)


class DarkshoreProgressionTests(unittest.TestCase):
    def assert_goal(self, host, kind, quest, status=None):
        active = host.active_goal()
        self.assertEqual((active[0].t, active[0].quest), (kind, quest))
        if status:
            self.assertEqual(active[2], status)
        return active[0]

    def test_beach_collect_delivery_acceptance_and_next_boxes_use_real_quest_credit(self):
        h = DarkshoreHost()
        self.assert_goal(h, "collect", 983, "active")
        self.assertEqual(h.point().goal.quest, 983)
        h.set_quest(983, counts=[(6, 6)])
        h.event()
        self.assert_goal(h, "turnin", 983)
        self.assertEqual(h.point().goal.object, 17182)
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 983))
        h.set_quest(983, delivered=True)
        h.event("QUEST_TURNED_IN", 983)
        self.assert_goal(h, "accept", 1001, "active")
        self.assertEqual(h.point().goal.object, 17182)
        h.set_quest(1001, counts=[(0, 3)])
        h.event("QUEST_ACCEPTED", 1001)
        self.assert_goal(h, "collect", 1001)
        h.set_quest(1001, counts=[(3, 3)])
        h.event()
        self.assertEqual(h.cursor, 3)

        # The next delivery is explicitly in the later northern excursion.
        for q in (954, 955, 956, 957):
            h.set_quest(q, delivered=True)
        h.go(9)
        self.assert_goal(h, "turnin", 1001)
        self.assertEqual(h.point().goal.object, 17183)
        h.set_quest(1001, delivered=True)
        h.event("QUEST_TURNED_IN", 1001)
        self.assert_goal(h, "accept", 1002)
        h.set_quest(1002, counts=[(0, 6)])
        h.event("QUEST_ACCEPTED", 1002)
        self.assertEqual(h.cursor, 10)
        self.assert_goal(h, "collect", 1002)
        h.set_quest(1002, counts=[(6, 6)])
        h.event()
        self.assert_goal(h, "turnin", 1002)
        self.assertEqual(h.point().goal.object, 17184)
        h.set_quest(1002, delivered=True)
        h.event("QUEST_TURNED_IN", 1002)
        self.assert_goal(h, "accept", 1003)
        h.set_quest(1003, counts=[(0, 4)])
        h.event("QUEST_ACCEPTED", 1003)
        self.assert_goal(h, "collect", 1003)
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 1003))

    def test_skipping_only_the_work_never_hides_the_selected_delivery_row(self):
        h = DarkshoreHost(skipped={"2:1": True})
        _, step, state = h.ns.GetCurrent(h.ns)
        goal, index, _ = h.active_goal()[:3]
        rows = h.ns.GetStepGoalItems(h.ns, step, state)
        rows = rows[0] if isinstance(rows, tuple) else rows
        self.assertIn(index, {row.index for row in rows.values()})
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 983))
        self.assertEqual(h.s.quests[983].objectives[1].numFulfilled, 2)
        self.assertEqual(h.ns.GetGoalStatus(h.ns, step.goals[3], step, state, 3)[0], "blocked")

    def test_blocked_rows_recover_the_real_prerequisite_with_one_left_click(self):
        for skipped, goal_index in (({"2:1": True}, 2), ({"2:1": True, "2:2": True}, 3)):
            with self.subTest(skipped=skipped):
                h = DarkshoreHost(skipped=skipped)
                h.ns.RefreshUI(h.ns)
                row = next(row for row in h.ns.trackerRows.values()
                           if row.shown and not row.preview and row.goalIndex == goal_index)
                before = primitive_copy(h.progress_state)
                row.scripts.OnClick(row, "LeftButton")
                self.assertEqual(h.ns.char.activeGuide, "_recovery")
                self.assert_goal(h, "collect", 983, "active")
                self.assertEqual(h.point().goal.quest, 983)
                self.assertEqual(h.s.quests[983].objectives[1].numFulfilled, 2)
                self.assertEqual(primitive_copy(h.progress_state), before)
                self.assertFalse(h.ns.IsQuestDelivered(h.ns, 983))

    def test_blocked_requirement_has_no_premature_box_destination_before_recovery(self):
        for skipped in ({"2:1": True}, {"2:1": True, "2:2": True}):
            with self.subTest(skipped=skipped):
                h = DarkshoreHost(skipped=skipped)
                self.assertEqual(h.active_goal()[2], "blocked")
                self.assertIsNone(h.point())
                self.assertEqual(h.cursor, 2)

    def test_unknown_completion_does_not_unlock_411_or_advance_the_visit(self):
        h = DarkshoreHost(skipped={"2:1": True})
        h.h.lua.execute("""
            local complete = C_QuestLog.IsComplete
            function C_QuestLog.IsComplete(id)
                if id == 983 then return nil end
                return complete(id)
            end
        """)
        h.event()
        _, step, state = h.ns.GetCurrent(h.ns)
        self.assertEqual(h.cursor, 2)
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 983))
        self.assertFalse(h.ns.IsQuestActive(h.ns, 1001))
        self.assertEqual(h.ns.GetGoalStatus(h.ns, step.goals[3], step, state, 3)[0], "blocked")

    def test_preview_click_does_not_start_recovery_or_change_saved_progress(self):
        h = DarkshoreHost(skipped={"2:1": True, "2:2": True})
        h.set_quest(2118, counts=[(0, 1)])
        h.ns.RefreshUI(h.ns)
        row = next(row for row in h.ns.trackerRows.values() if row.shown and row.preview)
        before = primitive_copy(h.ns.char.progress)
        row.scripts.OnClick(row, "LeftButton")
        self.assertEqual(h.ns.char.activeGuide, DARK)
        self.assertIsNone(h.ns.char.recovery)
        self.assertEqual(primitive_copy(h.ns.char.progress), before)

    def test_restoring_pending_journal_work_recovers_legs_without_inventing_delivery(self):
        h = DarkshoreHost(skipped={"2:1": True, "2:2": True, "9:4": True})
        self.assert_goal(h, "accept", 1001, "blocked")
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 983))
        ok, _ = h.ns.ResumePendingQuests(h.ns)
        self.assertTrue(ok)
        self.assertEqual(h.cursor, 2)
        self.assert_goal(h, "collect", 983, "active")
        self.assertEqual(h.point().goal.quest, 983)
        self.assertIsNone(h.progress_state.skipped["2:1"])
        self.assertIsNone(h.progress_state.skipped["2:2"])
        self.assertTrue(h.progress_state.skipped["9:4"])
        self.assertTrue(h.progress_state.confirmed["1:1"])
        self.assertEqual(h.s.quests[983].objectives[1].numFulfilled, 2)

    def test_explicit_recovery_finishes_827_then_restores_the_blocked_411_visit(self):
        h = DarkshoreHost(skipped={"2:1": True, "2:2": True, "9:4": True})
        recovery = h.ns.Recovery
        blockers = recovery.GetBlockers(recovery)
        entry = next(row for row in blockers.values() if row.questID == 1001)
        self.assertEqual(list(entry.requiredQuestIDs.values()), [983])
        before = primitive_copy(h.progress_state)
        ok, _ = recovery.Start(recovery, 1001)
        self.assertTrue(ok)
        self.assertEqual(h.ns.char.activeGuide, "_recovery")
        self.assert_goal(h, "collect", 983)
        self.assertEqual(h.point().goal.quest, 983)
        h.set_quest(983, counts=[(6, 6)])
        h.event()
        self.assert_goal(h, "turnin", 983)
        self.assertEqual(h.point().goal.object, 17182)
        h.set_quest(983, delivered=True)
        h.event("QUEST_TURNED_IN", 983)
        self.assertEqual(h.ns.char.activeGuide, DARK)
        self.assertEqual(primitive_copy(h.progress_state), before)
        self.assert_goal(h, "accept", 1001, "active")

    def test_paladin_and_hunter_do_not_enter_druid_training_visits(self):
        for cls in ("PALADIN", "HUNTER"):
            h = DarkshoreHost(cls=cls)
            guide = h.ns.guides[DARK]
            for index in (12, 13, 38, 39, 40, 41, 42):
                with self.subTest(cls=cls, step=index):
                    step = guide.steps[index]
                    self.assertTrue(h.ns.IsStepComplete(h.ns, step, h.progress_state))
                    for gi, goal in step.goals.items():
                        self.assertEqual(h.ns.GetGoalStatus(h.ns, goal, step, h.progress_state, gi)[0], "skip")

    def test_two_classes_wait_for_the_slower_beach_chain_without_copying_credit(self):
        a = DarkshoreHost(legs=2, paired=True)
        b = DarkshoreHost("Dos", "Uno", cls="HUNTER", legs=5, paired=True)
        a.s.friendClass, b.s.friendClass = "HUNTER", "PALADIN"
        for h in (a, b):
            h.roster()

        def exchange(ticks=40):
            for _ in range(ticks):
                a.tick(); b.tick()
                a.deliver(b); b.deliver(a)

        exchange(75)
        self.assertEqual((a.cursor, b.cursor), (2, 2))
        a.set_quest(983, delivered=True)
        a.event("QUEST_TURNED_IN", 983)
        a.set_quest(1001, counts=[(3, 3)])
        a.event("QUEST_ACCEPTED", 1001)
        exchange()
        self.assertEqual((a.cursor, b.cursor), (2, 2))
        self.assertEqual(b.s.quests[983].objectives[1].numFulfilled, 5)
        self.assertFalse(b.ns.IsQuestDelivered(b.ns, 983))
        self.assertFalse(b.ns.IsQuestActive(b.ns, 1001))
        self.assert_goal(b, "collect", 983)

        b.set_quest(983, counts=[(6, 6)])
        b.event()
        exchange()
        self.assert_goal(b, "turnin", 983)
        self.assertEqual((a.cursor, b.cursor), (2, 2))
        b.set_quest(983, delivered=True)
        b.event("QUEST_TURNED_IN", 983)
        self.assert_goal(b, "accept", 1001)
        b.set_quest(1001, counts=[(3, 3)])
        b.event("QUEST_ACCEPTED", 1001)
        exchange()
        self.assertEqual((a.cursor, b.cursor), (3, 3))
        for h in (a, b):
            self.assertFalse(h.ns.IsQuestDelivered(h.ns, 1001))
            self.assertLessEqual(h.s.maxSyncDepth, 2)
            self.assertTrue(all(len(packet["message"]) <= 255 for packet in h.packets))


if __name__ == "__main__":
    unittest.main()
