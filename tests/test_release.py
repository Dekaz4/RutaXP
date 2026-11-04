"""Verify the actual release, without running the interactive installer UI."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "RutaXP"
VERSION = re.search(r"^## Version:\s*(\S+)", (ADDON / "RutaXP.toc").read_text(encoding="utf-8-sig"), re.M).group(1)
RELEASE = ROOT / "dist" / f"RutaXP-{VERSION}.zip"


@unittest.skipUnless(RELEASE.is_file(), "Build the release first with tools/build_release.py")
class ReleaseTests(unittest.TestCase):
    def test_published_runtime_is_identical_to_source_and_contains_no_python_cache(self):
        with ZipFile(RELEASE) as archive:
            self.assertFalse(any("__pycache__" in n or n.endswith(".pyc") for n in archive.namelist()))
            for name in archive.namelist():
                if name.startswith("RutaXP/"):
                    self.assertEqual(archive.read(name), (ROOT / name).read_bytes(), name)
            manifest = archive.read("RutaXP/manifest.sha256").decode("utf-8")
            entries = {}
            for line in manifest.splitlines():
                if not line or line.startswith("#"):
                    continue
                checksum, name = line.split("  ", 1)
                entries[f"RutaXP/{name}"] = checksum
            runtime_names = {n for n in archive.namelist() if n.startswith("RutaXP/")}
            self.assertEqual(runtime_names, set(entries) | {"RutaXP/manifest.sha256"})
            for name, checksum in entries.items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), checksum)

    def test_executable_embeds_exact_current_payload(self):
        payload = (ROOT / "tools" / "payload.zip").read_bytes()
        executable = (ROOT / "Instalador_RutaXP.exe").read_bytes()
        self.assertIn(payload, executable)
        with ZipFile(ROOT / "tools" / "payload.zip") as packed, ZipFile(RELEASE) as release:
            for name in packed.namelist():
                self.assertEqual(packed.read(name), release.read(name), name)
            self.assertEqual(release.read("Instalador_RutaXP.exe"), executable)

    def test_updater_assets_and_hashes_match_the_complete_release(self):
        addon = ROOT / "dist" / f"RutaXP-{VERSION}-addon.zip"
        self.assertEqual(addon.read_bytes(), (ROOT / "tools/payload.zip").read_bytes())
        names = {f"RutaXP-{VERSION}.zip", addon.name, "Instalador_RutaXP.exe"}
        checksums = {}
        for line in (ROOT / "dist/SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
            checksum, name = line.split("  ", 1)
            self.assertNotIn(name, checksums)
            checksums[name] = checksum
        self.assertEqual(set(checksums), names)
        for name, checksum in checksums.items():
            self.assertEqual(hashlib.sha256((ROOT / "dist" / name).read_bytes()).hexdigest(), checksum)
        with ZipFile(RELEASE) as release, ZipFile(addon) as runtime:
            for name in runtime.namelist():
                self.assertTrue(name.startswith("RutaXP/"))
                self.assertEqual(runtime.read(name), release.read(name))
            for name in ("Instalador_RutaXP.exe", "tools/Updater.cs", "tools/publish_release.py", "LICENSE", "NOTICE.md"):
                self.assertEqual(release.read(name), (ROOT / name).read_bytes())
            self.assertFalse(any(n.startswith((".sources/", ".backups/", ".git/")) or "/WTF/" in n for n in release.namelist()))

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell.exe"), "Windows PowerShell required")
    def test_actual_embedded_release_and_ps_installer_update_temp_client_preserving_backup_and_wtf(self):
        script = r"""
param([string]$SourceRoot,[string]$TemporaryRoot,[string]$ReleasePath)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$assembly=[Reflection.Assembly]::LoadFrom((Join-Path $SourceRoot 'Instalador_RutaXP.exe'))
$client=Join-Path $TemporaryRoot '_classic_beta_'
$addons=Join-Path $client 'Interface\AddOns'
[IO.Directory]::CreateDirectory($addons) | Out-Null
$saved=Join-Path $client 'WTF\SavedVariables\RutaXP.lua'
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($saved)) | Out-Null
[IO.File]::WriteAllText($saved,'player saved data')
$resource=@($assembly.GetManifestResourceNames() | Where-Object { $_.EndsWith('payload.zip') })[0]
$stream=$assembly.GetManifestResourceStream($resource)
try { $first=[RutaXPInstaller.InstallerCore]::InstallFromArchive($stream,$addons) } finally { $stream.Dispose() }
if ($first.Backup) { throw 'A first installation has no previous copy.' }
[IO.File]::WriteAllText((Join-Path $first.Target 'personal-note.txt'),'keep my old note')
$stream=$assembly.GetManifestResourceStream($resource)
try { $second=[RutaXPInstaller.InstallerCore]::InstallFromArchive($stream,$addons) } finally { $stream.Dispose() }
if ([IO.File]::ReadAllText((Join-Path $second.Backup 'personal-note.txt')) -ne 'keep my old note') { throw 'Previous user file lost.' }
$unpacked=Join-Path $TemporaryRoot 'unpacked release'
[IO.Compression.ZipFile]::ExtractToDirectory($ReleasePath,$unpacked)
. (Join-Path $SourceRoot 'Instalar.ps1')
$third=Install-RutaXP -Source (Join-Path $unpacked 'RutaXP') -AddOns ($addons+'\')
if (-not $third.Backup -or -not [IO.File]::Exists((Join-Path $third.Backup 'RutaXP.toc'))) { throw 'PS update lost previous addon.' }
$manifest=Get-RutaXPManifest $third.Target
if ($manifest.Count -lt 100) { throw 'Full runtime was not installed.' }
if ([IO.File]::ReadAllText($saved) -ne 'player saved data') { throw 'SavedVariables changed.' }
Write-Output 'Full EXE payload and PS update verified in temporary client.'
"""
        with tempfile.TemporaryDirectory(prefix="RutaXP release integration ") as temporary:
            fixture = Path(temporary) / "fixture.ps1"
            fixture.write_text(script, encoding="utf-8-sig")
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                     "-File", str(fixture), "-SourceRoot", str(ROOT), "-TemporaryRoot", temporary,
                                     "-ReleasePath", str(RELEASE)], capture_output=True, text=True, errors="replace", timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Full EXE payload and PS update verified", result.stdout)


if __name__ == "__main__":
    unittest.main()
