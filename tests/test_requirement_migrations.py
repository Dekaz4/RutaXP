"""Progress migrations retain action identity and defer uncertain repairs."""
import json
import unittest

from test_addon import ADDON
from test_duo_journey import primitive_copy
from test_quest_engine import QuestEngineHost
from test_westfall_migration import MigrationHost, WEST


ROUTE = "forever/alliance/migration-test"
OTHER = "forever/alliance/other-test"
MIGRATION = {
    "from": 1, "to": 2, "previousStepCount": 3, "firstAffectedStep": 1,
    "affectedQuestIDs": [100], "stepMap": {1: 2, 2: 1, 3: 3, 4: 4},
    "goalMap": {"1:1": "2:1", "2:1": "1:1"},
}


class RequirementHost(QuestEngineHost):
    def __init__(self, cursor=3, active=ROUTE, affected=True, **saved):
        super().__init__()
        migration = {**MIGRATION, "affectedQuestIDs": [100] if affected else []}
        self.guide(ROUTE, routeRevision=2, progressMigrations=[migration], steps=[
            {"title": "Shared task", "goals": [{"t": "accept", "quest": 200}]},
            {"title": "Moved acceptance", "goals": [{"t": "accept", "quest": 100}]},
            {"title": "Work and delivery", "goals": [
                {"t": "complete", "quest": 100}, {"t": "turnin", "quest": 100}]},
        ])
        self.guide(OTHER, steps=[{"title": "Other task", "goals": [{"t": "accept", "quest": 300}]}])
        self.load((ADDON / "GuideMigrations.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        self.ns.char = self.table({"activeGuide": active, "auto": False, "progress": {
            ROUTE: {"cursor": cursor, "routeRevision": 1, "review": True,
                    "confirmed": {"1:1": True, "2:1": True, "3:1": True},
                    "skipped": {"1:1": True, "2:1": False, "3:2": True}},
            OTHER: {"cursor": 1, "review": True, "confirmed": {"1:1": True}},
        }, **saved})

    @property
    def progress(self):
        return self.ns.char.progress[ROUTE]

    def migrate(self):
        self.call("MigrateGuideProgress")


