import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from lupa.lua51 import LuaRuntime

from tools.suite_rested import COMMIT, VERSION, prepare_official_source, transform_lua


class EmbeddedRestedXPTests(unittest.TestCase):
    def test_native_identity_and_both_texture_path_formats(self):
        source = r"""
            local addonName, addon = ...
            return addonName, "Interface/AddOns/" .. addonName ..
                "/Textures/logo", "Interface\\AddOns\\" .. addonName .. "\\Textures\\arrow"
        """
        compiled = LuaRuntime(unpack_returned_tuples=True).eval("loadstring")(
            transform_lua("RXPGuides", "QuestLog.lua", source)
        )
        name, first, second = compiled("RXPGuides", None)
        self.assertEqual(name, "RXPGuides")
        self.assertEqual(first, "Interface/AddOns/RutaXP/Modules/RXPGuides/Textures/logo")
        self.assertEqual(second, r"Interface\AddOns\RutaXP\Modules\RXPGuides\Textures\arrow")

    def test_metadata_and_load_event_use_the_host_toc(self):
        source = """local addonName = ...
            local function GetAddOnMetadata(name, tag) return name .. "/" .. tag end
            return GetAddOnMetadata(addonName, "Title"), GetAddOnMetadata(addonName, "Version")"""
        lua = LuaRuntime(unpack_returned_tuples=True)
        chunk = lua.eval("loadstring")(transform_lua("RXPGuides", "RXPGuides.lua", source))
        self.assertEqual(chunk("RXPGuides"), ("RutaXP/X-RXPGuides-Title", "RutaXP/X-RXPGuides-Version"))
        source = 'local addonName, arg1 = ...; if arg1 == addonName then return true end'
        chunk = lua.eval("loadstring")(transform_lua("RXPGuides", "QuestLog.lua", source))
        self.assertTrue(chunk("RXPGuides", "RutaXP"))
        self.assertIsNone(chunk("RXPGuides", "RXPGuides"))

    def test_guide_content_and_other_modules_pass_through(self):
        source = 'return "Interface/AddOns/" .. addonName .. "/example"'
        for path in ("Guides/forever/guide.lua", "lang/Guides-esES/index.lua", "DB/forever/quest.lua",
                     "locale/esES.lua", "libs/compatibility.lua"):
            with self.subTest(path=path):
                self.assertEqual(transform_lua("RXPGuides", path, source), source)
        self.assertEqual(transform_lua("OpenMap", "SettingsPanel.lua", source), source)

    def test_native_guide_import_storage_is_separate_and_talents_opt_in(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        source = """local function getDB(n) return n end
            RXPString = "suite"
            return {db=getDB("RXPDB"), payload=RXPString, enableTalentGuides = true,}"""
        lua.globals().RXPString = "original"
        settings = lua.execute(transform_lua("RXPGuides", "SettingsPanel.lua", source))
        self.assertEqual(settings.db, "RutaXPRestedDB")
        self.assertEqual(settings.payload, "suite")
        self.assertEqual(lua.globals().RXPString, "original")
        self.assertFalse(settings.enableTalentGuides)

    def test_only_verified_archive_supplies_code_and_guides(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = root / "installed"
            local.mkdir()
            (local / "RXPGuides.toc").write_text(f"## Version: {VERSION}")
            (local / "unofficial-guide.lua").write_text("local injected = true")
            archive = root / "stock.zip"
            with ZipFile(archive, "w") as package:
                for file, text in {"Guides/stock.lua": "-- stock", "Guides/Import.lua": "--\n",
                                   "RXPGuides.toc": "## Version: @project-version@",
                                   "Scripts/unrelated.py": "dev file"}.items():
                    package.writestr(f"RXPGuides-{COMMIT}/{file}", text)
            with patch("tools.suite_rested._official_archive", return_value=archive):
                staged = prepare_official_source(local, root, root / "staging")
                self.assertEqual((staged / "Guides/Import.lua").read_text(), "--\n")
                self.assertEqual((staged / "RXPGuides.toc").read_text(), f"## Version: {VERSION}")
                self.assertFalse((staged / "unofficial-guide.lua").exists())
                self.assertFalse((staged / "Scripts").exists())
                with self.assertRaises(ValueError):
                    prepare_official_source(local, root, staged)
