"""Published requirement evidence is diagnostic, explicit and reproducible."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP/Source"
spec = importlib.util.spec_from_file_location("requirements_audit", ROOT / "tools/audit_quest_requirements.py")
requirements = importlib.util.module_from_spec(spec)
spec.loader.exec_module(requirements)


def document(*goals, only=None):
    return {"guides": [{"id": "a", "faction": "Alliance", "steps": [
        {"title": "Camp", "only": only or {}, "goals": list(goals)}]}]}


def evidence(quest, **fields):
    return {"sources": {"test": {"commit": "pinned"}}, "quests": {str(quest): {
        **fields, "reportedFields": list(fields),
        "fieldSources": {field: [{"source": "test", "line": 12}] for field in fields}}}}


class QuestRequirementAuditTests(unittest.TestCase):
    def findings(self, goal, **facts):
        return requirements.audit(document(goal), evidence(goal["quest"], **facts))["findings"]

    def test_or_and_singletons_order_and_redundancy_are_equivalent(self):
        self.assertEqual(requirements.prerequisites({"pre": [2]}), requirements.prerequisites({"preAll": [2]}))
        self.assertEqual(requirements.prerequisites({"preAll": [3, 2]}), requirements.prerequisites({"preAll": [2, 3]}))
        self.assertEqual(requirements.prerequisites({"pre": [2, 3], "preAll": [2]}),
                         requirements.prerequisites({"preAll": [2]}))
        self.assertEqual(self.findings({"t": "accept", "quest": 1, "pre": [2]}, preAll=[2]), [])
        different = self.findings({"t": "accept", "quest": 1, "pre": [2, 3]}, preAll=[2, 3])
        self.assertEqual(different[0]["kind"], "prerequisite_conflict_review")

    def test_negative_active_requirement_never_equals_delivered_requirement(self):
        self.assertNotEqual(requirements.prerequisites({"preAll": [-2]}), requirements.prerequisites({"preAll": [2]}))
        self.assertEqual(requirements.prerequisites({"preAll": [-2]}), requirements.prerequisites({"parent": 2}))
        matching = self.findings({"t": "accept", "quest": 1, "preAll": [-2]}, parent=2)
        self.assertEqual(matching, [])
        mismatch = self.findings({"t": "accept", "quest": 1, "preAll": [2]}, parent=2)
        self.assertIn("missing_active_parent", {row["kind"] for row in mismatch})

    def test_missing_source_does_not_prove_no_requirements(self):
        rows = self.findings({"t": "accept", "quest": 1, "pre": [2]}, minLevel=10)
        self.assertIn("source_omission_review", {row["kind"] for row in rows})
        unknown = requirements.audit(document({"t": "accept", "quest": 1}), {"sources": {}, "quests": {}})
        self.assertEqual(unknown["scope"]["withoutReportedEvidence"], 1)
        self.assertEqual(unknown["findings"][0]["kind"], "no_source_data")

    def test_missing_positive_requirement_carries_source_and_dependency_order(self):
        doc = document({"t": "accept", "quest": 1}, {"t": "turnin", "quest": 2})
        result = requirements.audit(doc, evidence(1, preAll=[2]))
        finding = result["findings"][0]
        self.assertEqual(finding["kind"], "missing_prerequisite")
        self.assertEqual(finding["dependencyLocations"]["2"], [{"step": 1, "goal": 2, "action": "turnin"}])
        self.assertEqual(finding["evidence"], [{"source": "test", "line": 12}])

    def test_profession_line_and_rank_are_compared_without_changing_goal(self):
        goal = {"t": "accept", "quest": 1, "profLine": 202, "profRank": 1}
        original = copy.deepcopy(goal)
        self.assertEqual(self.findings(goal, skill={"id": 202, "rank": 1}), [])
        self.assertEqual(goal, original)
        self.assertEqual(self.findings(goal, skill={"id": 202, "rank": 50})[0]["kind"], "missing_profession_requirement")
        self.assertEqual(self.findings(goal, skill={"id": 333, "rank": 1})[0]["kind"], "missing_profession_requirement")

    def test_level_zero_and_one_are_not_false_conflicts(self):
        self.assertEqual(self.findings({"t": "accept", "quest": 1, "minLevel": 1}, minLevel=0), [])
        self.assertEqual(self.findings({"t": "accept", "quest": 1, "minLevel": 1}, minLevel=1), [])
        self.assertEqual(self.findings({"t": "accept", "quest": 1, "minLevel": 8}, minLevel=9)[0]["kind"], "level_conflict_review")

    def test_effective_class_and_race_conditions_include_containing_step(self):
        goal = {"t": "accept", "quest": 1}
        doc = document(goal, only={"classes": ["MAGE"], "races": ["Dwarf"]})
        source = evidence(1, classMask=128, raceMask=4)
        self.assertEqual(requirements.audit(doc, source)["findings"], [])
        source = evidence(1, classMask=2, raceMask=1)
        rows = requirements.audit(doc, source)["findings"]
        self.assertEqual({row["field"] for row in rows}, {"classMask", "raceMask"})

    def test_parser_reads_numeric_records_without_executing_lua(self):
        parsed = requirements.parse_eq('gates = {\n [1]=914000770000,\n},\npre = {\n [1]={-2,3},\n},\nos.execute("bad")')
        self.assertEqual(parsed["gates"][1], (914000770000, 2))
        self.assertEqual(parsed["pre"][1][0], [-2, 3])
        with self.assertRaises(ValueError):
            requirements.parse_eq('os.execute("anything")')

    def test_capture_retains_only_requested_ids_and_checks_att_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "eq.lua"
            path.write_text('gates = {\n [1]=914000770000,\n [2]=101000000000,\n},\nskill = {\n [1]=2020001,\n},')
            result = requirements.capture(path, {"repo": "owner/repo", "commit": "abc", "path": "data.lua"}, {1, 3})
            self.assertEqual(set(result["quests"]), {"1", "3"})
            self.assertEqual(result["quests"]["1"]["skill"], {"id": 202, "rank": 1})
            self.assertEqual(result["quests"]["1"]["minLevel"], 9)
            self.assertEqual(result["quests"]["1"]["raceMask"], 77)
            self.assertEqual(result["quests"]["3"]["reportedFields"], [])

    def test_att_parser_ignores_comments_strings_and_nested_quest_fields(self):
        lua = '''q(10, { -- sourceQuest = 99,
            description = "sourceQuest = 77, }",
            --[[ sourceQuest = 66, } ]]
            sourceQuests = { 20, -- comment
            }, groups = { q(11, { sourceQuest = 30, isBreadcrumb = true, }) },
        })'''
        outer = requirements.att_quest_facts(lua, 10)
        self.assertEqual(outer, [{"sourceQuestIDs": [20], "declaresBreadcrumb": False, "line": 1}])
        self.assertTrue(requirements.att_quest_facts(lua, 11)[0]["declaresBreadcrumb"])

    def test_att_corroboration_rejects_breadcrumbs_alternatives_and_changed_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "zone.lua"
            path.write_text('''q(1, {sourceQuest=2,})
q(2, {isBreadcrumb=true,})
q(3, {sourceQuests={2,4},})
q(4, {})
q(5, {sourceQuest=4,})
q(6, {groups={q(7, {sourceQuest=4,})},})''')
            manifest = {"repository": "owner/repo", "commit": "pinned", "sourceRoot": "data/",
                "reviewQuestIDs": [1, 3, 5, 6], "files": {"zone.lua": {
                    "sha256": requirements.sha(path.read_bytes()), "questIDs": [1, 2, 3, 4, 5, 6]}}}
            records = {str(q): evidence(q, preAll=[p])["quests"][str(q)] for q, p in ((1,2), (3,4), (5,4))}
            records["6"] = evidence(6, parent=4)["quests"]["6"]
            requirements.capture_att_reviews(records, {}, root, manifest)
            self.assertEqual(records["1"]["crossSourceReview"]["status"], "parent_breadcrumb")
            self.assertEqual(records["3"]["crossSourceReview"]["status"], "prerequisite_not_corroborated")
            self.assertEqual(records["5"]["crossSourceReview"]["status"], "corroborated_single_completed_parent")
            self.assertEqual(records["6"]["crossSourceReview"]["status"], "active_parent_not_explicit_in_att")
            self.assertEqual(len(records["1"]["fieldSources"]["preAll"]), 1)
            self.assertEqual(len(records["5"]["fieldSources"]["preAll"]), 2)
            path.write_text('q(1, {sourceQuest=999,})')
            with self.assertRaisesRegex(ValueError, "hash changed"):
                requirements.capture_att_reviews(records, {}, root, manifest)

    def test_shipped_evidence_covers_every_authored_quest_and_pins_both_sources(self):
        doc = json.loads((SOURCE / "leveling.json").read_text(encoding="utf-8"))
        data = json.loads((SOURCE / "quest_requirements_evidence.json").read_text(encoding="utf-8"))
        ids = {str(goal["quest"]) for guide in doc["guides"] for step in guide["steps"] for goal in step["goals"] if goal.get("quest")}
        self.assertEqual(ids, set(data["quests"]))
        for source in data["sources"].values():
            self.assertRegex(source["commit"], r"^[0-9a-f]{40}$")
            self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
            self.assertIn(source["commit"], source["url"])
            self.assertEqual(source["license"], "MIT")
        for qid in (92910, 92911):
            self.assertEqual(data["quests"][str(qid)]["skill"], {"id": 202, "rank": 1})
        self.assertEqual(data["quests"]["92910"]["startItem"], 255155)
        self.assertEqual(data["quests"]["92911"]["preAll"], [92910])
        self.assertEqual(data["quests"]["918"]["crossSourceReview"]["status"], "corroborated_single_completed_parent")
        self.assertEqual(data["quests"]["1639"]["crossSourceReview"]["status"], "prerequisite_not_corroborated")
        self.assertEqual(data["quests"]["6341"]["crossSourceReview"]["status"], "parent_breadcrumb")
        self.assertEqual(data["quests"]["339"]["crossSourceReview"]["status"], "active_parent_not_explicit_in_att")
        report = requirements.audit(doc, data)
        self.assertEqual(report["scope"]["guides"], 57)
        self.assertGreater(report["scope"]["withReportedEvidence"], 1800)
        self.assertGreater(report["scope"]["withoutReportedEvidence"], 0)
        self.assertTrue(report["limits"])


if __name__ == "__main__":
    unittest.main()
