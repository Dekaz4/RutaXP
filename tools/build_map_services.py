"""Regenerate RutaXP/MapServices.lua from two pinned source checkouts (requires lupa).

Pass --pfquest pointing to https://github.com/shagu/pfQuest at
104f35678ca39ab1fb78b655f815cc7016f5e0c8 and --sendafh pointing to
https://github.com/julen92/SendaFH at 5d207e28e82e2c529143b21ace74fe88692f0067.
Reads only the named files, verifies their contents and never accesses the network.
"""

import argparse
from collections import defaultdict
import hashlib
import gzip
import json
from pathlib import Path
import re

from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "RutaXP" / "MapServices.lua"
ROLES = ROOT / "RutaXP/Source/map_service_roles.json"
VENDOR_CATEGORIES = {"vendor", "vendor_goods", "vendor_food", "vendor_equipment", "vendor_supplies",
                     "vendor_reagents", "vendor_bags", "vendor_mounts"}
PF_FILES = {
    "db/units.lua": "b8de09aa33fd4b16edb2287b8c4224c86e6ee420e717a4d428e2935c22c4a922",
    "db/objects.lua": "be4846e2f2049cafba7da5ed18d6422bde35ed0e6f6ac34cb1215c1bbafd306e",
    "db/meta.lua": "0f6dfef398946112d8220688c29d33025aad02677b43e21e2387550d9f9e760e",
    "db/esES/units.lua": "adc10a0d356d4bd1d1318ba2131640a5125f918d48f85b7528a767ee244c1ffc",
    "db/enUS/units.lua": "f2ae827b04668c0236919f702485038a4d56330be00652d7c2970dc7e27e2922",
}
SENDA_FILES = {
    "Nav/TravelData.lua": "1e7e2503c00b52fe96fa4001dc168ffb9d3805952dea4041c25dd6eb7f3c51a8",
    "Core/ClassTrainers.lua": "4019f60ddfc12726d2ff782d639cad8ead95244696a118e82f90e4b7cbe1ec0f",
}
# pfQuest locations use Classic AreaTable IDs and map percentages, in the Era frame.
# Only include outdoor zone/city maps covered by RutaXP/MapFrames.lua.
AREA_TO_MAP = {
    1: 1426, 3: 1418, 4: 1419, 8: 1435, 10: 1431, 11: 1437, 12: 1429,
    14: 1411, 15: 1445, 16: 1447, 17: 1413, 28: 1422, 33: 1434,
    36: 1416, 38: 1432, 40: 1436, 44: 1433, 45: 1417, 46: 1428,
    47: 1425, 51: 1427, 85: 1420, 130: 1421, 139: 1423, 141: 1438,
    148: 1439, 215: 1412, 267: 1424, 331: 1440, 357: 1444, 361: 1448,
    400: 1441, 405: 1443, 406: 1442, 440: 1446, 490: 1449, 493: 1450,
    618: 1452, 1377: 1451, 1497: 1458, 1519: 1453, 1537: 1455,
    1637: 1454, 1638: 1456, 1657: 1457,
}


def checked_source(root, name, digest):
    source = (root / name).read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(source).hexdigest() != digest:
        raise ValueError(f"Unexpected revision of {root / name}")
    return source.decode("utf-8")


def role_catalog():
    evidence = json.loads(ROLES.read_text(encoding="utf-8"))
    if evidence["schemaVersion"] != 1:
        raise ValueError("Unsupported merchant role evidence")
    result = {}
    for ident, (title, source) in evidence["npcs"].items():
        translation = evidence["titles"][title]
        if source not in evidence["sources"] or translation["category"] not in VENDOR_CATEGORIES \
                or not translation["label"] or not ident.isdecimal():
            raise ValueError("Invalid merchant role: " + ident)
        result[int(ident)] = translation
    return result


