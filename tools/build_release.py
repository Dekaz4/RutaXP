"""Build and verify the Windows installer and the distributable RutaXP ZIP.

Run from any directory: python tools/build_release.py
Only release artifacts and RutaXP/manifest.sha256 are written. The script
never installs into a game directory or runs the installer executable.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

if __package__:
    from .suite_lua import suite_files
else:
    from suite_lua import suite_files

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "RutaXP"
SUITE_INSTALLER = "Instalar_Suite_RutaXP.exe"


def runtime_files():
    names = (*suite_files(ADDON), SUITE_INSTALLER)
    notices = [p for p in (ADDON / "Licenses").iterdir() if p.is_file() and p.suffix.lower() in (".md", ".txt")]
    return sorted([ADDON / name for name in names] + notices)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_toc():
    text = (ADDON / "RutaXP.toc").read_text(encoding="utf-8-sig")
    version = re.search(r"^## Version:\s*([\w.-]+)\s*$", text, re.M).group(1)
    checked = set()
    def check_dependency(source):
        source = source.resolve()
        if not source.is_relative_to(ADDON.resolve()):
            raise RuntimeError(f"Addon dependency escapes its directory: {source}")
        if not source.is_file():
            raise RuntimeError(f"Addon dependency is missing: {source}")
        if source in checked:
            return
        checked.add(source)
        if source.suffix.lower() == ".xml":
            for element in ET.parse(source).iter():
                name = element.tag.rsplit("}", 1)[-1]
                if name in {"Include", "Script"} and element.get("file"):
                    check_dependency(source.parent / element.get("file").replace("\\", "/"))
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            source = ADDON / line.replace("\\", "/")
            check_dependency(source)
    public = set(p.resolve() for p in runtime_files())
    if not checked <= public or re.search(r"^##\s*X-RutaXP-Embedded\s*:", text, re.I | re.M):
        raise RuntimeError("Unexpected file in the public suite TOC")
    return version


def write_manifest(version):
    lines = [f"# RutaXP {version}"]
    lines += [f"{digest(p.read_bytes())}  {p.relative_to(ADDON).as_posix()}" for p in runtime_files()]
    (ADDON / "manifest.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def archive_files():
    files = runtime_files() + [ADDON / "manifest.sha256"]
    return {f"RutaXP/{p.relative_to(ADDON).as_posix()}": p.read_bytes() for p in files}


def write_zip(path, files):
    with ZipFile(path, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    with ZipFile(path) as archive:
        if set(archive.namelist()) != set(files):
            raise RuntimeError(f"ZIP file list mismatch: {path}")
        for name, expected in files.items():
            if archive.read(name) != expected:
                raise RuntimeError(f"ZIP byte mismatch: {name}")


def compile_installer(payload):
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    framework = windows / "Microsoft.NET" / "Framework64" / "v4.0.30319"
    if not (framework / "csc.exe").is_file():
        framework = windows / "Microsoft.NET" / "Framework" / "v4.0.30319"
    compiler = framework / "csc.exe"
    if not compiler.is_file():
        raise RuntimeError("The Windows .NET Framework C# compiler was not found.")
    output = ROOT / "Instalador_RutaXP.exe"
    subprocess.run([str(compiler), "/nologo", "/target:exe", "/optimize+",
                    "/main:RutaXPUpdater.Program",
                    f"/out:{output}", "/r:System.IO.Compression.dll",
                    "/r:System.IO.Compression.FileSystem.dll",
                    "/r:System.Web.Extensions.dll", "/r:System.Windows.Forms.dll",
                    f"/resource:{payload},RutaXPInstaller.payload.zip", str(ROOT / "tools" / "Installer.cs"),
                    str(ROOT / "tools" / "Updater.cs")],
                   check=True, cwd=ROOT)
    # An exact resource match prevents distributing a stale embedded addon.
    if payload.read_bytes() not in output.read_bytes():
        raise RuntimeError("The installer does not contain the current payload.")
    return output


def main():
    version = check_toc()
    # The helper's builder checks both the SHA-256 of its cached EXE and the
    # fingerprint of its public inputs before reusing a release executable.
    subprocess.run([sys.executable, str(ROOT / "tools/build_suite_setup.py")], cwd=ROOT, check=True)
    shutil.copyfile(ROOT / "dist" / SUITE_INSTALLER, ADDON / SUITE_INSTALLER)
    write_manifest(version)
    payload = ROOT / "tools" / "payload.zip"
    files = archive_files()
    write_zip(payload, files)
    installer = compile_installer(payload)
    release_files = dict(files)
    for name in ["Instalador_RutaXP.exe", "Instalar_RutaXP.bat", "Instalar.ps1", "LEEME_INSTALACION.txt", "README.md", "LICENSE", "NOTICE.md"]:
        release_files[name] = (ROOT / name).read_bytes()
    # Source for the executable and tools accompanies the binary distribution.
    for name in ["Installer.cs", "Updater.cs", "build_release.py", "publish_release.py", "build_talents.js",
                 "build_personal_suite.py", "suite_lua.py", "suite_map_journal.py", "suite_rested.py", "Install-Suite.ps1",
                 "suite_setup.py", "build_suite_setup.py", "verify_personal_suite.py", "PersonalSetup.cs",
                 "build_personal_setup.py", "suite_world_services.py", "suite_journey.py", "build_guide_legacy.py",
                 "build_dungeon_quest_links.py"]:
        release_files[f"tools/{name}"] = (ROOT / "tools" / name).read_bytes()
    test_dir = ROOT / "tests"
    for pattern in ("test_install_suite.py", "test_personal_*.py", "test_suite_*.py", "test_guide_*.py",
                    "test_dungeon_*.py", "test_quest_focus.py", "test_installers.py", "test_installers.ps1",
                    "test_updater.py", "test_updater.ps1", "test_release.py", "test_publish_release.py"):
        for source in sorted(test_dir.glob(pattern)):
            release_files[source.relative_to(ROOT).as_posix()] = source.read_bytes()
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    zip_path = destination / f"RutaXP-{version}.zip"
    write_zip(zip_path, release_files)
    addon_zip = destination / f"RutaXP-{version}-addon.zip"
    shutil.copyfile(payload, addon_zip)
    shutil.copyfile(installer, destination / installer.name)
    assets = [zip_path, addon_zip, destination / installer.name]
    (destination / "SHA256SUMS.txt").write_text(
        "".join(f"{digest(path.read_bytes())}  {path.name}\n" for path in assets), encoding="utf-8", newline="\n")
    print(f"Verified RutaXP {version}: {len(files)} addon files, {len(release_files)} packaged files.")
    print(f"ZIP: {zip_path}")
    print(f"Installer: {installer}")


if __name__ == "__main__":
    main()
