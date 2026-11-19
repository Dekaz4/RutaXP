"""Solo leveling choices and the playable final level of the Alliance guide."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from test_quest_engine import QuestEngineHost
from tools import solo_late_route as route

ROOT = Path(__file__).resolve().parents[1]


class SoloLateRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        document = json.loads((ROOT / "RutaXP/Source/leveling.json").read_text(encoding="utf8"))
        cls.snapshot = {"guides": [g for g in document["guides"]
                                   if g["id"].removeprefix(route.ALLIANCE) in route.QUESTS]}
        cls.reviewed = deepcopy(cls.snapshot)
        route.apply_late_detours(cls.reviewed)
        cls.guides = {g["id"].removeprefix(route.ALLIANCE): g for g in cls.reviewed["guides"]}

    def test_rebuild_is_idempotent_and_preserves_saved_goal_indices(self):
        saved_fields = ("t", "quest", "oi", "item", "level", "only", "optional", "pre", "preAll")
        def keys(guide):
            return [[tuple(q.get(k) for k in saved_fields) for q in s["goals"]] for s in guide["steps"]]

        for before, after in zip(self.snapshot["guides"], self.reviewed["guides"], strict=True):
            self.assertEqual(keys(before), keys(after), before["id"])
        twice = deepcopy(self.reviewed)
        route.apply_late_detours(twice)
        self.assertEqual(twice, self.reviewed)

    def test_all_twelve_cloth_donations_are_bag_opportunities_in_both_chapters(self):
        items = {7791: 2592, 7793: 4306, 7794: 4338, 7795: 14047,
                 7802: 2592, 7803: 4306, 7804: 4338, 7805: 14047,
                 7807: 2592, 7808: 4306, 7809: 4338, 7811: 14047}
        seen = {}
        for chapter in (route.SILITHUS, route.FINAL):
            for step in self.guides[chapter]["steps"]:
                for q in step["goals"]:
                    if q.get("quest") in items:
                        self.assertTrue(q["levelingDetour"])
                        self.assertEqual(q["detourItems"], {str(items[q["quest"]]): 60})
                        seen.setdefault(q["quest"], set()).add(q["t"])
        self.assertEqual(set(seen), set(items))
        self.assertTrue(all({"accept", "turnin"} <= actions for actions in seen.values()))

    def test_mixed_steps_keep_keys_flight_paths_and_main_experience(self):
        for chapter, step_number, quest in [
            (route.HINTERLANDS, 8, 2583), (route.WINTERSPRING, 28, 5211),
            (route.PLAGUELANDS, 3, 5092), (route.PLAGUELANDS, 19, 5225),
            (route.SILITHUS, 19, 8275), (route.FINAL, 9, 4005),
        ]:
            goals = self.guides[chapter]["steps"][step_number - 1]["goals"]
            self.assertTrue(any(g.get("levelingDetour") for g in goals))
            self.assertTrue(any(g.get("quest") == quest and not g.get("levelingDetour") for g in goals))
        for chapter, index, quest in ((route.STEPPES, 27, 3501), (route.SILITHUS, 20, 7261)):
            flight = self.guides[chapter]["steps"][index-1]["goals"][0]
            self.assertEqual((flight["t"], flight["detourQuest"], flight["levelingDetour"]), ("fly", quest, True))

    def test_tanaris_wanted_poster_still_works_after_skipping_the_escort(self):
        steps = self.guides[route.TANARIS]["steps"]
        self.assertTrue(all(g["levelingDetour"] for g in steps[17]["goals"]))
        poster = steps[18]["goals"][0]
        self.assertEqual((poster["t"], poster["quest"], poster["object"]), ("accept", 2781, 150075))
        self.assertEqual((poster["map"], poster["x"], poster["y"], poster["f"]), (1446, 51.8, 27, "e"))
        self.assertNotIn("z", poster)
        self.assertEqual(steps[19]["title"], "Gadgetzan")
        self.assertFalse(poster.get("levelingDetour"))

    def test_final_level_hunt_has_a_real_arrow_and_finishes_on_level_60(self):
        steps = self.guides[route.FINAL]["steps"]
        self.assertTrue(steps[35]["goals"][0]["levelingDetour"])
        self.assertLess(max(g.get("minLevel", 0) for s in steps[36:] for g in s["goals"]), 59)
        end = steps[52]["goals"][0]
        bear = self.guides[route.PLAGUELANDS]["steps"][6]["goals"][0]
        self.assertEqual(bear["npc"], 1816)
        self.assertEqual([end[k] for k in ("map", "x", "y", "f")], [bear[k] for k in ("map", "x", "y", "f")])
        self.assertNotIn("levelingDetour", end)
        h = QuestEngineHost()
        h.group([end], next_goals=[{"t": "train"}])
        for name in ("MapFrames", "Navigation"):
            h.load((ROOT / "RutaXP" / (name + ".lua")).read_text(encoding="utf8"), "RutaXP", h.ns)
        h.ns.UpdateNavigation = None
        h.lua.execute("C_Map.GetMapPosFromWorldPos=function(_,_,map) return map,{GetXY=function() return .53,.62 end} end")
        h.state.level, h.state.classToken, h.state.mapID = 59, "ROGUE", 1422
        h.initialize()
        _, step, state = h.call("GetCurrent")
        self.assertEqual(h.status(step.goals[1], step, state), "active")
        self.assertEqual(h.call("GetBaseStepWaypoint", step).mapID, 1422)
        h.state.level = 60
        self.assertEqual(h.status(step.goals[1], step, state), "done")

    def test_hunts_stay_near_the_previous_quest_or_the_next_destination(self):
        for chapter, index, expected in [
            (route.UNGORO, 12, (50, 1449, 63.1, 17.4, "e")),
            (route.UNGORO, 28, (51, 1449, 60.7, 38.9, "e")),
            (route.WINTERSPRING, 12, (54, 1452, 66.4, 41.5, "e")),
            (route.SILITHUS, 26, (57, 1423, 14.3, 67.9, "l")),
        ]:
            goal = self.guides[chapter]["steps"][index-1]["goals"][-1]
            self.assertEqual(tuple(goal[k] for k in ("level", "map", "x", "y", "f")), expected)
            self.assertNotIn("levelingDetour", goal)
        horns = self.guides[route.WINTERSPRING]["steps"][11]["goals"][0]
        self.assertEqual((horns["quest"], horns["item"]), (977, 12367))

    def test_torwa_early_offer_credits_pelts_without_moving_either_quest(self):
        steps = self.guides[route.UNGORO]["steps"]
        self.assertIn("Los simios de Un'Goro", steps[1]["note"])
        self.assertEqual([g["quest"] for g in steps[1]["goals"]], [4290])
        self.assertEqual([g["quest"] for g in steps[16]["goals"]], [4289])
        h = QuestEngineHost(catalog=True)
        for name in ("EarlyQuestData", "QuestOfferAdvice"):
            h.load((ROOT / "RutaXP" / (name + ".lua")).read_text(encoding="utf8"), "RutaXP", h.ns)
        h.state.classToken, h.state.level = "ROGUE", 48
        h.initialize()
        h.call("SelectGuide", route.ALLIANCE + route.UNGORO)
        guide, _, state = h.call("GetCurrent")
        state.cursor, state.review = 2, False
        h.lua.execute("function C_QuestLog.GetNumQuestLogEntries() return 2,1 end; function C_QuestLog.GetMaxNumQuestsCanAccept() return 20 end")
        self.assertEqual(h.call("GetEarlyQuestOffer", 4289)[1], "ahora")
        h.quest(4289, onQuest=True, complete=True)
        self.assertEqual(h.status(guide.steps[17].goals[1], guide.steps[17], state), "done")
        for index in range(1, 4):
            self.assertEqual(h.status(guide.steps[23].goals[index], guide.steps[23], state, index), "done")
