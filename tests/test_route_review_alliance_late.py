"""Regression cases specific to the reviewed Forever Alliance 30–60 route."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools import route_review_alliance_late as review
from tools.guide_instructions import enrich_document
from tools.route_review_alliance_late_capture import Page


ROOT = Path(__file__).resolve().parents[1]


class AllianceLateReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((ROOT / "RutaXP/Source/leveling.json").read_text(encoding="utf8"))
        chapters = [g for g in catalog["guides"] if g["id"] in review.REFERENCES]
        cls.catalog = enrich_document(review.apply({"guides": chapters, "provenance": catalog["provenance"]}))
        cls.guides = {g["id"]: g for g in cls.catalog["guides"]}
        cls.pages = json.loads((ROOT / "tools/route_review_alliance_late_sage.json").read_text(encoding="utf8"))["pages"]

    def goals(self, chapter):
        return [goal for step in self.guides[review.ALLIANCE + chapter]["steps"] for goal in step["goals"]]

    def test_all_chapters_have_an_independently_linked_quest(self):
        self.assertEqual(len(self.guides), 19)
        by_url = {row["url"]: row for row in self.pages}
        for chapter, (path, quest, _, _) in review.CHAPTERS.items():
            with self.subTest(chapter=chapter):
                self.assertIn(quest, {q.get("quest") for q in self.goals(chapter)})
                page = by_url[review.SAGE + path]
                self.assertTrue(any(quest in page[k] for k in ("accept", "work", "turnin")))
                self.assertIn((review.ALLIANCE + chapter, quest), review.NOTES)

    def test_capture_only_credits_eligible_rows_and_their_own_action(self):
        parser = Page()
        parser.feed('<ul><li><img title="Classic"><img title="Quest Do">'
                    '<a href="https://www.wowhead.com/classic/quest=10">A</a></li>'
                    '<li><img title="Forever"><img title="Quest Start">'
                    '<a href="https://www.wowhead.com/forever/quest=20">B</a>'
                    '<a href="https://www.wowhead.com/forever/quest=21">C</a></li>'
                    '<li><img title="Quest End"><a href="https://www.wowhead.com/classic/quest=22">D</a></li></ul>')
        self.assertEqual(parser.rows, [("accept", 20), ("mentions", 21), ("turnin", 22)])

    def test_applies_to_raw_and_is_idempotent_without_affecting_other_factions(self):
        controls = {"id": "forever/horde/" + review.HILLS, "steps": [{"goals": [
            {"t": "goto", "text": "Ayuntamiento de Trabalomas"}]}]}
        copy = deepcopy(self.catalog)
        for guide in copy["guides"]:
            for step in guide["steps"]:
                for goal in step["goals"]:
                    for key in ("workForQuest", "workVisit", "workForObjective", "reviewedVerb"):
                        goal.pop(key, None)
        copy["guides"].append(deepcopy(controls))
        review.apply(copy)
        self.assertEqual(copy["guides"][-1], controls)
        self.assertEqual(copy["guides"][:-1], self.catalog["guides"])
        self.assertEqual(review.apply(deepcopy(copy)), copy)

    def test_specimens_and_friends_use_exact_credits_and_correct_player_verbs(self):
        goals = [q for c in review.CHAPTERS for q in self.goals(c)]
        captures = [(q["npc"], q["workForObjective"]) for q in goals if q.get("workForQuest") == 93176]
        self.assertCountEqual(captures, [(217588, 1), (217589, 2), (217590, 3)])
        for q in goals:
            if q.get("workForQuest") == 93176:
                self.assertFalse(q.get("levelingDetour"))
            if q.get("quest") == 93176:
                self.assertTrue(q.get("levelingDetour"))
        scares = [(q["npc"], q["oi"]) for q in goals if q.get("quest") == 5163 and q["t"] == "kill"]
        self.assertCountEqual(scares, [(10978, 1), (7583, 2), (10977, 3)])
        self.assertEqual(Counter(q.get("reviewedVerb") for q in goals if q.get("reviewedVerb")),
                         {"Captura": 3, "Asusta": 3})
        self.assertCountEqual([q["workForObjective"] for q in goals if q.get("workForQuest") == 5163], [1, 2])
        for q in goals:
            if "reviewedVerb" in q:
                self.assertTrue(q["instruction"].startswith(q["reviewedVerb"] + " "))

    def test_gated_travel_keeps_independent_activities(self):
        for chapter, groups in ((review.HILLS, {98059: 1}), (review.DESOLACE, {1440: 1}),
                                (review.CRATER, {4285: 1, 4287: 1, 4288: 1}), (review.FELWOOD, {5156: 3})):
            actions = [q for q in self.goals(chapter) if q["t"] == "goto" and q.get("workForQuest") in groups]
            self.assertEqual(Counter(q["workForQuest"] for q in actions), groups)
            for goal in actions:
                self.assertEqual(bool(goal.get("workVisit")), chapter == review.FELWOOD)
        arathi = self.goals(review.ARATHI)
        for quest in (522, 523):
            goals = [q for q in arathi if q.get("quest") == quest]
            self.assertTrue(goals and all(q.get("levelingDetour") for q in goals))
        self.assertFalse(any(q.get("levelingDetour") for q in arathi if q.get("quest") in (525, 537)))
        self.assertEqual([q.get("detourItems") for q in arathi if q.get("detourQuest") == 522], [{"3668": 1}])
        ships = self.goals(review.JUNGLE_SOUTH)
        scroll = [q for q in ships if q.get("item") == 4056]
        self.assertEqual(len(scroll), 2)
        self.assertTrue(all(q.get("detourItems") == {"4056": 1} for q in scroll))
        self.assertTrue(any(q["t"] == "turnin" and q.get("quest") == 624 and not q.get("levelingDetour") for q in ships))
        displacer, = [q for q in self.goals(review.PLAGUE) if q.get("item") == 12627]
        self.assertEqual((displacer.get("workForQuest"), displacer.get("workForObjective")), (4971, 1))

    def test_solo_has_local_coordinates_at_the_four_existing_level_gates(self):
        for (chapter, level), (zone, x, y, _) in review.LEVEL_HUNTS.items():
            gate, = [q for q in self.goals(chapter) if q.get("level") == level and q["t"] == "level"]
            self.assertEqual((gate["map"], gate["x"], gate["y"], gate["f"]), (zone, x, y, "e"))
            self.assertFalse(gate.get("levelingDetour"))
        temple, = [q for q in self.goals(review.WINTERSPRING)
                   if q["t"] == "note" and "Templo Sumergido" in q.get("text", "")]
        self.assertTrue(temple["levelingDetour"])
