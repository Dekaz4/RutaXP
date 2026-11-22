"""Build factual dungeon links locally from the installed journal and pinned Forever data.

Requires lupa and the SendaFH checkout used for the leveling catalog. Only quest
IDs and places are taken from RestedXP; no guide instructions enter the output.
"""

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

from lupa.lua51 import LuaRuntime, lua_type

try:
    from .suite_rested import ARCHIVE_HASH
except ImportError:
    from suite_rested import ARCHIVE_HASH


ROOT = Path(__file__).resolve().parents[1]


def ARRAY(table):
    return [table[i] for i in range(1, len(table) + 1)] if table is not None else []


def refs(value):
    if value is None:
        return []
    return ARRAY(value) if lua_type(value) == "table" else [value]


def read_lua(path):
    return path.read_text(encoding="utf-8-sig")


def load_sources(journal, senda):
    # The build-time interpreter can only see data tables, Lua's basic library
    # and inert event frames. It has no WoW, Python, I/O or OS globals.
    lua = LuaRuntime(register_eval=False, register_builtins=False)
    env, run = lua.execute("""
        local env={pairs=pairs, ipairs=ipairs, type=type, next=next, tonumber=tonumber,
            tostring=tostring, select=select, unpack=unpack, pcall=pcall, tonumber=tonumber,
            math=math, string=string, table=table, assert=assert, error=error,
            setmetatable=setmetatable, getmetatable=getmetatable, strlower=string.lower,
            strsplit=nil, tinsert=table.insert, tremove=table.remove, wipe=function(t) for k in pairs(t) do t[k]=nil end end}
        env._G=env
        return env,function(text,name,...)
            local chunk=assert(loadstring(text,"@"..name));setfenv(chunk,env);return chunk(...)
        end
    """)
    run(
        """
        FDJ={Constants={ALBA_FAIRMOON_LOCATION="Alba Fairmoon"},ContentLocales={}}
        ForeverDungeonJournal_NS=FDJ
        function RutaXPModuleContext() return "ForeverDungeonJournal",FDJ end
        function CreateFrame() return {RegisterEvent=function() end, SetScript=function() end} end
        db={}; names={}
        SendaFH={QuestDB={AddData=function(kind, rows)
            db[kind]=db[kind] or {};for id,row in pairs(rows) do db[kind][id]=row end
        end},Names={Add=function(_,kind,rows)
            names[kind]=names[kind] or {};for id,name in pairs(rows) do names[kind][id]=name end
        end}}
    """,
        "catalog bootstrap",
    )
    fdj = env.FDJ
    data = journal / "Data"
    updates = read_lua(data / "QuestUpdates.lua")
    for key in re.findall(r"FDJ\.([A-Z][A-Z_0-9]+)\[", updates):
        fdj[key] = lua.table()
    for file in (
        "Dungeons",
        "DungeonEntrances",
        "ArrowNpcIds",
        "QuestMaps",
        "QuestChains",
        "QuestUpdates",
    ):
        run(read_lua(data / (file + ".lua")), file, "ForeverDungeonJournal", fdj)
    localized = read_lua(journal / "Localization/Content_esES.lua")
    run(localized, "journal esES", "ForeverDungeonJournal", fdj)
    for file in ("Quests", "Npcs", "Objects", "Items"):
        run(read_lua(senda / "SendaFH_QuestDB" / (file + ".lua")), file)
    run(read_lua(senda / "SendaFH_Names_esES/Names.lua"), "names")
    return fdj, env.db, env.names


FIXED_GOTO = re.compile(
    r"^\s*\.goto\s+(\d+)/(\d+),(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)(?=[,\s]|$)"
)
ACTION = re.compile(r"^\s*\.(accept|turnin|complete)\s+(\d+)\b(?:,(\d+))?")
INDIRECT_STEP = re.compile(
    r"^\s*(?:#(?:completewith|loop|sticky)\b|\.(?:loop|waypoint|line|subzone|fly|hs)\b)",
    re.MULTILINE,
)


