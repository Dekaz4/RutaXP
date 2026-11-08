"""Check the playable order of the human rogue's early leveling circuit."""
import json
from pathlib import Path
import unittest

from test_quest_engine import QuestEngineHost


ELWYNN = "forever/alliance/human/01-elwynn-forest"
WESTFALL = "forever/alliance/02-westfall"


class HumanStartingCircuitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        filename = Path(__file__).resolve().parents[1] / "RutaXP/Source/leveling.json"
        catalog = json.loads(filename.read_text(encoding="utf-8"))
        cls.catalog = {g["id"]: g for g in catalog["guides"]}

    def locate(self, guide, action, quest, **fields):
        matches = [(si, gi, goal)
                   for si, step in enumerate(self.catalog[guide]["steps"], 1)
                   for gi, goal in enumerate(step["goals"], 1)
                   if goal["t"] == action and goal.get("quest") == quest
                   and all(goal.get(k) == v for k, v in fields.items())]
        self.assertEqual(len(matches), 1, (guide, action, quest, fields))
        return matches[0]

    def test_mcbride_gives_all_available_orders_before_leaving(self):
        for accepted, destination, npc in ((15, 3102, 915), (21, 91743, 951), (54, 91758, 248415)):
            with self.subTest(accepted=accepted):
                si, gi, _ = self.locate(ELWYNN, "accept", accepted, npc=197)
                carrier, target, _ = self.locate(ELWYNN, "turnin", destination, npc=npc)
                self.assertEqual(si, carrier)
                self.assertLess(gi, target)

    def test_boar_hunt_and_thomas_report_are_part_of_their_local_loop(self):
        blood = self.locate(ELWYNN, "collect", 99130, item=286215)[0]
        meat = self.locate(ELWYNN, "collect", 86, item=769)[0]
        self.assertEqual(blood, meat)
        for quest in (99130, 86):
            self.assertLess(self.locate(ELWYNN, "accept", quest)[0], meat)
        self.assertGreater(self.locate(ELWYNN, "accept", 88)[0], meat)
        after_lake = self.locate(ELWYNN, "turnin", 71, npc=261)[0]
        self.assertLess(self.locate(ELWYNN, "accept", 71)[0], after_lake)
        self.assertLess(after_lake, self.locate(ELWYNN, "collect", 91725)[0])
        self.assertLess(after_lake, self.locate(ELWYNN, "complete", 76)[0])

    def test_westfall_goes_to_the_coast_then_collects_ozwins_job_before_molsen(self):
        tower = self.locate(WESTFALL, "accept", 102)[0:2]
        flight_master = self.locate(WESTFALL, "turnin", 6181)[0:2]
        stew = self.locate(WESTFALL, "accept", 38)[0:2]
        coast = self.locate(WESTFALL, "collect", 38, item=730)[0:2]
        ozwin = self.locate(WESTFALL, "accept", 92909)[0:2]
        reaper = self.locate(WESTFALL, "collect", 92909, item=255007)[0:2]
        well = self.locate(WESTFALL, "collect", 92742, item=254547)[0:2]
        alba = self.locate(WESTFALL, "turnin", 92742)[0:2]
        expected = [tower, flight_master, stew, coast, ozwin, well, reaper, alba]
        self.assertEqual(expected, sorted(expected))

    def test_dagger_chain_uses_the_class_quest_givers_and_pickpocket_target(self):
        order = [(2205, "accept"), (2205, "turnin"), (2206, "accept"), (2206, "collect"), (2206, "turnin")]
        rows = [self.locate(ELWYNN, action, quest) for quest, action in order]
        self.assertEqual([r[:2] for r in rows], sorted(r[:2] for r in rows))
        keryn, delivery, accept, theft, reward = [r[2] for r in rows]
        self.assertEqual((keryn["npc"], keryn["map"], keryn["minLevel"]), (917, 1429, 10))
        for at_shaw in (delivery, accept, reward):
            self.assertEqual((at_shaw["npc"], at_shaw["map"], at_shaw["x"], at_shaw["y"]),
                             (332, 1453, 78.31, 70.74))
            self.assertNotIn("f", at_shaw)  # Coordinates were measured in the live Stormwind frame.
        self.assertEqual(accept["pre"], [2205])
        self.assertEqual((theft["item"], theft["oi"], theft["fromKind"], theft["map"]),
                         (7675, 1, "pickpocket", 1429))
        self.assertIn("Robar", theft["note"])
        self.assertIn(7298, [item["item"] for item in reward["rewards"]["items"]])

        host = QuestEngineHost()
        host.group([keryn, delivery, accept, theft, reward])
        host.initialize()
        for race, cls in (("Human", "WARRIOR"), ("Dwarf", "ROGUE")):
            host.state.raceToken, host.state.classToken = race, cls
            for _, _, goal in rows:
                self.assertEqual(host.status(goal), "skip")
        host.state.raceToken, host.state.classToken = "Human", "ROGUE"
        host.state.level = 9
        self.assertEqual(host.status(keryn), "blocked")
        host.state.level = 10
        self.assertEqual(host.status(keryn), "active")
        self.assertEqual(host.status(accept), "blocked")
        host.quest(2205, delivered=True)
        self.assertEqual(host.status(accept), "active")


if __name__ == "__main__":
    unittest.main()
