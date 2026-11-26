"""Verify the personal suite and the RutaXP guide catalog for its release."""

import argparse
import hashlib
from collections import Counter
from pathlib import Path, PurePosixPath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from zlib import crc32

from lupa.lua51 import LuaRuntime
if __package__:
    from . import suite_journey
else:
    import suite_journey


MODULES = ("OpenMap", "ForeverDungeonJournal")
# Hash the original v0.7.36 catalog with each reviewed chapter reduced to its
# header, preserving chapter order. Pin each chapter body for its release.
UNCHANGED_GUIDES_HASH = "98e97b7d25fc108833520029f0a63899e943121a6e8d578e831298801782f338"
CHAPTER_HASHES = {
    "forever/alliance/30-40/04-stranglethorn-vale": (
        ((1, 2, 16), "014155fe8bbf89da889316cf3aa1f60b8f2ea3eff7e0313fc1e96dfe5efa47ac"),  # Singing Blue Shards
        ((1, 2, 6), "982e6710802e5a845e2a4cc12ee62b3cb36d7c637bd529d0e666ad4e63d011df"),  # Yohwa / Thorsen
        ((0, 0, 0), "37e395001a0ec0eded431ae0fdb9f15dd9a787177163893bde5c6a9be6cca73c"),
    ),
    "forever/horde/30-40/02-stranglethorn-vale": (
        ((1, 2, 16), "8d88d1fa8e65f334576bf45e38be70fdd2a5bff7f01316485544b7e81c431fa6"),  # Singing Blue Shards
        ((0, 0, 0), "353f9815c674fc6acf7f48479a6caacc52c3f722ed034f2fc78277105cee972f"),
    ),
    "forever/alliance/30-40/05-arathi-highlands": (
        ((1, 2, 24), "c6dc92dc7eb53288cff3ad27bb93d119500ce3bb6c4ba3e1dfffed189d6263d0"),  # Phin / Quae
        ((0, 0, 0), "d1e0adb53901aa72bf8475cf44d5d88a5faa86ee364c7686a2dbc99f5e07b107"),
    ),
}
ORIGINAL_ASSET = re.compile(r"Interface[/\\]+AddOns[/\\]+(?:OpenMap|ForeverDungeonJournal|RXPGuides)[/\\]", re.I)
LITERAL_ASSET = re.compile(r"""["']Interface[/\\]+AddOns[/\\]+RutaXP[/\\]+(?P<asset>[^"'{}\n%]+?\.(?:tga|blp|ttf|otf|ogg|mp3|wav))["']""", re.I)
ASSET_SUFFIXES = {".tga", ".blp", ".png", ".ttf", ".otf", ".ogg", ".mp3", ".wav", ".atlas"}


class Tree:
    def __init__(self, archive, root):
        self.archive, self.root = archive, root.rstrip("/") + "/"
        self.names = {name[len(self.root):].casefold(): name[len(self.root):]
                      for name in archive.namelist() if name.startswith(self.root) and not name.endswith("/")}

    def read(self, name):
        return self.archive.read(self.root + self.names[name.casefold()]).decode("utf-8-sig")

    def graph(self, files):
        found = {}
        def visit(name):
            key = name.casefold()
            if key in found:
                return
            if key not in self.names:
                raise ValueError(f"Missing file in load graph: {name}")
            found[key] = self.names[key]
            if not key.endswith(".xml"):
                return
            for node in ET.fromstring(self.read(name)).iter():
                if node.tag.split("}")[-1] not in ("Include", "Script") or "file" not in node.attrib:
                    continue
                target = node.get("file").replace("\\", "/")
                local = str(PurePosixPath(name).parent / target)
                visit(local if local.casefold() in self.names else target)
        for path in files:
            visit(path)
        return list(found.values())


def toc(text):
    meta, files = {}, []
    for row in text.splitlines():
        row = row.strip()
        if row.startswith("##"):
            key, sep, value = row[2:].partition(":")
            if sep:
                meta[key.strip()] = value.strip()
        elif row and not row.startswith("#"):
            path, _, rule = row.partition("[")
            if rule.startswith("AllowLoadGameType ") and "camelot" not in rule[:-1].split(" ", 1)[1].split(","):
                continue
            files.append(path.strip().replace("\\", "/"))
    return meta, files


def check_bindings(tree):
    entries = [n.get("name") for n in ET.fromstring(tree.read("Bindings.xml"))]
    if len(set(entries)) != len(entries) or not {"OPENMAP_FIND", "FOREVERDUNGEONJOURNAL_TOGGLE"} <= set(entries):
        raise ValueError("Native map and journal keybindings are incomplete or duplicated")
    return len(entries)


