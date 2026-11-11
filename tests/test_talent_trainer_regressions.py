"""LuaJIT regressions for live talent validation and Forever trainer advice."""

import unittest

from lupa.luajit21 import LuaRuntime

from test_addon import ADDON, UI_STUBS, WOW_STUBS


TALENT_STUBS = r"""
TEST.classToken, TEST.raceToken, TEST.level = "MAGE", "Human", 60
TEST.now, TEST.money, TEST.trainerType = 0, 100000, 0
TEST.services, TEST.rows = {}, {}
function UnitClass() return "Mago", TEST.classToken, 8 end
function UnitRace() return "Humano", TEST.raceToken, 1 end
function GetTime() return TEST.now end
function GetMoney() return TEST.money end
Enum = { TrainerType = { General = 0, TalentsObsolete = 1, Tradeskills = 2, Pet = 3 } }
C_Trainer = { GetTrainerType = function() return TEST.trainerType end }
function IsTradeskillTrainer() return TEST.trainerType == 2 end
function GetNumTrainerServices() return #TEST.services end
function GetTrainerServiceInfo(index)
    local s = TEST.services[index]
    return s.name, s.category, 12345, s.level or 1, s.rank
end
function GetTrainerServiceCost(index) return TEST.services[index].cost or 0 end
function MakeTrainerRow(index, label, modern)
    local row = CreateFrame()
    row.label = row:CreateFontString()
    row.label:SetText(label)
    function row.label:GetObjectType() return "FontString" end
    function row:GetRegions() return self.label end
    if modern then
        function row:GetElementData() return { data = { skillIndex = index } } end
    else
        function row:GetID() return index end
    end
    TEST.rows[#TEST.rows + 1] = row
    return row
end
ClassTrainerFrame = CreateFrame()
ClassTrainerFrame.ScrollBox = {
    ForEachFrame = function(_, callback) for _, row in ipairs(TEST.rows) do callback(row) end end
}
function InstallLiveTalents(ns, classToken)
    local data = ns.Talents.Registry[classToken]
    TEST.liveNodes, TEST.entries = {}, {}
    TEST.unspent, TEST.spent = 1, 0
    for id, n in pairs(data.nodes) do
        TEST.liveNodes[id] = { ID = id, activeRank = 0, currentRank = 0, maxRanks = n.max,
            entryIDs = { n.entry }, activeEntry = { entryID = n.entry } }
        TEST.entries[n.entry] = { spellID = n.spell, overrideName = n.nameEs }
    end
    C_ClassTalents = { GetActiveConfigID = function() return TEST.configID or 1 end }
    C_Traits = {
        GetTreeNodes = function()
            local ids = {}
            for id in pairs(TEST.liveNodes) do ids[#ids + 1] = id end
            return ids
        end,
        GetNodeInfo = function(_, id) return TEST.liveNodes[id] end,
        GetEntryInfo = function(_, id) return { definitionID = id } end,
        GetDefinitionInfo = function(id) return TEST.entries[id] end,
        GetTreeCurrencyInfo = function() return { { quantity = TEST.unspent, spent = TEST.spent } } end,
    }
end
"""


class TalentTrainerHost:
    def __init__(self, full_toc=False):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(WOW_STUBS)
        self.lua.execute(UI_STUBS)
        self.lua.execute(TALENT_STUBS)
        if full_toc:
            self.lua.execute(r"""
                local original = CreateFrame
                TEST.eventFrames = {}
                CreateFrame = function(...)
                    local frame = original(...)
                    TEST.eventFrames[#TEST.eventFrames + 1] = frame
                    return frame
                end
                function EmitAddonEvent(event, ...)
                    for _, frame in ipairs(TEST.eventFrames) do
                        if frame.events[event] and frame.scripts.OnEvent then frame.scripts.OnEvent(frame, event, ...) end
                    end
                end
            """)
        self.g = self.lua.globals()
        self.ns = self.lua.table_from({"char": self.lua.table()})
        load = self.lua.eval("function(s, ns) assert(loadstring(s))('RutaXP', ns) end")
        files = ["Talents.lua", "TalentBuilds.lua", "Trainer.lua"]
        if full_toc:
            files = [line.strip() for line in (ADDON / "RutaXP.toc").read_text(encoding="utf-8-sig").splitlines()
                     if line.strip().endswith(".lua") and not line.strip().startswith("#")]
        for filename in files:
            load((ADDON / filename).read_text(encoding="utf-8-sig"), self.ns)
        self.t, self.tr, self.state = self.ns.Talents, self.ns.TrainerAdvice, self.g.TEST

    def table(self, value):
        return self.lua.table_from(value, recursive=True)

    def live(self, cls="MAGE"):
        self.g.InstallLiveTalents(self.ns, cls)

    def panel(self):
        self.t.TogglePanel(True)
        return self.t.panel

    def services(self, entries, modern=True):
        self.state.services = self.table(entries)
        self.state.rows = self.lua.table()
        for index, entry in enumerate(entries, 1):
            self.g.MakeTrainerRow(index, entry["name"], modern)
        self.tr.cache = None
        self.tr.Refresh(self.g.ClassTrainerFrame)
        return self.state.rows


class TalentCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.h = TalentTrainerHost()

    def test_missing_modern_api_keeps_reference_panel_without_fictional_points(self):
        h = self.h
        c = h.t.Evaluate()
        self.assertFalse(c.compatible)
        self.assertEqual(c.state.status, "unavailable")
        self.assertIsNone(c.state.points)
        self.assertIsNone(c.state.unspent)
        panel = h.panel()
        self.assertIn("NO DISPONIBLE", panel.nextCard.header.text)
        self.assertIn("Solo referencia", panel.detectedText.text)
        self.assertEqual(len(panel.rows), 51)
        self.assertNotIn("SUBE AHORA", panel.nextCard.header.text)

    def test_missing_or_zero_config_never_infers_level_based_points(self):
        h = self.h
        h.live()
        h.state.configID = 0
        c = h.t.Evaluate()
        self.assertFalse(c.compatible)
        self.assertIsNone(c.staged.unspent)

    def test_level_nine_paladin_previews_first_talent_then_validates_at_unlock(self):
        h = TalentTrainerHost(full_toc=True)
        h.state.classToken, h.state.raceToken, h.state.level = "PALADIN", "Dwarf", 9
        h.live("PALADIN")
        guide = h.t.Registry.PALADIN.builds[4]
        h.t.SetChoice(guide.key, "PALADIN")
        first_node = guide.picks[1].node
        saved_node = h.state.liveNodes[first_node]
        h.state.liveNodes[first_node] = None
        panel = h.panel()
        self.assertEqual(h.t.current.staged.status, "early")
        self.assertEqual(h.t.current.staged.unspent, 0)
        self.assertIn("NIVEL 10", panel.nextCard.header.text)
        self.assertIn(h.t.Registry.PALADIN.nodes[first_node].nameEs, panel.nextCard.main.text)
        self.assertNotIn("Solo referencia", panel.detectedText.text)

        h.state.level = 10
        h.g.EmitAddonEvent("PLAYER_LEVEL_UP", 10)
        self.assertEqual(h.t.current.staged.status, "unavailable")
        self.assertIn("NO DISPONIBLE", panel.nextCard.header.text)
        h.state.liveNodes[first_node] = saved_node
        h.g.EmitAddonEvent("TRAIT_CONFIG_UPDATED", 1)
        self.assertTrue(h.t.current.compatible)
        self.assertIn("SUBE AHORA", panel.nextCard.header.text)

    def test_changed_or_empty_tree_is_explicitly_incompatible(self):
        h = self.h
        h.live()
        selected = h.t.Evaluate()
        self.assertTrue(selected.compatible)
        h.t.SetChoice(selected.build.key)
        first = selected.build.picks[1].node
        h.state.liveNodes[first] = None
        c = h.t.Evaluate()
        self.assertFalse(c.compatible)
        self.assertFalse(c.valid.ok)
        self.assertEqual(len(c.valid.missing), 1)
        self.assertIsNone(c.state.unspent)
        h.state.liveNodes = h.lua.table()
        self.assertFalse(h.t.Evaluate().compatible)

    def test_unknown_spent_node_cannot_disappear_from_point_accounting(self):
        h = self.h
        h.live()
        h.state.liveNodes[999999] = h.table({"ID": 999999, "activeRank": 2, "currentRank": 2, "maxRanks": 5})
        self.assertFalse(h.t.Evaluate().compatible)

    def test_unspent_node_outside_the_selected_plan_does_not_hide_live_ranks(self):
        h = self.h
        h.live()
        build = h.t.Registry.MAGE.builds[1]
        h.t.SetChoice(build.key)
        chosen = {p.node for p in build.picks.values()}
        irrelevant = next(node for node in h.state.liveNodes.keys() if node not in chosen)
        h.state.liveNodes[irrelevant] = None
        first = build.picks[1].node
        h.state.liveNodes[first].activeRank = h.state.liveNodes[first].currentRank = 1
        h.state.spent, h.state.unspent = 1, 0
        result = h.t.Evaluate()
        self.assertTrue(result.compatible)
        self.assertEqual(result.state.spent, 1)
        self.assertEqual(result.activeRanks[first], 1)

    def test_no_currency_does_not_infer_free_talent_points_from_character_level(self):
        h = self.h
        h.live()
        h.g.C_Traits.GetTreeCurrencyInfo = None
        result = h.t.Evaluate()
        self.assertTrue(result.compatible)
        self.assertEqual(result.state.spent, 0)
        self.assertIsNone(result.state.unspent)
        self.assertIsNone(result.state.points)
        panel = h.panel()
        self.assertNotIn("SUBE AHORA", panel.nextCard.header.text)

    def test_live_node_remapping_by_spell_preserves_spent_ranks(self):
        h = self.h
        h.live()
        source_id = h.t.Registry.MAGE.builds[1].picks[1].node
        node = h.state.liveNodes[source_id]
        node.ID, node.activeRank, node.currentRank = 999999, 2, 2
        h.state.liveNodes[source_id] = None
        h.state.liveNodes[999999] = node
        h.state.unspent, h.state.spent = 0, 2
        c = h.t.Evaluate()
        self.assertTrue(c.compatible)
        self.assertEqual(c.valid.map[source_id], 999999)
        self.assertEqual(c.state.spent, 2)
        self.assertEqual(c.state.unspent, 0)

    def test_off_plan_spending_warns_instead_of_claiming_player_is_on_plan(self):
        h = self.h
        h.live()
        build = h.t.Registry.MAGE.builds[1]
        h.ns.char.talents = h.table({"builds": {"MAGE": build.key}})
        planned = {p.node for _, p in build.picks.items()}
        for _, pick in build.picks.items():
            if pick.order <= 50:
                n = h.state.liveNodes[pick.node]
                n.activeRank = n.currentRank = pick.rank
        unused = next(id for id, n in h.t.Registry.MAGE.nodes.items() if id not in planned and n.row == 1)
        h.state.liveNodes[unused].activeRank = h.state.liveNodes[unused].currentRank = 1
        h.state.unspent, h.state.spent = 0, 51
        c = h.t.Evaluate()
        self.assertEqual(c.state.status, "offplan")
        panel = h.panel()
        self.assertIn("DIFIERE", panel.nextCard.header.text)
        self.assertNotIn("AL DÍA", panel.nextCard.header.text)

    def test_previewing_another_class_preserves_all_four_guides(self):
        h = self.h
        h.t.selectedClass = "DRUID"
        panel = h.panel()
        self.assertEqual(h.t.current.data["class"], "DRUID")
        self.assertFalse(h.t.current.isPlayerClass)
        self.assertEqual(len(panel.buildBtns), 4)
        self.assertEqual(len(panel.rows), 51)
        self.assertIn("PRIMER PUNTO", panel.nextCard.header.text)

    def test_live_overlay_highlight_is_hidden_when_the_tree_becomes_unreadable(self):
        h = self.h
        h.live()
        h.g.NS = h.ns
        h.lua.execute(r"""
            local original = CreateFrame
            TEST.talentButton = CreateFrame()
            function TEST.talentButton:GetNodeID() return NS.Talents.Registry.MAGE.builds[1].picks[1].node end
            CreateFrame = function(kind, name, parent, template)
                local frame = original(kind, name, parent, template)
                if parent == TEST.talentButton then TEST.overlayMark = frame end
                return frame
            end
            local talentFrame = CreateFrame()
            function talentFrame:EnumerateAllTalentButtons()
                local returned = false
                return function()
                    if not returned then returned = true; return TEST.talentButton end
                end
            end
            PlayerSpellsFrame = { TalentsFrame = talentFrame }
        """)
        h.t.current = h.t.Evaluate()
        h.t.DrawOverlay()
        self.assertTrue(h.state.overlayMark.shown)
        self.assertTrue(h.state.overlayMark.Ring.shown)
        h.g.C_ClassTalents = None
        h.t.current = h.t.Evaluate()
        h.t.DrawOverlay()
        self.assertFalse(h.state.overlayMark.shown)


