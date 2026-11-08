"""Hub order and prerequisites on the human rogue's Darkshore and Redridge circuit."""
import json
from pathlib import Path
import unittest


CATALOG = Path(__file__).resolve().parents[1] / "RutaXP/Source/leveling.json"
GUIDES = {g["id"]: g for g in json.loads(CATALOG.read_text(encoding="utf8"))["guides"]}
DARK = GUIDES["forever/alliance/03-darkshore"]
RED = GUIDES["forever/alliance/04-redridge-mountains"]


class HumanMidEfficiencyTests(unittest.TestCase):
    def test_auberdine_continuations_use_the_same_stop_as_their_prerequisite(self):
        goals = DARK["steps"][20]["goals"]
        for parent, child in [(4762, 4763), (985, 986)]:
            with self.subTest(quest=child):
                i = next(i for i, goal in enumerate(goals)
                         if goal["t"] == "turnin" and goal.get("quest") == parent)
                self.assertEqual((goals[i + 1]["t"], goals[i + 1]["quest"], goals[i + 1]["npc"]),
                                 ("accept", child, goals[i]["npc"]))
                self.assertIn(parent, goals[i + 1]["pre"])

    def test_stormwind_finishes_baros_before_rogue_trainer_and_shaw(self):
        first = RED["steps"][0]["goals"]
        self.assertEqual([(g["t"], g.get("quest")) for g in first],
                         [("turnin", 97914), ("accept", 97926), ("vendor", None), ("train", None)])
        trainer = next(c for c in first[-1]["candidates"]
                       if c["map"] == 1453 and "ROGUE" in c.get("classes", []))
        shaw = next(g for g in RED["steps"][2]["goals"] if g.get("quest") == 2360)
        self.assertEqual((trainer["npc"], shaw["npc"]), (918, 332))
        self.assertEqual(shaw["only"]["classes"], ["ROGUE"])

    def test_south_shore_deliveries_precede_the_western_hunt_and_garden(self):
        visits = RED["steps"]
        feldon_olento = visits[9]["goals"]
        self.assertEqual([(g["t"], g["quest"]) for g in feldon_olento],
                         [("turnin", 246), ("turnin", 98407), ("turnin", 89), ("accept", 98386)])
        self.assertIn(89, feldon_olento[-1]["pre"])
        self.assertEqual([(g["t"], g["quest"], g["item"]) for g in visits[10]["goals"]],
                         [("collect", 34, 3631)])
        martie, poster = visits[11]["goals"]
        self.assertEqual((martie["t"], martie["quest"], poster["t"], poster["quest"], poster["minLevel"]),
                         ("turnin", 34, "accept", 180, 21))


if __name__ == "__main__":
    unittest.main()
