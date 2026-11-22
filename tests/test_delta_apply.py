"""Exercise the native updater on an isolated Forever client, without starting WoW."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
def SHA(data):
    return hashlib.sha256(data).hexdigest()
HARNESS = r"""
using System;
using System.IO;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using RutaXPUpdater;
class Exercise {
    static int Main(string[] args) {
        FileStream busy = null;
        try {
            if (args[1] == "recover") { IncrementalInstall.Recover(args[0]); return 0; }
            var changes = new JavaScriptSerializer().Deserialize<List<IncrementalChange>>(File.ReadAllText(args[2]));
            Action guard = delegate {
                if (args[1] == "opened") throw new IOException("WoW opened.");
                if (args[1] == "lock") busy = File.Open(Path.Combine(args[0], "Interface/AddOns/RutaXP/Retired.lua"), FileMode.Open, FileAccess.Read, FileShare.None);
            };
            Console.WriteLine(IncrementalInstall.Apply(args[0], changes, guard));
            return 0;
        } catch (Exception e) { Console.Error.WriteLine(e); return 1; }
        finally { if (busy != null) busy.Dispose(); }
    }
}
"""


@unittest.skipUnless(os.name == "nt", "Windows client required")
class DeltaApplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.exe = Path(cls.tmp.name) / "Exercise.exe"
        source = cls.exe.with_suffix(".cs")
        source.write_text(HARNESS)
        fw = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319"
        subprocess.run([str(fw / "csc.exe"), "/nologo", "/main:Exercise", "/out:" + str(cls.exe),
                        *["/r:" + str(fw / (name + ".dll")) for name in
                          ("System.IO.Compression", "System.IO.Compression.FileSystem", "System.Web.Extensions")],
                        str(source), str(ROOT / "tools/Installer.cs"), str(ROOT / "tools/DeltaApply.cs")], check=True)

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.client = self.work / "Warcraft/_forever_"
        self.store = self.work / "RutaXP-Suite-Backups/Warcraft/_forever_"
        self.addon = self.client / "Interface/AddOns/RutaXP"
        self.external = "Modules/OpenMap/intact.lua"
        self.before = b"## Interface: 16001\n## Version: 1.2.11\n## SavedVariables: RutaXPDB\n\nCore.lua\nRetired.lua\n"
        self.after = self.before.replace(b"1.2.11", b"1.2.12").replace(b"Retired.lua", b"New/Added.lua")

        def compose(native):
            return (b"## X-RutaXP-Embedded: OpenMap, ForeverDungeonJournal\n## OptionalDeps: Other\n" +
                    native.replace(b"RutaXPDB", b"RutaXPDB, OpenMapDB") + b"\nModules/OpenMap/intact.lua\n")

        self.initial = {"Core.lua": b"older", "Retired.lua": b"old", self.external: b"external",
                        "RutaXP.toc": compose(self.before), "Static.lua": b"keep"}
        self.next_toc = compose(self.after)
        initial_manifest = "# RutaXP 1.2.11\n" + "".join(
            f"{SHA(data)}  {name}\n" for name, data in sorted(self.initial.items()))
        for name, data in dict(self.initial, **{"manifest.sha256": initial_manifest.encode()}).items():
            path = self.addon / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.changes = [self.row("Core.lua", b"older", b"newer"), self.row("New/Added.lua", None, b"added"),
                        self.row("Retired.lua", b"old", None), self.row("RutaXP.toc", self.before, self.after)]
        self.changes[-1]["OldData"] = list(self.before)

    @staticmethod
    def row(path, old, new):
        return {"Path": path, "OldHash": SHA(old) if old is not None else None,
                "NewHash": SHA(new) if new is not None else None, "Data": list(new) if new is not None else None}

    def invoke(self, action, ok=True):
        patch = self.work / "changes.json"
        patch.write_text(json.dumps(self.changes))
        result = subprocess.run([str(self.exe), str(self.client), action, str(patch)], capture_output=True,
                                text=True, errors="replace", timeout=30)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_updates_only_changed_files_and_recovers_interrupted_commit(self):
        stable = [(self.addon / name) for name in ("Static.lua", self.external)]
        old_times = [path.stat().st_mtime_ns for path in stable]
        self.invoke("apply")
        self.assertEqual((self.addon / "RutaXP.toc").read_bytes(), self.next_toc)
        self.assertEqual((self.addon / "New/Added.lua").read_bytes(), b"added")
        self.assertFalse((self.addon / "Retired.lua").exists())
        self.assertEqual(old_times, [path.stat().st_mtime_ns for path in stable])
        manifest = (self.addon / "manifest.sha256").read_text()
        self.assertIn(SHA(self.next_toc) + "  RutaXP.toc", manifest)
        self.assertIn(SHA(self.initial[self.external]) + "  " + self.external, manifest)
        self.assertNotIn("Retired.lua", manifest)
        tx = next(self.store.glob("*/committed")).parent
        (tx / "committed").unlink()
        self.invoke("recover")
        for name, data in self.initial.items():
            self.assertEqual((self.addon / name).read_bytes(), data)
        self.assertFalse((self.addon / "New/Added.lua").exists())
        self.assertTrue((tx / "restored").exists())
        self.invoke("apply")

    def test_sharing_violation_rolls_back_and_can_retry(self):
        self.invoke("lock", ok=False)
        self.assertEqual((self.addon / "Core.lua").read_bytes(), b"older")
        self.assertFalse((self.addon / "New/Added.lua").exists())
        self.assertTrue(list(self.store.glob("*/restored")))
        self.invoke("apply")

    def test_reopening_game_before_commit_discards_staging(self):
        self.assertIn("WoW opened", self.invoke("opened", ok=False).stderr)
        self.assertEqual((self.addon / "Core.lua").read_bytes(), b"older")
        self.assertFalse(any(path.is_dir() for path in self.store.iterdir()))

    def test_pending_full_install_is_referred_to_the_suite_helper(self):
        tx = self.store / ("20261122000000000-" + "a" * 32)
        tx.mkdir(parents=True)
        (tx / "plan.json").write_text(json.dumps({"rows": [{"dest": "Interface/AddOns/RutaXP",
                                                           "old": True, "add": True, "sources": []}]}))
        self.assertIn("IncrementalBaseMismatchException", self.invoke("recover", ok=False).stderr)
        self.assertFalse((tx / "restored").exists())
        self.assertEqual((self.addon / "Core.lua").read_bytes(), b"older")

    def test_full_installer_restore_accepts_native_transaction(self):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            self.skipTest("PowerShell required")
        self.invoke("apply")
        result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                 "-File", str(ROOT / "tools/Install-Suite.ps1"),
                                 "-Client", str(self.client), "-Restore"],
                                capture_output=True, text=True, errors="replace", timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name, data in self.initial.items():
            self.assertEqual((self.addon / name).read_bytes(), data)
        self.assertFalse((self.addon / "New/Added.lua").exists())

    def test_changed_base_and_unmanaged_paths_do_not_apply(self):
        (self.addon / "Retired.lua").write_bytes(b"personal edits")
        self.assertIn("IncrementalBaseMismatchException", self.invoke("apply", ok=False).stderr)
        self.assertEqual((self.addon / "Core.lua").read_bytes(), b"older")
        self.changes[0]["Path"] = "../outsider"
        self.assertIn("InvalidDataException", self.invoke("apply", ok=False).stderr)
        self.changes[0]["Path"] = self.external
        self.assertIn("InvalidDataException", self.invoke("apply", ok=False).stderr)
        self.assertFalse(list(self.store.glob("*/committed")))


if __name__ == "__main__":
    unittest.main()
