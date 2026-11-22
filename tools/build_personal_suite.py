"""Compose a single installable WoW Forever addon from locally installed modules.

Only the active Forever load graph and its assets are copied. This program does
not open WTF or run an installer. Its output is for the owner of those copies.
"""
import argparse
import hashlib
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from suite_lua import suite_files, bind_namespace
from suite_map_journal import transform_lua as transform_journal_map
import suite_journey

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("OpenMap", "ForeverDungeonJournal")
ASSETS = {".blp", ".tga", ".png", ".ogg", ".mp3", ".wav", ".ttf", ".otf", ".atlas"}
ASSET_ROOT = re.compile(r"(Interface)([/\\]+)(AddOns)\2(OpenMap|ForeverDungeonJournal|RXPGuides)(?=[/\\])", re.I)
FILE_TAG = re.compile(r"""<!--.*?-->|<(?:Script|Include)\b[^<>]*?\bfile\s*=\s*(["'])([^"']+)\1[^<>]*>""", re.S)
TOC_ENTRY = re.compile(r"([^\[\]]+?)(?:\s+\[(AllowLoadGameType|AllowLoadTextLocale) ([\w,]+)\])?")


def relocate(text):
    return ASSET_ROOT.sub(lambda m: m[2].join(("Interface", "AddOns", "RutaXP", "Modules", m[4])), text)


def lines_and_metadata(text):
    entries, metadata = [], {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("##") and ":" in line:
            key, value = line[2:].split(":", 1)
            metadata[key.strip()] = value.strip()
        elif line and not line.startswith("#"):
            match = TOC_ENTRY.fullmatch(line)
            if not match:
                raise ValueError(f"Unsupported TOC entry: {line}")
            path, kind, value = match.groups()
            if kind != "AllowLoadGameType" or "camelot" in value.split(","):
                suffix = f" [{kind} {value}]" if kind == "AllowLoadTextLocale" else ""
                entries.append((path.strip().replace("\\", "/"), suffix))
    return entries, metadata


class Module:
    def __init__(self, name, source):
        self.name, self.root = name, source.resolve(strict=True)
        self.prefix = f"Modules/{name}/"
        self.required, self.xml = set(), {}
        self.entries, self.metadata = lines_and_metadata(self.read(name + ".toc"))
        self.locales = {path: suffix.split()[-1].rstrip("]") for path, suffix in self.entries if suffix}
        if not self.entries or "Version" not in self.metadata:
            raise ValueError(f"Missing native TOC data for {name}")
        for path, _ in self.entries:
            self.visit(self.resolve(path))

    def read(self, path):
        return (self.root / path).read_text(encoding="utf-8-sig")

    def resolve(self, target, parent=None):
        target = Path(target.replace("\\", "/"))
        if target.is_absolute() or target.drive:
            raise ValueError(f"Absolute load path in {self.name}: {target}")
        for base in (parent or self.root, self.root):
            path = (base / target).resolve()
            if path.is_relative_to(self.root) and path.is_file():
                return path
        raise FileNotFoundError(f"Missing {self.name}/{target} referenced from {parent or self.root}")

    def visit(self, path):
        rel = path.relative_to(self.root).as_posix()
        if rel in self.required:
            return
        self.required.add(rel)
        if path.suffix.lower() != ".xml":
            return
        def adapt(match):
            if not match[2]:
                return match[0]
            child = self.resolve(match[2], path.parent)
            self.visit(child)
            # Blizzard accepts both XML-relative and addon-root-relative references.
            if child.is_relative_to(path.parent):
                link = child.relative_to(path.parent).as_posix()
            else:
                link = self.prefix + child.relative_to(self.root).as_posix()
            return match[0][:match.start(2)-match.start()] + link + match[0][match.end(2)-match.start():]
        text = FILE_TAG.sub(adapt, self.read(rel))
        ET.fromstring(text)
        self.xml[rel] = relocate(text)

    def contents(self):
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root).as_posix()
            suffix = path.suffix.lower()
            if rel in self.xml:
                yield self.prefix + rel, self.xml[rel].encode("utf8")
            elif rel in self.required and suffix == ".lua":
                text = self.read(rel)
                # Relocate upstream literal paths before inserting new module-specific paths.
                text = bind_namespace(self.name, rel, transform_journal_map(self.name, rel, relocate(text)))
                # The updater distributed with 0.7 reads one plain path per TOC line.
                # Run the very same native locale gate without a TOC path annotation.
                if rel in self.locales:
                    text = f'if GetLocale() ~= "{self.locales[rel]}" then return end\n' + text
                yield self.prefix + rel, text.encode("utf8")
            elif rel in self.required or suffix in ASSETS or path.name.lower().startswith(
                    ("license", "copying", "sources", "credits", "notice", "map_sources")) or "LICENSES/" in rel:
                yield self.prefix + rel, path.read_bytes()

    def bindings(self):
        path = self.root / "Bindings.xml"
        return ET.parse(path).getroot() if path.is_file() else ()


