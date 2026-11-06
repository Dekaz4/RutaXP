"""Reviewed Alba quest prerequisites, ordered visits and reproducible imports."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP/Source"
WEST = "forever/alliance/02-westfall"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class WestfallAlbaContentTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((SOURCE / "leveling.json").read_text(encoding="utf-8"))
        self.guide = next(guide for guide in self.doc["guides"] if guide["id"] == WEST)
        self.builder = module("westfall_alba_builder", SOURCE / "build_guides.py")

    def test_both_independent_quests_are_delivered_before_mines_acceptance_and_work(self):
        guide = self.guide
        self.assertEqual((guide["routeRevision"], len(guide["steps"])), (3, 22))
        initial = {goal.get("quest"): goal for goal in guide["steps"][0]["goals"] if goal["t"] == "accept"}
        self.assertIn(92742, initial)
        self.assertIn(92744, initial)
        self.assertNotIn(92745, initial)
        for quest in (92742, 92744):
            self.assertFalse(initial[quest].get("pre") or initial[quest].get("preAll"))
        coast = guide["steps"][5]["goals"]
        self.assertEqual([(goal["t"], goal.get("quest")) for goal in coast], [("collect", 92744), ("collect", 38)])
        alba = guide["steps"][6]["goals"]
        self.assertEqual([(goal["t"], goal["quest"]) for goal in alba], [("turnin", 92742), ("turnin", 92744), ("accept", 92745)])
        self.assertEqual(alba[2]["preAll"], [92742, 92744])
        for goal in alba:
            self.assertEqual((goal["npc"], goal["map"], goal["x"], goal["y"]), (253092, 1436, 52.48, 53.05))
            self.assertEqual(goal["npcName"], "Alba Lunajusta")
            self.assertIn("Alba Lunajusta", goal["instruction"])
        miners = guide["steps"][7]["goals"][0]
        kobolds = guide["steps"][8]["goals"][0]
        self.assertEqual((miners["t"], miners["quest"], miners["oi"]), ("kill", 92745, 2))
        self.assertEqual((kobolds["t"], kobolds["quest"], kobolds["oi"]), ("kill", 92745, 1))
        final = [(goal["t"], goal.get("quest")) for goal in guide["steps"][12]["goals"]]
        self.assertIn(("turnin", 92745), final)
        self.assertNotIn(("turnin", 92742), final)
        self.assertNotIn(("turnin", 92744), final)

    def test_overlay_is_idempotent_and_rejects_changed_reviewed_semantics(self):
        before = copy.deepcopy(self.doc)
        self.builder.apply_guide_revisions(self.doc, SOURCE / "guide_revisions.json")
        self.assertEqual(self.doc, before)
        self.guide["steps"][6]["goals"][2]["preAll"] = [92744]
        with self.assertRaisesRegex(ValueError, "semantics changed"):
            self.builder.apply_guide_revisions(self.doc, SOURCE / "guide_revisions.json")

    def test_evidence_is_pinned_and_every_source_goal_has_one_destination(self):
        overlay = json.loads((SOURCE / "guide_revisions.json").read_text(encoding="utf-8"))
        revision = overlay["revisions"][0]
        self.assertEqual(revision["guideID"], WEST)
        self.assertEqual(revision["evidence"]["sourceCommit"], "54a16756db16adeb9d5602bace1507077df37185")
        self.assertEqual(revision["evidence"]["preAll"], [92742, 92744])
        self.assertEqual(self.builder.route_shape(self.guide), next(r for r in overlay["revisions"] if r["id"] == "westfall-engineering-3")["resultShape"])
        self.assertEqual(self.doc["statistics"]["steps"], 2343)

    def test_clean_reimport_reapplies_only_reviewed_route_semantics(self):
        upstream = ROOT / ".sources/SendaFH"
        if not upstream.is_dir():
            self.skipTest("Optional pinned upstream checkout is unavailable")
        importer = module("westfall_alba_importer", ROOT / "tools/import_guides.py")
        with tempfile.TemporaryDirectory(prefix="rutaxp-alba-content-") as directory:
            output = Path(directory)
            (output / "Source").mkdir()
            for filename in ("build_guides.py", "guide_overrides.json", "guide_locations.json", "guide_revisions.json"):
                shutil.copyfile(SOURCE / filename, output / "Source" / filename)
            importer.import_guides(upstream, output, importer.PINNED_COMMIT)
            imported = json.loads((output / "Source/leveling.json").read_text(encoding="utf-8"))
            self.assertEqual(imported["guides"], self.doc["guides"])
            self.assertEqual(imported["provenance"]["routeRevisions"], self.doc["provenance"]["routeRevisions"])


if __name__ == "__main__":
    unittest.main()
