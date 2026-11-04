#!/usr/bin/env python3
"""Publish a verified stable release to github.com/Dekaz4/RutaXP.

Without --publish this only prints a plan: no subprocess, build, test, write or
network request is made. Publication requires a clean committed tree whose HEAD
is already the default branch's remote HEAD and Spanish release notes supplied
with --notes-file. A missing vX.Y.Z tag is created/pushed only after verification;
existing tags are never moved. The script never commits or pushes a branch.
Any incomplete upload remains a draft. Re-running can repair that same draft;
published releases are never changed. GitHub credentials stay inside gh.

GitHub CLI contracts: https://cli.github.com/manual/gh_release_create,
https://cli.github.com/manual/gh_release_edit and gh_release_download.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from zipfile import BadZipFile, ZipFile


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "Dekaz4/RutaXP"
HOST_REPOSITORY = "github.com/" + REPOSITORY
VERSION = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
SHA = re.compile(r"[a-fA-F0-9]{40}\Z")


class PublishError(RuntimeError):
    pass


def stable_version(value):
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise PublishError("La versión debe ser estable y tener formato X.Y.Z, sin prefijos ni sufijos.")
    return value


def version_from_toc(data):
    values = re.findall(r"^## Version:\s*(\S+)\s*$", data, re.M)
    if len(values) != 1:
        raise PublishError("RutaXP.toc debe declarar una única versión.")
    return stable_version(values[0])


def asset_names(version):
    stable_version(version)
    return (f"RutaXP-{version}.zip", f"RutaXP-{version}-addon.zip", "Instalador_RutaXP.exe", "SHA256SUMS.txt")


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def official_remote(url):
    return bool(re.fullmatch(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
                             r"Dekaz4/RutaXP(?:\.git)?", url.strip(), re.I))


def run_command(arguments, root, timeout=120):
    try:
        result = subprocess.run(arguments, cwd=root, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PublishError(f"No se pudo ejecutar {Path(arguments[0]).name}; comprueba su instalación y conexión.") from error
    if result.returncode:
        # Avoid echoing URLs with credentials, authorization errors or tokens.
        raise PublishError(f"Falló {Path(arguments[0]).name} (código {result.returncode}); comprueba el estado remoto antes de reintentar.")
    return result.stdout


def checksums(path, expected_names):
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line:
            continue
        match = re.fullmatch(r"([a-fA-F0-9]{64})  ([A-Za-z0-9_.-]+)", line)
        if not match or match[2] in result or match[2] not in expected_names:
            raise PublishError("SHA256SUMS.txt contiene una entrada inválida, duplicada o ajena a esta versión.")
        result[match[2]] = match[1].lower()
    if set(result) != set(expected_names):
        raise PublishError("SHA256SUMS.txt no contiene exactamente los tres archivos de la versión.")
    return result


def inspect_archives(directory, version):
    full, addon = directory / f"RutaXP-{version}.zip", directory / f"RutaXP-{version}-addon.zip"
    with ZipFile(addon) as small, ZipFile(full) as large:
        small_names, full_names = small.namelist(), large.namelist()
        for names in (small_names, full_names):
            if len(names) != len(set(names)):
                raise PublishError("Un ZIP contiene entradas duplicadas.")
            for name in names:
                parts = PurePosixPath(name).parts
                if (not name or "\\" in name or name.startswith("/") or ":" in name or ".." in parts
                        or any(part.lower() in {"wtf", "savedvariables", ".backups", ".sources", "__pycache__"} for part in parts)):
                    raise PublishError("Un ZIP contiene rutas o datos que no deben publicarse.")
        if any(not name.startswith("RutaXP/") for name in small_names):
            raise PublishError("El ZIP del addon contiene archivos fuera de RutaXP.")
        runtime = {name for name in full_names if name.startswith("RutaXP/")}
        if runtime != set(small_names):
            raise PublishError("Los dos ZIP no contienen el mismo addon.")
        for archive in (small, large):
            if version_from_toc(archive.read("RutaXP/RutaXP.toc").decode("utf-8-sig")) != version:
                raise PublishError("La versión de un ZIP no coincide con RutaXP.toc.")
        for name in small_names:
            if small.read(name) != large.read(name):
                raise PublishError("Los bytes del addon difieren entre los dos ZIP.")


def verify_local_assets(directory, version):
    names = asset_names(version)
    for name in names:
        path = directory / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
            raise PublishError(f"Falta un asset válido: {name}")
    expected = checksums(directory / names[-1], names[:-1])
    for name, value in expected.items():
        if digest(directory / name) != value:
            raise PublishError(f"El hash local no coincide: {name}")
    for name in names[2:-1]:
        with (directory / name).open("rb") as stream:
            if stream.read(2) != b"MZ":
                raise PublishError(f"El ejecutable no tiene una cabecera Windows válida: {name}")
    inspect_archives(directory, version)
    return {name: {"sha256": digest(directory / name), "size": (directory / name).stat().st_size} for name in names}


class Publisher:
    def __init__(self, root=ROOT, runner=run_command):
        self.root, self.runner = Path(root), runner

    def run(self, arguments, timeout=120):
        return self.runner([str(a) for a in arguments], self.root, timeout)

    def api(self, path, paginate=False):
        command = ["gh", "api", "--hostname", "github.com"]
        if paginate:
            command.extend(["--paginate", "--slurp"])
        command.append(path)
        try:
            return json.loads(self.run(command))
        except json.JSONDecodeError as error:
            raise PublishError("GitHub devolvió una respuesta que no se pudo verificar.") from error

    def tag_state(self, version):
        tag = "v" + stable_version(version)
        local_names = self.run(["git", "tag", "--list", tag]).splitlines()
        if local_names not in ([], [tag]):
            raise PublishError("No se pudo comprobar el tag local exacto.")
        local = self.run(["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"]).strip() if local_names else None
        references = {}
        for line in self.run(["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}" ]).splitlines():
            bits = line.split()
            if len(bits) == 2:
                references[bits[1]] = bits[0]
        remote = references.get(f"refs/tags/{tag}^{{}}", references.get(f"refs/tags/{tag}"))
        return local, remote

    def preflight(self, version, expected_head=None, allow_missing_tag=False):
        if self.run(["git", "status", "--porcelain=v1", "--untracked-files=all"]).strip():
            raise PublishError("Guarda y confirma todos los cambios antes de publicar; el árbol de Git debe estar limpio.")
        for option in ([], ["--push"]):
            remotes = self.run(["git", "remote", "get-url", *option, "--all", "origin"]).splitlines()
            if len(remotes) != 1 or not official_remote(remotes[0]):
                raise PublishError("El remote origin debe apuntar exclusivamente a github.com/Dekaz4/RutaXP.")
        head = self.run(["git", "rev-parse", "--verify", "HEAD"]).strip()
        if not SHA.fullmatch(head) or (expected_head and head != expected_head):
            raise PublishError("HEAD ha cambiado durante la preparación o no es un commit verificable.")
        remote_head = self.run(["git", "ls-remote", "origin", "HEAD"]).split()
        if len(remote_head) != 2 or remote_head != [head, "HEAD"]:
            raise PublishError("Publica primero el commit en la rama predeterminada de origin; su HEAD debe coincidir con el local.")
        local, remote = self.tag_state(version)
        if local != head and (local is not None or not allow_missing_tag):
            raise PublishError("El tag local de la versión debe apuntar a HEAD.")
        if remote != head and (remote is not None or not allow_missing_tag):
            raise PublishError("Publica primero el tag correcto: su commit remoto debe coincidir con HEAD.")
        return head

    def ensure_tag(self, version, head):
        self.preflight(version, head, allow_missing_tag=True)
        local, remote = self.tag_state(version)
        tag = "v" + version
        if local is None:
            if remote is None:
                self.run(["git", "tag", tag, head])
            else:
                self.run(["git", "fetch", "origin", f"refs/tags/{tag}:refs/tags/{tag}"])
        if remote is None:
            self.run(["git", "push", "origin", f"refs/tags/{tag}:refs/tags/{tag}"])
        self.preflight(version, head)

    def releases(self):
        pages = self.api(f"repos/{REPOSITORY}/releases?per_page=100", paginate=True)
        if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
            raise PublishError("No se pudo comprobar la lista de releases.")
        return [item for page in pages for item in page]

    def find_release(self, version):
        tag, found = "v" + version, []
        for release in self.releases():
            if not isinstance(release, dict):
                raise PublishError("La lista de releases contiene datos no válidos.")
            if release.get("tag_name") == tag:
                found.append(release)
            other = release.get("tag_name")
            if not isinstance(other, str):
                raise PublishError("La lista de releases contiene un tag inválido.")
            other = other.removeprefix("v")
            if (release.get("draft") is False and release.get("prerelease") is False and VERSION.fullmatch(other)
                    and tuple(map(int, other.split("."))) > tuple(map(int, version.split(".")))):
                raise PublishError("Ya existe una versión estable posterior; esta publicación no puede sustituir latest.")
        if len(found) > 1:
            raise PublishError("Hay varios borradores para el mismo tag; resuélvelos antes de publicar.")
        return found[0] if found else None

    def draft(self, ident, tag):
        if not isinstance(ident, int) or isinstance(ident, bool) or ident < 1:
            raise PublishError("El identificador del borrador no es válido.")
        value = self.api(f"repos/{REPOSITORY}/releases/{ident}")
        if (not isinstance(value, dict) or value.get("id") != ident or value.get("tag_name") != tag
                or value.get("draft") is not True or value.get("prerelease") is not False):
            raise PublishError("La release ya está publicada o no es el borrador estable esperado; no se modifica.")
        return value

    @staticmethod
    def metadata(release, assets, exact=True):
        entries = release.get("assets")
        if not isinstance(entries, list):
            raise PublishError("La lista de assets no es válida.")
        names = [entry.get("name") for entry in entries if isinstance(entry, dict)]
        if len(names) != len(entries) or len(names) != len(set(names)) or not set(names) <= set(assets):
            raise PublishError("El borrador contiene assets inesperados o duplicados; no se sobrescriben.")
        if exact and set(names) != set(assets):
            raise PublishError("La carga está incompleta; la release permanece como borrador.")
        fingerprint = []
        for entry in entries:
            if exact:
                expected = assets[entry["name"]]
                if entry.get("state") != "uploaded" or entry.get("size") != expected["size"]:
                    raise PublishError("Un asset no terminó de cargarse correctamente.")
                checksum = entry.get("digest")
                if checksum and checksum != "sha256:" + expected["sha256"]:
                    raise PublishError("GitHub informa de un hash distinto para un asset.")
            fingerprint.append((entry.get("id"), entry.get("name"), entry.get("size"), entry.get("state"), entry.get("digest")))
        return sorted(fingerprint)

    def publish(self, version, notes_file):
        version = stable_version(version)
        notes_file = Path(notes_file).resolve()
        if not notes_file.is_file() or not notes_file.read_text(encoding="utf-8-sig").strip():
            raise PublishError("Indica un archivo UTF-8 con las notas de publicación en español.")
        head = self.preflight(version, allow_missing_tag=True)
        existing = self.find_release(version)
        if existing and existing.get("draft") is not True:
            raise PublishError("La versión ya está publicada; nunca se modifican releases publicadas.")
        print("Construyendo los cuatro assets de publicación…")
        self.run([sys.executable, "-B", "tools/build_release.py"], timeout=900)
        print("Ejecutando la suite completa antes de subir archivos…")
        self.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"], timeout=1800)
        self.preflight(version, head, allow_missing_tag=True)
        assets = verify_local_assets(self.root / "dist", version)
        self.ensure_tag(version, head)
        tag = "v" + version
        # Query again after the build; another actor may have published meanwhile.
        existing = self.find_release(version)
        if existing:
            draft = self.draft(existing.get("id"), tag)
            self.metadata(draft, assets, exact=False)
            self.run(["gh", "release", "edit", tag, "--repo", HOST_REPOSITORY, "--draft",
                      "--title", f"RutaXP {version}", "--notes-file", notes_file])
        else:
            self.run(["gh", "release", "create", tag, "--repo", HOST_REPOSITORY, "--draft", "--verify-tag",
                      "--target", head, "--title", f"RutaXP {version}", "--notes-file", notes_file])
            existing = self.find_release(version)
            if not existing:
                raise PublishError("No se pudo recuperar el borrador; comprueba GitHub antes de reintentar.")
        ident = existing.get("id")
        self.draft(ident, tag)
        self.run(["gh", "release", "upload", tag, "--repo", HOST_REPOSITORY, "--clobber",
                  *[self.root / "dist" / name for name in assets]], timeout=900)
        uploaded = self.draft(ident, tag)
        fingerprint = self.metadata(uploaded, assets)
        print("Descargando el borrador y comprobando todos los SHA-256…")
        with tempfile.TemporaryDirectory(prefix="RutaXP-release-verification-") as temporary:
            command = ["gh", "release", "download", tag, "--repo", HOST_REPOSITORY, "--dir", temporary]
            for name in assets:
                command.extend(["--pattern", name])
            self.run(command, timeout=900)
            for name, expected in assets.items():
                path = Path(temporary) / name
                if not path.is_file() or path.stat().st_size != expected["size"] or digest(path) != expected["sha256"]:
                    raise PublishError("Un archivo descargado no coincide; el borrador NO se publica.")
        self.preflight(version, head)
        if fingerprint != self.metadata(self.draft(ident, tag), assets):
            raise PublishError("Los assets cambiaron tras verificarlos; el borrador NO se publica.")
        for name, expected in assets.items():
            if digest(self.root / "dist" / name) != expected["sha256"]:
                raise PublishError("Un asset local cambió durante la verificación; el borrador NO se publica.")
        self.run(["gh", "release", "edit", tag, "--repo", HOST_REPOSITORY, "--draft=false", "--latest", "--verify-tag"])
        latest = self.api(f"repos/{REPOSITORY}/releases/latest")
        if latest.get("id") != ident or latest.get("draft") is not False or latest.get("tag_name") != tag:
            raise PublishError("GitHub recibió la publicación, pero latest no se pudo confirmar; comprueba la release antes de reintentar.")
        self.metadata(latest, assets)
        return f"https://github.com/{REPOSITORY}/releases/tag/{tag}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="Construir, probar, cargar un borrador y publicarlo tras verificarlo")
    parser.add_argument("--notes-file", type=Path, help="Archivo UTF-8 con las notas españolas de esta versión")
    args = parser.parse_args(argv)
    try:
        version = version_from_toc((ROOT / "RutaXP/RutaXP.toc").read_text(encoding="utf-8-sig"))
        if not args.publish:
            print(f"Plan sin efectos: {REPOSITORY}, tag v{version}, cuatro assets: " + ", ".join(asset_names(version)))
            print("Para ejecutar: python tools/publish_release.py --publish --notes-file RUTA_AL_ARCHIVO_DE_NOTAS")
            return 0
        if not args.notes_file:
            raise PublishError("--publish requiere --notes-file con las notas en español.")
        print(Publisher().publish(version, args.notes_file))
        return 0
    except (PublishError, OSError, KeyError, ValueError, BadZipFile) as error:
        print(f"Publicación detenida: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
