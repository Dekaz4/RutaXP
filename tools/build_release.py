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
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "RutaXP"


def runtime_files():
    return sorted(p for p in ADDON.rglob("*") if p.is_file()
                  and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"}
                  and p.name != "manifest.sha256")


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
    write_manifest(version)
    payload = ROOT / "tools" / "payload.zip"
    files = archive_files()
    write_zip(payload, files)
    installer = compile_installer(payload)
    release_files = dict(files)
    for name in ["Instalador_RutaXP.exe", "Instalar_RutaXP.bat", "Instalar.ps1", "LEEME_INSTALACION.txt", "README.md", "INFORME_GUIAS.md", "LICENSE", "NOTICE.md"]:
        release_files[name] = (ROOT / name).read_bytes()
    # Source for the executable and tools accompanies the binary distribution.
    for name in ["Installer.cs", "Updater.cs", "build_release.py", "import_guides.py", "build_talents.js", "vendor_pathing.py", "build_waypoints.py",
                 "guide_coordinates.py", "guide_instructions.py", "audit_guides.py", "audit_guide_structure.py", "refresh_guides.py", "publish_release.py"]:
        release_files[f"tools/{name}"] = (ROOT / "tools" / name).read_bytes()
    for source in (ROOT / "tests").rglob("*"):
        if source.is_file() and source.suffix in {".py", ".ps1"} and "__pycache__" not in source.parts:
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