class ForeverConvictionTests(unittest.TestCase):
    def setUp(self):
        h = self.h = TalentTrainerHost()
        h.state.classToken, h.state.level = "PALADIN", 27
        self.data = h.t.Registry.PALADIN
        self.conviction = next(id for id, node in self.data.nodes.items() if node.name == "Conviction")
        self.retribution = next(b for b in self.data.builds.values() if b.key == "retribution")
        h.t.SetChoice(self.retribution.key)

    def test_static_paladin_guides_and_reference_rows_respect_convictions_three_ranks(self):
        self.assertEqual(self.data.nodes[self.conviction].max, 3)
        for build in self.data.builds.values():
            with self.subTest(build=build.key):
                ranks = [p.rank for p in build.picks.values() if p.node == self.conviction]
                self.assertTrue(all(1 <= rank <= 3 for rank in ranks))
                if build.key == self.retribution.key:
                    self.assertEqual(sorted(ranks), [1, 2, 3])
        panel = self.h.panel()
        rows = [row for row in panel.rows.values() if row.shown and "Convicción" in row.name.text]
        self.assertEqual(len(rows), 3)
        for rank in (1, 2, 3):
            self.assertTrue(any(f"{rank}/3" in row.name.text for row in rows))

    def test_three_full_ranks_in_the_active_tree_do_not_suggest_a_fourth(self):
        h = self.h
        h.live("PALADIN")
        h.lua.execute("""
            local getNodes = C_Traits.GetTreeNodes
            C_Traits.GetConfigInfo = function() return {treeIDs = {987654}} end
            C_Traits.GetTreeNodes = function(treeID)
                return treeID == 987654 and getNodes() or {}
            end
        """)
        # The seven lit-up talents in the Forever character's 18-point tree.
        retri = {(n.row, n.col): id for id, n in self.data.nodes.items() if n.spec == 3}
        self.assertEqual(retri[2, 2], self.conviction)
        spent = {(1, 3): 5, (2, 1): 2, (2, 2): 3, (2, 3): 3, (3, 1): 3, (3, 3): 1, (4, 2): 1}
        for pos, rank in spent.items():
            node = h.state.liveNodes[retri[pos]]
            self.assertLessEqual(rank, node.maxRanks)
            node.activeRank = node.currentRank = rank
        h.state.spent, h.state.unspent = 18, 0
        panel = h.panel()
        c = h.t.current
        self.assertTrue(c.compatible)
        self.assertEqual((c.state.spent, c.state.unspent), (18, 0))
        self.assertEqual(c.activeRanks[self.conviction], 3)
        next_node = self.data.nodes[c.staged.next.node]
        self.assertEqual((next_node.name, c.staged.next.rank, next_node.max),
                         ("Two-Handed Weapon Specialization", 1, 3))
        self.assertIn(next_node.nameEs, panel.nextCard.main.text)
        self.assertTrue(any("Convicción" in row.name.text and "3/3" in row.name.text
                            for row in panel.rows.values() if row.shown))

    def test_a_lower_cap_from_a_new_client_displays_invested_ranks_without_a_false_next_pick(self):
        h = self.h
        h.live("PALADIN")
        node = h.state.liveNodes[self.conviction]
        node.maxRanks = node.activeRank = node.currentRank = 2
        h.state.spent, h.state.unspent = 2, 0
        panel = h.panel()
        c = h.t.current
        self.assertFalse(c.compatible)
        self.assertIsNone(c.staged.next)
        self.assertEqual(c.activeRanks[self.conviction], 2)
        self.assertEqual(c.state.spent, 2)
        rows = [row for row in panel.rows.values() if row.shown]
        self.assertEqual(len(rows), 1)
        self.assertIn("Convicción", rows[0].name.text)
        self.assertIn("2/2", rows[0].name.text)
        self.assertNotIn("SUBE AHORA", panel.nextCard.header.text)

    def test_reused_node_and_name_cannot_hide_a_different_spell(self):
        h = self.h
        h.live("PALADIN")
        entry = self.data.nodes[self.conviction].entry
        h.state.entries[entry].spellID = 901234
        c = h.t.Evaluate()
        self.assertFalse(c.compatible)
        self.assertIsNone(c.staged.next)

    def test_build_cannot_pass_a_prerequisite_with_a_newly_increased_rank_limit(self):
        h = self.h
        h.live("PALADIN")
        planned = {p.node for p in self.retribution.picks.values()}
        parent = next(edge[1] for edge in self.data.edges.values()
                      if edge[1] in planned and edge[2] in planned)
        h.state.liveNodes[parent].maxRanks += 1
        self.assertFalse(h.t.Evaluate().compatible)

    def test_inactive_placeholder_in_live_tree_does_not_invalidate_known_talents(self):
        h = self.h
        h.live("PALADIN")
        h.state.liveNodes[901234] = h.table({"ID": 0, "activeRank": 0, "currentRank": 0})
        self.assertTrue(h.t.Evaluate().compatible)


