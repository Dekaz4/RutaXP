"""Verify the assembled personal ZIP against the native Forever guide lists."""

import argparse
from collections import Counter
from pathlib import Path, PurePosixPath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from zlib import crc32

from lupa.lua51 import LuaRuntime


MODULES = ("OpenMap", "ForeverDungeonJournal", "RXPGuides")
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


def check_native_bindings(tree, official, addons):
    def definitions(root):
        # Count the action code too. A binding with a surviving label but the
        # wrong function would look correct in the options screen.
        return Counter((n.get("name"), n.get("category"), (n.text or "").strip()) for n in root)
    expected = Counter()
    for module in MODULES:
        if module == "RXPGuides":
            matches = [p for p in official.namelist() if p.count("/") == 1 and p.endswith("/Bindings.xml")]
            if matches:
                expected.update(definitions(ET.fromstring(official.read(matches[0]))))
        else:
            expected.update(definitions(ET.parse(addons / module / "Bindings.xml").getroot()))
    if definitions(ET.fromstring(tree.read("Bindings.xml"))) != expected:
        raise ValueError("Native keybinding labels or actions differ in the assembled ZIP")


def check_native_assets(tree, official, addons):
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
    for module in ("OpenMap","ForeverDungeonJournal"):
        folder = addons / module
        for p in folder.rglob("*"):
            if p.suffix.lower() in ASSET_SUFFIXES and p.is_file():
                check(module, p.relative_to(folder).as_posix(), p.stat().st_size, crc32(p.read_bytes()))
    for info in official.infolist():
        parts = info.filename.split("/", 1)
        if (len(parts) == 2 and parts[1].split("/")[0] in {"Textures","UI","libs","DB","Guides","lang","locale"}
                and PurePosixPath(parts[1]).suffix.lower() in ASSET_SUFFIXES):
            check("RXPGuides", parts[1], info.file_size, info.CRC)
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
        local _, rxp = RutaXPModuleContext('RXPGuides')
        local _, map = RutaXPModuleContext('OpenMap')
        local _, journal = RutaXPModuleContext('ForeverDungeonJournal')
        assert(map~=journal and journal~=rxp and map~=rxp)
        assert(select(2, RutaXPModuleContext('OpenMap'))==map)
        rxp.v2 = {ShowGuideSelectionMenu=function() actions.guias=true end}
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


def compare_guides(tree, entries, reference):
    native_root = next(iter({name.rsplit("/", 1)[0] for name in reference.namelist()
                             if name.count("/") == 1 and name.endswith("/RXPGuides.toc")}))
    native = Tree(reference, native_root)
    _, native_entries = toc(native.read("RXPGuides.toc"))
    lists = [p for p in native_entries if p.lower().endswith("guidelist-forever.xml")]
    if not any(p.startswith("lang/Guides-esES/") for p in lists):
        raise ValueError("Missing native list of Spanish guides")
    prefix = "Modules/RXPGuides/"
    if {p for p in entries if p.lower().endswith("guidelist-forever.xml")} != {prefix + p for p in lists}:
        raise ValueError("The package does not load all the native Forever guide lists")
    # Compare each list in load order, including the actual Lua source of every
    # registration. Namespaces are adapted, localized guide text stays identical.
    bytes_seen = set()
    english, spanish = [], []
    for path in lists:
        original = [p for p in native.graph([path]) if p.lower().endswith(".lua")]
        copied = [p[len(prefix):] for p in tree.graph([prefix + path]) if p.lower().endswith(".lua")]
        if original != copied:
            raise ValueError(f"Different guides or registration order in {path}")
        for rel in original:
            if rel in bytes_seen:
                continue
            src = native.read(rel).replace("\r\n", "\n")
            embedded = tree.read(prefix + rel).replace("\r\n", "\n")
            if src != embedded.replace('RutaXPModuleContext("RXPGuides")', "..."):
                raise ValueError(f"Guide differs from official copy: {rel}")
            bytes_seen.add(rel)
        if path.startswith("Guides/"):
            english = copied
        elif path.startswith("lang/Guides-esES/"):
            spanish = copied
    registrations = {}
    for locale, files in (("enUS", english), ("esES", spanish)):
        for faction in ("Alliance", "Horde"):
            # A sandbox exposes just the two character queries used by stock
            # guides. Guide text is collected without executing its contents.
            lua = LuaRuntime(unpack_returned_tuples=True, register_eval=False, register_builtins=False)
            setup = lua.eval("""function(locale, faction)
                local counts=0
                local mod={enabledLocale={}}
                if locale~='enUS' then mod.enabledLocale[locale]=true end
                mod.RegisterGuide=function(body) assert(type(body)=='string' and #body>0); counts=counts+1 end
                local env={RXPGuides=mod,RXP=mod,GetLocale=function() return locale end,
                    UnitFactionGroup=function() return faction end,RutaXPModuleContext=function(name) return name,mod end}
                return function(source, name)
                    local f=assert(loadstring(source,name)); setfenv(f,env); f('RutaXP',{})
                end, function() return counts end
            end""")
            run, count = setup(locale, faction)
            for rel in files:
                run(tree.read(prefix + rel), rel)
            if not count():
                raise ValueError(f"No {locale} guide registrations for {faction}")
            registrations[f"{locale}/{faction}"] = count()
    return registrations


def verify(archive_path, official_path, addons=None):
    with ZipFile(archive_path) as archive, ZipFile(official_path) as reference:
        names = archive.namelist()
        if any(not n.startswith("RutaXP/") for n in names) or [n for n in names if n.lower().endswith(".toc")] != ["RutaXP/RutaXP.toc"]:
            raise ValueError("The ZIP must contain exactly one root addon and TOC")
        if len(names) != len({n.casefold() for n in names}):
            raise ValueError("Duplicate file in ZIP")
        tree = Tree(archive, "RutaXP")
        meta, entries = toc(tree.read("RutaXP.toc"))
        settings = {s.strip() for s in meta["SavedVariables"].split(",")}
        characters = {s.strip() for s in meta["SavedVariablesPerCharacter"].split(",")}
        if not {"OpenMapDB","ForeverDungeonJournalDB","RutaXPDB","RXPSettings","RutaXPRestedDB"} <= settings:
            raise ValueError("Missing native account settings")
        if not {"OpenMapCharDB","ForeverDungeonJournalCharacterDB","RutaXPCharDB","RXPCSettings"} <= characters:
            raise ValueError("Missing native character settings")
        if any(not meta.get(f"X-{m}-Version") for m in MODULES):
            raise ValueError("Missing native module version")
        graph = tree.graph(entries)
        scripts = [p for p in graph if p.lower().endswith(".lua")]
        if not {"Modules/OpenMap/Init.lua", "Modules/ForeverDungeonJournal/Core/Journal.lua",
                "Modules/RXPGuides/RXPGuides.lua", "Suite.lua"} <= set(scripts):
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
                  "bindings":check_bindings(tree), "registrations":compare_guides(tree, entries, reference)}
        if addons is not None:
            check_native_bindings(tree, reference, addons)
            report["native_assets"] = check_native_assets(tree, reference, addons)
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("official", type=Path, help="Pinned upstream RestedXP source ZIP")
    parser.add_argument("--addons", type=Path, help="Compare the native map and journal keybinding actions")
    args = parser.parse_args()
    print(verify(args.artifact, args.official, args.addons))