class RequirementMigrationTests(unittest.TestCase):
    def test_swapped_keys_remain_distinct_and_backups_do_not_alias_live_data(self):
        h = RequirementHost(cursor=1, affected=False, duo={"autoSession": {"reviews": {
            ROUTE: {"cursor": 1, "review": True}, OTHER: {"cursor": 1}}}})
        h.progress.confirmed = h.table({"1:1": "first", "2:1": "second", "3:1": "work", "custom": "unchanged"})
        before = primitive_copy(h.ns.char)
        h.migrate()
        self.assertEqual(h.progress.cursor, 2)
        self.assertEqual(primitive_copy(h.progress.confirmed), {
            "2:1": "first", "1:1": "second", "3:1": "work", "custom": "unchanged"})
        self.assertTrue(h.progress.skipped["2:1"])
        self.assertFalse(h.progress.skipped["1:1"])
        self.assertEqual(h.ns.char.duo.autoSession.reviews[ROUTE].cursor, 2)
        backup = h.ns.char.guideMigrationBackups[ROUTE + ":2"]
        self.assertEqual(primitive_copy(backup.progress), before["progress"][ROUTE])
        h.progress.confirmed["2:1"] = False
        self.assertEqual(backup.progress.confirmed["1:1"], "first")
        after = primitive_copy(h.ns.char)
        h.migrate()
        self.assertEqual(primitive_copy(h.ns.char), after)

    def test_inactive_state_maps_indices_without_selecting_or_repairing_it(self):
        h = RequirementHost(cursor=3, active=OTHER)
        other = primitive_copy(h.ns.char.progress[OTHER])
        h.migrate()
        self.assertEqual(h.ns.char.activeGuide, OTHER)
        self.assertEqual(primitive_copy(h.ns.char.progress[OTHER]), other)
        self.assertEqual(h.progress.cursor, 3)
        self.assertTrue(h.progress.requirementsRepair[100])
        self.assertTrue(h.progress.skipped["2:1"])
        self.assertFalse(h.call("RepairGuideRequirements"))
        h.ns.char.activeGuide = ROUTE
        self.assertTrue(h.call("RepairGuideRequirements"))
        self.assertEqual(h.progress.cursor, 2)
        self.assertIsNone(h.progress.skipped["2:1"])
        self.assertIsNone(h.progress.confirmed["3:1"])
        self.assertIsNone(h.progress.skipped["3:2"])
        self.assertTrue(h.progress.confirmed["1:1"])

    def test_unknown_api_remaps_marks_but_defers_repair_without_erasing_them(self):
        for api in ("IsOnQuest", "IsQuestFlaggedCompleted"):
            with self.subTest(api=api):
                h = RequirementHost()
                original = h.globals.C_QuestLog[api]
                h.globals.C_QuestLog[api] = h.lua.eval("function() return nil end")
                if api == "IsQuestFlaggedCompleted":
                    h.globals.IsQuestFlaggedCompleted = h.lua.eval("function() return nil end")
                h.migrate()
                self.assertEqual(h.progress.cursor, 3)
                self.assertTrue(h.progress.requirementsRepair[100])
                self.assertTrue(h.progress.skipped["2:1"])
                self.assertTrue(h.progress.confirmed["3:1"])
                h.globals.C_QuestLog[api] = original
                self.assertTrue(h.call("RepairGuideRequirements"))
                self.assertEqual(h.progress.cursor, 2)
                self.assertIsNone(h.progress.requirementsRepair)

    def test_current_journal_beats_historical_flag_and_repairs_only_pending_work(self):
        h = RequirementHost()
        h.quest(100, onQuest=True, delivered=True, complete=False)
        journal = primitive_copy(h.state.quests)
        h.migrate()
        self.assertEqual(h.progress.cursor, 3)
        self.assertTrue(h.progress.confirmed["2:1"])
        self.assertIsNone(h.progress.confirmed["3:1"])
        self.assertIsNone(h.progress.skipped["3:2"])
        self.assertEqual(primitive_copy(h.state.quests), journal)
        self.assertFalse(h.call("IsQuestDelivered", 100))

    def test_delivery_in_the_future_never_advances_past_unrelated_pending_steps(self):
        h = RequirementHost(cursor=2)
        h.quest(100, onQuest=True, complete=True)
        h.migrate()
        self.assertEqual(h.progress.cursor, 1)
        self.assertIsNone(h.progress.skipped["3:2"])

    def test_completed_route_and_outgoing_journey_are_not_reopened(self):
        trips = {ROUTE: {"cursor": 2, "ready": True, "localStart": True}}
        h = RequirementHost(cursor=4, guideTrips=trips, travelOrigins={OTHER: ROUTE})
        h.migrate()
        self.assertEqual(h.progress.cursor, 4)
        self.assertIsNone(h.progress.requirementsRepair)
        self.assertTrue(h.progress.review)
        self.assertEqual(primitive_copy(h.ns.char.guideTrips), trips)
        self.assertEqual(primitive_copy(h.ns.char.travelOrigins), {OTHER: ROUTE})

    def test_deferred_repair_does_not_reopen_a_route_completed_since_migration(self):
        h = RequirementHost()
        api = h.globals.C_QuestLog.IsOnQuest
        h.globals.C_QuestLog.IsOnQuest = h.lua.eval("function() return nil end")
        h.migrate()
        self.assertTrue(h.progress.requirementsRepair[100])
        h.progress.cursor = 4
        h.globals.C_QuestLog.IsOnQuest = api
        self.assertFalse(h.call("RepairGuideRequirements"))
        self.assertEqual(h.progress.cursor, 4)

    def test_waypoints_remap_target_and_route_keys_without_losing_coordinates(self):
        old1, old2 = ROUTE + ":1:1:accept:100", ROUTE + ":2:1:accept:200"
        new1, new2 = ROUTE + ":2:1:accept:100", ROUTE + ":1:1:accept:200"
        points = [{"map": 1436, "x": 30, "y": 40, "label": "Entrada"}]
        waypoints = {
            "ownRoutes": {old1: {"id": "observed:" + old1, "points": points}, old2: {"id": old2}},
            "entries": {old1 + ":observed:" + old1: {"targetKey": old1, "index": 2},
                        "access:mine": {"targetKey": old2, "done": True}},
            "active": {"key": old1, "route": "observed:" + old1,
                       "entryKey": old1 + ":observed:" + old1}}
        h = RequirementHost(affected=False, waypoints=waypoints)
        h.migrate()
        result = h.ns.char.waypoints
        self.assertEqual(set(result.ownRoutes.keys()), {new1, new2})
        self.assertEqual(result.ownRoutes[new1].id, "observed:" + new1)
        self.assertEqual(primitive_copy(result.ownRoutes[new1].points), {1: points[0]})
        self.assertEqual(result.entries["access:mine"].targetKey, new2)
        self.assertEqual(result.active.entryKey, new1 + ":observed:" + new1)
        self.assertEqual(primitive_copy(h.ns.char.guideMigrationBackups[ROUTE + ":2"].waypoints),
                         primitive_copy(h.table(waypoints)))

    def recovery(self, quest, active=True):
        return {"active": active, "requestedQuestID": quest, "requiredQuestIDs": [quest],
                "bookmark": {"guideID": ROUTE, "cursor": 1, "review": True},
                "guide": {"steps": [{"goals": [{"t": "turnin", "quest": quest}]}]}}

    def test_stale_recovery_is_archived_and_unrelated_recovery_keeps_its_plan(self):
        for quest in (100, 999):
            with self.subTest(quest=quest):
                original = self.recovery(quest)
                h = RequirementHost(active="_recovery", recovery=original)
                h.ns.char.progress._recovery = h.table({"cursor": 1, "confirmed": {"1:1": True}})
                h.migrate()
                backup = h.ns.char.guideMigrationBackups[ROUTE + ":2"]
                self.assertEqual(primitive_copy(backup.recovery), primitive_copy(h.table(original)))
                self.assertTrue(backup.recoveryProgress.confirmed["1:1"])
                if quest == 100:
                    self.assertEqual(h.ns.char.activeGuide, ROUTE)
                    self.assertIsNone(h.ns.char.recovery)
                    self.assertEqual(h.progress.cursor, 2)
                else:
                    self.assertEqual(h.ns.char.activeGuide, "_recovery")
                    self.assertEqual(h.ns.char.recovery.bookmark.cursor, 2)
                    self.assertEqual(primitive_copy(h.ns.char.recovery.guide), primitive_copy(h.table(original["guide"])))

    def test_inactive_recovery_bookmark_does_not_change_the_selected_route(self):
        h = RequirementHost(active=OTHER, recovery=self.recovery(100, active=False))
        h.migrate()
        self.assertEqual(h.ns.char.activeGuide, OTHER)
        self.assertFalse(h.ns.char.recovery.active)
        self.assertEqual(h.ns.char.recovery.bookmark.cursor, 2)

    def test_paused_stale_recovery_does_not_replace_selected_route_or_newer_progress(self):
        h = RequirementHost(cursor=3, active=OTHER, recovery=self.recovery(100))
        other = primitive_copy(h.ns.char.progress[OTHER])
        h.migrate()
        self.assertEqual(h.ns.char.activeGuide, OTHER)
        self.assertEqual(primitive_copy(h.ns.char.progress[OTHER]), other)
        self.assertEqual(h.progress.cursor, 3)
        self.assertIsNone(h.ns.char.recovery)
        self.assertTrue(h.ns.char.guideMigrationBackups[ROUTE + ":2"].recovery.active)