class InstalledModule:
    """Reuse a user's integrated module when this PC never had the standalone addon."""
    def __init__(self, name, suite):
        self.name, self.root = name, suite.resolve(strict=True)
        self.prefix = f"Modules/{name}/"
        self.hashes = {}
        for row in (self.root / "manifest.sha256").read_text(encoding="utf-8-sig").splitlines():
            if not row or row.startswith("#"):
                continue
            digest, path = row.split("  ", 1)
            if path.startswith(self.prefix) or path in ("RutaXP.toc", "Bindings.xml"):
                if (path in self.hashes or any(p in ("", ".", "..") for p in path.split("/"))
                        or "\\" in path or ":" in path or not re.fullmatch(r"[a-fA-F0-9]{64}", digest)):
                    raise ValueError(f"Manifiesto del módulo {name} no válido: {path}")
                self.hashes[path] = digest.lower()
        rows, meta = lines_and_metadata(self.read("RutaXP.toc").decode("utf-8-sig"))
        self.required = {p for p in self.hashes if p.startswith(self.prefix)}
        self.entries = [(p[len(self.prefix):], flag) for p, flag in rows if p.startswith(self.prefix)]
        if not self.entries or any(self.prefix + p not in self.required for p, _ in self.entries):
            raise ValueError(f"Faltan los archivos del módulo instalado {name}.")
        if name == "Journey":
            self.metadata = {"Version": meta["X-RutaXP-Journey-UI"]}
            if [self.prefix + p for p, _ in self.entries] != suite_journey.entries(None):
                raise ValueError("Versión de Journey incompatible con esta actualización.")
        else:
            self.metadata = {k:meta[f"X-{name}-{k}"] for k in ("Title","Version")}
            for key in ("SavedVariables", "SavedVariablesPerCharacter"):
                self.metadata[key] = ", ".join(v for v in re.split(r"[,\s]+", meta.get(key, "")) if v.startswith(name))
            self.metadata["OptionalDeps"] = ", ".join(v for v in re.split(r"[,\s]+", meta.get("OptionalDeps",""))
                                                       if v and not v.startswith("RXPGuides"))

    def read(self, name):
        path = (self.root / name).resolve(strict=True)
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError(f"Ruta de módulo no válida: {name}")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.hashes.get(name):
            raise ValueError(f"El archivo del módulo instalado ha cambiado: {name}")
        return data

    def contents(self):
        if self.name == "Journey":
            yield from suite_journey.embedded_contents(self.read)
        else:
            for p in sorted(self.required):
                yield p, self.read(p)

    def bindings(self):
        xml = ET.fromstring(self.read("Bindings.xml"))
        return [node for node in xml if node.get("name","").startswith(self.name.upper() + "_")]


def merged_bindings(modules):
    bindings, names = ET.Element("Bindings"), set()
    for module in modules:
        for node in module.bindings():
            name = node.get("name")
            if not name or name in names:
                raise ValueError(f"Invalid or duplicate binding {name}")
            bindings.append(node)
            names.add(name)
    return ET.tostring(bindings, encoding="utf-8")


