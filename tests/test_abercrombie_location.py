"""The hermit's recorded Forever position works before this player has visited him."""
import unittest

from test_access_navigation import AccessHost


class AbercrombieLocationTests(unittest.TestCase):
    def test_every_visit_to_the_hermit_survives_unavailable_era_projection(self):
        h = AccessHost("forever/alliance/05-duskwood", 21, 1, x=.746, y=.472)
        h.h.lua.execute("""
            C_Map.GetMapPosFromWorldPos = nil
            C_Map.GetWorldPosFromMapPos = nil
            C_QuestLog.GetNextWaypoint = nil
            C_QuestLog.GetQuestsOnMap = nil
        """)
        self.assertEqual((h.step.goals[1].quest, h.step.goals[2].quest), (159, 133))
        visits = [goal for guide in h.ns.guides.values() for step in guide.steps.values()
                  for goal in step.goals.values() if goal.npc == 289 and goal.map == 1431]
        self.assertEqual(len(visits), 10)
        for goal in visits:
            point = h.ns.GetGoalWaypoint(h.ns, goal)
            self.assertEqual(point.mapID, 1431)
            self.assertAlmostEqual(point.x, .2797)
            self.assertAlmostEqual(point.y, .3153)
            self.assertEqual(point.source, "guide")
        h.s.quests[159] = h.h.table({"onQuest": True, "complete": True})
        before = h.progress()
        h.ns.RefreshUI(h.ns)
        self.assertTrue(h.ns.trackerMap.enabled)
        h.ns.trackerRows[1].scripts.OnClick(h.ns.trackerRows[1], "LeftButton")
        self.assertEqual(h.s.lastWaypoint.mapID, 1431)
        self.assertAlmostEqual(h.s.lastWaypoint.x, .2797)
        self.assertAlmostEqual(h.s.lastWaypoint.y, .3153)
        self.assertIn("Abercrombie", h.s.messages[len(h.s.messages)])
        self.assertEqual(h.progress(), before)


if __name__ == "__main__":
    unittest.main()
