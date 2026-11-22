"""Regenerate the checked-in, distance-independent Forever service locations.

Requires lupa and local checkouts of julen92/SendaFH at 5d207e28e82e2c529143b21ace74fe88692f0067
and shagu/pfQuest at 104f35678ca39ab1fb78b655f815cc7016f5e0c8. These are build inputs only.
"""

import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path

from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
HASHES = {
    "SendaFH_Codex/Npcs1.lua": "d4673aa84c1a8adfc94c9c775788d38b254aac20997917eec5ee9459d121fefc",
    "SendaFH_Codex/Npcs2.lua": "abc1a73d40137504ce4e61902f1c67ec0bb6c8a59eb1e02831e68a876da42827",
    "SendaFH_Codex/Npcs3.lua": "67d9bdfc2af4f9dc3bdf32350e7f9f16cc237b28f565b4f45ba2f9e02349e763",
    "SendaFH_Codex/Objects1.lua": "c87b30c8a322a8b25e0f5767d14ec7420fe2be728aff6ca431bce129819dffa1",
    "SendaFH_Codex/Meta.lua": "ccd6070a269d3b05bb73e127ed1774f3d90eda0fc08dc26be2bf584fa2fa13ea",
    "SendaFH_Names_esES/Names.lua": "f72519937e3310f4ef47e1aee41480c0f6732b1f4bc2cd8c3befa14a34ae7a75",
    "SendaFH/Core/ClassTrainers.lua": "4019f60ddfc12726d2ff782d639cad8ead95244696a118e82f90e4b7cbe1ec0f",
    "SendaFH/Nav/TravelData.lua": "1e7e2503c00b52fe96fa4001dc168ffb9d3805952dea4041c25dd6eb7f3c51a8",
    "db/meta.lua": "0f6dfef398946112d8220688c29d33025aad02677b43e21e2387550d9f9e760e",
    "db/objects.lua": "be4846e2f2049cafba7da5ed18d6422bde35ed0e6f6ac34cb1215c1bbafd306e",
}
PROFESSIONS = {
    129: "Primeros auxilios", 164: "Herrería", 165: "Peletería", 171: "Alquimia",
    182: "Herboristería", 185: "Cocina", 186: "Minería", 197: "Sastrería",
    202: "Ingeniería", 333: "Encantamiento", 356: "Pesca", 393: "Desuello",
}
ROLES = {"auctioneer": "auctioneer", "banker": "banker", "battlemaster": "battlemaster",
         "innkeeper": "innkeeper", "repair": "repair", "stablemaster": "stable"}
# The Codex records these as generic trainers. QuestieDB Forever, revision
# e1652ce, gives their specialties in npcKeys.subName. The two trauma surgeons
# teach bandage recipes after Triage (SendaFH's Forever first-aid.guide).
TRAINER_SPECIALTIES = {
    1355: "trainer:185",  # Cook Ghilm
    1701: "trainer:186",  # Dank Drizzlecut
    4898: "trainer:182",  # Brant Jasperbloom
    4900: "trainer:171",  # Alchemist Narett
    8140: "class:PALADIN",  # Brother Karman
    8141: "class:WARRIOR",  # Captain Evencane
    12920: "trainer:129",  # Doctor Gregory Victor
    12939: "trainer:129",  # Doctor Gustaf VanHowzen
}
# AreaTable -> UiMap for classic outdoor zones and capitals where pfQuest locates a mailbox.
AREA_MAPS = {
    1: 1426, 3: 1418, 4: 1419, 8: 1435, 10: 1431, 11: 1437, 12: 1429,
    14: 1411, 15: 1445, 16: 1447, 17: 1413, 28: 1422, 33: 1434, 36: 1416,
    38: 1432, 40: 1436, 44: 1433, 45: 1417, 46: 1428, 47: 1425, 51: 1427,
    85: 1420, 130: 1421, 139: 1423, 141: 1438, 148: 1439, 215: 1412, 267: 1424,
    331: 1440, 357: 1444, 361: 1448, 400: 1441, 405: 1443, 406: 1442, 440: 1446,
    490: 1449, 493: 1450, 618: 1452, 1377: 1451, 1497: 1458, 1519: 1453,
    1537: 1455, 1637: 1454, 1638: 1456, 1657: 1457,
}


def load(lua, directory, name, *args):
    source = (directory / name).read_bytes().replace(b"\r\n", b"\n")
    if sha256(source).hexdigest() != HASHES[name]:
        raise ValueError(f"Unexpected source revision: {name}")
    lua.execute(source, *args)