class PublishedMigrationContractTests(unittest.TestCase):
    def test_unlocked_holy_diver_does_not_reopen_inactive_historical_parents(self):
        dark = "forever/alliance/03-darkshore"
        for child in ({"onQuest": True, "complete": False}, {"delivered": True}):
            with self.subTest(child=child):
                saved = {"seen": True, "auto": False, "activeGuide": dark, "progress": {dark: {
                    "cursor": 26, "routeRevision": 2, "review": True, "placed": True,
                    "skipped": {"7:7": True, "11:12": True}, "confirmed": {"1:1": True}}}}
                h = MigrationHost(saved, {87760: child})
                expected = h.call("GetGuideCursorForRevision", dark, 26, 2)
                h.initialize()
                state = h.ns.char.progress[dark]
                self.assertEqual(state.cursor, expected)
                self.assertTrue(state.skipped["7:7"])
                self.assertTrue(state.skipped["11:12"])
                self.assertTrue(state.confirmed["1:1"])
                self.assertIsNone(state.requirementsRepair)
                for parent in (4722, 4723, 4725, 4727, 4728, 4730, 4731, 4732, 4733):
                    self.assertFalse(h.call("IsQuestDelivered", parent))
                    self.assertIsNone(h.ns.turnedIn[parent])

    def test_active_holy_diver_parent_is_still_repaired_from_its_real_journal_state(self):
        dark = "forever/alliance/03-darkshore"
        saved = {"seen": True, "auto": False, "activeGuide": dark, "progress": {dark: {
            "cursor": 26, "routeRevision": 2, "review": True, "placed": True,
            "skipped": {"7:7": True, "11:12": True}, "confirmed": {"1:1": True}}}}
        h = MigrationHost(saved, {87760: {"onQuest": True, "complete": False},
                                 4722: {"onQuest": True, "complete": False}})
        h.initialize()
        state = h.ns.char.progress[dark]
        self.assertEqual(state.cursor, 11)
        self.assertIsNone(state.skipped["11:12"])
        self.assertTrue(h.call("IsQuestActive", 4722))
        self.assertFalse(h.call("IsQuestDelivered", 4722))
        self.assertTrue(h.call("IsQuestActive", 87760))
        self.assertTrue(state.confirmed["1:1"])

    def test_unlocked_child_does_not_choose_an_unproven_or_parent(self):
        h = RequirementHost(cursor=3)
        guide = h.ns.guides[ROUTE]
        guide.progressMigrations[1].affectedQuestIDs = h.table([100, 200])
        guide.steps[2].goals[1].pre = h.table([200, 300])
        h.quest(100, onQuest=True, complete=False)
        h.migrate()
        self.assertEqual(h.progress.cursor, 1)
        self.assertFalse(h.call("IsQuestDelivered", 200))
        self.assertIsNone(h.progress.confirmed["1:1"])

    def test_paused_legacy_mine_recovery_preserves_the_selected_other_guide(self):
        other = "forever/alliance/human/01-elwynn-forest"
        saved = {"seen": True, "auto": False, "activeGuide": other, "progress": {
            WEST: {"cursor": 6, "review": True}, other: {"cursor": 4, "review": True}},
            "recovery": {"version": 1, "active": True, "requestedQuestID": 92745,
                         "requiredQuestIDs": [92745], "bookmark": {"guideID": WEST, "cursor": 4, "review": True}}}
        h = MigrationHost(saved)
        h.initialize()
        self.assertEqual(h.ns.char.activeGuide, other)
        self.assertEqual(h.ns.char.progress[other].cursor, 4)
        self.assertEqual(h.progress.cursor, 8)
        self.assertIsNone(h.ns.char.recovery)
        self.assertTrue(h.ns.char.guideMigrationBackups[WEST + ":2"].recovery.active)

    def test_legacy_deferred_repair_keeps_a_newly_completed_westfall_route_closed(self):
        saved = {"seen": True, "auto": False, "activeGuide": WEST, "progress": {WEST: {
            "cursor": 6, "review": True, "skipped": {"6:1": True}}}}
        h = MigrationHost(saved)
        api = h.globals.C_QuestLog.IsOnQuest
        h.globals.C_QuestLog.IsOnQuest = h.lua.eval("function() return nil end")
        h.initialize()
        self.assertTrue(h.progress.routeRepairPending)
        h.progress.cursor = len(h.ns.guides[WEST].steps) + 1
        complete = h.progress.cursor
        h.globals.C_QuestLog.IsOnQuest = api
        h.update_log()
        self.assertEqual(h.progress.cursor, complete)
        self.assertIsNone(h.progress.routeRepairPending)
        self.assertIsNone(h.progress.requirementsRepair)
        self.assertTrue(h.progress.skipped["8:1"])

    def test_every_published_goal_maps_once_and_keeps_saved_marks(self):
        revisions = json.loads((ADDON / "Source" / "guide_revisions.json").read_text(encoding="utf-8"))["revisions"]
        h = QuestEngineHost(catalog=True)
        h.load((ADDON / "GuideMigrations.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        for revision in revisions:
            if "previousGoalCounts" not in revision:
                continue
            with self.subTest(revision=revision["id"]):
                guide = h.ns.guides[revision["guideID"]]
                migration = next(m for m in guide.progressMigrations.values() if m["from"] == revision["previousRevision"])
                old = {f"{si}:{gi}": f"{si}:{gi}" for si, count in enumerate(revision["previousGoalCounts"], 1)
                       for gi in range(1, count + 1)}
                chain, current = [], revision["previousRevision"]
                while current < guide.routeRevision:
                    update = next(m for m in guide.progressMigrations.values() if m["from"] == current)
                    chain.append(update)
                    current = update.to
                expected, added = dict(old), set()
                for update in chain:
                    expected = {update.goalMap[key] or key: value for key, value in expected.items()}
                    added = {update.goalMap[key] or key for key in added}
                    added.update((update.addedGoalKeys or h.table([])).values())
                actual_keys = {f"{si}:{gi}" for si, step in guide.steps.items() for gi in step.goals.keys()}
                self.assertEqual(len(expected), len(old), "Distinct old actions must never collide")
                self.assertFalse(set(expected) & added, "New actions cannot inherit an old confirmation")
                self.assertEqual(set(expected) | added, actual_keys)
                h.ns.char = h.table({"activeGuide": "unselected", "progress": {guide.id: {
                    "routeRevision": revision["previousRevision"], "cursor": len(revision["previousGoalCounts"]) + 1,
                    "confirmed": old, "skipped": dict(old)}}})
                h.call("MigrateGuideProgress")
                state = h.ns.char.progress[guide.id]
                self.assertEqual(state.routeRevision, guide.routeRevision)
                self.assertEqual(primitive_copy(state.confirmed), expected)
                self.assertEqual(primitive_copy(state.skipped), expected)
                self.assertEqual(state.cursor, len(guide.steps) + 1)
                for old_step in migration.stepMap.keys():
                    new_step = old_step
                    for update in chain:
                        new_step = update.stepMap[new_step] or new_step
                    self.assertEqual(h.call("GetGuideCursorForRevision", guide.id, old_step, migration["from"]), new_step)

    def test_westfall_two_migrations_keep_earlier_live_repair_and_both_backups(self):
        saved = {"seen": True, "auto": False, "activeGuide": WEST, "progress": {WEST: {
            "cursor": 6, "routeRevision": 1, "review": True,
            "confirmed": {"2:5": True, "5:5": True}, "skipped": {"11:6": True}}}}
        h = MigrationHost(saved, {92742: {"delivered": True},
                                 92744: {"onQuest": True, "complete": False},
                                 92910: {"onQuest": True, "complete": True}})
        h.initialize()
        self.assertEqual(h.progress.routeRevision, 3)
        self.assertEqual(h.progress.cursor, 6)  # Coast first; engineering return is later.
        self.assertTrue(h.progress.confirmed["12:6"])
        self.assertTrue(h.progress.confirmed["12:7"])
        self.assertIsNotNone(h.ns.char.guideMigrationBackups[WEST + ":2"])
        self.assertIsNotNone(h.ns.char.guideMigrationBackups[WEST + ":3"])
        self.assertEqual(h.call("GetGuideCursorForRevision", WEST, 22, 1), 23)
        self.assertEqual(h.call("GetGuideCursorForRevision", WEST, 23, 2), 23)


if __name__ == "__main__":
    unittest.main()
