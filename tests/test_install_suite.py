"""Exercise the offline installer with disposable client, addon, and WTF trees."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from zipfile import ZipFile


SCRIPT = Path(__file__).resolve().parents[1] / "tools/Install-Suite.ps1"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
MODULES = ("OpenMap", "ForeverDungeonJournal", "RXPGuides")


@unittest.skipUnless(POWERSHELL, "PowerShell required")
class LocalSuiteInstallTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.client = self.work / "World of Warcraft/_forever_"
        self.store = self.work / "RutaXP-Suite-Backups/World of Warcraft/_forever_"
        self.addons = self.client / "Interface/AddOns"
        for module in (*MODULES, "RutaXP"):
            old = self.addons / module
            old.mkdir(parents=True)
            (old / "old").write_text(module, encoding="utf8")
        self.package = self.work / "package/RutaXP"
        self.package.mkdir(parents=True)
        (self.package / "Suite.lua").write_bytes(b"local _, ns = ...\n")
        (self.package / "RutaXP.toc").write_bytes(
            b"## X-RutaXP-Embedded: OpenMap, ForeverDungeonJournal, RXPGuides\nSuite.lua\n"
        )
        self.archive = self.work / "RutaXP-personal.zip"
        self.pack()

    def pack(self):
        manifest = self.package / "manifest.sha256"
        files = sorted(p for p in self.package.rglob("*") if p.is_file() and p != manifest)
        manifest.write_text("\n".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(self.package).as_posix()}"
            for path in files
        ) + "\n", encoding="utf8")
        with ZipFile(self.archive, "w") as bundle:
            for path in [*files, manifest]:
                bundle.write(path, "RutaXP/" + path.relative_to(self.package).as_posix())

    def script(self, *arguments, ok=True):
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(SCRIPT), "-Client", str(self.client), *map(str, arguments)],
            capture_output=True, text=True, errors="replace", timeout=45,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result.stdout

    def test_settings_across_accounts_and_characters_and_restore(self):
        account = self.client / "WTF/Account/account/SavedVariables"
        character = self.client / "WTF/Account/account/Realm/Player/SavedVariables"
        other = self.client / "WTF/Account/other/SavedVariables"
        for directory in (account, character, other):
            directory.mkdir(parents=True)
            (directory / "RXPGuides.lua").write_bytes(b'RXPData = {"PRIVATE_GUIDE_MARKER"}')
        source = b"\xef\xbb\xbfOpenMapDB = {} -- trailing comment"
        original = b"RutaXPDB = { Choice = 42 }"
        (account / "OpenMap.lua").write_bytes(source)
        (account / "RutaXP.lua").write_bytes(original)
        (other / "ForeverDungeonJournal.lua").write_bytes(b"FDJ = {}")
        (character / "OpenMap.lua").write_bytes(b'characterMap = "player"')
        self.script("-Archive", self.archive)
        self.assertFalse(any((self.addons / module).exists() for module in MODULES))
        self.assertEqual((account / "RutaXP.lua").read_bytes(), source[3:] + b"\n" + original + b"\n")
        self.assertIn(b"FDJ", (other / "RutaXP.lua").read_bytes())
        self.assertIn(b'characterMap', (character / "RutaXP.lua").read_bytes())
        for directory in (account, character, other):
            self.assertNotIn(b"PRIVATE_GUIDE_MARKER", (directory / "RutaXP.lua").read_bytes())
            self.assertIn(b"PRIVATE_GUIDE_MARKER", (directory / "RXPGuides.lua").read_bytes())
        newer = b'OpenMapDB={zoom=7}\nRutaXPDB={Choice=99}'
        (account / "RutaXP.lua").write_bytes(newer)
        self.script("-AddonDirectory", self.package)
        self.assertEqual((account / "RutaXP.lua").read_bytes(), newer)
        store = self.store
        self.assertEqual(len(list(store.glob("*/committed"))), 1)
        self.assertFalse((self.client / "RutaXP-Suite-Backups").exists())
        (self.package / "Suite.lua").write_bytes(b"-- next version")
        self.pack()
        self.script("-Archive", self.archive)
        self.assertEqual((account / "RutaXP.lua").read_bytes(), newer)
        self.script("-Restore")
        self.assertEqual((account / "RutaXP.lua").read_bytes(), original)
        self.assertEqual((account / "OpenMap.lua").read_bytes(), source)
        self.assertFalse((character / "RutaXP.lua").exists())
        self.assertFalse((other / "RutaXP.lua").exists())
        self.assertTrue(any(path.read_bytes() == newer for path in store.glob("*/after/*") if path.is_file()))
        for module in (*MODULES, "RutaXP"):
            self.assertEqual((self.addons / module / "old").read_text(), module)
        self.script("-Restore")

    def test_upgrade_from_rested_suite_replaces_its_runtime_and_retains_original_progress(self):
        self.script("-Archive", self.archive)
        old_runtime = self.addons / "RutaXP/Modules/RXPGuides/GuideWindow.lua"
        old_runtime.parent.mkdir(parents=True)
        old_runtime.write_text("-- prior RestedXP")
        saved = self.client / "WTF/Account/account/Realm/Paladin/SavedVariables/RutaXP.lua"
        saved.parent.mkdir(parents=True)
        progress = b'RutaXPCharDB = { activeGuide = "forever/alliance/03", progress = { cursor = 37 } }\n'
        saved.write_bytes(progress)
        (self.package / "Leveling.lua").write_text("-- original RutaXP guide data")
        (self.package / "RutaXP.toc").write_text(
            "## X-RutaXP-Embedded: OpenMap, ForeverDungeonJournal\nLeveling.lua\nSuite.lua\n")
        marker = self.package / "Modules/RXPGuides/Migracion.txt"
        marker.parent.mkdir(parents=True)
        marker.write_text("RutaXP")
        self.pack()
        self.script("-Archive", self.archive)
        self.assertFalse(old_runtime.exists())
        self.assertTrue((self.addons / "RutaXP/Leveling.lua").is_file())
        self.assertTrue((self.addons / "RutaXP/Modules/RXPGuides").is_dir())
        self.assertEqual(saved.read_bytes(), progress)
        self.script("-Archive", self.archive)
        store = self.store
        self.assertEqual(len(list(store.glob("*/committed"))), 2)
        self.assertTrue(any(store.glob("*/prior/0/Modules/RXPGuides/GuideWindow.lua")))

    def test_invalid_archive_or_manifest_leaves_addons_untouched(self):
        (self.package / "Suite.lua").write_bytes(b"-- tampered")
        self.script("-AddonDirectory", self.package, ok=False)
        with ZipFile(self.archive, "a") as bundle:
            bundle.writestr("RutaXP/../escape", b"invalid")
        self.script("-Archive", self.archive, ok=False)
        for module in (*MODULES, "RutaXP"):
            self.assertTrue((self.addons / module / "old").is_file())
        self.assertFalse((self.client / "escape").exists())

    def test_journey_is_retired_only_for_a_verified_journey_presentation(self):
        native = self.addons / "Journey"
        native.mkdir()
        (native / "Journey.toc").write_text("## Version: 4.00.13")
        self.script("-Archive", self.archive)
        self.assertTrue(native.is_dir())
        toc = self.package/"RutaXP.toc"
        toc.write_text("## X-RutaXP-Journey-UI: 4.00.13\n" + toc.read_text())
        self.pack()
        self.script("-Archive", self.archive, ok=False)
        self.assertTrue(native.is_dir())
        for filename in ("ui/GuideContainer.lua","lib/TomCats/Arrows.lua"):
            path=self.package/"Modules/Journey"/filename
            path.parent.mkdir(parents=True,exist_ok=True)
            path.touch()
        self.pack()
        self.script("-Archive", self.archive)
        self.assertFalse(native.exists())
        self.assertTrue((self.addons/"RutaXP/Modules/Journey/lib/TomCats/Arrows.lua").is_file())
        self.script("-Restore")
        self.assertTrue((native/"Journey.toc").is_file())

    def test_clean_reinstall_replaces_old_files_and_archives_only_rutaxp_backups(self):
        self.script("-Archive", self.archive)
        stale = self.addons / "RutaXP/obsolete.lua"
        stale.write_text("-- Old version")
        legacy = self.addons / (".RutaXP.backup." + "a" * 32)
        legacy.mkdir()
        (legacy / "RutaXP.toc").write_text("## Title: RutaXP")
        unrelated = [self.addons / "AnotherAddon", self.addons / ".RutaXP.backup.mine",
                     self.addons / (".RutaXP.backup." + "b" * 32)]
        for folder in unrelated:
            folder.mkdir()
            (folder / "keep.lua").write_text("keep")
        duplicate = self.addons / "OpenMap"
        duplicate.mkdir()
        (duplicate / "OpenMap.toc").touch()
        self.script("-Archive", self.archive)
        self.assertFalse(stale.exists())
        self.assertFalse(duplicate.exists())
        self.assertFalse(legacy.exists())
        self.assertTrue((self.addons / "RutaXP/Suite.lua").is_file())
        self.assertTrue(all((d / "keep.lua").read_text() == "keep" for d in unrelated))
        self.script("-Restore")
        self.assertTrue((self.store / legacy.name / "RutaXP.toc").is_file())
        self.assertFalse(legacy.exists())
        self.assertTrue((self.addons / "RutaXP/old").is_file())

    def test_recovers_interrupted_activation_before_restoring(self):
        store = self.client / "RutaXP-Suite-Backups"
        transaction = store / ("20260102030405000-" + "a" * 32)
        prior = transaction / "prior"
        prior.mkdir(parents=True)
        (transaction / "new").mkdir()
        (self.addons / "OpenMap").rename(prior / "0")
        (transaction / "plan.json").write_text(json.dumps({"rows": [
            {"dest": "Interface/AddOns/OpenMap", "old": True, "add": False, "sources": []},
            {"dest": "Interface/AddOns/RutaXP", "old": True, "add": True, "sources": []},
        ]}))
        self.script("-Restore")
        self.assertTrue((self.store / transaction.name / "restored").exists())
        self.assertFalse(transaction.exists())
        self.assertTrue((self.addons / "OpenMap/old").exists())
        self.assertTrue((self.addons / "RutaXP/old").exists())

    def test_running_client_prevents_activation_and_backups(self):
        def ps_arg(value):
            return "'" + str(value).replace("'", "''") + "'"

        command = (
            f"function Get-Process {{ [PSCustomObject]@{{Path={ps_arg(self.client / 'WowClassic.exe')}}} }}; "
            f"& {ps_arg(SCRIPT)} -Client {ps_arg(self.client)} -Archive {ps_arg(self.archive)}"
        )
        result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                 "-Command", command], capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"Cierra WoW", result.stderr)
        self.assertFalse((self.client / "RutaXP-Suite-Backups").exists())
        self.assertFalse(self.store.exists())

    def test_mixed_legacy_and_external_history_remains_restorable(self):
        self.script("-Archive", self.archive)
        txn = next(p.parent for p in self.store.glob("*/committed"))
        old_store = self.client / "RutaXP-Suite-Backups"
        old_store.mkdir()
        original = old_store / txn.name
        txn.rename(original)
        interrupted_stage = old_store / ("20260102030405001-" + "b" * 32) / "new/0"
        interrupted_stage.mkdir(parents=True)
        (interrupted_stage / "partial.lua").write_text("partial")
        (old_store / "unrelated").mkdir()
        (self.package / "Suite.lua").write_bytes(b"-- update")
        self.pack()
        self.script("-Archive", self.archive)
        self.assertTrue((old_store / "unrelated").is_dir())
        self.assertFalse(original.exists())
        self.assertEqual(len(list(self.store.glob("*/committed"))), 2)
        self.assertFalse(interrupted_stage.exists())
        self.assertEqual(len(list((self.store / "Incomplete-transactions").glob("*/new/0/partial.lua"))), 1)
        self.script("-Restore")
        self.assertEqual((self.addons / "RutaXP/old").read_text(), "RutaXP")
        self.assertEqual(len(list(self.store.glob("*/restored"))), 2)

    def test_duplicate_external_copy_is_preserved_without_rolling_back_twice(self):
        self.script("-Archive", self.archive)
        txn = next(p.parent for p in self.store.glob("*/committed"))
        legacy = self.client / "RutaXP-Suite-Backups" / txn.name
        shutil.copytree(txn, legacy)
        self.script("-Restore")
        self.assertTrue((self.addons / "RutaXP/old").is_file())
        self.assertFalse(legacy.exists())
        self.assertEqual(len(list((self.store / "Archived-duplicates").glob("*/prior/0/old"))), 1)