def collect(senda, pfquest):
    lua = LuaRuntime()
    lua.execute("""
        pfDB = {objects={}}
        SendaFH = { Names = { Add = function(_, kind, rows)
            if kind == "npc" then for id,name in pairs(rows) do names[id] = name end end
        end }, Codex={}, RegisterMapFrames=function(t) frames=t.era end }
        names = {}
        ns = { RegisterClassTrainers=function(t) trainers=t end,
            RegisterClassTrainerIds=function() end, RegisterMapFrames=function() end,
            Nav={RegisterTravelData=function(t) inns=t.inns end, RegisterCrossings=function() end} }
    """)
    env = lua.globals()
    load(lua, pfquest, "db/meta.lua")
    load(lua, pfquest, "db/objects.lua")
    load(lua, senda, "SendaFH_Names_esES/Names.lua")
    load(lua, senda, "SendaFH/Core/ClassTrainers.lua", "SendaFH", env.ns)
    load(lua, senda, "SendaFH/Nav/TravelData.lua", "SendaFH", env.ns)
    pins = defaultdict(set)
    meta = env.pfDB.meta
    inns = {(inn.npc, inn.map): inn for inn in env.inns.values()}
    class_sites = {(t.npc, t.map): t for t in env.trainers.values()}
    preferred_sites = {"innkeeper": inns, "classTrainer": class_sites}

    def read_records(kind, names, records, *_):
        english = {int(row[0]): row[2] for row in
                   (line.split("\t", 2) for line in names.splitlines() if line)}
        for line in records.splitlines():
            if not line:
                continue
            key, record = line.split("\t", 1)
            ident = int(key)
            fields = record.split(";")
            if kind == "object":
                # Two additional mailboxes recorded in the Forever capitals.
                if ident in (659159, 696264) and english[ident] == "Mailbox":
                    for location in filter(None, fields[2:]):
                        map_text, frame, x, y = location.split(",")
                        map_id = int(map_text)
                        faction = {1453: "A", 1454: "H"}[map_id]
                        pins[map_id].add(("mailbox", faction, int(x) / 10, int(y) / 10,
                                          "Buzón", None, None, frame == "e"))
                continue
            side = fields[2]
            for role in fields[5].split(","):
                if role == "trainer":
                    role = TRAINER_SPECIALTIES.get(ident, role)
                category, required_class, detail = ROLES.get(role), None, None
                if role.startswith("trainer:"):
                    category, detail = "profTrainer", PROFESSIONS[int(role[8:])]
                elif role.startswith("class:"):
                    category, required_class = "classTrainer", role[6:]
                if not category or (category == "repair" and ident in (2404, 3543)):
                    continue  # Unreliable Forever repair offers at these two Hillsbrad merchants.
                faction = side or (meta[role] and meta[role][ident])
                if not faction and ident in (2836, 8736):
                    faction = "AH"  # Booty Bay's Brikk Keencraft and Gadgetzan's Buzzek Bracketswing.
                if faction not in {"A", "H", "AH"}:
                    continue
                for location in filter(None, fields[7:]):
                    map_text, frame, *coords = location.split(",")
                    map_id = int(map_text)
                    override = preferred_sites.get(category, {}).get((ident, map_id))
                    if override:
                        x, y, era = override.x, override.y, override.f == "e"
                    elif len(coords) == 2 and frame in ("", "e"):
                        x, y, era = int(coords[0]) / 10, int(coords[1]) / 10, frame == "e"
                    else:
                        continue  # No single known position for a roaming NPC on this map.
                    pins[map_id].add((category, faction, x, y, env.names[ident] or english[ident],
                                      required_class, detail, era, ident))

    env.SendaFH.Codex.Register = read_records
    for name in HASHES:
        if name.startswith(("SendaFH_Codex/Npcs", "SendaFH_Codex/Objects")):
            load(lua, senda, name)
    env.SendaFH.Codex.Register = lua.eval("function() end")
    load(lua, senda, "SendaFH_Codex/Meta.lua")
    for negative_id, side in meta.mailbox.items():
        obj = env.pfDB.objects.data[-negative_id]
        if obj is None or side not in ("A", "H", "AH"):
            continue
        for point in obj.coords.values():
            if point[3] in AREA_MAPS and 0 < point[1] < 100 and 0 < point[2] < 100:
                pins[AREA_MAPS[point[3]]].add(("mailbox", side, point[1], point[2], "Buzón", None, None, True))
    return pins, dict(env.frames)


def lua_value(value):
    if value is None:
        return "nil"
    return json.dumps(value, ensure_ascii=False)


def render(pins, frames):
    lines = [
        "-- Generated by tools/suite_world_services.py from pfQuest 104f356 (MIT) and SendaFH 5d207e2.",
        "-- Source notices in Licenses: pfQuest-MIT.txt, SendaFH-Codex-DATA.txt and SendaFH-Names-esES-LICENSE-DATA.txt.",
        "-- Additional trainer specialties from QuestieDB Forever e1652ce (Licenses/QuestieDB-NOTICE.md).",
        "local _, ns = ...", "",
        "-- Era map bounds: continent, north, west, south, east (world yards).",
        "ns.worldMapServiceEra = {",
    ]
    for map_id in sorted(k for k, sites in pins.items() if any(row[7] for row in sites)):
        f = frames[map_id]
        lines.append(f"    [{map_id}] = {{{f.c}, {f.top}, {f.left}, {f.bottom}, {f.right}}},")
    lines.extend(["}", "", "-- Per map: service, faction, x%, y%, name, class, specialty, Era frame, NPC ID.",
                  "ns.worldMapServiceData = {"])
    for map_id, sites in sorted(pins.items()):
        lines.append(f"    [{map_id}] = {{")
        for row in sorted(sites, key=lambda r: (r[0], r[4], r[1], r[2], r[3], r[5] or "", r[6] or "",
                                                r[7], r[8:] or (0,))):
            lines.append("        {" + ", ".join(map(lua_value, row)) + "},")
        lines.append("    },")
    return "\n".join([*lines, "}", ""])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sendafh", type=Path, default=ROOT / ".sources/SendaFH")
    parser.add_argument("--pfquest", type=Path, default=ROOT / ".backups/map-services/pfQuest")
    parser.add_argument("--output", type=Path, default=ROOT / "RutaXP/WorldMapServiceData.lua")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    pins, frames = collect(args.sendafh / "addon", args.pfquest)
    result = render(pins, frames)
    if args.check:
        if args.output.read_text(encoding="utf-8") != result:
            raise SystemExit("Stored map services differ from pinned sources")
    else:
        args.output.write_text(result, encoding="utf-8", newline="\n")
    print(f"{sum(map(len, pins.values()))} service locations across {len(pins)} maps")


if __name__ == "__main__":
    main()
