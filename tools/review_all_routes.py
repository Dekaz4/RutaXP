"""Build the offline chapter and quest comparison for both factions."""
import argparse
from collections import defaultdict, Counter
import json
from pathlib import Path
import re
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
SOURCE = ROOT / "RutaXP/Source"
OUTPUT = ROOT / "REVISION_GUIAS.html"

STAGES = {"accept": "A", "turnin": "E"}
ACTIONS = {"accept": "Aceptar", "turnin": "Entregar", "collect": "Recoger", "kill": "Derrotar",
           "complete": "Completar", "objective": "Completar", "interact": "Interactuar", "use": "Usar",
           "fly": "Volar", "boat": "Tomar el barco", "goto": "Ir", "travel": "Viajar", "getfp": "Registrar vuelo",
           "hearth": "Usar la piedra", "sethome": "Fijar el hogar", "vendor": "Vender", "buy": "Comprar",
           "train": "Entrenar", "level": "Subir de nivel", "note": "Indicación", "talk": "Hablar"}
ISSUES = {"missing_prerequisite":"Posible previa adicional", "missing_active_parent":"Posible misión simultánea",
          "prerequisite_conflict_review":"Discrepancia de previas", "source_omission_review":"Requisito sin corroborar",
          "selector_conflict_review":"Discrepancia de raza o clase", "level_conflict_review":"Discrepancia de nivel",
          "additional_gate_review":"Requisito adicional por comprobar", "no_source_data":"Disponibilidad sin documentar"}


def load(path):
    return json.loads(path.read_bytes())


def independent_routes():
    facts = load(TOOLS / "route_comparison_facts.json")
    pages = []
    for source_id, path, _ in facts["files"]:
        _, repo, commit = facts["sources"][source_id]
        pages.append(f"https://github.com/{repo}/blob/{commit}/{quote(path)}")
    hits = defaultdict(list)
    for side, qid, source_id, entries in facts["rows"]:
        hits[side, qid].append([facts["sources"][source_id][0], entries])
    sage = load(TOOLS / "route_review_alliance_late_sage.json")
    stages = defaultdict(dict)
    for page in sage["pages"]:
        file_id = len(pages)
        pages.append(page["url"])
        for field, tag in (("accept","A"), ("work","O"), ("turnin","E")):
            for qid in page[field]:
                stages[qid].setdefault(tag, [file_id, None, None])
    for qid, entries in stages.items():
        hits["Alliance", qid].append(["Sage", entries])
    return hits, pages


def evidence_link(record, metadata):
    for field in ("preAll", "pre", "minLevel", "parent", "classMask", "raceMask", "startItem"):
        sources = record.get("fieldSources", {}).get(field, [])
        if sources:
            ref = sources[0]
            return metadata[ref["source"]]["url"] + "#L" + str(ref["line"])
    return ""


