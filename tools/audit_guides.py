#!/usr/bin/env python3
"""Read-only inventory of guide navigation and authored instructions.

No coordinates are inferred, copied, or applied. A complete quest is not its
turn-in NPC, and a taxi destination does not establish the current departure.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "RutaXP" / "Source" / "leveling.json"
SEMANTIC_FIELDS = (
    "t", "action", "quest", "questID", "oi", "item", "count", "only", "optional",
    "minLevel", "maxLevel", "level", "n", "pre", "preAll", "closedBy", "group",
    "profLine", "profName", "profRank", "class", "classes", "races", "factions",
    "node", "area", "location", "requiredLevel",
)
POINT_FIELDS = ("map", "x", "y", "z", "f", "r")
EXCEPTIONS = {
    "note": ("semantic_no_location", "Nota informativa; no establece un destino físico."),
    "level": ("semantic_no_location", "Requisito de nivel; no establece una zona de farmeo por sí solo."),
    "hearth": ("semantic_no_location", "Usa el hogar realmente vinculado; no debe inventarse su posición."),
}
NAVIGATION_MODES = {
    "inventory": "Acción en el inventario; no se presenta un NPC o una posición inventada.",
    "ability": "Uso de habilidad u objeto; no establece por sí solo un destino fijo.",
    "escort": "Sigue al NPC que se desplaza; sus coordenadas de inicio son solo una referencia.",
}


def digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def has_point(value: dict[str, Any], inherited_map: Any = None) -> bool:
    map_id = value.get("map", inherited_map)
    return (number(map_id) and map_id > 0 and int(map_id) == map_id
            and number(value.get("x")) and 0 <= value["x"] <= 100
            and number(value.get("y")) and 0 <= value["y"] <= 100)


def goal_key(guide_id: str, step: int, goal: int) -> str:
    return f"{guide_id}:{step}:{goal}"


def iter_goals(document: dict[str, Any]):
    for guide in document["guides"]:
        for si, step in enumerate(guide["steps"], 1):
            for gi, goal in enumerate(step["goals"], 1):
                yield guide, si, step, gi, goal


def semantics(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"key": goal_key(g["id"], si, gi),
             "fields": {name: goal[name] for name in SEMANTIC_FIELDS if name in goal}}
            for g, si, _, gi, goal in iter_goals(document)]


def navigation_kind(goal: dict[str, Any]) -> str:
    if goal.get("navigationMode") == "inventory" and any(has_point(c) for c in goal.get("candidates", [])):
        return "conditional_navigation"
    if goal.get("navigationMode") in NAVIGATION_MODES:
        return "no_fixed_navigation"
    return authored_navigation_kind(goal)


def authored_navigation_kind(goal: dict[str, Any]) -> str:
    if has_point(goal):
        return "direct"
    if any(has_point(spot, goal.get("map")) and not spot.get("alt") for spot in goal.get("spots", [])):
        return "spots"
    if any(has_point(candidate) for candidate in goal.get("candidates", [])):
        return "candidates"
    return "missing"


def missing_classification(goal: dict[str, Any]) -> tuple[str, str]:
    action = goal.get("t", goal.get("action"))
    if action in EXCEPTIONS:
        return EXCEPTIONS[action]
    if action == "accept" and number(goal.get("item")) and goal["item"] > 0:
        return "item_start", "La misión comienza usando un objeto; no implica un NPC de aceptación fijo."
    if action == "fly":
        return "taxi_departure_unknown", "El destino del vuelo no identifica al maestro de vuelo de salida."
    if action in ("getfp", "sethome", "train", "vendor", "buy"):
        return "unlocated_service", "Falta un proveedor compatible y su posición documentada."
    if action in ("complete", "kill", "collect", "objective", "interact", "use"):
        return "unlocated_objective", "Se necesitan objetivos y ubicaciones de la misión; entregar no es completar."
    return "unlocated_action", "Falta una posición documentada para esta acción."


def source_reference(document, guide, si, gi):
    provenance = document.get("provenance", {})
    return {"repository": provenance.get("repository"), "commit": guide.get("sourceCommit", provenance.get("commit")),
            "compiledFile": "addon/SendaFH_Guides/Guides.lua", "guideID": guide["id"],
            "stepIndex": si, "goalIndex": gi}


def authored_subtitle(goal):
    candidate = next((c.get("npcName") for c in goal.get("candidates", []) if text(c.get("npcName"))), None)
    names = (goal.get("itemName"), goal.get("target"), goal.get("npcName") or candidate,
             goal.get("objName") or goal.get("objectName"))
    action = goal.get("t", goal.get("action"))
    content = names[2] if action in ("accept", "turnin", "talk") else next((n for n in names if text(n)), None)
    note = goal.get("note")
    if text(note) and not any(text(name) and note.strip().casefold() == name.strip().casefold() for name in names):
        content = note
    return content if text(content) else None


def audit(document: dict[str, Any], include_baseline: bool = False,
          locations: dict[str, Any] | None = None,
          revisions: dict[str, Any] | None = None) -> dict[str, Any]:
    by_action = defaultdict(Counter)
    by_guide = {g["id"]: {"guideID": g["id"], "title": g["title"], "counts": Counter(),
                                  "byAction": defaultdict(Counter)} for g in document["guides"]}
    totals = Counter(guides=len(document["guides"]))
    missing, issues, invalid = [], [], []
    direct_digests = {}
    mode_evidence = {}
    if locations and locations.get("sourceCommit") == document.get("provenance", {}).get("commit"):
        for patch in locations.get("patches", []):
            mode = patch.get("set", {}).get("navigationMode")
            evidence = patch.get("evidence", [])
            proved = bool(evidence) and all(
                isinstance(entry, dict) and text(entry.get("sourceFile"))
                and isinstance(entry.get("sourceSha256"), str) and len(entry["sourceSha256"]) == 64
                and locations.get("sourceFiles", {}).get(entry["sourceFile"]) == entry["sourceSha256"]
                for entry in evidence)
            if mode in NAVIGATION_MODES and proved:
                guide = next((guide for guide in document["guides"] if guide["id"] == patch["guideID"]), {})
                key = f'{patch["step"]}:{patch["goal"]}'
                for migration in guide.get("progressMigrations", []):
                    if key in migration.get("retiredGoalKeys", {}):
                        break
                    key = migration.get("goalMap", {}).get(key, key)
                else:
                    si, gi = (int(part) for part in key.split(":"))
                    mode_evidence[goal_key(patch["guideID"], si, gi)] = mode
    if revisions and revisions.get("sourceCommit") == document.get("provenance", {}).get("commit"):
        applied = document.get("provenance", {}).get("routeRevisions", {}).get("applied", [])
        for revision in revisions.get("revisions", []):
            proof = revision.get("evidence", {})
            sha = proof.get("sourceSha256", "")
            if revision.get("id") not in applied or not text(proof.get("sourceFile")) or not text(proof.get("sourceUrl")) \
                    or len(sha) != 64 or any(char not in "0123456789abcdef" for char in sha):
                continue
            for patch in revision.get("goalChanges", []):
                mode = patch.get("set", {}).get("navigationMode")
                if mode not in NAVIGATION_MODES:
                    continue
                expected = {**patch["match"], **patch["set"]}
                matches = [(guide, si, gi) for guide, si, _, gi, goal in iter_goals(document)
                           if guide["id"] == revision["guideID"]
                           and all(goal.get(key) == value for key, value in expected.items())]
                if len(matches) == patch["count"]:
                    for guide, si, gi in matches:
                        mode_evidence[goal_key(guide["id"], si, gi)] = mode
    era = document.get("mapFrames", {}).get("era", {})
    for guide, si, step, gi, goal in iter_goals(document):
        key = goal_key(guide["id"], si, gi)
        action = goal.get("t", goal.get("action", "unknown"))
        kind = navigation_kind(goal)
        counts = [totals, by_action[action], by_guide[guide["id"]]["counts"], by_guide[guide["id"]]["byAction"][action]]
        for counter in counts:
            counter["goals"] += 1
            counter[kind] += 1
        identity = {"key": key, "guideID": guide["id"], "stepIndex": si, "goalIndex": gi,
                    "action": action, "questID": goal.get("quest", goal.get("questID")),
                    "title": goal.get("title"), "source": source_reference(document, guide, si, gi)}
        if kind in ("missing", "no_fixed_navigation", "conditional_navigation"):
            if kind in ("no_fixed_navigation", "conditional_navigation"):
                mode = goal["navigationMode"]
                proved = mode_evidence.get(key) == mode
                classification = ("documented_mixed_objective" if kind == "conditional_navigation" else
                                  "documented_navigation_mode") if proved else "unproven_navigation_exception"
                reason = ("Solo se señala la parte del objetivo pendiente en el mundo; la acción restante de inventario no tiene pin fijo."
                          if kind == "conditional_navigation" else NAVIGATION_MODES[mode]) if proved else \
                         "El modo de navegación necesita su evidencia de overlay vinculada."
                unresolved = not proved
                if kind == "no_fixed_navigation" and authored_navigation_kind(goal) != "missing":
                    for counter in counts:
                        counter["reference_only"] += 1
            else:
                classification, reason = missing_classification(goal)
                unresolved = classification not in ("semantic_no_location", "item_start")
            missing.append({**identity, "classification": classification, "reason": reason,
                            "unresolved": unresolved, "goalNote": goal.get("note", goal.get("text")),
                            "stepNote": step.get("note", step.get("text")),
                            "navigationMode": goal.get("navigationMode"),
                            "referenceNavigationKind": authored_navigation_kind(goal)})
            for counter in counts:
                counter["unresolved" if unresolved else
                        "conditional_point_expected" if kind == "conditional_navigation" else "no_fixed_point_expected"] += 1
        if authored_navigation_kind(goal) == "direct":
            direct_digests[key] = digest({name: goal[name] for name in POINT_FIELDS if name in goal})
        for place, label in [(goal, "goal")] + [(c, f"candidate:{i}") for i, c in enumerate(goal.get("candidates", []), 1)] \
                + [(s, f"spot:{i}") for i, s in enumerate(goal.get("spots", []), 1)]:
            if "x" not in place and "y" not in place:
                continue
            effective = {**place, "map": place.get("map", goal.get("map"))}
            frame = place.get("f", goal.get("f"))
            reason = None
            if not has_point(effective):
                reason = "Coordenadas incompletas, no finitas o fuera de rango."
            elif frame not in (None, "e", "l"):
                reason = "Marco de coordenadas no reconocido."
            elif frame == "e" and str(effective["map"]) not in era and effective["map"] not in era:
                reason = "No hay rectángulo Era para convertir estas coordenadas."
            elif "z" in place and not number(place["z"]):
                reason = "Altura no finita."
            if reason:
                invalid.append({**identity, "location": label, "reason": reason})
        goal_detail = text(goal.get("note")) or text(goal.get("text"))
        step_detail = text(step.get("note")) or text(step.get("text"))
        if text(goal.get("instruction")):
            for counter in counts:
                counter["generated_instruction"] += 1
        if not goal_detail:
            for counter in counts:
                counter["missing_goal_note_text"] += 1
        if authored_subtitle(goal) is None:
            for counter in counts:
                counter["empty_authored_subtitle"] += 1
        if action == "complete" and not goal_detail and step_detail:
            issues.append({**identity, "kind": "step_instructions_not_goal", "severity": "review",
                           "reason": "La explicación está en el paso; comprobar que la fila compacta permita consultarla."})
        unclear = ((action == "note" and not goal_detail)
                   or (action == "level" and not number(goal.get("level", goal.get("n"))))
                   or (action == "complete" and not goal_detail and not step_detail))
        if unclear:
            issues.append({**identity, "kind": "unclear_instruction", "severity": "unresolved",
                           "reason": "La fuente no explica la acción; necesita objetivos legibles del diario o revisión manual."})
            for counter in counts:
                counter["unclear_instruction"] += 1
    totals["steps"] = sum(len(g["steps"]) for g in document["guides"])
    report = {
        "schemaVersion": 1, "scope": "Source/leveling.json; información de fuente, sin verificación completa dentro del juego",
        "source": document.get("provenance", {}), "totals": dict(totals),
        "byAction": {a: dict(c) for a, c in sorted(by_action.items())},
        "byGuide": [{**row, "counts": dict(row["counts"]),
                     "byAction": {a: dict(c) for a, c in sorted(row["byAction"].items())}}
                    for row in by_guide.values()],
        "missingNavigation": missing, "instructionIssues": issues, "invalidNavigation": invalid,
        "knownExceptions": [{"action": a, "classification": c, "reason": reason}
                            for a, (c, reason) in sorted(EXCEPTIONS.items())] + [
            {"action": "accept", "classification": "item_start", "reason": "Un objeto que inicia misión no implica un NPC fijo."}] + [
            {"navigationMode": mode, "classification": "documented_navigation_mode", "reason": reason}
            for mode, reason in sorted(NAVIGATION_MODES.items())],
        "interpretation": {
            "missing_goal_note_text": "Conteo literal; un verbo, nombre o descripción de misión puede bastar sin nota adicional.",
            "empty_authored_subtitle": "Sin contenido estático de subtítulo; objetivos del diario y razones del motor pueden añadir texto en tiempo de ejecución.",
            "unresolved": "Ausencia de destino estático documentado, no prueba que la misión sea imposible.",
        },
        "preservation": {"semanticFields": list(SEMANTIC_FIELDS), "semanticsSha256": digest(semantics(document))},
    }
    if include_baseline:
        report["preservation"]["authoredDirectDigests"] = direct_digests
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--locations", type=Path, help="Defaults to guide_locations.json beside the snapshot when present")
    args = parser.parse_args()
    document = json.loads(args.input.read_text(encoding="utf-8"))
    locations_path = args.locations or args.input.with_name("guide_locations.json")
    locations = json.loads(locations_path.read_text(encoding="utf-8")) if locations_path.exists() else None
    revisions_path = args.input.with_name("guide_revisions.json")
    revisions = json.loads(revisions_path.read_text(encoding="utf-8")) if revisions_path.exists() else None
    report = audit(document, args.baseline, locations, revisions)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
        print(json.dumps({"output": str(args.output), "totals": report["totals"]}, ensure_ascii=False))
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
