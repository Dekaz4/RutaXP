"""Create a single offline Windows installer carrying one verified personal suite."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def build(archive, dest):
    with ZipFile(archive) as bundle:
        toc = bundle.read("RutaXP/RutaXP.toc").decode("utf-8-sig")
        if "## X-RutaXP-Embedded: OpenMap, ForeverDungeonJournal, RXPGuides" not in toc:
            raise ValueError("Se necesita el ZIP personal completo.")
    framework = Path(os.environ["WINDIR"]) / "Microsoft.NET"
    compiler = next(framework.glob("Framework64/v4.0.30319/csc.exe"), framework / "Framework/v4.0.30319/csc.exe")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as staging:
        exe = Path(staging) / dest.name
        subprocess.run([str(compiler), "/nologo", "/target:winexe", "/optimize+", "/codepage:65001",
                        "/r:System.Windows.Forms.dll", "/r:System.Drawing.dll", f"/out:{exe}",
                        f"/resource:{ROOT / 'tools/Install-Suite.ps1'},Install-Suite.ps1",
                        str(ROOT / "tools/PersonalSetup.cs")], check=True)
        digest = hashlib.sha256()
        size = 0
        with archive.open("rb") as src, exe.open("ab") as out:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
                out.write(chunk)
            out.write(struct.pack("<Q", size) + digest.digest() + b"RUTAXP-PERSONAL-1")
        subprocess.run([str(exe), "--verify"], check=True, timeout=240)
        os.replace(exe, dest)
    return dest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/Instalar_RutaXP_Personal.exe")
    args = parser.parse_args()
    print(build(args.archive, args.output))