def verify_roles(classic_path, forever_path):
    """Check every shipped title against pinned bytes, without executing SQL."""
    evidence = json.loads(ROLES.read_text(encoding="utf-8"))
    for name, path in (("classic", classic_path), ("forever", forever_path)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence["sources"][name]["sha256"]:
            raise ValueError("Unexpected merchant source: " + name)
    titles = {}
    fields = re.compile(r"(?:VALUES \(|\),\()(\d+),'(?:[^'\\]|\\.)*',(NULL|'(?:[^'\\]|\\.)*'),")
    with gzip.open(classic_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("INSERT INTO `creature_template` VALUES "):
                for match in fields.finditer(line):
                    if match[2] != "NULL":
                        titles[match[1]] = match[2][1:-1].replace("\\'", "'")
    live = json.loads(forever_path.read_bytes())["creatures"]
    for ident, (title, source) in evidence["npcs"].items():
        expected = live.get(ident, {}).get("title") if source == "forever" else titles.get(ident)
        if title != expected:
            raise ValueError("Merchant title does not match its source: " + ident)


def service_catalog(pfquest, sendafh):
    merchant_roles = role_catalog()
    lua = LuaRuntime()
    lua.execute("""pfDB = {units = {}, objects = {}}
        ns = {RegisterMapFrames = function() end,
              RegisterClassTrainers = function(t) trainers = t end,
              RegisterClassTrainerIds = function() end,
              Nav = {RegisterTravelData = function(t) inns = t.inns end,
                     RegisterCrossings = function() end}}
    """)
    for name, digest in PF_FILES.items():
        lua.execute(checked_source(pfquest, name, digest))
    for name, digest in SENDA_FILES.items():
        lua.execute(checked_source(sendafh / "addon/SendaFH", name, digest), "SendaFH", lua.globals().ns)
    db = lua.globals().pfDB
    catalog = defaultdict(set)
    assigned = set()
    overrides = {}
    for inn in lua.globals().inns.values():
        overrides[inn.npc, inn.map] = (inn.x, inn.y, inn.f or "l")
    snapshot = json.loads((ROOT / "RutaXP/Source/leveling.json").read_text(encoding="utf-8"))
    for guide in snapshot["guides"]:
        for step in guide["steps"]:
            for goal in step["goals"]:
                if (goal["t"] in {"buy", "vendor", "getfp", "sethome"}
                        and goal.get("npc") and goal.get("f") != "e"
                        and goal.get("x") is not None and goal.get("y") is not None):
                    overrides[goal["npc"], goal["map"]] = (goal["x"], goal["y"], "l")
    for trainer in lua.globals().trainers.values():
        for player_class in trainer.classes.values():
            name = db.units.esES[trainer.npc] or trainer.npcName
            catalog[trainer.map].add(("trainer", trainer.faction, trainer.x, trainer.y,
                                      name, trainer.f or "l", player_class, "", trainer.npc))
        assigned.add(trainer.npc)

    # A merchant who repairs gear gets the anvil, a merchant who keeps an inn gets
    # the inn icon, etc. Do not place a second generic vendor icon on top.
    roles = [("banker", "bank"), ("auctioneer", "auction"), ("flight", "flight"),
             ("innkeeper", "inn"), ("mailbox", "mailbox"), ("repair", "repair"), ("vendor", "vendor")]
    for role, category in roles:
        for ident, side in db.meta[role].items():
            if ident in assigned or side not in ("A", "H", "AH"):
                continue
            is_mail = category == "mailbox"
            record = db.objects.data[-ident] if is_mail else db.units.data[ident]
            if not record:
                continue
            locations = defaultdict(set)
            for point in record.coords.values():
                map_id = AREA_TO_MAP.get(point[3])
                if map_id and 0 < point[1] < 100 and 0 < point[2] < 100:
                    locations[map_id].add((point[1], point[2]))
            if not is_mail:
                english = db.units.enUS[ident] or ""
                if english.startswith(("TEST ", "[UNUSED]", "Programmer ")):
                    continue
            name = "Buzón" if is_mail else db.units.esES[ident] or db.units.enUS[ident]
            merchant = merchant_roles.get(ident) if category in {"vendor", "repair"} else None
            point_category = merchant["category"] if category == "vendor" and merchant else category
            detail = merchant["label"] if merchant else ""
            for map_id, coords in locations.items():
                if not is_mail and len(coords) > 1 and (ident, map_id) not in overrides:
                    continue  # A roaming NPC has no single reliable position on this map.
                for x, y in coords:
                    x, y, frame = overrides.get((ident, map_id), (x, y, "e"))
                    catalog[map_id].add((point_category, side, x, y, name, frame, False, detail,
                                        0 if is_mail else ident))
            assigned.add(ident)
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pfquest", type=Path, default=ROOT / ".sources/pfQuest")
    parser.add_argument("--sendafh", type=Path, default=ROOT / ".sources/SendaFH")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verify-roles", action="store_true", help="Verify role facts against pinned cached sources")
    parser.add_argument("--classic-db", type=Path, default=ROOT / ".backups/requirements-audit/early-classic-template.sql.gz")
    parser.add_argument("--forever-creatures", type=Path, default=ROOT / ".backups/map-services/creature_details.enUS.json")
    args = parser.parse_args()
    if args.verify_roles:
        verify_roles(args.classic_db, args.forever_creatures)
    catalog = service_catalog(args.pfquest, args.sendafh)
    lines = []
    for map_id, sites in sorted(catalog.items()):
        lines.append(f"    [{map_id}] = {{")
        for site in sorted(sites):
            fields = ", ".join(json.dumps(v, ensure_ascii=False) for v in site)
            lines.append(f"        {{{fields}}},")
        lines.append("    },")
    current = TARGET.read_text(encoding="utf-8")
    start, rest = current.split("-- BEGIN GENERATED SERVICES\n")
    _, end = rest.split("-- END GENERATED SERVICES\n")
    updated = start + "-- BEGIN GENERATED SERVICES\n" + "\n".join(lines) + "\n-- END GENERATED SERVICES\n" + end
    if args.check and updated != current:
        raise SystemExit("MapServices.lua does not match the pinned sources")
    if not args.check:
        TARGET.write_text(updated, encoding="utf-8", newline="\n")
    print(f"{sum(map(len, catalog.values()))} service locations on {len(catalog)} maps")


if __name__ == "__main__":
    main()
