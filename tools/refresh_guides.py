#!/usr/bin/env python3
"""Refresh reviewed navigation, Spanish instructions and the catalog audit.

Uses only the standard library and the shipped, pinned evidence overlays.
Does not read or modify a WoW installation, character data or quest progress.
"""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path

try:
    from .audit_guides import audit
    from .guide_instructions import enrich_document
except ImportError:  # Direct CLI execution from the packaged tools directory.
    from audit_guides import audit
    from guide_instructions import enrich_document

ROOT = Path(__file__).resolve().parents[1]


def refresh(source: Path) -> tuple[dict, dict]:
    spec = importlib.util.spec_from_file_location("rutaxp_snapshot_builder", source / "build_guides.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    document = json.loads((source / "leveling.json").read_text(encoding="utf-8"))
    builder.apply_guide_overrides(document, source / "guide_overrides.json")
    builder.apply_guide_revisions(document, source / "guide_revisions.json")
    builder.apply_guide_locations(document, source / "guide_locations.json")
    document = enrich_document(document)
    document["statistics"]["goalFields"] = dict(sorted(Counter(key for guide in document["guides"]
        for step in guide["steps"] for goal in step["goals"] for key in goal).items()))
    locations_path = source / "guide_locations.json"
    locations = json.loads(locations_path.read_text(encoding="utf-8")) if locations_path.is_file() else None
    return document, audit(document, locations=locations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "RutaXP/Source")
    parser.add_argument("--check", action="store_true", help="Verify without writing")
    args = parser.parse_args()
    document, report = refresh(args.source)
    render = lambda value: json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    snapshot = args.source / "leveling.json"
    report_path = args.source / "guide_audit.json"
    if args.check:
        if json.loads(snapshot.read_text(encoding="utf-8")) != document or not report_path.is_file() or json.loads(report_path.read_text(encoding="utf-8")) != report:
            raise SystemExit("Guide instructions, navigation or audit need refreshing")
    else:
        snapshot.write_text(render(document), encoding="utf-8", newline="\n")
        report_path.write_text(render(report), encoding="utf-8", newline="\n")
        spec = importlib.util.spec_from_file_location("rutaxp_snapshot_builder", args.source / "build_guides.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        builder.build(snapshot, args.source.parent)
    print(json.dumps(report["totals"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
