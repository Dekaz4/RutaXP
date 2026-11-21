from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime

from tools.suite_map_journal import transform_lua


class MapJournalIntegrationTests(unittest.TestCase):
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
