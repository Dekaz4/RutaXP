"""Level and reputation apply to Rutherford's offer, even with optional quests shown."""

import json
import unittest
from copy import deepcopy

from test_quest_engine import ADDON, QuestEngineHost


class BattlefieldRewardTests(unittest.TestCase):
    def setUp(self):
        self.h = h = QuestEngineHost()
        for module in ("NPCQuestContext.lua", "TrackerPreview.lua"):
            h.load((ADDON / module).read_text(encoding="utf-8"), "RutaXP", h.ns)
        record = ADDON.parent / "tools" / "solo_review_unmatched_c.json"
        self.limits = json.loads(record.read_text(encoding="utf-8"))["8263"]["offerLimits"]
        goal = dict(quest=8263, npc=15126, levelingDetour=True, offerLimits=self.limits)
        self.guide = h.group(
            [{"t": "accept", "quest": 101}],
            next_goals=[dict(goal, t="accept", minLevel=25), dict(deepcopy(goal), t="turnin"),
                        {"t": "accept", "quest": 102}],
        )
        h.state.level = 34
        h.initialize()
        h.ns.char.optional = True
        h.state.rep = 3000
        h.lua.execute("""
            C_Reputation = {GetFactionDataByID=function(id)
                if id == 510 then return {currentStanding=TEST.rep} end
            end}
        """)
        self.step = self.guide.steps[2]

    def status(self, index):
        return self.h.status(self.step.goals[index], self.step, None, index)

    def preview(self):
        rows = self.h.call("GetTrackerPlannedUpcomingItems", self.guide, 1)
        return [(row.questID, row.action) for row in rows.values()]

    def test_exact_eligibility_and_unknown_reputation(self):
        h = self.h
        self.assertEqual(self.status(1), "active")
        self.assertIn((8263, "accept"), self.preview())
        h.state.rep = 2999
        self.assertEqual(self.status(1), "skip")
        self.assertNotIn(8263, [qid for qid, _ in self.preview()])
        h.state.rep = None
        self.assertEqual(self.status(1), "active")
        h.lua.execute("function GetFactionInfoByID(id) return 'Rapiñadores', nil, 4, 0, 3000, 2999 end")
        self.assertEqual(self.status(1), "skip")

    def test_expired_offer_never_blocks_next_quest_but_carried_delivery_remains(self):
        h = self.h
        h.state.level = 35
        self.assertEqual([self.status(i) for i in (1, 2, 3)], ["skip", "skip", "active"])
        self.assertEqual(self.preview(), [(102, "accept")])
        h.quest(8263, onQuest=True, complete=True)
        for optional in (True, False):
            h.ns.char.optional = optional
            self.assertEqual([self.status(i) for i in (1, 2)], ["done", "active"])
            self.assertIn((8263, "turnin"), self.preview())

    def test_offer_from_this_npc_overrides_static_requirements(self):
        h = self.h
        h.state.level = 35
        h.state.rep = 0
        h.lua.execute("""
            function UnitGUID(unit)
                if unit == 'npc' then return 'Creature-0-0-0-0-' .. TEST.npc .. '-0001' end
            end
            C_GossipInfo = {GetAvailableQuests=function() return {{questID=8263}} end}
        """)
        h.state.npc = 15126
        self.assertEqual(self.status(1), "active")
        h.state.npc = 15127
        self.assertEqual(self.status(1), "skip")
