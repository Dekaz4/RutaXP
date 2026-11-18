"""Solo route decisions from Forever data and observed journal state."""
import unittest

from test_addon import ADDON
from test_quest_engine import QuestEngineHost


class SoloQuestTests(unittest.TestCase):
    def host(self, catalog=False):
        h = QuestEngineHost(catalog=catalog)
        for file in ("GroupQuestData", "QuestOfferAdvice", "TrackerPreview", "Navigation"):
            h.load((ADDON / (file + ".lua")).read_text(encoding="utf8"), "RutaXP", h.ns)
        h.ns.UpdateNavigation = None  # exercise the real destination selector without drawing textures
        return h

    def test_golm_to_next_solo_objective_with_real_catalog(self):
        h = self.host(catalog=True)
        h.initialize()
        h.state.level = 30
        h.ns.char.auto = False
        guide_id = "forever/alliance/30-40/01-hillsbrad-foothills"
        h.call("SelectGuide", guide_id)
        guide, _, state = h.call("GetCurrent")
        steps = list(guide.steps.values())
        golm = next(i for i, step in enumerate(steps, 1) if step.title == "Golm")
        for q in (98310, 98283, 98297, 98072):
            h.quest(q, onQuest=True, complete=False)
        h.quest(98216, delivered=True)
        state.cursor, state.review, state.placed = golm, None, True
        h.ns.char.auto = True
        h.call("Sync")
        goal = h.active()[0]
        self.assertEqual(goal.quest, 98072)
        h.lua.execute("C_Map.GetMapPosFromWorldPos=function(_,_,map) return map,{GetXY=function() return .6,.45 end} end")
        self.assertEqual(h.call("GetBaseStepWaypoint", guide.steps[state.cursor]).goal.quest, 98072)
        self.assertGreater(state.cursor, golm)
        self.assertTrue(h.call("IsQuestActive", 98310))
        self.assertFalse(h.call("IsQuestDelivered", 98310))
        self.assertFalse(state.skipped and list(state.skipped.keys()))
        self.assertFalse(list(state.confirmed.keys()))
        previews = h.call("GetTrackerPlannedUpcomingItems", guide, golm-1, 12)
        self.assertFalse(any(x.questID in (98310, 98283, 98297, 98300, 98313) for x in previews.values()))
        resumed, _ = h.call("ResumeGroupQuests")
        self.assertTrue(resumed)
        self.assertTrue(h.ns.char.includeGroupQuests)
        self.assertIn(h.active()[0].quest, (98310, 98283, 98297))
        h.call("SetIncludeGroupQuests", False)
        self.assertEqual(h.active()[0].quest, 98072)

    def test_verified_completion_allows_delivery_and_then_unblocks_child(self):
        h = self.host()
        h.group([{"t":"turnin","quest":98310}, {"t":"accept","quest":98313,"preAll":[98310]}],
                next_goals=[{"t":"accept","quest":44444}])
        h.quest(98310, onQuest=True, complete=True)
        h.initialize()
        self.assertEqual(h.active()[0].quest, 98310)
        self.assertTrue(h.call("WantsQuest", "turnin", 98310))
        self.assertFalse(h.call("WantsQuest", "accept", 98313))
        h.quest(98310, delivered=True)
        h.fire("QUEST_TURNED_IN", 98310)
        self.assertEqual(h.active()[0].quest, 98313)
        self.assertTrue(h.call("WantsQuest", "accept", 98313))

    def test_followups_skip_only_when_every_possible_path_requires_group(self):
        h = self.host()
        h.group([{"t":"accept","quest":101,"preAll":[98310]},
                 {"t":"accept","quest":102,"pre":[101,98297]},
                 {"t":"accept","quest":103,"pre":[101,111]},
                 {"t":"accept","quest":104,"parent":98310},
                 {"t":"accept","quest":105,"preAll":[106]},
                 {"t":"accept","quest":106,"preAll":[105]}])
        h.initialize()
        _, step, s = h.call("GetCurrent")
        statuses = lambda: [h.status(step.goals[i], step, s, i) for i in range(1, 7)]
        self.assertEqual(statuses(), ["skip","skip","blocked","skip","blocked","blocked"])
        h.quest(111, delivered=True)
        h.quest(98310, onQuest=True)
        h.quest(101, onQuest=True)
        self.assertEqual(statuses()[:4], ["done","blocked","active","active"])

    def test_only_positive_difficulty_or_group_evidence_qualifies(self):
        h = self.host()
        h.group([{"t":"accept","quest":99901,"qlvl":60},
                 {"t":"accept","quest":99902}, {"t":"accept","quest":99903},
                 {"t":"accept","quest":99904}, {"t":"accept","quest":99905}])
        h.lua.execute("""
            C_QuestLog.GetQuestTagInfo=function(id)
                if id==99902 then return {tagID=81} elseif id==99903 then return {tagID=41} end
                if id==99905 then error('restricted') end
            end
            C_QuestLog.GetSuggestedGroupSize=function(id) return id==99904 and 3 or 0 end
            function IsInGroup() return true end
        """)
        h.initialize()
        _, step, s = h.call("GetCurrent")
        self.assertEqual([h.status(step.goals[i], step, s, i) for i in range(1, 6)],
                         ["active","skip","active","skip","active"])
        self.assertFalse(h.call("WantsQuest","accept",99902))
        self.assertEqual(h.call("GetQuestOfferAdvice",99902)[1],"opcional")
        h.call("SetIncludeGroupQuests",True)
        self.assertTrue(h.call("WantsQuest","accept",99902))

    def test_repeated_group_reads_reuse_metadata_until_new_data_or_retry(self):
        h = self.host()
        h.group([{"t": "accept", "quest": 99931}])
        h.initialize()
        h.lua.execute("""
            TEST.clock, TEST.tagCalls, TEST.sizeCalls, TEST.ready = 50, 0, 0, {}
            function GetTime() return TEST.clock end
            function C_QuestLog.GetQuestTagInfo(id)
                TEST.tagCalls = TEST.tagCalls + 1
                if TEST.ready[id] then return {tagID=81} end
            end
            function C_QuestLog.GetSuggestedGroupSize() TEST.sizeCalls = TEST.sizeCalls + 1 end
        """)
        # These IDs aren't yet in the journal. Redrawing the arrow and panel
        # mustn't re-query missing client data for every occurrence.
        for _ in range(20):
            for quest in (99932, 99933):
                self.assertFalse(h.call("IsGroupQuest", quest))
        self.assertEqual((h.state.tagCalls, h.state.sizeCalls), (2, 2))
        h.state.ready[99932] = True
        h.fire("QUEST_DATA_LOAD_RESULT", 99932, True)
        before = h.state.tagCalls
        for _ in range(5):
            self.assertTrue(h.call("IsGroupQuest", 99932))
            self.assertFalse(h.call("IsGroupQuest", 99933))
        self.assertEqual(h.state.tagCalls, before + 1)
        h.state.clock += 11
        h.state.ready[99933] = True
        self.assertTrue(h.call("IsGroupQuest", 99933))
        self.assertEqual(h.state.tagCalls, before + 2)

    def test_old_single_goal_guides_defer_without_persisting_skip(self):
        h = self.host()
        h.guide(steps=[{"title":"Optional dungeon","action":"accept","questID":704},
                       {"title":"Solo","action":"accept","questID":99999}])
        h.initialize()
        self.assertEqual(h.cursor(), 2)
        self.assertTrue(h.call("ResumeGroupQuests")[0])
        self.assertEqual(h.cursor(), 1)

    def test_explicit_group_hunt_and_dungeon_without_quest_keep_unrelated_services(self):
        h = self.host()
        h.group([{"t":"kill","group":{"kind":"group"}},
                 {"t":"collect","quest":98310}, {"t":"train","npc":27}],
                next_goals=[{"t":"accept","quest":88000}])
        h.initialize()
        self.assertEqual(h.cursor("grouped"), 1)
        self.assertEqual(h.active()[0].t, "train")
        h.call("Next")
        self.assertEqual(h.active()[0].quest, 88000)
        h.guide(id="dungeon", steps=[{"title":"Entrar","group":{"kind":"dungeon"}},
                                     {"title":"Visita al vendedor","action":"vendor"}])
        h.call("SelectGuide", "dungeon")
        self.assertEqual(h.cursor("dungeon"), 2)
