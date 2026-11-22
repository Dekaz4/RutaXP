"""Obtain the original Forever addons on the player's PC before composing RutaXP."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from http.client import HTTPException
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
    browser_url: str = ""
    # For an original installation verified after unpacking, pin the entire
    # addon's file tree rather than the publisher's ZIP compression/metadata.
    tree_root: str = ""
    archive_sha256: str = ""


SOURCES = {
    "OpenMap": Source("OpenMap-v0.8.11-forever.zip",
                      "ef561c3026a14024dab9ac02afc4fd02a0ea7f8e6d298d6a68fc23c19d57b53b",
                      "https://github.com/openmap-world/openmap/releases/download/v0.8.11/OpenMap-v0.8.11-forever.zip"),
    "ForeverDungeonJournal": Source("DungeonJournal2.1.2.zip",
                                    "383e2c9b055133810f7ca8b30d54181339b02c70210c08b6a5b05fa387a42cdd",
                                    "https://edge.forgecdn.net/files/9730/326/DungeonJournal2.1.2.zip",
                                    "https://www.curseforge.com/wow/addons/dungeonjournal/download/9730326",
                                    "ForeverDungeonJournal",
                                    "627dd7838c9c85ba409dc63328d4a8693faabe019b5226f7e8a9af661a50abc4"),
    "Journey": Source("Journey-4.00.13.zip",
                      "ac03e7a1e02ba8c029d42e5c8da206f5c12d5db01ee02aaecc056293ac68281d",
                      "https://edge.forgecdn.net/files/9707/278/Journey-4.00.13.zip",
                      "https://www.curseforge.com/wow/addons/journey/download/9707278"),
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
            if source.archive_sha256:
                if digest_stream(stream) == source.archive_sha256:
                    return True
                stream.seek(0)
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


def find_download(source, directories, examined):
    for directory in directories:
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


def download_release(source, incoming, report):
    report(f"Descargando {source.filename} desde su publicación oficial…")
    request = Request(source.url, headers={"User-Agent": "RutaXP-Installer"})
    try:
        response = urlopen(request, timeout=30)
    except (HTTPException, OSError) as error:
        raise ConnectionError(f"No se pudo conectar para descargar {source.filename}.") from error
    with response as remote, incoming.open("wb") as dest:
        length = getattr(remote, "headers", {}).get("Content-Length", "")
        total = f" de {int(length) // (1024 * 1024)} MB" if length.isdecimal() else " MB"
        update_at = time.monotonic() + 5
        received = 0
        checksum = hashlib.sha256()
        while True:
            try:
                chunk = remote.read(1024 * 1024)
            except (HTTPException, OSError) as error:
                raise ConnectionError(f"Se interrumpió la descarga de {source.filename}.") from error
            if not chunk:
                break
            dest.write(chunk)
            checksum.update(chunk)
            received += len(chunk)
            now = time.monotonic()
            if now >= update_at:
                report(f"Descargando {source.filename} · {received // (1024 * 1024)}{total}")
                update_at = now + 5
    if checksum.hexdigest() != (source.archive_sha256 or source.sha256):
        raise ValueError(f"El ZIP de {source.filename} no coincide con la versión comprobada.")


def browser_archive(source, directories, examined, report):
    downloads = directories[0]
    report(f"Guarda {source.filename} en {downloads}. El instalador continuará automáticamente. {source.browser_url}")
    if not webbrowser.open(source.browser_url, new=2):
        raise ValueError(f"No se pudo abrir la descarga oficial. Guarda {source.filename} en {downloads} desde {source.browser_url}.")
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        found = find_download(source, directories, examined)
        if found:
            return found
        time.sleep(1)
    raise ValueError(f"No se encontró el ZIP oficial {source.filename} en {downloads}. Comprueba las descargas del navegador y vuelve a pulsar 1.")


@contextmanager
def acquire(name, cache, report):
    source = SOURCES[name]
    cache = Path(cache).absolute()
    try:
        cache.mkdir(parents=True, exist_ok=True)
        staging = tempfile.TemporaryDirectory(prefix="rutaxp-", dir=cache)
    except OSError:
        report(f"No se puede escribir en {cache}. Se usará la carpeta temporal para {source.filename}.")
        staging = tempfile.TemporaryDirectory(prefix="rutaxp-")
    cached = cache / source.filename
    with staging as temporary:
        work = Path(temporary)
        package = cached
        if not matches(cached, source):
            incoming = work / "download.zip"
            directories = tuple(dict.fromkeys((downloads_directory(), cache)))
            examined = {}
            found = find_download(source, directories, examined)
            if found is None:
                try:
                    download_release(source, incoming, report)
                except (ConnectionError, ValueError) as error:
                    if not source.browser_url:
                        raise
                    report(str(error))
                    found = browser_archive(source, directories, examined, report)
            if found is not None:
                shutil.copyfile(found, incoming)
                if not matches(incoming, source):
                    raise ValueError(f"El ZIP de {name} no coincide con la versión comprobada.")
            package = incoming
        # Only exact, hash-verified release archives are extracted; keep other
        # addons and metadata in the publisher's archive out of the composition.
        with ZipFile(package) as archive:
            for item in archive.infolist():
                if item.filename.startswith(name + "/") and not item.is_dir():
                    archive.extract(item, work)
        source_root = work / name
        if not (source_root / (name + ".toc")).is_file():
            raise ValueError(f"Falta {name}.toc en la descarga oficial.")
        # Cache publication is optional. Windows can deny the rename when the
        # destination is read-only or another process holds the file open.
        if package != cached and work.parent == cache:
            try:
                package.replace(cached)
            except OSError:
                report(f"{source.filename} verificado. La instalación continúa sin guardar el ZIP en la caché.")
        yield source_root
