"""Real tracker and map-button clicks must identify the intended current goal."""
import unittest

from test_duo_journey import primitive_copy
import test_quest_engine as fixtures


class TrackerMapTargetTests(unittest.TestCase):
    def setUp(self):
        fixtures.NavigationAndFullTocTests.setUp(self)
        self.host.state.mapID = 1431

    def visit(self, first=None, second=None):
        host = self.host
        host.guide("visit", steps=[{"title": "Villa Oscura", "goals": [
            first or {"t": "accept", "title": "Primer encargo", "quest": 81,
                      "npc": 901, "npcName": "Primer NPC", "map": 1431, "x": 24, "y": 30},
            second or {"t": "turnin", "title": "Segundo encargo", "quest": 82,
                       "npc": 902, "npcName": "Segundo NPC", "map": 1431, "x": 61.2, "y": 53.4},
        ]}])
        host.quest(82, onQuest=True, complete=True)
        host.initialize()
        host.call("SelectGuide", "visit")
        return primitive_copy(host.ns.char.progress)

    def click_second_row(self):
        row = next(row for row in self.host.ns.trackerRows.values()
                   if row.shown and row.goalIndex == 2 and not row.preview)
        row.scripts.OnClick(row, "LeftButton")

    def assert_pin(self, x, y):
        point = self.host.state.lastWaypoint
        self.assertIsNotNone(point)
        self.assertEqual(point.mapID, 1431)
        self.assertAlmostEqual(point.x, x)
        self.assertAlmostEqual(point.y, y)

    def test_clicking_a_distinct_actionable_row_pins_it_and_map_button_still_pins_current_goal(self):
        host = self.host
        before = self.visit()
        self.click_second_row()
        self.assert_pin(.612, .534)
        feedback = host.state.messages[len(host.state.messages)]
        self.assertIn("Segundo NPC", feedback)
        self.assertIn("61.2", feedback)
        self.assertIn("53.4", feedback)
        host.globals.Click(host.ns.trackerMap)
        self.assert_pin(.24, .3)
        self.assertEqual(primitive_copy(host.ns.char.progress), before)

    def test_selected_delivery_can_be_marked_after_a_service_without_coordinates(self):
        host = self.host
        before = self.visit(first={"t": "sethome", "title": "Fija tu hogar", "location": "Posada"})
        self.assertFalse(host.call("Navigate"))
        self.assertIsNone(host.state.lastWaypoint)
        self.click_second_row()
        self.assert_pin(.612, .534)
        self.assertEqual(primitive_copy(host.ns.char.progress), before)

    def test_unavailable_row_cannot_place_a_marker_on_another_goal(self):
        host = self.host
        before = self.visit(second={"t": "accept", "title": "Requiere otra misión", "quest": 83,
                                    "pre": [79], "map": 1431, "x": 61.2, "y": 53.4})
        host.call("Navigate", 2)
        self.assertEqual(host.state.waypointCalls, 0)
        self.assertIn("79", host.state.messages[len(host.state.messages)])
        host.call("Navigate", 37)
        self.assertEqual(host.state.waypointCalls, 0)
        self.assertEqual(primitive_copy(host.ns.char.progress), before)

    def test_map_can_show_destination_while_arrow_is_waiting_for_an_access_point(self):
        host = self.host
        before = self.visit()
        host.ns.Waypoints = host.lua.eval("{Resolve = function() return nil end}")
        _, step, _ = host.call("GetCurrent")
        self.assertIsNone(host.call("GetStepWaypoint", step))
        host.call("RefreshUI")
        self.assertTrue(host.ns.trackerMap.enabled)
        self.assertTrue(host.ns.mapButton.enabled)
        host.globals.Click(host.ns.trackerMap)
        self.assert_pin(.24, .30)
        self.assertIsNone(host.call("GetStepWaypoint", step))
        self.assertEqual(primitive_copy(host.ns.char.progress), before)

    def test_use_item_from_bags_explains_action_without_placing_a_marker(self):
        host = self.host
        before = self.visit(first={"quest": 80, "t": "accept", "title": "Carta misteriosa",
                                   "item": 721, "navigationMode": "inventory"})
        self.assertFalse(host.call("Navigate"))
        self.assertIn("bolsas", host.state.messages[len(host.state.messages)])
        self.assertIsNone(host.state.lastWaypoint)
        self.assertEqual(primitive_copy(host.ns.char.progress), before)

    def test_following_partner_does_not_mark_local_objective_or_edit_local_progress(self):
        host = self.host
        before = self.visit()
        host.ns.DuoAuto = host.lua.eval("""{
            GetSharedView = function() return {following=true, guideID="visit", sharedCursor=1} end,
            GetNavigationOverride = function() return {mapID=1431,x=.74,y=.46,source="duo-follow"} end,
        }""")
        host.call("Navigate", 2)
        self.assert_pin(.74, .46)
        self.assertEqual(primitive_copy(host.ns.char.progress), before)
