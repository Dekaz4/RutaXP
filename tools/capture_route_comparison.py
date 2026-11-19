"""Capture numeric quest references from two specific published Forever itineraries.

Run with clean local checkouts at the revisions below. Store file hashes, quest
IDs, milestones and line references only. The comparison report works offline.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tools/route_comparison_facts.json"
SOURCES = (
    ("MacQuest", "Methodologist/MacQuest", "42b87f9c8de2a83120a455b5b2c63c9df1334d20"),
    ("OpenXP", "mjared123/OpenXP", "b3f094095ceca7a5eee1d64b2851c861cf25ecf1"),
)
SIDES = ("Alliance", "Horde")
KINDS = {"A": "A", "C": "O", "T": "E", "accept": "A", "complete": "O", "turnin": "E"}


def mac_rows(lines, side):
    entry = section = None
    for n, line in enumerate(lines, 1):
        if line.startswith("{title="):
            section = n
            found = re.search(r"\bentry=(\d+)", line)
            entry = int(found[1]) if found else None
        found = re.match(r'\s*\{t="([ACT])",q=(\d+)[,}]', line)
        if found:
            yield side, int(found[2]), KINDS[found[1]], n, entry, section


def allowed_side(condition, side):
    if "<<" not in condition:
        return True
    expression = condition.split("<<", 1)[1].split("--", 1)[0]
    def allowed(branch):
        tokens = set(re.findall(r"!?[A-Za-z]+", branch))
        other = "Horde" if side == "Alliance" else "Alliance"
        return "!" + side not in tokens and other not in tokens
    return any(allowed(branch) for branch in expression.split("/"))


def open_rows(lines, sides):
    section = None
    entry, step, guide_scope, in_guide = None, "", "", False
    for n, line in enumerate(lines, 1):
        line = line.strip()
        if "RegisterGuide([[" in line and not line.startswith("--"):
            entry, step, guide_scope, in_guide = None, "", "", True
            section = n
        if line.startswith("]])"):
            in_guide = False
        if not in_guide:
            continue
        if line.startswith("#name "):
            level = re.search(r"#name\s+(\d+)\s*[-–]", line)
            entry = int(level[1]) if level else None
        elif line.startswith("<<"):
            guide_scope = line
        elif re.match(r"^step\b", line):
            step = line
        else:
            match = re.match(r"\.(accept|complete|turnin)\s+(-?\d+)\b", line)
            if match:
                for side in sides:
                    if all(allowed_side(text, side) for text in (guide_scope, step, line)):
                        yield side, abs(int(match[2])), KINDS[match[1]], n, entry, section


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def capture(roots, document):
    needed = {side: {q["quest"] for g in document["guides"] if g["faction"] == side
                     for s in g["steps"] for q in s["goals"] if q.get("quest")} for side in SIDES}
    files, facts = [], defaultdict(dict)
    for source, root in enumerate(roots):
        commit = SOURCES[source][2]
        paths = git(root, "ls-tree", "-r", "--name-only", commit).decode().splitlines()
        for path in paths:
            name = Path(path).name
            if source == 0:
                match = re.fullmatch(r"SpeedLevel/Data/Route_(Horde|Alliance)_safe\.lua", path)
                if not match:
                    continue
                sides = (match[1],)
            else:
                if not path.startswith(("Guides/forever/", "Guides/openxp/")) or not name.endswith(".lua"):
                    continue
                sides = tuple(side for side in SIDES if name.startswith(side + "-"))
                if name == "RestedXP-Skyborne.lua":
                    sides = SIDES
                if not sides:
                    continue
            raw = git(root, "show", f"{commit}:{path}")
            lines = raw.decode("utf-8-sig").splitlines()
            file_id = len(files)
            files.append([source, path, hashlib.sha256(raw).hexdigest()])
            rows = mac_rows(lines, sides[0]) if source == 0 else open_rows(lines, sides)
            for side, quest, action, line, level, section in rows:
                if quest in needed[side]:
                    # One independently inspectable example per action and source.
                    facts[side, quest, source].setdefault(action, [file_id, line, level, section])
    return {"sources": SOURCES, "files": files,
            "rows": [[side, quest, source, actions] for (side, quest, source), actions in sorted(facts.items())]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("macquest", type=Path)
    parser.add_argument("openxp", type=Path)
    args = parser.parse_args()
    document = json.loads((ROOT / "RutaXP/Source/leveling.json").read_bytes())
    facts = capture((args.macquest, args.openxp), document)
    OUTPUT.write_text(json.dumps(facts, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    print(f"{len(facts['rows'])} comparisons with quest actions in {len(facts['files'])} files")


if __name__ == "__main__":
    main()
