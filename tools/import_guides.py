#!/usr/bin/env python3
"""Capture SendaFH's compiled leveling tables into RutaXP's editable snapshot.

One-time import (requires lupa; the rebuild after import uses only stdlib):
    python tools/import_guides.py --source .sources/SendaFH

Normal editing/rebuild:
    python RutaXP/Source/build_guides.py

No guide goal, condition or prerequisite is flattened or silently discarded.
The upstream Spanish presentation localizer runs as written; quest titles,
entity names, travel identities, IDs and coordinate frames retain their data.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

try:
    from lupa.lua51 import LuaRuntime, lua_type
except ImportError as error:
    raise SystemExit("The initial import needs lupa with its Lua 5.1 runtime: python -m pip install lupa") from error


PINNED_COMMIT = "5d207e28e82e2c529143b21ace74fe88692f0067"
WORKSPACE = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://github.com/julen92/SendaFH"
INPUTS = {
    "guides": "addon/SendaFH_Guides/Guides.lua",
    "mapFrames": "addon/SendaFH_Guides/MapFrames.lua",
    "translation": "addon/SendaFH/Core/SendaGuideES.lua",
    "localizer": "addon/SendaFH/Core/SendaGuideLocale.lua",
    "names": "addon/SendaFH_Names_esES/Names.lua",
    "aliases": "addon/SendaFH/Core/SendaNamesES.lua",
}
NOTICES = {
    "LICENSE": "SendaFH-GPL-3.0.txt",
    "LICENSE-EXCEPTION.md": "SendaFH-LICENSE-EXCEPTION.md",
    "THIRD_PARTY.md": "SendaFH-THIRD_PARTY.md",
    "addon/SendaFH_Guides/LICENSE-DATA.txt": "Polestar-Guide-Data.txt",
    "addon/SendaFH_QuestDB/LICENSE-DATA.txt": "SendaFH-QuestDB-DATA.txt",
    "addon/SendaFH_Codex/LICENSE-DATA.txt": "SendaFH-Codex-DATA.txt",
    "addon/SendaFH/Licenses/pfQuest-MIT.txt": "pfQuest-MIT.txt",
    "addon/SendaFH_Names_esES/LICENSE-DATA.txt": "SendaFH-Names-esES-LICENSE-DATA.txt",
    "addon/SendaFH_Names_esES/CREDITS.md": "DingDB-CREDITS.md",
}

ZONE_NAMES_ES = {
    "Dun Morogh": "Dun Morogh",
    "Elwynn Forest": "Bosque de Elwynn",
    "Teldrassil": "Teldrassil",
    "Zephras Isle": "Isla de Zephras",
    "Westfall": "Páramos de Poniente",
    "Darkshore": "Costa Oscura",
    "Redridge Mountains": "Montañas Crestagrana",
    "Duskwood": "Bosque del Ocaso",
    "Ashenvale": "Vallefresno",
    "Thousand Needles": "Las Mil Agujas",
    "Wetlands": "Los Humedales",
    "Desolace": "Desolace",
    "Stranglethorn Vale": "Vega de Tuercespina",
    "Arathi Highlands": "Tierras Altas de Arathi",
    "Badlands": "Tierras Inhóspitas",
    "Feralas": "Feralas",
    "Tanaris": "Tanaris",
    "The Hinterlands": "Tierras del Interior",
    "Searing Gorge": "La Garganta de Fuego",
    "Un'Goro Crater": "Cráter de Un'Goro",
    "Burning Steppes": "Las Estepas Ardientes",
    "Felwood": "Frondavil",
    "Winterspring": "Cuna del Invierno",
    "Western Plaguelands": "Tierras de la Peste del Oeste",
    "Silithus": "Silithus",
    "Durotar": "Durotar",
    "Mulgore": "Mulgore",
    "Tirisfal Glades": "Claros de Tirisfal",
    "The Barrens": "Los Baldíos",
    "Silverpine Forest": "Bosque de Argénteos",
    "Stonetalon Mountains": "Sierra Espolón",
    "Hillsbrad Foothills": "Laderas de Trabalomas",
    "Swamp of Sorrows": "Pantano de las Penas",
    "Dustwallow Marsh": "Marjal Revolcafango",
    "Azshara": "Azshara",
    "Eastern Plaguelands": "Tierras de la Peste del Este",
    "Loch Modan": "Loch Modan",
}


def to_python(value: Any) -> Any:
    if lua_type(value) != "table":
        return value
    entries = list(value.items())
    if entries and all(isinstance(key, (int, float)) and int(key) == key for key, _ in entries):
        numeric = {int(key): item for key, item in entries}
        if set(numeric) == set(range(1, len(numeric) + 1)):
            return [to_python(numeric[index]) for index in range(1, len(numeric) + 1)]
    # JSON represents integer-keyed non-array tables as objects with decimal
    # keys; build_guides.py restores those keys to integers for Lua.
    return {str(int(key)) if isinstance(key, (int, float)) and int(key) == key else str(key): to_python(item)
            for key, item in entries}


def canonical(value: Any) -> Any:
    """Stable field ordering for reviewable, reproducible JSON snapshots."""
    preferred = (
        "id", "title", "faction", "races", "classes", "minLevel", "maxLevel",
        "category", "kind", "status", "summary", "zone", "zoneName", "next",
        "nextChoices", "author", "sourceAuthor", "sourceUrl", "sourceCommit",
        "sourceLicense", "steps", "note", "only", "goals", "t", "quest",
        "oi", "target", "npc", "npcName", "object", "objName", "item",
        "itemName", "count", "pre", "preAll", "closedBy", "preTitles",
        "map", "x", "y", "z", "f", "r", "spots", "candidates", "optional",
    )
    positions = {key: index for index, key in enumerate(preferred)}
    if isinstance(value, list):
        return [canonical(item) for item in value]
    if isinstance(value, dict):
        return {key: canonical(value[key]) for key in sorted(value, key=lambda key: (positions.get(key, 1000), key))}
    return value


def localize_entities(data: dict[str, Any], id_names: dict[str, dict[int, str]], aliases: dict[str, str]) -> None:
    zone_en = data.get("zoneName")
    if isinstance(zone_en, str):
        data["zoneName"] = ZONE_NAMES_ES.get(zone_en, aliases.get(zone_en, zone_en))
    for step in data.get("steps", []):
        for goal in step.get("goals", []):
            qid = goal.get("quest")
            if isinstance(qid, int) and qid in id_names["quest"]:
                goal["title"] = id_names["quest"][qid]
            elif isinstance(goal.get("title"), str) and goal["title"] in aliases:
                goal["title"] = aliases[goal["title"]]
            nid = goal.get("npc")
            if isinstance(nid, int) and nid in id_names["npc"]:
                if "npcName" in goal:
                    goal["npcName"] = id_names["npc"][nid]
                if "target" in goal:
                    goal["target"] = id_names["npc"][nid]
            if isinstance(goal.get("npcName"), str) and goal["npcName"] in aliases:
                goal["npcName"] = aliases[goal["npcName"]]
            if isinstance(goal.get("target"), str) and goal["target"] in aliases:
                goal["target"] = aliases[goal["target"]]
            iid = goal.get("item")
            if isinstance(iid, int) and iid in id_names["item"] and "itemName" in goal:
                goal["itemName"] = id_names["item"][iid]
            elif isinstance(goal.get("itemName"), str) and goal["itemName"] in aliases:
                goal["itemName"] = aliases[goal["itemName"]]
            oid = goal.get("object")
            if isinstance(oid, int) and oid in id_names["object"] and "objName" in goal:
                goal["objName"] = id_names["object"][oid]
            elif isinstance(goal.get("objName"), str) and goal["objName"] in aliases:
                goal["objName"] = aliases[goal["objName"]]
            if isinstance(goal.get("location"), str):
                loc = goal["location"]
                goal["location"] = ZONE_NAMES_ES.get(loc, aliases.get(loc, loc))
            if isinstance(goal.get("from"), str) and goal["from"] in aliases:
                goal["from"] = aliases[goal["from"]]
            for cand in goal.get("candidates", []):
                cnid = cand.get("npc")
                if isinstance(cnid, int) and cnid in id_names["npc"] and "npcName" in cand:
                    cand["npcName"] = id_names["npc"][cnid]
                elif isinstance(cand.get("npcName"), str) and cand["npcName"] in aliases:
                    cand["npcName"] = aliases[cand["npcName"]]


def import_guides(source_path: Path, addon_path: Path, expected_commit: str) -> dict[str, Any]:
    source_path = source_path.resolve()
    commit = subprocess.check_output(["git", "-C", str(source_path), "rev-parse", "HEAD"], text=True).strip()
    if commit != expected_commit:
        raise ValueError(f"Expected source commit {expected_commit}, found {commit}; pass --commit deliberately to change it")
    input_text = {key: (source_path / relative).read_text(encoding="utf-8-sig") for key, relative in INPUTS.items()}
    lua = LuaRuntime(unpack_returned_tuples=True)
    globals_ = lua.globals()
    # The capture needs tables, functions and standard string/table helpers,
    # never filesystem, process, module loading or debug access.
    for name in ("os", "io", "package", "require", "dofile", "loadfile", "debug"):
        globals_[name] = None
    globals_.GetLocale = lambda: "esES"
    namespace = lua.table()
    upstream = lua.table()
    upstream.Names = lua.table()
    id_names: dict[str, dict[int, str]] = {"quest": {}, "npc": {}, "object": {}, "item": {}}

    def add_names(loc: str, kind: str, table_val: Any) -> None:
        if loc == "esES" and kind in id_names:
            for k, v in table_val.items():
                id_names[kind][int(k)] = str(v)

    upstream.Names.Add = add_names
    globals_.SendaFH = upstream
    run_chunk = lua.eval("function(code, name, ns) local fn = assert(loadstring(code, name)); return fn(name, ns) end")
    run_chunk(input_text["translation"], "SendaGuideES.lua", namespace)
    run_chunk(input_text["localizer"], "SendaGuideLocale.lua", namespace)
    run_chunk(input_text["aliases"], "SendaNamesES.lua", namespace)
    run_chunk(input_text["names"], "SendaFH_Names_esES/Names.lua", namespace)
    aliases = {str(k): str(v) for k, v in namespace.SendaNames.items()} if namespace.SendaNames else {}
    guides: list[dict[str, Any]] = []
    categories: Counter[str] = Counter()
    captured_frames: list[dict[str, Any]] = []

    def capture(guide: Any) -> None:
        categories[str(guide.category)] += 1
        if guide.category != "Leveling":
            return
        namespace.LocalizeGuide(guide)
        data = to_python(guide)
        localize_entities(data, id_names, aliases)
        lo, hi = data.get("minLevel", 1), data.get("maxLevel", 60)
        zone_es = data.get("zoneName") or data.get("title", "esta zona")
        # Presentation-only fields enrich the original data without changing
        # IDs, grouping, conditions, prerequisites or positions.
        data.update({
            "kind": "Misiones",
            "status": "beta",
            "summary": f"Ruta paso a paso por {zone_es} (niveles {lo}–{hi}). Avanza automáticamente al aceptar, completar y entregar misiones, y descarta las que ya tengas hechas.",
            "sourceAuthor": "Polestar y colaboradores; adaptación y traducción de Forever Hispano",
            "sourceUrl": SOURCE_URL,
            "sourceCommit": commit,
            "sourceLicense": "GPL-3.0-only; avisos de datos en Licenses/",
        })
        guides.append(canonical(data))

    upstream.RegisterGuide = capture
    upstream.RegisterMapFrames = lambda frames, _pack=None: captured_frames.append(to_python(frames))
    run_chunk(input_text["guides"], "SendaFH_Guides/Guides.lua", namespace)
    run_chunk(input_text["mapFrames"], "SendaFH_Guides/MapFrames.lua", namespace)
    guides.sort(
        key=lambda guide: (
            guide.get("faction", ""),
            guide.get("minLevel", 0),
            guide.get("maxLevel", 0),
            0 if guide.get("races") else 1,
            guide["id"],
        )
    )
    if len(captured_frames) != 1 or not captured_frames[0].get("era"):
        raise ValueError("Expected exactly one non-empty Era map-frame registry")
    if len(guides) != 57 and commit == PINNED_COMMIT:
        raise ValueError(f"Pinned import must contain 57 leveling guides, found {len(guides)}")

    all_goals = [goal for guide in guides for step in guide["steps"] for goal in step["goals"]]
    stats = {
        "registeredGuides": sum(categories.values()),
        "sourceCategories": dict(sorted(categories.items())),
        "levelingGuides": len(guides),
        "levelingByFaction": dict(sorted(Counter(guide.get("faction", "Any") for guide in guides).items())),
        "steps": sum(len(guide["steps"]) for guide in guides),
        "goals": len(all_goals),
        "goalTypes": dict(sorted(Counter(goal["t"] for goal in all_goals).items())),
        "goalFields": dict(sorted(Counter(key for goal in all_goals for key in goal).items())),
    }
    document = {
        "schemaVersion": 1,
        "editing": "Edit guides below, preserving the grouped goals and all conditions. Rebuild with python RutaXP/Source/build_guides.py. Integer-keyed maps use decimal JSON object keys.",
        "provenance": {
            "project": "SendaFH / Polestar",
            "repository": SOURCE_URL,
            "branch": "sendafh",
            "commit": commit,
            "license": "GPL-3.0-only, with separate third-party notices in Licenses/",
            "capture": "Compiled upstream tables captured with Lua 5.1; Leveling category only; upstream esES presentation localizer applied without translating quest/entity/travel identities.",
            "translationStatus": "Upstream Spanish translation is partly AI-assisted and has not been fully reviewed sentence by sentence.",
            "verificationStatus": "Upstream compile/lint/simulator checks; full in-game Forever route testing pending. New 30-60 content is incomplete.",
            "inputSha256": {relative: hashlib.sha256((source_path / relative).read_bytes()).hexdigest() for relative in INPUTS.values()},
        },
        "statistics": stats,
        "mapFrames": canonical(captured_frames[0]),
        "guides": guides,
    }
    snapshot_path = addon_path / "Source" / "leveling.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    builder_path = addon_path / "Source" / "build_guides.py"
    spec = importlib.util.spec_from_file_location("rutaxp_build_guides", builder_path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load the standalone snapshot builder")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.apply_guide_overrides(document, addon_path / "Source" / "guide_overrides.json")
    builder.apply_guide_revisions(document, addon_path / "Source" / "guide_revisions.json")
    locations = addon_path / "Source" / "guide_locations.json"
    if locations.is_file():
        evidence = json.loads(locations.read_text(encoding="utf-8"))
        for relative, digest in evidence.get("sourceFiles", {}).items():
            evidence_path = (source_path / relative).resolve()
            if not evidence_path.is_relative_to(source_path.resolve()) or hashlib.sha256(evidence_path.read_bytes()).hexdigest() != digest:
                raise ValueError("Location evidence source changed: " + relative)
        builder.apply_guide_locations(document, locations)
    instruction_spec = importlib.util.spec_from_file_location("rutaxp_guide_instructions", WORKSPACE / "tools" / "guide_instructions.py")
    if instruction_spec is None or instruction_spec.loader is None:
        raise ValueError("Cannot load the guide instruction builder")
    instructions = importlib.util.module_from_spec(instruction_spec)
    instruction_spec.loader.exec_module(instructions)
    document = instructions.enrich_document(document)
    document["statistics"]["goalFields"] = dict(sorted(Counter(key for guide in document["guides"]
        for step in guide["steps"] for goal in step["goals"] for key in goal).items()))
    snapshot_path.write_text(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    licenses = addon_path / "Licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    for relative, target in NOTICES.items():
        shutil.copyfile(source_path / relative, licenses / target)
    (licenses / "PROVENANCE.txt").write_text(
        "RutaXP leveling guide adaptation\n"
        "===============================\n\n"
        "Original guide routes: Polestar, by Fitz and contributors.\n"
        "Spanish adaptation and translation: SendaFH / Forever Hispano.\n"
        f"Source: {SOURCE_URL}\nBranch: sendafh\nCommit: {commit}\n\n"
        "RutaXP captures the 57 Leveling guides, applies SendaFH's Spanish\n"
        "presentation catalogue and preserves all grouped goals, prerequisites,\n"
        "conditions, quest/object/NPC/item IDs and coordinate frames.\n"
        "RutaXP's import and build tools produce the editable Source/leveling.json\n"
        "snapshot and the runtime Leveling.lua and MapFrames.lua from that snapshot.\n\n"
        "Adapted guide text and original project code are GPL-3.0-only.\n"
        "The compiler exception does not remove the GPL from copied guide text.\n"
        "Read SendaFH-GPL-3.0.txt, SendaFH-LICENSE-EXCEPTION.md,\n"
        "SendaFH-THIRD_PARTY.md and Polestar-Guide-Data.txt for original notices.\n\n"
        "The upstream pack resolves factual quest/NPC/object/item records from\n"
        "sources including pfQuest, Blizzard tables and QuestieDB. The notices\n"
        "identify their provenance and licensing separately. No Questie code or\n"
        "quest narrative text is imported by RutaXP's capture tool.\n\n"
        "These are beta routes, not fully play-tested Forever guides. The 30-60\n"
        "route includes Classic and known Forever quests while new content is\n"
        "still being added. The Spanish catalogue also needs in-game review.\n",
        encoding="utf-8", newline="\n",
    )
    builder.build(snapshot_path, addon_path)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=WORKSPACE / ".sources" / "SendaFH")
    parser.add_argument("--output", type=Path, default=WORKSPACE / "RutaXP")
    parser.add_argument("--commit", default=PINNED_COMMIT)
    args = parser.parse_args()
    print(json.dumps(import_guides(args.source, args.output, args.commit), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
