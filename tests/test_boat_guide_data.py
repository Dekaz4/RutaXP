"""A real boat replaces the old note without inheriting its manual progress."""
import copy
import json
import unittest

import test_guide_additions as additions
from test_westfall_migration import MigrationHost


GUIDE = "forever/alliance/07-thousand-needles"
SOURCE, builder = additions.SOURCE, additions.builder


def shipping_boat():
    document = json.loads((SOURCE / "leveling.json").read_text(encoding="utf8"))
    guide = next(g for g in document["guides"] if g["id"] == GUIDE)
    return guide, guide["steps"][30]["goals"][2]


class BoatGuideDataTests(unittest.TestCase):
    def revision_fixture(self):
        case = additions.ReviewedAdditionsTests()
        guide, result, revision = case.fixture()
        _, boat = shipping_boat()
        boat = copy.deepcopy(boat)
        revision["addedGoals"]["followup"]["goal"] = boat
        result["steps"][0]["goals"][2] = copy.deepcopy(boat)
        revision["resultShape"] = builder.route_shape(result)
        return case, guide, result, revision

    def test_reviewed_transport_is_a_nonquest_action_with_a_distinct_land_arrival(self):
        guide, boat = shipping_boat()
        self.assertEqual((len(guide["steps"]), len(guide["steps"][30]["goals"])), (37, 3))
        self.assertEqual(boat["t"], "boat")
        self.assertNotIn("quest", boat)
        self.assertNotIn("questID", boat)
        self.assertEqual((boat["map"], boat["x"], boat["y"]), (1437, 4.74, 63.76))
        self.assertEqual((boat["departureLand"]["map"], boat["departureLand"]["x"], boat["departureLand"]["y"],
                          boat["departureLand"]["radius"]), (1437, 9.52, 59.66, 80))
        self.assertEqual((boat["arrivalDock"]["map"], boat["arrivalDock"]["x"], boat["arrivalDock"]["y"]),
                         (1445, 71.73, 56.66))
        self.assertEqual((boat["arrival"]["map"], boat["arrival"]["x"], boat["arrival"]["y"], boat["arrival"]["radius"]),
                         (1445, 67.46, 51.2, 25))
        self.assertIn("barco", boat["instruction"])
        self.assertIn("tierra firme", boat["instruction"])
        case, original, expected, revision = self.revision_fixture()
        self.assertEqual(case.apply(original, revision)["guides"][0]["steps"], expected["steps"])

    def test_unreviewed_or_malformed_transport_cannot_enter_the_catalog(self):
        for problem in ("no-evidence", "fake-quest", "missing-arrival", "missing-dock", "bad-map", "bad-radius",
                        "nan-coordinate", "wrong-pin", "different-arrival-map", "same-zone", "bad-departure-land",
                        "wrong-departure-land-map"):
            with self.subTest(problem=problem):
                _, _, _, revision = self.revision_fixture()
                added = revision["addedGoals"]["followup"]
                boat = added["goal"]
                if problem == "no-evidence": added.pop("evidence")
                elif problem == "fake-quest": boat["quest"] = 123
                elif problem == "missing-arrival": boat.pop("arrival")
                elif problem == "missing-dock": boat.pop("arrivalDock")
                elif problem == "bad-map": boat["arrival"]["map"] = True
                elif problem == "bad-radius": boat["arrival"]["radius"] = 0
                elif problem == "nan-coordinate": boat["departure"]["x"] = float("nan")
                elif problem == "wrong-pin": boat["x"] = 8
                elif problem == "different-arrival-map": boat["arrivalDock"]["map"] = 1437
                elif problem == "bad-departure-land": boat["departureLand"]["radius"] = 0
                elif problem == "wrong-departure-land-map": boat["departureLand"]["map"] = 1445
                else: boat["departure"]["map"] = boat["arrival"]["map"]
                with self.assertRaises(ValueError):
                    builder.reviewed_additions(revision)

    def test_changed_transport_endpoint_is_a_semantic_route_change(self):
        guide, _ = shipping_boat()
        original = builder.route_shape(guide)
        for field in ("arrival", "departure", "departureLand", "arrivalDock"):
            with self.subTest(field=field):
                changed = copy.deepcopy(guide)
                changed["steps"][30]["goals"][2][field]["x"] += 1
                self.assertNotEqual(builder.route_shape(changed), original)

    def test_old_note_mark_is_archived_without_completing_the_boat(self):
        for field in ("confirmed", "skipped"):
            with self.subTest(field=field):
                saved = {"seen": True, "auto": False, "activeGuide": GUIDE, "progress": {GUIDE: {
                    "cursor": 31, "routeRevision": 4, "placed": True, "review": True,
                    "confirmed": {"31:1": True}, "skipped": {"31:2": True}}}}
                saved["progress"][GUIDE][field]["31:3"] = True
                h = MigrationHost(saved)
                h.state.level = 30
                h.initialize()
                state = h.ns.char.progress[GUIDE]
                self.assertEqual(state.cursor, 31)
                self.assertEqual(state.routeRevision, 5)
                self.assertTrue(state.confirmed["31:1"])
                self.assertTrue(state.skipped["31:2"])
                self.assertIsNone(state.confirmed["31:3"])
                self.assertIsNone(state.skipped["31:3"])
                self.assertTrue(h.ns.char.guideMigrationBackups[GUIDE + ":5"].progress[field]["31:3"])

    def test_completed_chapter_remains_complete(self):
        h = MigrationHost({"seen": True, "auto": False, "activeGuide": GUIDE,
                           "progress": {GUIDE: {"cursor": 38, "routeRevision": 4, "placed": True}}})
        h.state.level = 30
        h.initialize()
        self.assertEqual(h.ns.char.progress[GUIDE].cursor, 38)
        self.assertIsNone(h.ns.char.progress[GUIDE].requirementsRepair)


if __name__ == "__main__":
    unittest.main()
