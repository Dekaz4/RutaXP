"""Updater helpers run against temporary fixtures, without network or EXE execution."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows PowerShell is required")
class UpdaterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="RutaXP updater tests ")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.base = Path(cls.temporary.name)
        framework = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319"
        compiler = framework / "csc.exe"
        if not compiler.is_file():
            raise unittest.SkipTest("The .NET Framework C# compiler is unavailable")
        cls.assembly = cls.base / "Updater.Tests.dll"
        sources = [str(ROOT / "tools/Installer.cs"), str(ROOT / "tools/Updater.cs")]
        refs = ["/r:" + str(framework / name) for name in (
            "System.IO.Compression.dll", "System.IO.Compression.FileSystem.dll",
            "System.Web.Extensions.dll", "System.Windows.Forms.dll")]
        for flags in (["/target:library", "/out:" + str(cls.assembly)],
                      ["/target:exe", "/main:RutaXPUpdater.Program", "/out:" + str(cls.base / "Compiled.NeverRun.exe")]):
            result = subprocess.run([str(compiler), "/nologo", *flags, *refs, *sources],
                                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)

    def check_case(self, case):
        result = subprocess.run([
            shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(ROOT / "tests/test_updater.ps1"), "-FixtureRoot", str(self.base / case),
            "-Assembly", str(self.assembly), "-Case", case],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS " + case, result.stdout)

    def test_numeric_versions_strict_release_urls_and_required_assets(self): self.check_case("metadata")
    def test_update_keeps_backup_wtf_and_other_addons(self): self.check_case("update")
    def test_equal_version_skip_repair_and_corruption_repair(self): self.check_case("repair")
    def test_offline_hash_bad_and_old_release_leave_installation_untouched(self): self.check_case("download_failures")
    def test_corrupt_manifest_toc_zip_traversal_and_real_decompression_limits(self): self.check_case("packages")
    def test_activation_failure_and_wow_starting_during_commit_roll_back(self): self.check_case("rollback")
    def test_restore_is_validated_local_to_client_and_preserves_both_copies(self): self.check_case("restore")
    def test_running_game_blocks_changes_and_local_settings_can_change_client(self): self.check_case("settings")
    def test_embedded_offline_install_repair_downgrade_and_rollback(self): self.check_case("bundled")

    def test_executable_never_launches_wow_or_remote_programs(self):
        text = (ROOT / "tools/Updater.cs").read_text(encoding="utf-8")
        self.assertNotIn("Process.Start", text)
        self.assertNotIn("ProcessStartInfo", text)
        self.assertNotIn("--play", text)
        self.assertNotIn(".Kill(", text)
        self.assertNotIn("powershell.exe", text.lower())
        self.assertIn("WowClassicB", text)
        self.assertIn("--install-bundled", text)


if __name__ == "__main__":
    unittest.main()