def fixed_point(line, frames):
    """RestedXP's fixed-map notation is map/continent,west,north in yards."""
    match = FIXED_GOTO.match(line)
    if not match:
        return None
    frame = frames.get(match[1])
    if not frame or frame["c"] != int(match[2]):
        return None
    x = (float(match[3]) - frame["left"]) / (frame["right"] - frame["left"]) * 100
    y = (float(match[4]) - frame["top"]) / (frame["bottom"] - frame["top"]) * 100
    if 0 <= x <= 100 and 0 <= y <= 100:
        return int(match[1]), round(x, 2), round(y, 2)
    return None


def rxp_facts(archive, frames):
    """Match only active directives in the pinned first-party Forever sources."""
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_HASH:
        raise ValueError(
            "Se necesita el ZIP oficial de RestedXP fijado para esta versión."
        )
    world, dungeon = set(), set()
    acts, contacts, observed = defaultdict(set), defaultdict(set), defaultdict(set)
    with ZipFile(archive) as z:
        for name in z.namelist():
            match = re.fullmatch(r"[^/]+/Guides/forever/(dungeon/)?([^/]+)\.lua", name)
            if not match:
                continue
            is_dungeon = bool(match[1])
            file_faction = match[2].partition("-")[0]
            text = z.read(name).decode("utf-8-sig")
            chapters = re.split(r"(?=^#name\s+)", text, flags=re.MULTILINE)
            for chunk in chapters:
                title = re.match(r"^#name\s+([^\r\n]+)", chunk)
                if not title:
                    continue
                chapter = (
                    re.sub(r"^\d+(?:-\d+)?\s+", "", title[1])
                    .strip()
                    .removeprefix("The ")
                )
                for step in re.split(r"^step\b", chunk, flags=re.MULTILINE)[1:]:
                    # A long step can visit several NPCs, work areas or even zones.
                    # A single fixed-map point and a directly attached directive
                    # are needed to turn it into a reusable, stand-alone waypoint.
                    step = step.split("]])", 1)[0]
                    points = [
                        fixed_point(line, frames)
                        for line in step.splitlines()
                        if re.match(r"^\s*\.goto\b", line)
                    ]
                    direct = (
                        not INDIRECT_STEP.search(step)
                        and len(set(points)) == 1
                        and bool(points)
                        and points[0] is not None
                    )
                    faction = (
                        file_faction if file_faction in ("Alliance", "Horde") else None
                    )
                    if not faction:
                        label = re.match(
                            r"^\s*<<\s*(Alliance|Horde)\s*(?:\r?\n|$)", step
                        )
                        if label:
                            faction = label[1]
                    reached = False
                    for line in step.splitlines():
                        if re.match(r"^\s*\.goto\b", line):
                            reached = True
                        action = ACTION.match(line)
                        if not action:
                            continue
                        tag, quest, obj = action[1], int(action[2]), action[3]
                        key = {
                            "accept": "pickup",
                            "complete": "work",
                            "turnin": "turnin",
                        }[tag]
                        (dungeon if is_dungeon else world).add(quest)
                        if is_dungeon:
                            acts[chapter, tag].add(quest)
                        if direct and reached and "<<" not in line:
                            point = points[0]
                            if key in ("pickup", "turnin"):
                                contacts[quest, key].add(point)
                            if (
                                not is_dungeon
                                and key in ("work", "turnin")
                                and (key != "work" or obj)
                            ):
                                observed[quest, key].add(
                                    (*point, int(obj) if obj else None, faction)
                                )
    places = {}
    for key, choices in contacts.items():
        if len(choices) == 1:
            map_id, x, y = next(iter(choices))
            places[key] = {"map": map_id, "x": x, "y": y, "f": "e"}
    targets = defaultdict(dict)
    for (quest, action), rows in observed.items():
        unique = {r[:4] for r in rows}
        if len(unique) != 1:
            continue
        map_id, x, y, obj = next(iter(unique))
        point = {"map": map_id, "x": x, "y": y, "f": "e"}
        factions = {r[4] for r in rows}
        if len(factions) == 1 and None not in factions:
            point["faction"] = next(iter(factions))
        if obj:
            point["objectiveIndex"] = obj
        targets[quest][action] = point
    return world, dungeon, acts, places, dict(targets)


