"""Journal plans explain future visits without moving the current objective."""

import unittest

import test_quest_engine as engine
import test_tracker_preview as source_preview
from test_duo_journey import primitive_copy
from test_tracker_resize import ResizableTrackerHost


DUN_MOROGH = "forever/alliance/dwarf-gnome/01-dun-morogh"


class TrackerQuestPlanTests(unittest.TestCase):
    def host(self, catalog=True):
        h = engine.QuestEngineHost(catalog=catalog)
        h.load((engine.ADDON / "TrackerPreview.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.state.classToken, h.state.raceToken = "WARRIOR", "Dwarf"
        h.state.level = 8
        h.initialize()
        h.ns.char.auto = False
        return h

    def place(self, h, guide_id, cursor):
        h.ns.char.activeGuide = guide_id
        h.ns.char.progress[guide_id] = h.table({
            "cursor": cursor, "placed": True,
            "confirmed": {"manual": True}, "skipped": {"keep": True},
        })

    def guide(self, h, guide_id, steps, **fields):
        for index, step in enumerate(steps, 1):
            step.setdefault("title", f"Visita {index}")
        return h.guide(guide_id, steps=steps, **fields)

    def plan(self, h, guide_id=DUN_MOROGH, cursor=28, limit=12):
        return list(h.call("GetTrackerPlannedUpcomingItems", h.ns.guides[guide_id], cursor, limit).values())

    def wood(self, h):
        h.quest(99159, title="En busca de calor", onQuest=True, objectives=[{
            "text": "Leña casi seca: 10/14", "numFulfilled": 10,
            "numRequired": 14, "finished": False,
        }])

    def test_real_dun_morogh_lists_firewood_38_39_and_ready_ammunition_delivery_29(self):
        h = self.host()
        self.place(h, DUN_MOROGH, 28)
        self.wood(h)
        h.quest(5541, title="La munición de Estruendo", onQuest=True, complete=True)
        before = primitive_copy(h.ns.char)
        guide_before = primitive_copy(h.ns.guides[DUN_MOROGH])
        rows = self.plan(h)
        wood = [row for row in rows if row.questID == 99159]
        ammo = [row for row in rows if row.questID == 5541]
        self.assertEqual(len(wood), 1)
        self.assertEqual(wood[0].title, "En busca de calor")
        self.assertEqual(wood[0].subtitle, "En tu diario · Hacer: paso 38 · Entregar: 39 · 10/14")
        self.assertEqual((wood[0].workStep, wood[0].turninStep), (38, 39))
        self.assertEqual(len(ammo), 1)
        self.assertEqual(ammo[0].subtitle, "En tu diario · Entregar: 29")
        self.assertEqual(ammo[0].action, "turnin")
        self.assertIsNone(ammo[0].workStep)
        for row in wood + ammo:
            self.assertTrue(row.questPlan)
            self.assertTrue(row.preview)
            self.assertIsNone(row.index)
            self.assertFalse(row.isCurrent)
            self.assertIn("no cambia el paso, la flecha", row.details)
        self.assertLessEqual(len(rows), 12)
        self.assertEqual(primitive_copy(h.ns.char), before)
        self.assertEqual(primitive_copy(h.ns.guides[DUN_MOROGH]), guide_before)

    def test_active_step_keeps_live_10_of_14_and_the_short_firewood_instruction(self):
        h = self.host()
        self.place(h, DUN_MOROGH, 38)
        self.wood(h)
        step = h.ns.guides[DUN_MOROGH].steps[38]
        hint = h.call("GetGoalHint", step.goals[1])
        self.assertIn("14", hint)
        self.assertIn("troncos", hint.lower())
        before = primitive_copy(h.ns.char.progress)
        result = h.call("GetStepGoalItems", step)
        rows = list((result[0] if isinstance(result, tuple) else result).values())
        self.assertEqual(len(rows), 1)
        self.assertIn("10/14", rows[0].subtitle)
        self.assertIn(hint, rows[0].subtitle)
        self.assertFalse(any(row.questPlan and row.questID == 99159 for row in self.plan(h, cursor=38)))
        self.assertEqual(primitive_copy(h.ns.char.progress), before)

    def test_profiles_optional_choices_manual_skips_and_closed_branches_are_respected(self):
        h = self.host(catalog=False)
        self.guide(h, "plan", faction="Alliance", races=["Dwarf"], steps=[
            {"goals": [{"t": "complete", "quest": 101}]},
            {"only": {"classes": ["MAGE"]}, "goals": [{"t": "complete", "quest": 102}]},
            {"goals": [{"t": "complete", "quest": 103, "only": {"races": ["NightElf"]}}]},
            {"goals": [{"t": "complete", "quest": 104, "optional": True}]},
            {"goals": [{"t": "complete", "quest": 105, "optional": True}, {"t": "turnin", "quest": 105}]},
            {"goals": [{"t": "accept", "quest": 106, "closedBy": [107]},
                       {"t": "complete", "quest": 106}, {"t": "turnin", "quest": 106}]},
            {"goals": [{"t": "complete", "quest": 108}, {"t": "turnin", "quest": 108}]},
            {"goals": [{"t": "complete", "quest": 109, "oi": 1}, {"t": "turnin", "quest": 109}]},
            {"goals": [{"t": "turnin", "quest": 101}]},
        ])
        self.place(h, "plan", 1)
        for qid in (101, 102, 103, 105, 107, 108):
            h.quest(qid, onQuest=True)
        h.quest(109, onQuest=True, objectives=[{"finished": True}])
        state = h.ns.char.progress.plan
        state.skipped["7:1"], state.confirmed["7:2"] = True, True
        before = primitive_copy(h.ns.char)
        rows = self.plan(h, "plan", 1)
        ids = [row.questID for row in rows]
        self.assertTrue(set(ids).isdisjoint({102, 103, 104, 106, 108}))
        plans = {row.questID: row for row in rows if row.questPlan}
        self.assertEqual(set(plans), {105, 109})
        self.assertNotIn(101, plans)  # Its objective is already in the current step.
        self.assertEqual(plans[109].subtitle, "En tu diario · Entregar: 8")
        self.assertEqual(primitive_copy(h.ns.char), before)

    def test_filler_removes_delivered_accepted_and_finished_objective_rows_before_limit(self):
        h = self.host(catalog=False)
        self.guide(h, "filtered", steps=[
            {"goals": [{"t": "note", "text": "Current"}]},
            {"goals": [{"t": "accept", "quest": 201}, {"t": "complete", "quest": 201},
                       {"t": "turnin", "quest": 201}]},
            {"goals": [{"t": "accept", "quest": 202}, {"t": "complete", "quest": 202, "oi": 1}]},
            {"goals": [{"t": "accept", "quest": 203}, {"t": "complete", "quest": 203}]},
            {"goals": [{"t": "note", "text": "Useful future information"}]},
        ])
        self.place(h, "filtered", 1)
        h.quest(201, delivered=True)
        h.quest(202, onQuest=True, objectives=[{"finished": True}])
        rows = self.plan(h, "filtered", 1, 3)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row.questID not in (201, 202) for row in rows))
        self.assertEqual([row.action for row in rows], ["accept", "complete", "note"])

    def test_real_active_return_quest_overrides_a_closed_branch_but_later_accepts_do_not(self):
        h = self.host()
        self.place(h, DUN_MOROGH, 54)
        h.quest(415, onQuest=True, complete=True, title="Vuelta a casa")
        h.quest(413, delivered=True)
        rows = [row for row in self.plan(h, cursor=54) if row.questID == 415]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].questPlan)
        self.assertEqual(rows[0].subtitle, "En tu diario · Entregar: 56")

        self.guide(h, "later-branch", steps=[
            {"goals": [{"t": "accept", "quest": 401}]},
            {"goals": [{"t": "turnin", "quest": 401}]},
            {"goals": [{"t": "accept", "quest": 401, "closedBy": [402]}]},
        ])
        self.place(h, "later-branch", 1)
        h.quest(402, onQuest=True)
        rows = self.plan(h, "later-branch", 1)
        self.assertEqual([(row.questID, row.stepIndex, row.action) for row in rows], [(401, 2, "turnin")])

    def test_limits_six_journal_quests_and_twelve_rows_even_with_unknown_counts(self):
        h = self.host(catalog=False)
        steps = [{"goals": [{"t": "note", "text": "Current"}]}]
        for qid in range(301, 321):
            steps.append({"goals": [{"t": "complete", "quest": qid}, {"t": "turnin", "quest": qid}]})
            h.quest(qid, onQuest=True, objectives=[{"finished": False}])
        self.guide(h, "bounded", steps=steps)
        self.place(h, "bounded", 1)
        rows = self.plan(h, "bounded", 1, 100)
        plans = [row for row in rows if row.questPlan]
        self.assertEqual((len(rows), len(plans)), (12, 6))
        for row in plans:
            self.assertNotIn("0/0", row.subtitle)
            self.assertEqual(sum(other.questID == row.questID for other in rows), 1)
        self.assertEqual(len(self.plan(h, "bounded", 1, 2)), 2)
        self.assertEqual(self.plan(h, "bounded", 1, 0), [])
        self.assertEqual(self.plan(h, "bounded", -1), [])

    def test_duo_helper_retains_source_preview_without_inspecting_our_quest_history(self):
        fixture = source_preview.TrackerPreviewTests()
        fixture.setUp()
        fixture.check('''
            TEST.helper=true
            function C_QuestLog.IsOnQuest() error("Own diary must not filter partner rows") end
            function C_QuestLog.IsComplete() error("Own completion must not filter partner rows") end
            function C_QuestLog.GetQuestObjectives() error("Own objectives must not filter partner rows") end
            local before=Fingerprint(NS.char)
            local source=Fingerprint(NS:GetTrackerUpcomingItems(GUIDE,1))
            local planned=Fingerprint(NS:GetTrackerPlannedUpcomingItems(GUIDE,1))
            assert(source==planned)
            assert(Fingerprint(NS.char)==before)
        ''')

    def test_compact_tracker_displays_the_plan_and_clicks_cannot_change_arrow_or_progress(self):
        host = ResizableTrackerHost()
        ns, s = host.ns, host.s
        s.classToken, s.raceToken, s.level = "WARRIOR", "Dwarf", 8
        ns.char.activeGuide = DUN_MOROGH
        ns.char.progress[DUN_MOROGH] = host.h.table({
            "cursor": 28, "placed": True, "confirmed": {"manual": True}, "skipped": {"keep": True},
        })
        s.quests[99159] = host.h.table({"title": "En busca de calor", "onQuest": True, "objectives": [
            {"text": "Leña casi seca: 10/14", "numFulfilled": 10, "numRequired": 14, "finished": False},
        ]})
        s.quests[5541] = host.h.table({"title": "La munición de Estruendo", "onQuest": True, "complete": True})
        before = primitive_copy(ns.char.progress)
        arrow_before = (s.waypointCalls, s.superTrackCalls, ns.char.arrow)
        self.assertIsNone(ns.char.trackerSize)
        host.refresh()
        rows = [row for row in ns.trackerRows.values() if row.shown and row.questPlan]
        self.assertEqual(len(rows), 2)
        wood = next(row for row in rows if row.goalTitle == "En busca de calor")
        self.assertIn("Hacer: paso 38 · Entregar: 39 · 10/14", wood.goalSub)
        self.assertIn("EN TU DIARIO", ns.trackerUpcomingLabel.text)
        self.assertIn("no cambia el paso, la flecha", wood.goalDetails)
        for row in rows:
            self.assertTrue(row.preview)
            self.assertIsNone(row.goalIndex)
            for button in ("LeftButton", "RightButton"):
                row.scripts.OnClick(row, button)
        self.assertEqual(primitive_copy(ns.char.progress), before)
        self.assertEqual((s.waypointCalls, s.superTrackCalls, ns.char.arrow), arrow_before)


if __name__ == "__main__":
    unittest.main()
