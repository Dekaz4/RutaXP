"""Build the offline early-accept allowlist. Use --verify-sources to repeat the source review.

Efficient Games (https://efficient.games) publishes server quest-cache facts under CC BY 4.0.
CMaNGOS Classic-DB (GPL-3.0) provides independent script, spell and objective fields.
Only quest IDs and eligibility decisions are redistributed, not quest dialogue or SQL.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "RutaXP/EarlyQuestData.lua"
EG_COMMIT = "45f58b070b84501f8001bdcad43864aa929a6a4b"
DB_COMMIT = "c33f90b8eeb3f8bacb53d5cbfee45075c80b416c"
EG_ROOT = f"https://raw.githubusercontent.com/JIVESCORP/eg-link-output-wowf/{EG_COMMIT}/data/wowf/"
DB_URL = f"https://raw.githubusercontent.com/cmangos/classic-db/{DB_COMMIT}/Full_DB/ClassicDB_1_12_1_z2815.sql.gz"
BUILDS = {
    "1.60.1.70790": "1d338604744f0100ec58ea14c904f1b1c676b826d832bc747c90eae27b569bc7",
    "1.60.1.70840": "1a8e5263510de3d9ec98f99dfda56653b1bbe30a77f97268740b28ac466016fd",
}
DB_SHA = "4f92db520868ab4e566726f68b5b2e380ae781209beaf22237b4f7f04600d0c0"

# Source-qualified signatures, grouped by the supporting live build(s) in verify_sources().
# Positive integers are monster IDs, negatives are item IDs. Empty means the individually
# reviewed Report to Gryan Stoutmantle, a direct report with no item, timer or start script.
WITNESSES = {
    "70790": """
        21:80 33:-750 47:-773 60:-772 170:707,724 182:706 183:708 376:-3265,-3264 381:-3266 404:-2855
        427:1535 432:1115 443:-3236 457:1985,2032 459:-3297 845:-5086 869:-5062 880:-5098 887:3381,3382
        907:-5143 3901:1890 3902:-11127 5481:-12737 6128:-15852,-2449
    """,
    "70790+70840": """
        7:6 15:257 18:-752 83:-1019 86:-769 112:-1256 179:-750 356:1529,1532 358:-2834,1675,1941
        364:1501,1502 365:-2846 367:-2858 368:-2859 369:-2872 374:-2875 380:1504,1505 426:-3163,-3162
        433:1117 456:1984,2031 487:2152 488:-3412,-3411,-3409 501:-3496 516:1973,1974 528:2267 546:-3692
        549:2260,2261 788:3098 789:-4862 791:-4870 792:3101 815:-4890 817:-4892 818:-4888,-4887 825:-4863
        835:3117,3118 837:3111,3112,3113,3114 844:-5087 848:-5012 855:-5030 865:-5055 867:-5064
        871:3265,3267,3268 875:-5065 878:3260,3261,3263 899:-5085 916:-5166 918:-5168 919:-5169 937:-5204
        1087:4051,4053,4057 4402:-11583 5482:-13702 6282:4022,4023,4024,4025 6393:-16312 6442:-5490
        6462:-16602
    """,
    "70840": """
        9:114 11:-782 12:95,504 13:589,590 38:-732,-731,-730,-729 46:-780 57:202,531 58:604 82:-8587
        91:-1075 92:-2296,-1081,-1080 101:-2378,-1130,-1129 109: 127:-1467 133:-884 150:-1468 151:-1528
        153:-829 156:-1598 185:681 186:682 189:-1519 191:736 192:684 195:686 222:206,920 226:213,565
        246:423,424 261:11561 276:1007,1008 277:-2611 294:1020,1021 295:1022,1023 319:1127,1196,1201
        323:785,787,1110 489:-3418 500:-2843 505:2240,2241 536:2376,2377 559:-3716 562:2369,2371
        564:2406,2407 568:686 569:1142,1144 572:-3863 575:-4053 581:-3901 587:-3910 589:-3911 598:-3916
        600:-3917 601:-3923 605:-3918 606:-3919 627:-4278 642:-4435 664:2595,2596 671:-4495
        677:2554,2555,2556 681:2586,2589 698:-6169 699:-6168 710:-4626 711:-4627 827:-4871 834:-4918
        846:-5019,-5018,-5017 951:-5273 955:-5336 958:-5360 966:-5348 983:-5385 986:-5386 1002:-5413
        1003:-5414 1010:-5437 1071:3989,3991 1104:-5794 1105:-5795 1110:-5798 1138:-12237 1169:-5841,-5840
        1175:4147,4150,4151 1176:-5848 1204:-5883 1396:767,858,1084 1419:-6166 1426:747,750,751
        1459:-6249,-6248 1466:-6252,-6251,-6250 1707:-8483 2138:2164 2500:-7848,-7847,-7846 2821:-8973
        2862:-9237 2869:-9247 2877:2655,2656 2970:7725,7726,7727 2974:-9460 2975:5229,5232,5237
        2980:5234,5236,5240 2982:5232,5236,5240 3442:-10511,-10509 4101:-11503
        4284:-11188,-11186,-11185,-11184 4289:-11480,-11479,-11478 4502:-11829 4503:-11831,-11830
        4504:-11834 4767:-12356 4841:4093,4094,4096 5092:1783,1791 5501:-13703 6123:-15851,-2449 6142:-15924
        6143:4711,4712,4714 6301:-16205 6441:-5481 6503:12856 7723:5854 7724:5858 7727:9318 7729:5844,5846
        8460:7153,7154,7155
    """,
}


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


def classic_signatures(data):
    # Read only numeric fields of quest_template. Erase quoted fields before splitting
    # mysqldump tuples so dialogue containing commas/parentheses cannot shift columns.
    marker = "INSERT INTO `quest_template` VALUES "
    quoted = re.compile(r"'(?:[^'\\]|\\.)*'")
    results = {}
    with gzip.open(io.BytesIO(data), "rt", encoding="utf8") as stream:
        for line in stream:
            if line.startswith("CREATE TABLE `quest_template`"):
                break
        columns = []
        for line in stream:
            if line.startswith("  `"):
                columns.append(line.split("`")[1])
            elif line.startswith(")"):
                break
        for line in stream:
            if line.startswith("UNLOCK TABLES"):
                break
            if not line.startswith(marker):
                continue
            numeric = quoted.sub("NULL", line[len(marker):]).strip()
            for fields in numeric[1:-2].split("),("):
                row = dict(zip(columns, fields.split(","), strict=True))
                if row["Method"] != "2" or row["QuestFlags"] not in ("0", "8"):
                    continue
                gates = ("Type", "SpecialFlags", "StartScript", "LimitTime", "SrcItemId", "SrcSpell",
                         "SuggestedPlayers", "ExclusiveGroup", "RequiredSkill", "RequiredCondition")
                if any(row[key] != "0" for key in gates) or any(row[f"ReqSpellCast{i}"] != "0" for i in range(1, 5)):
                    continue
                signature = {}
                for i in range(1, 5):
                    monster, item = int(row[f"ReqCreatureOrGOId{i}"]), int(row[f"ReqItemId{i}"])
                    if monster < 0:  # game object activation in the classic template
                        break
                    if monster:
                        signature[monster] = int(row[f"ReqCreatureOrGOCount{i}"])
                    if item:
                        signature[-item] = int(row[f"ReqItemCount{i}"])
                else:
                    results[int(row["entry"])] = signature
    return results


def live_signature(row):
    # Normal (2), no flags or SHAREABLE (8) only. Reject unknown bits and categories.
    if row.get("questType") != 2 or row.get("flags") not in (0, 8):
        return None
    if any(row.get(k) for k in ("timeLimitSeconds", "flagsEx", "flagsEx2", "startItemId",
                                "questInfoId", "conditionalDescriptions", "areaDescription", "treasurePickerIds")):
        return None
    signature = {}
    for objective in row.get("objectives", []):
        kind, obj = objective.get("type"), objective.get("objectId")
        if kind not in ("item", "monster") or not isinstance(obj, int) or obj <= 0:
            return None
        count = objective.get("amount")
        if not isinstance(count, int) or count < 2:
            return None
        signature[obj if kind == "monster" else -obj] = count
    return signature


def authored_signatures(guides):
    """Require normal accept/work/turn-in rows and repeatable open-world targets."""
    rows = {}
    for guide in guides:
        for step in guide["steps"]:
            for q in step["goals"]:
                if q.get("quest"):
                    rows.setdefault(q["quest"], []).append(q)
    results = {}
    for qid, goals in rows.items():
        actions = {g["t"] for g in goals}
        if not {"accept", "turnin"} <= actions <= {"accept", "turnin", "collect", "kill"}:
            continue
        if any(g.get(key) for g in goals for key in ("group", "profLine", "closedBy", "fromFaction", "fromRank", "rank", "optional")):
            continue
        signature = set()
        for g in goals:
            if g["t"] in ("accept", "turnin"):
                continue
            target = g.get("npc") if g["t"] == "kill" else g.get("item")
            if not target or g.get("count", 2) < 2 or g.get("fromKind") not in (None, "npc", "object"):
                break
            if len([p for p in g.get("spots", []) if not p.get("alt")]) < 2:
                break
            signature.add(target if g["t"] == "kill" else -target)
        else:
            if signature or (qid == 109 and all(q.get("npc") == 234 for q in goals if q["t"] == "turnin")):
                results[qid] = tuple(sorted(signature))
    return results


def verify_sources(authored, cache):
    classic = classic_signatures(raw_source(cache, "early-classic-template.sql.gz", DB_URL, DB_SHA))
    live = {}
    for build, sha in BUILDS.items():
        data = raw_source(cache, f"early-offers-{build}.json", EG_ROOT + build + "/quests.enUS.json", sha)
        live[build] = json.loads(data)["quests"]
    eligible = {}
    for qid, targets in authored.items():
        builds = [b for b, quests in live.items() if str(qid) in quests]
        if qid not in classic or not builds or tuple(sorted(classic[qid])) != targets:
            continue
        if qid == 109 and any(not live[b][str(qid)].get("objectivesText", "").startswith("Talk to Gryan Stoutmantle.")
                              for b in builds):
            continue
        if all(live_signature(live[b][str(qid)]) == classic[qid] for b in builds):
            eligible[qid] = (tuple(b.rsplit(".", 1)[1] for b in builds), targets)
    return eligible


def snapshot():
    rows = {}
    for builds, group in WITNESSES.items():
        for entry in group.split():
            qid, targets = entry.split(":")
            rows[int(qid)] = (tuple(builds.split("+")), tuple(map(int, targets.split(","))) if targets else ())
    return rows


def render(authored, proofs):
    rows = [qid for qid, (_, targets) in proofs.items() if authored.get(qid) == targets]
    return "\n".join([
        "-- Generated by tools/build_early_quest_offers.py. Only ordinary pre-acceptances with source evidence.",
        "-- Derived quest IDs: Efficient Games (https://efficient.games), CC BY 4.0; CMaNGOS Classic-DB, GPL-3.0.",
        "-- See NOTICE.md and tools/build_early_quest_offers.py for pinned sources, hashes and review criteria.",
        "local _, ns = ...", "ns.earlyQuestOffers = {",
        *[f"    [{qid}] = true," for qid in sorted(rows)], "}", ""])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check shipped Lua against source witnesses offline")
    parser.add_argument("--verify-sources", action="store_true", help="Fetch or reuse the pinned public datasets and repeat eligibility checks")
    parser.add_argument("--cache", type=Path, default=ROOT / ".backups/requirements-audit")
    args = parser.parse_args()
    data = json.loads((ROOT / "RutaXP/Source/leveling.json").read_bytes())
    authored = authored_signatures(data["guides"])
    proofs = snapshot()
    if args.verify_sources and verify_sources(authored, args.cache) != proofs:
        raise SystemExit("New source/guide matches differ from the reviewed witnesses. Review them before regenerating.")
    text = render(authored, proofs)
    if args.check:
        if OUTPUT.read_text(encoding="utf8") != text:
            raise SystemExit("Early quest catalogue is stale")
    else:
        OUTPUT.write_text(text, encoding="utf8", newline="\n")
    print(f"Reviewed {len(data['guides'])} guides, {text.count(' = true,')} early offers.")


if __name__ == "__main__":
    main()
