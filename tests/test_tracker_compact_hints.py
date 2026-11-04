"""Restore the 0.6.2 row density while retaining complete optional details."""
import re
import json
from pathlib import Path
import unittest

from test_access_navigation import AccessHost, DWARF
from test_duo_journey import primitive_copy


GENERIC = ("Abre", "Acceso o lugar:", "Zona:", "En este paso:", "referencia del objetivo")
SPECIAL_WORDS = {
    98326: ("Sack of Fish",), 1440: ("Dalinda",), 99134: ("5", "Deathguards"),
    1046: ("calavera", "Dartol"), 5149: ("Combina", "muñeca"), 5051: ("mitades",),
    3786: ("10", "Mañagrana"), 3804: ("Mañagrana",),
    91899: ("248765",), 91904: ("248770",), 6022: ("7", "10", "almirez"),
    94568: ("Habla", "Talaanis"), 92640: ("Valennia", "Ayessa", "Elaadrin"),
    6001: ("Garraluna", "espíritu"), 6002: ("Garraluna", "espíritu"),
    96873: ("Desencanta", "3", "Encantamiento"), 92474: ("Walk on Air",),
}


def result_items(value):
    return value[0] if isinstance(value, tuple) else value


def plain(value):
    return re.sub(r"\|c[0-9a-fA-F]{8}|\|r", "", value or "")


