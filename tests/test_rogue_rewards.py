"""Quest rewards in the human rogue's current tracker row, with the live Lua engine."""
import unittest

from test_quest_engine import ADDON, QuestEngineHost


DAGGER = dict(id=501, name="Daga del catálogo", choice=True, kind="Daga",
              stat="dps", value=12, inv=13, level=12)
LEATHER = dict(id=502, name="Túnica de cuero", choice=False, kind="Cuero",
               stat="agi", value=4, inv=20, level=1)


class RogueRewardTests(unittest.TestCase):
    def setUp(self):
        h = self.host = QuestEngineHost()
        h.state.classToken = "ROGUE"
        h.state.raceToken = "Human"
        h.lua.execute("""
            local original = CreateFrame
            function CreateFrame(...) REWARD_FRAME = original(...) return REWARD_FRAME end
        """)
        h.load((ADDON / "RogueRewards.lua").read_text(encoding="utf-8"), "RutaXP", h.ns)
        self.frame = h.globals.REWARD_FRAME
        h.ns.rogueQuestRewards = h.table({100: [DAGGER, LEATHER], 101: [DAGGER.copy()]})
        h.group([{"t": action, "quest": quest} for action, quest in
                 [("accept", 100), ("complete", 100), ("turnin", 100), ("accept", 101)]])
        h.initialize()

    def items(self):
        h = self.host
        _, step, state = h.call("GetCurrent")
        rows, _ = h.call("GetStepGoalItems", step, state)
        return list(rows.values())

    def test_only_current_accept_or_turnin_shows_a_compact_hint(self):
        h = self.host
        accept, *others = self.items()
        self.assertTrue(accept.isCurrent)
        self.assertEqual(accept.subtitle, "Recompensas · Daga, Cuero")
        self.assertIn("A elegir · Daga del catálogo (Daga) · 12 DPS · nivel 12", accept.details)
        self.assertIn("Fija · Túnica de cuero (Cuero) · 4 agilidad", accept.details)
        self.assertTrue(all("Daga" not in (row.subtitle or "") for row in others))
        h.quest(100, onQuest=True)
        h.fire("QUEST_ACCEPTED", 100)
        self.assertTrue(all("Daga" not in (row.subtitle or "") for row in self.items()))
        h.quest(100, onQuest=True, complete=True)
        h.fire("QUEST_LOG_UPDATE")
        turnin, *others = self.items()
        self.assertEqual(turnin.action, "turnin")
        self.assertIn("Recompensas · Daga, Cuero", turnin.subtitle)
        self.assertTrue(all("Daga" not in (row.subtitle or "") for row in others))

    def test_race_class_and_catalog_eligibility(self):
        h = self.host
        self.assertIsNone(h.call("GetRogueQuestRewardInfo", 999))
        for race, cls in [("Dwarf", "ROGUE"), ("Human", "PALADIN")]:
            h.state.raceToken, h.state.classToken = race, cls
            self.assertIsNone(h.call("GetRogueQuestRewardInfo", 100))
            self.assertNotIn("Recompensas", self.items()[0].subtitle or "")

    def open_reward_dialog(self):
        h = self.host
        h.quest(100, onQuest=True, complete=True)
        h.fire("QUEST_LOG_UPDATE")
        h.lua.execute("""
            TEST.dialogQuest, TEST.shown = 100, true
            TEST.choice, TEST.reward = {999}, {501}
            TEST.dialogReads = 0
            QuestFrameRewardPanel = {IsVisible=function() return TEST.shown end}
            function GetQuestID() return TEST.dialogQuest end
            function GetNumQuestChoices() return #TEST.choice end
            function GetNumQuestRewards() return #TEST.reward end
            function GetQuestItemLink(kind, i)
                TEST.dialogReads = TEST.dialogReads + 1
                if kind == "choice" then return "|Hitem:" .. TEST[kind][i] .. ":0|h[Objeto]|h" end
            end
            function GetQuestItemInfo(kind, i) return nil, nil, 1, nil, true, TEST[kind][i] end
        """)

    def test_complete_turnin_dialog_filters_and_reclassifies_known_items(self):
        self.open_reward_dialog()
        h = self.host
        turnin = self.items()[0]
        self.assertEqual(turnin.subtitle, "Recompensa fija · Daga (12 DPS)")
        self.assertIn("Fija · Daga del catálogo", turnin.details)
        self.assertNotIn("Cuero", turnin.details)
        self.assertNotIn("999", turnin.details)
        h.lua.execute("TEST.choice = {502}; TEST.reward = {999}")
        turnin = self.items()[0]
        self.assertEqual(turnin.subtitle, "A elegir · Cuero (4 agilidad)")
        self.assertIn("A elegir · Túnica de cuero", turnin.details)
        self.assertNotIn("Daga", turnin.details)
        h.lua.execute("TEST.choice = {999}; TEST.reward = {}")
        self.assertIsNone(h.call("GetRogueQuestRewardInfo", 100, "turnin"))
        h.state.shown = False
        self.assertIn("Recompensas · Daga, Cuero", self.items()[0].subtitle)
        self.assertTrue(h.ns.rogueQuestRewards[100][1].choice)
        self.assertFalse(h.ns.rogueQuestRewards[100][2].choice)

    def test_another_quest_partial_read_or_unopened_dialog_uses_full_catalog(self):
        self.open_reward_dialog()
        h = self.host
        h.state.dialogQuest = 222
        self.assertEqual(self.items()[0].subtitle, "Recompensas · Daga, Cuero")
        h.state.shown = False
        h.state.dialogQuest = 100
        self.assertEqual(self.items()[0].subtitle, "Recompensas · Daga, Cuero")
        self.assertEqual(h.state.dialogReads, 0)
        h.state.shown = True
        self.assertIn("Daga, Cuero", h.call("GetRogueQuestRewardInfo", 100, "accept")[0])
        self.assertEqual(h.state.dialogReads, 0)
        # Fixed item is readable, second choice is still cached as a placeholder.
        h.lua.execute("TEST.choice = {502, 0}")
        self.assertEqual(self.items()[0].subtitle, "Recompensas · Daga, Cuero")
        self.assertIn("A elegir · Daga del catálogo", self.items()[0].details)
        h.lua.execute("TEST.choice = {}; TEST.reward = {}")
        self.assertEqual(self.items()[0].subtitle, "Recompensas · Daga, Cuero")
        h.lua.execute("GetNumQuestChoices=nil; TEST.reward={999}")
        self.assertEqual(self.items()[0].subtitle, "Recompensas · Daga, Cuero")

    def test_dialog_updates_refresh_only_the_active_turnin(self):
        self.open_reward_dialog()
        h = self.host
        emit = self.frame.scripts.OnEvent
        before = h.state.refreshes
        emit(self.frame, "QUEST_COMPLETE")
        self.assertEqual(h.state.refreshes, before + 1)
        self.items()  # the tracker observed the visible dialog
        emit(self.frame, "QUEST_ITEM_UPDATE")
        self.assertEqual(h.state.refreshes, before + 2)
        h.state.dialogQuest = 101
        emit(self.frame, "QUEST_ITEM_UPDATE")
        self.assertEqual(h.state.refreshes, before + 2)
        h.state.shown = False
        emit(self.frame, "QUEST_FINISHED")
        self.assertEqual(h.state.refreshes, before + 3)
        emit(self.frame, "QUEST_FINISHED")
        self.assertEqual(h.state.refreshes, before + 3)

    def test_catalog_links_northshire_choices_and_westfall_fixed_dagger(self):
        h = self.host
        h.load((ADDON / "RogueRewardData.lua").read_text(encoding="utf-8"), "RutaXP", h.ns)
        hint, details = h.call("GetRogueQuestRewardInfo", 18)
        self.assertEqual(hint, "A elegir · Daga, Espada, Maza")
        self.assertIn("A elegir · Daga de milicia", details)
        hint, details = h.call("GetRogueQuestRewardInfo", 38)
        self.assertIn("Recompensa fija · Daga", hint)
        self.assertIn("Fija · Cuchillo de cocina afilado", details)

    def test_optional_defias_dungeon_hint_preserves_current_duo_quest(self):
        h = self.host
        h.load((ADDON / "RogueRewardData.lua").read_text(encoding="utf-8"), "RutaXP", h.ns)
        self.assertIsNone(h.ns.rogueQuestRewards[65])
        h.active()[0].quest = 65
        h.lua.execute("function IsInGroup() return true end")
        _, _, state = h.call("GetCurrent")
        before = state.cursor
        first, *others = self.items()
        self.assertEqual(first.subtitle, "Cadena opcional · Túnica de cuero")
        for phrase in ("Wiley el Negro", "Gryan Mantorrecio", "Traidor Defias", "grupo", "Minas de la Muerte",
                       "VanCleef", "elegir la Túnica", "+11 agilidad, +5 aguante"):
            self.assertIn(phrase, first.details)
        self.assertTrue(all("Túnica" not in (row.subtitle or "") for row in others))
        self.assertEqual((h.active()[0].quest, state.cursor), (65, before))
        h.state.classToken = "HUNTER"
        self.assertIsNone(h.call("GetRogueQuestRewardInfo", 65))

    def test_comparisons_use_only_applicable_equipped_slots_and_live_stat(self):
        h = self.host
        h.lua.execute("""
            C_Item = {GetItemInfo = function(id) return "Objeto " .. id end}
            function GetInventoryItemLink(_, slot) return "equip:" .. slot end
            function C_Item.GetItemStats(link)
                local dps = { ["item:501"]=14.6, ["equip:16"]=12.1, ["equip:17"]=15 }
                local agi = { ["item:502"]=4, ["equip:5"]=2 }
                return { ITEM_MOD_DAMAGE_PER_SECOND_SHORT=dps[link], ITEM_MOD_AGILITY_SHORT=agi[link] }
            end
        """)
        _, details = h.call("GetRogueQuestRewardInfo", 100)
        armor = details.splitlines()[1]
        self.assertIn("Objeto 501 (Daga) · 14,6 DPS (mano principal +2,5 DPS, mano secundaria -0,4 DPS)", details)
        self.assertIn("ranura equipada +2 agilidad", armor)
        self.assertNotIn("mano", armor)
        for inv, yes, no in [(21, "mano principal", "mano secundaria"), (22, "mano secundaria", "mano principal")]:
            h.ns.rogueQuestRewards[100][1].inv = inv
            _, details = h.call("GetRogueQuestRewardInfo", 100)
            self.assertIn(yes, details)
            self.assertNotIn(no, details)
        h.lua.execute("C_Item.GetItemStats = function(link) if link == 'equip:16' then return {ITEM_MOD_DAMAGE_PER_SECOND_SHORT=5} end end")
        hint, details = h.call("GetRogueQuestRewardInfo", 101)
        self.assertEqual(hint, "A elegir · Daga (12 DPS)")
        self.assertNotIn("mano principal", details)

    def test_blade_of_cunning_agility_appears_in_tooltip_only_with_cache_override(self):
        h = self.host
        h.load((ADDON / "RogueRewardData.lua").read_text(encoding="utf-8"), "RutaXP", h.ns)
        hint, details = h.call("GetRogueQuestRewardInfo", 2206)
        self.assertIn("Fija · Hoja de Astucia (Daga) · 6,8 DPS · +2 agilidad", details)
        self.assertEqual(hint, "Recompensa fija · Daga (6,8 DPS)")
        h.lua.execute("""
            C_Item = {GetItemStats = function(link)
                TEST.statReads = (TEST.statReads or 0) + 1
                if link == "item:7298" then return {ITEM_MOD_AGILITY_SHORT=TEST.agility} end
            end}
        """)
        h.state.agility = 3
        live_hint, details = h.call("GetRogueQuestRewardInfo", 2206)
        self.assertIn("+3 agilidad", details)
        self.assertNotIn("+2 agilidad", details)
        self.assertEqual(live_hint, hint)
        self.assertEqual(h.state.statReads, 1)
        h.state.agility = 0
        self.assertNotIn("agilidad", h.call("GetRogueQuestRewardInfo", 2206)[1])

    def test_percentage_ratings_are_never_compared(self):
        h = self.host
        h.ns.rogueQuestRewards[100] = h.table([dict(LEATHER, stat="crit", value=2)])
        h.lua.execute("C_Item = {GetItemStats = function() error('rating must not be requested') end}")
        self.assertEqual(h.call("GetRogueQuestRewardInfo", 100),
                         ("Recompensa fija · Cuero (2 % de crítico)", "Fija · Túnica de cuero (Cuero) · 2 % de crítico"))

    def test_ranged_comparisons_never_read_equipped_daggers(self):
        h = self.host
        h.lua.execute("""
            function GetInventoryItemLink(_, slot)
                TEST.queried[#TEST.queried+1] = slot
                return "equip:" .. slot
            end
            C_Item = { GetItemStats = function(link)
                local dps = { ["item:501"]=14, ["equip:18"]=12, ["equip:16"]=4, ["equip:17"]=20 }
                return {ITEM_MOD_DAMAGE_PER_SECOND_SHORT=dps[link]}
            end }
        """)
        for inv, kind in [(15, "Arco"), (25, "Arma arrojadiza"), (26, "Ballesta")]:
            with self.subTest(inv=inv):
                h.state.queried = h.table([])
                h.ns.rogueQuestRewards[100] = h.table([dict(DAGGER, inv=inv, kind=kind)])
                _, details = h.call("GetRogueQuestRewardInfo", 100)
                self.assertIn("arma a distancia +2 DPS", details)
                self.assertNotIn("mano", details)
                self.assertEqual(list(h.state.queried.values()), [18])
        h.state.queried = h.table([])
        h.ns.rogueQuestRewards[100] = h.table([dict(DAGGER, kind="Hacha", inv=13)])
        _, details = h.call("GetRogueQuestRewardInfo", 100)
        self.assertIn("mano principal +10 DPS, mano secundaria -6 DPS", details)
        self.assertEqual(list(h.state.queried.values()), [16, 17])

    def test_neck_cloak_rings_and_trinkets_compare_by_slot(self):
        h = self.host
        h.lua.execute("""
            function GetInventoryItemLink(_, slot)
                if slot ~= TEST.emptySlot then return "equip:" .. slot end
            end
            C_Item = { GetItemStats = function(link)
                local equipped = tonumber(link:match("^equip:(%d+)$"))
                return {ITEM_MOD_AGILITY_SHORT=equipped or 13}
            end }
        """)
        for inv, kind, expected in [
            (2, "Collar", "cuello +11 agilidad"), (16, "Capa", "capa equipada -2 agilidad"),
            (11, "Anillo", "anillo 1 +2 agilidad, anillo 2 +1 agilidad"),
            (12, "Abalorio", "abalorio 1 0 agilidad, abalorio 2 -1 agilidad"),
        ]:
            with self.subTest(inv=inv):
                h.ns.rogueQuestRewards[100] = h.table([dict(LEATHER, inv=inv, kind=kind)])
                _, details = h.call("GetRogueQuestRewardInfo", 100)
                self.assertIn("(" + expected + ")", details)
        h.state.emptySlot = 13
        _, details = h.call("GetRogueQuestRewardInfo", 100)
        self.assertIn("(abalorio 2 -1 agilidad)", details)
        self.assertNotIn("abalorio 1", details)

    def test_item_and_equipment_updates_only_refresh_the_visible_reward(self):
        h = self.host
        self.assertIn("Daga del catálogo", self.items()[0].details)
        emit = self.frame.scripts.OnEvent
        before = h.state.refreshes
        emit(self.frame, "ITEM_DATA_LOAD_RESULT", 999, True)
        self.assertEqual(h.state.refreshes, before)
        h.lua.execute("C_Item = {GetItemInfo=function(id) return 'Nombre local ' .. id end}")
        emit(self.frame, "ITEM_DATA_LOAD_RESULT", 501, True)
        self.assertEqual(h.state.refreshes, before + 1)
        self.assertIn("Nombre local 501", self.items()[0].details)
        emit(self.frame, "PLAYER_EQUIPMENT_CHANGED", 16, True)
        self.assertEqual(h.state.refreshes, before + 2)
        self.assertEqual(h.active()[1], 1)
        h.quest(100, onQuest=True)
        h.fire("QUEST_ACCEPTED", 100)
        before = h.state.refreshes
        emit(self.frame, "PLAYER_EQUIPMENT_CHANGED", 16, True)
        self.assertEqual(h.state.refreshes, before)
