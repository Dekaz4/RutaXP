"""Build the standalone public setup from an explicit list of redistributable files."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


ROOT = Path(__file__).resolve().parents[1]
BUILD_VERSION = "6.13.0"
NAME = "Instalar_Suite_RutaXP"
SCRIPTS = ("suite_setup.py", "build_suite_setup.py", "build_personal_suite.py",
           "suite_lua.py", "suite_map_journal.py", "suite_rested.py")
TEMPLATE = ("RutaXP.toc", "TalentCore.lua", "Talents.lua", "TalentBuilds.lua", "Suite.lua")


def bundle_inputs(root):
    return [
        *(root / "RutaXP" / name for name in TEMPLATE),
        *(f for f in sorted((root / "RutaXP/Licenses").iterdir())
          if f.is_file() and f.suffix.lower() in (".md", ".txt")),
        root / "tools/Install-Suite.ps1", root / "NOTICE.md", root / "LICENSE",
    ]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(root, public):
    h = hashlib.sha256()
    h.update(f"{BUILD_VERSION} {sys.version_info[:3]}".encode())
    for path in sorted([*public, *(root / "tools" / f for f in SCRIPTS)]):
        h.update(path.relative_to(root).as_posix().encode() + b"\0")
        h.update(bytes.fromhex(digest(path)))
    return h.hexdigest()


def build_python(root):
    try:
        if importlib.metadata.version("PyInstaller") == BUILD_VERSION:
            return Path(sys.executable)
    except importlib.metadata.PackageNotFoundError:
        pass
    directory = root / ".backups/suite-setup-venv"
    interpreter = directory / "Scripts/python.exe"
    if not interpreter.is_file():
        venv.EnvBuilder(with_pip=True).create(directory)
    version = subprocess.run([str(interpreter), "-m", "PyInstaller", "--version"],
                             capture_output=True, text=True)
    if version.returncode or version.stdout.strip() != BUILD_VERSION:
        subprocess.run([str(interpreter), "-m", "pip", "--disable-pip-version-check", "install",
                        f"PyInstaller=={BUILD_VERSION}"], check=True)
    return interpreter


def build(root=ROOT, force=False):
    root = Path(root).resolve()
    public = bundle_inputs(root)
    inputs = fingerprint(root, public)
    cache = root / ".backups/suite-setup-build"
    binary = root / "dist" / f"{NAME}.exe"
    record = cache / "record.json"
    if not force and binary.is_file() and record.is_file():
        try:
            previous = json.loads(record.read_text("utf8"))
            if previous == {"source": inputs, "sha256": digest(binary)}:
                return binary
        except (OSError, UnicodeError, ValueError):
            pass
    if sys.platform != "win32":
        raise RuntimeError("La compilación del instalador de Windows requiere Windows.")
    cache.mkdir(parents=True, exist_ok=True)
    binary.parent.mkdir(parents=True, exist_ok=True)
    python = build_python(root)
    with tempfile.TemporaryDirectory(dir=cache) as new:
        new = Path(new)
        cmd = [str(python), "-m", "PyInstaller", "--noconfirm", "--onefile", "--noupx",
               "--console", "--hide-console", "hide-early", "--name", NAME, "--log-level", "WARN",
               "--specpath", str(new), "--distpath", str(new), "--workpath", str(cache / "work")]
        for path in public:
            cmd.extend(["--add-data", str(path) + os.pathsep + path.relative_to(root).parent.as_posix()])
        cmd.append(str(root / "tools/suite_setup.py"))
        subprocess.run(cmd, check=True, cwd=root)
        product = new / f"{NAME}.exe"
        checksum = digest(product)
        product.replace(binary)
        temp = new / "record.json"
        temp.write_text(json.dumps({"source": inputs, "sha256": checksum}), encoding="utf8")
        temp.replace(record)
    return binary


if __name__ == "__main__":
    print(build(force="--force" in sys.argv))
