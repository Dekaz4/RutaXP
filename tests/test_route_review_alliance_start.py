import copy
import json
import unittest

from test_addon import ROOT
from test_quest_engine import QuestEngineHost
from tools import route_review_alliance_start as review


class EarlyAllianceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((ROOT / "RutaXP/Source/leveling.json").read_text(encoding="utf8"))
        cls.document = {"guides": [g for g in catalog["guides"] if g["id"] in review.REFERENCES]}
        review.apply(cls.document)

    def test_each_note_and_source_belongs_to_a_real_chapter_and_quest(self):
        self.assertEqual(len(self.document["guides"]), 10)
        for guide in self.document["guides"]:
            guide_id = guide["id"]
            ids = {a.get("quest") for step in guide["steps"] for a in step["goals"]}
            notes = {quest for chapter, quest in review.NOTES if chapter == guide_id}
            self.assertTrue(notes and notes <= ids, (guide_id, notes - ids))
            self.assertTrue(all(url.startswith("https://") and detail for url, detail in review.REFERENCES[guide_id]))

    def test_reimport_preserves_all_positions_and_conditions(self):
        route = copy.deepcopy(self.document)
        for guide in route["guides"]:
            for step in guide["steps"]:
                for goal in step["goals"]:
                    if goal.get("quest") in review.SOLO_DETOURS.get(guide["id"], {}):
                        goal.pop("levelingDetour", None)
                        goal.pop("detourBelowLevel", None)
                    if goal.get("quest") in (184, 337) or goal.get("item") in (1972, 2794):
                        for field in ("levelingDetour", "detourItems", "detourQuest"):
                            goal.pop(field, None)
        review.apply(route)
        self.assertEqual(route, self.document)
        review.apply(route)
        self.assertEqual(route, self.document)

    def test_optional_escorts_do_not_hide_the_local_breadcrumb_or_their_reward(self):
        host = QuestEngineHost()
        host.group([{"t": "accept", "quest": 945}])
        host.initialize()
        for guide in self.document["guides"]:
            for step in guide["steps"]:
                for goal in step["goals"]:
                    quest = goal.get("quest")
                    if quest in (729, 967, 91, 1110, 1104, 1105, 1176):
                        self.assertFalse(goal.get("levelingDetour"), quest)
                    if quest not in review.SOLO_DETOURS.get(guide["id"], {}):
                        continue
                    self.assertTrue(goal["levelingDetour"])
                    threshold = review.SOLO_DETOURS[guide["id"]][quest]
                    host.state.level = (threshold or 35) - 1
                    self.assertTrue(host.call("IsSoloLevelingDetour", host.table(goal)))
                    if goal["t"] == "turnin":
                        self.assertFalse(host.call("GetLevelingDetourReason", host.table(goal), True, True))
                    if threshold:
                        host.state.level = threshold
                        self.assertFalse(host.call("IsSoloLevelingDetour", host.table(goal)))

    def test_found_books_and_deeds_can_be_used_and_delivered_in_passing(self):
        host = QuestEngineHost()
        host.group([{"t": "accept", "quest": 184}])
        host.initialize()
        host.state.level = 26
        host.lua.execute("C_Item = {GetItemCount=function(id) return id == TEST.carried and 1 or 0 end}")
        for quest, item, count in [(184, 1972, 4), (337, 2794, 3)]:
            goals = [g for guide in self.document["guides"] for step in guide["steps"] for g in step["goals"]
                     if g.get("item") == item or g.get("quest") == quest]
            self.assertEqual(len(goals), count)
            for goal in goals:
                self.assertTrue(goal["levelingDetour"])
                self.assertEqual(goal["detourItems"], {str(item): 1})
                if goal["t"] == "accept":
                    self.assertTrue(host.call("GetLevelingDetourReason", host.table(goal)))
                    host.state.carried = item
                    self.assertFalse(host.call("GetLevelingDetourReason", host.table(goal)))
                    host.state.carried = None
                elif goal["t"] == "turnin":
                    self.assertFalse(host.call("GetLevelingDetourReason", host.table(goal), True, True))
