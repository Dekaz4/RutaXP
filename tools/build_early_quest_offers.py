"""Review every NPC pickup in leveling.json. Use --report for chapter totals and reasons.

The route and the NPC's live offer establish an ordinary pickup. Exceptions are
things that actually happen on acceptance (or a repeatable/exclusive choice).
--verify-sources rechecks the pinned Forever client caches and Classic templates.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "RutaXP/EarlyQuestData.lua"
EVIDENCE = ROOT / "RutaXP/Source/early_quest_timing.json"
DB_COMMIT = "c33f90b8eeb3f8bacb53d5cbfee45075c80b416c"
DB_URL = f"https://raw.githubusercontent.com/cmangos/classic-db/{DB_COMMIT}/Full_DB/ClassicDB_1_12_1_z2815.sql.gz"
DB_SHA = "4f92db520868ab4e566726f68b5b2e380ae781209beaf22237b4f7f04600d0c0"
CACHES = {
    "1.60.1.70790": ("45f58b070b84501f8001bdcad43864aa929a6a4b", "1d338604744f0100ec58ea14c904f1b1c676b826d832bc747c90eae27b569bc7"),
    "1.60.1.70840": ("45f58b070b84501f8001bdcad43864aa929a6a4b", "1a8e5263510de3d9ec98f99dfda56653b1bbe30a77f97268740b28ac466016fd"),
    "1.60.1.70862": ("156f29c9af78b1586883e8eb94a13467eb89638c", "0f8b890bbedc79f6c80b99511a88ff5f699048f4a34303bd6d0a0281cfde4b7a"),
}

# Ordered by the most useful explanation when multiple sources flag a quest.
REASONS = {
    "escort": "Empieza una escolta.",
    "timer": "Tiene un límite de tiempo.",
    "perishable": "El objeto de misión caduca.",
    "transport": "Inicia un traslado.",
    "event": "Inicia una escena o un encuentro.",
    "spell": "Al aceptarla se lanza un hechizo.",
    "pvp": "Es una misión JcJ.",
    "survival": "Falla si mueres.",
    "repeatable": "Es una entrega repetible.",
}
# Authored instructions and quest objectives identify starts without a timer,
# even when the client only records quest credit as a kill or an empty event.
# Introductions to an escort (e.g. #979) do not acquire the escort's restriction.
REVIEWED_STARTS = {
    "escort": {
        219, 435, 648, 660, 665, 731, 836, 863, 898, 945, 994, 1222, 1270, 1273,
        1393, 1440, 1560, 2742, 2767, 2845, 3367, 4261, 4491, 4770, 4901, 4904,
        5203, 5321, 5821, 5943, 6132, 6482, 6544, 6641, 87491, 98430,
        99053, 99123, 99144,
    },
    "event": {590, 1090, 1173, 1249, 1324, 1447, 1640, 1719, 2460, 2480, 2608,
              3377, 3441, 3702, 4321, 4966, 92595, 92679, 92708, 92709, 97257},
    "transport": {1149},
    "timer": {98252},  # Va'xug's eye must reach the road during its four-minute channel.
    "perishable": {95805, 97891},
}
# These start scripts give an item, speak or emote on a normal delivery or
# collection; the player can leave immediately. For all other start scripts
# the route keeps the interaction at the intended step.
PORTABLE_SCRIPTS = {54, 96, 114, 753, 804, 947, 993, 1363, 1364, 3449}


def raw_source(directory, name, url, expected):
    path = directory / name
    if path.exists():
        data = path.read_bytes()
    else:
        with urlopen(url, timeout=30) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"Source checksum mismatch for {name}")
    if not path.exists():
        directory.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data


def sql_rows(compressed, name):
    # Use only numeric template columns. Remove quoted SQL fields before
    # splitting rows so punctuation inside localized dialogue is harmless.
    marker = "INSERT INTO `" + name + "` VALUES "
    quoted = re.compile(r"'(?:[^'\\]|\\.)*'")
    with gzip.open(io.BytesIO(compressed), "rt", encoding="utf8") as stream:
        for line in stream:
            if line.startswith("CREATE TABLE `" + name + "`"):
                break
        else:
            raise ValueError(f"Missing SQL table {name}")
        columns = []
        for line in stream:
            if line.startswith("  `"):
                columns.append(line.split("`")[1])
            elif line.startswith(")"):
                break
        for line in stream:
            if line.startswith("UNLOCK TABLES"):
                return
            if line.startswith(marker):
                numeric = quoted.sub("NULL", line[len(marker):]).strip()
                for values in numeric[1:-2].split("),("):
                    yield dict(zip(columns, values.split(","), strict=True))


def pickups(guide):
    return [goal for step in guide["steps"] for goal in step["goals"] if goal["t"] == "accept"]


def npc_quests(guides):
    return {goal["quest"] for guide in guides for goal in pickups(guide) if goal.get("npc")}


def live_reasons(row):
    flags = row.get("flags", 0)
    if row.get("timeLimitSeconds", 0):
        yield "timer"
    if row.get("questInfoId") == 84:
        yield "escort"
    if row.get("questInfoId") == 41 or flags & 0x2000:
        yield "pvp"
    if flags & 1:
        yield "survival"
    if flags & (0x1000 | 0x8000):
        yield "repeatable"


def classic_reasons(qid, row, perishable):
    if int(row["LimitTime"]):
        yield "timer"
    if int(row["SrcItemId"]) in perishable:
        yield "perishable"
    if int(row["Type"]) == 84:
        yield "escort"
    if int(row["Type"]) == 41 or int(row["QuestFlags"]) & 0x2000:
        yield "pvp"
    if int(row["QuestFlags"]) & 1:
        yield "survival"
    if int(row["SpecialFlags"]) & 1 or int(row["QuestFlags"]) & 0x8000:
        yield "repeatable"
    if int(row["StartScript"]) and qid not in PORTABLE_SCRIPTS:
        yield "event"
    # 19027 teaches the druid teleport for later use. Receiving this spell
    # doesn't send the character to Moonglade on acceptance.
    if int(row["SrcSpell"]) not in (0, 19027):
        yield "spell"


def source_evidence(ids, cache):
    """Distil flags by source. The shipped audit can then run fully offline."""
    sql = raw_source(cache, "early-classic-template.sql.gz", DB_URL, DB_SHA)
    perishable = {int(r["entry"]) for r in sql_rows(sql, "item_template") if int(r["Duration"])}
    groups = defaultdict(list)
    evidence = {}
    classic = defaultdict(list)
    for row in sql_rows(sql, "quest_template"):
        qid = int(row["entry"])
        group = int(row["ExclusiveGroup"])
        if group > 0:
            groups[group].append(qid)
        if qid not in ids:
            continue
        for reason in classic_reasons(qid, row, perishable):
            classic[reason].append(qid)
    evidence["ClassicDB"] = {reason: sorted(values) for reason, values in sorted(classic.items())}
    for build, (commit, digest) in CACHES.items():
        url = f"https://raw.githubusercontent.com/JIVESCORP/eg-link-output-wowf/{commit}/data/wowf/{build}/quests.enUS.json"
        live = json.loads(raw_source(cache, f"early-offers-{build}.json", url, digest))["quests"]
        facts = defaultdict(list)
        for qid in ids:
            if str(qid) in live:
                for reason in live_reasons(live[str(qid)]):
                    facts[reason].append(qid)
        evidence[build] = {reason: sorted(values) for reason, values in sorted(facts.items())}
    return {
        "sources": evidence,
        "positiveExclusiveGroups": sorted(sorted(items) for items in groups.values() if len(items) > 1 and ids.intersection(items)),
        "npcQuestIDsSha256": hashlib.sha256(",".join(map(str, sorted(ids))).encode()).hexdigest(),
    }


def classify(guides, facts):
    ids = npc_quests(guides)
    deferred = {}
    recorded = list(facts["sources"].values()) + [REVIEWED_STARTS]
    for reason in REASONS:
        for source in recorded:
            for qid in source.get(reason, ()):
                if qid in ids:
                    deferred.setdefault(qid, reason)
    # closedBy is directional: accepting B can close an earlier A that
    # declares closedBy=[B]. Preserve that direction across chapter boundaries.
    # Include object/item branches as possible victims of an NPC acceptance.
    alternatives = defaultdict(set)
    planned_ids = set()
    for guide in guides:
        for row in pickups(guide):
            qid = row["quest"]
            planned_ids.add(qid)
            for blocker in row.get("closedBy", ()):
                if blocker in ids and blocker != qid:
                    alternatives[blocker].add(qid)
    for group in facts["positiveExclusiveGroups"]:
        planned_group = planned_ids.intersection(group)
        if len(planned_group) > 1:
            for qid in planned_group:
                alternatives[qid].update(planned_group - {qid})
    return ids - deferred.keys(), deferred, alternatives


def render(eligible, deferred, alternatives):
    lines = [
        "-- Generated by tools/build_early_quest_offers.py from the 57 routes and pinned timing facts.",
        "-- Sources: Efficient Games (CC BY 4.0), CMaNGOS Classic-DB (GPL-3.0), Polestar/SendaFH.",
        "local _, ns = ...", "ns.earlyQuestOffers = {",
    ]
    lines.extend(f"    [{q}] = true," for q in sorted(eligible))
    lines += ["}", "ns.deferredQuestOffers = {"]
    lines.extend(f'    [{q}] = "{REASONS[reason]}",' for q, reason in sorted(deferred.items()))
    lines += ["}", "ns.earlyQuestAlternatives = {"]
    for q, victims in sorted(alternatives.items()):
        if q in eligible:
            lines.append("    [%d] = {%s}," % (q, ", ".join(map(str, sorted(victims)))))
    return "\n".join(lines + ["}", ""])


def report(guides, eligible, deferred):
    print("Guía | Misiones de NPC | Anticipables | En su paso | Solo de objeto o elemento del mundo")
    for guide in guides:
        rows = pickups(guide)
        ids = {r["quest"] for r in rows if r.get("npc")}
        other = {r["quest"] for r in rows} - ids
        print(f"{guide['id']} | {len(ids)} | {len(ids & eligible)} | {len(ids & deferred.keys())} | {len(other)}")
    for reason, count in Counter(deferred.values()).most_common():
        print(f"{REASONS[reason]} {count}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check shipped Lua without downloading any data")
    parser.add_argument("--verify-sources", action="store_true", help="Repeat the pinned external data audit")
    parser.add_argument("--refresh-sources", action="store_true", help="Rebuild the offline timing evidence from the pinned sources")
    parser.add_argument("--report", action="store_true", help="Show pickup coverage per guide and reasons for deferral")
    parser.add_argument("--cache", type=Path, default=ROOT / ".backups/requirements-audit")
    args = parser.parse_args()
    guides = json.loads((ROOT / "RutaXP/Source/leveling.json").read_bytes())["guides"]
    ids = npc_quests(guides)
    if args.refresh_sources:
        fetched = source_evidence(ids, args.cache)
        EVIDENCE.write_text(json.dumps(fetched, indent=2) + "\n", encoding="utf8", newline="\n")
    facts = json.loads(EVIDENCE.read_bytes())
    if args.verify_sources and source_evidence(ids, args.cache) != facts:
        raise SystemExit("Timing evidence differs from the pinned sources; review and refresh with --refresh-sources")
    signature = hashlib.sha256(",".join(map(str, sorted(ids))).encode()).hexdigest()
    if signature != facts["npcQuestIDsSha256"]:
        raise SystemExit("New guide pickups require a source review; use --refresh-sources")
    eligible, deferred, alternatives = classify(guides, facts)
    text = render(eligible, deferred, alternatives)
    if args.check:
        if OUTPUT.read_text(encoding="utf8") != text:
            raise SystemExit("Early quest catalogue is stale")
    else:
        OUTPUT.write_text(text, encoding="utf8", newline="\n")
    print(f"Reviewed {len(guides)} guides, {len(ids)} NPC quests: {len(eligible)} early offers, {len(deferred)} kept at their step.")
    if args.report:
        report(guides, eligible, deferred)


if __name__ == "__main__":
    main()
