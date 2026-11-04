"""Navigation enrichment follows objective/service evidence without quest edits."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("guide_coordinates", ROOT / "tools/guide_coordinates.py")
coords = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coords)


class Reference:
    def __init__(self, records=None, events=None, travel=None):
        self.records = records or {}
        self.events = events or {}
        self.travel = travel or {}
        self.files = {"fixture.lua": "fixture", "addon/SendaFH_QuestDB/Quests.lua": "events",
                      "addon/SendaFH/Nav/TravelData.lua": "travel"}

    def get(self, kind, ident):
        return self.records.get((kind, ident), {})

    def event_points(self, qid):
        return self.events.get(qid, [])

    def evidence(self, kind, ident):
        return {"sourceFile": "fixture.lua", "sourceSha256": "fixture"}


def document(goals, faction="Alliance"):
    return {"provenance": {"commit": "test"}, "guides": [
        {"id": "test-route", "faction": faction, "steps": [{"goals": goals}]}]}


class CoordinateProposalTests(unittest.TestCase):
    def test_quest_turnin_is_not_used_as_the_place_to_complete_an_unlocated_event(self):
        doc = document([{"t": "complete", "quest": 10},
                        {"t": "turnin", "quest": 10, "npc": 99, "map": 1426, "x": 50, "y": 50}])
        reference = Reference({("quest", 10): {"objectives": [{"type": "event", "text": "An undocumented event"}], "end": {"npc": [99]}}})
        result = coords.propose(doc, reference)
        self.assertEqual(len(result["unresolved"]), 1)
        self.assertNotIn("candidates", result["patches"][0]["set"])

    def test_friendly_npc_credit_retains_complete_and_explicit_live_frame(self):
        doc = document([{"t": "complete", "quest": 10, "only": {"classes": ["PRIEST"]}}])
        before = copy.deepcopy(doc)
        reference = Reference({("quest", 10): {"objectives": [{"type": "kill", "id": 1699}]},
                               ("npc", 1699): {"name": "Gremlock", "faction": "H", "spawns": [{"map": 1426, "x": 47.7, "y": 52.3}]}})
        patch = coords.propose(doc, reference)["patches"][0]
        self.assertEqual(patch["match"]["t"], "complete")
        self.assertEqual(patch["match"]["only"], {"classes": ["PRIEST"]})
        point = patch["set"]["candidates"][0]
        self.assertEqual(point["f"], "l")
        self.assertEqual(point["npc"], 1699)
        self.assertEqual(point["objectiveIndex"], 1)
        self.assertNotIn("faction", point, "Hostile quest targets cannot be filtered as a player allegiance")
        self.assertEqual(doc, before)

    def test_event_point_preserves_objective_index_and_era_frame(self):
        reference = Reference({("quest", 10): {"objectives": [{"type": "event"}]}},
                              {10: [(1, {"map": 1420, "x": 60.7, "y": 51.9, "f": "e"})]})
        result = coords.propose(document([{"t": "complete", "quest": 10}]), reference)
        point = result["patches"][0]["set"]["candidates"][0]
        self.assertEqual((point["objectiveIndex"], point["f"]), (1, "e"))
        self.assertEqual(result["patches"][0]["evidence"][0]["kind"], "quest-event")
        self.assertEqual(result["unresolved"], [])

    def test_partial_coverage_keeps_unknown_objectives_and_never_uses_spawnless_credit(self):
        reference = Reference({("quest", 10): {"objectives": [{"type": "kill", "id": 1}, {"type": "kill", "id": 2}]},
                               ("npc", 1): {"name": "Target", "spawns": [{"map": 1426, "x": 30, "y": 40, "f": "e"}]},
                               ("npc", 2): {"name": "DNT Invisible Credit", "spawns": []}})
        result = coords.propose(document([{"t": "complete", "quest": 10}]), reference)
        self.assertEqual(result["statistics"]["outcomes"]["partial"], 1)
        self.assertEqual(result["unresolved"][0]["unknownObjectives"][0]["objectiveIndex"], 2)
        self.assertEqual(len(result["patches"][0]["set"]["candidates"]), 1)

    def test_item_objective_uses_its_documented_object_source(self):
        reference = Reference({("quest", 10): {"objectives": [{"type": "item", "id": 20}]},
                               ("item", 20): {"sources": [{"type": "object", "object": 30}]},
                               ("object", 30): {"name": "Chest", "spawns": [{"map": 1426, "x": 30, "y": 40, "f": "e"}]}})
        patch = coords.propose(document([{"t": "complete", "quest": 10}]), reference)["patches"][0]
        self.assertEqual(patch["set"]["candidates"][0]["object"], 30)
        self.assertEqual(patch["evidence"][0]["via"]["itemID"], 20)

    def test_sethome_selects_the_inn_area_for_the_characters_faction(self):
        inns = [{"area": 1, "npc": 7, "map": 1426, "x": 40, "y": 50, "f": "e"},
                {"area": 1, "npc": 8, "map": 1426, "x": 50, "y": 60, "f": "e"}]
        reference = Reference({("npc", 7): {"faction": "A"}, ("npc", 8): {"faction": "H"}}, travel={"inns": inns})
        patch = coords.propose(document([{"t": "sethome", "area": 1}]), reference)["patches"][0]
        self.assertEqual([p["npc"] for p in patch["set"]["candidates"]], [7])

    def test_fly_targets_an_explicit_connected_origin_and_preserves_node_class_condition(self):
        taxi = [[1, 0, 0, 0, 1426, 10, 20, 1, "Origin"], [2, 0, 0, 0, 1455, 30, 40, 1, "Destination"]]
        doc = document([{"t": "getfp", "node": 1, "only": {"classes": ["DRUID"]}},
                        {"t": "getfp", "node": 2, "area": 100, "location": "Destination"},
                        {"t": "fly", "area": 100, "location": "Destination", "from": 1}])
        reference = Reference(travel={"taxi": taxi, "flights": [1, 2, 10]})
        patch = coords.propose(doc, reference)["patches"][-1]
        points = patch["set"]["candidates"]
        self.assertEqual([p["flightNode"] for p in points], [1])
        self.assertEqual(points[0]["classes"], ["DRUID"])
        self.assertEqual(points[0]["navigationRole"], "flight-origin")

    def test_legitimate_non_location_actions_and_authored_points_are_preserved(self):
        goals = [{"t": "accept", "quest": 10, "item": 20}, {"t": "hearth", "area": 1},
                 {"t": "level", "level": 5}, {"t": "note", "text": "Follow the instructions"},
                 {"t": "complete", "quest": 11, "map": 1426, "x": 1, "y": 2, "z": 3, "f": "e"}]
        doc = document(goals)
        before = copy.deepcopy(doc)
        result = coords.propose(doc, Reference())
        self.assertEqual(result["patches"], [])
        self.assertEqual(result["unresolved"], [])
        self.assertEqual(doc, before)

    def test_regeneration_removes_only_identical_previous_overlay_values(self):
        raw = document([{"t": "complete", "quest": 10}])
        reference = Reference({("quest", 10): {"objectives": [{"type": "event"}]}},
                              {10: [(1, {"map": 1426, "x": 20, "y": 30, "f": "e"})]})
        overlay = coords.propose(raw, reference)
        applied = copy.deepcopy(raw)
        applied["guides"][0]["steps"][0]["goals"][0].update(copy.deepcopy(overlay["patches"][0]["set"]))
        baseline = coords.without_applied_overlay(applied, overlay)
        self.assertEqual(baseline, raw)
        self.assertEqual(coords.propose(baseline, reference), overlay)
        applied["guides"][0]["steps"][0]["goals"][0]["navigationHint"] = "A deliberate manual edit"
        with self.assertRaisesRegex(ValueError, "edited after"):
            coords.without_applied_overlay(applied, overlay)


class ShippingCoordinateOverlayTests(unittest.TestCase):
    def test_every_added_point_has_frame_objective_and_pinned_evidence(self):
        overlay = json.loads((ROOT / "RutaXP/Source/guide_locations.json").read_text(encoding="utf-8"))
        self.assertEqual(overlay["unresolved"], [])
        self.assertEqual(len(overlay["patches"]), 433)
        for patch in overlay["patches"]:
            self.assertLessEqual(set(patch["set"]), {"candidates", "navigationHint", "navigationMode"})
            points = patch["set"].get("candidates", [])
            proofs = {e.get("candidateIndex") for e in patch["evidence"] if e.get("candidateIndex")}
            self.assertEqual(proofs, set(range(1, len(points) + 1)), patch["id"])
            for point in points:
                self.assertIn(point["f"], {"e", "l"})
                self.assertTrue(coords.located(point))
                if patch["match"]["t"] == "complete":
                    self.assertGreater(point["objectiveIndex"], 0)
            for proof in patch["evidence"]:
                self.assertEqual(proof["sourceSha256"], overlay["sourceFiles"][proof["sourceFile"]])
        mixed = next(p for p in overlay["patches"] if p["match"].get("quest") == 1046)
        self.assertEqual(mixed["set"]["navigationMode"], "inventory")
        self.assertTrue(mixed["set"]["candidates"])
        self.assertEqual({p["objectiveIndex"] for p in mixed["set"]["candidates"]}, {1})


if __name__ == "__main__":
    unittest.main()
