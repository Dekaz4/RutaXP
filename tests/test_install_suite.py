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
        self.client = self.work / "_forever_"
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
        manifest.write_text("\n".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
            for path in sorted(self.package.iterdir()) if path != manifest
        ) + "\n", encoding="utf8")
        with ZipFile(self.archive, "w") as bundle:
            for path in self.package.iterdir():
                bundle.write(path, "RutaXP/" + path.name)

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
        store = self.client / "RutaXP-Suite-Backups"
        self.assertEqual(len(list(store.glob("*/committed"))), 1)
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

    def test_invalid_archive_or_manifest_leaves_addons_untouched(self):
        (self.package / "Suite.lua").write_bytes(b"-- tampered")
        self.script("-AddonDirectory", self.package, ok=False)
        with ZipFile(self.archive, "a") as bundle:
            bundle.writestr("RutaXP/../escape", b"invalid")
        self.script("-Archive", self.archive, ok=False)
        for module in (*MODULES, "RutaXP"):
            self.assertTrue((self.addons / module / "old").is_file())
        self.assertFalse((self.client / "escape").exists())

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
        self.assertTrue((legacy / "RutaXP.toc").is_file())
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
        self.assertTrue((transaction / "restored").exists())
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
