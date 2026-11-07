"""Reviewed additions cannot remove old goals or inherit their saved marks."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "RutaXP/Source"
spec = importlib.util.spec_from_file_location("addition_builder", SOURCE / "build_guides.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ReviewedAdditionsTests(unittest.TestCase):
    def fixture(self):
        guide = {"id": "example", "steps": [{"title": "Camp", "goals": [
            {"t": "accept", "quest": 1}, {"t": "turnin", "quest": 1}]}]}
        added = {"t": "accept", "quest": 2, "pre": [1]}
        result = copy.deepcopy(guide)
        result["steps"][0]["goals"].append(added)
        revision = {"id": "reviewed", "guideID": "example", "previousRevision": 1, "revision": 2,
            "sourceShape": builder.route_shape(guide), "resultShape": builder.route_shape(result),
            "previousGoalCounts": [2], "firstAffectedStep": 1, "affectedQuestIDs": [2],
            "steps": [{"title": "Camp", "goals": [[1, 1], [1, 2], {"added": "followup"}]}],
            "addedGoals": {"followup": {"goal": added, "evidence": {"source": "test fixture"}}},
            "evidence": {"review": "Test-only reviewed facts"}}
        return guide, result, revision

    def apply(self, guide, revision):
        document = {"provenance": {"commit": "test"}, "statistics": {}, "guides": [guide]}
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "revision.json"
            file.write_text(json.dumps({"schemaVersion": 1, "sourceCommit": "test", "revisions": [revision]}), encoding="utf8")
            builder.apply_guide_revisions(document, file)
            before = copy.deepcopy(document)
            builder.apply_guide_revisions(document, file)
            self.assertEqual(document, before)
        return document

    def test_addition_is_explicit_and_old_keys_keep_their_identity(self):
        guide, result, revision = self.fixture()
        document = self.apply(guide, revision)
        self.assertEqual(document["guides"][0]["steps"], result["steps"])
        self.assertEqual(document["statistics"]["goals"], 3)
        migration = builder.revision_progress(revision)
        self.assertEqual(migration["goalMap"], {})
        self.assertEqual(migration["addedGoalKeys"], ["1:3"])
        self.assertEqual(migration["firstAffectedStep"], 1)
        self.assertEqual(migration["stepMap"], {"1": 1, "2": 2})

    def test_missing_duplicate_and_unreviewed_additions_are_rejected(self):
        for case in ("missing", "duplicate", "evidence", "unknown", "lost-original"):
            with self.subTest(case=case):
                guide, _, revision = self.fixture()
                refs = revision["steps"][0]["goals"]
                if case == "missing": refs.pop()
                elif case == "duplicate": refs.append({"added": "followup"})
                elif case == "evidence": revision["addedGoals"]["followup"].pop("evidence")
                elif case == "unknown": refs[-1] = {"added": "unknown"}
                else: refs.pop(0)
                with self.assertRaises(ValueError): builder.revision_progress(revision)
                with self.assertRaises(ValueError): self.apply(guide, revision)

    def test_replacement_on_reused_indices_requires_matching_source_actions(self):
        guide, _, revision = self.fixture()
        revision["retiredGoals"] = {
            "1:1": {"match": {"t": "accept", "quest": 1}, "evidence": "Old acceptance"},
            "1:2": {"match": {"t": "turnin", "quest": 1}, "evidence": "Old delivery"},
        }
        revision["steps"][0].update(cursorFromStep=1, goals=[{"added": "followup"}])
        result_steps = [{"title": "Camp", "goals": [revision["addedGoals"]["followup"]["goal"]]}]
        revision["resultShape"] = builder.route_shape(dict(guide, steps=result_steps))
        final = self.apply(copy.deepcopy(guide), revision)["guides"][0]
        self.assertEqual(final["steps"], result_steps)
        self.assertIsNone(builder.current_goal_key(final, 1, 1))
        self.assertEqual(final["progressMigrations"][0]["stepMap"], {"1": 1, "2": 2})
        revision["retiredGoals"]["1:1"]["match"]["quest"] = 222
        with self.assertRaisesRegex(ValueError, "Retired source action changed"):
            self.apply(guide, revision)


if __name__ == "__main__":
    unittest.main()
