#!/usr/bin/env python3
"""Rebuild only Waypoints.lua's Catalog from the editable audited snapshot.

    python tools/build_waypoints.py
    python tools/build_waypoints.py --check

The navigation implementation surrounding the single generated line is kept
byte-for-byte. Uses the bundled stdlib Lua serializer also used for guides.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def render(snapshot: Path, target: Path) -> bytes:
    doc = json.loads(snapshot.read_text(encoding="utf-8"))
    routes = doc.get("routes")
    if doc.get("schema") != 1 or not isinstance(routes, list) or not routes:
        raise ValueError("Unsupported or empty waypoint snapshot")
    seen = set()
    for route in routes:
        route_id = route.get("id")
        if not isinstance(route_id, str) or not route_id or route_id in seen:
            raise ValueError("Invalid/duplicate route ID")
        seen.add(route_id)
        match = route.get("match", {})
        if route.get("kind") == "cave" and not (match.get("quests") or match.get("npcs") or match.get("guide")):
            raise ValueError(f"Cave access requires an objective-specific match: {route_id}")
        provenance = route.get("provenance", {})
        if provenance.get("commit") != doc.get("commit") or doc["commit"] not in provenance.get("url", ""):
            raise ValueError(f"Unpinned provenance: {route_id}")
        if not route.get("points"):
            raise ValueError(f"No authored points: {route_id}")
        for point in route["points"]:
            if not isinstance(point.get("map"), int) or point["map"] <= 0:
                raise ValueError(f"Invalid point map: {route_id}")
            if any(not isinstance(point.get(k), (int, float)) or not 0 <= point[k] <= 100 for k in ("x", "y")):
                raise ValueError(f"Invalid source percentages: {route_id}")
    spec = importlib.util.spec_from_file_location("rutaxp_lua_serializer", ROOT / "RutaXP/Source/build_guides.py")
    if spec is None or spec.loader is None:
        raise ValueError("The bundled Lua serializer is unavailable")
    serializer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(serializer)
    text = target.read_bytes().decode("utf-8")  # Preserve the implementation's line endings.
    pattern = re.compile(r"^local Catalog = [^\r\n]*", re.MULTILINE)
    if len(pattern.findall(text)) != 1:
        raise ValueError("Expected one generated Catalog line")
    generated = "local Catalog = " + serializer.lua_value(doc, compact=True)
    return pattern.sub(lambda _: generated, text, count=1).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "RutaXP/Source/waypoints.json")
    parser.add_argument("--target", type=Path, default=ROOT / "RutaXP/Waypoints.lua")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = render(args.snapshot, args.target)
    if args.check:
        if args.target.read_bytes() != data:
            raise ValueError("Waypoints Catalog differs from Source/waypoints.json")
        print("Verified waypoint Catalog; navigation implementation preserved")
    else:
        args.target.write_bytes(data)
        print("Rebuilt waypoint Catalog; navigation implementation preserved")


if __name__ == "__main__":
    main()
