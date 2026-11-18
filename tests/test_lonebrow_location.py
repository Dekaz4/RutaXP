"""The moved Forever journal must not send players back to its old corpse."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from test_boat_navigation import BoatHost, GUIDE


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP/Source"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


builder = module("lonebrow_builder", SOURCE / "build_guides.py")


def journal(document):
    guide = next(g for g in document["guides"] if g["id"] == GUIDE)
    hits = [(step, goal) for step in guide["steps"] for goal in step["goals"]
            if goal.get("item") == 5791 and goal["t"] == "collect"]
    if len(hits) != 1:
        raise AssertionError("The journal collection must be unique in this guide")
    return guide, hits[0][0], hits[0][1]


class LonebrowLocationTests(unittest.TestCase):
    def document(self):
        return json.loads((SOURCE / "leveling.json").read_text(encoding="utf8"))

    def test_native_contact_and_instructions_replace_the_old_elevator_location(self):
        _, step, goal = journal(self.document())
        self.assertEqual((goal["map"], goal["x"], goal["y"], goal["f"]), (1441, 31.3, 28.1, "l"))
        self.assertEqual((goal["t"], goal["item"]), ("collect", 5791))
        self.assertIn("esqueleto", goal["instruction"])
        self.assertIn("bolsas", goal["instruction"])
        self.assertEqual(step["title"], "Gran Elevador")
        self.assertNotIn("al pie del ascensor", step["note"])
        acceptance = step["goals"][1]
        self.assertEqual((acceptance["t"], acceptance["quest"], acceptance["item"]), ("accept", 1100, 5791))
        self.assertNotIn("map", acceptance)

    def test_overlay_reapplies_to_all_object_collections_without_changing_progress_or_semantics(self):
        document = self.document()
        guide, step, goal = journal(document)
        duplicate = {"id": "test/second-journal-visit", "steps": [{"goals": [copy.deepcopy(goal)]}]}
        duplicate["steps"][0]["goals"][0].update(obj=19861)
        document["guides"].append(duplicate)
        route_shapes = {g["id"]: builder.route_shape(g) for g in document["guides"]}
        progress = copy.deepcopy(guide["progressMigrations"])
        for target in (goal, duplicate["steps"][0]["goals"][0]):
            target.update(x=30.7, y=24.3, f="e", note="Old corpse")
        step.update(title="El Great Lift", note="El diario se encuentra al pie del ascensor.")
        builder.apply_guide_overrides(document, SOURCE / "guide_overrides.json")
        for target in (goal, duplicate["steps"][0]["goals"][0]):
            self.assertEqual((target["x"], target["y"], target["f"]), (31.3, 28.1, "l"))
        self.assertEqual({g["id"]: builder.route_shape(g) for g in document["guides"]}, route_shapes)
        self.assertEqual(guide["progressMigrations"], progress)
        once = copy.deepcopy(document)
        builder.apply_guide_overrides(document, SOURCE / "guide_overrides.json")
        self.assertEqual(document, once)

    def test_actual_navigation_uses_native_new_location_without_quest_credit(self):
        h = BoatHost(position=(1441, .307, .243))
        state = h.ns.char.progress[GUIDE]
        state.cursor = 33
        step = h.guide.steps[33]
        self.assertIsNone(h.ns.GetStepWaypoint(h.ns, step))
        h.ns.SetIncludeGroupQuests(h.ns, True)
        point = h.ns.GetStepWaypoint(h.ns, step)
        self.assertEqual(point.mapID, 1441)
        self.assertAlmostEqual(point.x, .313)
        self.assertAlmostEqual(point.y, .281)
        self.assertEqual(point.goal.item, 5791)
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 1100))
        self.assertEqual(state.cursor, 33)

    def test_reimport_of_the_original_pinned_guides_retains_the_relocation(self):
        upstream = ROOT / ".sources/SendaFH"
        if not upstream.is_dir():
            self.skipTest("Pinned upstream checkout unavailable")
        importer = module("lonebrow_importer", ROOT / "tools/import_guides.py")
        with tempfile.TemporaryDirectory(prefix="rutaxp-lonebrow-") as temporary:
            destination = Path(temporary)
            (destination / "Source").mkdir()
            for filename in ("build_guides.py", "guide_overrides.json"):
                shutil.copyfile(SOURCE / filename, destination / "Source" / filename)
            importer.import_guides(upstream, destination, importer.PINNED_COMMIT)
            imported = json.loads((destination / "Source/leveling.json").read_text(encoding="utf8"))
            _, step, goal = journal(imported)
            self.assertEqual((goal["x"], goal["y"], goal["f"]), (31.3, 28.1, "l"))
            self.assertEqual(step["title"], "Gran Elevador")


if __name__ == "__main__":
    unittest.main()
