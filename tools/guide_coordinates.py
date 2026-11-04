#!/usr/bin/env python3
"""Propose sourced navigation data; never edit quest/progress semantics.

The generated overlay is reviewed/applied separately by the snapshot importer.
Reading the pinned upstream packs requires lupa. The shipped snapshot builder
does not depend on this tool, Lua, a network connection, or the upstream DB.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPILED = "addon/SendaFH_Guides/Guides.lua"
POINT_FIELDS = ("map", "x", "y", "z", "f", "r")
NO_FIXED_POINT = {"note", "level", "hearth"}


def array(value):
    return value if isinstance(value, list) else []


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def located(point, inherited=None):
    inherited = inherited or {}
    return (isinstance(point, dict) and finite(point.get("map", inherited.get("map"))) and point.get("map", inherited.get("map")) > 0
            and finite(point.get("x")) and 0 <= point["x"] <= 100
            and finite(point.get("y")) and 0 <= point["y"] <= 100)


def availability(goal):
    if located(goal):
        return "direct"
    if any(located(c) for c in array(goal.get("candidates"))):
        return "candidates"
    if any(located(s, goal) for s in array(goal.get("spots")) if not s.get("alt")):
        return "spots"
    point = goal.get("waypoint")
    if isinstance(point, dict) and finite(point.get("mapID")) and all(finite(point.get(k)) and 0 <= point[k] <= 1 for k in ("x", "y")):
        return "waypoint"
    return "none"


def iter_goals(document):
    for guide in document["guides"]:
        for si, step in enumerate(guide["steps"], 1):
            for gi, goal in enumerate(step["goals"], 1):
                yield guide, si, step, gi, goal


class PinnedReference:
    """Read original compact records with their own decoder, in isolated Lua."""

    def __init__(self, source_path: Path, document: dict[str, Any]):
        from lupa.lua51 import LuaRuntime, lua_type

        self.source = source_path.resolve()
        expected = document["provenance"]["commit"]
        actual = subprocess.check_output(["git", "-C", str(self.source), "rev-parse", "HEAD"], text=True).strip()
        if actual != expected:
            raise ValueError(f"Expected pinned source {expected}, got {actual}")
        self.files, self.entities, self.cache = {}, {}, {}
        self.travel, self.crossings = {}, {}
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua_type = lua_type
        self.ns = self.lua.table()
        self.lua.globals().SendaFH = self.ns
        for key in ("os", "io", "package", "require", "dofile", "loadfile", "debug"):
            self.lua.globals()[key] = None
        self.load_chunk = self.lua.eval("function(s,n,ns) return assert(loadstring(s,n))(n,ns) end")
        self._load("addon/SendaFH/Lookup/Codex.lua")
        original = self.ns.Codex.Register

        def register(group, names, records=None, lo=None, hi=None):
            if isinstance(names, str):
                for line in names.splitlines():
                    ident = line.split("\t", 1)[0]
                    if ident.isdecimal():
                        self.entities[group, int(ident)] = self.current_file
            return original(group, names, records, lo, hi)

        self.ns.Codex.Register = register
        for path in sorted((self.source / "addon/SendaFH_Codex").glob("*.lua")):
            if path.name not in {"Index.lua", "Dungeons1.lua"}:
                self._load(path.relative_to(self.source).as_posix())
        self.ns.Nav = self.lua.table()
        self.ns.Nav.RegisterTravelData = lambda value: self.travel.update(self._python(value))
        self.ns.Nav.RegisterCrossings = lambda value: self.crossings.update(self._python(value))
        self.ns.Nav.RegisterTimetables = lambda *args: None
        self._load("addon/SendaFH/Nav/TravelData.lua")
        self.quest_db = {}
        self.ns.QuestDB = self.lua.table()
        self.ns.QuestDB.AddData = lambda kind, records: self.quest_db.update(self._python(records)) if kind == "quests" else None
        self._load("addon/SendaFH_QuestDB/Quests.lua")
        self._record(COMPILED)
        if self.files[COMPILED] != document["provenance"]["inputSha256"][COMPILED]:
            raise ValueError("The compiled source differs from the snapshot's capture")

    def _record(self, relative):
        self.files[relative] = hashlib.sha256((self.source / relative).read_bytes()).hexdigest()

    def _load(self, relative):
        self._record(relative)
        self.current_file = relative
        self.load_chunk((self.source / relative).read_text(encoding="utf-8-sig"), relative, self.ns)

    def _python(self, value):
        if self.lua_type(value) != "table":
            return value
        pairs = list(value.items())
        if pairs and all(isinstance(k, (int, float)) and int(k) == k for k, _ in pairs) and set(k for k, _ in pairs) == set(range(1, len(pairs) + 1)):
            return [self._python(value[i]) for i in range(1, len(pairs) + 1)]
        return {str(k): self._python(v) for k, v in pairs}

    def get(self, kind, ident):
        key = kind, ident
        if key not in self.cache:
            self.cache[key] = self._python(self.ns.Codex[kind.capitalize()](ident)) or {}
        return self.cache[key]

    def with_role(self, role):
        return array(self._python(self.ns.Codex.WithRole(role)))

    def evidence(self, kind, ident):
        groups = {"npc": ("npc", "rare"), "object": ("object", "treasure"), "item": ("item", "mount", "pet", "recipe", "tabard")}.get(kind, (kind,))
        path = next((self.entities[g, ident] for g in groups if (g, ident) in self.entities), None)
        return {"sourceFile": path, "sourceSha256": self.files.get(path)}

    def event_points(self, quest_id):
        row = self.quest_db.get(str(quest_id), {})
        def field(value, index):
            return value[index - 1] if isinstance(value, list) and 1 <= index <= len(value) else value.get(str(index)) if isinstance(value, dict) else None
        events = field(row, 14) or []
        objectives = field(row, 12) or []
        size = len(objectives) if isinstance(objectives, list) else max((int(k) for k in objectives), default=0)
        found = []
        for start in range(1, size + 1, 3):
            if field(objectives, start) == 4:
                event = field(objectives, start + 1)
                if not isinstance(event, (int, float)) or event < 1:
                    continue
                offset = (event - 1) * 4
                point = {"map": field(events, offset + 1), "x": field(events, offset + 3), "y": field(events, offset + 4)}
                if field(events, offset + 2) == 0:
                    point["f"] = "e"
                if located(point):
                    found.append((1 + (start - 1) // 3, point))
        return found


def load_reference(source_path, document):
    return PinnedReference(Path(source_path), document)


def census(document):
    actions = defaultdict(Counter)
    for _, _, _, _, goal in iter_goals(document):
        actions[goal["t"]][availability(goal)] += 1
    return {"totalGoals": sum(sum(v.values()) for v in actions.values()),
            "byAction": {k: dict(sorted(v.items())) for k, v in sorted(actions.items())}}


def faction_code(value):
    return {"Alliance": "A", "Horde": "H"}.get(value, value)


def accessible(faction, guide):
    return faction in (None, "AH", faction_code(guide.get("faction")))


def source_candidate(kind, ident, point, name=None, objective_index=None):
    candidate = {k: point[k] for k in POINT_FIELDS if k in point}
    # Codex's blank frame is the live-map frame; only explicit "e" uses
    # Classic Era geometry (Lookup/Codex.lua's spawn decoder, same as Compat).
    candidate["f"] = "e" if point.get("f") == "e" else "l"
    if kind == "npc":
        candidate.update(npc=ident, npcName=name or f"NPC {ident}")
    elif kind == "object":
        candidate.update(object=ident, objName=name or f"Objeto {ident}")
    if objective_index:
        candidate["objectiveIndex"] = objective_index
    return candidate


def authored_evidence(reference, relative, line=None):
    path = reference.source / relative
    reference.files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"kind": "authored-action", "sourceFile": relative,
            "sourceSha256": reference.files[relative], **({"sourceLine": line} if line else {})}


def manual_navigation(reference, guide, goal, add, entity_points):
    """Reviewed exceptions whose location/absence needs the authored mechanic.

    These are source facts, not observed play tests. Quest identity and the
    original complete action remain unchanged, including friendly NPC credit.
    """
    qid = goal.get("quest")
    relative = f"guides/{guide['id']}.guide"
    if qid in {6001, 6002}:
        path = "guides/forever/class/druid/bear-form.guide"
        line, item, point = ((90, 15208, {"map": 1439, "x": 43.5, "y": 46.0, "f": "e"}) if qid == 6001
                              else (137, 15710, {"map": 1412, "x": 71.7, "y": 65.0, "f": "e"}))
        candidate = {**point, "objectiveIndex": 1, "navigationRole": "summon-location"}
        add(candidate, {**authored_evidence(reference, path, line), "entityType": "item", "entityID": item,
                        "objectiveIndex": 1, "authoredAction": "use"})
        return None, "Usa el polvo Cenarion junto a la Piedra de lechúcico lunar, derrota a Garraluna y habla con su espíritu; llegar al lugar no completa la misión.", []
    if qid == 96873:
        path = "guides/forever/horde/orc-troll/01-durotar.guide"
        proof = authored_evidence(reference, path, 45)
        # The guide explicitly says to disenchant Hexed Pendants. Their drops
        # are material sources, not NPCs credited as quest kills.
        for npc in (3206, 3207):
            entity_points("npc", npc, 1, "item-source", {
                "questID": qid, "objectiveIndex": 1, "itemID": 275724,
                "resultItemID": 247884, "operation": "disenchant", "operationEvidence": proof,
                "itemSourceType": "drop", "itemEvidence": reference.evidence("item", 275724)})
        return "inventory", "Desencanta los colgantes embrujados (Hexed Pendant) para obtener Luminous Residue. La marca señala una fuente de colgantes; la transformación se hace con el objeto, no al llegar.", []
    if qid == 99053:
        path = "guides/forever/alliance/nightelf/01-teldrassil.guide"
        add({"map": 1438, "x": 46.4, "y": 57.3, "f": "e", "r": 25, "objectiveIndex": 1,
             "navigationRole": "escort-exit"}, {**authored_evidence(reference, path, 317),
             "entityType": "quest", "entityID": qid, "objectiveIndex": 1, "authoredAction": "goto"})
        return None, "Acompaña a Lynessa y mantenla viva hasta salir del túmulo. La marca es la salida documentada; sigue a la escolta y no avances la misión solo por llegar.", []
    if qid in {99123, 99144}:
        npc = 275811 if qid == 99123 else 275954
        name = "Pal'juh" if qid == 99123 else "Bareth Dawnstone"
        # Retain the documented starting location for the map, but do not
        # steer a running escort back there: Navigation handles escort mode.
        entity_points("npc", npc, 1, "quest-objective", {
            "questID": qid, "objectiveIndex": 1, "relationship": "named-escort-and-starter",
            **reference.evidence("quest", qid)})
        return "escort", f"Acompaña a {name} y mantenlo a salvo hasta que el diario confirme la escolta. El punto conservado es su inicio; sigue al NPC que se mueve.", []
    if qid in {1046, 3786, 3804, 5051, 5149, 6022, 91899, 91904}:
        evidence = {**authored_evidence(reference, relative), "entityType": "quest", "entityID": qid,
                    "classification": "inventory", "scope": "fallback after located objectives"}
        hint = "Esta acción requiere comprobar o combinar objetos de las bolsas; sigue las instrucciones de la misión y revisa su requisito en el diario. No tiene un punto fijo de finalización."
        if qid == 1046:
            hint = "Reúne la Calavera de Ran Sangradientes si falta y conserva la Vara de transformación de Dartol de la cadena anterior. La marca solo señala la fuente de la calavera; después comprueba ambos objetos en las bolsas."
        return "inventory", hint, [evidence]
    if qid == 92474:
        return "ability", "Usa Caminata en el aire (Walk on Air) según el objetivo del diario; la fuente no exige una ubicación fija para activarla.", [
            {**authored_evidence(reference, relative, 116), "entityType": "quest", "entityID": qid, "classification": "ability"}]
    return None, None, None


def propose(document, reference):
    """Return an overlay/report; all source document objects stay untouched."""
    patches, unresolved = [], []
    statistics = census(document)
    outcome = Counter()
    taxi = {row[0]: row for row in array(reference.travel.get("taxi"))}
    inns = array(reference.travel.get("inns"))
    node_areas, node_names, node_restrictions = defaultdict(set), defaultdict(set), defaultdict(list)
    for _, _, _, _, goal in iter_goals(document):
        if goal["t"] == "getfp" and goal.get("node"):
            if goal.get("area"):
                node_areas[goal["area"]].add(goal["node"])
            if goal.get("location"):
                node_names[goal["location"]].add(goal["node"])
            node_restrictions[goal["node"]].append(goal.get("only", {}))
    reverse = defaultdict(set)
    flights = array(reference.travel.get("flights"))
    for i in range(0, len(flights) - 2, 3):
        reverse[flights[i + 1]].add(flights[i])

    def node_point(node):
        row = taxi[node]
        point = {"map": row[4], "x": row[5], "y": row[6], "f": "e",
                 "faction": {1: "A", 2: "H", 3: "AH"}.get(row[7]), "flightNode": node}
        # Keep explicit restrictions only when every authored use agrees.
        restrictions = node_restrictions.get(node, [])
        for key in ("classes", "races"):
            if restrictions and all(r.get(key) for r in restrictions):
                values = {tuple(r[key]) for r in restrictions}
                if len(values) == 1:
                    point[key] = list(next(iter(values)))
        return point

    for guide, si, step, gi, goal in iter_goals(document):
        action = goal["t"]
        if availability(goal) != "none":
            continue
        context = {"guideID": guide["id"], "step": si, "goal": gi, "action": action,
                   "questID": goal.get("quest"), "title": goal.get("title"),
                   "note": goal.get("note"), "stepNote": step.get("note")}
        if action in NO_FIXED_POINT or action == "accept" and goal.get("item"):
            outcome["legitimateNoFixedPoint"] += 1
            continue
        candidates, evidence, unknown = [], [], []
        hint, mode = None, None

        def add(candidate, proof):
            if not located(candidate):
                return
            # Different objectives keep separate markers even at the same spot.
            if candidate in candidates:
                return
            candidates.append(candidate)
            evidence.append({"candidateIndex": len(candidates), **proof})

        def entity_points(kind, ident, oi, proof_kind, via=None):
            record = reference.get(kind, ident)
            points = array(record.get("spawns"))
            for point in points:
                if not located(point):
                    continue
                candidate = source_candidate(kind, ident, point, record.get("name"), oi)
                # Quest targets can be hostile; NPC allegiance is NOT a player
                # eligibility filter. Existing goal/step/guide conditions apply.
                proof = {"kind": proof_kind, "entityType": kind, "entityID": ident,
                         "objectiveIndex": oi, **reference.evidence(kind, ident)}
                if via:
                    proof["via"] = via
                add(candidate, proof)
            return bool(points)

        if action == "complete" and goal.get("quest"):
            quest_id = goal["quest"]
            quest = reference.get("quest", quest_id)
            event_points = dict(reference.event_points(quest_id))
            objectives = array(quest.get("objectives"))
            for oi, objective in enumerate(objectives, 1):
                before = len(candidates)
                typ, ident = objective.get("type"), objective.get("id")
                via = {"questID": quest_id, "objectiveIndex": oi, "objectiveType": typ,
                       **reference.evidence("quest", quest_id)}
                if typ in {"kill", "object"} and ident:
                    entity_points("npc" if typ == "kill" else "object", ident, oi, "quest-objective", via)
                elif typ == "item" and ident:
                    item = reference.get("item", ident)
                    for source in array(item.get("sources")):
                        if source.get("type") not in {"drop", "object", "gift", "vendor"} or source.get("chance") == 0:
                            continue
                        kind = "npc" if source.get("npc") else "object" if source.get("object") else None
                        entity = source.get("npc") or source.get("object")
                        if kind:
                            entity_points(kind, entity, oi, "item-source", {
                                **via, "itemID": ident, "itemSourceType": source["type"],
                                "itemEvidence": reference.evidence("item", ident)})
                elif typ == "event" and oi in event_points:
                    candidate = source_candidate("event", quest_id, event_points[oi], objective_index=oi)
                    candidate["navigationRole"] = "event-area"
                    path = "addon/SendaFH_QuestDB/Quests.lua"
                    add(candidate, {"kind": "quest-event", "entityType": "quest", "entityID": quest_id,
                                    "objectiveIndex": oi, "sourceField": "events[objective.event]",
                                    "sourceFile": path, "sourceSha256": reference.files[path]})
                if len(candidates) == before:
                    unknown.append({"objectiveIndex": oi, **objective})
            if not objectives:
                unknown.append({"reason": "No objective record in the pinned source"})
            hint = "La marca es una referencia del objetivo; consulta sus instrucciones y espera a que el juego confirme el progreso."
            if unknown:
                hint = goal.get("note") or step.get("note") or "Consulta los objetivos de la misión en el diario; la fuente no documenta una ubicación para todos ellos."
            if unknown and getattr(reference, "source", None):
                manual_mode, manual_hint, manual_evidence = manual_navigation(reference, guide, goal, add, entity_points)
                if manual_evidence is not None:
                    mode, hint = manual_mode, manual_hint
                    evidence.extend(manual_evidence)
                    unknown = []

        elif action == "getfp" and goal.get("node") in taxi:
            node = goal["node"]
            point = node_point(node)
            if accessible(point.get("faction"), guide):
                path = "addon/SendaFH/Nav/TravelData.lua"
                add(point, {"kind": "flight-node", "entityType": "taxi-node", "entityID": node,
                            "sourceFile": path, "sourceSha256": reference.files[path]})
            hint = "Habla con el maestro de vuelo de este punto para descubrirlo. Llegar a la marca no confirma que lo hayas aprendido."

        elif action == "sethome":
            for inn in inns:
                if inn.get("area") != goal.get("area"):
                    continue
                npc = reference.get("npc", inn["npc"])
                if not accessible(npc.get("faction"), guide):
                    continue
                candidate = source_candidate("npc", inn["npc"], inn, npc.get("name"))
                if npc.get("faction"):
                    candidate["faction"] = npc["faction"]
                path = "addon/SendaFH/Nav/TravelData.lua"
                add(candidate, {"kind": "inn-area", "entityType": "npc", "entityID": inn["npc"],
                                "areaID": inn["area"], "sourceFile": path, "sourceSha256": reference.files[path]})
            hint = "Habla con el tabernero y elige convertir esta posada en tu hogar. Estar dentro no cambia tu Piedra de hogar."

        elif action == "fly":
            destinations = node_areas.get(goal.get("area"), set()) or node_names.get(goal.get("location"), set())
            connected, queue = set(destinations), list(destinations)
            while queue:
                for node in reverse[queue.pop()]:
                    if node not in connected:
                        connected.add(node)
                        queue.append(node)
            explicit = goal.get("from")
            if explicit is not None:
                origins = set(explicit if isinstance(explicit, list) else [explicit])
                connected &= origins
            for node in sorted(connected):
                if node not in taxi:
                    continue
                point = node_point(node)
                if not accessible(point.get("faction"), guide):
                    continue
                point.update(navigationRole="flight-origin", destinationNodes=sorted(destinations))
                path = "addon/SendaFH/Nav/TravelData.lua"
                add(point, {"kind": "flight-node", "entityType": "taxi-node", "entityID": node,
                            "destinationNodes": sorted(destinations), "sourceFile": path, "sourceSha256": reference.files[path]})
            hint = "La flecha señala un maestro de vuelo de salida. Habla con él y elige " + goal.get("location", "el destino indicado") + "; el juego confirma qué vuelos tienes disponibles."

        if candidates or hint:
            fields = {}
            if candidates:
                fields["candidates"] = candidates
            if hint:
                fields["navigationHint"] = hint
            if mode:
                fields["navigationMode"] = mode
            match = {key: copy.deepcopy(goal[key]) for key in ("t", "quest", "area", "node", "location", "only", "item") if key in goal}
            patches.append({"id": f"{guide['id']}:{si}:{gi}", "guideID": guide["id"], "step": si, "goal": gi,
                            "match": match, "set": fields, "evidence": evidence})
            outcome["partial" if unknown and candidates else "unresolved" if unknown else "located" if candidates else "classifiedNoFixedPoint" if mode else "hintOnly"] += 1
        if unknown or not candidates and not mode:
            unresolved.append({**context, "knownCandidates": len(candidates), "unknownObjectives": unknown,
                               "reason": "Some objectives lack a documented point" if unknown else "No compatible authored service point"})
    statistics.update(outcomes=dict(sorted(outcome.items())), patches=len(patches),
                      candidates=sum(len(p["set"].get("candidates", [])) for p in patches),
                      mixedMapPatches=sum(len({c["map"] for c in p["set"].get("candidates", [])}) > 1 for p in patches),
                      candidatesWithoutHeight=sum("z" not in c for p in patches for c in p["set"].get("candidates", [])))
    return {"schemaVersion": 1, "sourceCommit": document["provenance"]["commit"],
            "sourceFiles": dict(sorted(reference.files.items())), "patches": patches,
            "unresolved": unresolved, "statistics": statistics}


def without_applied_overlay(document, overlay):
    """Recover the baseline on regeneration, preserving all authored points.

    Only fields this overlay introduced on previously unlocated goals are
    removed. A manually changed value is rejected for review, never erased.
    """
    baseline = copy.deepcopy(document)
    guides = {guide["id"]: guide for guide in baseline["guides"]}
    for patch in overlay.get("patches", []):
        guide = guides.get(patch["guideID"])
        if not guide:
            raise ValueError(f"Previous overlay guide not found: {patch['id']}")
        goal = guide["steps"][patch["step"] - 1]["goals"][patch["goal"] - 1]
        if any(goal.get(k) != v for k, v in patch["match"].items()):
            raise ValueError(f"Previous overlay no longer matches: {patch['id']}")
        for key, expected in patch["set"].items():
            if key not in goal:
                continue
            if goal[key] != expected:
                raise ValueError(f"Navigation was edited after the overlay: {patch['id']} {key}")
            del goal[key]
    return baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / ".sources/SendaFH")
    parser.add_argument("--input", type=Path, default=ROOT / "RutaXP/Source/leveling.json")
    parser.add_argument("--output", type=Path, default=ROOT / "RutaXP/Source/guide_locations.json")
    parser.add_argument("--report", type=Path, default=ROOT / ".backups/coordinate-proposals.json")
    args = parser.parse_args()
    document = json.loads(args.input.read_text(encoding="utf-8"))
    if args.output.is_file():
        document = without_applied_overlay(document, json.loads(args.output.read_text(encoding="utf-8")))
    report = propose(document, load_reference(args.source, document))
    for path in (args.output, args.report):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report["statistics"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