def numeric_maps(journal):
    script = read_lua(journal / "Core/Journal.lua")

    def read(key):
        block = re.search(r"FDJ\." + key + r"\s*=\s*\{(.*?)\}", script, re.DOTALL)
        return (
            {
                name: int(id)
                for id, name in re.findall(r'\[(\d+)\]\s*=\s*"([^"]+)"', block[1])
            }
            if block
            else {}
        )

    return read("INSTANCE_ID_TO_DUNGEON"), read("SCARLET_WING_MAPS")


def map_point(point):
    if (
        point
        and isinstance(point.mapID, int)
        and point.x is not None
        and point.y is not None
    ):
        return {
            "map": point.mapID,
            "x": round(point.x * 100, 3),
            "y": round(point.y * 100, 3),
            "f": "l",
        }
    return {}


def first_spawn(row):
    if row is None or not row[2] or not row[4]:
        return {}
    return {"map": row[2], "f": "e" if row[3] == 0 else "l", "x": row[5], "y": row[6]}


def named_ref(db, names, ident, kind):
    table = "npcs" if kind == "npc" else "objects"
    row = db[table][ident]
    point = first_spawn(row)
    point.update({kind: ident})
    name = names[kind][ident] or (row and row[1])
    if name:
        point["name"] = name
    return point


def quest_places(
    id, quest, journal_row, fdj, db, names, route_points, in_flags, rested_places
):
    result = {}
    for field, pos, wording in (("pickup", 7, "pickup"), ("turnin", 8, "turnin")):
        ids = refs(quest[pos])
        item = next(iter(refs(quest[9])), None) if field == "pickup" else None
        if not item and field == "pickup" and journal_row["startItem"]:
            item = journal_row["startItem"][1]
        hint = str(journal_row[wording] or "")
        authored = (
            (journal_row["startMap"] or fdj.QUEST_START_MAPS[id] or journal_row["map"])
            if field == "pickup"
            else journal_row["turninMap"]
        )
        npc_name = (authored and authored.targetName) or hint.partition(",")[0].strip()
        guessed = fdj.ARROW_NPC_IDS[npc_name]
        if guessed in ids:
            ids = [guessed] + [i for i in ids if i != guessed]
        elif not ids and guessed and not item:
            ids = [guessed]
        ref = ids[0] if ids else None
        point = (
            named_ref(db, names, abs(ref), "npc" if ref > 0 else "object")
            if ref
            else {}
        )
        if item and not ref:
            source = db["items"][item]
            point.update(item=item, name=names.item[item] or (source and source[1]))
        if not point.get("name") and authored and authored.targetName:
            point["name"] = authored.targetName
        route = route_points.get((id, field))
        if route and (
            not ref or route.get("npc") == ref or route.get("object") == -ref
        ):
            point.update(route)
        override = map_point(authored)
        if override:
            point.update(override)
        elif "map" not in point and not item and (id, field) in rested_places:
            point.update(rested_places[id, field])
            point["rested"] = True
        inside = in_flags.get((id, field))
        phrase = hint.lower()
        if (
            inside is None
            and field == "pickup"
            and journal_row["startsInDungeon"]
            and journal_row["dungeonStep"] is not False
            and "outside" not in phrase
        ):
            inside = True
        if inside is None and re.search(
            r"\binside (?:the (?:dungeon|instance)|hall of thanes|the deadmines|blackfathom deeps)",
            phrase,
        ):
            inside = True
        if inside is None and (
            point.get("map")
            or re.search(r"\boutside (?:the )?(?:dungeon|instance|portal)", phrase)
        ):
            inside = (
                False if point.get("map", 0) in OUTDOOR or "outside" in phrase else None
            )
        if inside is True:
            # Exterior arrows often point at an approach for an interior NPC.
            for k in ("map", "x", "y", "f"):
                point.pop(k, None)
        if inside is not None:
            point["inside"] = inside
        result[field] = {k: v for k, v in point.items() if v is not None}
    return result


