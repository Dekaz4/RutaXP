"""Semantic coverage for the grouped leveling-guide engine, in real Lua 5.1.

Fixtures are small authored quest scenarios. Shipping catalog checks also load
the original compiled source, when present, to protect route ordering.
"""

from pathlib import Path
import unittest

from test_addon import ADDON, ROOT, AddonHost


CHARACTER_STUBS = r"""
TEST.classToken = "WARRIOR"
TEST.raceToken = "Human"
function UnitClass() return "Guerrero", TEST.classToken, TEST.classID or 1 end
function UnitRace() return "Raza localizada", TEST.raceToken, TEST.raceID or 1 end
"""


class QuestEngineHost(AddonHost):
    def __init__(self, catalog=False):
        self.leveling_catalog = catalog
        super().__init__()

    def new_namespace(self):
        self.lua.execute(CHARACTER_STUBS)
        self.ns = self.lua.table()
        for name in ["Core.lua", "QuestEngine.lua"]:
            self.load((ADDON / name).read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        if self.leveling_catalog:
            for name in ["Leveling.lua", "MapFrames.lua"]:
                self.load((ADDON / name).read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        self.globals.InstallFakeUI(self.ns)
        return self.ns

    def group(self, goals, id="grouped", next_goals=None, **step_fields):
        first = {"title": "Quest hub", "goals": goals, **step_fields}
        steps = [first]
        if next_goals is not None:
            steps.append({"title": "Next destination", "goals": next_goals})
        self.guide(id, steps=steps)
        return self.ns.guides[id]

    def status(self, goal, step=None, state=None, index=1):
        if isinstance(goal, dict):
            goal = self.table(goal)
        if step is None:
            _, step, current_state = self.call("GetCurrent")
            state = state or current_state
        result = self.call("GetGoalStatus", goal, step, state, index)
        return result[0] if isinstance(result, tuple) else result

    def active(self):
        result = self.call("GetActiveGoal")
        return result if isinstance(result, tuple) else (result,)


class GroupedGoalTests(unittest.TestCase):
    def setUp(self):
        self.host = QuestEngineHost()
        self.host.group([
            {"t": "accept", "quest": 100, "title": "Pick up quest"},
            {"t": "complete", "quest": 100, "title": "Do quest"},
            {"t": "turnin", "quest": 100, "title": "Deliver quest"},
        ], next_goals=[{"t": "note", "text": "Read the next destination"}])
        self.host.initialize()

    def test_accept_objectives_and_delivery_cause_separate_goal_transitions(self):
        h = self.host
        self.assertEqual(h.active()[1], 1)
        self.assertEqual(h.cursor("grouped"), 1)
        h.quest(100, onQuest=True)
        h.fire("QUEST_ACCEPTED", 100)
        self.assertEqual(h.active()[1], 2)
        self.assertEqual(h.cursor("grouped"), 1)
        h.quest(100, onQuest=True, complete=True)
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(h.active()[1], 3)
        self.assertEqual(h.cursor("grouped"), 1)
        h.fire("QUEST_TURNED_IN", 100)
        self.assertEqual(h.cursor("grouped"), 2)

    def test_acceptance_does_not_complete_the_whole_group(self):
        h = self.host
        h.quest(100, onQuest=True)
        h.call("Sync")
        guide, step, state = h.call("GetCurrent")
        self.assertEqual(state.cursor, 1)
        self.assertEqual(h.status(step.goals[1]), "done")
        self.assertEqual(h.status(step.goals[2]), "active")
        self.assertEqual(h.status(step.goals[3]), "active")

    def test_specific_objectives_are_independent_and_do_not_imply_delivery(self):
        h = self.host
        h.group([
            {"t": "complete", "quest": 200, "oi": 1, "title": "First objective"},
            {"t": "complete", "quest": 200, "oi": 2, "title": "Second objective"},
            {"t": "turnin", "quest": 200, "title": "Delivery"},
        ], id="objectives")
        h.quest(200, onQuest=True, complete=False, objectives=[
            {"text": "One", "finished": True}, {"text": "Two", "finished": False}
        ])
        h.call("SelectGuide", "objectives")
        self.assertEqual(h.active()[1], 2)
        h.quest(200, onQuest=True, complete=True, objectives=[
            {"text": "One", "finished": True}, {"text": "Two", "finished": True}
        ])
        h.call("Sync")
        self.assertEqual(h.active()[1], 3)
        self.assertEqual(h.cursor("objectives"), 1)

    def test_next_confirms_only_one_pending_goal_per_click(self):
        h = self.host
        h.call("Next")
        self.assertEqual(h.cursor("grouped"), 1)
        self.assertEqual(h.active()[1], 2)
        state = h.call("GetProgress", "grouped")
        self.assertTrue(state.skipped["1:1"])
        self.assertIsNone(state.confirmed["1:1"])
        self.assertIsNone(state.confirmed["1:2"])
        h.call("Next")
        self.assertEqual(h.cursor("grouped"), 1)
        self.assertEqual(h.active()[1], 3)
        h.call("Next")
        self.assertEqual(h.cursor("grouped"), 2)
        self.assertTrue(state.skipped["1:3"])

    def test_auto_disabled_keeps_current_step_after_all_goals_finish(self):
        h = self.host
        h.ns.char.auto = False
        h.quest(100, delivered=True)
        h.call("Sync")
        self.assertEqual(h.cursor("grouped"), 1)
        h.call("Next")
        self.assertEqual(h.cursor("grouped"), 2)

    def test_manual_service_never_autocompletes_because_quest_is_done(self):
        h = self.host
        h.group([
            {"t": "turnin", "quest": 300, "title": "Deliver"},
            {"t": "train", "title": "Train your class abilities"},
            {"t": "vendor", "title": "Sell junk and restock"},
        ], id="services")
        h.quest(300, delivered=True)
        h.call("SelectGuide", "services")
        self.assertEqual(h.active()[1], 2)
        self.assertEqual(h.active()[2], "manual")
        h.call("Next")
        self.assertEqual(h.cursor("services"), 1)
        self.assertEqual(h.active()[1], 3)
        h.call("Next")
        self.assertEqual(h.cursor("services"), 2)

    def test_blocked_prerequisite_does_not_silently_skip_a_quest_or_group(self):
        h = self.host
        h.group([{"t": "accept", "quest": 400, "pre": [399], "title": "Locked quest"}], id="locked")
        h.call("SelectGuide", "locked")
        self.assertEqual(h.active()[2], "blocked")
        self.assertEqual(h.cursor("locked"), 1)
        h.quest(399, delivered=True)
        h.call("Sync")
        self.assertEqual(h.active()[2], "active")
        self.assertEqual(h.cursor("locked"), 1)

    def test_prerequisite_or_and_and_are_both_enforced(self):
        h = self.host
        goal = {"t": "accept", "quest": 400, "pre": [10, 11], "preAll": [12, 13]}
        self.assertEqual(h.status(goal), "blocked")
        h.quest(11, delivered=True)
        h.quest(12, delivered=True)
        self.assertEqual(h.status(goal), "blocked")
        h.quest(13, delivered=True)
        self.assertEqual(h.status(goal), "active")

    def test_accepting_a_quest_bypasses_stale_prerequisite_block(self):
        h = self.host
        h.quest(400, onQuest=True)
        self.assertEqual(h.status({"t": "accept", "quest": 400, "pre": [399]}), "done")

    def test_closedby_skips_only_when_an_alternative_is_active_or_delivered(self):
        h = self.host
        goal = {"t": "accept", "quest": 400, "closedBy": [401, 402]}
        self.assertEqual(h.status(goal), "active")
        h.quest(402, onQuest=True)
        self.assertEqual(h.status(goal), "skip")
        h.quest(402, delivered=True)
        self.assertEqual(h.status(goal), "skip")

    def test_optional_goals_skip_by_default_but_active_quests_remain(self):
        h = self.host
        self.assertFalse(bool(h.ns.char.optional))
        goal = {"t": "complete", "quest": 500, "optional": True}
        self.assertEqual(h.status(goal), "skip")
        h.quest(500, onQuest=True)
        self.assertEqual(h.status(goal), "active")
        h.quest(500)
        h.ns.char.optional = True
        self.assertEqual(h.status(goal), "active")

    def test_group_level_conditions_skip_entire_inapplicable_step(self):
        h = self.host
        h.group([{"t": "train", "title": "Mage training"}], id="mage-only",
                only={"classes": ["MAGE"]}, next_goals=[{"t": "vendor", "title": "General supplies"}])
        h.call("SelectGuide", "mage-only")
        self.assertEqual(h.cursor("mage-only"), 2)

    def test_skipped_goal_and_done_goal_can_advance_but_manual_cannot(self):
        h = self.host
        h.group([
            {"t": "accept", "quest": 600, "only": {"classes": ["MAGE"]}},
            {"t": "accept", "quest": 601},
            {"t": "train", "title": "Training"},
        ], id="mixed")
        h.quest(601, onQuest=True)
        h.call("SelectGuide", "mixed")
        self.assertEqual(h.cursor("mixed"), 1)
        self.assertEqual(h.active()[1], 3)
        h.call("Next")
        self.assertEqual(h.cursor("mixed"), 2)

    def test_confirmation_is_per_step_guide_and_character_and_survives_reload(self):
        h = self.host
        h.call("Next")
        h.group([{"t": "train", "title": "Other service"}], id="other")
        h.call("SelectGuide", "other")
        self.assertIsNone(h.call("GetProgress", "other").confirmed["1:1"])
        first_character = h.ns.char
        h.globals.RutaXPCharDB = h.lua.table()
        h.new_namespace()
        h.group([{"t": "train", "title": "Other service"}], id="grouped")
        h.initialize()
        self.assertIsNone(h.call("GetProgress", "grouped").confirmed["1:1"])
        h.globals.RutaXPCharDB = first_character
        h.new_namespace()
        h.group([
            {"t": "accept", "quest": 100}, {"t": "complete", "quest": 100}, {"t": "turnin", "quest": 100}
        ], id="grouped")
        h.initialize()
        h.call("SelectGuide", "grouped")
        self.assertTrue(h.call("GetProgress", "grouped").skipped["1:1"])
        self.assertEqual(h.active()[1], 2)

    def test_previous_review_does_not_autoadvance_a_completed_group(self):
        h = self.host
        h.quest(100, delivered=True)
        h.call("Sync")
        self.assertEqual(h.cursor("grouped"), 2)
        h.call("Previous")
        h.fire("QUEST_LOG_UPDATE")
        self.assertEqual(h.cursor("grouped"), 1)
        self.assertTrue(h.call("GetProgress", "grouped").review)

    def test_all_completed_groups_finish_at_bounded_terminal_cursor(self):
        h = self.host
        h.quest(100, delivered=True)
        h.call("Sync")
        h.call("Next")
        self.assertEqual(h.cursor("grouped"), 3)
        h.call("Next")
        self.assertEqual(h.cursor("grouped"), 3)

    def test_absent_carried_turnin_is_skipped_until_quest_is_active(self):
        h = self.host
        h.group([
            {"t": "turnin", "quest": 1861, "title": "Carried from prior zone"},
            {"t": "accept", "quest": 12, "title": "Local zone quest"},
        ], id="carried")
        h.call("SelectGuide", "carried")
        self.assertEqual(h.active()[1], 2)
        h.quest(1861, onQuest=True)
        h.call("Sync")
        self.assertEqual(h.active()[1], 1)

    def test_service_events_confirm_matching_manual_goals(self):
        h = self.host
        h.group([
            {"t": "sethome", "location": "Sentinel Hill"},
            {"t": "getfp", "location": "Sentinel Hill", "npc": 123},
            {"t": "train", "class": True},
            {"t": "vendor"},
        ], id="service-events", next_goals=[{"t": "note", "text": "Done"}])
        h.call("SelectGuide", "service-events")
        h.lua.execute(r"""
        function GetBindLocation() return "Sentinel Hill" end
        function UnitGUID() return "Creature-0-1-0-1-123-0000000001" end
        """)
        for idx, event in [(1, "HEARTHSTONE_BOUND"), (2, "NEW_TAXI_PATH"), (3, "TRAINER_SHOW"), (4, "MERCHANT_SHOW")]:
            self.assertEqual(h.active()[1], idx)
            h.call("ObserveService", event)
            h.call("Sync")
            if idx >= 3:
                # Opening a window does not prove training, selling or repairing.
                self.assertEqual(h.active()[1], idx)
                h.call("Next")
        self.assertEqual(h.cursor("service-events"), 2)


class CharacterConditionTests(unittest.TestCase):
    def setUp(self):
        self.host = QuestEngineHost()
        self.host.guide()
        self.host.initialize()

    def matches(self, **conditions):
        return bool(self.host.call("MatchesConditions", self.host.table(conditions)))

    def test_conditions_use_english_tokens_and_and_across_dimensions(self):
        self.assertTrue(self.matches(classes=["WARRIOR"], races=["Human"], factions=["Alliance"]))
        self.assertFalse(self.matches(classes=["MAGE"], races=["Human"], factions=["Alliance"]))
        self.assertFalse(self.matches(classes=["WARRIOR"], races=["Orc"], factions=["Alliance"]))
        self.assertFalse(self.matches(classes=["WARRIOR"], races=["Human"], factions=["Horde"]))

    def test_each_condition_list_accepts_any_listed_value(self):
        self.assertTrue(self.matches(classes=["PRIEST", "WARRIOR"], races=["Orc", "Human"]))

    def test_undead_scourge_alias(self):
        h = self.host
        h.state.raceToken = "Scourge"
        self.assertTrue(self.matches(races=["Undead"]))
        self.assertTrue(self.matches(races=["Scourge"]))
        self.assertFalse(self.matches(races=["Human"]))

    def test_skyborne_variants_match_generic_skyborne_without_losing_faction(self):
        h = self.host
        for race in ["Skyborne", "SkyborneAlliance", "SkyborneHorde"]:
            with self.subTest(race=race):
                h.state.raceToken = race
                self.assertTrue(self.matches(races=["Skyborne"]))
                self.assertFalse(self.matches(races=["Human"]))
        h.state.raceToken = "SkyborneHorde"
        h.state.faction = "Horde"
        self.assertTrue(self.matches(races=["Skyborne"], factions=["Horde"]))
        self.assertFalse(self.matches(races=["Skyborne"], factions=["Alliance"]))


class NavigationAndFullTocTests(unittest.TestCase):
    def setUp(self):
        self.host = AddonHost(real_ui=True)
        self.host.lua.execute(CHARACTER_STUBS + r"""
        TEST.facing = 0
        TEST.continent = 0
        function GetPlayerFacing() return TEST.facing end
        function IsInInstance() return TEST.inInstance == true end
        function CreateVector2D(x, y)
            return { x = x, y = y, GetXY = function(self) return self.x, self.y end }
        end
        function C_Map.GetWorldPosFromMapPos(mapID, pos)
            local b = _G.RUTAXP_TEST_BOUNDS and _G.RUTAXP_TEST_BOUNDS[mapID]
            if not b then return nil end
            local x, y = pos:GetXY()
            local north = b.top + (b.bottom - b.top) * y
            local west = b.left + (b.right - b.left) * x
            return b.c, CreateVector2D(north, west)
        end
        """)
        self.host.ns = self.host.lua.table()
        for name in ["Core.lua", "MapFrames.lua", "QuestEngine.lua", "Navigation.lua", "UI.lua"]:
            self.host.load((ADDON / name).read_text(encoding="utf-8-sig"), "RutaXP", self.host.ns)
        self.host.globals.RUTAXP_TEST_BOUNDS = self.host.ns.mapFrames.era

    def test_era_coordinates_and_candidates_resolve_to_valid_waypoint(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, 0.50, 0.50
        h.state.classToken = "PRIEST"
        step = h.table({
            "title": "Colina del Centinela",
            "goals": [
                {"t": "sethome", "location": "Sentinel Hill"},
                {"t": "accept", "quest": 12, "map": 1436, "x": 56.33, "y": 47.52, "f": "e"},
            ],
        })
        point = h.call("GetStepWaypoint", step)
        self.assertIsNone(point)  # Current service has no coordinates; never aim at a future quest.
        point = h.call("GetGoalWaypoint", step.goals[2])
        self.assertIsNotNone(point)
        self.assertEqual(point.mapID, 1436)
        self.assertAlmostEqual(point.x, 0.5633, places=4)
        self.assertAlmostEqual(point.y, 0.4752, places=4)

        trainer_goal = h.table({
            "t": "train",
            "candidates": [
                {"faction": "A", "classes": ["PALADIN"], "npcName": "Katherine", "map": 1436, "x": 20, "y": 30, "f": "e"},
                {"faction": "A", "classes": ["PRIEST"], "npcName": "Laurena", "map": 1436, "x": 40, "y": 60, "f": "e"},
            ],
        })
        trainer_point = h.call("GetGoalWaypoint", trainer_goal)
        self.assertIsNotNone(trainer_point)
        self.assertAlmostEqual(trainer_point.x, 0.40, places=4)
        self.assertAlmostEqual(trainer_point.y, 0.60, places=4)

    def test_learned_npc_position_beats_approximate_guide_coordinates(self):
        h = self.host
        h.initialize()
        h.globals.UnitGUID = h.lua.eval("function() return 'Creature-0-1-0-1-2079-000001' end")
        goal = h.table({"t": "accept", "quest": 456, "npc": 2079, "map": 1436, "x": 10, "y": 10, "f": "e"})
        guide_point = h.call("GetGoalWaypoint", goal)
        self.assertEqual(guide_point.source, "guide")
        h.state.mapID, h.state.x, h.state.y = 1436, 0.30, 0.40
        h.call("LearnNpcPosition", 2079)
        point = h.call("GetGoalWaypoint", goal)
        self.assertEqual(point.source, "learned")
        self.assertAlmostEqual(point.x, 0.30, places=4)
        self.assertAlmostEqual(point.y, 0.40, places=4)
        # A second visit nearby is averaged instead of replacing the first one.
        h.state.x, h.state.y = 0.302, 0.402
        h.call("LearnNpcPosition", 2079)
        point = h.call("GetGoalWaypoint", goal)
        self.assertAlmostEqual(point.x, 0.301, places=4)
        # Turn-ins use the game's own waypoint once the quest is complete.
        h.lua.execute("function C_QuestLog.GetNextWaypoint(id) return 1436, 0.61, 0.52 end")
        h.quest(777, onQuest=True, complete=True)
        turnin = h.call("GetGoalWaypoint", h.table({"t": "turnin", "quest": 777, "map": 1436, "x": 5, "y": 5, "f": "e"}))
        self.assertEqual(turnin.source, "game")
        self.assertAlmostEqual(turnin.x, 0.61, places=4)

    def test_waypoint_vector_and_goto_arrival_advance_only_travel_goals(self):
        h = self.host
        h.state.mapID, h.state.x, h.state.y = 1436, 0.50, 0.50
        h.load((ADDON / "Leveling.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.ns.RegisterGuide(h.ns, h.table({
            "id": "nav-test",
            "title": "Nav Test",
            "steps": [
                {"title": "Travel step", "goals": [
                    {"t": "goto", "map": 1436, "x": 50, "y": 50, "f": "e", "text": "Arrive here"},
                    {"t": "accept", "quest": 12, "map": 1436, "x": 50, "y": 50, "f": "e", "title": "The People's Militia"},
                ]},
            ],
        }))
        h.initialize()
        h.call("SelectGuide", "nav-test")
        h.call("OnNavigationTick")
        # Being at (50, 50) completes the goto goal, advancing active goal to index 2 (accept),
        # but NEVER completes the quest accept goal just by proximity.
        _, step, state = h.call("GetCurrent")
        self.assertEqual(state.cursor, 1)
        active = h.call("GetActiveGoal")
        self.assertEqual(active[1], 2)
        self.assertTrue(h.ns.navigationFrame.shown)
        self.assertTrue(h.call("Navigate"))


class LevelingCatalogTests(unittest.TestCase):
    def test_production_catalog_contains_all_57_source_routes_and_real_goals(self):
        h = QuestEngineHost(catalog=True)
        self.assertEqual(len(h.ns.order), 57)
        self.assertEqual(len({id for _, id in h.ns.order.items()}), 57)
        quest_goal_count = 0
        for _, guide_id in h.ns.order.items():
            guide = h.ns.guides[guide_id]
            self.assertTrue(guide.title)
            self.assertGreater(len(guide.steps), 0)
            for _, step in guide.steps.items():
                self.assertIsNotNone(step.goals, guide_id)
                self.assertGreater(len(step.goals), 0, guide_id)
                for _, goal in step.goals.items():
                    if goal.t in ("accept", "complete", "turnin"):
                        self.assertIsInstance(goal.quest, (int, float))
                        self.assertGreater(goal.quest, 0)
                        quest_goal_count += 1
        self.assertGreater(quest_goal_count, 1000)

    def test_recommended_route_matches_race_faction_and_current_level(self):
        h = QuestEngineHost(catalog=True)
        h.initialize()
        for faction, race in [("Alliance", "Human"), ("Alliance", "NightElf"), ("Horde", "Scourge"), ("Horde", "Tauren")]:
            with self.subTest(faction=faction, race=race):
                h.state.faction, h.state.raceToken, h.state.level = faction, race, 1
                guide = h.call("GetRecommendedGuide")
                self.assertIsNotNone(guide)
                self.assertEqual(guide.faction, faction)
                self.assertLessEqual(guide.minLevel, 1)
                self.assertGreaterEqual(guide.maxLevel, 1)

    def test_route_next_links_resolve_inside_shipping_catalog(self):
        h = QuestEngineHost(catalog=True)
        links = 0
        for _, guide_id in h.ns.order.items():
            guide = h.ns.guides[guide_id]
            if guide.next:
                links += 1
                self.assertIsNotNone(h.ns.guides[guide.next], f"Broken continuation from {guide_id}")
        self.assertGreater(links, 20)

    def test_dwarf_in_elwynn_forest_detects_zone_without_discarding_unfinished_steps(self):
        h = QuestEngineHost(catalog=True)
        h.state.faction = "Alliance"
        h.state.raceToken = "Gnome"
        h.state.classToken = "WARLOCK"
        h.state.level = 12
        h.state.mapID = 1429  # Elwynn Forest
        for qid in (35, 37, 45, 5545):
            h.quest(qid, delivered=True)
        h.quest(147, onQuest=True, complete=False)
        h.quest(1688, onQuest=True, complete=False)
        h.initialize()
        guide, step, state = h.call("DetectZoneGuide", True)
        self.assertEqual(guide.id, "forever/alliance/human/01-elwynn-forest")
        self.assertEqual(state.cursor, 1)
        self.assertFalse(h.call("IsQuestDelivered", 147))
        self.assertFalse(h.call("IsStepComplete", step, state))

    def test_quest_automation_accepts_and_turns_in_guide_quests(self):
        h = QuestEngineHost()
        h.lua.execute(r"""
        TEST.accepted = 0
        TEST.completed = 0
        TEST.rewarded = nil
        TEST.shift = false
        TEST.choices = 1
        function IsShiftKeyDown() return TEST.shift end
        function GetQuestID() return TEST.dialogQuestID end
        function AcceptQuest() TEST.accepted = TEST.accepted + 1 end
        function IsQuestCompletable() return true end
        function CompleteQuest() TEST.completed = TEST.completed + 1 end
        function GetNumQuestChoices() return TEST.choices end
        function GetQuestMoneyToGet() return 0 end
        function GetQuestReward(choice) TEST.rewarded = choice end
        """)
        h.group([
            {"t": "accept", "quest": 501, "title": "Auto quest"},
            {"t": "turnin", "quest": 501, "title": "Auto quest"},
        ], id="auto-test")
        h.initialize()
        h.call("SelectGuide", "auto-test")
        h.state.dialogQuestID = 501
        h.state.shift = True
        h.call("HandleQuestAutomation", "QUEST_DETAIL")
        self.assertEqual(h.state.accepted, 0)
        h.state.shift = False
        h.call("HandleQuestAutomation", "QUEST_DETAIL")
        self.assertEqual(h.state.accepted, 1)
        h.call("HandleQuestAutomation", "QUEST_PROGRESS")
        self.assertEqual(h.state.completed, 1)
        h.state.choices = 2
        h.call("HandleQuestAutomation", "QUEST_COMPLETE")
        self.assertIsNone(h.state.rewarded)
        h.state.choices = 1
        h.call("HandleQuestAutomation", "QUEST_COMPLETE")
        self.assertEqual(h.state.rewarded, 1)

    def test_spanish_localization_applied_to_npcs_and_zones(self):
        h = QuestEngineHost(catalog=True)
        elwynn = h.ns.guides["forever/alliance/human/01-elwynn-forest"]
        self.assertEqual(elwynn.zoneName, "Bosque de Elwynn")
        self.assertEqual(elwynn.steps[1].goals[1].npcName, "Eagan Desollapelambres")
        tirisfal = h.ns.guides["forever/horde/undead/01-tirisfal-glades"]
        self.assertEqual(tirisfal.zoneName, "Claros de Tirisfal")
        self.assertEqual(tirisfal.steps[1].goals[1].npcName, "Enterrador Mordo")

    def test_step_goal_items_deduplicate_notes_and_hide_premature_turnin(self):
        h = QuestEngineHost()
        h.group([
            {
                "t": "collect",
                "quest": 1688,
                "obj": 1,
                "title": "Restos de tortuga marina",
                "itemName": "Restos de tortuga marina",
                "count": 1,
                "note": "Restos de tortuga marina, en la playa",
            },
            {
                "t": "turnin",
                "quest": 1688,
                "title": "Entrega la misión",
                "npcName": "Gwennyth Bly'Leggonde",
            },
        ], id="dedup-test")
        h.quest(1688, onQuest=True, complete=False, objectives=[
            {"text": "Restos de tortuga marina: 0/1", "finished": False}
        ])
        h.initialize()
        h.call("SelectGuide", "dedup-test")
        guide, step, state = h.call("GetCurrent")
        items, done_count = h.call("GetStepGoalItems", step, state)
        self.assertEqual(len(items), 1)
        self.assertEqual(done_count, 0)
        self.assertEqual(items[1].title, "Reúne: Restos de tortuga marina")
        self.assertEqual(items[1].subtitle, "Restos de tortuga marina: 0/1\nEn la playa")


class TalentGuideTests(unittest.TestCase):
    def setUp(self):
        self.host = AddonHost(real_ui=True)
        self.host.lua.execute(CHARACTER_STUBS)
        self.host.load((ADDON / "Talents.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.host.ns)
        self.host.load((ADDON / "TalentBuilds.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.host.ns)
        self.host.guide()
        self.host.initialize()

    def test_all_9_classes_and_10_races_have_multiple_validated_guides(self):
        talents = self.host.ns.Talents
        expected_classes = [
            "WARRIOR", "PALADIN", "HUNTER", "ROGUE", "PRIEST",
            "SHAMAN", "MAGE", "WARLOCK", "DRUID",
        ]
        for cls in expected_classes:
            data = talents.Registry[cls]
            self.assertIsNotNone(data, f"Missing class {cls}")
            self.assertEqual(len(data.builds), 4, f"{cls} should offer 4 talent guides")
            for idx in range(1, 5):
                build = data.builds[idx]
                self.assertEqual(len(build.picks), 51, f"{cls} build {build.key} must have 51 talent picks")
                self.assertTrue(build.stats)
                self.assertTrue(build.weapons)
                self.assertTrue(build.skills)
                self.assertTrue(build.rotation)

        expected_races = [
            "Human", "Dwarf", "NightElf", "Gnome", "Skyborne",
            "Orc", "Undead", "Tauren", "Troll", "Goblin",
        ]
        for race in expected_races:
            self.assertIsNotNone(talents.RaceGuides[race], f"Missing race guide for {race}")

    def test_auto_detects_player_class_race_and_switches_build_by_spent_points_or_choice(self):
        h = self.host
        h.globals.TEST.classToken = "MAGE"
        h.globals.TEST.raceToken = "Gnome"
        h.globals.TEST.level = 14
        talents = h.ns.Talents

        res = talents.Evaluate()
        self.assertEqual(res.player.classToken, "MAGE")
        self.assertEqual(res.player.raceToken, "Gnome")
        self.assertEqual(res.build.key, "frost_single")
        self.assertEqual(res.source, "auto_recommended")

        # Simulate spending 3 points in Fire node 105795 (Improved Fireball) -> should auto-detect fire_burst
        mage_data = talents.Data("MAGE")
        ranks = h.table({105795: 3})
        matched_build, source = talents.BestBuild(mage_data, ranks)
        self.assertEqual(matched_build.key, "fire_burst")
        self.assertEqual(source, "auto_points")

        # Explicit user selection overrides auto detection
        talents.SetChoice("arcane_blast", "MAGE")
        res2 = talents.Evaluate()
        self.assertEqual(res2.build.key, "arcane_blast")
        self.assertEqual(res2.source, "chosen")

    def test_toggle_panel_and_slash_command_render_all_51_steps(self):
        h = self.host
        h.globals.TEST.classToken = "PALADIN"
        h.globals.TEST.raceToken = "Human"
        h.globals.TEST.level = 20
        h.call("Command", "talentos")
        panel = h.ns.Talents.panel
        self.assertIsNotNone(panel)
        self.assertTrue(panel.shown)
        self.assertIn("Humano", panel.detectedText.text)
        self.assertIn("Paladín", panel.detectedText.text)
        self.assertEqual(len(panel.rows), 51)

    def test_spells_tab_lists_trainer_purchases_for_the_class(self):
        h = self.host
        h.globals.TEST.classToken = "PALADIN"
        h.globals.TEST.level = 6
        h.call("Command", "talentos")
        panel = h.ns.Talents.panel
        h.lua.execute("function noop() end")
        panel.activeTab = "spells"
        h.ns.Talents.RenderPanel()
        spells = h.ns.Talents.Registry.PALADIN.trainerSpells
        self.assertGreater(len(spells), 10)
        self.assertIn("COMPRAR", panel.rows[1].spec.text + panel.rows[2].spec.text)

    def test_trainer_window_marks_each_spell_with_a_recommendation(self):
        h = self.host
        h.load((ADDON / "Trainer.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.globals.TEST.classToken = "PALADIN"
        h.globals.TEST.level = 6
        h.lua.execute(r"""
        local services = {
            { "Bendición del poderío (Rango 1)", "available" },
            { "Sentencia", "available" },
            { "Furia Cósmica", "available" },
            { "Sello del Cruzado", "unavailable" },
            { "Luz Sagrada", "used" },
        }
        function IsTradeskillTrainer() return false end
        Enum = Enum or {}; Enum.TrainerType = { General=0, Pet=3, Tradeskills=2 }
        C_Trainer = { GetTrainerType = function() return 0 end }
        function GetNumTrainerServices() return #services end
        function GetTrainerServiceInfo(i) return services[i][1], services[i][2], 12345, 1, "Rango 1" end
        function GetTrainerServiceCost() return 100 end
        function GetMoney() return 119 end
        function fakeText(text)
            local t = CreateFrame()
            t.text = text
            t.GetObjectType = function() return "FontString" end
            return t
        end
        function fakeRow(name)
            local r = CreateFrame()
            local label = fakeText(name)
            r.GetRegions = function() return label end
            r.GetChildren = function() end
            return r
        end
        TEST.rows = {}
        for _, s in ipairs(services) do TEST.rows[#TEST.rows + 1] = fakeRow(s[1]) end
        ClassTrainerFrame = CreateFrame()
        ClassTrainerFrame.ScrollBox = { ForEachFrame = function(_, fn)
            for _, r in ipairs(TEST.rows) do fn(r) end
        end }
        """)
        h.ns.TrainerAdvice.Refresh(h.globals.ClassTrainerFrame)
        rows = h.state.rows
        self.assertIn("COMPRAR", rows[1].RutaXPBadge.text)      # Bendición del poderío (guide: must)
        self.assertIn("COMPRAR", rows[2].RutaXPBadge.text)      # Sentencia (guide: must)
        self.assertIn("Opcional", rows[3].RutaXPBadge.text)     # unknown spell receives no spending priority
        self.assertIn("Más adelante", rows[4].RutaXPBadge.text) # not learnable yet
        self.assertEqual(rows[5].RutaXPBadge.text, "")          # already learned
        banner = h.ns.TrainerAdvice.banner.text.text
        self.assertIn("Compra ahora", banner)
        self.assertIn("Bendición del poderío", banner)
        self.assertIn("Te falta oro", banner)  # only 119 copper for 100-copper spells


if __name__ == "__main__":
    unittest.main()



