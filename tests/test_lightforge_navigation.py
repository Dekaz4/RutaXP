"""The shipped Lightforge chain must navigate to an actionable quest target."""
import unittest

from test_access_navigation import AccessHost


GUIDE = "forever/alliance/07-thousand-needles"


def visit(action, quest):
    h = AccessHost(GUIDE, x=.1058, y=.6059, find_goal={"t": action, "quest": quest})
    h.s.level = 28
    h.h.lua.execute("C_QuestLog.GetNextWaypoint=nil; C_QuestLog.GetQuestsOnMap=nil")
    return h


def find(h, action, quest):
    matches = [(step, index, goal) for step in h.guide.steps.values()
               for index, goal in step.goals.items() if goal.t == action and goal.quest == quest]
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one {action} {quest}, got {len(matches)}")
    return matches[0]


def status(h, action, quest):
    step, index, goal = find(h, action, quest)
    return h.ns.GetGoalStatus(h.ns, goal, step, h.ns.char.progress[GUIDE], index, h.guide)[0]


class LightforgeNavigationTests(unittest.TestCase):
    def test_holding_lightforge_iron_selects_the_chest_before_glorins_followup(self):
        h = visit("accept", 321)
        h.s.quests[321] = h.h.table({"onQuest": True, "complete": False})
        before = h.progress()
        goal, _, goal_status, _ = h.ns.GetActiveGoal(h.ns)
        self.assertEqual((goal.t, goal.quest, goal.object, goal_status), ("turnin", 321, 2734, "active"))
        point = h.point()
        self.assertEqual(point.mapID, 1437)
        self.assertAlmostEqual(point.x, .1211)
        self.assertAlmostEqual(point.y, .6419)
        self.assertEqual(status(h, "accept", 526), "blocked")
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 321))
        self.assertEqual(h.progress(), before)

    def test_missing_prerequisite_does_not_pin_glorin_or_mark_any_quest_finished(self):
        h = visit("accept", 526)
        # The early branch applies only after this character has started it.
        # Delivery of 270 does not itself satisfy 526's direct prerequisite 321.
        h.s.quests[270] = h.h.table({"delivered": True})
        before = h.progress()
        goal, index, goal_status, _ = h.ns.GetActiveGoal(h.ns)
        self.assertEqual((goal.quest, goal_status), (526, "blocked"))
        self.assertIsNone(h.point())
        h.ns.Navigate(h.ns, index)
        self.assertEqual(h.s.waypointCalls, 0)
        self.assertIsNone(h.s.lastWaypoint)
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 321))
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 526))
        self.assertEqual(h.progress(), before)

    def test_a_fresh_character_with_only_the_first_letter_is_not_sent_to_the_chest(self):
        h = visit("accept", 321)
        h.s.quests[269] = h.h.table({"onQuest": True, "complete": True})
        before = h.progress()
        for action, quest in (("accept", 321), ("turnin", 321), ("accept", 324),
                              ("collect", 324), ("turnin", 324), ("accept", 526),
                              ("collect", 526), ("turnin", 526)):
            with self.subTest(action=action, quest=quest):
                self.assertEqual(status(h, action, quest), "skip")
                self.assertFalse(h.ns.IsQuestDelivered(h.ns, quest))
        self.assertIsNone(h.ns.GetActiveGoal(h.ns))
        self.assertIsNone(h.point())
        h.ns.Navigate(h.ns)
        self.assertEqual(h.s.waypointCalls, 0)
        self.assertIsNone(h.s.lastWaypoint)
        self.assertEqual(h.ns.char.activeGuide, GUIDE)
        self.assertEqual(h.progress(), before)

    def test_manually_omitting_iron_delivery_does_not_unlock_the_followups(self):
        h = visit("turnin", 321)
        _, index, _ = find(h, "turnin", 321)
        h.ns.ToggleGoalConfirm(h.ns, index)
        self.assertEqual(status(h, "turnin", 321), "skip")
        self.assertEqual(status(h, "accept", 324), "blocked")
        self.assertEqual(status(h, "accept", 526), "blocked")
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 321))
        self.assertIsNone(h.point())

        # The actual game event, not the omission, opens the next quest.
        h.s.quests[321] = h.h.table({"onQuest": False, "delivered": True})
        h.h.g.EmitAddonEvent("QUEST_TURNED_IN", 321)
        self.assertTrue(h.ns.IsQuestDelivered(h.ns, 321))
        goal, _, goal_status, _ = h.ns.GetActiveGoal(h.ns)
        self.assertEqual((goal.t, goal.quest, goal.object, goal_status), ("accept", 324, 2734, "active"))
        self.assertAlmostEqual(h.point().x, .1211)
        self.assertAlmostEqual(h.point().y, .6419)

    def test_chest_branch_keeps_its_collection_and_excludes_glorins_alternative(self):
        h = visit("collect", 324)
        before = h.progress()
        goal, _, goal_status, _ = h.ns.GetActiveGoal(h.ns)
        self.assertEqual((goal.t, goal.quest, goal.item, goal_status), ("collect", 324, 2702, "active"))
        self.assertEqual(status(h, "accept", 526), "skip")
        self.assertEqual(status(h, "collect", 526), "skip")
        self.assertEqual(status(h, "turnin", 526), "skip")
        point = h.point()
        self.assertEqual(point.mapID, 1437)
        self.assertAlmostEqual(point.x, goal.x / 100)
        self.assertAlmostEqual(point.y, goal.y / 100)
        self.assertNotAlmostEqual(point.x, .1058)
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 324))
        self.assertFalse(h.ns.IsQuestDelivered(h.ns, 526))
        self.assertEqual(h.progress(), before)


if __name__ == "__main__":
    unittest.main()
