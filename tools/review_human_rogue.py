"""Review the published Human Rogue path and build its quest-reward hints."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

from audit_guide_structure import fits, guide_fits, links
from audit_guides import navigation_kind
from guide_coordinates import PinnedReference

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "RutaXP/Source"
sys.path.insert(0, str(SOURCE))
from build_guides import lua_value

PERSONA = ("ROGUE", "Human", "Alliance")
START = "forever/alliance/human/01-elwynn-forest"
MELEE = {0: "Hacha", 4: "Maza", 7: "Espada", 13: "Arma de puño", 15: "Daga"}
RANGED = {2: "Arco", 3: "Arma de fuego", 16: "Arma arrojadiza", 18: "Ballesta"}
ACCESSORIES = {2: "Collar", 11: "Anillo", 12: "Abalorio", 16: "Capa"}
ACTION = dict(accept="Aceptar", turnin="Entregar", collect="Recoger", kill="Derrotar",
              complete="Completar", interact="Interactuar", train="Entrenar", talk="Hablar",
              use="Usar", fly="Volar", getfp="Registrar vuelo", sethome="Fijar hogar",
              hearth="Piedra de hogar", buy="Comprar", vendor="Vender", level="Nivel",
              goto="Ir", note="Indicación")
WARNINGS = dict(no_source_data="sin datos externos de requisitos", missing_prerequisite="posible previa adicional",
                prerequisite_conflict_review="fuentes en desacuerdo sobre previas",
                missing_active_parent="posible misión simultánea", source_omission_review="requisito sin corroboración",
                selector_conflict_review="discrepancia de clase o raza", level_conflict_review="discrepancia de nivel",
                additional_gate_review="condición adicional por verificar")


ORDER_REVIEW = """## Posibles ahorros en los otros 13 capítulos

Estas propuestas parten de los pasos de la versión 0.7.12. Para medir su efecto en partida hay que contar también caminos, esperas y tiempo de combate.

