"""A real boat replaces the old note without inheriting its manual progress."""
import copy
import json
import unittest

import test_guide_additions as additions
from test_westfall_migration import MigrationHost


GUIDE = "forever/alliance/07-thousand-needles"
DESOLACE = "forever/alliance/30-40/02-desolace"
SOURCE, builder = additions.SOURCE, additions.builder


def shipping_boat():
    document = json.loads((SOURCE / "leveling.json").read_text(encoding="utf8"))
    guide = next(g for g in document["guides"] if g["id"] == GUIDE)
    return guide, next(goal for goal in guide["steps"][30]["goals"] if goal["t"] == "boat")


class BoatGuideDataTests(unittest.TestCase):
    def test_desolace_landing_precedes_thundris_and_the_astranaar_flight_in_existing_saves(self):
        for cursor in (2, 3, 22):
            with self.subTest(cursor=cursor):
                saved = {"seen": True, "auto": False, "activeGuide": DESOLACE, "progress": {
                    DESOLACE: {"cursor": cursor, "routeRevision": 2, "placed": True,
                               "skipped": {"2:1": True}, "confirmed": {"2:2": True}}}}
                host = MigrationHost(saved)
                host.state.level = 33
                host.initialize()
                guide = host.ns.guides[DESOLACE]
                state = host.ns.char.progress[DESOLACE]
                self.assertEqual((state.cursor, state.routeRevision), (cursor, 3))
                self.assertTrue(state.skipped["2:2"])
                self.assertTrue(state.confirmed["2:3"])
                self.assertIsNone(state.skipped["2:1"])
                self.assertIsNone(state.confirmed["2:1"])
                boat, thundris, flight = [guide.steps[2].goals[i] for i in (1, 2, 3)]
                self.assertEqual((boat.t, boat.departure.map, boat.departure.x, boat.departure.y),
                                 ("boat", 1437, 4.49, 56.66))
                self.assertEqual((boat.stopover.name, boat.stopover.map, boat.stopover.x, boat.stopover.y),
                                 ("Costasur", 1424, 50.67, 70.44))
                self.assertEqual((boat.arrivalDock.map, boat.arrivalDock.x, boat.arrivalDock.y),
                                 (1439, 32.34, 44.13))
                self.assertEqual((boat.visitQuest, thundris.t, thundris.quest, thundris.npc),
                                 (98209, "turnin", 98209, 3649))
                self.assertEqual((flight.t, flight.location, flight.requiredTravel), ("fly", "Astranaar", True))
                self.assertIn("Quédate a bordo en Costasur", boat.instruction)

    def test_optional_boat_data_must_describe_distinct_ports_and_valid_land_on_the_arrival_map(self):
        revisions = json.loads((SOURCE / "guide_revisions.json").read_bytes())["revisions"]
        reviewed = next(r for r in revisions if r["id"] == "desolace-menethil-auberdine-boat-3")
        for field, replacement in (
            ("stopover", {"map": 1437, "x": 50, "y": 70, "f": "e", "name": "Costasur"}),
            ("stopover", {"map": 1424, "x": 50, "y": 70, "f": "e", "name": ""}),
            ("arrivalAlternatives", [{"map": 1437, "x": 9.5, "y": 59.6, "f": "e"}]),
            ("visitQuest", True),
        ):
            with self.subTest(field=field, value=replacement):
                revision = copy.deepcopy(reviewed)
                revision["addedGoals"]["barco_auberdine"]["goal"][field] = replacement
                with self.assertRaises(ValueError):
                    builder.reviewed_additions(revision)

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
        self.assertEqual((len(guide["steps"]), len(guide["steps"][30]["goals"])), (37, 4))
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
                boat = next(goal for goal in changed["steps"][30]["goals"] if goal["t"] == "boat")
                boat[field]["x"] += 1
                self.assertNotEqual(builder.route_shape(changed), original)

    def test_old_note_mark_is_archived_without_completing_the_boat(self):
        for field in ("confirmed", "skipped"):
            with self.subTest(field=field):
                saved = {"seen": True, "auto": False, "activeGuide": GUIDE, "progress": {GUIDE: {
                    "cursor": 31, "routeRevision": 4, "placed": True, "review": True,
                    "confirmed": {"31:1": True}, "skipped": {"31:2": True}}}}
                saved["progress"][GUIDE][field]["31:3"] = True
                h = MigrationHost(saved, {98223: {"delivered": True}})
                h.state.level = 30
                h.initialize()
                state = h.ns.char.progress[GUIDE]
                self.assertEqual(state.cursor, 31)
                self.assertEqual(state.routeRevision, h.ns.guides[GUIDE].routeRevision)
                self.assertTrue(state.confirmed["31:1"])
                self.assertTrue(state.skipped["31:3"])
                self.assertIsNone(state.confirmed["31:4"])
                self.assertIsNone(state.skipped["31:4"])
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