class TrackerCompactHintTests(unittest.TestCase):
    def screenshot(self):
        h = AccessHost(DWARF, 21, 1, x=.465, y=.538)
        h.s.quests[384] = h.h.table({"onQuest": True, "complete": False, "objectives": [
            {"text": "Costilla de jabalí: 4/6", "numFulfilled": 4, "numRequired": 6, "finished": False},
            {"text": "Malta rapsódica: 1/1", "numFulfilled": 1, "numRequired": 1, "finished": True},
        ]})
        h.s.quests[317] = h.h.table({"onQuest": True, "complete": False})
        return h

    def items(self, h, step=None):
        return result_items(h.ns.GetStepGoalItems(h.ns, step or h.step))

    def assert_no_generic(self, value):
        for phrase in GENERIC:
            self.assertNotIn(phrase.casefold(), plain(value).casefold())

    def test_reported_step21_restores_exact_live_counter_without_instruction_paragraph(self):
        h = self.screenshot()
        before = h.progress()
        rows = self.items(h)
        self.assertEqual(rows[1].subtitle, "Costilla de jabalí: 4/6")
        self.assertNotIn("Malta rapsódica: 1/1", rows[1].subtitle)
        self.assert_no_generic(rows[1].subtitle)
        self.assertIsInstance(rows[1].details, str)
        self.assertIn("registro", rows[1].details)
        self.assertIn(h.step.note, rows[1].details)
        self.assertEqual(h.progress(), before)

    def test_missing_live_data_for_the_other_quest_does_not_expand_a_generic_fallback(self):
        h = self.screenshot()
        rows = self.items(h)
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(rows[2].goal.quest, 317)
        self.assert_no_generic(rows[2].subtitle)
        self.assertLessEqual(len((rows[2].subtitle or "").splitlines()), 2)
        self.assertIsInstance(rows[2].details, str)

    def test_turnin_npc_remains_visible_once_despite_a_full_generated_instruction(self):
        h = AccessHost(DWARF, 22, 1, x=.465, y=.538)
        h.s.quests[384].complete = True
        row = self.items(h)[1]
        self.assertIn("Ragnar Cebatruenos", row.subtitle)
        self.assertEqual(row.subtitle.count("Ragnar Cebatruenos"), 1)
        self.assertLessEqual(len(row.subtitle.splitlines()), 2)
        self.assert_no_generic(row.subtitle)
        self.assertIn("entrega", row.details.casefold())

    def test_upcoming_step22_shows_ragnar_and_step_number_without_full_instruction(self):
        h = self.screenshot()
        before = h.progress()
        rows = h.ns.GetTrackerUpcomingItems(h.ns, h.guide, 21, 3)
        self.assertTrue(rows[1].preview)
        self.assertIn("22", rows[1].subtitle)
        self.assertIn("Ragnar Cebatruenos", rows[1].subtitle)
        self.assertEqual(rows[1].subtitle.count("Ragnar Cebatruenos"), 1)
        self.assert_no_generic(rows[1].subtitle)
        self.assertLessEqual(len(rows[1].subtitle), 120)
        self.assertEqual(h.progress(), before)

    def test_all17_sourced_special_hints_are_a_single_short_sentence(self):
        h = self.screenshot()
        self.assertIsNotNone(h.ns.GetGoalHint)
        for quest, words in SPECIAL_WORDS.items():
            with self.subTest(quest=quest):
                goal = h.h.table({"t": "complete", "quest": quest,
                    "instruction": "Abre la misión en el registro.\nZona: ejemplo.\nAcceso o lugar: referencia."})
                hint = h.ns.GetGoalHint(h.ns, goal)
                self.assertIsInstance(hint, str)
                self.assertNotIn("\n", hint)
                self.assertLessEqual(len(hint.encode("utf-8")), 160)
                self.assert_no_generic(hint)
                for word in words:
                    self.assertIn(word.casefold(), hint.casefold())

    def test_campfire_instruction_remains_essential_but_not_the_entire_step_paragraph(self):
        h = AccessHost(DWARF, 19, 3, x=.465, y=.538)
        row = next(row for _, row in self.items(h).items() if row.goal.quest == 96608 and row.goal.t == "complete")
        self.assertIn("/sit", row.subtitle)
        self.assertTrue("hoguera" in row.subtitle.casefold() or "fogata" in row.subtitle.casefold())
        self.assertNotIn("Gremlock", row.subtitle)
        self.assert_no_generic(row.subtitle)
        self.assertIn(h.step.note, row.details)

    def test_only_the_six_sourced_great_outdoors_quests_get_a_sitting_hint(self):
        h = self.screenshot()
        for quest in (96606, 96608, 95998, 96101, 96604, 96607):
            with self.subTest(quest=quest):
                hint = h.ns.GetGoalHint(h.ns, h.h.table({"t": "complete", "quest": quest}))
                self.assertIn("/sit", hint)
                self.assertTrue("hoguera" in hint.casefold() or "fogata" in hint.casefold())
                self.assertLessEqual(len(hint.encode("utf-8")), 160)

    def test_cooking_quests_in_a_campfire_step_do_not_inherit_the_sitting_instruction(self):
        h = self.screenshot()
        document = json.loads((Path(__file__).resolve().parents[1] / "RutaXP/Source/leveling.json").read_text(encoding="utf-8"))
        found = set()
        for guide in document["guides"]:
            for step in guide["steps"]:
                for goal in step["goals"]:
                    if goal.get("quest") in (96629, 96634, 96646) and goal["t"] in ("kill", "complete"):
                        hint = h.ns.GetGoalHint(h.ns, h.h.table(goal))
                        self.assertNotIn("/sit", hint or "")
                        found.add(goal["quest"])
        self.assertEqual(found, {96629, 96634, 96646})

    def test_live_objective_text_and_counters_are_never_hard_truncated_like_authored_notes(self):
        h = self.screenshot()
        live = "Objetivo de misión con nombre extremadamente largo y caracteres acentuados: " * 3 + "4/6"
        h.s.quests[384].objectives[1].text = live
        self.assertEqual(self.items(h)[1].subtitle, live)

    def test_long_authored_warning_is_shortened_at_a_utf8_word_boundary_only_in_row(self):
        h = self.screenshot()
        long_note = "Peligro: evita los élites y conserva la llave para salir de la cueva " * 6 + "ADVERTENCIA FINAL."
        goal = h.h.table({"t": "kill", "quest": 900991, "target": "Criatura", "note": long_note,
                          "instruction": long_note})
        h.s.quests[900991] = h.h.table({"onQuest": True, "complete": False})
        step = h.h.table({"title": "Warning", "goals": [goal]})
        row = self.items(h, step)[1]
        hint = h.ns.GetGoalHint(h.ns, goal)
        self.assertLessEqual(len(hint.encode("utf-8")), 163)  # Includes an optional UTF-8 ellipsis.
        self.assertIn("Peligro", hint)
        last_word = hint.rstrip("… .").split()[-1]
        self.assertIn(last_word, long_note.split())
        self.assertIn("ADVERTENCIA FINAL", row.details)
        self.assertEqual(goal.note, long_note)

    def test_conflicting_crate_context_is_not_restored_in_rows_or_full_details(self):
        h = self.screenshot()
        for quest in (91899, 91904):
            with self.subTest(quest=quest):
                h.s.quests[quest] = h.h.table({"onQuest": True, "complete": False})
                goal = {"t": "complete", "quest": quest, "instructionReplacesContext": True,
                        "instruction": "Verifica la caja sellada; las fuentes discrepan sobre su obtención."}
                step = h.h.table({"title": "Crates", "note": "Open cada caja que le da.", "goals": [goal]})
                row = self.items(h, step)[1]
                self.assertNotIn("Open cada caja", row.subtitle or "")
                self.assertNotIn("Open cada caja", row.details or "")
                self.assertEqual(step.note, "Open cada caja que le da.")

    def test_real_tracker_tooltip_receives_full_details_while_the_row_stays_compact(self):
        h = self.screenshot()
        h.h.lua.execute('''
            GameTooltip={lines={}}
            function GameTooltip:SetOwner() self.lines={} end
            function GameTooltip:SetText(text) self.lines[#self.lines+1]=text end
            function GameTooltip:AddLine(text) self.lines[#self.lines+1]=text end
            function GameTooltip:Show() self.shown=true end
            function GameTooltip:Hide() self.shown=false end
        ''')
        before = primitive_copy(h.ns.char.progress)
        h.ns.RefreshUI(h.ns)
        row = h.ns.trackerRows[1]
        self.assertEqual(row.sub.text, "Costilla de jabalí: 4/6")
        row.scripts.OnEnter(row)
        tooltip = "\n".join(h.h.g.GameTooltip.lines.values())
        self.assertIn("registro", tooltip)
        self.assertIn(h.step.note, tooltip)
        self.assertEqual(primitive_copy(h.ns.char.progress), before)


if __name__ == "__main__":
    unittest.main()
