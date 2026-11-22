"""Exercise option 1 against local release assets, without starting WoW or contacting GitHub."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BASE, NEXT = "1.2.11", "1.2.12"
HARNESS = r'''
using System;
using System.IO;
using RutaXPUpdater;
public class LauncherTest {
    public static int Main(string[] args) {
        try {
            if (args[0] == "--update") return Program.Main(args);
            if (args.Length == 2 && args[1] == "hold") {
                using (var lease = Program.TryBeginInstallation(args[0])) {
                    if (lease == null) return 1;
                    Console.WriteLine("LOCKED"); Console.Out.Flush(); Console.ReadLine(); lease.ReleaseMutex(); return 0;
                }
            }
            if (args.Length == 5)
                return DeltaBridge.Run(new [] { args[0], args[1], args[2], args[3] }, () => args[4] == "playing");
            UpdateResult r = UpdaterCore.Update(args[0], args[2] == "repair", null,
                (url, limit) => {
                    string name = Path.GetFileName(new Uri(url).AbsolutePath);
                    Console.WriteLine("GET " + name);
                    string file = Path.Combine(args[1], name);
                    if (args[2] == "race" && name.EndsWith("-delta.zip") &&
                        DeltaBridge.Run(new [] {args[0], file, "1.2.11", "1.2.12"}, () => false) != 0)
                        throw new Exception("Fixture could not complete the other installation");
                    return File.ReadAllBytes(file);
                }, () => false, null, launch => { throw new IOException("SUITE " + launch.Arguments); });
            Console.WriteLine("OK " + r.Version + " changed=" + r.Changed);
            return 0;
        } catch (Exception ex) { Console.WriteLine(ex.Message); return 1; }
    }
}
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def put(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def zip_bytes(entries):
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return data.getvalue()


def seal(files, version):
    return (f"# RutaXP {version}\n" + "".join(f"{sha(data)}  {name}\n" for name, data in sorted(files.items()))).encode()


@unittest.skipUnless(os.name == "nt", ".NET Framework launcher is Windows only")
class IncrementalUpdaterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="RutaXP incremental launcher ")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        fw = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319"
        cs = cls.root / "LauncherTest.cs"
        cs.write_text(HARNESS, encoding="utf8")
        cls.launcher = cls.root / "LauncherTest.exe"
        refs = ["/r:" + str(fw / name) for name in ("System.IO.Compression.dll", "System.IO.Compression.FileSystem.dll",
                                                       "System.Web.Extensions.dll", "System.Windows.Forms.dll")]
        sources = [str(ROOT / "tools" / f) for f in ("Updater.cs", "DeltaApply.cs", "Installer.cs")]
        subprocess.run([str(fw / "csc.exe"), "/nologo", "/main:LauncherTest", "/out:" + str(cls.launcher),
                        *refs, *sources, str(cs)], check=True)
        cls.bridge = cls.root / "DeltaBridge.exe"
        subprocess.run([str(fw / "csc.exe"), "/nologo", "/main:RutaXPUpdater.DeltaBridge",
                        "/out:" + str(cls.bridge), *refs, *sources], check=True)

    def setUp(self):
        root = self.root / self._testMethodName
        self.remote = root / "release"
        self.remote.mkdir(parents=True)
        self.addons = root / "_forever_/Interface/AddOns"
        self.addon = self.addons / "RutaXP"
        self.old_toc = f"## Interface: 16001\n## Version: {BASE}\nCore.lua\nLeveling.lua\n".encode()
        self.new_toc = self.old_toc.replace(BASE.encode(), NEXT.encode())
        modules = ["Modules/Journey/ui/UI.lua", "Modules/Journey/ui/TaskDetailContainers.lua",
                   "Modules/Journey/lib/TomCats/Arrows.lua", "Modules/OpenMap/Core.lua",
                   "Modules/ForeverDungeonJournal/Core/Journal.lua"]
        self.toc = b"## X-RutaXP-Embedded: OpenMap, ForeverDungeonJournal\n## X-RutaXP-Journey-UI: 4\n" + self.old_toc
        self.toc += ("\n" + "\n".join(modules) + "\n").encode()
        self.files = {"RutaXP.toc": self.toc, "Core.lua": b"old", "Leveling.lua": b"-- guide",
                      **{m: b"-- module" for m in modules}}
        for name, data in self.files.items():
            put(self.addon, name, data)
        put(self.addon, "manifest.sha256", seal(self.files, BASE))
        for name in ("LFGForever/LFGForever.toc", "LFGForeverLanguageSpanish/LFGForeverLanguageSpanish.toc",
                     "LFGForeverLanguageSpanish/Spanish.lua"):
            put(self.addons, name, b"-- lfg")
        self.delta_name = f"RutaXP-{BASE}-a-{NEXT}-delta.zip"
        self.descriptor = (f"RutaXP-delta-v1\t{BASE}\t{NEXT}\n{sha(self.old_toc)}\t{sha(self.new_toc)}\tRutaXP.toc\n"
                           f"{sha(b'old')}\t{sha(b'new')}\tCore.lua\n")
        self.delta_entries = {"delta.tsv": self.descriptor, "old/RutaXP.toc": self.old_toc,
                              "files/RutaXP.toc": self.new_toc, "files/Core.lua": b"new"}
        self.full_name = f"RutaXP-{NEXT}-addon.zip"
        full = {"RutaXP.toc": self.new_toc, "Core.lua": b"new", "Leveling.lua": b"--guide",
                "Instalar_Suite_RutaXP.exe": b"fixture"}
        full["manifest.sha256"] = seal(full, NEXT)
        self.full = zip_bytes({"RutaXP/" + n: v for n, v in full.items()})
        self.publish()

    def publish(self, extra=None):
        files = {self.full_name: self.full, self.delta_name: zip_bytes({**self.delta_entries, **(extra or {})})}
        files["SHA256SUMS.txt"] = "".join(f"{sha(value)}  {name}\n" for name, value in files.items()).encode()
        address = f"https://github.com/Dekaz4/RutaXP/releases/download/v{NEXT}/"
        assets = [{"name": n, "size": len(v), "browser_download_url": address + n} for n, v in files.items()]
        for name, value in files.items():
            put(self.remote, name, value)
        meta = {"tag_name": "v" + NEXT, "draft": False, "prerelease": False, "assets": assets}
        put(self.remote, "latest", json.dumps(meta).encode())

    def update(self, repair=False, ok=True, mode="update"):
        run = subprocess.run([str(self.launcher), str(self.addons), str(self.remote), "repair" if repair else mode],
                             capture_output=True, timeout=20)
        out = run.stdout.decode(errors="replace")
        self.assertEqual(run.returncode, 0 if ok else 1, out)
        return out

    def test_only_delta_then_only_metadata(self):
        out = self.update()
        self.assertIn("GET " + self.delta_name, out)
        self.assertNotIn("GET " + self.full_name, out)
        self.assertEqual((self.addon / "Core.lua").read_bytes(), b"new")
        self.assertEqual((self.addon / "RutaXP.toc").read_bytes(), self.toc.replace(BASE.encode(), NEXT.encode()))
        self.assertEqual(self.update().splitlines(), ["GET latest", f"OK {NEXT} changed=False"])

    def test_same_version_missing_lfg_runs_full(self):
        self.update()
        (self.addons / "LFGForeverLanguageSpanish/Spanish.lua").unlink()
        out = self.update(ok=False)
        self.assertIn("GET " + self.full_name, out)
        self.assertIn("SUITE --addons", out)

    def test_local_edit_falls_back_and_repair_skips_delta(self):
        put(self.addon, "Core.lua", b"edited")
        out = self.update(ok=False)
        self.assertIn("GET " + self.delta_name, out)
        self.assertIn("GET " + self.full_name, out)
        self.assertIn(" --full", out)
        self.assertEqual((self.addon / "Core.lua").read_bytes(), b"edited")
        out = self.update(repair=True, ok=False)
        self.assertNotIn("GET " + self.delta_name, out)
        self.assertIn(" --full", out)

    def test_invalid_signed_delta_fails_before_writing(self):
        self.publish({"files/Core.lua": b"wrong content"})
        out = self.update(ok=False)
        self.assertNotIn("GET " + self.full_name, out)
        self.assertEqual((self.addon / "Core.lua").read_bytes(), b"old")

    def test_legacy_bridge_and_running_game(self):
        args = [str(self.launcher), str(self.addons), str(self.remote / self.delta_name), BASE, NEXT]
        def bridge(state):
            return subprocess.run([*args, state], capture_output=True, timeout=20).returncode
        self.assertEqual(bridge("playing"), 1)
        put(self.addon, "Core.lua", b"edited locally")
        self.assertEqual(bridge("closed"), 3)
        self.assertEqual((self.addon / "Core.lua").read_bytes(), b"edited locally")
        put(self.addon, "Core.lua", b"old")
        self.assertEqual(bridge("closed"), 0)
        self.assertEqual((self.addon / "Core.lua").read_bytes(), b"new")
        self.assertEqual(bridge("closed"), 3)

    def test_concurrent_commit_avoids_full_download(self):
        out = self.update(mode="race")
        self.assertIn("GET " + self.delta_name, out)
        self.assertNotIn("GET " + self.full_name, out)
        self.assertIn("changed=False", out)
        self.assertEqual((self.addon / "Core.lua").read_bytes(), b"new")

    def test_second_launcher_exits_before_querying_github(self):
        with subprocess.Popen([str(self.launcher), str(self.addons), "hold"], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE) as holder:
            try:
                self.assertEqual(holder.stdout.readline().strip(), b"LOCKED")
                second = subprocess.run([str(self.launcher), "--update", "--client", str(self.addons.parent / "AddOns")],
                                        capture_output=True, timeout=5)
                self.assertEqual(second.returncode, 0, second.stderr)
                self.assertIn(b"primera ventana", second.stdout)
                self.assertNotIn(b"GitHub", second.stdout)
            finally:
                holder.communicate(b"\n", timeout=5)