# Classic zone/city UiMapIDs in the SendaFH coordinate database. Other map
# IDs require journal evidence before being called an exterior or interior.
OUTDOOR = set(range(1411, 1459))


def catalog(journal, senda, archive, snapshot):
    fdj, db, names = load_sources(journal, senda)
    original = json.loads(snapshot.read_bytes())
    world, dungeon_guide, actions, rested_places, world_targets = rxp_facts(
        archive, original["mapFrames"]["era"]
    )
    instances, wings = numeric_maps(journal)
    route_points = {}
    for guide in original["guides"]:
        for step in guide["steps"]:
            for goal in step["goals"]:
                if (
                    goal.get("quest")
                    and goal.get("t") in ("accept", "turnin")
                    and all(k in goal for k in ("x", "y", "map"))
                ):
                    point = {
                        k: goal[k]
                        for k in ("map", "x", "y", "f", "npc", "object")
                        if k in goal
                    }
                    route_points.setdefault(
                        (
                            goal["quest"],
                            "pickup" if goal["t"] == "accept" else "turnin",
                        ),
                        point,
                    )

    inside = {}
    work = set()
    chain_names = {}
    for _, chain in sorted(fdj.QUEST_PREREQ_CHAINS.items()):
        for link in ARRAY(chain):
            if link.id and not link.itemStep:
                chain_names[link.id] = link.name
                if link.needsDungeon:
                    work.add(link.id)
                if link.startsInDungeon:
                    inside[link.id, "pickup"] = True
    for pins in fdj.MAP_QUEST_PINS.values():
        for pin in ARRAY(pins):
            for spot in ARRAY(pin.spots):
                for quest in ARRAY(spot.quests):
                    for act in ARRAY(quest.acts):
                        if act in ("start", "end"):
                            inside[
                                quest.id, "pickup" if act == "start" else "turnin"
                            ] = True
                        elif quest.id:
                            work.add(quest.id)

    dungeons, rows, required = {}, {}, set()
    for key, section in sorted(fdj.DB.items()):
        levels = [int(x) for x in re.findall(r"\d+", str(section.level or ""))]
        # The journal also lists seasonal chains, professions and pseudo-pages.
        entrance = map_point(section.entrance)
        if not entrance and key not in instances and key not in wings:
            continue
        localized = fdj.ContentLocales.esES.dungeons[key]
        quests = []
        for row in ARRAY(section.quests):
            if (
                not isinstance(row.id, int)
                or row.id < 1
                or row.id > 999999
                or row.learnTitle
            ):
                continue
            quests.append(row.id)
            rows[row.id] = row
            if (
                row.dungeonStep is not False
                and not row.routeNoRun
                and not row.hideFromMainList
            ):
                work.add(row.id)
        # The named official chapters mix in travel quests, so only attribute
        # dungeon work to IDs the journal independently assigns to that dungeon.
        work.update(set(quests) & actions[key.removeprefix("The "), "complete"])
        dungeons[key] = {
            k: v
            for k, v in {
                "name": localized and localized.name or key,
                "minLevel": levels[0] if levels else None,
                "maxLevel": levels[-1] if levels else None,
                "entrance": entrance or None,
                "instanceID": instances.get(key),
                "instanceMapID": wings.get(key),
                "quests": sorted(set(quests)),
            }.items()
            if v is not None
        }
        required.update(quests)

    result = {}
    while required:
        id = required.pop()
        if id in result:
            continue
        quest = db.quests[id] or {}
        journal_row = rows.get(id) or fdj.QUEST_PREREQ_DETAILS[id] or {}
        # Python and Lua return different values for missing indices.
        if isinstance(quest, dict):
            quest = defaultdict(lambda: None)
        if isinstance(journal_row, dict):
            journal_row = defaultdict(lambda: None)
        faction = {1: "Alliance", 2: "Horde"}.get(quest[6], journal_row["faction"])
        record = {
            k: v
            for k, v in {
                "title": names.quest[id]
                or quest[1]
                or journal_row["name"]
                or chain_names.get(id),
                "level": journal_row["level"] or quest[2],
                "minLevel": journal_row["requires"] or quest[3],
                "faction": faction if faction in ("Alliance", "Horde") else None,
                "classes": quest[5],
                "races": quest[4],
                "raceHigh": quest[18],
                "skill": quest[15],
                "holiday": quest[16],
                "classToken": journal_row["classOnly"],
                "profession": journal_row["profession"],
                "unavailable": journal_row["unavailable"],
            }.items()
            if isinstance(v, (str, int))
        }
        if journal_row["unavailableRaces"]:
            record["unavailableRaces"] = sorted(
                k for k, v in journal_row["unavailableRaces"].items() if v
            )
        if journal_row["repNeeds"]:
            record["reputation"] = [
                {"faction": r.faction, "standing": r.standing}
                for r in ARRAY(journal_row["repNeeds"])
            ]
        record.update(
            quest_places(
                id,
                quest,
                journal_row,
                fdj,
                db,
                names,
                route_points,
                inside,
                rested_places,
            )
        )
        prereqs = refs(quest[10])
        all_parents = refs(quest[17])
        if not prereqs and not all_parents:
            all_parents = [
                link.id
                for link in ARRAY(fdj.QUEST_PREREQ_CHAINS[id])
                if link.id and link.id != id and not link.itemStep
            ]
        for field, ids in (
            ("pre", prereqs),
            ("preAll", all_parents),
            ("excl", refs(quest[11]) + refs(journal_row["lostIf"])),
        ):
            if ids:
                record[field] = sorted(set(ids))
                if field != "excl":
                    required.update(abs(i) for i in ids if i != id)
        if id in work:
            record["workInside"] = True
        result[id] = record
    return {
        "dungeons": dungeons,
        "quests": result,
        "restedWorld": dict.fromkeys(sorted(world), True),
        "restedDungeon": dict.fromkeys(sorted(dungeon_guide), True),
        "restedTargets": world_targets,
    }


