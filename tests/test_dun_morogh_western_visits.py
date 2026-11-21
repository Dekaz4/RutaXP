"""Playable order and saved positions for the gnome's Dun Morogh visits."""
import json
from pathlib import Path
import unittest


class DunMoroghVisitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / "RutaXP/Source/leveling.json"
        guides = json.loads(source.read_text(encoding="utf-8"))["guides"]
        cls.guide = next(g for g in guides if g["id"] == "forever/alliance/dwarf-gnome/01-dun-morogh")

    def locate(self, action, quest):
        found = [(si, gi, goal) for si, step in enumerate(self.guide["steps"], 1)
                 for gi, goal in enumerate(step["goals"], 1)
                 if goal["t"] == action and goal.get("quest") == quest]
        self.assertEqual(len(found), 1)
        return found[0]

    def test_timed_delivery_and_follow_up_share_one_visit_before_leaving_anvilmar(self):
        drink = self.locate("turnin", 3364)
        mug = self.locate("accept", 3365)
        imp = self.locate("turnin", 1599)
        felix = self.locate("turnin", 3361)
        self.assertEqual((drink[0], drink[1] + 1, drink[2]["npc"]), (mug[0], mug[1], mug[2]["npc"]))
        self.assertEqual({v[0] for v in (drink, mug, imp, felix)}, {drink[0]})
        self.assertLess(mug[1], imp[1])
        self.assertLess(imp[1], felix[1])

    def test_macgrann_visits_are_together_between_western_village_and_eastern_depot(self):
        village = self.locate("turnin", 315)[0]
        meat = [self.locate(action, 312) for action in ("accept", "complete", "turnin")]
        depot = self.locate("accept", 96408)[0]
        self.assertEqual([(row[0], row[1]) for row in meat], [(village + 1, i) for i in (1, 2, 3)])
        self.assertEqual(depot, village + 2)

    def test_saved_marks_and_pending_meat_visit_survive_reordering(self):
        migration = next(m for m in self.guide["progressMigrations"] if m["from"] == 3)
        meat_step = self.locate("accept", 312)[0]
        self.assertEqual(migration["stepMap"]["68"], meat_step)
        self.assertEqual(migration["stepMap"]["81"], 81)
        for old_step in range(57, 69):
            self.assertLessEqual(migration["stepMap"][str(old_step)], meat_step)
        for old_key, target in (("68:3", self.locate("turnin", 312)), ("12:2", self.locate("turnin", 3361))):
            self.assertEqual(migration["goalMap"][old_key], f"{target[0]}:{target[1]}")
