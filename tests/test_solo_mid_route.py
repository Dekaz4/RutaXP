"""Midgame solo route, from the coast at 32 to the first Zorbin quests at 45."""
import copy
import json
from pathlib import Path
import sys
import unittest

from test_duo_journey import primitive_copy
from test_quest_engine import QuestEngineHost
from test_westfall_migration import MigrationHost

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP/Source"
sys.path.insert(0, str(ROOT / "tools"))
from solo_mid_route import ALLIANCE, DETOURS, apply_mid_detours


class SoloMidRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((SOURCE / "leveling.json").read_text(encoding="utf8"))
        cls.guides = {g["id"].removeprefix(ALLIANCE): g for g in cls.document["guides"]
                      if g["id"].startswith(ALLIANCE)}

    def goals(self, chapter):
        return [(i, q) for i, step in enumerate(self.guides[chapter]["steps"], 1) for q in step["goals"]]

    def visit(self, chapter, quest, action):
        visits = {i for i, q in self.goals(chapter) if q.get("quest") == quest and q["t"] == action}
        self.assertEqual(len(visits), 1)
        return visits.pop()

    def test_separate_returns_now_share_a_visit(self):
        for chapter, left, right in (
            ("30-40/01-hillsbrad-foothills", (562, "turnin"), (555, "turnin")),
            ("30-40/02-desolace", (1458, "turnin"), (1465, "turnin")),
            ("30-40/03-ashenvale", (1031, "collect"), (98418, "kill")),
            ("30-40/04-stranglethorn-vale", (616, "accept"), (201, "turnin")),
            ("30-40/04-stranglethorn-vale", (577, "turnin"), (578, "turnin")),
            ("30-40/06-badlands", (1455, "turnin"), (1466, "turnin")),
            ("40-50/01-stranglethorn-vale", (608, "turnin"), (606, "turnin")),
        ):
            with self.subTest(chapter=chapter, quest=left[0]):
                self.assertEqual(self.visit(chapter, *left), self.visit(chapter, *right))

    def test_quest_work_stays_between_pickup_and_reward(self):
        for chapter, quest_ids in (
            ("30-40/01-hillsbrad-foothills", [562, 555, 563]),
            ("30-40/02-desolace", [1437, 1458, 1459, 1465, 1438]),
            ("30-40/03-ashenvale", [1031, 98418, 1011, 1012, 1140]),
            ("30-40/04-stranglethorn-vale", [577, 616, 578, 213]),
            ("30-40/05-arathi-highlands", [1389, 1393, 1421]),
            ("30-40/06-badlands", [1455, 5501]),
            ("40-50/01-stranglethorn-vale", [608]),
            ("40-50/02-badlands", [2988, 2880, 2881]),
        ):
            for quest in quest_ids:
                with self.subTest(chapter=chapter, quest=quest):
                    actions = [q["t"] for _, q in self.goals(chapter) if q.get("quest") == quest]
                    self.assertEqual(actions[0], "accept")
                    self.assertEqual(actions[-1], "turnin")
                    self.assertEqual((actions.count("accept"), actions.count("turnin")), (1, 1))
        swamp = "30-40/05-arathi-highlands"
        self.assertEqual(self.visit(swamp, 1421, "collect") + 1, self.visit(swamp, 1393, "accept"))
        self.assertLess(self.visit(swamp, 1393, "complete"), self.visit(swamp, 1421, "turnin"))
        peak = [q.get("quest") for i, q in self.goals("40-50/02-badlands") if i == 14]
        self.assertEqual(peak, [2880, 2881, 2881, 2988, None])

    def test_low_yield_branches_are_complete_and_materials_preserve_rewards(self):
        chapter = "30-40/04-stranglethorn-vale"
        pages = [q for _, q in self.goals(chapter) if q.get("quest") in range(338, 343)]
        self.assertEqual(len(pages), 14)
        self.assertTrue(all(q["levelingDetour"] for q in pages))
        self.assertFalse(any(q.get("levelingDetour") for _, q in self.goals(chapter) if q.get("quest") == 192))
        for chapter, quest, material in (
            ("30-40/06-badlands", 716, {"2868": 1}),
            ("40-50/01-stranglethorn-vale", 1203, {"3853": 1}),
            ("40-50/02-badlands", 2881, {"9259": 5}),
            ("40-50/03-feralas", 7735, {"18969": 1}),
        ):
            with self.subTest(quest=quest):
                goals = [q for _, q in self.goals(chapter) if q.get("quest") == quest]
                self.assertEqual([q["t"] for q in goals], ["accept", "turnin"])
                self.assertTrue(all(q["levelingDetour"] and q["detourItems"] == material for q in goals))
        feralas = [q for _, q in self.goals("40-50/03-feralas")]
        dungeon = next(q for q in feralas if q.get("text") == "Zul'Farrak")
        self.assertTrue(dungeon["levelingDetour"])
        level = next(q for q in feralas if q["t"] == "level")
        self.assertEqual(level["level"], 45)
        self.assertFalse(level.get("levelingDetour"))
        self.assertTrue(all(q["minLevel"] == 45 for q in feralas if q.get("quest") in (7003, 7721) and q["t"] == "accept"))

    def test_lethlor_level_gate_and_rare_drop_are_independent(self):
        goals = [q for _, q in self.goals("40-50/02-badlands")]
        grind = next(q for q in goals if q["t"] == "level")
        self.assertEqual((grind["level"], grind["map"], grind["x"], grind["y"], grind["f"]), (43, 1418, 71.2, 52.7, "e"))
        self.assertFalse(grind.get("levelingDetour"))
        start, heart, reward = [q for q in goals if q.get("quest") == 706]
        self.assertFalse(start.get("levelingDetour"))
        self.assertEqual([q["t"] for q in (start, heart, reward)], ["accept", "collect", "turnin"])
        self.assertTrue(all(q["levelingDetour"] and q["detourItems"] == {"4612": 1} for q in (heart, reward)))
        host = QuestEngineHost(catalog=True)
        host.initialize()
        route = ALLIANCE + "40-50/02-badlands"
        host.ns.char.activeGuide = route
        guide = host.ns.guides[route]
        progress = host.call("GetProgress", route)
        progress.cursor, progress.placed = 8, True
        host.quest(706, onQuest=True, complete=False)
        journal = primitive_copy(host.state.quests)
        host.state.level = 42
        self.assertEqual(host.status(guide.steps[8].goals[1], guide.steps[8], progress), "active")
        host.state.level = 43
        self.assertEqual(host.status(guide.steps[8].goals[1], guide.steps[8], progress), "done")
        self.assertEqual(host.status(guide.steps[8].goals[2], guide.steps[8], progress, 2), "skip")
        self.assertEqual(host.status(guide.steps[9].goals[1], guide.steps[9], progress), "skip")
        self.assertEqual(primitive_copy(host.state.quests), journal)
        host.quest(706, onQuest=True, complete=True)
        self.assertEqual(host.status(guide.steps[9].goals[1], guide.steps[9], progress), "active")

    def test_enrichment_reimports_from_unmarked_goals_and_is_idempotent(self):
        total = 0
        for chapter in DETOURS:
            with self.subTest(chapter=chapter):
                guide = copy.deepcopy(self.guides[chapter])
                original_goals = list(q for _, q in self.goals(chapter))
                document = {"guides": [guide]}
                goals = [q for step in guide["steps"] for q in step["goals"]]
                for goal in goals:
                    for field in ("levelingDetour", "detourItems", "detourQuest"):
                        goal.pop(field, None)
                apply_mid_detours(document)
                for goal, original in zip(goals, original_goals, strict=True):
                    if goal.get("levelingDetour"):
                        self.assertEqual(goal, original)
                        total += 1
                first = copy.deepcopy(guide)
                apply_mid_detours(document)
                self.assertEqual(guide, first)
        self.assertEqual(total, 42)  # Includes the pickup, five kodo returns and hand-in at Smeed.

    def test_saved_booty_bay_cursor_revisits_uncollected_offers_with_marks_intact(self):
        route = ALLIANCE + "30-40/04-stranglethorn-vale"
        saved = {"seen": True, "auto": False, "activeGuide": route,
                 "progress": {route: {"cursor": 24, "routeRevision": 1, "placed": True, "review": True,
                                      "skipped": {"24:3": True}, "confirmed": {"22:1": True}}}}
        host = MigrationHost(saved, {577: {"onQuest": True, "complete": True}, 575: {"delivered": True}})
        before = primitive_copy(host.state.quests)
        host.state.level = 36
        host.initialize()
        state = host.ns.char.progress[route]
        self.assertEqual(state.cursor, 22)
        self.assertEqual(state.routeRevision, 2)
        self.assertEqual(primitive_copy(state.skipped), {"22:6": True})
        self.assertEqual(primitive_copy(state.confirmed), {"22:1": True})
        goal = host.ns.guides[route].steps[22].goals[6]
        self.assertEqual((goal.quest, goal.t), (616, "accept"))
        self.assertEqual(primitive_copy(host.state.quests), before)
        self.assertEqual(host.ns.char.guideMigrationBackups[route + ":2"].progress.cursor, 24)
