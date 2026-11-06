#!/usr/bin/env python3
"""Build the bundled Lua data from editable leveling.json; Python stdlib only.

From the addon workspace:
    python RutaXP/Source/build_guides.py

Edit leveling.json for route or translation corrections, then rebuild. The
snapshot preserves upstream goal fields, grouping, conditions and coordinate
frames. It does not require the upstream compiler or its private reference DB.
Numeric JSON object keys represent numeric Lua table keys (map/quest IDs).
Pinned navigation corrections in guide_overrides.json are reapplied by the
initial import tool, so a deliberate reimport preserves their source evidence.
"""

from __future__ import annotations

import argparse
import copy
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def lua_string(value: str) -> str:
    """Quote UTF-8 text for Lua 5.1, including literal control characters."""
    out = ['"']
    for char in value:
        code = ord(char)
        if char == "\\":
            out.append("\\\\")
        elif char == '"':
            out.append('\\"')
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif code < 32 or code == 127:
            out.append(f"\\{code:03d}")
        else:
            out.append(char)
    out.append('"')
    return "".join(out)


def lua_key(key: Any) -> str:
    if isinstance(key, int) or (isinstance(key, str) and key.isdecimal()):
        return f"[{int(key)}]"
    # Always bracket string keys: 'until' and other Lua keywords stay valid.
    return f"[{lua_string(str(key))}]"


