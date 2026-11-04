"""Opt-in prerequisite recovery against real Core/QuestEngine/Recovery Lua."""

import unittest

from test_addon import ADDON
from test_quest_engine import QuestEngineHost


class RecoveryHost(QuestEngineHost):
    def load_recovery(self):
        self.load((ADDON / "Recovery.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.ns)
        self.recovery = self.ns.Recovery

    def ready(self):
        self.initialize()
        self.recovery.Initialize(self.recovery)

    def blockers(self):
        return self.recovery.GetBlockers(self.recovery)

    def start(self, which=1):
        return self.recovery.Start(self.recovery, which)

    def status(self):
        return self.recovery.GetStatus(self.recovery)

    def source(self, ids, id="source", prereqs=None, **fields):
        prereqs = prereqs or {}
        steps = [
            {"title": "Accept at the camp", "goals": [
                {"t": "accept", "quest": q, "title": f"Quest {q}", "npc": q + 1000,
                 "npcName": f"Giver {q}", "map": 1436, "x": 10 + i, "y": 20,
                 **prereqs.get(q, {})} for i, q in enumerate(ids)
            ]},
            {"title": "Complete the camp objectives", "note": "Follow the authored camp route.", "goals": [
                {"t": "kill", "quest": q, "oi": 1, "title": f"Work {q}", "map": 1436, "x": 30 + i, "y": 40}
                for i, q in enumerate(ids)
            ]},
            {"title": "Return to the camp", "goals": [
                {"t": "turnin", "quest": q, "title": f"Quest {q}", "npc": q + 1000,
                 "npcName": f"Giver {q}", "map": 1436, "x": 10 + i, "y": 20}
                for i, q in enumerate(ids)
            ]},
        ]
        return self.guide(id, steps=steps, **fields)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.h = RecoveryHost()
        self.h.load_recovery()

    def main(self, **goal):
        self.h.group([{"t": "accept", "quest": 900, "title": "Blocked follow-up", **goal}], id="main")

    def test_preview_two_required_quests_keeps_route_and_authored_order_unchanged(self):
        h = self.h
        self.main(preAll=[101, 102])
        source = h.source([101, 102])
        h.ready()
        h.lua.execute("function MutationProbe(self, goal) goal._rxpSpot = 777; return {mapID=1436,x=.1,y=.2} end")
        h.ns.GetGoalWaypoint = h.globals.MutationProbe
        entries = h.blockers()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[1].kind, "prerequisite")
        self.assertEqual(h.ns.char.activeGuide, "main")
        self.assertIsNone(h.ns.char.recovery)
        self.assertEqual(list(entries[1].missingQuestIDs.values()), [101, 102])
        steps = entries[1].plan.steps
        self.assertEqual(len(steps), 3)
        self.assertEqual([steps[1].goals[i].quest for i in [1, 2]], [101, 102])
        self.assertEqual(steps[2].goals[1].t, "kill")
        self.assertEqual(steps[3].goals[2].t, "turnin")
        self.assertIsNone(source.steps[1].goals[1]._rxpSpot)

    def test_start_and_real_delivery_restore_exact_bookmark_without_erasing_progress(self):
        h = self.h
        self.main(preAll=[101, 102])
        h.source([101, 102])
        h.ready()
        original = h.call("GetProgress", "main")
        original.review = True
        original.confirmed["8:2"] = True
        original.skipped = h.lua.table()
        original.skipped["9:3"] = True
        self.assertTrue(h.start()[0])
        self.assertEqual(h.ns.char.activeGuide, "_recovery")
        h.quest(101, onQuest=True)
        h.quest(102, onQuest=True)
        h.call("Sync")
        self.assertEqual(h.cursor("_recovery"), 2)
        h.quest(101, onQuest=True, complete=True)
        h.quest(102, onQuest=True, complete=True)
        h.call("Sync")
        self.assertEqual(h.cursor("_recovery"), 3)
        h.fire("QUEST_TURNED_IN", 101)
        self.assertEqual(h.ns.char.activeGuide, "_recovery")
        h.fire("QUEST_TURNED_IN", 102)
        self.assertEqual(h.ns.char.activeGuide, "main")
        self.assertIsNone(h.ns.char.recovery)
        self.assertEqual(original.cursor, 1)
        self.assertTrue(original.review)
        self.assertTrue(original.confirmed["8:2"])
        self.assertTrue(original.skipped["9:3"])
        self.assertEqual(h.status().status, "completed")

    def test_cancel_restores_original_review_and_manual_markers(self):
        h = self.h
        self.main(pre=[101])
        h.source([101])
        h.ready()
        original = h.call("GetProgress", "main")
        original.review = True
        original.skipped = h.lua.table()
        original.confirmed["4:1"], original.skipped["5:1"] = True, True
        h.start()
        h.call("Next")
        ok, _ = h.recovery.Cancel(h.recovery)
        self.assertTrue(ok)
        self.assertEqual(h.ns.char.activeGuide, "main")
        self.assertEqual(original.cursor, 1)
        self.assertTrue(original.review)
        self.assertTrue(original.confirmed["4:1"])
        self.assertTrue(original.skipped["5:1"])
        self.assertIsNone(h.ns.guides["_recovery"])

    def test_or_chooses_the_shortest_available_authored_chain(self):
        h = self.h
        self.main(pre=[101, 201])
        h.source([101, 102], prereqs={101: {"preAll": [102]}})
        h.source([201], id="short")
        h.ready()
        entry = h.blockers()[1]
        self.assertEqual(list(entry.requiredQuestIDs.values()), [201])
        self.assertEqual(entry.plan.steps[1].goals[1].quest, 201)
        self.assertEqual(h.ns.char.activeGuide, "main")

    def test_delivered_or_alternative_does_not_create_an_unnecessary_recovery(self):
        h = self.h
        self.main(pre=[101, 201])
        h.source([201])
        h.quest(101, delivered=True)
        h.ready()
        self.assertEqual(len(h.blockers()), 0)
        self.assertFalse(h.start()[0])
        self.assertEqual(h.ns.char.activeGuide, "main")

    def test_missing_or_branch_can_fall_back_to_a_known_branch(self):
        h = self.h
        self.main(pre=[404, 201])
        h.source([201])
        h.ready()
        self.assertEqual(list(h.blockers()[1].requiredQuestIDs.values()), [201])

    def test_unknown_prerequisite_uses_its_authored_title_for_the_manual_hint(self):
        h = self.h
        self.main(pre=[404], preTitles={404: "The missing courier"})
        h.ready()
        entry = h.blockers()[1]
        self.assertIn("The missing courier", entry.reason)
        self.assertEqual(entry.missingQuestTitles[404], "The missing courier")
        self.assertFalse(h.start()[0])

    def test_cycles_unknown_quests_and_missing_objectives_never_swap_the_route(self):
        h = self.h
        self.main(pre=[101])
        h.source([101, 102], prereqs={101: {"pre": [102]}, 102: {"pre": [101]}})
        h.ready()
        self.assertIn("ciclo", h.blockers()[1].reason)
        self.assertFalse(h.start()[0])
        self.assertEqual(h.ns.char.activeGuide, "main")
        h.ns.guides.source = None
        self.assertIn("No hay", h.blockers()[1].reason)
        self.assertFalse(h.start()[0])
        h.guide("incomplete", steps=[{"title": "Incomplete source", "goals": [
            {"t": "accept", "quest": 101}, {"t": "turnin", "quest": 101}
        ]}])
        self.assertIn("objetivos", h.blockers()[1].reason)
        self.assertFalse(h.start()[0])

    def test_wrong_race_class_or_faction_cannot_supply_recovery_actions(self):
        h = self.h
        self.main(preAll=[101, 102, 103])
        h.source([101], id="race", races=["NightElf"])
        h.source([102], id="class", classes=["MAGE"])
        h.source([103], id="faction", faction="Horde")
        h.ready()
        self.assertIsNone(h.blockers()[1].plan)
        self.assertFalse(h.start()[0])
        self.assertEqual(h.ns.char.activeGuide, "main")

    def test_level_blocker_gives_a_reason_instead_of_an_impossible_miniguide(self):
        h = self.h
        self.main(pre=[101], minLevel=10)
        h.source([101])
        h.ready()
        entry = h.blockers()[1]
        self.assertEqual(entry.kind, "level")
        self.assertEqual(entry.requiredLevel, 10)
        self.assertIsNone(entry.plan)
        self.assertFalse(h.start()[0])
        self.assertEqual(h.ns.char.activeGuide, "main")

    def test_abandoned_required_quest_proposes_its_real_acceptance_again(self):
        h = self.h
        h.source([101], id="main")
        h.ready()
        state = h.call("GetProgress", "main")
        state.cursor = 2
        h.call("Sync")
        self.assertEqual(h.active()[2], "blocked")
        entry = h.blockers()[1]
        self.assertEqual(entry.kind, "missing_quest")
        self.assertEqual(entry.action, "accept")
        self.assertTrue(h.start()[0])
        self.assertEqual(h.ns.guides["_recovery"].steps[1].goals[1].quest, 101)

    def test_skipping_miniguide_steps_does_not_claim_the_prerequisite_was_delivered(self):
        h = self.h
        self.main(pre=[101])
        h.source([101])
        h.ready()
        h.start()
        for _ in range(3): h.call("Next")
        self.assertEqual(h.ns.char.activeGuide, "_recovery")
        self.assertEqual(h.status().status, "incomplete")
        self.assertFalse(h.status().canResume)
        self.assertFalse(h.recovery.Resume(h.recovery)[0])
        self.assertFalse(h.call("IsQuestDelivered", 101))

    def test_reload_registers_saved_miniguide_before_active_guide_validation(self):
        h = self.h
        self.main(pre=[101])
        h.source([101])
        h.ready()
        h.start()
        h.quest(101, onQuest=True)
        h.call("Sync")
        self.assertEqual(h.cursor("_recovery"), 2)
        h.new_namespace()
        h.load_recovery()
        self.main(pre=[101])
        h.source([101])
        # Core calls this hook after binding SavedVariables and before deciding
        # that an unknown active guide needs to be replaced by a recommendation.
        h.ns.char, h.ns.db = h.globals.RutaXPCharDB, h.globals.RutaXPDB
        self.assertTrue(h.recovery.RestoreSaved(h.recovery))
        h.ready()
        self.assertEqual(h.ns.char.activeGuide, "_recovery")
        self.assertEqual(h.cursor("_recovery"), 2)
        self.assertEqual(h.status().bookmark.guideID, "main")
        self.assertTrue(h.recovery.Cancel(h.recovery)[0])
        self.assertEqual(h.ns.char.activeGuide, "main")

    def test_completed_original_goal_keeps_exact_bookmark_when_review_was_enabled(self):
        h = self.h
        h.source([101], id="main")
        h.ready()
        state = h.call("GetProgress", "main")
        state.cursor, state.review = 3, True
        h.start()
        h.fire("QUEST_TURNED_IN", 101)
        self.assertEqual(h.ns.char.activeGuide, "main")
        self.assertEqual(state.cursor, 3)
        self.assertTrue(state.review)

    def test_completed_original_goal_autoadvances_only_from_real_delivery(self):
        h = self.h
        h.source([101], id="main")
        h.ready()
        state = h.call("GetProgress", "main")
        state.cursor = 3
        h.start()
        h.fire("QUEST_TURNED_IN", 101)
        self.assertEqual(h.ns.char.activeGuide, "main")
        self.assertEqual(state.cursor, 4)
        self.assertIsNone(state.review)

    def test_dependency_order_wins_when_a_route_cut_lists_acceptance_too_early(self):
        h = self.h
        self.main(pre=[101])
        h.source([101, 102], prereqs={101: {"preAll": [102]}})
        h.ready()
        steps = h.blockers()[1].plan.steps
        actions = [(g.t, g.quest) for _, step in steps.items() for _, g in step.goals.items()]
        self.assertLess(actions.index(("turnin", 102)), actions.index(("accept", 101)))

    def test_deep_chain_has_a_bounded_manual_explanation(self):
        h = self.h
        self.main(pre=[100])
        ids = list(range(100, 130))
        h.source(ids, prereqs={q: {"pre": [q + 1]} for q in ids[:-1]})
        h.ready()
        entry = h.blockers()[1]
        self.assertIsNone(entry.plan)
        self.assertIn("límite", entry.reason)
        self.assertFalse(h.start()[0])

    def test_invalid_saved_sequence_does_not_resume_as_completed_and_can_be_cancelled(self):
        h = self.h
        self.main(pre=[101])
        h.source([101])
        h.ready()
        h.start()
        h.ns.char.recovery.requiredQuestIDs = "corrupt"
        self.assertFalse(h.recovery.RestoreSaved(h.recovery))
        self.assertFalse(h.recovery.Resume(h.recovery)[0])
        self.assertFalse(h.status().canResume)
        self.assertTrue(h.recovery.Cancel(h.recovery)[0])
        self.assertEqual(h.ns.char.activeGuide, "main")

    def test_saved_recovery_contains_only_savedvariables_compatible_values(self):
        h = self.h
        self.main(pre=[101])
        source = h.source([101])
        source.steps[1].goals[1].callback = h.lua.eval("function() end")
        h.ready()
        h.start()
        serializable = h.lua.eval(r"""function(value)
            local function check(item)
                local t = type(item)
                if t == "nil" or t == "boolean" or t == "string" or t == "number" then return true end
                if t ~= "table" then return false end
                for key, child in pairs(item) do
                    if (type(key) ~= "number" and type(key) ~= "string") or not check(child) then return false end
                end
                return true
            end
            return check(value)
        end""")
        self.assertTrue(serializable(h.ns.char.recovery))
        self.assertIsNone(h.ns.char.recovery.guide.steps[1].goals[1].callback)


if __name__ == "__main__":
    unittest.main()
