"""Regression cases for required Wetlands work omitted before later chapters."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

from test_quest_engine import QuestEngineHost

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP/Source"
TH = "forever/alliance/07-thousand-needles"
HI = "forever/alliance/30-40/01-hillsbrad-foothills"
STV = "forever/alliance/40-50/01-stranglethorn-vale"
REVISIONS = {"thousand-needles-nekrosh-chain-2", "hillsbrad-wetlands-prerequisite-chains-3"}


class SuccessorChainContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((SOURCE / "leveling.json").read_text(encoding="utf8"))
        cls.guides = {g["id"]: g for g in cls.document["guides"]}
        cls.revisions = [r for r in json.loads((SOURCE / "guide_revisions.json").read_text(encoding="utf8"))["revisions"] if r["id"] in REVISIONS]
        spec = importlib.util.spec_from_file_location("successor_builder", SOURCE / "build_guides.py")
        cls.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.builder)

    def route_goals(self, *ids):
        return [goal for ident in ids for step in self.guides[ident]["steps"] for goal in step["goals"]]

    def index(self, goals, quest, action):
        return next(i for i, goal in enumerate(goals) if goal.get("quest") == quest and goal["t"] == action)

    def test_each_missing_quest_has_accepted_work_and_delivery_before_followup(self):
        goals = self.route_goals(TH, HI)
        for parent, child in ((474, 98230), (98208, 98209), (98291, 98297)):
            with self.subTest(parent=parent, child=child):
                accepted, delivered = self.index(goals, parent, "accept"), self.index(goals, parent, "turnin")
                followup = self.index(goals, child, "accept")
                self.assertLess(accepted, delivered)
                self.assertLess(delivered, followup)
                work = [i for i, goal in enumerate(goals) if goal.get("quest") == parent and goal["t"] in ("kill", "collect", "complete")]
                self.assertTrue(work)
                self.assertTrue(all(accepted < i < delivered for i in work))
                self.assertEqual(goals[followup]["preAll"], [parent])
                self.assertFalse(any(goal.get("optional") for goal in goals if goal.get("quest") == parent))
        for parent, child in ((471, 98072), (299, 98216)):
            self.assertLess(self.index(goals, parent, "turnin"), self.index(goals, child, "accept"))

    def test_nekrosh_is_completed_before_leaving_menethil_and_old_skip_note_is_gone(self):
        steps = self.guides[TH]["steps"]
        self.assertEqual([(g["t"], g.get("quest")) for g in steps[28]["goals"]],
                         [("turnin", 465), ("accept", 474), ("note", None)])
        self.assertEqual(steps[29]["goals"][0]["quest"], 474)
        self.assertEqual([(g["t"], g.get("quest")) for g in steps[30]["goals"]],
                         [("hearth", None), ("turnin", 474), ("note", None)])
        self.assertIn("élite", steps[29]["goals"][0]["note"])
        self.assertNotIn("saltarlo", steps[28]["goals"][2]["text"])
        self.assertNotIn("skip it", steps[28]["goals"][2]["text"])

    def test_nordel_and_dragonmaw_objectives_match_sources_and_have_real_destinations(self):
        goals = self.route_goals(HI)
        flower = next(g for g in goals if g.get("quest") == 98208 and g["t"] == "collect")
        self.assertEqual((flower["item"], flower["count"], flower["map"], flower["x"], flower["y"]),
                         (279915, 1, 1437, 12.2, 63.8))
        mobs = [g for g in goals if g.get("quest") == 98291 and g["t"] == "kill"]
        self.assertEqual([(g["oi"], g["npc"], g["count"]) for g in mobs],
                         [(1, 271351, 8), (2, 271348, 5), (3, 271346, 3)])
        additions = [a for r in self.revisions for a in r["addedGoals"].values()]
        self.assertEqual(len(additions), 11)
        for addition in additions:
            goal = addition["goal"]
            self.assertEqual(goal["map"], 1437)
            self.assertTrue(0 < goal["x"] < 100 and 0 < goal["y"] < 100)
            self.assertTrue(goal["note"])
            for proof in addition["evidence"]["sources"]:
                self.assertRegex(proof["sha256"], r"^[0-9a-f]{64}$")
                self.assertIn(proof["commit"], proof["url"])
            if "z" in goal:
                self.assertTrue(addition["evidence"].get("navigationDonor"))

    def test_partial_dragonmaw_work_does_not_unlock_the_followup(self):
        host = QuestEngineHost(catalog=True)
        host.state.level = 30
        host.initialize()
        host.ns.char.auto = False
        host.call("SelectGuide", HI)
        host.quest(98291, onQuest=True, complete=False, objectives=[
            {"finished": True, "numFulfilled": 8, "numRequired": 8},
            {"finished": False, "numFulfilled": 1, "numRequired": 5},
            {"finished": False, "numFulfilled": 0, "numRequired": 3},
        ])
        state = host.call("GetProgress", HI)
        guide = host.ns.guides[HI]
        for si, step in guide.steps.items():
            for gi, goal in step.goals.items():
                if goal.quest == 98291 and goal.t == "kill":
                    state.cursor = si
                    self.assertEqual(host.status(goal, step, state, gi), "done" if goal.oi == 1 else "active")
                if goal.quest == 98297 and goal.t == "accept":
                    state.cursor = si
                    self.assertEqual(host.status(goal, step, state, gi), "blocked")
                    host.quest(98291, onQuest=True, complete=True)
                    self.assertEqual(host.status(goal, step, state, gi), "blocked")
                    host.quest(98291, onQuest=False, delivered=True)
                    self.assertEqual(host.status(goal, step, state, gi), "active")

    def test_additions_never_replace_old_action_marks_and_completed_cursor_maps_to_end(self):
        for revision in self.revisions:
            migration = self.builder.revision_progress(revision)
            guide = self.guides[revision["guideID"]]
            old = {f"{si}:{gi}" for si, count in enumerate(revision["previousGoalCounts"], 1) for gi in range(1, count + 1)}
            mapped = {migration["goalMap"].get(key, key) for key in old}
            added = set(migration["addedGoalKeys"])
            current = {f"{si}:{gi}" for si, step in enumerate(guide["steps"], 1) for gi in range(1, len(step["goals"]) + 1)}
            self.assertEqual(len(mapped), len(old))
            self.assertFalse(mapped & added)
            self.assertEqual(mapped | added, current)
            self.assertEqual(len(added), len(revision["addedGoals"]))
            self.assertEqual(migration["stepMap"][str(len(revision["previousGoalCounts"]) + 1)], len(guide["steps"]) + 1)
        before = copy.deepcopy(self.document)
        self.builder.apply_guide_revisions(self.document, SOURCE / "guide_revisions.json")
        self.assertEqual(self.document, before)

    def test_late_conflicting_feast_requirement_is_reported_without_unusable_gate(self):
        report = json.loads((SOURCE / "successor_review.json").read_text(encoding="utf8"))
        self.assertEqual(report["scope"]["guides"], 24)
        self.assertTrue(report["limits"])
        feast = next(r for r in report["notApplied"] if r["questID"] == 1271)
        self.assertEqual(feast["authored"], {"pre": [1222]})
        self.assertEqual(feast["reportedByEverythingQuestsAndATT"], {"preAll": [1222, 1258]})
        current = next(g for g in self.route_goals(STV) if g.get("quest") == 1271 and g["t"] == "accept")
        self.assertEqual(current["pre"], [1222])
        self.assertNotIn("preAll", current)
        self.assertFalse(any(g.get("quest") == 1258 for g in self.route_goals(STV)))


if __name__ == "__main__":
    unittest.main()