def lua_value(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, list):
        return "{" + ",".join(map(lua_value, value)) + "}"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                "[" + lua_value(k) + "]=" + lua_value(v)
                for k, v in sorted(value.items())
            )
            + "}"
        )
    return str(value)


def write(data, destination):
    text = [
        "-- Generated by tools/build_dungeon_quest_links.py. Numeric quest/route facts only.",
        "-- Sources: SendaFH_QuestDB and Names_esES (see Licenses/), ForeverDungeonJournal and official RestedXP Forever.",
        "local _, ns = ...",
        "ns.DungeonQuestData = {",
    ]
    for kind, rows in data.items():
        text.append("    " + kind + " = {")
        for key, row in sorted(rows.items()):
            text.append("        [" + lua_value(key) + "] = " + lua_value(row) + ",")
        text.append("    },")
    text.append("}")
    destination.write_text("\n".join(text) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--journal", type=Path, required=True)
    p.add_argument("--senda", type=Path, default=ROOT / ".sources/SendaFH/addon")
    p.add_argument(
        "--rested", type=Path, required=True, help="Pinned first-party RXPGuides ZIP"
    )
    p.add_argument(
        "--snapshot", type=Path, default=ROOT / "RutaXP/Source/leveling.json"
    )
    p.add_argument("--output", type=Path, default=ROOT / "RutaXP/DungeonQuestData.lua")
    args = p.parse_args()
    data = catalog(args.journal, args.senda, args.rested, args.snapshot)
    write(data, args.output)
    print({k: len(v) for k, v in data.items()})
