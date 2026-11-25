from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime

from tools.suite_map_journal import transform_lua


class MapJournalIntegrationTests(unittest.TestCase):
    def test_gamer_mode_applies_once_per_character_before_the_chooser(self):
        module = (Path(__file__).resolve().parents[1] / "RutaXP/JournalMode.lua").read_text(encoding="utf8")
        self.lua.globals().module = module
        self.lua.execute("""
            function CreateFrame()
                return {RegisterEvent=function() end, UnregisterEvent=function() end,
                    SetScript=function(_, _, handler) loaded=handler end}
            end
            local player = {rpgKills={BRD=true}, journalMode="rpg"}
            local journal = {SetJournalMode=function(mode)
                assert(mode == "gamer")
                ForeverDungeonJournalCharacterDB = ForeverDungeonJournalCharacterDB or {}
                ForeverDungeonJournalCharacterDB.journalMode = mode
            end}
            local function login(db, embedded)
                ForeverDungeonJournalCharacterDB = db
                assert(loadstring(module))("RutaXP", {GetEmbeddedModule=function() return embedded end})
                loaded(CreateFrame(), "ADDON_LOADED", "Blizzard_WorldMap")
                assert(db == ForeverDungeonJournalCharacterDB)
                loaded(CreateFrame(), "ADDON_LOADED", "RutaXP")
                return ForeverDungeonJournalCharacterDB
            end
            assert(login(nil, nil) == nil)
            local new = login(nil, journal)
            assert(new.journalMode == "gamer")
            assert(login(player, journal) == player and player.rpgKills.BRD and player.journalMode == "gamer")
            player.journalMode = "rpg"
            assert(login(player, journal).journalMode == "rpg")
        """)

    def setUp(self):
        self.lua = LuaRuntime()
        self.lua.execute("""
            function GetAddOnMetadata(name, field)
                if name == "RutaXP" then
                    return ({ ["X-OpenMap-Version"]="v0.8.11",
                              ["X-ForeverDungeonJournal-Version"]="2.1.2" })[field]
                end
            end
        """)

    def test_map_uses_embedded_assets_and_starts_on_host_load(self):
        module = self.lua.table()
        self.lua.execute(transform_lua("OpenMap", "Core.lua", r'''
            local ADDON, ns = ...
            ns.name = ADDON
            ns.version = GetAddOnMetadata(ADDON, "Version")
            ns.Media = { path = "Interface\\AddOns\\" .. ADDON .. "\\Media\\" }
        '''), "OpenMap", module)
        self.assertEqual(module.name, "OpenMap")
        self.assertEqual(module.version, "v0.8.11")
        self.assertEqual(module.Media.path, "Interface\\AddOns\\RutaXP\\Modules\\OpenMap\\Media\\")
        self.lua.execute(transform_lua("OpenMap", "Init.lua", '''
            local ADDON, ns = ...
            function ns.event(event, name)
                return event == "ADDON_LOADED" and name == ADDON
            end
        '''), "OpenMap", module)
        self.assertFalse(module.event("ADDON_LOADED", "Blizzard_WorldMap"))
        self.assertTrue(module.event("ADDON_LOADED", "RutaXP"))
        self.assertFalse(module.event("PLAYER_LOGIN", "RutaXP"))

    def test_journal_reports_native_version_to_its_ui_peers_and_export(self):
        for path, expression in (
            (Path("Core") / "Journal.lua", 'GetAddOnMetadata("ForeverDungeonJournal", "Version")'),
            (r"Systems\VersionCheck.lua", 'GetAddOnMetadata(ADDON_NAME, "Version")'),
            ("Systems/CharacterSnapshot.lua", "metadata('ForeverDungeonJournal','Version')"),
            ("Systems/OptionsPanel.lua", 'select(2, pcall(getter, "ForeverDungeonJournal", "Version"))'),
            ("Systems/SettingsPanel.lua", 'select(2, pcall(getter, "ForeverDungeonJournal", "Version"))'),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.lua.execute(transform_lua("ForeverDungeonJournal", path, '''
                    local ADDON_NAME = ...
                    local metadata, getter = GetAddOnMetadata, GetAddOnMetadata
                    return ''' + expression), "ForeverDungeonJournal"), "2.1.2")

    def test_dungeon_entrance_default_and_existing_preference(self):
        patched = transform_lua("OpenMap", "Map/Dungeons.lua", '''
            local saved = ...
            local d = {}
            d.entranceClick = "map"
            return saved.entranceClick or d.entranceClick
        ''')
        self.assertEqual(self.lua.execute(patched, self.lua.table()), "journal")
        self.assertEqual(self.lua.execute(patched, self.lua.table(entranceClick="map")), "map")

    def test_other_addons_and_libraries_keep_their_own_identity(self):
        text = 'return GetAddOnMetadata(ADDON, "Version")'
        self.assertEqual(transform_lua("RXPGuides", "Core.lua", text), text)
        self.assertEqual(transform_lua("OpenMap", "Libs/AnotherAddon/Core.lua", text), text)
        self.assertEqual(transform_lua("ForeverDungeonJournal", "Core/Journal.lua", text), text)

    def test_flight_filter_wins_over_legacy_switch_zoom_and_exploration(self):
        self.lua.execute('''
            RutaXPWorldMapTracking = { Get = function(key) return state[key] end }
            state = {flight=true}; S = {}; places = {hidden=false, world={flight=true}}
        ''')
        self.lua.execute(transform_lua("OpenMap", "Map/Stitch.lua", '''
            function S.WorldPinsHidden(key)
                return places.hidden and places.world[key] or false
            end
            function visible(key, set, zoom)
                local from = set.minZoom
                local shown = set.on and not S.WorldPinsHidden(key) and zoom >= from
                return shown
            end
        '''))
        self.lua.execute('''
            assert(visible("flight", {minZoom=8,on=false}, 1))
            state.flight=false
            assert(not visible("flight", {minZoom=1,on=true}, 12))
            state.flight=nil
            assert(not visible("flight", {minZoom=3,on=true}, 1))
            assert(visible("flight", {minZoom=3,on=true}, 5))
            assert(not visible("boats", {minZoom=3,on=false}, 5))
            places.hidden=true
            assert(S.WorldPinsHidden("rutaxp_service_mailbox"))
            assert(S.WorldPinsHidden("rutaxp_service_lowLevelQuests"))
            assert(not S.WorldPinsHidden("userpins"))
        ''')
        self.lua.execute(transform_lua("OpenMap", "Map/Flights.lua", '''
            function knownOnly(known)
                local mod = {db={foundOnly=true}}
                local pin = { SetShown=function(self, shown) self.shown=shown end }
                pin:SetShown(known or not mod.db.foundOnly)
                return pin.shown
            end
        '''))
        self.lua.execute('state.flight = true; assert(knownOnly(false)); state.flight=nil; assert(not knownOnly(false))')

    def test_remote_trivial_offers_follow_character_state_and_native_map_pins(self):
        self.lua.execute('''
            state = {on=true, pad=false, sets=0, scanned=0}
            RutaXPWorldMapTracking = {
                Get=function() return state.on end, Info=function() return {texture=123} end,
                GetAreaScope=function() return state.area end,
                IsMapInArea=function(id, scope) return scope == nil or id == scope end,
            }
            C_QuestLog = {IsOnQuest=function(id) return id==4 end,
                IsQuestFlaggedCompleted=function(id) return id==5 end,
                IsQuestTrivial=function(id) return id==8 end}
            map = { IsShown=function() return true end, GetMapID=function() return 10 end,
                EnumeratePinsByTemplate=function(self,template)
                    return coroutine.wrap(function()
                        local id=({QuestOfferPinTemplate=3,StorylineQuestPinTemplate=11})[template]
                        assert(id)
                        coroutine.yield({questID=id, IsShown=function() return true end,
                            GetPosition=function() return .2,.3 end})
                    end)
                end }
            stitch = {IsBuilt=function() return true end,
                Rect=function() return 0, 1, 0, 1 end,
                PinSet=function(key, zoom) assert(zoom==0); state.sets=state.sets+1; return {} end,
                ClearPinSet=function() state.pins={} end,
                SetPinSetOn=function(_,v) state.visible=v end,
                AddPin=function(_,u,v,icon,data)
                    assert(icon.texture==123)
                    state.pins[#state.pins+1]=data.id
                    return {SetScript=function() end}
                end}
            mod = {IsStitched=function() return true end, PadViewOn=function() return state.pad end,
                ToWorld=function(zone,x,y) return (zone==10 and 0 or .6)+x*.4, y*.3 end }
            function maps() return {10,30,31,32} end
            requests, timers={},{}
            C_Timer={After=function(_, fn) timers[#timers+1]=fn end}
            function finish() while #timers>0 do table.remove(timers,1)() end end
            C_QuestLine={
                GetAvailableQuestLines=function(zone)
                    state.scanned=state.scanned+1
                    if zone==10 then return {{questID=3,x=.2,y=.3,isHidden=true},
                        {questID=11,x=.2,y=.3,isHidden=true}} end
                    if zone==32 then
                        if state.received then return {{questID=10,x=.4,y=.3,isHidden=true}} end
                        return {}
                    end
                    return {
                        {questID=1,x=.1,y=.3,isHidden=true}, {questID=2,x=.1,y=.3},
                        {questID=4,x=.2,y=.3,isHidden=true}, {questID=5,x=.2,y=.3,isHidden=true},
                        {questID=6,x=.2,y=.3,isHidden=true,inProgress=true},
                        {questID=7,x=.2,y=.3,isHidden=true,floorLocation=0},
                        {questID=8,x=.5,y=.5}, {questID=9,x=-1,y=.2,isHidden=true},
                    }
                end,
                RequestQuestLinesForMap=function(id) requests[id]=(requests[id] or 0)+1 end,
            }
        ''')
        path = Path(__file__).resolve().parents[1] / "RutaXP" / "WorldMapQuestTracking.lua"
        self.lua.execute(path.read_text(encoding="utf-8-sig"))
        self.lua.execute('''
            local function refresh()
                RutaXPWorldMapTracking.RefreshQuestOffers({MapStitch=stitch},mod,map,maps,function() end)
            end
            refresh()
            assert(state.scanned==3 and not state.pins)
            finish()
            assert(state.visible and table.concat(state.pins,",")=="1,8")
            for _,id in ipairs(maps()) do assert(requests[id]==1) end
            state.received=true
            RutaXPWorldMapTracking.QuestOfferEvent("QUESTLINE_UPDATE",false)
            refresh(); finish()
            assert(table.concat(state.pins,",")=="1,8,10" and requests[32]==1)
            state.pad=true
            refresh(); finish()
            assert(state.visible and table.concat(state.pins,",")=="3,11,1,8,10")
            assert(requests[32]==1 and state.sets==1)
            state.pad=false
            state.area=30
            refresh(); finish()
            assert(state.visible and table.concat(state.pins,",")=="1,8")
            state.area=32
            refresh(); finish()
            assert(state.visible and table.concat(state.pins,",")=="10")
            state.area=nil
            refresh(); finish()
            assert(state.visible and table.concat(state.pins,",")=="1,8,10")
            QuestOfferDataProviderMixin={
                GetAllQuestOffersForMap=function(self,zone)
                    assert(self:GetMap():GetMapID()==zone)
                    return {
                        [90]={questID=90,isHidden=true,isQuestStart=true,x=.5,y=.5},
                        [91]={questID=91,isHidden=true,isQuestStart=false,x=.2,y=.5},
                        [92]={questID=92,isHidden=true,isQuestStart=true,x=.4,y=.5},
                    }
                end,
                ShouldAddQuestOffer=function(self,q,zone)
                    return q.questID~=92 and self:GetMap():GetMapID()==zone and zone==30
                end,
            }
            RutaXPWorldMapTracking.QuestOfferEvent("QUESTLINE_UPDATE",true)
            RutaXPWorldMapTracking.QuestOfferEvent("QUEST_ACCEPTED")
            refresh(); finish()
            assert(table.concat(state.pins,",")=="90")
            for _,id in ipairs(maps()) do assert(requests[id]==2) end
            RutaXPWorldMapTracking.QuestOfferEvent("PLAYER_LEVEL_UP")
            refresh(); finish()
            assert(requests[32]==3)
            refresh()
            state.on=false; refresh(); finish()
            assert(not state.visible)
        ''')
