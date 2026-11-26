"""Choose actual Forever chapter rows without changing a character's saved step."""
import unittest

from test_access_navigation import ADDON, AccessHost
from test_guide_singing_shards import GUIDE, HORDE


class LocalCircuitTests(unittest.TestCase):
    def host(self, guide=GUIDE, **kwargs):
        h = AccessHost(guide, **kwargs)
        if not h.ns.circuitCreatures:
            h.h.lua.execute((ADDON / "CircuitCreatureData.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        if not h.ns.LocalCircuit:
            h.h.lua.execute((ADDON / "LocalCircuit.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        h.ns.char.auto, h.s.level = True, 35
        if guide == HORDE:
            h.s.faction, h.s.raceToken = "Horde", "Orc"
        h.state = h.ns.char.progress[guide]
        h.state.confirmed = h.h.table({})
        h.h.lua.execute("""
            TEST.verdict = true
            ACCESS_NS.CircuitTerrain = {Check=function()
                TEST.comparisons = (TEST.comparisons or 0) + 1
                return TEST.verdict
            end}
        """)
        return h

    def active(self, h, quest, done=0, total=10, ready=False, objective_index=1):
        objectives = [
            {"finished": False, "numFulfilled": 0, "numRequired": total}
            for _ in range(objective_index)
        ]
        objectives[-1]["numFulfilled"] = done
        objectives[-1]["finished"] = ready
        h.s.quests[quest] = h.h.table({"onQuest": True, "complete": ready, "objectives": objectives})
        h.ns.LocalCircuit.Invalidate(h.ns.LocalCircuit)

    def choose(self, h, si, gi, base_status="active"):
        h.state.cursor = si
        step = h.guide.steps[si]
        return h.ns.LocalCircuit.Choose(h.ns.LocalCircuit, h.guide, step, h.state, step.goals[gi], gi, base_status)

    def test_raptors_on_the_way_hold_through_updates_and_reload(self):
        h = self.host(find_goal={"quest": 191, "t": "kill"}, x=.266, y=.168)
        self.active(h, 191)
        self.active(h, 194, 8)
        self.active(h, 605, 0)
        selected = self.choose(h, 13, 1)
        self.assertEqual((selected.goal.quest, selected.reason), (194, "Te faltan 2 bajas de camino"))
        self.assertFalse(selected.authored)
        self.assertEqual(h.state.cursor, 13)
        h.s.x, h.s.y = .285, .163  # The original panther now appears closer.
        self.active(h, 194, 9)
        h.h.lua.execute((ADDON / "LocalCircuit.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        resumed = self.choose(h, 13, 1)
        self.assertEqual((resumed.goal.quest, resumed.reason), (194, "Te falta una baja de camino"))
        h.s.quests[194] = h.h.table({"delivered": True})
        self.active(h, 191)
        replacement = self.choose(h, 13, 1)
        self.assertTrue(replacement is None or replacement.goal.quest != 194)

    def test_no_detour_if_terrain_unconfirmed_or_too_expensive(self):
        for verdict in (False, None):
            with self.subTest(verdict=verdict):
                h = self.host(find_goal={"quest": 191, "t": "kill"}, x=.24, y=.168)
                self.active(h, 191)
                self.active(h, 194, 8)
                h.s.verdict = verdict
                result = self.choose(h, 13, 1)
                self.assertTrue(result is None or result.authored)
                self.assertEqual(h.s.comparisons, 1)
                self.assertEqual(h.state.cursor, 13)

    def test_early_nesingwary_visit_collects_both_ready_turnins(self):
        h = self.host(find_goal={"quest": 191, "t": "kill"}, x=.3565, y=.107)
        self.active(h, 195, 10, ready=True)
        self.active(h, 188, 1, 1, ready=True)
        selected = self.choose(h, 16, 1, "manual")  # Authored departure for Booty Bay.
        self.assertIn(selected.goal.quest, (195, 188))
        self.assertEqual(selected.goal.t, "turnin")
        self.assertIn("una sola visita", selected.reason)
        h.s.quests[selected.goal.quest] = h.h.table({"delivered": True})
        h.ns.LocalCircuit.Invalidate(h.ns.LocalCircuit)
        second = self.choose(h, 16, 1, "manual")
        self.assertEqual({selected.goal.quest, second.goal.quest}, {195, 188})
        h.ns.LocalCircuit.Defer(h.ns.LocalCircuit, h.guide, h.state, second)
        self.assertIsNone(self.choose(h, 16, 1, "manual"))
        self.assertEqual(h.state.cursor, 16)
        self.assertIsNone(h.state.skipped["19:1"])

    def test_same_mob_advances_both_horde_quests_even_when_distant_in_book(self):
        h = self.host(HORDE, find_goal={"quest":195, "t":"kill"}, x=.325, y=.239)
        self.active(h, 195)
        self.active(h, 568, 0, 15)
        selected = self.choose(h, h.step_index, 2)
        self.assertTrue(selected.authored)
        self.assertEqual(selected.goal.quest, 195)
        self.assertIn("La defensa de Grom'gol", selected.reason)

    def test_optional_pouches_are_incidental_to_the_tanaris_mages(self):
        h = self.host("forever/alliance/40-50/04-tanaris",
                      find_goal={"quest":1691, "npc":5617}, x=.588, y=.367)
        h.s.level = 45
        self.active(h, 1691, objective_index=3)
        self.active(h, 1878, 0, 5)
        selected = self.choose(h, h.step_index, 1)
        self.assertTrue(selected.authored)
        self.assertEqual(selected.goal.npc, 5617)
        self.assertIn("pueden dar botín", selected.reason)
        self.assertIn("Cazador de bolsas de agua", selected.reason)
        h.s.quests[1878] = h.h.table({})
        h.ns.LocalCircuit.Invalidate(h.ns.LocalCircuit)
        self.assertIsNone(self.choose(h, h.step_index, 1))

    def test_manual_omission_does_not_become_opportunistic_work(self):
        h = self.host(find_goal={"quest": 191, "t": "kill"}, x=.266, y=.168)
        self.active(h, 191)
        self.active(h, 194, 8)
        h.state.skipped["13:2"] = True
        self.assertIsNone(self.choose(h, 13, 1))

    def test_personal_progress_can_precede_or_follow_the_cursor_by_many_steps(self):
        for current in (5, 16):
            with self.subTest(current=current):
                h = self.host(find_goal={"quest":191, "t":"kill"}, x=.266, y=.168)
                self.active(h, 185)
                self.active(h, 194, 8)
                self.assertEqual(self.choose(h, current, 1).goal.quest, 194)
                h.state.skipped["13:2"] = True
                h.ns.LocalCircuit.Invalidate(h.ns.LocalCircuit)
                remaining = self.choose(h, current, 1)
                self.assertTrue(remaining is None or remaining.goal.quest != 194)
                self.assertEqual(h.state.cursor, current)

    def test_two_different_loot_items_from_the_same_forever_source(self):
        h = self.host("forever/alliance/human/01-elwynn-forest",
                      find_goal={"quest":47, "t":"collect"}, x=.4034, y=.8253)
        h.s.level = 8
        self.active(h, 47, total=10)
        self.active(h, 60, total=8)
        selected = self.choose(h, h.step_index, 2)
        self.assertTrue(selected.authored)
        self.assertEqual(selected.goal.item, 773)
        self.assertIn("Las velas de los kóbolds", selected.reason)
        self.assertIn("pueden dar botín", selected.reason)
        self.assertFalse(h.ns.IsQuestDelivered(h.ns,60))

    def test_easy_alternate_on_another_beach_does_not_make_the_primary_stop_safe(self):
        h = self.host("forever/alliance/03-darkshore", find_goal={"quest":983, "t":"collect"},
                      x=.3742, y=.4032)
        loot = h.step.goals[1]
        primary = h.ns.circuitCreatures[loot['from']]
        alternate = h.ns.circuitCreatures[loot.fromAlso]
        self.assertEqual((primary.min, primary.max, alternate.min, alternate.max), (20,21,9,10))
        self.active(h, 983, 4, 6)
        h.s.level = 15
        self.assertIsNone(self.choose(h, 1, 1, "manual"))
        h.s.level = 21
        chosen = self.choose(h, 1, 1, "manual")
        self.assertEqual((chosen.goal.quest, round(chosen.point.x,4), round(chosen.point.y,4)),
                         (983, .3742, .4032))

    def test_loot_credit_depends_on_which_tanaris_creature_is_targeted(self):
        h = self.host("forever/alliance/40-50/04-tanaris",
                      find_goal={"quest":1690, "npc":5616}, x=.6393, y=.2909)
        h.s.level = 45
        self.active(h, 1690, objective_index=2)
        self.active(h, 1707, total=5)
        thief = self.choose(h, 8, 2)
        self.assertTrue(thief.authored)
        self.assertIn("pueden dar botín", thief.reason)
        # The pouch stop points to the mage camp. Thieves are an alternate
        # source of pouches, but killing the primary mage does not count as a thief.
        pouches = self.choose(h, 8, 3)
        self.assertFalse(pouches and pouches.authored and "Las bajas también cuentan" in pouches.reason)

    def test_missing_creature_identity_does_not_create_shared_credit(self):
        h = self.host("forever/alliance/40-50/04-tanaris",
                      find_goal={"quest":1691,"npc":5617}, x=.588, y=.367)
        h.s.level = 45
        self.active(h,1691, objective_index=3)
        self.active(h,1878, total=5)
        h.ns.circuitCreatures["Mago oscuro Deambulador"] = None
        selected = self.choose(h, h.step_index, 1)
        self.assertFalse(selected and "pueden dar botín" in selected.reason)

    def test_unknown_combat_difficulty_does_not_start_independent_detour(self):
        h = self.host(find_goal={"quest":191, "t":"kill"}, x=.266, y=.168)
        self.active(h,191)
        self.active(h,194,9)
        h.ns.circuitCreatures["Raptor de Tuercespina"] = None
        h.ns.travelEnemyLevels[194] = None
        self.assertIsNone(self.choose(h, 13, 1))

    def test_loot_progress_counts_objects_and_tenth_shard_retargets_handin(self):
        h = self.host(find_goal={"quest":191, "t":"kill"}, x=.267, y=.183)
        self.active(h, 191)
        self.active(h, 605, 8)
        h.h.lua.execute("function GetItemCount(id) return id==3918 and TEST.shards or 0 end")
        selected = self.choose(h, 13, 1)
        self.assertEqual((selected.goal.quest, selected.goal.t), (605,"collect"))
        self.assertIn("2 objetos", selected.reason)
        h.s.shards = 10
        h.h.g.EmitAddonEvent("BAG_UPDATE_DELAYED")
        handin = self.choose(h, 13, 1)
        self.assertEqual((handin.goal.quest, handin.goal.t, handin.goal.npc), (605,"turnin",2498))
        self.assertEqual(h.state.cursor, 13)

    def test_elite_or_high_upper_bound_prevents_a_detour_even_if_partial(self):
        h = self.host(find_goal={"quest":191, "t":"kill"}, x=.266, y=.168)
        self.active(h, 191)
        self.active(h, 194, 9)
        known = h.ns.circuitCreatures["Raptor de Tuercespina"]
        known.elite = True
        self.assertIsNone(self.choose(h, 13, 1))
        known.elite, known.max = None, 40
        h.ns.LocalCircuit.Invalidate(h.ns.LocalCircuit)
        self.assertIsNone(self.choose(h, 13, 1))

    def test_future_pickup_requires_a_real_offer_space_and_shared_work(self):
        # A character who collected Gold Dust Exchange out of order visits
        # Goldshire before going to the mine. Use the actual Forever rows.
        for shown, used, expected in ((True, 39, 60), (False, 39, None), (True, 40, None)):
            with self.subTest(shown=shown, used=used):
                h = self.host("forever/alliance/human/01-elwynn-forest",
                              find_goal={"quest":47, "t":"collect"}, x=.4332, y=.657)
                h.s.level, h.s.used, h.s.shown = 8, used, shown
                self.active(h, 47)
                h.h.lua.execute("""
                    local ns = ACCESS_NS
                    local old = ns.guides[ns.char.activeGuide]
                    local guide = {id="forever/circuit-pickup-fixture", faction="Alliance", title="Elwynn",
                        steps={{goals={old.steps[24].goals[2]}}, {goals={old.steps[16].goals[7]}},
                               {goals={old.steps[24].goals[3]}}}}
                    ns.guides[guide.id]=guide
                    ns.char.activeGuide=guide.id
                    ns.char.progress[guide.id]={cursor=1, placed=true, skipped={}, confirmed={}}
                    function C_QuestLog.GetNumQuestLogEntries() return 1, TEST.used end
                    function C_QuestLog.GetMaxNumQuestsCanAccept() return 40 end
                    function C_QuestLog.GetQuestsOnMap()
                        return TEST.shown and {{questID=60,x=.4332,y=.657}} or {}
                    end
                """)
                h.guide = h.ns.guides[h.ns.char.activeGuide]
                h.state = h.ns.char.progress[h.ns.char.activeGuide]
                selected = self.choose(h, 1, 1)
                self.assertEqual(selected and selected.goal.quest, expected)

    def test_high_level_enemies_deferred_but_ready_high_level_turnin_valid(self):
        h = self.host(find_goal={"quest": 191, "t": "kill"}, x=.266, y=.168)
        self.active(h, 191)
        self.active(h, 194, 8)
        h.s.level = 29  # These raptors are 33–34.
        self.assertIsNone(self.choose(h, 13, 1))
        h.s.x, h.s.y = .3565,.107
        self.active(h, 195, 10, ready=True)
        self.assertEqual(self.choose(h, 16, 1, "manual").goal.quest, 195)


if __name__ == "__main__":
    unittest.main()