class TrainerRegressionTests(unittest.TestCase):
    def setUp(self):
        self.h = TalentTrainerHost()

    def test_same_spell_name_resolves_each_rank_by_its_live_service_index(self):
        h = self.h
        rows = h.services([
            {"name": "Descarga de Escarcha", "category": "used", "rank": "Rango 1"},
            {"name": "Descarga de Escarcha", "category": "available", "rank": "Rango 2", "cost": 100},
            {"name": "Descarga de Escarcha", "category": "unavailable", "rank": "Rango 3"},
        ])
        self.assertEqual(rows[1].RutaXPBadge.text, "")
        self.assertFalse(rows[1].RutaXPStripe.shown)
        self.assertIn("COMPRAR", rows[2].RutaXPBadge.text)
        self.assertIn("Más adelante", rows[3].RutaXPBadge.text)
        self.assertIn("Rango 2", h.tr.banner.text.text)

    def test_ambiguous_text_only_legacy_rows_receive_no_rank_guess(self):
        h = self.h
        rows = h.services([
            {"name": "Descarga de Escarcha", "category": "used"},
            {"name": "Descarga de Escarcha", "category": "available", "cost": 100},
        ], modern=False)
        self.assertEqual(rows[1].RutaXPBadge.text, "")
        self.assertEqual(rows[2].RutaXPBadge.text, "")

    def test_unique_legacy_service_can_still_receive_advice(self):
        rows = self.h.services([{"name": "Descarga de Escarcha", "category": "available", "cost": 100}], modern=False)
        self.assertIn("COMPRAR", rows[1].RutaXPBadge.text)

    def test_pet_profession_and_unknown_trainers_clear_recycled_badges(self):
        h = self.h
        rows = h.services([{"name": "Descarga de Escarcha", "category": "available", "cost": 100}])
        self.assertTrue(rows[1].RutaXPStripe.shown)
        for trainer_type in [3, 2, 1, 999]:
            with self.subTest(trainer_type=trainer_type):
                h.state.trainerType = trainer_type
                h.tr.Refresh(h.g.ClassTrainerFrame)
                self.assertFalse(h.tr.banner.shown)
                self.assertEqual(rows[1].RutaXPBadge.text, "")
                self.assertFalse(rows[1].RutaXPStripe.shown)
                h.state.trainerType = 0
                h.tr.Refresh(h.g.ClassTrainerFrame)

    def test_unknown_trainer_type_api_disables_advice_without_error(self):
        h = self.h
        h.g.C_Trainer = None
        h.services([{"name": "Descarga de Escarcha", "category": "available"}])
        self.assertIsNone(h.tr.banner)

    def test_weapon_or_riding_services_do_not_get_class_purchase_advice(self):
        h = self.h
        h.state.level = 10
        h.services([{"name": "Montar a caballo", "category": "available", "cost": 100}])
        self.assertIsNone(h.tr.banner)

    def test_preview_class_does_not_change_real_class_trainer_priorities(self):
        h = self.h
        h.t.selectedClass = "WARRIOR"
        rows = h.services([{"name": "Descarga de Escarcha", "category": "available", "cost": 100}])
        self.assertIn("COMPRAR", rows[1].RutaXPBadge.text)
        self.assertEqual(h.tr.cache.build.data["class"], "MAGE")

    def test_only_selected_role_skills_are_strong_recommendations(self):
        h = self.h
        frost = h.t.Registry.MAGE.builds[1]
        index = h.tr.BuildIndex("MAGE", frost)
        self.assertEqual(index[h.tr.Normalize("Descarga de Escarcha")].rank, 3)
        self.assertEqual(index[h.tr.Normalize("Bola de Fuego")].rank, 2)
        foreign = h.tr.BuildIndex("MAGE", h.t.Registry.WARRIOR.builds[1])
        self.assertEqual(foreign[h.tr.Normalize("Descarga de Escarcha")].rank, 2)

    def test_english_parenthetical_spell_aliases_are_retained(self):
        index = self.h.tr.BuildIndex("MAGE", None)
        self.assertEqual(index["frostbolt"].rank, 2)
        self.assertEqual(index["counterspell"].rank, 2)

    def test_unknown_service_category_is_not_treated_as_available(self):
        h = self.h
        h.services([{"name": "Descarga de Escarcha", "category": "unknown", "cost": 100}])
        self.assertIsNone(h.tr.banner)


