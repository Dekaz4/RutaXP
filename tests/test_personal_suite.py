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
        self.bundle = Path(tmp.name) / "suite.zip"
        entrypoints = ["Modules/OpenMap/Init.lua", "Modules/ForeverDungeonJournal/Core/Journal.lua",
                       "Core.lua", "Leveling.lua", "QuestEngine.lua", "GuideOriginal.lua"]
        self.files = dict.fromkeys(entrypoints, "-- bundled source fixture")
        self.files["Suite.lua"] = (ROOT / "RutaXP/Suite.lua").read_text(encoding="utf-8-sig")
        self.files["Leveling.lua"] = (ROOT / "RutaXP/Leveling.lua").read_text(encoding="utf8")
        meta = [
            "## Version: 1.2.16",
            "## SavedVariables: OpenMapDB, ForeverDungeonJournalDB, RutaXPDB",
            "## SavedVariablesPerCharacter: OpenMapCharDB, ForeverDungeonJournalCharacterDB, RutaXPCharDB",
            "## X-OpenMap-Version: 0.8", "## X-ForeverDungeonJournal-Version: 2.1", "## X-RutaXP-Guide-Version: 0.7.36",
        ]
        self.files["RutaXP.toc"] = "\n".join(meta + ["Suite.lua"] + entrypoints)
        self.files["Bindings.xml"] = '<Bindings><Binding name="OPENMAP_FIND"/><Binding name="FOREVERDUNGEONJOURNAL_TOGGLE"/></Bindings>'

    def check(self):
        with ZipFile(self.bundle, "w") as z:
            for name, text in self.files.items():
                z.writestr("RutaXP/" + name, text)
        return verify(self.bundle)

    def test_uses_packaged_launcher_and_native_registrations(self):
        result = self.check()
        self.assertEqual(result["compiled_lua"], 7)
        self.assertEqual(set(result["registrations"]), {"Alliance", "Horde"})
        self.assertEqual(sum(result["registrations"].values()), 57)

    def test_rejects_restedxp_code_and_changed_or_missing_original_guides(self):
        rxp = "Modules/RXPGuides/RXPGuides.lua"
        self.files[rxp] = "-- old runtime"
        with self.assertRaisesRegex(ValueError, "Unexpected RestedXP"):
            self.check()
        del self.files[rxp]
        path = "Leveling.lua"
        self.files[path] += "\n-- changed"
        with self.assertRaisesRegex(ValueError, "differs from RutaXP"):
            self.check()
        del self.files[path]
        with self.assertRaisesRegex(ValueError, "Missing file in load graph"):
            self.check()

    def test_rejects_changes_inside_reviewed_chapter(self):
        source = self.files["Leveling.lua"]
        self.assertIn("Habla primero con el sargento Yohwa", source)
        self.files["Leveling.lua"] = source.replace("Habla primero con el sargento Yohwa", "Espera a Thorsen", 1)
        with self.assertRaisesRegex(ValueError, "Alliance Stranglethorn differs"):
            self.check()

    def test_rejects_revised_guides_in_an_older_suite(self):
        self.files["RutaXP.toc"] = self.files["RutaXP.toc"].replace("## Version: 1.2.16", "## Version: 1.2.15")
        with self.assertRaisesRegex(ValueError, "Alliance Stranglethorn differs"):
            self.check()

    def test_rejects_changes_inside_reviewed_horde_chapter(self):
        title = "Basiliscos y aldea Sangrapellejo"
        self.assertIn(title, self.files["Leveling.lua"])
        self.files["Leveling.lua"] = self.files["Leveling.lua"].replace(title, "Otro destino", 1)
        with self.assertRaisesRegex(ValueError, "Horde Stranglethorn differs"):
            self.check()

    def test_rejects_broken_module_reference_before_shipping(self):
        self.files["Modules/OpenMap/Init.lua"] = r'local t="Interface\\AddOns\\OpenMap\\Media\\lost.tga"'
        with self.assertRaisesRegex(ValueError, "Unrelocated"):
            self.check()
