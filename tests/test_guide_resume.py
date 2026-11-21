"""Exercise character migrations against native-style guides and game events."""
import json
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime

from tools.build_guide_legacy import build

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "RutaXP"


class GuideResumeTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("""
            ns={char={}, GuideEngine={}}; engine=ns.GuideEngine
            active,done,completed,quests = {},{},{},{}
            timers, frames, previews, catalog, selections = {},{},{},{},{}
            ready, map, level, cursor = true, 1426, 5, 1
            Enum={UIMapType={Zone=3}}
            C_Map = {
                GetBestMapForUnit=function() return map end,
                GetMapInfo=function(n)
                    if n==10000 then return {mapID=10000,parentMapID=1426,mapType=5} end
                    return {mapID=n,name='Zona '..n,mapType=3}
                end,
                GetPlayerMapPosition=function()
                    return {GetXY=function() return .28,.66 end}
                end
            }
            C_QuestLog={
                IsComplete=function(id) return completed[id] end,
                GetQuestObjectives=function(id) return quests[id] end,
                GetNumQuestLogEntries=function() return 0 end,
            }
            function ns:IsQuestDelivered(id) return done[id] end
            function ns:IsQuestActive(id) return active[id] end
            function GetZoneText() return 'Zona' end
            function UnitLevel() return level end
            function InCombatLockdown() return combat end
            function UnitOnTaxi() return taxi end
            function CreateFrame()
                local f={events={}}; frames[#frames+1]=f
                function f:RegisterEvent(event) self.events[event]=true end
                function f:SetScript(_,cb) self.cb=cb end
                return f
            end
            C_Timer={After=function(_,cb) timers[#timers+1]=cb end}
            function flush()
                local n=0
                while #timers>0 do n=n+1; assert(n<100); table.remove(timers,1)() end
            end
            function fire(event)
                for _,f in ipairs(frames) do if f.events[event] then f.cb(f,event) end end
                flush()
            end
            function login() fire('PLAYER_ENTERING_WORLD'); fire('QUEST_LOG_UPDATE') end
            engine.Ready=function() return ready end
            engine.Catalog=function() return catalog end
            engine.Current=function() return current,cursor end
            engine.SavedSelection=function()
                if native then return native.group,native.name,nativeStep end
            end
            engine.Select=function(g)
                current, cursor = g.processed or g,g.saved or 1
                selections[#selections+1]=g.key
                return true
            end
            engine.Preview=function(g) previews[g.key]=(previews[g.key] or 0)+1; return g end
            engine.SetStep=function(n) cursor=n end
            engine.Clear=function() current=nil; cursor=1; clears=(clears or 0)+1 end
            engine.Subscribe=function(cb) change=cb end
            engine.MapID=function(name) if name=="Dun Morogh" then return 1426 end end
            function el(tag,id,extra)
                local e=extra or {}; e.tag=tag; e.questId=id; return e
            end
            function s(zone,...)
                return {map=zone,elements={...}}
            end
            function guide(name, ...)
                local g = {name=name,key='g-'..name,group='g',steps={...}}
                catalog[#catalog+1]=g; return g
            end
            function duoJournal(state)
                journalState=state
                ns.GuideCarryover = {
                    Check=function()
                        if not dismissed and journalState then return journalState, "Diario del personaje" end
                    end,
                    Dismiss=function() dismissed=true end,
                }
            end
        """)
        self.g = self.lua.globals()
        self.lua.execute((ADDON / "GuideLegacyAnchors.lua").read_text(encoding="utf8"), "RutaXP", self.g.ns)
        self.lua.execute((ADDON / "GuideResume.lua").read_text(encoding="utf8"), "RutaXP", self.g.ns)

    def test_legacy_index_is_reproducible_for_all_57_chapters(self):
        snapshot = json.loads((ADDON / "Source/leveling.json").read_text(encoding="utf8"))
        self.assertEqual((ADDON / "GuideLegacyAnchors.lua").read_text(encoding="utf8"),build(snapshot))
        self.assertEqual(len(list(self.g.ns.legacyGuideAnchors)),len(snapshot["guides"]))
        for chapter in snapshot["guides"]:
            self.assertEqual(len(self.g.ns.legacyGuideAnchors[chapter["id"]]),len(chapter["steps"]))

    def test_active_quest_and_zone_match_real_legacy_char_after_filtered_steps(self):
        self.lua.execute("""
            local id="forever/alliance/dwarf-gnome/01-dun-morogh"
            local old=ns.legacyGuideAnchors[id]; local q=old[1][2]; assert(q)
            ns.char.activeGuide=id; ns.char.progress={[id]={routeRevision=old.revision,cursor=1}}
            early=guide('1-5 Otra zona',s(1429,el('accept',800)))
            g=guide('1-5 Valle',s('Dun Morogh',el('accept',q)),s(1426,el('complete',q)))
            g.processed={name=g.name,key=g.key,group=g.group,steps={
                s(1426),s(1426,el('accept',q)),s(1426,el('complete',q)),s(1426,el('turnin',q))}}
            map=10000; active[q]=true
            login()
            assert(current==g.processed and cursor==3)
            assert(ns.char.activeGuide==id and ns.char.progress[id].cursor==1)
            assert(ns.char.guideLink.key==g.key and #selections==1)
            change(); flush(); assert(#selections==1)
        """)

    def test_stale_provisional_first_step_cannot_send_high_level_character_back(self):
        self.lua.execute("""
            level=33
            local id="forever/alliance/06-ashenvale"
            local old=ns.legacyGuideAnchors[id]
            ns.char.activeGuide=id; ns.char.progress={[id]={routeRevision=old.revision,cursor=1}}
            native=guide('1-5 Valle',s(1426,el('accept',1)))
            nativeStep=1; current=native
            login()
            assert(ns.GuideResume.Status()=='unavailable' and not current and clears==1)
            assert(ns.char.activeGuide==id and not previews[native.key])
            change(); flush(); assert(clears==1)
            local manual=guide('Llaves de mazmorra',s(1429))
            assert(ns.GuideResume.SelectManually(manual))
            map=1439; fire('ZONE_CHANGED_NEW_AREA')
            assert(current==manual and ns.GuideResume.Status()=='manual')
        """)

    def test_matching_progress_from_native_session_precedes_legacy_or_nearby_quests(self):
        self.lua.execute("""
            g=guide('1-5 Valle',s(1426,el('accept',1)))
            native=guide('Otro capítulo',s(1439)); nativeStep=7; native.saved=7
            current=g
            login()
            assert(current==native and cursor==7 and ns.GuideResume.Status()=='saved')
            map=1439; fire('ZONE_CHANGED_NEW_AREA'); assert(#selections==1 and cursor==7)
        """)

    def test_restore_manual_bookmark_explicit_redetect_and_new_character(self):
        self.lua.execute("""
            mine=guide('Monturas',s(1426))
            ns.char.guideLink={key=mine.key,mode='manual'}
            elsewhere=guide('4-6 Bosque',s(1429,el('accept',52)))
            good=guide('4-6 Dun Morogh',s(1426),s(1426,el('accept',42)))
            login(); assert(current==mine and ns.GuideResume.Status()=='manual')
            ns.GuideResume.UseZone(); assert(current==good and cursor==1)
            map=1429; fire('ZONE_CHANGED_NEW_AREA')
            assert(current==elsewhere)
        """)

    def test_wait_for_live_journal_catalog_zone_and_combat_then_keep_chain_intact(self):
        self.lua.execute("""
            ready=false
            g=guide('4-6 Dun Morogh',
                s(1426,el('accept',1)),s(1426,el('accept',2)),
                s(1426,el('complete',2)),s(1426,el('complete',1),el('turnin',2)))
            fire('PLAYER_ENTERING_WORLD'); ready=true; change(); flush(); assert(not current)
            active[2]=true; combat=true; fire('QUEST_LOG_UPDATE'); assert(not current)
            combat=false; fire('PLAYER_REGEN_ENABLED')
            assert(current==g and cursor==1) -- Quest one must be acquired before step four.
        """)

    def test_unsupported_or_wrong_race_chapters_never_become_auto_default(self):
        self.lua.execute("""
            a=guide('4-6 Otra raza',s(1426)); a.lowPrio='*g'
            h=guide('4-6 Hardcore',s(1426)); h.hardcore=true
            d=guide('4-6 Mazmorra',s(1426)); d.enabledungeons=true
            g=guide('1-5 Valle',s(1426,el('accept',1)))
            nextChapter=guide('5-7 Seguimiento',s(1429,el('accept',3)))
            login(); assert(current==g)
            assert(not previews[a.key] and not previews[h.key] and not previews[d.key])
            current=nextChapter; cursor=4; change(); flush()
            assert(ns.char.guideLink.key==nextChapter.key and ns.char.guideLink.mode=='auto' and cursor==4)
            another=guide('4-6 Otra zona',s(1439))
            map=1439; fire('ZONE_CHANGED_NEW_AREA')
            assert(current==another and ns.char.guideLink.mode=='auto')
            change(); flush(); assert(#selections==2)
        """)

    def test_replaces_unavailable_when_player_reaches_supported_zone(self):
        self.lua.execute("""
            map=1439; g=guide('4-6 Bosque',s(1429,el('accept',1)))
            login(); assert(ns.GuideResume.Status()=='unavailable')
            map=1429; fire('ZONE_CHANGED_NEW_AREA')
            assert(current==g and ns.GuideResume.Status()=='auto')
        """)

    def test_reload_rechecks_automatic_zone_and_preserves_real_native_cursor(self):
        self.lua.execute("""
            native=guide('4-6 Ruta A',s(1426)); nativeStep=1
            ns.char.guideLink={mode='auto',key=native.key}
            zone=guide('4-6 Ruta B',s(1429))
            map=1429; login()
            assert(current==zone and ns.GuideResume.Status()=='auto')
        """)

    def test_saved_revision_two_cursor_four_links_to_current_dun_morogh_row_three(self):
        self.lua.execute("""
            local id='forever/alliance/dwarf-gnome/01-dun-morogh'
            ns.char.activeGuide=id; ns.char.progress={[id]={routeRevision=2,cursor=4}}
            local g=guide('1-5 Valle',s(1426),s(1426,el('accept',3106)))
            login()
            assert(current==g and cursor==2)
            assert(ns.char.progress[id].cursor==4 and ns.char.progress[id].routeRevision==2)
        """)

    def test_all_delivered_chapter_at_a_level_boundary_does_not_win_again(self):
        self.lua.execute("""
            done[80]=true
            old=guide('1-5 Inicio',s(1426,el('accept',80)),s(1426,el('turnin',80)))
            new=guide('5-11 Zona',s(1426,el('accept',83)))
            login(); assert(current==new and cursor==1)
        """)

    def test_restore_more_advanced_native_step_if_preloaded_default_dropped_it(self):
        self.lua.execute("""
            current=guide('1-5 Temporal',s(1426))
            native=guide('1-5 Valle',s(1426),s(1426),s(1426),s(1426))
            nativeStep=3
            login()
            assert(current==native and cursor==3 and ns.GuideResume.Status()=='saved')
        """)

    def test_follow_zone_holds_manual_guide_then_changes_once_on_entering_covered_zone(self):
        self.lua.execute("""
            g=guide('Monturas',s(1429))
            nextZone=guide('4-6 Bosque',s(1429))
            ns.char.guideLink={mode='manual',key=g.key}
            login()
            cursor=7
            notices=0
            function ns.OnGuideResumeChanged() notices=notices+1; change() end
            local mode,text,found=ns.GuideResume.UseZone()
            assert(mode=='auto' and not found and text:match('Sin guía') and current==g and cursor==7)
            assert(ns.char.guideLink.awaitingZone and notices==1)
            flush(); assert(notices==1 and #selections==1)
            combat=true
            mode,text,found=ns.GuideResume.UseZone()
            assert(not found and text:match('combate'))
            combat=false; taxi=true
            mode,text,found=ns.GuideResume.UseZone()
            assert(not found and text:match('aterrizar'))
            taxi=false; map=1429; fire('ZONE_CHANGED_NEW_AREA')
            assert(current==nextZone and ns.char.guideLink.mode=='auto' and not ns.char.guideLink.awaitingZone)
            change(); flush(); assert(#selections==2 and notices==2)
        """)

    def test_native_chapter_change_keeps_manual_and_saved_modes(self):
        self.lua.execute("""
            g=guide('Guía de mazmorras',s(1426))
            continuation=guide('Siguiente mazmorra',s(1426)); guide('4-6 Bosque',s(1429))
            native=g; login()
            current=continuation; cursor=3; change(); flush()
            assert(ns.char.guideLink.mode=='saved' and ns.char.guideLink.key==continuation.key and cursor==3)
            assert(ns.GuideResume.SelectManually(g))
            current=continuation; cursor=5; change(); flush()
            map=1429; fire('ZONE_CHANGED_NEW_AREA')
            assert(ns.char.guideLink.mode=='manual' and current==continuation and cursor==5)
            assert(#selections==2)
        """)

    def test_duo_journal_precedes_default_and_resumes_once_after_last_quest(self):
        self.lua.execute("""
            duoJournal('pending'); ready=false
            old=guide('1-5 Inicio',s(1426)); current=old
            g=guide('4-6 Zona',s(1429))
            map=1429; login()
            assert(ns.GuideResume.Status()=='pending' and ns.GuideResume.HoldingJournal() and not clears and #selections==0)
            ready=true; change(); flush()
            assert(not current and clears==1 and #selections==0)
            journalState='journal'; fire('QUEST_LOG_UPDATE')
            assert(ns.GuideResume.Status()=='journal' and #selections==0)
            change(); flush(); fire('QUEST_LOG_UPDATE'); assert(clears==1)
            journalState=nil; fire('QUEST_LOG_UPDATE')
            assert(ns.GuideResume.Status()=='auto' and not ns.GuideResume.HoldingJournal() and current==g and #selections==1)
            fire('QUEST_LOG_UPDATE'); change(); flush(); assert(#selections==1)
        """)

    def test_verified_official_checkpoint_survives_client_reload_in_the_journal(self):
        self.lua.execute("""
            duoJournal('journal')
            g=guide('Rango nativo',s(1439),s(1439),s(1439),s(1439))
            current=guide('1-5 Inicio',s(1426))
            native=g; nativeStep=3
            login()
            assert(ns.char.heldOfficialGuide.key==g.key and ns.char.heldOfficialGuide.step==3)
            assert(not current and ns.GuideResume.Status()=='journal' and #selections==0)
            -- The native character save now corresponds to its empty guide.
            frames={}; timers={}; native=nil; nativeStep=nil; g.saved=2
        """)
        self.lua.execute((ADDON / "GuideResume.lua").read_text(encoding="utf8"), "RutaXP", self.g.ns)
        self.lua.execute("""
            login()
            assert(not current and ns.char.heldOfficialGuide.key==g.key)
            journalState=nil; fire('QUEST_LOG_UPDATE')
            assert(current==g and cursor==3 and ns.GuideResume.Status()=='saved')
            assert(not ns.char.heldOfficialGuide and #selections==1)
            change(); flush(); assert(#selections==1)
        """)

    def test_explicit_manual_selection_and_follow_zone_can_leave_journal(self):
        self.lua.execute("""
            duoJournal('journal'); manual=guide('Otra guía',s(1439))
            zoneGuide=guide('4-6 Zona',s(1426))
            login()
            assert(ns.GuideResume.SelectManually(manual) and dismissed)
            fire('QUEST_LOG_UPDATE'); assert(current==manual and ns.GuideResume.Status()=='manual')
            dismissed=false; ns.char.guideLink=nil
            change(); flush(); assert(ns.GuideResume.Status()=='journal' and not current)
            local mode,_,matched=ns.GuideResume.UseZone()
            assert(matched and mode=='auto' and current==zoneGuide and dismissed)
            fire('QUEST_LOG_UPDATE'); change(); flush(); assert(current==zoneGuide)
        """)

    def test_existing_manual_choice_wins_and_no_coverage_after_journal_is_stable(self):
        self.lua.execute("""
            duoJournal('journal')
            g=guide('1-5 Valle',s(1426)); ns.char.guideLink={key=g.key,mode='manual'}
            level=33; login(); assert(current==g and ns.GuideResume.Status()=='manual' and not clears)
            ns.char.guideLink=nil; change(); flush()
            assert(not current and ns.GuideResume.Status()=='journal')
            journalState=nil; fire('QUEST_LOG_UPDATE')
            assert(not current and ns.GuideResume.Status()=='unavailable' and not ns.char.heldOfficialGuide)
            change(); flush(); fire('QUEST_LOG_UPDATE')
            assert(#selections==1 and clears==1)
        """)