class TalentCatalogRegressionTests(unittest.TestCase):
    def test_all_36_builds_keep_51_legal_picks_and_truthful_distributions(self):
        h = TalentTrainerHost()
        builds = 0
        for cls, data in h.t.Registry.items():
            for _, build in data.builds.items():
                builds += 1
                ranks, split = {}, [0, 0, 0]
                self.assertEqual(len(build.picks), 51, (cls, build.key))
                for _, pick in build.picks.items():
                    node = data.nodes[pick.node]
                    self.assertEqual(pick.rank, ranks.get(pick.node, 0) + 1)
                    self.assertLessEqual(pick.rank, node.max)
                    gates = data.gates[pick.node]
                    for _, gate in gates.items() if gates else []:
                        spent = sum(ranks.get(id, 0) for _, id in data.groups[gate[1]].items())
                        self.assertGreaterEqual(spent, gate[2], (cls, build.key, pick.order))
                    for _, edge in data.edges.items():
                        if edge[2] == pick.node:
                            self.assertEqual(ranks.get(edge[1], 0), data.nodes[edge[1]].max)
                    ranks[pick.node] = pick.rank
                    split[node.spec - 1] += 1
                self.assertEqual(build.split, "/".join(map(str, split)), (cls, build.key))
        self.assertEqual(builds, 36)


