"""Run the chat command against a mixed journal in the shipping Desolace chapter."""

import unittest

from test_addon import ADDON
from test_quest_engine import QuestEngineHost


class DesolaceCleanupCommandTests(unittest.TestCase):
    def test_one_confirmation_abandons_only_the_off_route_quest(self):
        h = QuestEngineHost(catalog=True)
        h.state.classToken, h.state.level = "ROGUE", 33
        h.initialize()
        for name in ("GroupQuestData", "RogueRewardData", "RogueRewards", "Extensions",
                     "QuestCleanupData", "QuestCleanupJournal", "QuestCleanupPlan", "QuestCleanup"):
            h.load((ADDON / (name + ".lua")).read_text(encoding="utf8"), "RutaXP", h.ns)
        guide = "forever/alliance/30-40/02-desolace"
        h.ns.char.activeGuide = guide
        h.call("GetProgress", guide).cursor = 14
        for quest, title in [(16, "Un trago para Gerard"), (104, "La amenaza costera"),
                             (1387, "Colección de orejas"), (1459, "Componentes para Reivindicadores y Cía.")]:
            h.quest(quest, onQuest=True, complete=quest == 104)
            h.state.entries[len(h.state.entries) + 1] = h.table({
                "title": title, "questID": quest, "isHeader": False, "isHidden": False,
                "isTask": False, "isInternalOnly": False, "isBounty": False, "isStory": False,
            })
        h.lua.execute("""
            function C_QuestLog.GetNumQuestLogEntries() return #TEST.entries, #TEST.entries end
            function C_QuestLog.CanAbandonQuest(id) return true end
            function C_QuestLog.GetQuestTagInfo() end
            function C_QuestLog.ReadyForTurnIn(id) return C_QuestLog.IsComplete(id) end
            function C_QuestLog.GetNumQuestObjectives() return 1 end
            function C_QuestLog.GetQuestObjectives()
                return {{numRequired=5, numFulfilled=0, finished=false}}
            end
            TEST.selected, TEST.target, TEST.abandons = 1459, 0, 0
            function C_QuestLog.GetSelectedQuest() return TEST.selected end
            function C_QuestLog.SetSelectedQuest(id) TEST.selected = id end
            function C_QuestLog.GetAbandonQuest() return TEST.target end
            function C_QuestLog.SetAbandonQuest() TEST.target = TEST.selected end
            function C_QuestLog.GetAbandonQuestItems() return {} end
            function C_QuestLog.AbandonQuest()
                TEST.abandons = TEST.abandons + 1
                TEST.quests[TEST.target].onQuest = false
                for i, entry in ipairs(TEST.entries) do
                    if entry.questID == TEST.target then table.remove(TEST.entries, i); break end
                end
            end
            C_Timer = {After = function(_, fn) fn() end}
            StaticPopupDialogs = {}
            function StaticPopup_Visible() return false end
            function StaticPopup_Show(name, count, list, data)
                TEST.confirm = function() StaticPopupDialogs[name].OnAccept(nil, data) end
                TEST.list = list
                return {}
            end
        """)
        h.globals.SlashCmdList.RUTAXP("limpiar ver")
        self.assertIsNone(h.state.confirm)
        h.globals.SlashCmdList.RUTAXP("limpiar")
        self.assertEqual(h.state.list, "Un trago para Gerard")
        self.assertEqual(h.state.abandons, 0)
        h.state.confirm()
        self.assertEqual(h.state.abandons, 1)
        self.assertFalse(h.state.quests[16].onQuest)
        self.assertEqual(h.state.selected, 1459)
        self.assertEqual({entry.questID for entry in h.state.entries.values()}, {104, 1387, 1459})