| Capítulo y pasos | Valoración | Recorrido que se podría probar |
|---|---|---|
| Desolace · 5–9 | Una vuelta menos al puesto | Tras los sátiros, visitar el cofre de Malem. Al regresar a Punta de Nijel se podrían entregar juntos los componentes a Kreldig y el encargo a Vahlarriel, y aceptar ambas continuaciones. |
| Vallefresno y Los Humedales · 8–16 | Una visita a Xavian | Una vez aceptada «Shared Fury» en el paso 11, conseguir la rama de Geltharis (#1031) y matar los sátiros (#98418) en la misma incursión. Los círculos de la Torre de Althalaxx conservan su secuencia. |
| Vega de Tuercespina · 22–25 | Depende del espacio en el diario | Antes de salir de Bahía del Botín, recoger «OPA hostil» y «La isla fantasma», y pasar por el barón para aceptar «La piedra de las mareas». Hacer la costa y el crocolisco en el mismo viaje, guardando su piel para entregarla a Drizzlik al volver. |
| Tierras Inhóspitas y Tierras del Interior · 13–15 | Desplazamiento corto | Al volver a Pico Nidal, entregar primero los collares a Fraggar y después las jaulas a Garracha. El siguiente vuelo sale hacia Puerto de Menethil. |
| Tanaris · 5, 10 y 19–21 | Depende de la aparición del objetivo | Recoger el encargo de Caliph Escorpijón (#2781) al visitar el cartel por primera vez. Si está en la zona y el grupo puede derrotarlo al pasar en el paso 10, aprovechar la ocasión. |
| Tierras del Interior, Tierras Devastadas y Loch Modan · 7 | Margen pequeño | Entregar los dos envíos a Lungertz en la misma conversación si ya están listos. Los destinatarios intermedios están muy cerca. Mantener el orden del encargo cronometrado de este capítulo. |
| La Garganta de Fuego · 1 y 10 | Margen pequeño | En el Puesto del Torio se pueden ordenar las paradas según la entrada y la salida. Los encargos de Hansel ya se recogen y entregan juntos. |
| Cráter de Un’Goro y Forjaz · 1, 12, 17 y 23 | Dos objetivos en la misma cueva | Si Torwa ofrece «Los simios de Un’Goro» (#4289) en la primera visita, aceptarla para recoger las tres pelambres durante el paso 12. Volver por las que falten si los gorilas no las sueltan todas. |
| Estepas Ardientes, Azshara y Tierras Devastadas · 8–11 | Depende del botín | Si ya han salido las runas de «El equipamiento perdido de Kim'jael» (#5534), volver a Kim'jael antes de completar las piedras. Desde las piedras se puede continuar hacia el piloto. |
| Frondavil · 7–11 | Depende de los enemigos que aparezcan | Si llevas los frascos de Laris, aprovechar los mocos que encuentres junto al camino de Jaedenar. La segunda entrada para recoger el agua necesita la entrega previa a Greta. |
| Cuna del Invierno y Tierras de la Peste del Este · 9–12 | Conservar la vuelta a Vista Eterna | Umi recibe el pelaje (#3783) antes de ofrecer el encargo de los cuernos (#977). En las ruinas de Kel’Theril (paso 3) queda por comprobar el camino entre los cuatro fragmentos. |
| Tierras de la Peste del Oeste, Tierras de la Peste del Este y Feralas · 8–17 | Reunir las tareas de dos granjas | Visitar a Janice (10) cuando se va al caldero de Piedra Mácula (13), antes de comprar el acelerador temporal. Hacer el diario y las llaves de Dalson (9) con el caldero de esa granja (16). Cada cadena mantiene sus entregas intermedias. |
| Silithus, Frondavil, Cuna del Invierno y Tierras de la Peste · 27–30 | Una visita al Fuerte Cenarion | Tras completar el Lexicón con Havunth, ir directamente al ermitaño Ortell. Con la piedra del paso 30 disponible y sitio en las bolsas, entregar al regresar al fuerte «Queridísima Natalia», la cartera de Noggle y «Un propósito terrible». |
"""


def route(document):
    by_id = {g["id"]: g for g in document["guides"]}
    visited = []
    guide = by_id[START]
    while True:
        if guide["id"] in visited or not guide_fits(guide, PERSONA):
            raise ValueError("Unexpected cycle or incompatible guide in human route")
        visited.append(guide["id"])
        yield guide
        targets = links(guide)
        if not targets:
            return
        if len(targets) != 1:
            raise ValueError("Review the new route alternatives explicitly")
        guide = by_id[targets[0]]


def gear(raw):
    if not raw:
        return
    fields = raw.split()
    inv, _, req, quality, cls, sub = map(int, fields[:6])
    stats = {}
    for token in fields[6:]:
        hit = re.fullmatch(r"([A-Za-z]+)(-?\d+(?:\.\d+)?)", token)
        if hit:
            stats[hit[1]] = float(hit[2])
    if quality < 1 or not (int(stats.get("cls", 8)) & 8):
        return
    weapon = None
    if inv in (13, 21, 22):
        weapon = MELEE.get(sub)
    elif inv in (15, 25, 26):
        weapon = RANGED.get(sub)
    if cls == 2 and weapon and stats.get("speed", 0) > 0:
        dps = (stats.get("dmin", 0) + stats.get("dmax", 0)) * 500 / stats["speed"]
        if dps > 0:
            result = dict(kind=weapon, stat="dps", value=round(dps, 1), inv=inv, level=req)
            if stats.get("agi", 0) > 0:
                result["agility"] = stats["agi"]
            return result
    kind = ACCESSORIES.get(inv)
    if sub == 2 and inv in (1, 3, 5, 6, 7, 8, 9, 10, 20):
        kind = "Cuero"
    if cls == 4 and kind:
        for stat in ("agi", "ap", "hit", "crit", "str"):
            if stats.get(stat, 0) > 0:
                return dict(kind=kind, stat=stat, value=stats[stat], inv=inv, level=req)


def ids(text):
    return [int(n) for n in text.split(",") if n]


def rewards(document, guides, upstream):
    ref = PinnedReference(upstream, document)
    stats, names = {}, {}
    database = {}
    ref.ns.ItemDB = ref.lua.table()
    ref.ns.ItemDB.Register = lambda _, rows: stats.update(rows.items())
    ref.ns.ItemDB.RegisterLeveling = lambda _, data: database.update(data.items())
    for filename in ("Items.lua", "Forever.lua"):
        ref._load("addon/SendaFH_ItemDB/" + filename)
    ref.ns.Names = ref.lua.table()
    ref.ns.Names.Add = lambda _, kind, rows: names.update(rows.items()) if kind == "item" else None
    ref._load("addon/SendaFH_Names_esES/Names.lua")
    quests = {q["quest"] for g in guides for s in g["steps"] if fits(s.get("only"), PERSONA)
              for q in s["goals"] if q["t"] in ("accept", "turnin") and fits(q.get("only"), PERSONA)}
    result = {}
    for qid in sorted(quests):
        row = database["quests"][qid]
        if row:
            head, choice, fixed, _ = row.split("|", 3)
            _, _, _, _, race, cls, _ = map(int, head.split())
            if (cls and not cls & 8) or (race and not race & 1):
                continue
            groups = [(False, ids(fixed)), (True, ids(choice))]
        else:
            info = ref.get("quest", qid)
            groups = [(False, info.get("rewards") or []), (True, info.get("choices") or [])]
        items = []
        for choice, item_ids in groups:
            for item in item_ids:
                value = gear(stats.get(item))
                if value and not any(record["id"] == item for record in items):
                    name = names.get(item) or database["names"][item] or ref.get("item", item).get("name")
                    if name:
                        items.append(dict(id=item, name=name, choice=choice, **value))
        if items:
            result[qid] = sorted(items, key=lambda r: (r["choice"], r["kind"] != "Daga", r["stat"] != "dps", r["id"]))
    return result


def write_or_check(path, content, check):
    if check:
        if path.read_text(encoding="utf8") != content:
            raise ValueError("Volver a generar " + path.name)
    else:
        path.write_text(content, encoding="utf8", newline="\n")


def reward_text(entries):
    parts = []
    for choice, label in ((False, "fija"), (True, "a elegir")):
        names = [entry["name"] for entry in entries if entry["choice"] == choice]
        if names:
            parts.append(label + " · " + ", ".join(names))
    return " / ".join(parts)


def review(guides, items, requirements, revisions):
    issues = defaultdict(set)
    for f in requirements["findings"]:
        issues[f["guideID"], f["step"], f["goal"]].add(WARNINGS.get(f["kind"], f["kind"]))
    summary, sections, totals = [], [], Counter()
    for guide in guides:
        gid = guide["id"]
        changed = next((r for r in reversed(revisions) if r["guideID"] == gid and r.get("preservePendingVisits")), None)
        sections.extend(["", f"## {guide['title']} ({guide['minLevel']}–{guide['maxLevel']})", ""])
        if changed:
            sections.extend([changed["evidence"]["reason"], ""])
        sections.extend(["| Paso y fila | Acción | Ubicación, condiciones y equipo |", "|---|---|---|"])
        total = applicable = 0
        for si, step in enumerate(guide["steps"], 1):
            rows = []
            for gi, goal in enumerate(step["goals"], 1):
                total += 1
                if not fits(step.get("only"), PERSONA) or not fits(goal.get("only"), PERSONA):
                    continue
                applicable += 1
                qid = goal.get("quest")
                action = goal["t"]
                label = goal.get("title") or goal.get("text") or goal.get("location") or goal.get("note") or step["title"]
                notes = []
                target = goal.get("itemName") or goal.get("target") or goal.get("objName") or goal.get("npcName")
                if isinstance(target, str) and target != label:
                    count = goal.get("count", 1)
                    notes.append(f"{target} ×{count}" if isinstance(count, (int, float)) and count > 1 else target)
                if goal.get("fromKind") == "pickpocket" and goal.get("note"):
                    notes.append(goal["note"])
                elif action == "collect" and isinstance(goal.get("from"), str):
                    notes.append(goal["from"])
                elif action in ("complete", "use", "interact") and goal.get("note") not in (None, label, target):
                    notes.append(goal["note"])
                if goal.get("minLevel"):
                    notes.append(f"desde nivel {goal['minLevel']}")
                for key, sep in (("preAll", " + "), ("pre", " o ")):
                    if goal.get(key):
                        notes.append("previa " + sep.join(map(str, goal[key])))
                if goal.get("optional"):
                    notes.append("opcional")
                if goal.get("profLine"):
                    notes.append(goal.get("profName") or "según profesión")
                mode = navigation_kind(goal)
                if mode == "direct":
                    notes.append(f"mapa {goal['map']} · {goal['x']:g}, {goal['y']:g}")
                elif mode in ("candidates", "spots", "conditional_navigation"):
                    notes.append("varios destinos o ubicaciones según objetivo")
                elif mode == "no_fixed_navigation":
                    notes.append("acción sin destino fijo")
                elif action in ("accept", "turnin", "kill", "collect", "complete", "interact") and not goal.get("item"):
                    notes.append("consultar indicación en el juego")
                if qid and action in ("accept", "turnin") and qid in items:
                    notes.append(reward_text(items[qid]))
                if qid == 65 and action in ("accept", "turnin"):
                    notes.append("cadena de mazmorra opcional · Túnica de Páramos de Poniente al terminar la misión 166")
                flags = issues[gid, si, gi]
                if flags:
                    notes.extend(sorted(flags))
                    totals["flagged"] += 1
                detail = " · ".join(str(text).replace("|", "/").replace("\n", " ") for text in notes)
                title = label.replace("|", "/").replace("\n", " ")
                rows.append(f"| {si}.{gi} | {ACTION[action]} · {title}" + (f" (#{qid})" if qid else "") + f" | {detail} |")
            if rows:
                sections.extend(rows)
            else:
                sections.append(f"| {si} | {step['title']} | Otra clase o raza |")
        summary.append(f"| {guide['title']} | {len(guide['steps'])} | {applicable} / {total} | " +
                       ("Recorrido ajustado" if changed else "Revisado") + " |")
        totals.update(steps=len(guide["steps"]), applicable=applicable, total=total)
    body = "\n".join(sections)
    return "\n".join(["# Ruta del pícaro humano", "",
        f"{len(guides)} capítulos, {totals['steps']} pasos y {totals['total']} acciones examinadas. "
        f"{totals['applicable']} acciones son compatibles por raza y clase, incluidas las opcionales.",
        "", f"En {len(items)} misiones del recorrido hay armas para el pícaro o cuero, capas y accesorios con atributos físicos. "
        "Desde nivel 10, la cadena de Keryn y Mathias Shaw da la Hoja de Astucia. "
        "Al aceptar o entregar una misión con equipo, pasa el ratón sobre la fila para ver qué recibes y qué puedes elegir.",
        "", "Si usas Mutilar, conserva una daga para cada mano. Las hachas de una mano también están disponibles "
        "para el pícaro de Forever tras aprender su manejo. [Cambios de clase de Blizzard](https://worldofwarcraft.blizzard.com/es-es/news/24310968).",
        "", "En Páramos de Poniente, la Hermandad de los Defias abre una cadena opcional para grupo. "
        "Con la misión final, entrega la cabeza de VanCleef tras hacer las Minas de la Muerte para elegir la "
        "Túnica de Páramos de Poniente (+11 agilidad y +5 aguante).",
        "", "Los números de paso y fila son los del addon. Las coordenadas usan el mapa del catálogo de origen. "
        f"Hay {totals['flagged']} filas con algún requisito pendiente de contrastar. Entre ellas siguen Lingotes Forjaluz (526) "
        "y Una fiesta en tu honor (1271). Los tiempos de viaje quedan pendientes de medir en el juego.",
        "", "| Capítulo | Pasos | Acciones compatibles / examinadas | Revisión |", "|---|---:|---:|---|",
        *summary, "", ORDER_REVIEW.rstrip(), "", body, ""])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / ".sources/SendaFH")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document, requirements, changes = [json.loads((SOURCE / name).read_text(encoding="utf8")) for name in
                                       ("leveling.json", "quest_requirements_audit.json", "guide_revisions.json")]
    guides = list(route(document))
    items = rewards(document, guides, args.source)
    lines = ["-- Generated by tools/review_human_rogue.py. See Licenses/PROVENANCE.txt.",
             "local _, ns = ...", "ns.rogueQuestRewards = {"]
    for qid, entries in items.items():
        lines.append(f"    [{qid}] = {lua_value(entries, compact=True)},")
    write_or_check(ROOT / "RutaXP/RogueRewardData.lua", "\n".join([*lines, "}", ""]), args.check)
    write_or_check(ROOT / "PICARO_HUMANO.md", review(guides, items, requirements, changes["revisions"]), args.check)
    print(f"{len(guides)} chapters, {len(items)} quests with documented rogue equipment.")


if __name__ == "__main__":
    main()
