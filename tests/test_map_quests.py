"""Quest pins on the viewed map reflect the journal without placing waypoints."""
import unittest

import test_quest_engine as fixtures
from test_addon import ADDON


class MapQuestPointsTests(unittest.TestCase):
    def setUp(self):
        fixtures.NavigationAndFullTocTests.setUp(self)
        h = self.host
        h.load((ADDON / "MapQuests.lua").read_text(encoding="utf8"), "RutaXP", h.ns)
        def goal(action, quest, **fields):
            return {"t": action, "quest": quest, "map": 1436, "x": 40, "y": 20, "f": "e",
                    "title": f"Misión {quest}", **fields}
        h.guide("zone", steps=[
            {"title": "Parada", "goals": [goal("accept", 10), goal("accept", 11, pre=[12]),
                goal("accept", 13, only={"classes": ["ROGUE"]})]},
            {"title": "Trabajo", "goals": [goal("kill", 10, oi=1), goal("accept", 14, npc=77)]},
            {"title": "Vuelta", "goals": [goal("turnin", 10, npcName="Alba"), goal("turnin", 10, npcName="Alba"),
                goal("accept", 15), goal("accept", 16, map=1429)]}])
        h.initialize()
        h.call("SelectGuide", "zone")
        h.ns.GetProgress = h.lua.eval("function() error('Map inspection requested mutable progress') end")
        h.globals.C_Map.SetUserWaypoint = h.lua.eval("function() error('Map inspection set a waypoint') end")

    def points(self, map_id=1436):
        rows = self.host.call("GetMapQuestPoints", map_id)
        return [rows[i] for i in range(1, len(rows) + 1)]

    def test_new_quest_to_done_by_objective_to_delivered(self):
        h = self.host
        initial = self.points()
        self.assertEqual([(p.questID, p.category) for p in initial], [(10, "accept")])
        self.assertAlmostEqual(initial[0].x, .40)
        self.assertAlmostEqual(initial[0].y, .20)
        self.assertTrue(initial[0].name)
        h.quest(10, onQuest=True)
        self.assertEqual([p.category for p in self.points()], ["objective"])
        h.quest(10, onQuest=True, objectives=[{"finished": True}], complete=False)
        self.assertEqual(self.points(), [])
        h.quest(10, onQuest=True, complete=True)
        self.assertEqual([(p.category, p.detail) for p in self.points()], [("turnin", "Alba")])
        h.quest(10, onQuest=False, delivered=True)
        self.assertEqual(self.points(), [])
        self.assertEqual(self.points(1429), [])
        self.assertEqual(h.ns.char.progress.zone.cursor, 1)

    def test_skips_and_authorized_next_pickups(self):
        h = self.host
        h.ns.char.progress.zone.skipped = h.table({"1:1": True})
        h.ns.GetPlannedPickupAtNPC = h.lua.eval("function(self,id,npc,map) return id==14 and npc==77 and map==1436 end")
        self.assertEqual([(p.questID, p.category) for p in self.points()], [(14, "accept")])

    def test_candidates_on_browsed_map_filter_objective_faction_and_class(self):
        h = self.host
        h.quest(10, onQuest=True, objectives=[{"finished": False}, {"finished": True}])
        goal = h.ns.guides.zone.steps[2].goals[1]
        goal.map, goal.x, goal.y = None, None, None
        goal.candidates = h.table([
            {"map": 1429, "x": 20, "y": 70, "objectiveIndex": 1, "npcName": "Aquí"},
            {"map": 1429, "x": 40, "y": 70, "objectiveIndex": 2},
            {"map": 1429, "x": 60, "y": 70, "faction": "H"},
            {"map": 1429, "x": 80, "y": 70, "classes": ["ROGUE"]}])
        self.assertEqual(self.points(), [])
        self.assertEqual([(p.category, p.detail, p.x) for p in self.points(1429)], [("objective", "Aquí", .2)])
