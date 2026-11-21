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

from suite_lua import SUITE_FILES, bind_namespace
from suite_map_journal import transform_lua as transform_journal_map
from suite_rested import transform_lua as transform_rested
import suite_journey

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("OpenMap", "ForeverDungeonJournal", "RXPGuides")
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
                transform = transform_rested if self.name == "RXPGuides" else transform_journal_map
                # Relocate upstream literal paths before inserting new module-specific paths.
                text = bind_namespace(self.name, rel, transform(self.name, rel, relocate(text)))
                # The updater distributed with 0.7 reads one plain path per TOC line.
                # Run the very same native locale gate without a TOC path annotation.
                if rel in self.locales:
                    text = f'if GetLocale() ~= "{self.locales[rel]}" then return end\n' + text
                yield self.prefix + rel, text.encode("utf8")
            elif rel in self.required or suffix in ASSETS or path.name.lower().startswith(
                    ("license", "copying", "sources", "credits", "notice", "map_sources")) or "LICENSES/" in rel:
                yield self.prefix + rel, path.read_bytes()


def merged_bindings(modules):
    bindings, names = ET.Element("Bindings"), set()
    for module in modules:
        path = module.root / "Bindings.xml"
        if not path.exists():
            continue
        for node in ET.parse(path).getroot():
            name = node.get("name")
            if not name or name in names:
                raise ValueError(f"Invalid or duplicate binding {name}")
            bindings.append(node)
            names.add(name)
    return ET.tostring(bindings, encoding="utf-8")


def compose(template, roots, destination):
    modules = [Module(name, roots[name]) for name in MODULES]
    base = (template / "RutaXP.toc").read_text(encoding="utf-8-sig")
    _, metadata = lines_and_metadata(base)
    for key in ("SavedVariables", "SavedVariablesPerCharacter", "OptionalDeps"):
        names = []
        for source in [metadata] + [m.metadata for m in modules]:
            for token in re.split(r"[,\s]+", source.get(key, "")):
                name = {"RXPDB":"RutaXPRestedDB","RXPString":"RutaXPRestedString"}.get(token, token)
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
    if journey:
        _, journey_meta = lines_and_metadata((journey / "Journey.toc").read_text(encoding="utf-8-sig"))
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
            for name in SUITE_FILES:
                write(name, toc.encode("utf8") if name == "RutaXP.toc" else (template / name).read_bytes())
            for module in modules:
                for name, data in module.contents():
                    write(name, data)
            if journey:
                for name, data in suite_journey.contents(journey):
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
    from suite_rested import prepare_official_source
    from suite_setup import find_native_sources, client_from
    roots = find_native_sources(client_from(args.addons))
    local_rested = args.addons / "RXPGuides"
    with tempfile.TemporaryDirectory(prefix="RutaXP-official-") as temp:
        roots["RXPGuides"] = prepare_official_source(local_rested if (local_rested / "RXPGuides.toc").is_file() else None,
                                                     ROOT / ".sources" / "suite", Path(temp) / "RXPGuides")
        loaded = compose(ROOT / "RutaXP", roots, args.output)
    print(f"{args.output} · " + ", ".join(f"{name}: {count}" for name,count in loaded.items()))


if __name__ == "__main__":
    main()