def lua_value(value: Any, indent: int = 0, compact: bool = False) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return lua_string(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Lua data must not contain non-finite numbers")
        return repr(value)
    if not isinstance(value, (list, dict)):
        raise TypeError(f"Cannot emit {type(value).__name__} to Lua")
    if not value:
        return "{}"
    # Each goal occupies one line, keeping a large guide readable without
    # producing thousands of lines for its spawn clusters and candidates.
    if compact:
        if isinstance(value, list):
            parts = [lua_value(item, compact=True) for item in value]
        else:
            parts = [f"{lua_key(key)} = {lua_value(item, compact=True)}" for key, item in value.items()]
        return "{ " + ", ".join(parts) + " }"
    pad, child = "\t" * indent, "\t" * (indent + 1)
    if isinstance(value, list):
        lines = [child + lua_value(item, indent + 1, compact=isinstance(item, dict) and "t" in item) + "," for item in value]
    else:
        lines = [child + lua_key(key) + " = " + lua_value(item, indent + 1) + "," for key, item in value.items()]
    return "{\n" + "\n".join(lines) + "\n" + pad + "}"


def apply_guide_overrides(document: dict[str, Any], path: Path) -> list[str]:
    """Reapply audited navigation hints on import without changing quest logic.

    A correction must match exactly one goal and donor in the stated step.
    NPC/coordinate data is copied from that donor, never supplied speculatively.
    The normal builder still emits the editable snapshot exactly as saved.
    """
    if not path.is_file():
        return []
    payload = path.read_bytes()
    overlay = json.loads(payload)
    source = document["provenance"]
    if overlay.get("schemaVersion") != 1 or overlay.get("sourceCommit") != source["commit"]:
        raise ValueError("Guide corrections do not match the pinned source")
    applied = []
    allowed = {"npc", "npcName", "map", "x", "y", "z", "f"}
    for patch in overlay.get("overrides", []):
        guides = [g for g in document["guides"] if g["id"] == patch["guideID"]]
        if len(guides) != 1:
            raise ValueError(f"Correction guide must match exactly once: {patch['id']}")
        step_index = patch["step"]
        if not isinstance(step_index, int) or not 1 <= step_index <= len(guides[0]["steps"]):
            raise ValueError(f"Invalid correction step: {patch['id']}")
        goals = guides[0]["steps"][step_index - 1]["goals"]

        def match(selector: dict[str, Any]) -> dict[str, Any]:
            hits = [g for g in goals if all(g.get(k) == v for k, v in selector.items())]
            if len(hits) != 1:
                raise ValueError(f"Correction goal must match exactly once: {patch['id']}")
            return hits[0]

        goal, donor = match(patch["match"]), match(patch["copyFrom"])
        evidence = patch["provenance"]
        if source["inputSha256"].get(evidence["compiledFile"]) != evidence["compiledSha256"]:
            raise ValueError(f"Correction evidence does not match source: {patch['id']}")
        fields = patch["copyFields"]
        if not fields or any(key not in allowed or key not in donor for key in fields):
            raise ValueError(f"Invalid correction navigation fields: {patch['id']}")
        if set(patch.get("set", {})) - {"note"}:
            raise ValueError(f"Corrections cannot change quest semantics: {patch['id']}")
        goal.update({key: donor[key] for key in fields})
        goal.update(patch.get("set", {}))
        applied.append(patch["id"])
    source["localOverrides"] = {
        "file": "Source/guide_overrides.json", "sha256": hashlib.sha256(payload).hexdigest(), "applied": applied,
    }
    fields = Counter(key for guide in document["guides"] for step in guide["steps"] for goal in step["goals"] for key in goal)
    document["statistics"]["goalFields"] = dict(sorted(fields.items()))
    return applied


ROUTE_FIELDS = ("t", "quest", "oi", "item", "count", "pre", "preAll", "closedBy", "only", "optional",
                "minLevel", "maxLevel", "level", "n", "class", "group", "order",
                "profLine", "profRank", "profName", "requiresSkill")


def route_shape(guide: dict[str, Any]) -> str:
    """Fingerprint quest semantics, independently of translated text/navigation."""
    shape = [{"only": step.get("only"), "goals": [
        {key: goal[key] for key in ROUTE_FIELDS if key in goal} for goal in step["goals"]
    ]} for step in guide["steps"]]
    return hashlib.sha256(json.dumps(shape, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def revision_progress(revision: dict[str, Any]) -> dict[str, Any] | None:
    """Derive character progress maps from the exact reviewed source references."""
    counts = revision.get("previousGoalCounts")
    if counts is None:  # Westfall revision 1 -> 2 retains its existing runtime migration.
        return None
    if not counts or any(not isinstance(count, int) or count < 1 for count in counts):
        raise ValueError("Invalid previous goal counts: " + revision["id"])
    entries = revision.get("steps")
    if revision.get("preserveSteps"):
        if entries is not None:
            raise ValueError("Revision cannot preserve and reorder steps together: " + revision["id"])
        entries = [{"sourceStep": index} for index in range(1, len(counts) + 1)]
    mapping, steps = {}, {}
    for si, entry in enumerate(entries or [], 1):
        old_step = entry.get("sourceStep")
        if old_step is not None:
            if not 1 <= old_step <= len(counts):
                raise ValueError("Invalid migration source step: " + revision["id"])
            refs = [[old_step, gi] for gi in range(1, counts[old_step - 1] + 1)
                    if gi not in entry.get("omitGoals", [])]
        else:
            refs = entry["goals"]
        for gi, (old_si, old_gi) in enumerate(refs, 1):
            key = f"{old_si}:{old_gi}"
            if key in mapping or not 1 <= old_si <= len(counts) or not 1 <= old_gi <= counts[old_si - 1]:
                raise ValueError("Invalid migration goal reference: " + revision["id"])
            mapping[key] = f"{si}:{gi}"
            steps[str(old_si)] = min(si, steps.get(str(old_si), si))
    expected = {f"{si}:{gi}" for si, count in enumerate(counts, 1) for gi in range(1, count + 1)}
    if set(mapping) != expected:
        raise ValueError("Migration must retain every source goal: " + revision["id"])
    changed = {old: new for old, new in mapping.items() if old != new}
    steps[str(len(counts) + 1)] = len(entries) + 1
    return {"from": revision["previousRevision"], "to": revision["revision"],
            "goalMap": changed, "stepMap": steps,
            "affectedQuestIDs": sorted(set(revision.get("affectedQuestIDs", []))),
            "previousStepCount": len(counts),
            "firstAffectedStep": min((int(key.split(":")[0]) for key in changed), default=len(counts) + 1)}


def current_goal_key(guide: dict[str, Any], step: int, goal: int) -> tuple[int, int]:
    """Translate original navigation-evidence keys through reviewed route moves."""
    key = f"{step}:{goal}"
    for migration in guide.get("progressMigrations", []):
        key = migration.get("goalMap", {}).get(key, key)
    return tuple(int(value) for value in key.split(":"))


def apply_guide_revisions(document: dict[str, Any], path: Path) -> list[str]:
    """Apply reviewed quest-order corrections, preserving every authored goal.

    Each revision has exact before/after semantic fingerprints and explicit
    evidence. It is deliberately separate from the navigation-only overlays.
    """
    if not path.is_file():
        return []
    payload = path.read_bytes()
    overlay = json.loads(payload)
    if overlay.get("schemaVersion") != 1 or overlay.get("sourceCommit") != document["provenance"]["commit"]:
        raise ValueError("Guide revisions do not match the pinned source")
    applied = []
    by_guide_revision = {}
    for entry in overlay.get("revisions", []):
        key = (entry["guideID"], entry["revision"])
        if key in by_guide_revision:
            raise ValueError("Duplicate guide revision: " + entry["id"])
        by_guide_revision[key] = entry
    for revision in overlay.get("revisions", []):
        matches = [guide for guide in document["guides"] if guide["id"] == revision["guideID"]]
        if len(matches) != 1 or not revision.get("evidence"):
            raise ValueError("Revision needs one guide and evidence: " + revision["id"])
        guide = matches[0]
        current_revision = guide.get("routeRevision", 1)
        if current_revision > revision["revision"]:
            # A rebuilt snapshot may already include several reviewed changes.
            # Only a known, fingerprint-checked successor can supersede one.
            current = by_guide_revision.get((guide["id"], current_revision))
            if not current or route_shape(guide) != current["resultShape"]:
                raise ValueError("Revised guide semantics changed: " + revision["id"])
            ancestor = current
            while ancestor["revision"] > revision["revision"]:
                ancestor = by_guide_revision.get((guide["id"], ancestor["previousRevision"]))
                if not ancestor:
                    raise ValueError("Missing guide revision ancestor: " + revision["id"])
            if ancestor["id"] != revision["id"]:
                raise ValueError("Guide revision is not an ancestor: " + revision["id"])
            applied.append(revision["id"])
            continue
        if guide.get("routeRevision", 1) == revision["revision"]:
            if route_shape(guide) != revision["resultShape"]:
                raise ValueError("Revised guide semantics changed: " + revision["id"])
            applied.append(revision["id"])
            continue
        if guide.get("routeRevision", 1) != revision["previousRevision"] or route_shape(guide) != revision["sourceShape"]:
            raise ValueError("Revision source semantics changed: " + revision["id"])
        original = guide["steps"]
        if revision.get("previousGoalCounts") is not None and revision["previousGoalCounts"] != [len(s["goals"]) for s in original]:
            raise ValueError("Migration source goal counts changed: " + revision["id"])
        revised, used = [], []
        entries = revision.get("steps")
        if revision.get("preserveSteps"):
            if entries is not None:
                raise ValueError("Revision cannot preserve and reorder steps together: " + revision["id"])
            entries = [{"sourceStep": index} for index in range(1, len(original) + 1)]
        for entry in entries or []:
            if "sourceStep" in entry:
                source_index = entry["sourceStep"]
                step = copy.deepcopy(original[source_index - 1])
                refs = [[source_index, index] for index in range(1, len(step["goals"]) + 1)
                        if index not in entry.get("omitGoals", [])]
                step["goals"] = [copy.deepcopy(original[si - 1]["goals"][gi - 1]) for si, gi in refs]
                step.update(copy.deepcopy(entry.get("set", {})))
            else:
                refs = entry["goals"]
                step = {key: copy.deepcopy(value) for key, value in entry.items() if key != "goals"}
                step["goals"] = [copy.deepcopy(original[si - 1]["goals"][gi - 1]) for si, gi in refs]
            if not step["goals"]:
                raise ValueError("Revision produces an empty step: " + revision["id"])
            used.extend(tuple(ref) for ref in refs)
            revised.append(step)
        expected = [(si, gi) for si, step in enumerate(original, 1) for gi in range(1, len(step["goals"]) + 1)]
        if sorted(used) != expected:
            raise ValueError("Revision must retain every goal exactly once: " + revision["id"])
        for patch in revision.get("goalChanges", []):
            goals = [goal for step in revised for goal in step["goals"]
                     if all(goal.get(key) == value for key, value in patch["match"].items())]
            if len(goals) != patch["count"]:
                raise ValueError("Revision goal selector changed: " + revision["id"])
            for goal in goals:
                for key in patch.get("unset", []):
                    if key not in ROUTE_FIELDS or key not in goal:
                        raise ValueError("Revision cannot remove an unexpected field: " + revision["id"])
                    del goal[key]
                goal.update(copy.deepcopy(patch["set"]))
        for step in revised:
            for key in ("title", "note", "text"):
                if isinstance(step.get(key), str):
                    for old, new in revision.get("textReplacements", {}).items():
                        step[key] = step[key].replace(old, new)
            for goal in step["goals"]:
                for key in ("npcName", "note", "text"):
                    if isinstance(goal.get(key), str):
                        for old, new in revision.get("textReplacements", {}).items():
                            goal[key] = goal[key].replace(old, new)
        candidate = dict(guide, steps=revised)
        if route_shape(candidate) != revision["resultShape"]:
            raise ValueError("Revision result does not match reviewed semantics: " + revision["id"])
        guide["steps"], guide["routeRevision"] = revised, revision["revision"]
        applied.append(revision["id"])
    for guide in document["guides"]:
        migrations = [revision_progress(revision) for revision in overlay.get("revisions", [])
                      if revision["guideID"] == guide["id"] and revision["revision"] <= guide.get("routeRevision", 1)]
        migrations = [entry for entry in migrations if entry is not None]
        if migrations:
            guide["progressMigrations"] = migrations
    document["provenance"]["routeRevisions"] = {
        "file": "Source/guide_revisions.json", "sha256": hashlib.sha256(payload).hexdigest(), "applied": applied,
    }
    document["statistics"]["steps"] = sum(len(guide["steps"]) for guide in document["guides"])
    return applied


def apply_guide_locations(document: dict[str, Any], path: Path) -> list[str]:
    """Apply pinned, additive navigation evidence without changing quest logic."""
    if not path.is_file():
        return []
    payload = path.read_bytes()
    overlay = json.loads(payload)
    provenance = document["provenance"]
    if overlay.get("schemaVersion") != 1 or overlay.get("sourceCommit") != provenance["commit"]:
        raise ValueError("Guide locations do not match the pinned source")
    compiled = "addon/SendaFH_Guides/Guides.lua"
    if overlay.get("sourceFiles", {}).get(compiled) != provenance["inputSha256"].get(compiled):
        raise ValueError("Guide locations do not match the compiled guides")
    guides = {guide["id"]: guide for guide in document["guides"]}
    applied, seen = [], set()
    for patch in overlay.get("patches", []):
        identity = patch["id"]
        if identity in seen:
            raise ValueError("Duplicate location correction: " + identity)
        seen.add(identity)
        guide = guides.get(patch["guideID"])
        si, gi = patch["step"], patch["goal"]
        if guide:
            si, gi = current_goal_key(guide, si, gi)
        if not guide or not isinstance(si, int) or not 1 <= si <= len(guide["steps"]):
            raise ValueError("Invalid location guide/step: " + identity)
        goals = guide["steps"][si - 1]["goals"]
        if not isinstance(gi, int) or not 1 <= gi <= len(goals):
            raise ValueError("Invalid location goal: " + identity)
        goal = goals[gi - 1]
        if not patch.get("match") or any(goal.get(key) != value for key, value in patch["match"].items()):
            raise ValueError("Location correction target changed: " + identity)
        fields = patch["set"]
        if not fields or set(fields) - {"candidates", "navigationHint", "navigationMode"}:
            raise ValueError("Locations cannot change quest semantics: " + identity)
        if "navigationMode" in fields and fields["navigationMode"] not in ("inventory", "ability", "escort"):
            raise ValueError("Invalid action navigation mode: " + identity)
        for candidate in fields.get("candidates", []):
            if not isinstance(candidate, dict) or not all(isinstance(candidate.get(key), (int, float))
                    and not isinstance(candidate[key], bool) and math.isfinite(candidate[key]) for key in ("map", "x", "y")):
                raise ValueError("Invalid location coordinates: " + identity)
            if candidate["map"] <= 0 or candidate["map"] != int(candidate["map"]) or not all(0 <= candidate[key] <= 100 for key in ("x", "y")):
                raise ValueError("Location coordinates out of bounds: " + identity)
            if candidate.get("f") not in ("e", "l"):
                raise ValueError("Location requires an explicit coordinate frame: " + identity)
        if not patch.get("evidence"):
            raise ValueError("Location correction needs evidence: " + identity)
        for key, value in fields.items():
            if key in goal and goal[key] != value:
                raise ValueError("Location correction would replace authored data: " + identity)
            goal[key] = value
        applied.append(identity)
    provenance["navigationCoverage"] = {
        "file": "Source/guide_locations.json", "sha256": hashlib.sha256(payload).hexdigest(),
        "sourceFiles": overlay["sourceFiles"], "applied": applied,
    }
    fields = Counter(key for guide in document["guides"] for step in guide["steps"] for goal in step["goals"] for key in goal)
    document["statistics"]["goalFields"] = dict(sorted(fields.items()))
    return applied


def build(snapshot_path: Path, addon_path: Path) -> dict[str, int]:
    document = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if document.get("schemaVersion") != 1:
        raise ValueError("Unsupported leveling snapshot schema")
    guides = document["guides"]
    if not isinstance(guides, list) or not guides:
        raise ValueError("The snapshot must contain a non-empty guides array")
    ids = [guide["id"] for guide in guides]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate guide ID")
    for guide in guides:
        if not guide.get("steps") or guide.get("category") != "Leveling":
            raise ValueError(f"Invalid leveling guide: {guide.get('id')}")
        for step in guide["steps"]:
            if not isinstance(step.get("goals"), list) or not step["goals"]:
                raise ValueError(f"A step has no goals: {guide['id']}")

    addon_path.mkdir(parents=True, exist_ok=True)
    source = document["provenance"]
    header = (
        "-- Generated from Source/leveling.json by Source/build_guides.py.\n"
        "-- Edit the JSON snapshot and rebuild; preserve all goal semantics.\n"
        "-- Adapted from Polestar / SendaFH under GPL-3.0-only.\n"
        f"-- Source commit: {source['commit']}\n"
        "-- Copyright and data notices: Licenses/.\n"
        "local _, ns = ...\n\n"
    )
    output = [header]
    ordered_guides = sorted(
        guides,
        key=lambda g: (
            g.get("faction", ""),
            g.get("minLevel", 0),
            g.get("maxLevel", 0),
            0 if g.get("races") else 1,
            g["id"],
        ),
    )
    for guide in ordered_guides:
        # Separate functions preserve Lua 5.1's per-function constant budget.
        output.append(f"-- {guide['id']}\ndo\n\tlocal function register()\n\t\tns:RegisterGuide(")
        output.append(lua_value(guide, 2))
        output.append(")\n\tend\n\tregister()\nend\n\n")
    (addon_path / "Leveling.lua").write_text("".join(output), encoding="utf-8", newline="\n")
    frames = header + "-- Era coordinate frames. A goal's f='e' must be converted at runtime.\n"
    frames += "ns.mapFrames = " + lua_value(document["mapFrames"]) + "\n"
    (addon_path / "MapFrames.lua").write_text(frames, encoding="utf-8", newline="\n")
    return {
        "guides": len(guides),
        "steps": sum(len(guide["steps"]) for guide in guides),
        "goals": sum(len(step["goals"]) for guide in guides for step in guide["steps"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("leveling.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