def compose(template, roots, destination):
    modules = [Module(name, roots[name]) if (roots[name] / (name + ".toc")).is_file()
               else InstalledModule(name, roots[name]) for name in MODULES]
    base = (template / "RutaXP.toc").read_text(encoding="utf-8-sig")
    _, metadata = lines_and_metadata(base)
    for key in ("SavedVariables", "SavedVariablesPerCharacter", "OptionalDeps"):
        names = []
        for source in [metadata] + [m.metadata for m in modules]:
            for name in re.split(r"[,\s]+", source.get(key, "")):
                if name and name not in names and name not in MODULES:
                    names.append(name)
        if names:
            header = f"## {key}: " + ", ".join(names)
            if key in metadata:
                base = re.sub(r"^## " + key + r":.*$", lambda _: header, base, flags=re.M)
            else:
                base = header + "\n" + base
    headers = ["## X-RutaXP-Embedded: " + ", ".join(MODULES)]
    load = []
    for module in modules:
        headers += [f"## X-{module.name}-{key}: {module.metadata[key]}" for key in ("Title", "Version")]
        load += [module.prefix + rel for rel, _ in module.entries]
    journey = roots.get("Journey")
    prior_journey = None
    if journey:
        if (journey / "Journey.toc").is_file():
            _, journey_meta = lines_and_metadata((journey / "Journey.toc").read_text(encoding="utf-8-sig"))
        else:
            prior_journey = InstalledModule("Journey", journey)
            journey_meta = prior_journey.metadata
        headers.append("## X-RutaXP-Journey-UI: " + journey_meta["Version"])
        load.extend(suite_journey.entries(journey))
    toc = "\n".join(headers) + "\n" + base.strip() + "\n\n" + "\n".join(load) + "\n"

    destination.parent.mkdir(parents=True, exist_ok=True)
    # Build beside the final path so an interrupted run never replaces a working ZIP.
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as handle:
        temp = Path(handle.name)
    try:
        checksums = {}
        with ZipFile(temp, "w", ZIP_DEFLATED, compresslevel=3) as archive:
            def write(name, data):
                if name in checksums:
                    raise ValueError(f"Duplicate archive entry: {name}")
                checksums[name] = hashlib.sha256(data).hexdigest()
                archive.writestr("RutaXP/" + name, data)
            for name in suite_files(template):
                write(name, toc.encode("utf8") if name == "RutaXP.toc" else (template / name).read_bytes())
            # The already-distributed 1.1.0 updater checks for this directory after activation.
            write("Modules/RXPGuides/Migracion.txt", "Las guías se cargan desde Leveling.lua de RutaXP.\n".encode("utf8"))
            for module in modules:
                for name, data in module.contents():
                    write(name, data)
            if journey:
                for name, data in (prior_journey.contents() if prior_journey else suite_journey.contents(journey)):
                    write(name, data)
            write("Bindings.xml", merged_bindings(modules))
            for name in ("NOTICE.md", "LICENSE"):
                write(name, (template.parent / name).read_bytes())
            license_dir = template / "Licenses"
            for lic in sorted(license_dir.glob("*")):
                if lic.is_file():
                    write("Licenses/" + lic.name, lic.read_bytes())
            manifest = [f"# RutaXP {metadata['Version']}"] + [f"{value}  {name}" for name, value in sorted(checksums.items())]
            archive.writestr("RutaXP/manifest.sha256", "\n".join(manifest) + "\n")
        with ZipFile(temp) as archive:
            for name, digest in checksums.items():
                if hashlib.sha256(archive.read("RutaXP/" + name)).hexdigest() != digest:
                    raise ValueError(f"Bad archive member: {name}")
        os.replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)
    return {module.name: len(module.required) for module in modules}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addons", required=True, type=Path, help="WoW Forever Interface/AddOns folder")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is None:
        _, metadata = lines_and_metadata((ROOT / "RutaXP/RutaXP.toc").read_text(encoding="utf-8-sig"))
        args.output = ROOT / "dist" / f"RutaXP-{metadata['Version']}-personal.zip"
    from suite_setup import find_native_sources, client_from
    roots = find_native_sources(client_from(args.addons))
    loaded = compose(ROOT / "RutaXP", roots, args.output)
    print(f"{args.output} · " + ", ".join(f"{name}: {count}" for name,count in loaded.items()))


if __name__ == "__main__":
    main()
