"""Keep the paladin's own journal and duo route intact across the migration."""
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime


ADDON = Path(__file__).resolve().parents[1] / "RutaXP"


class GuideCarryoverTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("""
            chapter = "forever/alliance/06-ashenvale"
            ns = {char = {
                activeGuide=chapter, progress={[chapter]={cursor=58,routeRevision=6}},
                duo={enabled=true,wait=false}, duoJourney={history={}},
            }, GuideResume={}}
            clock, online, inGroup = 100, true, true
            log, objectives, turnins, shared, waypoints = {}, {}, {}, {}, {}
            sent, delivered, timers, frames = {}, {}, {}, {}
            function GetTime() return clock end
            function GetServerTime() return math.floor(clock) end
            function UnitExists(unit) return unit == "player" or (unit=="party1" and inGroup) end
            function UnitIsConnected(unit) return unit=="player" or (unit=="party1" and online) end
            function UnitClass() return "Paladín", "PALADIN" end
            function IsInGroup() return inGroup end
            function IsInRaid() return false end
            function GetNumGroupMembers() return inGroup and 2 or 0 end
            function GetNumSubgroupMembers() return inGroup and 1 or 0 end
            function CreateFrame()
                local frame={events={}}
                function frame:RegisterEvent(event) self.events[event]=true end
                function frame:SetScript(_,callback) self.callback=callback end
                frames[#frames+1]=frame
                return frame
            end
            function fire(event)
                for _,frame in ipairs(frames) do
                    if frame.events[event] then frame.callback(frame,event) end
                end
            end
            function ns.GuideResume.Sync() return ns.GuideCarryover.Check() end
            C_Timer={After=function(delay, f)
                timers[#timers+1]={at=clock+delay, run=f}
            end}
            function advance(seconds)
                clock=clock+seconds
                local due=timers
                timers={}
                for _,timer in ipairs(due) do
                    if timer.at<=clock then timer.run() else timers[#timers+1]=timer end
                end
            end
            C_Map={GetBestMapForUnit=function() return 1455 end,
                GetMapInfo=function(id) if id==1455 then return {mapID=id,name="Forjaz"} end end}
            C_QuestLog={
                GetNumQuestLogEntries=function() return entries or #log, total or #log end,
                GetInfo=function(i) return log[i] end,
                GetQuestObjectives=function(id) return objectives[id] or {} end,
                GetNumQuestObjectives=function(id) return #(objectives[id] or {}) end,
                IsComplete=function(id) return turnins[id] or false end,
                ReadyForTurnIn=function(id) return turnins[id] or false end,
                IsQuestFlaggedCompleted=function(id) return delivered[id] or false end,
                IsUnitOnQuest=function(unit,id)
                    assert(unit=="party1")
                    return shared[id]
                end,
                GetNextWaypoint=function(id) return unpack(waypoints[id] or {}) end,
            }
            function C_QuestLog.GetLogIndexForQuestID(id)
                for i,row in pairs(log) do if row.questID==id then return i end end
            end
            function C_QuestLog.IsOnQuest(id) return C_QuestLog.GetLogIndexForQuestID(id)~=nil end
            function ns:IsQuestActive(id) return C_QuestLog.IsOnQuest(id) end
            function ns:IsQuestDelivered(id) return C_QuestLog.IsQuestFlaggedCompleted(id) end
            function QuestMapFrame_OpenToQuestDetails(id) sent[#sent+1]=id end
            function row(id,title) return {title=title or ("Misión "..id),questID=id,isHeader=false} end
            function obj(text,n,max) return {text=text,numFulfilled=n,numRequired=max,finished=n>=max} end
            function heads()
                local result={}
                for _,v in ipairs(ns.GuideCarryover.Rows()) do
                    if v.questID then result[#result+1]=v.questID end
                end
                return result
            end
            function mentions(word)
                for _,v in ipairs(ns.GuideCarryover.Rows()) do
                    if v.text:lower():find(word,1,true) then return true end
                end
            end
            function has(id)
                for _,v in ipairs(heads()) do if v==id then return true end end
                return false
            end
        """)
        self.load("GuideLegacyAnchors.lua")
        self.lua.execute("""
            function ns.GuideResume.LegacyPosition(char)
                local data=ns.legacyGuideAnchors[char.activeGuide]
                local saved=char.progress[char.activeGuide]
                if saved and data then return data[saved.cursor],data,saved.cursor end
            end
        """)
        self.load("GuideCarryover.lua")

    def load(self, filename):
        self.lua.execute((ADDON / filename).read_text(encoding="utf-8-sig"), "RutaXP",
                         self.lua.globals().ns)

    def reload_carryover(self):
        self.lua.execute("ns.GuideCarryover=nil; frames={}; timers={}")
        self.load("GuideCarryover.lua")

    def test_paladin_and_friend_two_quests_ahead(self):
        self.lua.execute("""
            local anchor=ns.legacyGuideAnchors[chapter][58]
            assert(anchor[1]==1455 and anchor[2]==1072)
            log={row(5645),row(1072,"Un viejo colega")}
            turnins[1072]=true
            objectives[5645]={obj("Objetivo propio: 2/5",2,5)}
            shared[1072]=true
            -- The other two belong to the partner; do not manufacture local tasks.
            shared[1274],shared[343]=true,true
            local status,message=ns.GuideCarryover.Check()
            assert(status=="journal" and type(message)=="string")
            local ids=heads()
            assert(ids[1]==1072 and ids[2]==5645 and #ids==2)
            assert(mentions("entregar") and mentions("ambos"))
            local found=false
            for _,r in ipairs(ns.GuideCarryover.Rows()) do
                if r.text:find("Objetivo propio",1,true) then found=true; assert(not r.questID) end
            end
            assert(found)
            assert(ns.char.progress[chapter].cursor==58)
            shared[1072]=nil
            ns.GuideCarryover.Check()
            assert(not mentions("ambos") and has(1072))
        """)

    def test_captured_batch_survives_reload_without_absorbing_new_quests(self):
        self.lua.execute("""
            log={row(1072),row(5645)}
            assert(ns.GuideCarryover.Check()=="journal")
            log={row(968),row(1072),row(5645)}
            ns.GuideCarryover.Check()
            assert(not has(968) and #heads()==2)
        """)
        self.reload_carryover()
        self.lua.execute("""
            fire("QUEST_LOG_UPDATE")
            assert(ns.GuideCarryover.Check()=="journal")
            assert(not has(968) and has(5645) and has(1072))
            delivered[1072]=true
            log={row(968),row(5645)}
            ns.GuideCarryover.Check()
            assert(#heads()==1 and has(5645))
            -- A briefly empty journal during a loading screen must not end the batch.
            log={}
            ns.GuideCarryover.Check()
            advance(0.5)
            log={row(5645),row(968)}
            assert(ns.GuideCarryover.Check()=="journal" and has(5645))
            delivered[5645]=true
            log={row(968)}
            ns.GuideCarryover.Check()
            advance(0.6)
            assert(ns.GuideCarryover.Check()~=nil)
            advance(1.5)
            assert(ns.GuideCarryover.Check()==nil)
            assert(ns.char.progress[chapter].cursor==58)
        """)
        self.reload_carryover()
        self.lua.execute("assert(ns.GuideCarryover.Check()==nil)")

    def test_first_empty_and_incomplete_frames_do_not_freeze_a_partial_set(self):
        self.lua.execute("""
            local carry=ns.GuideCarryover
            assert(carry.Check()=="pending")
            advance(2)
            fire("QUEST_LOG_UPDATE")
            assert(carry.Check()=="pending")
            advance(0.25)
            entries,total=3,2
            log={[1]={title="Forjaz",isHeader=true},[3]=row(5645)}
            assert(carry.Check()=="pending")
            advance(0.25)
            log[2]=row(1072)
            assert(carry.Check()=="journal")
            assert(#heads()==2 and heads()[1]==1072 and has(5645))
        """)

    def test_waypoint_open_and_dismiss_are_read_only(self):
        self.lua.execute("""
            local carry=ns.GuideCarryover
            log={row(1072),row(5645)}
            assert(carry.Check()=="journal")
            for _,coords in ipairs({{}, {0,.2,.3}, {1455,-.1,.3}, {1455,.2,1.1},
                                    {1455,0/0,.4}}) do
                waypoints[1072]=coords
                assert(carry.Waypoint()==nil)
            end
            waypoints[1072]={1455,.25,.8}
            local map,x,y=carry.Waypoint()
            assert(map==1455 and x==.25 and y==.8)
            waypoints[5645]={1453,.75,.45}
            carry.OpenQuest(5645)
            assert(#sent==1 and sent[1]==5645)
            map,x,y=carry.Waypoint()
            assert(map==1453 and x==.75 and y==.45)
            carry.OpenQuest(1274)
            assert(#sent==1)
            carry.Dismiss()
            assert(carry.Check()==nil and #log==2 and log[1].questID==1072 and log[2].questID==5645)
            assert(ns.char.progress[chapter].cursor==58 and not ns.char.duo.wait)
        """)

    def test_solo_characters_and_unknown_legacy_chapters_are_unaffected(self):
        self.lua.execute("""
            local carry=ns.GuideCarryover
            log={row(1072)}
            ns.char.duo.enabled=false
            assert(carry.Check()==nil)
            ns.char.duo.enabled=true
            ns.char.activeGuide="other"
            assert(carry.Check()==nil)
        """)

    def test_unrelated_quests_only_prioritized_with_live_evidence(self):
        self.lua.execute("""
            log={row(801234),row(801235),row(801236),row(1072)}
            objectives[801234]={obj("Primer objeto recogido",1,4)}
            shared[801235]=true
            shared[801236]=false
            assert(ns.GuideCarryover.Check()=="journal")
            local ids=heads()
            assert(#ids==3 and ids[1]==1072 and has(801234) and has(801235))
            assert(not has(801236))
            online=false
            ns.GuideCarryover.Check()
            assert(has(801235) and not mentions("ambos"))
        """)


if __name__ == "__main__":
    unittest.main()
