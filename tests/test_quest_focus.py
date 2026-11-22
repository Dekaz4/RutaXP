"""Journal focus, initial chapter recovery and transitions use the same live journal."""
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime


ADDON = Path(__file__).resolve().parents[1] / "RutaXP"


class QuestFocusTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("""
            guide={id="hunt", steps={
                {goals={{t="kill",quest=10}}},
                {map=12,goals={{t="collect",quest=20,oi=1}}},
            }}
            recovery={id="resumed",temporary=true,recovery=true,steps={{goals={{t="turnin",quest=90}}}}}
            ns={char={progress={hunt={cursor=1,confirmed={},skipped={keep=true}}}},
                guides={hunt=guide,resumed=recovery},order={"hunt","resumed"},
                DungeonQuestData={restedWorld={[30]=true}},RestedQuestState={
                    Active=function() return true end, Ready=function() return false end}}
            ns.GetProgress=function(self,id) return self.char.progress[id] end
            ns.MatchesConditions=function() return true end
            C_Map={GetBestMapForUnit=function() return 12 end}
            quantity={[20]=1,[30]=2}; journal={20,30}; tracked=0
            C_SuperTrack={GetSuperTrackedQuestID=function() return tracked end}
            C_QuestLog={GetNumQuestLogEntries=function() return #journal end,
                GetInfo=function(i) return {questID=journal[i]} end,
                GetQuestObjectives=function(id) return {{numFulfilled=quantity[id]}} end}
        """)
        self.lua.execute((ADDON / "QuestFocus.lua").read_text(encoding="utf-8-sig"), "RutaXP", self.lua.globals().ns)

    def test_registered_step_or_recovery_blocks_tracking_other_or_later_quests(self):
        self.lua.execute("""
            local f=ns.WorldQuestFocus
            local progress=ns.char.progress.hunt
            local getObjectives=C_QuestLog.GetQuestObjectives
            for _,active in ipairs({"hunt","resumed"}) do
                ns.char.activeGuide=active
                for _,id in ipairs({20,30}) do
                    tracked=id
                    C_QuestLog.GetQuestObjectives=function() error("A chapter scanned unrelated journal objectives") end
                    f.TrackingChanged(); f.Observe(); assert(not f.Current())
                    quantity[id]=quantity[id]+1; f.Observe(); assert(not f.Current())
                end
            end
            C_QuestLog.GetQuestObjectives=getObjectives
            assert(ns.char.progress.hunt==progress and progress.cursor==1 and progress.skipped.keep)
            assert(not ns.char.progress.resumed)
            assert(f.StartingStep(guide)==2 and f.Match(20,guide,12).si==2)
        """)

    def test_leaving_a_chapter_does_not_reuse_journal_gains_from_before_it(self):
        self.lua.execute("""
            local f=ns.WorldQuestFocus
            f.Observe(); quantity[20]=2; f.Observe(); assert(f.Current()==20)
            ns.char.activeGuide="hunt"; assert(not f.Current())
            quantity[30]=3
            ns.char.activeGuide="retired-chapter"
            f.Observe(); assert(not f.Current())
            quantity[30]=4; f.Observe(); assert(f.Current()==30)
            tracked=20; f.TrackingChanged(); assert(f.Current()==20)
        """)
