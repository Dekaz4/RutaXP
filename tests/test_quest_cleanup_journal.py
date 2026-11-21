import unittest

from test_addon import ADDON, LuaRuntime


class QuestCleanupJournalTests(unittest.TestCase):
    def journal(self, setup=""):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("""
            NS = {}
            function UnitClass() return "Pícara", "ROGUE" end
            LOCALIZED_CLASS_NAMES_MALE = { ROGUE = "Pícaro" }
            secret = {}
            function issecretvalue(x) return x == secret end
            function quest(id)
                return {title = "Misión " .. id, isHeader = false, questID = id,
                    isHidden = false, isTask = false, isInternalOnly = false,
                    isBounty = false, isStory = false}
            end
            log = {{title = "Desolace", isHeader = true, isCollapsed = true}, quest(1), quest(2)}
            total = 2
            objectives = {{finished = false, numFulfilled = 0, numRequired = 8}}
            C_QuestLog = {
                GetNumQuestLogEntries = function() return #log, total end,
                GetInfo = function(i) return log[i] end,
                CanAbandonQuest = function() return true end,
                IsComplete = function() return false end,
                ReadyForTurnIn = function() return nil end,
                GetQuestTagInfo = function() return nil end,
                GetNumQuestObjectives = function() return #objectives end,
                GetQuestObjectives = function() return objectives end,
            }
            function read() return NS:GetQuestCleanupJournal() end
        """)
        lua.eval("loadstring")((ADDON / "QuestCleanupJournal.lua").read_text(encoding="utf-8"))(
            "RutaXP", lua.globals().NS
        )
        lua.execute(setup)
        return lua.globals()

    def test_reads_all_collapsed_quests_without_writing_ui_or_selection(self):
        game = self.journal("""
            function forbidden() error("journal was mutated") end
            ExpandQuestHeader, CollapseQuestHeader = forbidden, forbidden
            C_QuestLog.SetSelectedQuest, C_QuestLog.SetAbandonQuest = forbidden, forbidden
        """)
        rows = game.read()
        self.assertEqual([rows[i].id for i in (1, 2)], [1, 2])
        self.assertTrue(game.log[1].isCollapsed)
        self.assertEqual(rows[1].index, 2)
        self.assertEqual(rows[2].header, "Desolace")
        self.assertFalse(rows[1].hasProgress)
        self.assertTrue(rows[1].canAbandon)
        self.assertIsNone(rows[1].protectedReason)

    def test_rejects_unidentifiable_or_incomplete_snapshot(self):
        for setup in ["total=3", "log[3].questID=1", "log[2].questID=secret",
                      "total=1", "log[2].isHidden=true", "log[2].isInternalOnly=secret",
                      "log[2].title=secret", "C_QuestLog.GetInfo=function() return nil end",
                      "C_QuestLog.GetNumQuestLogEntries=function() return 3 end"]:
            with self.subTest(setup=setup):
                rows, reason = self.journal(setup).read()
                self.assertIsNone(rows)
                self.assertTrue(reason)

    def test_native_evidence_keeps_complete_progressed_special_or_uncertain_quests(self):
        for setup in [
            "C_QuestLog.IsComplete=function() return true end",
            "C_QuestLog.ReadyForTurnIn=function() return true end",
            "objectives[1].finished=true",
            "objectives[1].numFulfilled=1",
            "objectives={}",
            "objectives[1].numRequired=0",
            "C_QuestLog.GetNumQuestObjectives=function() return 2 end",
            "objectives[1].numFulfilled=secret",
            "C_QuestLog.CanAbandonQuest=function() return false end",
            "C_QuestLog.GetQuestTagInfo=function() return {tradeskillLineID=171} end",
            "log[1].title='Pícaro'",
            "GetQuestLogSpecialItemInfo=function() return 'item:17' end",
        ]:
            with self.subTest(setup=setup):
                rows = self.journal(setup).read()
                self.assertTrue(rows[1].protectedReason)

    def test_restricted_row_does_not_hide_other_readable_quests(self):
        game = self.journal("""
            C_QuestLog.GetQuestObjectives = function(id)
                if id == 1 then error("restricted") end
                return objectives
            end
        """)
        rows = game.read()
        self.assertTrue(rows[1].protectedReason)
        self.assertIsNone(rows[2].protectedReason)

    def test_extra_internal_quest_is_retained_without_using_a_slot(self):
        rows = self.journal("log[4]=quest(3); log[4].isHidden=true").read()
        self.assertEqual(len(rows), 3)
        self.assertIsNone(rows[1].protectedReason)
        self.assertTrue(rows[3].protectedReason)

    def test_zero_campaign_is_normal_and_positive_campaign_is_kept(self):
        rows = self.journal("log[2].campaignID=0; log[3].campaignID=44").read()
        self.assertIsNone(rows[1].protectedReason)
        self.assertTrue(rows[2].protectedReason)