def check_native_bindings(tree, roots):
    def definitions(root):
        # Count the action code too. A binding with a surviving label but the
        # wrong function would look correct in the options screen.
        return Counter((n.get("name"), n.get("category"), (n.text or "").strip()) for n in root)
    expected = Counter()
    for module in MODULES:
        source = roots[module] / "Bindings.xml"
        if source.is_file():
            bindings = ET.parse(source).getroot()
            if (roots[module] / "RutaXP.toc").is_file():
                bindings = [node for node in bindings if node.get("name", "").startswith(module.upper() + "_")]
            expected.update(definitions(bindings))
    if definitions(ET.fromstring(tree.read("Bindings.xml"))) != expected:
        raise ValueError("Native keybinding labels or actions differ in the assembled ZIP")


def check_native_assets(tree, roots):
    counts = dict.fromkeys(MODULES, 0)
    def check(module, rel, size, crc):
        key = f"Modules/{module}/{rel}".casefold()
        member = tree.names.get(key)
        if member is None:
            raise ValueError(f"Missing native media: {module}/{rel}")
        info = tree.archive.getinfo(tree.root + member)
        if (info.file_size, info.CRC) != (size, crc):
            raise ValueError(f"Native media changed: {module}/{rel}")
        counts[module] += 1
    for module in MODULES:
        folder = roots[module]
        if (folder / "RutaXP.toc").is_file():
            folder = folder / "Modules" / module
        for p in folder.rglob("*"):
            if p.suffix.lower() in ASSET_SUFFIXES and p.is_file():
                check(module, p.relative_to(folder).as_posix(), p.stat().st_size, crc32(p.read_bytes()))
    return counts


def check_launcher(suite):
    lua = LuaRuntime()
    ns = lua.table()
    lua.execute("""
        labels, buttons, actions = {}, {}, {}
        local function noop() end
        function CreateFrame(kind)
            local f = setmetatable({shown=true}, {__index=function() return noop end})
            function f:SetText(label) self.label=label end
            function f:SetScript(event, fn) self[event]=fn end
            function f:Show() self.shown=true end
            function f:Hide() self.shown=false end
            function f:IsShown() return self.shown end
            function f:SetShown(value) self.shown=value end
            function f:CreateTexture() return CreateFrame('Texture') end
            f.TitleText = {SetText=noop}
            if kind=='Button' then table.insert(buttons,f) end
            return f
        end
        function ToggleWorldMap() actions.mapa=true end
        function ForeverDungeonJournal_Toggle() actions.mazmorras=true end
    """)
    lua.execute(suite, "RutaXP", ns)
    lua.globals().ROOT = ns
    lua.execute("""
        assert(ROOT.GetEmbeddedModule('OpenMap') == nil)
        assert(ROOT:HandleSuiteCommand('mapa') and actions.mapa)
        actions.mapa = nil
        local _, map = RutaXPModuleContext('OpenMap')
        local _, journal = RutaXPModuleContext('ForeverDungeonJournal')
        assert(map~=journal)
        assert(ROOT.GetEmbeddedModule('OpenMap') == map)
        assert(select(2, RutaXPModuleContext('OpenMap'))==map)
        ROOT.OpenGuideLibrary = function() actions.guias=true end
        ROOT.Talents = {TogglePanel=function() actions.talentos=true end}
        ROOT:HandleSuiteCommand('')
        assert(#buttons==4)
        for _, button in ipairs(buttons) do
            assert(type(button.label)=='string' and not labels[button.label])
            labels[button.label]=true
            button:OnClick()
        end
        assert(actions.mapa and actions.mazmorras and actions.guias and actions.talentos)
    """)


def chapter_block(source, chapter_id):
    match = re.search(r"^-- " + re.escape(chapter_id) + r"\n.*?(?=^-- forever/|\Z)", source, re.M | re.S)
    if match is None:
        raise ValueError(f"Missing guide chapter: {chapter_id}")
    return match


def verify_guides(tree, version):
    code = tree.read("Leveling.lua").replace("\r\n", "\n")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid RutaXP suite version for guide verification")
    release = tuple(int(part) for part in version.split("."))
    unchanged = code
    for chapter_id, versions in CHAPTER_HASHES.items():
        chapter = chapter_block(unchanged, chapter_id)
        expected = next(digest for start, digest in versions if release >= start)
        if hashlib.sha256(chapter.group().encode("utf8")).hexdigest() != expected:
            raise ValueError(f"Guide chapter {chapter_id} differs from RutaXP guides for suite {version}")
        unchanged = unchanged[:chapter.start()] + f"-- {chapter_id}\n" + unchanged[chapter.end():]
    if hashlib.sha256(unchanged.encode("utf8")).hexdigest() != UNCHANGED_GUIDES_HASH:
        raise ValueError("Guide catalog outside the reviewed chapters differs from RutaXP v0.7.36")
    lua = LuaRuntime(register_eval=False, register_builtins=False)
    loader = lua.eval("""function(source)
        local counts, ids = {}, {}
        local ns = {RegisterGuide = function(_, guide)
            assert(not ids[guide.id] and #guide.steps > 0)
            ids[guide.id] = true
            counts[guide.faction] = (counts[guide.faction] or 0) + 1
        end}
        assert(loadstring(source, 'Leveling.lua'))('RutaXP', ns)
        return counts
    end""")
    return dict(loader(code))


