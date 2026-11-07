"""Costa Oscura chains retain prerequisites, arrival points and personal branches."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

from test_quest_engine import QuestEngineHost

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP/Source"
DARK = "forever/alliance/03-darkshore"
ASHENVALE = "forever/alliance/06-ashenvale"
BEACHED = [4722, 4723, 4725, 4727, 4728, 4730, 4731, 4732, 4733]


class DarkshoreContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((SOURCE / "leveling.json").read_text(encoding="utf8"))
        cls.guide = next(g for g in cls.document["guides"] if g["id"] == DARK)
        cls.goals = [(si, gi, q) for si, s in enumerate(cls.guide["steps"], 1)
                     for gi, q in enumerate(s["goals"], 1)]

    def goal(self, action, quest):
        return next((si, gi, q) for si, gi, q in self.goals if q.get("quest") == quest and q["t"] == action)

    def host(self):
        h = QuestEngineHost(catalog=True)
        h.initialize()
        h.ns.char.auto = False
        h.call("SelectGuide", DARK)
        return h

    def test_buzzboxes_keep_complete_delivery_acceptance_order_and_actual_box_destinations(self):
        expected = [(983, 1001, 2, 17182, 36.64, 46.26),
                    (1001, 1002, 9, 17183, 41.96, 28.62),
                    (1002, 1003, 10, 17184, 51.29, 24.57)]
        for parent, child, step, obj, x, y in expected:
            delivered, accepted = self.goal("turnin", parent), self.goal("accept", child)
            self.assertLess(delivered[:2], accepted[:2])
            self.assertEqual(delivered[0], step)
            self.assertEqual(accepted[2]["pre"], [parent])
            for _, _, goal in (delivered, accepted):
                self.assertEqual((goal["object"], goal["map"], goal["x"], goal["y"]), (obj, 1439, x, y))
        self.assertLess(self.goal("collect", 1003)[:2], self.goal("turnin", 1003)[:2])

    def test_holy_diver_requires_all_beached_quests_before_the_later_northern_excursion(self):
        accepted, work, handed = self.goal("accept", 87760), self.goal("collect", 87760), self.goal("turnin", 87760)
        self.assertEqual((accepted[:2], work[:2], handed[:2]), ((33, 5), (34, 5), (37, 4)))
        self.assertEqual(accepted[2]["preAll"], BEACHED)
        for quest in BEACHED:
            self.assertLess(self.goal("turnin", quest)[:2], accepted[:2])
        self.assertEqual((work[2]["map"], work[2]["x"], work[2]["y"], work[2]["item"]),
                         (1439, 50.41, 14.27, 280686))
        self.assertEqual(accepted[2]["npc"], handed[2]["npc"])

    def test_eight_deliveries_or_a_complete_ninth_do_not_unlock_holy_diver(self):
        h = self.host()
        h.globals.UnitLevel = h.lua.eval("function() return 20 end")
        state = h.call("GetProgress", DARK)
        state.cursor = 33
        step = h.ns.guides[DARK].steps[33]
        for quest in BEACHED[:-1]:
            h.quest(quest, delivered=True)
        h.quest(BEACHED[-1], onQuest=True, complete=True)
        self.assertEqual(h.status(step.goals[5], step, state, 5), "blocked")
        h.quest(BEACHED[-1], delivered=True)
        self.assertEqual(h.status(step.goals[5], step, state, 5), "active")
        h.quest(BEACHED[0], delivered=False)
        h.quest(87760, onQuest=True, complete=False)
        self.assertEqual(h.status(step.goals[5], step, state, 5), "done")

    def test_arbal_offers_his_quest_after_return_to_onu_is_handed_in(self):
        parent = self.goal("turnin", 950)
        visit, index, accepted = self.goal("accept", 98013)
        delivery = self.goal("turnin", 98013)
        self.assertEqual(parent[0], visit)
        self.assertLess(parent[1], index)
        self.assertEqual(accepted["preAll"], [950])
        for goal in (accepted, delivery[2]):
            self.assertEqual((goal["npc"], goal["map"], goal["x"], goal["y"]),
                             (270269, 1439, 43.71, 76.49))
        kills = [(si, gi, goal) for si, gi, goal in self.goals
                 if goal.get("quest") == 98013 and goal["t"] == "kill"]
        self.assertEqual([(q["npc"], q["count"]) for _, _, q in kills],
                         [(2181, 12), (2182, 8), (2183, 6)])
        for si, gi, _ in kills:
            self.assertLess((visit, index), (si, gi))
            self.assertLess((si, gi), delivery[:2])
        h = self.host()
        h.globals.UnitLevel = h.lua.eval("function() return 20 end")
        state = h.call("GetProgress", DARK)
        state.cursor = visit
        step = h.ns.guides[DARK].steps[visit]
        h.quest(950, onQuest=True, complete=True)
        self.assertEqual(h.status(step.goals[index], step, state, index), "blocked")
        h.quest(950, delivered=True)
        self.assertEqual(h.status(step.goals[index], step, state, index), "active")

    def test_kerlonian_escort_starts_at_its_giver_and_runs_straight_to_delivery(self):
        self.assertFalse(any(q.get("quest") == 5321 for _, _, q in self.goals))
        guide = next(g for g in self.document["guides"] if g["id"] == ASHENVALE)
        goals = [q for step in guide["steps"] for q in step["goals"]]
        indices = [i for i, q in enumerate(goals) if q.get("quest") == 5321]
        self.assertEqual(indices, list(range(indices[0], indices[0] + 3)))
        accepted, escort, delivery = (goals[i] for i in indices)
        self.assertEqual([q["t"] for q in (accepted, escort, delivery)], ["accept", "complete", "turnin"])
        self.assertEqual((accepted["npc"], accepted["map"], accepted["x"], accepted["y"], accepted["minLevel"]),
                         (11218, 1439, 44.4, 76.43, 17))
        self.assertEqual((escort["map"], escort["x"], escort["y"]), (1439, 41.8, 90.2))
        self.assertNotIn("oi", escort)
        self.assertIn("cuerno", escort["instruction"].lower())
        self.assertEqual((delivery["npc"], delivery["map"], delivery["x"], delivery["y"]),
                         (11219, 1440, 27.26, 35.58))
        h = self.host()
        h.call("SelectGuide", ASHENVALE)
        state = h.call("GetProgress", ASHENVALE)
        state.cursor = 5
        step = h.ns.guides[ASHENVALE].steps[5]
        h.globals.UnitLevel = h.lua.eval("function() return 16 end")
        self.assertEqual(h.status(step.goals[1], step, state, 1), "blocked")
        h.globals.UnitLevel = h.lua.eval("function() return 17 end")
        self.assertEqual(h.status(step.goals[1], step, state, 1), "active")
        h.quest(5321, onQuest=True, complete=False)
        self.assertEqual(h.status(step.goals[2], step, state, 2), "active")
        h.quest(5321, onQuest=True, complete=True)
        self.assertEqual(h.status(step.goals[2], step, state, 2), "done")

    def test_pier_is_in_darkshore_and_all_moonglade_travel_is_personal_druid_work(self):
        goal = self.guide["steps"][36]["goals"][5]
        self.assertEqual((goal["t"], goal["map"], goal["x"], goal["y"], goal["f"]),
                         ("goto", 1439, 32.4, 43.8, "e"))
        for step in self.guide["steps"]:
            for q in step["goals"]:
                if q.get("map") == 1450:
                    conditions = q.get("only", step.get("only", {}))
                    self.assertIn("DRUID", conditions.get("classes", step.get("only", {}).get("classes", [])))

    def test_optional_fishing_learning_is_not_blocked_by_an_unverified_profession_gate(self):
        for _, _, goal in self.goals:
            if goal.get("quest") == 1141:
                self.assertTrue(goal["optional"])
                self.assertNotIn("profLine", goal)
                self.assertNotIn("requiresSkill", goal)
        h = self.host()
        h.ns.char.optional = True
        h.globals.UnitLevel = h.lua.eval("function() return 16 end")
        state = h.call("GetProgress", DARK)
        state.cursor = 1
        step = h.ns.guides[DARK].steps[1]
        self.assertEqual(h.status(step.goals[8], step, state, 8), "active")

    def test_jai_vhanel_minimum_level_is_fifteen_and_active_journal_takes_precedence(self):
        self.assertEqual(self.goal("accept", 98025)[2]["minLevel"], 15)
        h = self.host()
        h.globals.UnitLevel = h.lua.eval("function() return 14 end")
        state = h.call("GetProgress", DARK)
        state.cursor = 1
        step = h.ns.guides[DARK].steps[1]
        self.assertEqual(h.status(step.goals[5], step, state, 5), "blocked")
        h.quest(98025, onQuest=True)
        self.assertEqual(h.status(step.goals[5], step, state, 5), "done")

    def test_navigation_overlay_changes_only_the_reviewed_pier_map_and_is_idempotent(self):
        spec = importlib.util.spec_from_file_location("darkshore_builder", SOURCE / "build_guides.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        document = copy.deepcopy(self.document)
        guide = next(g for g in document["guides"] if g["id"] == DARK)
        pier = guide["steps"][36]["goals"][5]
        pier["map"] = 1450
        before = copy.deepcopy(pier)
        builder.apply_guide_overrides(document, SOURCE / "guide_overrides.json")
        self.assertEqual(pier, dict(before, map=1439))
        after = copy.deepcopy(document)
        builder.apply_guide_overrides(document, SOURCE / "guide_overrides.json")
        self.assertEqual(document, after)


if __name__ == "__main__":
    unittest.main()
