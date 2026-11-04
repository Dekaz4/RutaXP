"""Installer regression tests use only isolated temporary directories.

The C# source is compiled as a library, never launched as an installer. The
PowerShell installer is dot-sourced (its interactive entry point stays idle).
"""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows PowerShell is required")
class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="RutaXP installer tests ")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.base = Path(cls.temporary.name)
        framework = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319"
        compiler = framework / "csc.exe"
        if not compiler.exists():
            raise unittest.SkipTest("The .NET Framework C# compiler is unavailable")
        cls.assembly = cls.base / "Installer.Tests.dll"
        compiled = subprocess.run(
            [str(compiler), "/nologo", "/target:library", "/out:" + str(cls.assembly),
             "/r:" + str(framework / "System.IO.Compression.dll"),
             "/r:" + str(framework / "System.IO.Compression.FileSystem.dll"),
             str(ROOT / "tools/Installer.cs")],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)

    def check_case(self, name):
        result = subprocess.run(
            [shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(ROOT / "tests/test_installers.ps1"), "-Workspace", str(ROOT),
             "-FixtureRoot", str(self.base / name), "-Assembly", str(self.assembly), "-Case", name],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS " + name, result.stdout)

    def test_paths_single_trailing_slash_spaces_and_client_selection(self):
        self.check_case("paths")

    def test_update_preserves_backup_and_all_manifest_files(self):
        self.check_case("update")

    def test_copy_corruption_and_activation_failures_preserve_old_install(self):
        self.check_case("failures")

    def test_invalid_toc_manifest_and_source_equals_target_are_rejected(self):
        self.check_case("invalid")

    def test_embedded_zip_helpers_and_path_traversal(self):
        self.check_case("archive")

    def test_junctions_are_rejected_without_touching_their_targets(self):
        self.check_case("junctions")

    def test_name_notices_are_bundled_and_match_pinned_source(self):
        for source, bundled in (
            ("LICENSE-DATA.txt", "SendaFH-Names-esES-LICENSE-DATA.txt"),
            ("CREDITS.md", "DingDB-CREDITS.md"),
        ):
            notice = ROOT / "RutaXP/Licenses" / bundled
            self.assertTrue(notice.is_file())
            upstream = ROOT / ".sources/SendaFH/addon/SendaFH_Names_esES" / source
            if upstream.is_file():
                self.assertEqual(notice.read_bytes(), upstream.read_bytes())


if __name__ == "__main__":
    unittest.main()
