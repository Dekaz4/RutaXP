#!/usr/bin/env python3
"""Compare all authored quest acceptances with pinned availability evidence.

This audit never edits a guide. Positive source requirements and source
omissions are different findings: missing upstream data is not permission to
remove a prerequisite. The stored report is reproducible without networking.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP/Source"
SECTIONS = {"gates", "pre", "preAll", "parent", "skill", "minRep", "maxRep", "maxLevel", "excl", "chain"}
CLASS_BITS = {"WARRIOR": 1, "PALADIN": 2, "HUNTER": 4, "ROGUE": 8, "PRIEST": 16,
              "SHAMAN": 64, "MAGE": 128, "WARLOCK": 256, "DRUID": 1024}
RACE_BITS = {"Human": 1, "Orc": 2, "Dwarf": 4, "NightElf": 8, "Scourge": 16,
             "Tauren": 32, "Gnome": 64, "Troll": 128}
FACTION_RACES = {"Alliance": {"Human", "Dwarf", "Gnome", "NightElf"},
                 "Horde": {"Orc", "Tauren", "Scourge", "Troll"}}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse_eq(text):
    """Read numeric facts only; never execute downloaded Lua."""
    result, section = {}, None
    for line_number, line in enumerate(text.splitlines(), 1):
        header = re.fullmatch(r"(\w+) = \{", line)
        if header:
            section = header[1]
            if section in SECTIONS:
                result[section] = {}
            continue
        match = re.fullmatch(r"\s*\[(\d+)\]=(-?\d+|\{[-\d,]*\}),", line)
        if match and section in SECTIONS:
            value = match[2]
            fact = [int(v) for v in value[1:-1].split(",") if v] if value.startswith("{") else int(value)
            result[section][int(match[1])] = (fact, line_number)
    if not result.get("gates"):
        raise ValueError("The evidence file has no recognized availability records")
    return result


def lua_structure(text):
    """Mask comments/strings, preserving offsets; inspect data without running Lua."""
    pattern = r"--\[(=*)\[[\s\S]*?\]\1\]|--[^\n]*|\[(=*)\[[\s\S]*?\]\2\]|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'"
    return re.sub(pattern, lambda m: re.sub(r"[^\n]", " ", m[0]), text)


def att_quest_facts(text, qid):
    """Read only a quest's own fields, excluding nested quests/objectives."""
    masked = lua_structure(text)
    result = []
    for match in re.finditer(r"\bq\s*\(\s*" + str(qid) + r"\s*,\s*\{", masked):
        start, depth, end = match.end(), 1, None
        positions = {}
        for i in range(start, len(masked)):
            positions[i] = depth
            if masked[i] == "{":
                depth += 1
            elif masked[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is None:
            raise ValueError(f"Unclosed ATT quest record: {qid}")
        block = masked[start:end]
        parents, breadcrumb = [], False
        for field in re.finditer(r"\b(sourceQuest|sourceQuests|isBreadcrumb)\s*=\s*", block):
            if positions[start + field.start()] != 1:
                continue
            rest = block[field.end():]
            if field[1] == "isBreadcrumb":
                breadcrumb |= bool(re.match(r"true\b", rest))
            elif field[1] == "sourceQuest":
                value = re.match(r"(-?\d+)\s*(?:[,}]|$)", rest)
                if not value:
                    raise ValueError(f"Unsupported ATT sourceQuest expression: {qid}")
                parents.append(int(value[1]))
            else:
                value = re.match(r"\{([\s\d,-]*)\}", rest)
                if not value:
                    raise ValueError(f"Unsupported ATT sourceQuests expression: {qid}")
                parents.extend(int(v) for v in re.findall(r"-?\d+", value[1]))
        result.append({"sourceQuestIDs": sorted(set(parents)), "declaresBreadcrumb": breadcrumb,
                       "line": text[:match.start()].count("\n") + 1})
    return result


def capture_att_reviews(records, sources, directory, manifest):
    """Cross-check selected records, never infer completed gates from nested data."""
    facts = defaultdict(list)
    repo, commit = manifest["repository"], manifest["commit"]
    for relative, descriptor in manifest["files"].items():
        raw = (directory / relative).read_bytes()
        if sha(raw) != descriptor["sha256"]:
            raise ValueError(f"Pinned ATT source hash changed: {relative}")
        path = manifest["sourceRoot"] + relative
        key = next((k for k, v in sources.items() if v["repository"] == repo and v["file"] == path),
                   "att-" + re.sub(r"[^a-z0-9]+", "-", relative.lower()).strip("-"))
        sources[key] = {"repository": repo, "commit": commit, "file": path,
            "url": f"https://github.com/{repo}/blob/{commit}/{quote(path)}", "sha256": sha(raw),
            "license": "MIT", "licenseUrl": f"https://github.com/{repo}/blob/{commit}/LICENSE",
            "scope": "Reviewed prerequisite IDs and breadcrumb flags only; absence is not a confirmed lack of requirements."}
        text = raw.decode("utf-8-sig")
        for qid in descriptor["questIDs"]:
            extracted = att_quest_facts(text, qid)
            if not extracted:
                raise ValueError(f"Reviewed ATT record disappeared: {qid} in {relative}")
            facts[qid].extend(dict(fact, source=key) for fact in extracted)
    for qid in manifest["reviewQuestIDs"]:
        if str(qid) not in records:
            continue
        record, seen = records[str(qid)], facts[qid]
        expected = prerequisites(record)
        parent_ids = sorted(set(abs(v) for v in expected["all"] + expected["any"]))
        parents = [{"questID": parent, "records": facts[parent]} for parent in parent_ids]
        if record.get("parent"):
            status = "active_parent_not_explicit_in_att"
        elif not seen:
            status = "no_att_record_in_reviewed_sources"
        elif any(r["declaresBreadcrumb"] for r in seen):
            status = "child_breadcrumb"
        elif any(r["declaresBreadcrumb"] for p in parents for r in p["records"]):
            status = "parent_breadcrumb"
        elif any(not p["records"] for p in parents):
            status = "parent_not_reviewed"
        elif len(expected["all"]) != 1 or expected["any"] or expected["all"][0] <= 0:
            status = "non_singleton_requires_manual_review"
        elif any(r["sourceQuestIDs"] != expected["all"] for r in seen):
            status = "prerequisite_not_corroborated"
        else:
            status = "corroborated_single_completed_parent"
            field = "pre" if record.get("pre") == expected["all"] else "preAll"
            for fact in seen:
                reference = {"source": fact["source"], "line": fact["line"]}
                if reference not in record["fieldSources"].setdefault(field, []):
                    record["fieldSources"][field].append(reference)
        record["crossSourceReview"] = {"status": status, "records": seen, "parents": parents}


def capture(eq_path, metadata, quest_ids, att_path=None, att_metadata=None, att_directory=None, att_review=None):
    raw = eq_path.read_bytes()
    parsed = parse_eq(raw.decode("utf-8-sig"))
    url = f"https://github.com/{metadata['repo']}/blob/{metadata['commit']}/{quote(metadata['path'])}"
    sources = {"everythingquests": {"repository": metadata["repo"], "commit": metadata["commit"],
        "file": metadata["path"], "url": url, "sha256": sha(raw), "license": "MIT",
        "licenseUrl": f"https://github.com/{metadata['repo']}/blob/{metadata['commit']}/LICENSE",
        "scope": "Numeric availability facts for quest IDs present in RutaXP; no source code or quest text copied."}}
    records = {}
    for qid in sorted(quest_ids):
        record = {"reportedFields": [], "fieldSources": {}}
        if qid in parsed["gates"]:
            packed, line = parsed["gates"][qid]
            fields = {"minLevel": packed // 10**11, "classMask": packed % 10**4,
                      "raceMask": (packed // 10**4) % 10**4}
            for field, value in fields.items():
                record[field] = value
                record["reportedFields"].append(field)
                record["fieldSources"][field] = [{"source": "everythingquests", "line": line}]
        for field in sorted(SECTIONS - {"gates"}):
            if qid not in parsed.get(field, {}):
                continue
            value, line = parsed[field][qid]
            if field == "skill":
                value = {"id": value // 10000, "rank": value % 10000}
            elif field in {"minRep", "maxRep"}:
                value = {"factionID": value // 10**6, "standing": value % 10**6}
            record[field] = value
            record["reportedFields"].append(field)
            record["fieldSources"][field] = [{"source": "everythingquests", "line": line}]
        records[str(qid)] = record
    if att_path is not None:
        if att_metadata is None:
            raise ValueError("ATT evidence needs its pinned metadata")
        att_raw = att_path.read_bytes()
        att_text = att_raw.decode("utf-8-sig")
        source_url = f"https://github.com/{att_metadata['repo']}/blob/{att_metadata['commit']}/{quote(att_metadata['path'])}"
        sources["att-westfall"] = {"repository": att_metadata["repo"], "commit": att_metadata["commit"],
            "file": att_metadata["path"], "url": source_url, "sha256": sha(att_raw), "license": "MIT",
            "licenseUrl": f"https://github.com/{att_metadata['repo']}/blob/{att_metadata['commit']}/LICENSE",
            "scope": "Reviewed Engineering 1/2 and 2/2 quest facts, not a general ATT parser."}
        for qid, expected in ((92910, {"qs": "255155", "requireSkill": "ENGINEERING", "lvl": "8"}),
                              (92911, {"sourceQuest": "92910", "requireSkill": "ENGINEERING", "lvl": "8"})):
            if qid not in quest_ids:
                continue
            start = re.search(r"\bq\(" + str(qid) + r", \{", att_text)
            if not start:
                raise ValueError(f"ATT evidence lost quest {qid}")
            following = re.search(r"\bq\(\d+, \{", att_text[start.end():])
            block = att_text[start.end(): start.end() + following.start()] if following else att_text[start.end():]
            facts = {"skill": {"id": 202, "rank": 1}, "minLevel": 8}
            if qid == 92910:
                facts["startItem"] = 255155
            else:
                facts["preAll"] = [92910]
            for key, value in expected.items():
                if not re.search(r"\b" + key + r"\s*=\s*" + value + r"\s*,", block):
                    raise ValueError(f"ATT reviewed fact changed: {qid} {key}")
            record = records[str(qid)]
            for field, value in facts.items():
                if field in record and record[field] != value:
                    raise ValueError(f"Conflicting positive sources: {qid} {field}")
                record[field] = value
                if field not in record["reportedFields"]:
                    record["reportedFields"].append(field)
                record["fieldSources"].setdefault(field, []).append({"source": "att-westfall",
                    "line": att_text[:start.start()].count("\n") + 1})
    if att_directory is not None:
        manifest = att_review or json.loads((SOURCE / "quest_requirements_att_review.json").read_text(encoding="utf-8"))
        if att_metadata is not None and manifest["commit"] != att_metadata["commit"]:
            raise ValueError("ATT review manifest and profession evidence use different commits")
        capture_att_reviews(records, sources, att_directory, manifest)
    return {"schemaVersion": 1, "sources": sources, "quests": records,
            "limits": ["Source omissions do not prove that a quest has no gate.",
                       "ATT coverage is a reviewed subset; no captured evidence does not mean that no record exists elsewhere in ATT.",
                       "Availability comes from community-maintained addon data, not a query of the live server.",
                       "A published prerequisite must be reviewed with route ordering and variant/class context before editing a guide.",
                       "Only known Classic class/race bits are compared; Skyborne eligibility needs separate review."]}


def prerequisites(goal):
    """Normalize equivalent single-item OR/AND without erasing active parents."""
    all_ids, any_ids = set(goal.get("preAll") or []), set(goal.get("pre") or [])
    if goal.get("parent"):
        all_ids.add(-goal["parent"])
    if len(any_ids) == 1:
        all_ids |= any_ids
        any_ids.clear()
    if all_ids & any_ids:
        any_ids.clear()
    return {"all": sorted(all_ids), "any": sorted(any_ids)}


def token(value):
    return re.sub(r"[\s_-]", "", value).lower().replace("undead", "scourge")


def select(values, universe):
    if not values:
        return set(universe)
    positive = {token(v) for v in values if not v.startswith("!")}
    negative = {token(v[1:]) for v in values if v.startswith("!")}
    return {v for v in universe if (not positive or token(v) in positive) and token(v) not in negative}


def personas(guide, step, goal, field, universe):
    selected = select(guide.get(field), universe)
    for only in (guide.get("only"), step.get("only"), goal.get("only")):
        selected &= select((only or {}).get(field), universe)
    if field == "races" and guide.get("faction") in FACTION_RACES:
        selected &= FACTION_RACES[guide["faction"]]
    return selected


def audit(document, evidence):
    records = evidence["quests"]
    quests, known = set(), set()
    findings, guide_rows = [], []
    for guide in document["guides"]:
        count = 0
        locations = defaultdict(list)
        for si, step in enumerate(guide["steps"], 1):
            for gi, goal in enumerate(step["goals"], 1):
                if goal.get("quest"):
                    locations[goal["quest"]].append({"step": si, "goal": gi, "action": goal["t"]})
        for si, step in enumerate(guide["steps"], 1):
            for gi, goal in enumerate(step["goals"], 1):
                if goal.get("t") != "accept" or not goal.get("quest"):
                    continue
                count += 1
                qid = goal["quest"]
                quests.add(qid)
                source = records.get(str(qid), {})
                base = {"guideID": guide["id"], "step": si, "goal": gi, "questID": qid,
                        "title": goal.get("title", str(qid))}
                if source.get("crossSourceReview"):
                    base["crossSourceReview"] = source["crossSourceReview"]["status"]
                def add(kind, field, actual=None, expected=None, **extra):
                    findings.append(dict(base, kind=kind, field=field, authored=actual, reported=expected,
                                         evidence=source.get("fieldSources", {}).get(field, []), **extra))
                if not source.get("reportedFields"):
                    add("no_source_data", "availability")
                    continue
                known.add(qid)
                actual, expected = prerequisites(goal), prerequisites(source)
                if actual != expected:
                    positive = bool(expected["all"] or expected["any"])
                    has_authored = bool(actual["all"] or actual["any"])
                    kind = "source_omission_review" if not positive else (
                        "missing_prerequisite" if not has_authored else "prerequisite_conflict_review")
                    refs = source.get("fieldSources", {}).get("pre", []) + source.get("fieldSources", {}).get("preAll", [])
                    add(kind, "prerequisites", actual, expected,
                        dependencyLocations={str(v): locations.get(abs(v), []) for v in expected["all"] + expected["any"]})
                    findings[-1]["evidence"] = refs
                if source.get("parent"):
                    parent = source["parent"]
                    # Negative authored prerequisites mean active, not delivered.
                    if -parent not in (goal.get("pre") or []) + (goal.get("preAll") or []) and goal.get("parent") != parent:
                        add("missing_active_parent", "parent", goal.get("parent"), parent)
                if source.get("skill"):
                    expected_skill = source["skill"]
                    actual_skill = {"id": goal.get("profLine"), "rank": goal.get("profRank", 0)}
                    if actual_skill["id"] != expected_skill["id"] or actual_skill["rank"] < expected_skill["rank"]:
                        add("missing_profession_requirement", "skill", actual_skill, expected_skill)
                if source.get("startItem") and goal.get("item") != source["startItem"]:
                    add("missing_start_item", "startItem", goal.get("item"), source["startItem"])
                if source.get("minLevel", 0) > 1 and max(1, goal.get("minLevel") or 1) != source["minLevel"]:
                    add("level_conflict_review", "minLevel", goal.get("minLevel"), source["minLevel"])
                for field in ("maxLevel", "minRep", "maxRep"):
                    if source.get(field) is not None and goal.get(field) != source[field]:
                        add("additional_gate_review", field, goal.get(field), source[field])
                for field, mask_field, bits in (("classes", "classMask", CLASS_BITS), ("races", "raceMask", RACE_BITS)):
                    mask = source.get(mask_field)
                    if not mask:
                        continue
                    allowed = {name for name, bit in bits.items() if mask & bit}
                    authored = personas(guide, step, goal, field, bits)
                    excluded = sorted(authored - allowed)
                    if excluded:
                        add("selector_conflict_review", mask_field, sorted(authored), sorted(allowed), excluded=excluded)
        guide_rows.append({"guideID": guide["id"], "acceptances": count})
    counts = dict(sorted(Counter(f["kind"] for f in findings).items()))
    for row in guide_rows:
        row["findings"] = dict(sorted(Counter(f["kind"] for f in findings if f["guideID"] == row["guideID"]).items()))
    return {"schemaVersion": 1, "scope": {"guides": len(document["guides"]), "questIDs": len(quests),
                "acceptances": sum(row["acceptances"] for row in guide_rows),
                "withReportedEvidence": len(known), "withoutReportedEvidence": len(quests - known)},
            "sourceCommits": {key: value["commit"] for key, value in evidence["sources"].items()},
            "crossSourceReviewCounts": dict(sorted(Counter(record["crossSourceReview"]["status"]
                for qid, record in records.items() if int(qid) in quests and record.get("crossSourceReview")).items())),
            "counts": counts, "byGuide": guide_rows, "findings": findings,
            "limits": evidence.get("limits", []) + [
                "Findings are review candidates, not proof that every difference is a route defect.",
                "Local dependency locations are diagnostic; this audit does not assume a previous zone was completed.",
                "No runtime quest completion, profession or player's progress is modified by this audit."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=SOURCE / "leveling.json")
    parser.add_argument("--evidence", type=Path, default=SOURCE / "quest_requirements_evidence.json")
    parser.add_argument("--output", type=Path, default=SOURCE / "quest_requirements_audit.json")
    parser.add_argument("--capture-eq", type=Path)
    parser.add_argument("--eq-meta", type=Path)
    parser.add_argument("--att-westfall", type=Path)
    parser.add_argument("--att-meta", type=Path)
    parser.add_argument("--att-dir", type=Path, help="ATT forever source root matching quest_requirements_att_review.json (25 pinned files)")
    parser.add_argument("--att-review", type=Path, default=SOURCE / "quest_requirements_att_review.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document = json.loads(args.input.read_text(encoding="utf-8-sig"))
    if args.capture_eq:
        if args.check or not args.eq_meta:
            parser.error("Capture needs --eq-meta and cannot be combined with --check")
        ids = {goal["quest"] for guide in document["guides"] for step in guide["steps"] for goal in step["goals"] if goal.get("quest")}
        evidence = capture(args.capture_eq, json.loads(args.eq_meta.read_text()), ids, args.att_westfall,
                           json.loads(args.att_meta.read_text()) if args.att_meta else None, args.att_dir,
                           json.loads(args.att_review.read_text(encoding="utf-8")) if args.att_dir else None)
        args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = audit(document, evidence)
    result["inputSha256"] = sha(args.input.read_bytes())
    result["evidenceSha256"] = sha(args.evidence.read_bytes())
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != encoded:
            raise SystemExit("Quest requirement report is stale; rerun tools/audit_quest_requirements.py")
    else:
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(json.dumps({"scope": result["scope"], "counts": result["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
