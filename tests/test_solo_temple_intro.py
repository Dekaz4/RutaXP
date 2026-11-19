"""An outdoor dungeon breadcrumb is useful to a solo player on the road to Un'Goro."""
import json
import unittest

from test_addon import ADDON
from test_quest_engine import QuestEngineHost


class SoloTempleIntroTests(unittest.TestCase):
    def test_mojache_to_marvon_has_only_two_outdoor_conversations(self):
        document = json.loads((ADDON / "Source/leveling.json").read_bytes())
        calls = [(goal["t"], goal["npc"], goal["map"], step.get("group"), goal.get("group"))
                 for guide in document["guides"] for step in guide["steps"] for goal in step["goals"]
                 if goal.get("quest") == 3380]
        self.assertEqual(calls, [("accept", 8115, 1444, None, None),
                                 ("turnin", 7771, 1446, None, None)])

    def test_talk_opens_stone_circle_but_actual_dungeon_is_still_optional(self):
        h = QuestEngineHost()
        h.load((ADDON / "GroupQuestData.lua").read_text(encoding="utf8"), "RutaXP", h.ns)
        h.group([{"t": "accept", "quest": 3380}, {"t": "turnin", "quest": 3380},
                 {"t": "accept", "quest": 3444, "pre": [3380]},
                 {"t": "accept", "quest": 3446, "pre": [3444]}])
        h.lua.execute("""
            C_QuestLog.GetQuestTagInfo = function(id)
                if id == 3380 or id == 3446 then return {tagID=81} end
            end
        """)
        h.initialize()
        _, step, state = h.call("GetCurrent")
        self.assertTrue(h.ns.Data.groupQuests[3380])
        self.assertFalse(h.call("IsGroupQuest", 3380))
        self.assertEqual(h.status(step.goals[1], step, state, 1), "active")
        h.quest(3380, onQuest=True, complete=True)
        self.assertEqual(h.status(step.goals[2], step, state, 2), "active")
        h.quest(3380, delivered=True)
        self.assertEqual(h.status(step.goals[3], step, state, 3), "active")
        h.quest(3444, delivered=True)
        self.assertEqual(h.status(step.goals[4], step, state, 4), "skip")
        h.ns.char.includeGroupQuests = True
        self.assertEqual(h.status(step.goals[4], step, state, 4), "active")
