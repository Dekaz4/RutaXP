#!/usr/bin/env python3
"""Read-only route/quest-order audit; writes a report, never guide data.

The pinned DSL/compiled pack and Codex are evidence, not a simulator of the
server. An absent quest-linked work goal is a review category, not an error:
shopping, pre-collected items, conversation credit and escorts may be written
as unbound goals or notes. Live quest completion always remains authoritative.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PIN = "5d207e28e82e2c529143b21ace74fe88692f0067"
CLASSES = ("WARRIOR", "PALADIN", "HUNTER", "ROGUE", "PRIEST", "SHAMAN", "MAGE", "WARLOCK", "DRUID")
RACES = {"Alliance": ("Human", "Dwarf", "Gnome", "NightElf", "Skyborne"),
         "Horde": ("Orc", "Troll", "Tauren", "Scourge", "Skyborne")}
FIELDS = ("t", "quest", "oi", "item", "count", "pre", "preAll", "closedBy", "only", "optional",
          "minLevel", "maxLevel", "level", "n", "class", "group", "order")
GOAL_ACTIONS = {"accept", "turnin", "kill", "collect", "train", "goto", "sethome", "complete", "hearth",
                "buy", "getfp", "fly", "use", "note", "level", "interact", "vendor", "talk"}
CATEGORIES = ("work_before_accept", "turnin_without_accept", "accept_without_future_turnin",
              "prerequisite_not_in_prior_path", "prerequisite_forward_local", "ordered_closed_branch")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(value: Any) -> str:
    result = re.sub(r"[\s_-]", "", str(value)).lower()
    return "scourge" if result == "undead" else result


def matches(values, actual):
    """Same inclusive/exclusive selector semantics as QuestEngine.MatchesConditions."""
    if not values:
        return True
    positive = []
    for value in values:
        if str(value).startswith("!"):
            if normalized(str(value)[1:]) == normalized(actual):
                return False
        else:
            positive.append(normalized(value))
    return not positive or normalized(actual) in positive


def fits(only, persona):
    return not only or all(matches(only.get(key), persona[index])
                           for index, key in enumerate(("classes", "races", "factions")))


def guide_fits(guide, persona):
    return ((not guide.get("faction") or guide["faction"] == persona[2])
            and matches(guide.get("races"), persona[1]) and matches(guide.get("classes"), persona[0]))


def links(guide):
    value = guide.get("nextChoices") or guide.get("next") or []
    return value if isinstance(value, list) else [value]


def source_refs(source: Path | None, guides):
    refs, counts, steps, problems = {}, Counter(), 0, []
    if not source:
        return refs, {}, None, []
    for guide in guides:
        relative = "guides/" + guide["id"] + ".guide"
        path = source / relative
        if not path.exists():
            problems.append({"kind": "missing_dsl", "sourceFile": relative})
            continue
        si = gi = 0
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if line.startswith("step "):
                si += 1
                gi = 0
            hit = re.match(r"^  (\w+)\b", line)
            if hit and hit[1] in GOAL_ACTIONS:
                gi += 1
                counts[hit[1]] += 1
                refs[guide["id"], si, gi] = {"sourceFile": relative, "sourceLine": line_number,
                                             "sourceText": line.strip()}
        steps += si
    return refs, dict(sorted(counts.items())), steps, problems


def events_for(guides, refs):
    events = []
    for guide in guides:
        for si, step in enumerate(guide["steps"], 1):
            for gi, goal in enumerate(step["goals"], 1):
                events.append({"guideID": guide["id"], "step": si, "goal": gi, "action": goal.get("t"),
                               "questID": goal.get("quest"), "data": goal, "stepData": step,
                               **refs.get((guide["id"], si, gi), {})})
    return events


def reference(event):
    result = {key: event[key] for key in ("guideID", "step", "goal", "action", "questID", "sourceFile",
                                          "sourceLine", "sourceText") if key in event}
    for key in ("only", "optional"):
        if event["data"].get(key):
            result[key] = event["data"][key]
    if event["stepData"].get("only"):
        result["stepOnly"] = event["stepData"]["only"]
    return result


def route_paths(guides):
    """Keep alternative incoming paths separate: never union their completed quests."""
    by_id = {g["id"]: g for g in guides}
    incoming = Counter(n for g in guides for n in links(g) if n in by_id)
    roots = [g["id"] for g in guides if not incoming[g["id"]]]
    paths, cycles, dangling = [], [], []
    for g in guides:
        dangling.extend({"guideID": g["id"], "next": n} for n in links(g) if n not in by_id)

    def walk(gid, prefix):
        if gid in prefix:
            cycles.append(prefix[prefix.index(gid):] + [gid])
            return
        path = prefix + [gid]
        targets = [n for n in links(by_id[gid]) if n in by_id]
        if not targets:
            paths.append(path)
        else:
            for target in targets:
                walk(target, path)

    for gid in roots:
        walk(gid, [])
    # A component made entirely of a cycle has no root.
    visited = {gid for path in paths for gid in path} | {gid for cycle in cycles for gid in cycle}
    for gid in by_id:
        if gid not in visited:
            walk(gid, [])
            visited.update(gid for path in paths for gid in path)
            visited.update(gid for cycle in cycles for gid in cycle)
    return paths, cycles, dangling


def dependency_cycles(events):
    adjacency = defaultdict(set)
    for event in events:
        if event["action"] == "accept":
            adjacency[event["questID"]].update(abs(q) for key in ("pre", "preAll") for q in event["data"].get(key, []))
    indices, low, stack, active, found = {}, {}, [], set(), []

    def visit(v):
        indices[v] = low[v] = len(indices)
        stack.append(v)
        active.add(v)
        for w in sorted(adjacency.get(v, ())):
            if w not in indices:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in active:
                low[v] = min(low[v], indices[w])
        if low[v] == indices[v]:
            group = []
            while True:
                w = stack.pop()
                active.remove(w)
                group.append(w)
                if w == v:
                    break
            if len(group) > 1 or v in adjacency.get(v, ()):
                found.append(sorted(group))

    for v in sorted(adjacency):
        if v not in indices:
            visit(v)
    return sorted(found)


def scan_order(guides, events):
    by_id, by_guide = {g["id"]: g for g in guides}, defaultdict(list)
    for event in events:
        by_guide[event["guideID"]].append(event)
    paths, cycles, dangling = route_paths(guides)
    findings = {category: {} for category in CATEGORIES}
    no_work, carried, scenarios = {}, {}, 0

    def add(category, event, persona, path_index, **extra):
        key = (event["guideID"], event["step"], event["goal"])
        entry = findings[category].setdefault(key, {**reference(event), **extra, "modeledScenarios": []})
        scenario = {"path": path_index, "class": persona[0], "race": persona[1], "faction": persona[2]}
        if scenario not in entry["modeledScenarios"]:
            entry["modeledScenarios"].append(scenario)

    for path_index, path in enumerate(paths, 1):
        first = by_id[path[0]]
        sides = [first["faction"]] if first.get("faction") else list(RACES)
        for side in sides:
            for race in first.get("races") or RACES[side]:
                for cls in first.get("classes") or CLASSES:
                    persona = (cls, race, side)
                    sequence = [e for gid in path if guide_fits(by_id[gid], persona) for e in by_guide[gid]
                                if fits(e["stepData"].get("only"), persona) and fits(e["data"].get("only"), persona)]
                    if not sequence:
                        continue
                    scenarios += 1
                    by_quest = defaultdict(list)
                    for i, event in enumerate(sequence):
                        if event["questID"]:
                            by_quest[event["questID"]].append((i, event))
                    accepted, done = {}, {}
                    for i, event in enumerate(sequence):
                        qid, action, goal = event["questID"], event["action"], event["data"]
                        if not qid:
                            continue
                        if action == "accept":
                            future = [(n, e) for n, e in by_quest[qid] if n > i]
                            if not any(e["action"] == "turnin" for _, e in future):
                                add("accept_without_future_turnin", event, persona, path_index)
                            if not any(e["action"] not in ("accept", "turnin") for _, e in future):
                                no_work.setdefault((event["guideID"], event["step"], event["goal"]), reference(event))
                            for key in ("preAll", "pre"):
                                dependencies = goal.get(key, [])
                                absent = [abs(q) for q in dependencies if abs(q) not in done]
                                missing = absent if key == "preAll" else absent if dependencies and len(absent) == len(dependencies) else []
                                if missing:
                                    forward = [q for q in missing if any(n > i and e["guideID"] == event["guideID"]
                                               and e["action"] == "turnin" for n, e in by_quest[q])]
                                    add("prerequisite_not_in_prior_path", event, persona, path_index,
                                        prerequisiteKind=key, missing=missing, forwardLocal=forward)
                                    if forward and (key == "preAll" or len(forward) == len(missing)):
                                        add("prerequisite_forward_local", event, persona, path_index,
                                            prerequisiteKind=key, missing=missing, forwardLocal=forward)
                            closed = [q for q in goal.get("closedBy", []) if q in accepted or q in done]
                            if closed:
                                add("ordered_closed_branch", event, persona, path_index, closedBy=closed)
                            accepted[qid] = event
                        elif action == "turnin":
                            if qid not in accepted:
                                add("turnin_without_accept", event, persona, path_index)
                            elif accepted[qid]["guideID"] != event["guideID"]:
                                key = (event["guideID"], event["step"], event["goal"])
                                carried.setdefault(key, {**reference(event), "acceptedAt": reference(accepted[qid])})
                            done[qid] = event
                        elif qid not in accepted:
                            add("work_before_accept", event, persona, path_index)
    return {"modeledScenarios": scenarios, "paths": paths, "guideLinkCycles": cycles, "danglingNext": dangling,
            "candidates": {k: list(v.values()) for k, v in findings.items()},
            "counts": {k: len(v) for k, v in findings.items()}, "carriedTurnins": list(carried.values()),
            "noQuestLinkedFutureWork": list(no_work.values())}


def compare_compiled(source, guides, document=None):
    if not source:
        return {"available": False}
    from import_guides import to_python
    from lupa.lua51 import LuaRuntime
    captured = {}
    lua = LuaRuntime(unpack_returned_tuples=True)
    for name in ("os", "io", "package", "require", "dofile", "loadfile", "debug"):
        lua.globals()[name] = None

    def capture(value):
        if value.category == "Leveling":
            data = to_python(value)
            captured[data["id"]] = data

    lua.globals().SendaFH = lua.table_from({"RegisterGuide": capture})
    relative = "addon/SendaFH_Guides/Guides.lua"
    raw = (source / relative).read_bytes()
    lua.execute(raw.decode("utf-8-sig"))
    def compare(originals):
        differences, missing_text = [], []
        for guide in guides:
            original = originals.get(guide["id"])
            if not original:
                differences.append({"guideID": guide["id"], "field": "missing source guide"})
                continue
            for key in ("faction", "races", "classes", "next", "nextChoices"):
                if guide.get(key) != original.get(key):
                    differences.append({"guideID": guide["id"], "field": key})
            if len(guide["steps"]) != len(original["steps"]):
                differences.append({"guideID": guide["id"], "field": "step count"})
            for si, (step, old) in enumerate(zip(guide["steps"], original["steps"]), 1):
                if step.get("only") != old.get("only") or len(step["goals"]) != len(old["goals"]):
                    differences.append({"guideID": guide["id"], "step": si, "field": "group shape/condition"})
                for field in ("note", "text"):
                    if old.get(field) and not step.get(field):
                        missing_text.append({"guideID": guide["id"], "step": si, "field": field})
                for gi, (goal, before) in enumerate(zip(step["goals"], old["goals"]), 1):
                    for field in FIELDS:
                        if goal.get(field) != before.get(field):
                            differences.append({"guideID": guide["id"], "step": si, "goal": gi, "field": field,
                                                "source": before.get(field), "snapshot": goal.get(field)})
                    for field in ("note", "text"):
                        if before.get(field) and not goal.get(field):
                            missing_text.append({"guideID": guide["id"], "step": si, "goal": gi, "field": field})
        return differences, missing_text

    raw_differences, _ = compare(captured)
    revised, reviewed = captured, []
    revisions_path = ROOT / "RutaXP/Source/guide_revisions.json"
    if document and document.get("provenance", {}).get("routeRevisions") and revisions_path.is_file():
        spec = importlib.util.spec_from_file_location("audit_revision_builder", revisions_path.with_name("build_guides.py"))
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        corrected = {"provenance": {"commit": document["provenance"]["commit"]}, "statistics": {},
                     "guides": copy.deepcopy(list(captured.values()))}
        applied = builder.apply_guide_revisions(corrected, revisions_path)
        revised = {guide["id"]: guide for guide in corrected["guides"]}
        revisions = json.loads(revisions_path.read_text(encoding="utf-8"))["revisions"]
        reviewed = [{"id": entry["id"], "guideID": entry["guideID"], "revision": entry["revision"],
                     "evidence": entry["evidence"]} for entry in revisions if entry["id"] in applied]
    differences, missing_text = compare(revised)
    return {"available": True, "sourceFile": relative, "sourceSha256": sha(raw),
            "sourceLevelingGuides": len(captured), "sourceGuideIDsMissingFromSnapshot": sorted(set(captured) - {g["id"] for g in guides}),
            "structuralDifferences": differences, "rawStructuralDifferences": raw_differences,
            "reviewedCorrections": reviewed, "authoredTextPresenceLosses": missing_text,
            "sourceStepNotes": sum(bool(s.get("note")) for g in captured.values() for s in g["steps"]),
            "snapshotStepNotes": sum(bool(s.get("note")) for g in guides for s in g["steps"])}


# Reviewed only against the pinned source. These are classification notes,
# never changes to quests or proof that the player has finished their work.
CONTEXT = {
    338: ("chapter_rewards", "Los capítulos se reciben al entregar las cuatro submisiones; la nota pide reunir páginas durante la ruta."),
    6504: ("optional_inventory_in_context", "Opcional: la nota pide llevar las páginas del manual; no establece una recogida obligatoria nueva."),
    716: ("optional_inventory_in_context", "Entrega opcional solo si se llevan brazales fabricados; la condición está en la nota de entrega."),
    1203: ("optional_inventory_in_context", "La aceptación opcional exige llevar ya la espada fabricada, según su nota."),
    3785: ("optional_inventory_in_context", "La nota pide diez Mañagrana de la faltriquera; el trabajo se expresa como contexto de inventario."),
    3803: ("optional_inventory_in_context", "Entrega opcional de Mañagrana; no se copia la cantidad de otra misión sin evidencia."),
    5402: ("optional_inventory_in_context", "Entrega opcional de piedras ya recogidas; los enemigos y la insignia se describen en otros pasos."),
    5403: ("optional_inventory_in_context", "Entrega opcional de piedras ya recogidas; los enemigos y la insignia se describen en otros pasos."),
    5407: ("optional_inventory_in_context", "Entrega opcional de piedras previas; otras recogidas explícitas de12841 están ligadas a5509, no a esta misión."),
    5408: ("optional_inventory_in_context", "Entrega opcional de piedras previas; otras recogidas explícitas de12840 están ligadas a5510, no a esta misión."),
    2881: ("optional_repeat_inventory", "Entrega repetible opcional de collares sobrantes; el trabajo de recoger9259 está ligado a2880 en el paso anterior."),
    6031: ("optional_inventory_in_context", "La nota pide guardar treinta paños y tener reputación Neutral; no hay un goal de recogida separado."),
    8466: ("optional_inventory_in_context", "La nota del combate anterior pide guardar las plumas; la entrega es opcional."),
    8467: ("optional_inventory_in_context", "La ruta indica guardar plumas al combatir furbolgs; la entrega es opcional."),
    954: ("destination_credit", "La ruta lleva a las ruinas y al NPC de entrega; Codex registra un evento de descubrir ese lugar, no un combate omitido."),
    3377: ("npc_conversation_in_context", "Crédito de conversación en el lugar de aceptación/entrega; el tipo kill de Codex no autoriza a recomendar matar al NPC."),
    3441: ("npc_conversation_in_context", "La nota original pide escuchar la historia de Kalaran; no es un objetivo de combate ausente."),
    5742: ("npc_conversation_in_context", "La nota original pide escuchar a Tirion; el crédito NPC de Codex no debe convertirse en matar."),
    96392: ("npc_conversation_in_context", "La nota original pide hablar con Farsen para ver su visión."),
    4492: ("codex_route_disagreement", "La fuente usa4492 para encontrar a Ringo y4491 para escoltarlo; Codex atribuye la escolta a4492. Requiere verificación del cliente antes de corregir la ruta."),
    5321: ("escort_in_unbound_context", "La aceptación difiere la escolta; Ashenvale paso5 tiene goto+note con cuerno y sueño, sin questID. La continuidad real del NPC entre guías queda por verificar."),
    91772: ("optional_travel_clicks_in_context", "La nota de aceptación pide pulsar los rastros durante el viaje a Villadorada; no hay goal separado de trabajo ni se perdió al importar."),
}
DONATIONS = {7791, 7820, 7821, 7822, 7824, 7826, 7827, 7831, 7833, 7834, 7835, 7836}


def classify_work(document, events, missing_work, quest_records):
    by_quest = defaultdict(list)
    for occurrence in missing_work:
        by_quest[occurrence["questID"]].append(occurrence)
    all_by_quest = defaultdict(list)
    for event in events:
        if event["questID"]:
            all_by_quest[event["questID"]].append(event)
    paths, _, _ = route_paths(document["guides"])
    sides = {g["id"]: g.get("faction") for g in document["guides"]}
    cases, empty, unknown = [], [], []
    for qid in sorted(by_quest):
        record = quest_records.get(qid)
        if not record:
            unknown.append(qid)
            continue
        objectives = record.get("objectives") or []
        if not objectives:
            empty.append(qid)
            continue
        occurrences = by_quest[qid]
        factions = {sides[o["guideID"]] for o in occurrences}
        on_paths = {gid for path in paths if any(o["guideID"] in path for o in occurrences) for gid in path}
        item_ids = {o["id"] for o in objectives if o.get("type") == "item" and isinstance(o.get("id"), int) and o["id"] > 0}
        npc_ids = {o["id"] for o in objectives if o.get("type") == "kill" and isinstance(o.get("id"), int) and o["id"] > 0}
        unbound = [e for e in events if not e["questID"] and e["action"] not in ("accept", "turnin")
                   and (e["data"].get("item") in item_ids or e["data"].get("npc") in npc_ids)
                   and e["guideID"] in on_paths and sides[e["guideID"]] in factions]
        starts = {o.get("data", {}).get("item") for o in all_by_quest[qid] if o["action"] == "accept"}
        if document.get("provenance", {}).get("commit") == PIN and qid in CONTEXT:
            classification, explanation = CONTEXT[qid]
        elif unbound:
            classification, explanation = "unbound_work_goal", "Existen compras, recogidas o conversaciones explícitas por objeto/NPC sin questID; no faltan en la importación."
        elif item_ids and item_ids <= starts:
            classification, explanation = "item_start_already_carried", "El mismo objeto inicia la misión y es su requisito: debe existir antes de aceptar."
        elif document.get("provenance", {}).get("commit") == PIN and qid in DONATIONS:
            classification, explanation = "inventory_donation_in_context", "Donación de telas: las notas piden reservarlas, pero no hay un goal separado que guíe su obtención; entregar exige que el juego confirme los objetos."
        else:
            classification, explanation = "needs_manual_review", "Objetivos en la base original sin un goal de trabajo enlazado; las notas y las APIs del cliente requieren revisión."
        contexts = []
        for e in all_by_quest[qid]:
            texts = {key: e["data"][key] for key in ("note", "text") if e["data"].get(key)}
            if e["stepData"].get("note"):
                texts["stepNote"] = e["stepData"]["note"]
            if texts:
                contexts.append({**reference(e), **texts})
        cases.append({"questID": qid, "title": record.get("name") or record.get("title"), "objectives": objectives,
                      "classification": classification, "explanation": explanation, "occurrences": occurrences,
                      "questGoals": [reference(e) for e in all_by_quest[qid]], "unboundMatches": [reference(e) for e in unbound],
                      "contexts": contexts, "runtimeRisk": "Un turnin no demuestra que sus objetivos estén terminados; comprobar IsComplete/objetivos reales antes de dirigir exclusivamente al NPC."})
    return {"acceptOccurrencesWithoutQuestLinkedWork": len(missing_work), "uniqueQuestIDs": len(by_quest),
            "sourceQuestsWithoutObjectives": len(empty), "sourceQuestIDsWithoutObjectives": empty,
            "sourceQuestsWithObjectives": len(cases), "unknownQuestIDs": unknown,
            "classifications": dict(sorted(Counter(c["classification"] for c in cases).items())), "cases": cases}


def audit(document, source: Path | None = None, quest_records=None):
    guides = document["guides"]
    refs, verbs, dsl_steps, problems = source_refs(source, guides)
    events = events_for(guides, refs)
    order = scan_order(guides, events)
    if quest_records is None and source:
        from guide_coordinates import PinnedReference
        reference_data = PinnedReference(source, document)
        quest_records = {e["questID"]: reference_data.get("quest", e["questID"])
                         for e in order["noQuestLinkedFutureWork"]}
    work = classify_work(document, events, order.pop("noQuestLinkedFutureWork"), quest_records or {})
    historical_runtime_findings = []
    if document.get("provenance", {}).get("commit") == PIN and {5261, 415, 5241} <= {e["questID"] for e in events}:
        historical_runtime_findings = [{"kind": "closed_branch_delivery", "status": "reproduced_before_runtime_fix",
            "questIDs": [5261, 415, 5241],
            "trigger": "La aceptación queda omitida por closedBy, pero sus goals posteriores no heredan el cierre.",
            "impact": "5261 y5241 quedaban bloqueadas;415 pedía una entrega imposible al no haber sido aceptada.",
            "scope": "Interacción del motor con datos válidos, no pérdida ni cambio de orden en la importación. La corrección runtime y sus pruebas se verifican por separado.",
            "relatedCandidates": order["candidates"]["ordered_closed_branch"]}]
    return {"schemaVersion": 1, "sourceCommit": document.get("provenance", {}).get("commit"),
            "scope": {"guides": len(guides), "steps": sum(len(g["steps"]) for g in guides), "goals": len(events),
                      "questIDs": len({e["questID"] for e in events if e["questID"]}),
                      "actions": dict(sorted(Counter(e["action"] for e in events).items())),
                      "goalFields": {k: sum(k in e["data"] for e in events) for k in FIELDS},
                      "stepConditions": sum(bool(s.get("only")) for g in guides for s in g["steps"]),
                      "sourceDslSteps": dsl_steps, "sourceDslActions": verbs},
            "sourceComparison": compare_compiled(source, guides, document), "sourceReadProblems": problems,
            "order": order, "dependencyCycleCandidates": dependency_cycles(events), "workCoverage": work,
            "runtimeFindings": historical_runtime_findings,
            "limits": [
                "Es una auditoría estática, no una certificación de que el servidor ofrece cada misión o crédito.",
                "Se modela cada camino next por separado. No se unen prerrequisitos de rutas iniciales alternativas.",
                "Se prueban selectores de nueve clases y las razas de las guías; no se afirma que cada combinación clase/raza exista en el cliente.",
                "Los conteos de candidatos no son conteos de defectos. Entregas directas, inventario previo, conversación y contexto pueden ser correctos.",
                "El registro Codex también puede discrepar de la guía (ejemplo4492/4491); no se corrige contenido solo por tipo kill o por este informe.",
                "Las notas fuente se preservan, pero su redacción no prueba que el tracker muestre el trabajo en el momento adecuado.",
                "No se comprueba aquí la capacidad del diario, duración de escoltas/objetos, nivel dinámico ni disponibilidad real de NPCs.",
            ]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "RutaXP/Source/leveling.json")
    parser.add_argument("--source", type=Path, default=ROOT / ".sources/SendaFH")
    parser.add_argument("--output", type=Path, default=ROOT / "RutaXP/Source/guide_structure.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    raw = args.input.read_bytes()
    document = json.loads(raw.decode("utf-8-sig"))
    result = audit(document, args.source)
    result["inputSha256"] = sha(raw)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != encoded:
            raise SystemExit("Guide structure report is stale; rerun tools/audit_guide_structure.py")
    else:
        args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps({"guides": result["scope"]["guides"], "goals": result["scope"]["goals"],
                      "orderCandidates": result["order"]["counts"],
                      "workClassification": result["workCoverage"]["classifications"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
