"""Skipped Westfall objectives remain visibly pending and can be restored."""

import unittest

from test_access_navigation import AccessHost
from test_duo_journey import primitive_copy


WESTFALL = "forever/alliance/02-westfall"
TEXTURE_AND_TOOLTIP_STUBS = """
    local function capture(row)
        function row.icon:SetTexture(texture) self.texture = texture end
        function row.icon:SetVertexColor(...) self.color = {...} end
    end
    for _, row in ipairs(ACCESS_NS.trackerRows) do capture(row) end
    local create = ACCESS_NS.CreateTrackerRow
    function ACCESS_NS:CreateTrackerRow(index)
        create(self, index)
        capture(self.trackerRows[index])
    end
    GameTooltip = {lines = {}}
    function GameTooltip:SetOwner() self.lines = {} end
    function GameTooltip:SetText(text) self.lines[#self.lines + 1] = text end
    function GameTooltip:AddLine(text) self.lines[#self.lines + 1] = text end
    function GameTooltip:Show() end
    function GameTooltip:Hide() end
"""


class TrackerOmittedTests(unittest.TestCase):
    def farm(self):
        host = AccessHost(WESTFALL, 5, 1, x=.50, y=.27)
        host.s.quests[92742] = host.h.table({"onQuest": True, "complete": False, "objectives": [
            {"text": "Primera caja: 1/1", "numFulfilled": 1, "numRequired": 1, "finished": True},
            {"text": "Segunda caja: 0/1", "numFulfilled": 0, "numRequired": 1, "finished": False},
        ]})
        host.s.quests[9] = host.h.table({"onQuest": True, "complete": False, "objectives": [
            {"text": "Zahorí cosechador: 0/20", "numFulfilled": 0, "numRequired": 20, "finished": False},
        ]})
        host.ns.RefreshUI(host.ns)
        host.h.lua.execute(TEXTURE_AND_TOOLTIP_STUBS)
        return host

    def row(self, host, goal):
        return next(row for row in host.ns.trackerRows.values()
                    if row.shown and not row.preview and row.goalIndex == goal)

    def test_skipping_then_going_back_restores_molsen_as_pending_with_real_counts(self):
        host = self.farm()
        host.h.g.Click(host.ns.trackerSkip)
        host.h.g.Click(host.ns.trackerPrevious)
        state = host.ns.char.progress[WESTFALL]
        self.assertEqual(state.cursor, 5)
        self.assertIsNone(state.review)
        before = host.progress()
        for goal, counter in ((1, "Segunda caja: 0/1"), (2, "Zahorí cosechador: 0/20")):
            with self.subTest(goal=goal):
                row = self.row(host, goal)
                self.assertNotIn("Omitido", row.title.text)
                self.assertIn(counter, row.sub.text)
                self.assertFalse(row.icon.texture.endswith("\\check"))
                self.assertNotIn("|cff6be09e", row.title.text)
                self.assertIsNone(state.skipped[f"5:{goal}"])
                row.scripts.OnEnter(row)
                tooltip = "\n".join(host.h.g.GameTooltip.lines.values())
                self.assertNotIn("Omitido", tooltip)
        self.assertEqual(host.progress(), before)

    def test_legacy_confirmation_can_be_undone_by_right_clicking_the_visible_row(self):
        host = self.farm()
        state = host.ns.char.progress[WESTFALL]
        state.confirmed["5:1"] = True
        state.confirmed["unrelated-mark"] = True
        host.ns.RefreshUI(host.ns)
        row = self.row(host, 1)
        self.assertIn("Omitido", row.title.text)
        row.scripts.OnClick(row, "RightButton")
        row = self.row(host, 1)
        self.assertNotIn("Omitido", row.title.text)
        self.assertEqual(row.sub.text.splitlines()[0], "Segunda caja: 0/1")
        self.assertIsNone(state.confirmed["5:1"])
        self.assertTrue(state.confirmed["unrelated-mark"])
        self.assertEqual(state.cursor, 5)

    def test_delivered_goal_keeps_the_existing_green_check_style(self):
        host = AccessHost(WESTFALL, 8, 1)
        host.h.lua.execute(TEXTURE_AND_TOOLTIP_STUBS)
        host.s.quests[92745].delivered = True
        host.s.quests[92745].onQuest = False
        before = primitive_copy(host.ns.char.progress)
        host.ns.RefreshUI(host.ns)
        row = self.row(host, 1)
        self.assertTrue(row.icon.texture.endswith("\\check"))
        self.assertEqual(tuple(row.icon.color.values()), (.42, .88, .62))
        self.assertIn("|cff6be09e", row.title.text)
        self.assertNotIn("Omitido", row.title.text)
        self.assertEqual(primitive_copy(host.ns.char.progress), before)

    def live_molsen(self):
        host = self.farm()
        for quest, counters in ((9, ["Zahorí cosechador: 0/20"]),
                                (92742, ["Primera caja: 0/1", "Segunda caja: 0/1"]),
                                (92909, ["Caja antigua: 0/1", "Paquete antiguo: 0/1"])):
            host.s.quests[quest] = host.h.table({"onQuest": False, "delivered": True, "complete": False,
                "objectives": [{"text": text, "numFulfilled": 0, "numRequired": 20 if quest == 9 else 1,
                                "finished": False} for text in counters]})
        host.s.quests[38] = host.h.table({"onQuest": True, "complete": False, "objectives": [
            {"text": "Carne fibrosa: 0/3", "numFulfilled": 0, "numRequired": 3, "finished": False},
            {"text": "Ojo de múrloc: 0/3", "numFulfilled": 0, "numRequired": 3, "finished": False},
            {"text": "Hígado de Dentosangre: 0/3", "numFulfilled": 0, "numRequired": 3, "finished": False},
            {"text": "Okra: 3/3", "numFulfilled": 3, "numRequired": 3, "finished": True},
        ]})
        host.s.quests[92911] = host.h.table({"onQuest": True, "complete": False, "objectives": [
            {"text": "Suministros pendientes: 0/1", "numFulfilled": 0, "numRequired": 1, "finished": False},
        ]})
        state = host.ns.char.progress[WESTFALL]
        state.review = True
        for index in range(1, len(host.step.goals) + 1):
            state.skipped[f"5:{index}"] = True
        return host

    def test_live_molsen_evidence_shows_only_pending_omissions_and_excludes_delivered_zeroes(self):
        host = self.live_molsen()
        before = host.progress()
        host.ns.RefreshUI(host.ns)
        rows = [row for row in host.ns.trackerRows.values() if row.shown and not row.preview]
        self.assertEqual({row.goalIndex for row in rows}, {5, 7, 8, 9, 10, 11})
        for row in rows:
            self.assertIn("Omitido · ", row.title.text)
            self.assertFalse(row.icon.texture.endswith("\\check"))
            self.assertEqual(tuple(row.icon.color.values()), (.64, .72, .82))
        all_text = "\n".join(row.sub.text for row in rows)
        self.assertIn("Suministros pendientes: 0/1", all_text)
        self.assertIn("Hígado de Dentosangre: 0/3", all_text)
        for historical in ("Zahorí cosechador: 0/20", "Caja antigua: 0/1", "Segunda caja: 0/1"):
            self.assertNotIn(historical, all_text)
        self.assertEqual(host.progress(), before)

    def test_real_completion_replaces_old_molsen_counters_when_no_pending_rows_remain(self):
        host = self.live_molsen()
        state = host.ns.char.progress[WESTFALL]
        for goal in host.step.goals.values():
            if goal.quest and goal.quest != 38:
                entry = host.s.quests[goal.quest] or host.h.table({})
                entry.onQuest, entry.delivered = False, True
                host.s.quests[goal.quest] = entry
        host.s.quests[38].complete = True
        state.skipped["5:7"] = None
        state.confirmed["5:7"] = True  # The unbound inventory errand is a manual service.
        before = host.progress()
        host.ns.RefreshUI(host.ns)
        rows = [row for row in host.ns.trackerRows.values() if row.shown and not row.preview]
        self.assertEqual(len(rows), len(host.step.goals))
        for row in rows:
            self.assertTrue(row.icon.texture.endswith("\\check"))
            self.assertIn("|cff6be09e", row.title.text)
            self.assertNotIn("Omitido", row.title.text)
            self.assertNotIn("0/", row.sub.text)
        self.assertEqual(self.row(host, 2).sub.text, "Misión entregada")
        self.assertEqual(self.row(host, 6).sub.text, "Objetivos completados")
        self.assertEqual(host.progress(), before)


if __name__ == "__main__":
    unittest.main()
