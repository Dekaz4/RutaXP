import json
from collections import Counter
import unittest

from test_quest_engine import ADDON, QuestEngineHost
from tools import review_all_routes, unmatched_solo


class UnmatchedSoloTests(unittest.TestCase):
    def test_each_unmatched_id_has_one_individual_decision_used_in_the_report(self):
        report = review_all_routes.make_report()
        all_rows = [q for c in report["chapters"] for q in c["quests"]]
        missing = {q["id"] for q in all_rows} - {q["id"] for q in all_rows if q["routes"]}
        decisions = unmatched_solo.decisions()
        self.assertEqual(set(decisions), missing)
        self.assertEqual(len(missing), 223)
        self.assertEqual(len({c["reason"] for c in decisions.values()}), 223)
        for row in all_rows:
            if row["id"] in missing:
                case = decisions[row["id"]]
                self.assertTrue(case["url"].startswith("https://"))
                self.assertEqual(row["solo"], [case["policy"], case["reason"], case["url"]])
        catalog = json.loads((ADDON / "Source" / "leveling.json").read_bytes())
        actions = Counter()
        for guide in catalog["guides"]:
            for step in guide["steps"]:
                for goal in step["goals"]:
                    qid = goal.get("quest")
                    if qid in decisions and decisions[qid]["policy"] == "detour":
                        self.assertTrue(goal.get("levelingDetour"), (qid, guide["id"]))
                        actions[qid] += 1
        self.assertEqual(set(actions), {q for q, c in decisions.items() if c["policy"] == "detour"})

    def test_continuations_resume_if_prerequisite_is_delivered_or_quest_in_log(self):
        h = QuestEngineHost()
        step = h.group([{"t":"accept","quest":4966,"pre":[4881],"soloAfter":[4881]},
                        {"t":"complete","quest":4966,"soloAfter":[4881]}]).steps[1]
        h.initialize()
        self.assertEqual(h.status(step.goals[1]), "skip")
        self.assertEqual(h.status(step.goals[2]), "skip")
        h.ns.char.optional = True
        self.assertEqual(h.status(step.goals[1]), "blocked")
        h.ns.char.optional = False
        h.quest(4966, onQuest=True, complete=False)
        self.assertEqual(h.status(step.goals[2]), "active")
        h.quest(4966, onQuest=False)
        h.quest(4881, delivered=True)
        self.assertEqual(h.status(step.goals[1]), "active")

    def test_crate_flight_requires_a_box_or_a_ready_handin(self):
        h = QuestEngineHost(catalog=True)
        h.initialize()
        h.lua.execute("TEST.bags={}; C_Item={GetItemCount=function(id) return TEST.bags[id] or 0 end}")
        guide = h.ns.guides["forever/horde/50-60/04-azshara"]
        flight = guide.steps[2].goals[1]
        self.assertEqual(h.status(flight), "skip")
        for item in (248765, 248770):
            h.state.bags[item] = 1
            self.assertNotEqual(h.status(flight), "skip")
            h.state.bags[item] = 0
        h.quest(91904, onQuest=True, complete=True)
        self.assertNotEqual(h.status(flight), "skip")
        h.quest(91904, delivered=True)
        self.assertEqual(h.status(flight), "skip")
        h.quest(91899, delivered=True)
        h.ns.char.optional = True
        self.assertEqual(h.status(flight), "done")
        self.assertNotEqual(h.status(guide.steps[4].goals[1]), "skip")

    def test_librarian_only_brings_forward_a_reward_explicitly_offered_here(self):
        h = QuestEngineHost()
        h.load((ADDON / "NPCQuestContext.lua").read_text(encoding="utf8"), "RutaXP", h.ns)
        goal = h.group([{"t":"accept","quest":79536,"npc":211033,"levelingDetour":True,
                         "soloWhenOffered":True}]).steps[1].goals[1]
        h.initialize()
        self.assertEqual(h.status(goal), "skip")
        h.lua.execute("C_GossipInfo={GetAvailableQuests=function() return {{questID=79536}} end}")
        self.assertEqual(h.status(goal), "skip")
        h.lua.execute("UnitGUID=function(unit) if unit=='npc' then return 'Creature-0-1-2-3-211033-0001' end end")
        self.assertEqual(h.status(goal), "active")
