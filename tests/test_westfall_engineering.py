"""Engineering branches require their actual profession, chain and materials."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from test_quest_engine import QuestEngineHost


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP/Source"
WEST = "forever/alliance/02-westfall"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WestfallEngineeringTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads((SOURCE / "leveling.json").read_text(encoding="utf-8"))
        self.overlay = json.loads((SOURCE / "guide_revisions.json").read_text(encoding="utf-8"))
        self.guide = next(g for g in self.document["guides"] if g["id"] == WEST)
        self.builder = load_module("engineering_builder", SOURCE / "build_guides.py")

    def test_engineering_is_optional_and_the_universal_quest_remains_available(self):
        found = []
        for step in self.guide["steps"]:
            for goal in step["goals"]:
                if goal.get("quest") in (92910, 92911) or goal.get("item") == 255155:
                    found.append(goal)
                    self.assertTrue(goal["optional"])
                    self.assertEqual((goal["profLine"], goal["profRank"], goal["profName"]), (202, 1, "Ingeniería"))
                elif goal.get("quest") == 92909:
                    self.assertFalse(goal.get("optional"))
                    self.assertIsNone(goal.get("profLine"))
        self.assertEqual(len(found), 6)
        self.assertFalse(any(goal.get("quest") == 92911 for goal in self.guide["steps"][1]["goals"]))
        self.assertFalse(any(goal.get("quest") == 92911 for goal in self.guide["steps"][4]["goals"]))

    def test_followup_acceptance_follows_real_delivery_and_checks_all_materials(self):
        goals = self.guide["steps"][11]["goals"]
        self.assertEqual([(g["t"], g.get("quest")) for g in goals[4:]],
                         [("turnin", 92910), ("accept", 92911), ("complete", 92911), ("turnin", 92911)])
        self.assertEqual(goals[5]["preAll"], [92910])
        work = goals[6]
        self.assertNotIn("oi", work)
        self.assertEqual(work["navigationMode"], "inventory")
        for phrase in ("8 isomuelles", "4 moduladores", "1 mira"):
            self.assertIn(phrase, work["note"])
        self.assertIn("Molsen", work["navigationHint"])
        proof = next(r for r in self.overlay["revisions"] if r["id"] == "westfall-engineering-3")["evidence"]
        self.assertEqual(proof["materials"], {"255007": 8, "4363": 4, "4405": 1})
        self.assertEqual(proof["sourceCommit"], "b50b6d8335d56a215bb3053811745f617532cc14")
        self.assertRegex(proof["sourceSha256"], r"^[a-f0-9]{64}$")

    def test_finishing_only_springs_does_not_mark_the_material_quest_complete(self):
        host = QuestEngineHost(catalog=True)
        host.initialize()
        host.ns.char.auto = False
        host.call("SelectGuide", WEST)
        host.call("GetProgress", WEST).cursor = 12
        host.quest(92911, onQuest=True, complete=False, objectives=[
            {"finished": True, "numFulfilled": 8, "numRequired": 8},
            {"finished": False, "numFulfilled": 0, "numRequired": 4},
            {"finished": False, "numFulfilled": 0, "numRequired": 1},
        ])
        step = host.ns.guides[WEST].steps[12]
        self.assertEqual(host.status(step.goals[7], step, host.call("GetProgress", WEST), 7), "active")
        host.quest(92911, onQuest=True, complete=True)
        self.assertEqual(host.status(step.goals[7], step, host.call("GetProgress", WEST), 7), "done")

    def test_navigation_exception_requires_the_bound_revision_evidence(self):
        audit = load_module("engineering_audit", ROOT / "tools/audit_guides.py").audit
        key = WEST + ":12:7"
        without = next(item for item in audit(self.document)["missingNavigation"] if item["key"] == key)
        self.assertTrue(without["unresolved"])
        with_proof = next(item for item in audit(self.document, revisions=self.overlay)["missingNavigation"] if item["key"] == key)
        self.assertFalse(with_proof["unresolved"])
        self.assertEqual(with_proof["classification"], "documented_navigation_mode")
        wrong = copy.deepcopy(self.overlay)
        next(r for r in wrong["revisions"] if r["id"] == "westfall-engineering-3")["evidence"]["sourceSha256"] = "not-a-hash"
        unproven = next(item for item in audit(self.document, revisions=wrong)["missingNavigation"] if item["key"] == key)
        self.assertTrue(unproven["unresolved"])

    def test_latest_revision_rebuild_is_idempotent_but_unknown_revisions_are_rejected(self):
        before = copy.deepcopy(self.document)
        self.builder.apply_guide_revisions(self.document, SOURCE / "guide_revisions.json")
        self.assertEqual(self.document, before)
        self.guide["routeRevision"] = 99
        with self.assertRaisesRegex(ValueError, "semantics changed"):
            self.builder.apply_guide_revisions(self.document, SOURCE / "guide_revisions.json")

    def test_metadata_only_revision_preserves_every_goal_position(self):
        guide = {"id": "metadata", "steps": [{"title": "Original", "goals": [
            {"t": "accept", "quest": 1}, {"t": "complete", "quest": 1}]}]}
        changed = copy.deepcopy(guide)
        changed["steps"][0]["goals"][0]["minLevel"] = 8
        document = {"provenance": {"commit": "test-pin"}, "statistics": {}, "guides": [guide]}
        overlay = {"schemaVersion": 1, "sourceCommit": "test-pin", "revisions": [{
            "id": "metadata-2", "guideID": "metadata", "previousRevision": 1, "revision": 2,
            "sourceShape": self.builder.route_shape(guide), "resultShape": self.builder.route_shape(changed),
            "preserveSteps": True, "goalChanges": [{"match": {"t": "accept", "quest": 1}, "count": 1,
                                                    "set": {"minLevel": 8}}], "evidence": {"source": "test fixture"},
        }]}
        with tempfile.TemporaryDirectory(prefix="rutaxp-revision-") as directory:
            path = Path(directory) / "revisions.json"
            path.write_text(json.dumps(overlay), encoding="utf-8")
            self.builder.apply_guide_revisions(document, path)
        self.assertEqual(document["guides"][0]["steps"], changed["steps"])
        self.assertEqual(document["guides"][0]["routeRevision"], 2)


if __name__ == "__main__":
    unittest.main()