class FullTocIntegrationTests(unittest.TestCase):
    def test_shipping_load_order_handles_missing_capabilities_and_recovers_live_talents(self):
        h = TalentTrainerHost(full_toc=True)
        h.g.EmitAddonEvent("ADDON_LOADED", "RutaXP")
        h.g.EmitAddonEvent("PLAYER_LOGIN")
        self.assertTrue(h.ns.initialized)
        self.assertEqual(len(h.ns.order), 57)
        self.assertEqual(len(list(h.t.Registry.items())), 9)
        self.assertIsNotNone(h.ns.navigationFrame)
        # No C_Traits or world-position API is provided: retain the guide and
        # explain that live talent state cannot be read instead of inventing it.
        h.ns.Command(h.ns, "talentos")
        self.assertEqual(len(h.t.panel.rows), 51)
        self.assertIn("NO DISPONIBLE", h.t.panel.nextCard.header.text)
        self.assertIsNone(h.t.current.state.unspent)
        h.live()
        h.g.EmitAddonEvent("TRAIT_CONFIG_UPDATED", 1)
        self.assertTrue(h.t.current.compatible)
        self.assertEqual(h.t.current.state.unspent, 1)
        self.assertIn("TIENES 1", h.t.panel.nextCard.header.text)
        rows = h.services([{"name": "Descarga de Escarcha", "category": "available", "cost": 100}])
        self.assertIn("COMPRAR", rows[1].RutaXPBadge.text)


if __name__ == "__main__":
    unittest.main()
