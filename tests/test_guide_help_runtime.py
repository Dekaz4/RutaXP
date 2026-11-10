"""Instructions reach the tracker and navigation without completing a quest."""
import unittest

import test_quest_engine as fixtures


class GuideInstructionRuntimeTests(unittest.TestCase):
    def fixture(self, goal, **step_fields):
        host = fixtures.QuestEngineHost()
        host.group([goal], **step_fields)
        if goal.get("quest"):
            host.quest(goal["quest"], onQuest=True, objectives=[{"text": "Pendiente: 0/1", "finished": False}])
        host.initialize()
        return host

    def test_current_row_keeps_live_counts_and_moves_long_context_to_details(self):
        h = self.fixture({"t": "complete", "quest": 100,
                          "instruction": "Usa el objeto junto a la hoguera."},
                         note="Siéntate junto al fuego antes de usarlo.")
        _, step, state = h.call("GetCurrent")
        row = h.call("GetStepGoalItems", step, state)[0][1]
        self.assertIn("Pendiente: 0/1", row.subtitle)
        self.assertNotIn("Usa el objeto", row.subtitle)
        self.assertNotIn("Siéntate junto al fuego", row.subtitle)
        self.assertIn("Usa el objeto", row.details)
        self.assertIn("Siéntate junto al fuego", row.details)
        self.assertEqual(state.cursor, 1)
        self.assertIsNone(state.confirmed["1:1"])

    def test_authored_text_is_visible_even_without_a_generated_instruction(self):
        h = self.fixture({"t": "interact", "quest": 100, "text": "Lanza Leer línea Ley junto a la piedra."})
        _, step, state = h.call("GetCurrent")
        row = h.call("GetStepGoalItems", step, state)[0][1]
        self.assertIn("Lanza Leer línea Ley", row.subtitle)
        self.assertIn("Lanza Leer línea Ley", h.call("GetObjectives", step))

    def test_taming_presentation_does_not_change_the_quest_action(self):
        h = self.fixture({"t": "kill", "quest": 100, "instructionVerb": "Domestica",
                          "instruction": "Usa la fusta para domesticar la bestia."})
        _, step, state = h.call("GetCurrent")
        self.assertTrue(h.call("GetGoalTitle", step.goals[1]).startswith("Domestica:"))
        self.assertEqual(step.goals[1].t, "kill")
        self.assertEqual(h.status(step.goals[1]), "active")
        self.assertEqual(state.cursor, 1)

    def test_an_informational_note_is_kept_with_the_current_quest(self):
        h = fixtures.QuestEngineHost()
        h.group([{"t": "complete", "quest": 100, "instruction": "Escolta al personaje."},
                 {"t": "note", "text": "Quédate cerca y protégele hasta que salga de la fortaleza."}])
        h.quest(100, onQuest=True)
        h.initialize()
        _, step, state = h.call("GetCurrent")
        row = h.call("GetStepGoalItems", step, state)[0][1]
        self.assertNotIn("Quédate cerca", row.subtitle or "")
        self.assertIn("Quédate cerca", row.details)
        self.assertEqual(state.cursor, 1)


class GuideLocationRuntimeTests(unittest.TestCase):
    def setUp(self):
        fixtures.NavigationAndFullTocTests.setUp(self)

    def test_completed_objective_locations_are_not_the_next_arrow_target(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, .5, .5
        h.quest(100, onQuest=True, objectives=[{"finished": True}, {"finished": False}])
        goal = h.table({"t": "complete", "quest": 100, "candidates": [
            {"npc": 1, "objectiveIndex": 1, "map": 1436, "x": 50, "y": 50},
            {"object": 2, "objectiveIndex": 2, "map": 1436, "x": 60, "y": 50},
        ]})
        self.assertEqual(h.call("GetGoalWaypoint", goal).candidate.object, 2)
        self.assertIsNone(goal.oi)

    def test_unknown_objective_state_keeps_its_sourced_location_available(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, .5, .5
        h.lua.execute("C_QuestLog.GetQuestObjectives=function() return nil end")
        goal = h.table({"t": "complete", "quest": 100, "candidates": [
            {"npc": 1, "objectiveIndex": 1, "map": 1436, "x": 50, "y": 50},
        ]})
        self.assertEqual(h.call("GetGoalWaypoint", goal).candidate.npc, 1)

    def test_an_escort_does_not_point_back_to_its_static_start(self):
        h = self.host
        goal = h.table({"t": "complete", "quest": 100, "navigationMode": "escort",
                        "candidates": [{"npc": 1, "map": 1436, "x": 50, "y": 50}]})
        self.assertIsNone(h.call("GetGoalWaypoint", goal))

    def test_a_mixed_quest_switches_from_gathering_to_its_inventory_action(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, .5, .5
        h.quest(100, onQuest=True, objectives=[{"finished": False}, {"finished": False}])
        goal = h.table({"t": "complete", "quest": 100, "navigationMode": "inventory",
                        "candidates": [{"npc": 1, "objectiveIndex": 1, "map": 1436, "x": 50, "y": 50}]})
        self.assertEqual(h.call("GetGoalWaypoint", goal).candidate.npc, 1)
        h.quest(100, onQuest=True, objectives=[{"finished": True}, {"finished": False}])
        h.lua.execute("C_QuestLog.GetNextWaypoint=function() return 1436,.9,.9 end")
        self.assertIsNone(h.call("GetGoalWaypoint", goal))
        self.assertIsNone(goal.oi)

    def test_bag_item_and_other_actions_without_a_fixed_place_explain_the_action(self):
        for goal, message in [({"t": "accept", "quest": 200, "item": 300}, "bolsas"),
                              ({"t": "hearth", "location": "Posada"}, "piedra de hogar"),
                              ({"t": "level", "level": 60}, "experiencia"),
                              ({"t": "note", "text": "Descansa"}, "Indicaciones")]:
            with self.subTest(action=goal["t"]):
                h = self.host
                h.guide("no-fixed-" + goal["t"], steps=[{"title": "Acción sin punto fijo", "goals": [goal]}])
                h.initialize()
                h.call("SelectGuide", "no-fixed-" + goal["t"])
                h.call("UpdateNavigation")
                self.assertIn(message, h.ns.navigationFrame.statusText)
                self.assertEqual(h.ns.navigationFrame.distance.text, "")
                self.assertFalse(h.ns.navigationFrame.arrow.shown)


if __name__ == "__main__":
    unittest.main()