def format_requirement(value):
    if value is None:
        return "sin dato"
    if isinstance(value, dict):
        if "any" in value or "all" in value:
            parts = [" + ".join(map(str, value.get("all", []))), " o ".join(map(str, value.get("any", [])))]
            return " / ".join(filter(None, parts)) or "ninguna indicada"
        return ", ".join(f"{k} {v}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(map(str, value)) or "ninguno"
    return str(value)


def local_verdict(goals, stages, group, needed):
    if group:
        return "Grupo opcional", "Solo se propone combatir si activas las misiones de grupo. Puedes entregar una que ya tengas lista."
    slow = [g for g in goals if g.get("levelingDetour")]
    if slow:
        levels = sorted({g["detourBelowLevel"] for g in slow if g.get("detourBelowLevel")})
        if levels:
            return "Según el nivel", f"En solitario se aplaza el tramo difícil hasta el nivel {levels[-1]}."
        if any(g.get("detourItems") for g in slow):
            return "Si llevas los materiales", "Aprovecha el paso por el personaje cuando tengas lo necesario en la mochila."
        return "Desvío opcional", "La ruta rápida permite seguir con las demás tareas y aprovechar después una entrega lista."
    after = next((g["soloAfter"] for g in goals if g.get("soloAfter")), None)
    if after:
        return "Si hiciste la previa", "Se incorpora al itinerario al entregar " + ", ".join(map(str, after)) + " o si ya llevas el encargo."
    if all(g.get("optional") for g in goals):
        return "Opcional", "El capítulo deja esta tarea a elección del jugador."
    if needed:
        return "Conservar la cadena", "Hay continuaciones en la ruta que citan esta misión entre sus requisitos."
    if "A" not in stages and "E" in stages:
        return "Aprovechar la entrega", "El capítulo reserva una visita para una misión que puede venir de un tramo anterior."
    if "A" in stages and "O" not in stages and "E" in stages:
        return "Recogida y entrega", "El capítulo incluye ambas conversaciones. Comprueba en el diario el trabajo intermedio."
    return "Mantener el recorrido", "Conservar los pasos indicados en este capítulo."


def compare_visit_order(guide, missions, hits):
    """Compare successive conversations of the same type in a shared reference section."""
    previous = {}
    counts = Counter()
    for si, step in enumerate(guide["steps"], 1):
        for goal in step["goals"]:
            qid, npc = goal.get("quest"), goal.get("npc")
            stage = STAGES.get(goal["t"])
            if not qid or not npc or not stage:
                continue
            prior = previous.get(stage)
            previous[stage] = (si, npc, qid)
            if not prior:
                continue
            old_step, old_npc, old_qid = prior
            if npc == old_npc or qid == old_qid or si - old_step > 3:
                continue
            old_hits = dict(hits.get((guide["faction"], old_qid), []))
            for source, entries in hits.get((guide["faction"], qid), []):
                first = old_hits.get(source, {}).get(stage)
                second = entries.get(stage)
                # Sage identifies pages, not numbered positions within a route.
                if not first or not second or len(first) < 4 or len(second) < 4:
                    continue
                if first[0] != second[0] or not first[3] or first[3] != second[3]:
                    continue
                counts["checked"] += 1
                if first[1] > second[1]:
                    counts["different"] += 1
                    missions[qid].setdefault("order", []).append(
                        [source, stage, old_qid, old_step, si, first[0], first[1], second[1]])
    return dict(counts)


def make_report():
    if __package__:
        from . import route_review_horde, route_review_alliance_start, route_review_alliance_late, unmatched_solo
    else:
        import route_review_horde, route_review_alliance_start, route_review_alliance_late, unmatched_solo
    reviews = (route_review_horde, route_review_alliance_start, route_review_alliance_late)
    solo = unmatched_solo.decisions()
    references = {key: value for module in reviews for key, value in module.REFERENCES.items()}
    notes = {key: value for module in reviews for key, value in module.NOTES.items()}
    doc = load(SOURCE / "leveling.json")
    evidence = load(SOURCE / "quest_requirements_evidence.json")
    audits = load(SOURCE / "quest_requirements_audit.json")
    findings = defaultdict(list)
    for row in audits["findings"]:
        text = ISSUES[row["kind"]]
        if row["kind"] != "no_source_data":
            text += f" ({format_requirement(row.get('authored'))} en RutaXP / {format_requirement(row.get('reported'))} en la referencia)"
        if text not in findings[row["guideID"], row["questID"]]:
            findings[row["guideID"], row["questID"]].append(text)
    hits, pages = independent_routes()
    groups = set(map(int, re.findall(r"\[(\d+)\]\s*=\s*true", (ROOT / "RutaXP/GroupQuestData.lua").read_text(encoding="utf8"))))
    groups.discard(3380)  # The outdoor conversation with Marvon is solo in QuestEngine.
    timing = (ROOT / "RutaXP/EarlyQuestData.lua").read_text(encoding="utf8")
    early = set(map(int, re.findall(r"\[(\d+)\]\s*=\s*true", timing.split("ns.deferredQuestOffers")[0])))
    delayed = dict((int(q), why) for q, why in re.findall(r'\[(\d+)\]\s*=\s*"([^"]+)"', timing.split("ns.deferredQuestOffers = {")[1].split("\n}")[0]))
    distinct, matched, examined_notes = set(), set(), set()
    dependents = defaultdict(set)
    quest_names = {}
    for guide in doc["guides"]:
        for step in guide["steps"]:
            for goal in step["goals"]:
                if goal["t"] in ("accept", "turnin") and goal.get("quest") and goal.get("title"):
                    quest_names.setdefault((guide["faction"], goal["quest"]), goal["title"])
                if goal["t"] == "accept" and goal.get("quest"):
                    for pre in (goal.get("pre", []) + goal.get("preAll", []) + [goal.get("parent")]):
                        if pre:
                            dependents[guide["faction"], abs(pre)].add(goal["quest"])
    chapters, totals = [], Counter()
    for guide in doc["guides"]:
        gid, side = guide["id"], guide["faction"]
        if not references.get(gid):
            raise ValueError(f"Chapter without a reviewed reference: {gid}")
        missions, auxiliary = {}, []
        prior_visits, deliveries = defaultdict(list), defaultdict(set)
        for si, step in enumerate(guide["steps"], 1):
            for gi, goal in enumerate(step["goals"], 1):
                action = goal["t"]
                totals["actions"] += 1
                npc = goal.get("npc")
                if npc and action in ("accept", "turnin", "talk","vendor","train","sethome","getfp"):
                    prior_visits[npc].append((si, action))
                qid = goal.get("quest") or goal.get("workForQuest") or goal.get("detourQuest")
                here = f"{si}.{gi}"
                if not qid:
                    text = goal.get("note") or goal.get("text") or goal.get("location") or goal.get("npcName") or step["title"]
                    condition = (f"Hasta el nivel {goal['untilLevel']}" if goal.get("untilLevel") else
                                 "Opcional en solitario" if goal.get("levelingDetour") else "Opcional" if goal.get("optional") else "")
                    auxiliary.append([here, ACTIONS[action], text, condition])
                    continue
                if qid not in missions:
                    missions[qid] = {"id": qid, "name": "", "steps": [], "instructions": [], "goals": [], "requirements": [], "picks": [], "hands": [], "visits": []}
                row = missions[qid]
                stage = STAGES.get(action, "O")
                if goal.get("title") and not row["name"]:
                    row["name"] = goal["title"]
                row["steps"].append([here, stage])
                row["instructions"].append(goal.get("instruction") or goal.get("note") or step["title"])
                row["goals"].append(goal)
                if action == "turnin" and npc:
                    deliveries[si, npc].add(qid)
                if action in ("accept", "turnin"):
                    contact = goal.get("npcName") or goal.get("objName") or goal.get("itemName")
                    contacts = row["picks" if action == "accept" else "hands"]
                    if contact and contact not in contacts:
                        contacts.append(contact)
                for field, label, sep in (("preAll","Previas"," + "), ("pre","Previa"," o "), ("parent","En diario",""), ("minLevel","Nivel mínimo","")):
                    val = goal.get(field)
                    if val:
                        text = label + " " + (sep.join(str(abs(v)) for v in val) if isinstance(val, list) else str(val))
                        if text not in row["requirements"]:
                            row["requirements"].append(text)
                for key in ("classes", "races"):
                    for obj in (step, goal):
                        values = (obj.get("only") or {}).get(key)
                        if values:
                            text = ("Clase " if key == "classes" else "Raza ") + ", ".join(values)
                            if text not in row["requirements"]:
                                row["requirements"].append(text)
        for qid, row in missions.items():
            distinct.add(qid)
            goals = row.pop("goals")
            for (place, stage), goal in zip(row["steps"], goals, strict=True):
                si = int(place.split(".")[0])
                npc = goal.get("npc")
                if stage == "A" and qid in delayed:
                    row["visits"].append(f"Recogida en el paso {si}. {delayed[qid]}")
                if stage == "A" and npc and qid in early:
                    earlier = [s for s, _ in prior_visits[npc] if s < si]
                    if earlier:
                        row["visits"].append(f"Ya visitas al mismo personaje en el paso {max(earlier)}. Si ofrece la misión, hay sitio y cumples las condiciones, RutaXP permite adelantar la recogida del paso {si}.")
                if stage == "E" and npc:
                    peers = sorted(deliveries[si,npc] - {qid})
                    if peers:
                        row["visits"].append(f"Entrega agrupada en el paso {si} con " + ", ".join(map(str, peers)) + ".")
            row["name"] = quest_names.get((side, qid)) or row["name"] or f"Misión {qid}"
            row["routes"] = hits.get((side,qid), [])
            if row["routes"]:
                matched.add(qid)
                totals["compared"] += 1
            row["children"] = sorted(dependents.get((side,qid), set()))
            row["issues"] = findings.get((gid,qid), [])
            row["evidence"] = evidence_link(evidence["quests"].get(str(qid), {}), evidence["sources"])
            row["decision"], row["reason"] = local_verdict(goals, {s for _,s in row["steps"]},
                qid in groups or any(g.get("group") for g in goals), row["children"])
            if qid in solo:
                case = solo[qid]
                row["solo"] = [case["policy"], case["reason"], case["url"]]
            editorial = notes.get((gid, qid))
            if editorial:
                examined_notes.add((gid,qid))
                row["review"] = [editorial["decision"], editorial["reason"], editorial["url"]]
            totals["missions"] += 1
        order = compare_visit_order(guide, missions, hits)
        totals["visitPairs"] += order.get("checked", 0)
        totals["differentOrder"] += order.get("different", 0)
        chapters.append({"id":gid, "title":guide["title"], "side":side, "order":order,
                         "levels":f"{guide['minLevel']}–{guide['maxLevel']}", "n":len(guide["steps"]),
                         "refs":references[gid], "quests":list(missions.values()), "other":auxiliary})
    unused = set(notes) - examined_notes
    if unused:
        raise ValueError(f"Editorial notes do not match the catalog: {sorted(unused)}")
    if distinct - matched != solo.keys():
        raise ValueError(f"Solo decisions do not cover the unmatched set: {sorted((distinct - matched) ^ solo.keys())}")
    totals["soloReviewed"] = len(solo)
    return {"chapters":chapters, "pages":pages, "totals":dict(totals, distinct=len(distinct), matched=len(matched))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = make_report()
    data = json.dumps(report, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    page = (TOOLS / "route_review_template.html").read_text(encoding="utf8").replace("/*ROUTE_DATA*/", data)
    if args.check:
        if OUTPUT.read_text(encoding="utf8") != page:
            raise SystemExit("Regenerate REVISION_GUIAS.html")
    else:
        OUTPUT.write_text(page, encoding="utf8", newline="\n")
    print(report["totals"])


if __name__ == "__main__":
    main()
