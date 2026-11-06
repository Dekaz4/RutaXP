"""Regression cases for server quest chains that used to be accepted too early."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP/Source"


class ReviewedChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((SOURCE / "leveling.json").read_text(encoding="utf-8"))
        cls.guides = {g["id"]: g for g in cls.doc["guides"]}
        cls.revisions = json.loads((SOURCE / "guide_revisions.json").read_text(encoding="utf-8"))["revisions"]
        spec = importlib.util.spec_from_file_location("reviewed_chain_builder", SOURCE / "build_guides.py")
        cls.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.builder)

    def test_real_prerequisite_delivery_precedes_acceptance_work_and_rewards(self):
        cases = {
            "forever/alliance/skyborne/01-zephras-isle": {92860: 92834, 93320: 92860},
            "forever/alliance/04-redridge-mountains": {98386: 89},
            "forever/horde/tauren/01-mulgore": {99081: 99079, 99101: 99081, 99080: 99101, 99082: 99080},
            "forever/horde/undead/01-tirisfal-glades": {99156: 356},
            "forever/horde/03-silverpine-forest": {429: 428, 430: 429, 91920: 430, 91921: 91920},
        }
        for gid, chain in cases.items():
            goals = [goal for step in self.guides[gid]["steps"] for goal in step["goals"]]
            for quest, prerequisite in chain.items():
                with self.subTest(guide=gid, quest=quest):
                    accepted = next(i for i, g in enumerate(goals) if g.get("quest") == quest and g["t"] == "accept")
                    prior_delivery = next(i for i, g in enumerate(goals) if g.get("quest") == prerequisite and g["t"] == "turnin")
                    delivered = next(i for i, g in enumerate(goals) if g.get("quest") == quest and g["t"] == "turnin")
                    self.assertLess(prior_delivery, accepted)
                    self.assertLess(accepted, delivered)
                    self.assertIn(prerequisite, goals[accepted].get("pre", []) + goals[accepted].get("preAll", []))
                    for index, goal in enumerate(goals):
                        if goal.get("quest") == quest and goal["t"] not in ("accept", "turnin"):
                            self.assertLess(accepted, index)
                            self.assertLess(index, delivered)

    def test_added_visits_use_existing_npcs_and_keep_the_excursion_order_clear(self):
        mulgore = self.guides["forever/horde/tauren/01-mulgore"]["steps"]
        self.assertEqual([(g["t"], g.get("quest")) for g in mulgore[33]["goals"]], [("complete", 99080)])
        self.assertEqual([(g["t"], g.get("quest")) for g in mulgore[34]["goals"]], [("turnin", 99080), ("accept", 99082)])
        self.assertTrue(all(g["npc"] == 2993 for g in mulgore[34]["goals"]))
        tirisfal = self.guides["forever/horde/undead/01-tirisfal-glades"]["steps"]
        self.assertEqual([(g["t"], g.get("quest")) for g in tirisfal[58]["goals"]], [("turnin", 356), ("accept", 99156)])
        self.assertTrue(all(g["npc"] == 1495 for g in tirisfal[58]["goals"]))
        silverpine = self.guides["forever/horde/03-silverpine-forest"]["steps"]
        self.assertEqual([(g["t"], g.get("quest")) for g in silverpine[20]["goals"]], [("collect", 91920)])
        self.assertEqual([(g["t"], g.get("quest")) for g in silverpine[23]["goals"]], [("turnin", 91921)])
        self.assertEqual(silverpine[23]["goals"][0]["npc"], 1951)

    def test_migrations_cover_each_old_goal_once_and_keep_completed_cursors(self):
        for revision in self.revisions:
            if "previousGoalCounts" not in revision:
                continue
            migration = self.builder.revision_progress(revision)
            guide = self.guides[revision["guideID"]]
            self.assertIn(migration, guide["progressMigrations"])
            keys = {f"{si}:{gi}" for si, count in enumerate(revision["previousGoalCounts"], 1) for gi in range(1, count + 1)}
            destinations = [migration["goalMap"].get(key, key) for key in keys]
            self.assertEqual(len(destinations), len(set(destinations)), revision["id"])
            completed = migration["stepMap"][str(migration["previousStepCount"] + 1)]
            revision_number = migration["to"]
            while revision_number < guide["routeRevision"]:
                following = next(m for m in guide["progressMigrations"] if m["from"] == revision_number)
                completed = following["stepMap"].get(str(completed), completed)
                revision_number = following["to"]
            self.assertEqual(completed, len(guide["steps"]) + 1)
            self.assertTrue(all(old != new for old, new in migration["goalMap"].items()))
        west = self.guides["forever/alliance/02-westfall"]["progressMigrations"]
        self.assertFalse(any(m["from"] == 1 for m in west))
        self.assertEqual(west[0]["goalMap"]["2:5"], "12:6")
        self.assertEqual(west[0]["goalMap"]["5:5"], "12:7")

    def test_duplicate_or_missing_migration_references_are_rejected(self):
        revision = copy.deepcopy(next(r for r in self.revisions if r["id"] == "redridge-alther-bridge-2"))
        revision["steps"][11]["goals"][0] = revision["steps"][11]["goals"][1]
        with self.assertRaisesRegex(ValueError, "Invalid migration goal reference"):
            self.builder.revision_progress(revision)

    def test_28_metadata_requirements_are_corroborated_and_already_delivered_in_route(self):
        count = 0
        for revision in self.revisions:
            if not revision["id"].endswith("-prerequisites-metadata"):
                continue
            self.assertTrue(revision["preserveSteps"])
            migration = self.builder.revision_progress(revision)
            self.assertEqual(migration["goalMap"], {})
            self.assertEqual(migration["affectedQuestIDs"], [])
            goals = [goal for step in self.guides[revision["guideID"]]["steps"] for goal in step["goals"]]
            proofs = {entry["questID"]: entry for entry in revision["evidence"]["corroboratedAcceptances"]}
            self.assertEqual(len(proofs), len(revision["goalChanges"]))
            for patch in revision["goalChanges"]:
                count += 1
                quest = patch["match"]["quest"]
                proof = proofs[quest]
                accepted = next(i for i, goal in enumerate(goals) if goal.get("t") == "accept" and goal.get("quest") == quest)
                prerequisites = patch["set"].get("pre", []) + patch["set"].get("preAll", [])
                self.assertEqual(len(prerequisites), 1)
                for key, value in patch["set"].items():
                    self.assertEqual(goals[accepted][key], value)
                for parent in prerequisites:
                    self.assertTrue(any(goal.get("t") == "turnin" and goal.get("quest") == parent for goal in goals[:accepted]))
                self.assertTrue(proof["proofs"])
                self.assertTrue(proof["eqProofs"])
                self.assertTrue(any(p["sourceQuestIDs"] == prerequisites for p in proof["proofs"]))
                for att in proof["proofs"]:
                    self.assertEqual(att["commit"], "b50b6d8335d56a215bb3053811745f617532cc14")
                    self.assertFalse(att["declaresBreadcrumb"])
                    self.assertRegex(att["sha256"], r"^[0-9a-f]{64}$")
                    self.assertIn(att["commit"], att["url"])
                for eq in proof["eqProofs"]:
                    self.assertIn("/8e7aa971319226f984639d4dae06e864b50c4fb4/", eq["url"])
                    self.assertGreater(eq["source"]["line"], 0)
        self.assertEqual(count, 28)


if __name__ == "__main__":
    unittest.main()
