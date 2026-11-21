from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools.verify_personal_suite import verify


ROOT = Path(__file__).resolve().parents[1]


class PersonalSuiteVerificationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.official = Path(tmp.name) / "official.zip"
        self.bundle = Path(tmp.name) / "suite.zip"
        guides = {}
        lists = ["Guides/GuideList-forever.xml", "lang/Guides-esES/GuideList-forever.xml"]
        for name in lists:
            guides[name] = '<Ui><Script file="start.lua"/></Ui>'
            guides[name.replace("GuideList-forever.xml", "start.lua")] = 'RXPGuides.RegisterGuide([[#name Empieza aquí]])'
        with ZipFile(self.official, "w") as z:
            z.writestr("RXPGuides-reference/RXPGuides.toc", "\n".join(lists))
            for name, text in guides.items():
                z.writestr("RXPGuides-reference/" + name, text)
        self.files = {"Modules/RXPGuides/" + name: text for name, text in guides.items()}
        entrypoints = ["Modules/OpenMap/Init.lua","Modules/ForeverDungeonJournal/Core/Journal.lua",
                       "Modules/RXPGuides/RXPGuides.lua"]
        self.files.update(dict.fromkeys(entrypoints, "-- native source fixture"))
        self.files["Suite.lua"] = (ROOT / "RutaXP/Suite.lua").read_text(encoding="utf-8-sig")
        meta = [
            "## SavedVariables: OpenMapDB, ForeverDungeonJournalDB, RutaXPDB, RXPSettings, RutaXPRestedDB",
            "## SavedVariablesPerCharacter: OpenMapCharDB, ForeverDungeonJournalCharacterDB, RutaXPCharDB, RXPCSettings",
            "## X-OpenMap-Version: 0.8", "## X-ForeverDungeonJournal-Version: 2.1", "## X-RXPGuides-Version: 4.1",
        ]
        self.files["RutaXP.toc"] = "\n".join(meta + ["Suite.lua"] + entrypoints + ["Modules/RXPGuides/" + p for p in lists])
        self.files["Bindings.xml"] = '<Bindings><Binding name="OPENMAP_FIND"/><Binding name="FOREVERDUNGEONJOURNAL_TOGGLE"/></Bindings>'

    def check(self):
        with ZipFile(self.bundle, "w") as z:
            for name, text in self.files.items():
                z.writestr("RutaXP/" + name, text)
        return verify(self.bundle, self.official)

    def test_uses_packaged_launcher_and_native_registrations(self):
        result = self.check()
        self.assertEqual(result["compiled_lua"], 6)
        self.assertEqual(result["registrations"], dict.fromkeys(
            ["enUS/Alliance","enUS/Horde","esES/Alliance","esES/Horde"], 1))

    def test_does_not_accept_changed_guide_text_or_missing_script(self):
        path = "Modules/RXPGuides/lang/Guides-esES/start.lua"
        self.files[path] = 'RXPGuides.RegisterGuide([[#name Un cambio]])'
        with self.assertRaisesRegex(ValueError, "differs from official"):
            self.check()
        del self.files[path]
        with self.assertRaisesRegex(ValueError, "Missing file in load graph"):
            self.check()

    def test_rejects_broken_module_reference_before_shipping(self):
        self.files["Modules/OpenMap/Init.lua"] = r'local t="Interface\\AddOns\\OpenMap\\Media\\lost.tga"'
        with self.assertRaisesRegex(ValueError, "Unrelocated"):
            self.check()
