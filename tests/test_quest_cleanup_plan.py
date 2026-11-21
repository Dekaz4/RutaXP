import unittest

from test_addon import ADDON
from test_quest_engine import QuestEngineHost


def step(*goals, **fields):
    return {"title": "Visita", "goals": list(goals), **fields}


def goal(q, t="turnin", **fields):
    return {"t": t, "quest": q, **fields}


class QuestCleanupPlanTests(unittest.TestCase):
    def setUp(self):
        self.h = QuestEngineHost()
        self.h.load((ADDON / "QuestCleanupPlan.lua").read_text(encoding="utf-8"), "RutaXP", self.h.ns)
        self.h.ns.GetQuestCleanupJournal = self.h.lua.eval("function() return TEST.log, TEST.errorText end")
        self.h.ns.QuestCleanupData = self.h.table({"ordinary": {}, "prerequisites": {}})

    def start(self, *steps, **fields):
        self.h.guide("route", steps=list(steps), **fields)
        self.h.initialize()
        self.h.ns.char.activeGuide = "route"
        self.h.ns.char.auto = False
        self.h.call("GetProgress", "route").cursor = 1

    def journal(self, *quests):
        rows = []
        for entry in quests:
            fields = {"id": entry} if isinstance(entry, int) else entry
            q = fields["id"]
            self.h.quest(q, onQuest=True, complete=fields.get("complete", False))
            rows.append({"id": q, "title": f"Misión {q}", "canAbandon": True, **fields})
        self.h.state.log = self.h.table(rows)

    def ids(self):
        plan = self.h.call("GetQuestCleanupPlan")
        self.assertEqual(plan.guideID, "route")
        return tuple({row.id for row in plan[key].values()} for key in ["candidates", "kept", "review"])

    def test_all_reachable_branches_and_saved_cursors_and_character_conditions(self):
        self.h.guide("left", [step(goal(9)), step(goal(2))], next="join")
        self.h.guide("right", [step(goal(3))], next="join")
        self.h.guide("join", [step(goal(4))])
        self.h.guide("wrong", [step(goal(5))], faction="Horde")
        self.start(step(goal(6)), step(goal(1), goal(7, only={"classes": ["MAGE"]})),
                   nextChoices=["left", "right", "wrong"])
        self.h.call("GetProgress", "route").cursor = 2
        self.h.call("GetProgress", "left").cursor = 2
        self.h.call("GetProgress", "join").cursor = 1
        self.h.ns.QuestCleanupData.ordinary = self.h.table({q: True for q in range(1, 10)})
        self.journal(*range(1, 11))
        self.assertEqual(self.ids(), ({5, 6, 7, 8, 9}, {1, 2, 3, 4}, {10}))

    def test_transitive_prerequisites_or_and_parent_and_external_quest_data(self):
        self.h.guide("elsewhere", [step(goal(20, "accept", pre=[-19, 17]))])
        self.start(step(goal(22, "accept", parent=21, preAll=[20])))
        self.h.ns.QuestCleanupData.prerequisites = self.h.table({19: [10], 10: [19], 17: [11], 30: [13]})
        self.h.ns.QuestCleanupData.ordinary = self.h.table({q: True for q in [10, 11, 12, 13, 21]})
        self.journal(10, 11, 12, 13, 21, 30)
        self.assertEqual(self.ids(), ({12}, {10, 11, 13, 21}, {30}))

    def test_reviewed_detours_toggle_and_carried_ordinary_optional(self):
        self.start(step(goal(1, levelingDetour=True), goal(2, optional=True),
                        goal(3, group=True), goal(4, "collect", levelingDetour=True, detourItems={400: 1})))
        self.h.lua.execute("function GetItemCount(id) return id == 400 and 1 or 0 end")
        self.journal(1, 2, 3, 4)
        self.assertEqual(self.ids(), ({1, 3}, {2, 4}, set()))
        self.h.ns.char.optional = True
        self.h.ns.char.includeGroupQuests = True
        self.assertEqual(self.ids(), (set(), {1, 2, 3, 4}, set()))

    def test_live_state_class_rewards_professions_items_and_branches_override_ordinary(self):
        self.start(step(goal(90)))
        self.h.guide("past", [step(goal(5, only={"classes": ["WARRIOR"]}),
                                   goal(6, "accept", item=400), goal(7, "accept", profLine=185),
                                   goal(8, "accept", closedBy=[9]))])
        self.h.ns.QuestCleanupData.ordinary = self.h.table({q: True for q in range(1, 11)})
        self.h.ns.GetLevelingQuestRewardInfo = self.h.lua.eval("function(_,id) if id==10 then return 'Arma' end end")
        self.journal({"id": 1, "complete": True}, {"id": 2, "hasProgress": True},
                     {"id": 3, "canAbandon": False}, {"id": 4, "protectedReason": "Evento"},
                     5, 6, 7, 8, 9, 10)
        self.assertEqual(self.ids(), (set(), set(range(1, 11)), set()))

    def test_configured_duo_can_clean_personal_log_and_preserves_shared_quests(self):
        self.start(step(goal(1)))
        self.h.ns.QuestCleanupData.ordinary = self.h.table({2: True, 3: True})
        self.h.ns.char.duo = self.h.table({"enabled": True})
        self.h.ns.Duo = self.h.lua.eval("{GetPartnerQuest=function(_,q) if q==2 then return {state=1} end end}")
        self.journal(1, 2, 3)
        self.assertEqual(self.ids(), ({3}, {1, 2}, set()))

    def test_unreadable_journal_incomplete_links_or_recovery_make_no_plan(self):
        self.start(step(goal(1)), next="missing")
        self.journal(1)
        self.assertIsNone(self.h.call("GetQuestCleanupPlan")[0])
        self.h.ns.guides.route.next = None
        self.h.ns.guides.route.recovery = True
        self.assertIsNone(self.h.call("GetQuestCleanupPlan")[0])
        self.h.ns.guides.route.recovery = False
        self.h.state.log = None
        self.h.state.errorText = "Diario no disponible."
        self.assertEqual(self.h.call("GetQuestCleanupPlan"), (None, "Diario no disponible."))

    def test_shipping_desolace_human_rogue_keeps_scorpions_ears_and_escort_delivery(self):
        h = self.h
        for filename in ["Leveling.lua", "GroupQuestData.lua", "QuestCleanupData.lua",
                         "RogueRewardData.lua", "RogueRewards.lua"]:
            h.load((ADDON / filename).read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.state.classToken = "ROGUE"
        h.state.level = 33
        guide_id = "forever/alliance/30-40/02-desolace"
        h.initialize()
        h.ns.char.activeGuide = guide_id
        h.call("GetProgress", guide_id).cursor = 14
        self.journal(1459, 1387, 1440, {"id": 5561, "complete": True})
        plan = h.call("GetQuestCleanupPlan")
        self.assertEqual({row.id for row in plan.kept.values()}, {1459, 1387, 1440, 5561})
        self.assertEqual(len(plan.candidates), 0)


if __name__ == "__main__":
    unittest.main()