def verify(archive_path, addons=None):
    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        if any(not n.startswith("RutaXP/") for n in names) or [n for n in names if n.lower().endswith(".toc")] != ["RutaXP/RutaXP.toc"]:
            raise ValueError("The ZIP must contain exactly one root addon and TOC")
        if len(names) != len({n.casefold() for n in names}):
            raise ValueError("Duplicate file in ZIP")
        tree = Tree(archive, "RutaXP")
        meta, entries = toc(tree.read("RutaXP.toc"))
        settings = {s.strip() for s in meta["SavedVariables"].split(",")}
        characters = {s.strip() for s in meta["SavedVariablesPerCharacter"].split(",")}
        if not {"OpenMapDB","ForeverDungeonJournalDB","RutaXPDB"} <= settings:
            raise ValueError("Missing native account settings")
        if not {"OpenMapCharDB","ForeverDungeonJournalCharacterDB","RutaXPCharDB"} <= characters:
            raise ValueError("Missing native character settings")
        if any(not meta.get(f"X-{m}-Version") for m in MODULES):
            raise ValueError("Missing native module version")
        if meta.get("X-RutaXP-Guide-Version") != "0.7.36":
            raise ValueError("Missing original RutaXP guide version")
        if any(p.startswith("modules/rxpguides/") and p != "modules/rxpguides/migracion.txt" for p in tree.names):
            raise ValueError("Unexpected RestedXP content")
        graph = tree.graph(entries)
        scripts = [p for p in graph if p.lower().endswith(".lua")]
        if not {"Modules/OpenMap/Init.lua", "Modules/ForeverDungeonJournal/Core/Journal.lua",
                "Core.lua", "Leveling.lua", "QuestEngine.lua", "GuideOriginal.lua", "Suite.lua"} <= set(scripts):
            raise ValueError("Missing native entry point")
        lua = LuaRuntime(unpack_returned_tuples=True)
        compile_chunk = lua.eval("function(s,n) local f, err=loadstring(s,n); return err end")
        assets = set()
        for path in graph:
            source = tree.read(path)
            if path.lower().endswith(".lua"):
                error = compile_chunk(source,path)
                if error:
                    raise ValueError(error)
            if ORIGINAL_ASSET.search(source):
                raise ValueError(f"Unrelocated native asset reference in {path}")
            for match in LITERAL_ASSET.finditer(source):
                asset = re.sub(r"[/\\]+", "/", match["asset"])
                if asset.casefold() not in tree.names:
                    raise ValueError(f"Missing literal asset in {path}: {asset}")
                assets.add(asset.casefold())
        check_launcher(tree.read("Suite.lua"))
        report = {"compiled_lua":len(scripts), "xml":len(graph)-len(scripts), "literal_assets":len(assets),
                  "bindings":check_bindings(tree), "registrations":verify_guides(tree, meta.get("Version", ""))}
        journey_paths = {n for n in tree.names.values() if n.startswith(suite_journey.PREFIX)}
        if addons is not None:
            if __package__:
                from .suite_setup import client_from, find_native_sources
            else:
                from suite_setup import client_from, find_native_sources
            roots = find_native_sources(client_from(addons))
        if meta.get("X-RutaXP-Journey-UI"):
            journey_scripts = [p for p in graph if p.startswith(suite_journey.PREFIX)]
            expected = set(suite_journey.entries(None))
            expected.update(suite_journey.PREFIX + "images/" + p for p in suite_journey.IMAGES)
            expected.add(suite_journey.PREFIX + "license.txt")
            if journey_scripts != suite_journey.entries(None) or journey_paths != expected:
                raise ValueError("Unexpected Journey load order, assets or guide content")
            if addons is not None and "Journey" in roots:
                source = roots["Journey"]
                if (source / "Journey.toc").is_file():
                    content = suite_journey.contents(source)
                else:
                    content = suite_journey.embedded_contents(lambda name: (source / name).read_bytes())
                for name, data in content:
                    if archive.read("RutaXP/" + name) != data:
                        raise ValueError(f"The packaged Journey component differs from the local source: {name}")
            report["journey_ui"] = meta["X-RutaXP-Journey-UI"]
        elif journey_paths:
            raise ValueError("Journey files are present without the UI load metadata")
        if addons is not None:
            check_native_bindings(tree, roots)
            report["native_assets"] = check_native_assets(tree, roots)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--addons", type=Path, help="Compare the native map and journal keybinding actions")
    args = parser.parse_args()
    print(verify(args.artifact, args.addons))
