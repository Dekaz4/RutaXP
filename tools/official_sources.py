"""Obtain the original Forever addons on the player's PC before composing RutaXP."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import time
from urllib.request import Request, urlopen
import webbrowser
from zipfile import BadZipFile, ZipFile


@dataclass(frozen=True)
class Source:
    filename: str
    sha256: str
    url: str
    browser: bool = False
    # For an original installation verified after unpacking, pin the entire
    # addon's file tree rather than the publisher's ZIP compression/metadata.
    tree_root: str = ""


SOURCES = {
    "OpenMap": Source("OpenMap-v0.8.11-forever.zip",
                      "ef561c3026a14024dab9ac02afc4fd02a0ea7f8e6d298d6a68fc23c19d57b53b",
                      "https://github.com/openmap-world/openmap/releases/download/v0.8.11/OpenMap-v0.8.11-forever.zip"),
    "ForeverDungeonJournal": Source("DungeonJournal2.1.2.zip",
                                    "383e2c9b055133810f7ca8b30d54181339b02c70210c08b6a5b05fa387a42cdd",
                                    "https://www.curseforge.com/wow/addons/dungeonjournal/download/9730326",
                                    True, "ForeverDungeonJournal"),
    "Journey": Source("Journey-4.00.13.zip",
                      "ac03e7a1e02ba8c029d42e5c8da206f5c12d5db01ee02aaecc056293ac68281d",
                      "https://www.curseforge.com/wow/addons/journey/download/9707278", True),
}


def downloads_directory():
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
                location, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
            return Path(os.path.expandvars(location))
        except OSError:
            pass
    return Path.home() / "Downloads"


def digest_stream(stream):
    checksum = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        checksum.update(block)
    return checksum.hexdigest()


def matches(path, source):
    try:
        with path.open("rb") as stream:
            if not source.tree_root:
                return digest_stream(stream) == source.sha256
            prefix = source.tree_root + "/"
            with ZipFile(stream) as archive:
                members = sorted((i for i in archive.infolist() if i.filename.startswith(prefix) and not i.is_dir()),
                                 key=lambda i: i.filename)
                if not members or len(members) > 5000 or sum(i.file_size for i in members) > 160 * 1024 * 1024:
                    return False
                tree = hashlib.sha256()
                for item in members:
                    with archive.open(item) as file:
                        checksum = digest_stream(file)
                    tree.update(f"{checksum}  {item.filename[len(prefix):]}\n".encode("utf8"))
                return tree.hexdigest() == source.sha256
    except (OSError, BadZipFile, RuntimeError, EOFError):
        return False


def browser_archive(source, cache, report):
    # The author hosts this file on CurseForge. Let their normal download page
    # deliver it in the player's browser; reuse a previous download when present.
    downloads = downloads_directory()
    examined = {}

    def find_download():
        for directory in dict.fromkeys((downloads, cache)):
            for candidate in directory.glob(Path(source.filename).stem + "*.zip"):
                try:
                    stat = candidate.stat()
                except OSError:
                    continue
                stamp = (stat.st_size, stat.st_mtime_ns)
                if examined.get(candidate) != stamp:
                    if matches(candidate, source):
                        return candidate
                    examined[candidate] = stamp

    found = find_download()
    if found:
        return found
    report(f"Abriendo la descarga oficial de {source.filename}. Esperando el ZIP en {downloads}…")
    if not webbrowser.open(source.url, new=2):
        raise ValueError(f"No se pudo abrir la descarga oficial. Guarda {source.filename} en {downloads} desde {source.url}.")
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        found = find_download()
        if found:
            return found
        time.sleep(1)
    raise ValueError(f"No se encontró el ZIP oficial {source.filename} en {downloads}. Comprueba las descargas del navegador y vuelve a pulsar 1.")


@contextmanager
def acquire(name, cache, report):
    source = SOURCES[name]
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    cached = cache / source.filename
    with tempfile.TemporaryDirectory(prefix="rutaxp-", dir=cache) as temporary:
        work = Path(temporary)
        if not matches(cached, source):
            incoming = work / "download.zip"
            if source.browser:
                shutil.copyfile(browser_archive(source, cache, report), incoming)
            else:
                report(f"Descargando {name} desde su publicación oficial…")
                request = Request(source.url, headers={"User-Agent": "RutaXP-Installer"})
                try:
                    with urlopen(request, timeout=60) as remote, incoming.open("wb") as dest:
                        shutil.copyfileobj(remote, dest, length=1024 * 1024)
                except OSError as error:
                    raise OSError(f"No se pudo descargar {name}. Comprueba la conexión y vuelve a pulsar 1. {error}") from error
            if not matches(incoming, source):
                raise ValueError(f"El ZIP de {name} no coincide con la versión comprobada.")
            incoming.replace(cached)
        # Only exact, hash-verified release archives are extracted; keep other
        # addons and metadata in the publisher's archive out of the composition.
        with ZipFile(cached) as archive:
            for item in archive.infolist():
                if item.filename.startswith(name + "/") and not item.is_dir():
                    archive.extract(item, work)
        source_root = work / name
        if not (source_root / (name + ".toc")).is_file():
            raise ValueError(f"Falta {name}.toc en la descarga oficial.")
        yield source_root
