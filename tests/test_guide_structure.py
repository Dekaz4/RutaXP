"""Static route audit distinguishes source preservation, paths and manual work."""

import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_guide_structure import PIN, audit, dependency_cycles, events_for, scan_order


def guide(ident, goals, **metadata):
    return {"id": ident, "faction": "Alliance", "races": ["Human"],
            "steps": [{"title": "Visit", "goals": goals}], **metadata}


def scan(guides):
    return scan_order(guides, events_for(guides, {}))


class GuideStructureAuditTests(unittest.TestCase):
    def test_detects_work_before_accept_and_a_delivery_without_route_acceptance(self):
        result = scan([guide("g", [{"t": "complete", "quest": 1}, {"t": "accept", "quest": 1},
                                    {"t": "turnin", "quest": 1}, {"t": "turnin", "quest": 2}])])
        self.assertEqual(result["counts"]["work_before_accept"], 1)
        self.assertEqual(result["counts"]["turnin_without_accept"], 1)

    def test_cross_guide_carried_delivery_and_prerequisite_are_accounted_for(self):
        result = scan([guide("a", [{"t": "accept", "quest": 1}, {"t": "complete", "quest": 1}], next="b"),
                       guide("b", [{"t": "turnin", "quest": 1}, {"t": "accept", "quest": 2, "preAll": [1]},
                                   {"t": "turnin", "quest": 2}])])
        self.assertEqual(result["counts"]["turnin_without_accept"], 0)
        self.assertEqual(result["counts"]["prerequisite_not_in_prior_path"], 0)
        self.assertEqual(len(result["carriedTurnins"]), 1)
        self.assertEqual(result["carriedTurnins"][0]["acceptedAt"]["guideID"], "a")

    def test_alternative_incoming_routes_are_never_unioned_into_false_prerequisite_proof(self):
        result = scan([guide("root", [], nextChoices=["left", "right"]),
                       guide("left", [{"t": "accept", "quest": 1}, {"t": "turnin", "quest": 1}], next="join"),
                       guide("right", [{"t": "note", "text": "Another route"}], next="join"),
                       guide("join", [{"t": "accept", "quest": 2, "pre": [1]}, {"t": "turnin", "quest": 2}])])
        candidate = result["candidates"]["prerequisite_not_in_prior_path"][0]
        self.assertEqual(candidate["missing"], [1])
        self.assertEqual({s["path"] for s in candidate["modeledScenarios"]}, {2})

    def test_any_and_all_prerequisites_keep_different_meanings(self):
        prefix = [{"t": "accept", "quest": 1}, {"t": "turnin", "quest": 1}]
        suffix = [{"t": "accept", "quest": 3}, {"t": "turnin", "quest": 3}, {"t": "turnin", "quest": 2}]
        any_result = scan([guide("g", prefix + [{"t": "accept", "quest": 2, "pre": [1, 3]}] + suffix)])
        all_result = scan([guide("g", prefix + [{"t": "accept", "quest": 2, "preAll": [1, 3]}] + suffix)])
        self.assertEqual(any_result["counts"]["prerequisite_forward_local"], 0)
        self.assertEqual(all_result["counts"]["prerequisite_forward_local"], 1)

    def test_goal_and_step_conditions_do_not_mix_warrior_and_mage_branches(self):
        g = guide("g", [])
        for cls, q in [("WARRIOR", 1), ("MAGE", 2)]:
            g["steps"].append({"title": cls, "only": {"classes": [cls]}, "goals": [
                {"t": "accept", "quest": q}, {"t": "complete", "quest": q}, {"t": "turnin", "quest": q}]})
        self.assertTrue(all(v == 0 for v in scan([g])["counts"].values()))

    def test_source_notes_and_unbound_purchase_are_classified_without_changing_goals(self):
        g = guide("g", [{"t": "accept", "quest": 1}, {"t": "buy", "item": 99, "count": 3},
                        {"t": "turnin", "quest": 1}])
        document = {"guides": [g]}
        before = copy.deepcopy(document)
        result = audit(document, quest_records={1: {"title": "Supplies", "objectives": [
            {"type": "item", "id": 99, "count": 3}]}})
        case = result["workCoverage"]["cases"][0]
        self.assertEqual(case["classification"], "unbound_work_goal")
        self.assertEqual(case["unboundMatches"][0]["action"], "buy")
        self.assertEqual(document, before)

    def test_unknown_objective_id_cannot_match_every_unbound_goal(self):
        document = {"guides": [guide("g", [{"t": "accept", "quest": 1}, {"t": "note", "text": "A note"},
                                            {"t": "turnin", "quest": 1}])]}
        case = audit(document, quest_records={1: {"objectives": [{"type": "item"}]}})["workCoverage"]["cases"][0]
        self.assertEqual(case["classification"], "needs_manual_review")
        self.assertEqual(case["unboundMatches"], [])

    def test_item_start_and_courier_are_not_claimed_missing_work(self):
        document = {"guides": [guide("g", [{"t": "accept", "quest": 1, "item": 99}, {"t": "turnin", "quest": 1},
                                            {"t": "accept", "quest": 2}, {"t": "turnin", "quest": 2}])]}
        coverage = audit(document, quest_records={1: {"objectives": [{"type": "item", "id": 99}]},
                                                 2: {"objectives": []}})["workCoverage"]
        self.assertEqual(coverage["sourceQuestsWithoutObjectives"], 1)
        self.assertEqual(coverage["cases"][0]["classification"], "item_start_already_carried")

    def test_pinned_context_is_not_applied_to_a_different_source_revision(self):
        document = {"provenance": {"commit": "new-revision"}, "guides": [guide("g", [
            {"t": "accept", "quest": 91772}, {"t": "turnin", "quest": 91772}])]}
        records = {91772: {"objectives": [{"type": "object", "id": 563442}]}}
        self.assertEqual(audit(document, quest_records=records)["workCoverage"]["cases"][0]["classification"],
                         "needs_manual_review")
        document["provenance"]["commit"] = PIN
        self.assertEqual(audit(document, quest_records=records)["workCoverage"]["cases"][0]["classification"],
                         "optional_travel_clicks_in_context")

    def test_closed_branch_is_a_candidate_not_a_false_structural_proof_of_completion(self):
        result = scan([guide("g", [{"t": "accept", "quest": 1}, {"t": "accept", "quest": 2, "closedBy": [1]},
                                    {"t": "turnin", "quest": 2}, {"t": "turnin", "quest": 1}])])
        self.assertEqual(result["counts"]["ordered_closed_branch"], 1)
        self.assertEqual(result["candidates"]["ordered_closed_branch"][0]["closedBy"], [1])

    def test_dependency_and_next_cycles_are_explicit_candidates(self):
        guides = [guide("a", [{"t": "accept", "quest": 1, "pre": [2]}], next="b"),
                  guide("b", [{"t": "accept", "quest": 2, "preAll": [1]}], next="a")]
        self.assertEqual(dependency_cycles(events_for(guides, {})), [[1, 2]])
        self.assertTrue(scan(guides)["guideLinkCycles"])

    def test_shipped_report_covers_all_guides_and_keeps_the_48_work_cases_explicit(self):
        report = json.loads((ROOT / "RutaXP/Source/guide_structure.json").read_text(encoding="utf-8"))
        self.assertEqual((report["scope"]["guides"], report["scope"]["steps"], report["scope"]["goals"]), (57, 2342, 7446))
        self.assertEqual(report["sourceComparison"]["structuralDifferences"], [])
        comparison = report["sourceComparison"]
        revisions = json.loads((ROOT / "RutaXP/Source/guide_revisions.json").read_text(encoding="utf-8"))["revisions"]
        self.assertEqual(len(revisions), 44)
        self.assertEqual([r["id"] for r in revisions[:7]],
                         ["westfall-alba-mines-2", "westfall-engineering-3", "zephras-alliance-service-2",
                          "redridge-alther-bridge-2", "mulgore-malah-centaurs-2", "tirisfal-rear-guard-2",
                          "silverpine-quinn-potions-2"])
        self.assertEqual([entry["id"] for entry in comparison["reviewedCorrections"]],
                         [r["id"] for r in revisions])
        self.assertTrue(comparison["rawStructuralDifferences"])
        self.assertEqual({entry["guideID"] for entry in comparison["rawStructuralDifferences"]},
                         {r["guideID"] for r in revisions})
        expected_actions = dict(report["scope"]["sourceDslActions"])
        expected_actions["collect"] -= 1
        expected_actions["complete"] += 2
        expected_actions["goto"] -= 1
        expected_actions["note"] -= 1
        for action, count in {"accept": 3, "collect": 2, "kill": 3, "turnin": 3}.items():
            expected_actions[action] += count
        # The human rogue chain adds two starts, two rewards and one collection.
        # The second mandatory copy of the Duskwood collection was retired.
        expected_actions["accept"] += 2
        expected_actions["turnin"] += 2
        # Each faction retired the three unverified Alonso pickups and hand-ins.
        expected_actions["accept"] -= 6
        expected_actions["turnin"] -= 6
        self.assertEqual(report["scope"]["actions"], expected_actions)
        coverage = report["workCoverage"]
        self.assertEqual(coverage["sourceQuestsWithObjectives"], 48)
        self.assertEqual(coverage["unknownQuestIDs"], [])
        self.assertNotIn("needs_manual_review", coverage["classifications"])
        cases = {case["questID"]: case for case in coverage["cases"]}
        self.assertEqual(cases[4492]["classification"], "codex_route_disagreement")
        self.assertNotIn(5321, cases)
        self.assertTrue(all(case["occurrences"] and case["explanation"] for case in cases.values()))
        self.assertTrue(report["limits"])


if __name__ == "__main__":
    unittest.main()
