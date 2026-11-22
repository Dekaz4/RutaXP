"""Build cumulative, per-version updates from the native files owned by RutaXP."""
import base64
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

VERSION = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
CATALOG = Path("tools/delta_bases")
RECIPE_FILES = ("tools/build_personal_suite.py", "tools/suite_journey.py", "tools/suite_lua.py",
                "tools/suite_map_journal.py", "tools/vendor/lfg-forever/LFGForever.zip",
                "tools/vendor/lfg-forever/LFGForeverLanguageSpanish.zip")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def native_path(root, name):
    return root / name if name in ("LICENSE", "NOTICE.md") else root / "RutaXP" / name


def make_snapshot(version, toc, hashes, read):
    if not VERSION.fullmatch(version) or hashes["RutaXP.toc"] != sha(toc):
        raise ValueError("La versión o el TOC de la base incremental no coincide.")
    # A new integration recipe or upstream module version requires recomposition.
    versions = re.search(rb'^INSTALL_VERSIONS = (.+)$', read("tools/suite_setup.py"), re.M)[1].strip()
    recipe = sha(versions + b"\n" + b"".join(hashlib.sha256(read(path)).digest() for path in RECIPE_FILES))
    return {"version": version, "recipe": recipe, "toc": base64.b64encode(toc).decode("ascii"),
            "files": dict(sorted(hashes.items()))}


def snapshot(root, version, native):
    hashes = {name: sha(native_path(root, name).read_bytes()) for name in native}
    data = make_snapshot(version, native_path(root, "RutaXP.toc").read_bytes(), hashes,
                         lambda name: (root / name).read_bytes())
    path = root / CATALOG / (version + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(data, indent=2) + "\n").encode()
    if not path.exists() or path.read_bytes() != content:
        path.write_bytes(content)
    return data


def compatible_bases(root, new):
    target = tuple(map(int, new["version"].split(".")))
    for path in sorted((root / CATALOG).glob("*.json")):
        if VERSION.fullmatch(path.stem) and tuple(map(int, path.stem.split("."))) < target:
            old = json.loads(path.read_bytes())
            if old["version"] != path.stem:
                raise ValueError(f"Base incremental incorrecta en {path.name}")
            if old["recipe"] == new["recipe"]:
                yield old


def delta_name(start, end):
    return f"RutaXP-{start}-a-{end}-delta.zip"


def write_delta(root, old, new, filename):
    rows = [f'RutaXP-delta-v1\t{old["version"]}\t{new["version"]}']
    def put(archive, name, data):
        archive.writestr(ZipInfo(name, (1980, 1, 1, 0, 0, 0)), data, compress_type=ZIP_DEFLATED)
    with ZipFile(filename, "w") as archive:
        for name in sorted(old["files"].keys() | new["files"].keys()):
            before = old["files"].get(name, "-")
            after = new["files"].get(name, "-")
            if before == after:
                continue
            rows.append(f"{before}\t{after}\t{name}")
            if after != "-":
                data = native_path(root, name).read_bytes()
                if sha(data) != after:
                    raise ValueError(f"El archivo cambió durante la preparación: {name}")
                put(archive, "files/" + name, data)
        old_toc = base64.b64decode(old["toc"], validate=True)
        if sha(old_toc) != old["files"]["RutaXP.toc"]:
            raise ValueError("TOC anterior incorrecto")
        put(archive, "old/RutaXP.toc", old_toc)
        put(archive, "delta.tsv", ("\n".join(rows) + "\n").encode("utf-8"))


def published_deltas(root, new, dist):
    paths = []
    for old in compatible_bases(root, new):
        filename = dist / delta_name(old["version"], new["version"])
        write_delta(root, old, new, filename)
        paths.append(filename)
    return paths
