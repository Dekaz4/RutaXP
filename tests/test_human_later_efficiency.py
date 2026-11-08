"""Regression cases for the Alliance route from Duskwood through Silithus."""
import json
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "RutaXP" / "Source"


class LaterAllianceEfficiencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        guides = json.loads((SOURCE / "leveling.json").read_text(encoding="utf8"))["guides"]
        cls.guides = {g["id"]: g for g in guides}

    def step(self, suffix, index):
        return self.guides["forever/alliance/" + suffix]["steps"][index - 1]

    def test_duskwood_collects_the_same_ten_fingers_only_once_at_raven_hill(self):
        chapter = self.guides["forever/alliance/05-duskwood"]
        self.assertIn("dedos", chapter["steps"][2]["note"])
        matches = [(si, q) for si, s in enumerate(chapter["steps"], 1) for q in s["goals"]
                   if q.get("quest") == 101 and q.get("oi") == 3 and q["t"] == "collect"]
        self.assertEqual(len(matches), 1)
        step, goal = matches[0]
        self.assertEqual((step, goal["item"], goal["count"]), (7, 2378, 10))
        fiend = next(q for q in chapter["steps"][step - 1]["goals"] if q.get("npc") == 531)
        for field in ("map", "x", "y", "spots", "f"):
            self.assertEqual(goal[field], fiend[field], field)
        self.assertTrue(all(spot["x"] < 30 for spot in goal["spots"]))
        self.assertTrue(any(q.get("quest") == 101 and q["t"] == "turnin"
                            for s in chapter["steps"][step:] for q in s["goals"]))

    def test_rogue_gets_key_before_opening_chest_and_buys_cure_after_acceptance(self):
        tower = self.step("05-duskwood", 26)
        doctor = self.step("05-duskwood", 27)
        self.assertEqual(tower["only"], {"classes": ["ROGUE"]})
        self.assertEqual(doctor["only"], tower["only"])
        key, journal = tower["goals"][2:]
        self.assertEqual((key["item"], key["fromKind"], journal["item"]), (7923, "pickpocket", 7908))
        self.assertIn("Robar", key["instruction"])
        self.assertNotIn("botín", key["instruction"])
        self.assertIn("cofre", journal["note"])
        errands = doctor["goals"][6:]
        self.assertEqual([(q["t"], q.get("item")) for q in errands], [
            ("accept", None), ("buy", 3421), ("buy", 3372),
            ("collect", 8431), ("buy", 4371), ("turnin", None)])
        self.assertTrue(all(q.get("optional") for q in errands))
        self.assertEqual((errands[0]["quest"], errands[-1]["quest"]), (2609, 2609))

    def test_returning_to_a_giver_keeps_prerequisites_and_optional_items_honest(self):
        prospector = self.step("30-40/01-hillsbrad-foothills", 41)["goals"]
        self.assertEqual([q.get("quest") for q in prospector], [514, 525, 98313, 1453, 98300, None])
        self.assertEqual(prospector[1]["pre"], [514])
        self.assertEqual(prospector[0]["npc"], prospector[1]["npc"])
        books = self.step("06-ashenvale", 61)["goals"]
        self.assertEqual((books[2]["quest"], books[3]["quest"]), (343, 337))
        self.assertEqual(books[2]["npc"], books[3]["npc"])
        self.assertTrue(books[3]["optional"])
        delivery = self.step("07-thousand-needles", 36)["goals"]
        self.assertEqual([q["quest"] for q in delivery[:3]], [1105, 1104, 1106])
        self.assertEqual(set(delivery[2]["preAll"]), {1104, 1105})
        donations = self.step("50-60/05-silithus", 19)["goals"]
        self.assertEqual(donations[-1]["quest"], 7261)
        self.assertEqual([q["quest"] for q in donations[5:7]], [4512, 4513])
