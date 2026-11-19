import copy
import importlib.util
import json
from pathlib import Path
import unittest

from tools import route_review_horde as review


SOURCE = Path(__file__).resolve().parents[1] / "RutaXP" / "Source"
spec = importlib.util.spec_from_file_location("horde_review_builder", SOURCE / "build_guides.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class HordeReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((SOURCE / "leveling.json").read_text(encoding="utf-8"))
        builder.apply_guide_revisions(cls.document, SOURCE / "guide_revisions.json")
        cls.before = {g["id"]: builder.route_shape(g) for g in cls.document["guides"]}
        review.apply(cls.document)
        cls.guides = {g["id"][len(review.PREFIX):]: g for g in cls.document["guides"] if g["id"].startswith(review.PREFIX)}

    def goals(self, slug, quest):
        return [g for s in self.guides[slug]["steps"] for g in s["goals"] if g.get("quest") == quest]

    def test_every_horde_chapter_reviewed_and_overlay_is_repeatable(self):
        self.assertEqual(set(review.REFERENCES), {review.PREFIX + slug for slug in self.guides})
        self.assertEqual(len(review.REFERENCES), 28)
        self.assertEqual(self.before, {g["id"]: builder.route_shape(g) for g in self.document["guides"]})
        duplicate = copy.deepcopy(self.document)
        review.apply(duplicate)
        self.assertEqual(duplicate, self.document)
        for (chapter, quest), record in review.NOTES.items():
            self.assertTrue(self.goals(chapter.removeprefix(review.PREFIX), quest), (chapter, quest))
            self.assertTrue(record["url"].startswith("https://"))

    def test_repeats_preserve_first_quest_and_ready_ingredients(self):
        for slug, repeat, items, unrelated in (
            ("40-50/05-the-hinterlands", 2601, {"8394": 10, "8396": 2}, 2581),
            ("40-50/06-azshara", 7725, {"18956": 10}, 7003),
            ("50-60/06-silithus", 8323, {"20404": 10}, 8279),
            ("50-60/03-winterspring", 8469, {"21383": 5}, 8464),
        ):
            for goal in self.goals(slug, repeat):
                self.assertTrue(goal["levelingDetour"])
                self.assertEqual(goal["detourItems"], items)
            other = self.goals("40-50/03-feralas" if unrelated == 7003 else slug, unrelated)
            self.assertTrue(other)
            self.assertFalse(any(g.get("levelingDetour") for g in other))
        salfa = self.guides["50-60/03-winterspring"]["steps"][16]["goals"][0]
        self.assertEqual((salfa["t"], salfa["workForQuest"], salfa["workForObjective"]), ("goto", 8469, 1))
        for goal in self.goals("40-50/04-tanaris", 1560):
            self.assertTrue(goal["levelingDetour"])
        self.assertFalse(any(g.get("levelingDetour") for g in self.goals("40-50/04-tanaris", 3520)))
        for goal in self.goals("50-60/02-felwood", 6031):
            self.assertTrue(goal["levelingDetour"])
            self.assertNotIn("detourItems", goal)
            self.assertIn("Amistoso", goal["note"])

    def test_yeti_starts_in_everlook_and_keeps_individual_objective_credit(self):
        first = self.guides["50-60/03-winterspring"]["steps"][4]["goals"]
        self.assertEqual(first[-2]["quest"], 5163)
        self.assertEqual((first[-1]["workForQuest"], first[-1]["workForObjective"], first[-1]["map"]), (5163, 1, 1452))
        self.assertIn("Legacki", first[-1]["text"])
        for chapter, npc, index in (("50-60/05-eastern-plaguelands", 7583, 2), ("50-60/06-silithus", 10977, 3)):
            goal = self.goals(chapter, 5163)[0]
            self.assertEqual((goal["npc"], goal["oi"], goal["reviewedVerb"]), (npc, index, "Asusta"))
            self.assertIn("yeti mecánico", goal["note"])

    def test_only_travel_exclusively_for_missing_xp_expires_at_target_level(self):
        found = {(slug, g["untilLevel"]) for slug, guide in self.guides.items()
                 for s in guide["steps"] for g in s["goals"] if "untilLevel" in g and g["t"] == "goto"}
        self.assertEqual(found, review.GRIND_TRAVEL)
        for slug, level in found:
            step = next(s for s in self.guides[slug]["steps"] if any(g.get("untilLevel") == level for g in s["goals"]))
            walk = next(g for g in step["goals"] if g["t"] == "goto")
            hunt = next(g for g in step["goals"] if g["t"] == "level")
            self.assertEqual(tuple(hunt[k] for k in ("map", "x", "y")), tuple(walk[k] for k in ("map", "x", "y")))
        felwood = self.guides["50-60/02-felwood"]["steps"]
        self.assertTrue(felwood[19]["goals"][0]["levelingDetour"])
        self.assertFalse(felwood[46]["goals"][0].get("levelingDetour"))
        dungeon_note = self.guides["50-60/07-felwood"]["steps"][15]["goals"][0]
        self.assertEqual((dungeon_note["t"], dungeon_note["levelingDetour"]), ("note", True))

    def test_two_bandarion_quests_follow_leonid_and_the_elixir_stays_early(self):
        guide = self.guides["undead/01-tirisfal-glades"]
        self.assertEqual(len(guide["steps"]), 71)
        visits = []
        for si, step in enumerate(guide["steps"], 1):
            for goal in step["goals"]:
                if goal.get("quest") in (96896, 95314, 99152, 99153):
                    visits.append((goal["quest"], goal["t"], si))
                if goal.get("quest") in (99152, 99153):
                    self.assertFalse(step.get("only"))
                    self.assertFalse(goal.get("only"))
                    if goal["t"] == "accept":
                        self.assertEqual((goal["minLevel"], goal["qlvl"]), (10, 12))
        self.assertLess(visits.index((96896, "turnin", 65)), visits.index((99152, "accept", 65)))
        self.assertIn((95314, "collect", 44), visits)
        self.assertIn((99153, "collect", 66), visits)
        self.assertIn((99152, "turnin", 67), visits)
        migration = next(m for m in guide["progressMigrations"] if m["from"] == 3)
        self.assertEqual([migration["stepMap"][k] for k in ("44", "45", "46", "67", "68", "72")], [44, 44, 45, 65, 68, 72])
        self.assertEqual([migration["goalMap"][k] for k in ("44:1", "45:2", "46:1")], ["65:4", "44:1", "67:1"])
        kyle = self.goals("tauren/01-mulgore", 99411)
        self.assertEqual(kyle[0]["minLevel"], 5)


if __name__ == "__main__":
    unittest.main()
