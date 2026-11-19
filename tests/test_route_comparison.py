"""Check that every authored action is visible and external comparisons remain traceable."""
from collections import Counter
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import capture_route_comparison as capture
import review_all_routes as review


class CatalogComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = review.make_report()

    def test_every_chapter_quest_and_action_is_in_the_report_exactly_once(self):
        guides = review.load(review.SOURCE / "leveling.json")["guides"]
        self.assertEqual(len(guides), len(self.report["chapters"]))
        for guide, chapter in zip(guides, self.report["chapters"], strict=True):
            self.assertEqual(guide["id"], chapter["id"])
            self.assertTrue(chapter["refs"])
            expected, actual = {}, []
            for s, step in enumerate(guide["steps"], 1):
                for i, goal in enumerate(step["goals"], 1):
                    expected[f"{s}.{i}"] = goal.get("quest") or goal.get("workForQuest") or goal.get("detourQuest")
            for quest in chapter["quests"]:
                self.assertEqual(len(quest["steps"]), len(quest["instructions"]))
                actual.extend((position, quest["id"]) for position, _ in quest["steps"])
            actual.extend((position, None) for position, *_ in chapter["other"])
            self.assertEqual(Counter(actual), Counter(expected.items()), guide["id"])

    def test_each_external_comparison_points_to_the_correct_source_file(self):
        facts = review.load(TOOLS / "route_comparison_facts.json")
        for side, qid, source, stages in facts["rows"]:
            self.assertIn(side, capture.SIDES)
            self.assertGreater(qid, 0)
            for stage, (file_id, line, level, section) in stages.items():
                self.assertIn(stage, ("A", "O", "E"))
                self.assertEqual(facts["files"][file_id][0], source)
                self.assertGreaterEqual(line, section)
                self.assertGreater(section, 0)
                self.assertTrue(level is None or 1 <= level <= 60)

    def test_faction_guards_and_route_boundaries_do_not_mix_visits(self):
        rows = list(capture.open_rows([
            "RegisterGuide([[", "#name 20-21", "step << Alliance", ".turnin 220",
            "step", ".accept 221 << Horde", "]])", ".turnin 222",
            "RegisterGuide([[", "<< !Horde", "#name 25-26", "step", ".complete 220", "]])",
        ], capture.SIDES))
        self.assertEqual(rows, [("Alliance", 220, "E", 4, 20, 1), ("Horde", 221, "A", 6, 20, 1),
                                ("Alliance", 220, "O", 13, 25, 9)])

    def test_order_comparison_requires_same_section_and_distinct_contacts(self):
        guide = {"faction": "Alliance", "steps": [
            {"goals": [{"t": "accept", "quest": qid, "npc": npc}]}
            for qid, npc in ((10, 1), (11, 2), (12, 3), (13, 3))]}
        missions = {qid: {} for qid in (10, 11, 12, 13)}
        hits = {("Alliance", qid): [("MacQuest", {"A": [1, line, 20, block]})]
                for qid, line, block in ((10, 50, 1), (11, 40, 1), (12, 80, 75), (13, 79, 75))}
        self.assertEqual(review.compare_visit_order(guide, missions, hits), {"checked": 1, "different": 1})
        self.assertEqual(missions[11]["order"], [["MacQuest", "A", 10, 1, 2, 1, 50, 40]])
