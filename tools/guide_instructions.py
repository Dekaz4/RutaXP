#!/usr/bin/env python3
"""Deterministic Spanish presentation for authored goals; Python stdlib only.

The input is evidence, not a set of mechanics to infer. Only ``instruction``,
``instructionVerb``, ``instructionAsHint`` and ``instructionReplacesContext`` are generated. IDs, actions, conditions, coordinates,
notes and text remain unchanged, including explicit caveats and prerequisites.
Step-wide notes belong to the runtime's current-step presentation, rather than
being copied into every objective. No game state or completion is generated.
"""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
import json
import math
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "RutaXP" / "Source" / "leveling.json"
PINNED_COMMIT = "5d207e28e82e2c529143b21ace74fe88692f0067"
GENERATED_FIELDS = frozenset({"instruction", "instructionVerb", "instructionAsHint", "instructionReplacesContext"})
_TAMING = re.compile(r"^(?:tame\s+(?:with|con)|domestica(?:r)?|domar)\b", re.IGNORECASE)
_ENGLISH = re.compile(
    r"\b(?:the|and|then|with|from|inside|outside|until|before|after|near|click|cast|use|"
    r"kill|loot|collect|buy|return|follow|travel|wait|boat|next|tame|escort|cave|entrance)\b",
    re.IGNORECASE,
)
_NAMES = ("npcName", "itemName", "target", "objName", "objectName", "location", "title")
_PROFESSIONS = {"Cooking": "Cocina", "First Aid": "Primeros auxilios", "Fishing": "Pesca"}
_DWARF_TAMING_TARGETS = {6064: 1126, 6084: 1201, 6085: 1196}
_DWARF_TAMING_NOTE = re.compile(r":\s*(?:tame\s+it\s+with|domesticarlo\s+con)\b", re.IGNORECASE)
# Dun Morogh, source lines 581–583. Forever can offer the turn-in while the
# player still sees Narm lying down, so retain the item action in both phases.
_NARM_HINTS = {
    "complete": "Selecciona a Narm Faulk en la orilla del lago y usa el Símbolo de la Vida de tu mochila.",
    "turnin": "Si Narm Faulk sigue caído, usa el Símbolo de la Vida sobre él. Cuando se levante, habla con él.",
}

# Narrow, audited presentation exceptions. Evidence is pinned SendaFH commit
# 5d207e28e82e2c529143b21ace74fe88692f0067: guides/forever/*.guide tips and
# addon/SendaFH_Codex/Quests1.lua/Quests2.lua decoded by Lookup/Codex.lua.
# The source file/line/SHA and exact decoded objective are recorded in
# RutaXP/Source/guide_instructions_evidence.json. No coordinates or quest logic change.
DOCUMENTED_INSTRUCTIONS = {
    99159: "Recoge 14 leños de los troncos caídos en la nieve alrededor del lago de Refugio Pinobruma. Después entrégalos al Padre Gavin.",
    98326: "Consigue 1 «Sack of Fish», el objeto que requiere esta misión; comprueba su progreso en el registro.",
    1440: "Rescata a «Dalinda Malem»; comprueba el objetivo de rescate en el registro antes de regresar.",
    99134: "Motiva a 5 «Deathguards». Consulta el texto de la misión para ver la acción concreta; no basta con llegar al personaje que la ofrece.",
    1046: "Comprueba que tienes en las bolsas «Calavera de Ran Sangradientes» y «Vara de transformación de Dartol». Ambos son requisitos de esta misión; la vara procede de una misión anterior de la cadena.",
    5149: "Reúne la cabeza, la parte izquierda y la parte derecha de la muñeca de Pamela en las casas de Villa Darrow. Combina las tres piezas desde tus bolsas para crear «Muñeca de Pamela». Al recogerlas pueden aparecer fantasmas.",
    5051: "Consigue «La otra mitad del talismán de buena suerte» de los necrófagos farfullantes de Campo de Piedramácula. Combínala en tus bolsas con «Mitad de talismán de buena suerte» para formar «Talismán de buena suerte».",
    3786: "Reúne 10 «Mañagrana» mediante el cultivo con «Faltriquera de siempre verde» y Tierra de Un'Goro. Comprueba lo que requiere la faltriquera; la mañagrana es un resultado del cultivo, no un objeto fijo del suelo.",
    3804: "Reúne la cantidad de «Mañagrana» que pida el registro mediante el cultivo con «Faltriquera de siempre verde» y Tierra de Un'Goro. Comprueba el resultado y los requisitos en tus bolsas antes de entregarla.",
    91899: "Necesitas «Sealed Apprentice Crate» (objeto 248765). Verifica los materiales de la caja y el requisito del registro antes de entregarla. Las notas de la fuente discrepan sobre cómo obtenerla; no se ha documentado un punto de recogida.",
    91904: "Necesitas «Sealed Apprentice Crate» (objeto 248770). Verifica los materiales de la caja y el requisito del registro antes de entregarla. Las notas de la fuente discrepan sobre cómo obtenerla; no se ha documentado un punto de recogida.",
    6022: "Recoge 7 «Caña viva» de la Plaga de Cruce de Corin. Usa «Mano y almirez» para triturarlas y obtener «Putrefacción coagulada» antes de que pasen 10 minutos: las muestras caducan.",
    94568: "Habla con «Talaanis Shadowsong» y sigue su conversación. El crédito de esta misión se obtiene al hablar; no debes atacar al personaje.",
    92640: "Habla con «Valennia Stormfist», «Ayessa Dawnsinger» y «Elaadrin Evengale» para reunirlos. La guía sitúa a Ayessa al oeste del poblado. Comprueba las tres conversaciones en el registro; no debes atacar a estos personajes.",
    6001: "En la Piedra de lechúcico lunar de Costa Oscura, usa «Polvo lunar Cenarion» (objeto 15208), derrota a Garraluna y habla después con el Espíritu de Garraluna. La conversación con el espíritu forma parte del objetivo.",
    6002: "En la Piedra de lechúcico lunar del paso de Mulgore a Los Baldíos, usa «Polvo lunar Cenarion» (objeto 15710), derrota a Garraluna y habla después con el Espíritu de Garraluna. La conversación con el espíritu forma parte del objetivo.",
    96873: "Si tienes Encantamiento, desencanta «Hexed Pendant» (objeto 275724), que sueltan los trols de las Islas del Eco, para reunir 3 «Luminous Residue». No son residuos que se recojan directamente del suelo; esta misión es opcional y requiere desencantar los colgantes.",
    92474: "Usa la habilidad «Walk on Air» indicada por la misión y comprueba su objetivo en el registro. Es una acción de tu personaje; no tiene un punto fijo de recogida.",
}


def visible_text(value: Any) -> str:
    """Remove WoW presentation markup without removing its readable warning."""
    if not isinstance(value, str):
        return ""
    text = re.sub(r"\|H[^|]*\|h(.*?)\|h", r"\1", value, flags=re.DOTALL)
    text = re.sub(r"\|[TA][^|]*\|[ta]", "", text)
    text = re.sub(r"\|c[0-9a-fA-F]{8}|\|cRXP_[A-Z_]+|\|r", "", text)
    return text.strip()


def _name(goal: Mapping[str, Any], *keys: str) -> str:
    return next((name for key in keys if (name := visible_text(goal.get(key)))), "")


def _quote(value: str) -> str:
    return f"«{value}»"


def _sentence(value: str) -> str:
    value = value.strip()
    return value if not value or value[-1] in ".!?…:" else value + "."


def _normal(value: str) -> str:
    return value.casefold().strip().rstrip(".! ")


def _count(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        return ""
    return f"{value:g}"


def _quantity(goal: Mapping[str, Any]) -> str:
    count = _count(goal.get("count"))
    return f" ({count} en total)" if count else ""


def _is_label(text: str, goal: Mapping[str, Any]) -> bool:
    return any(_normal(text) == _normal(name) for key in _NAMES if (name := visible_text(goal.get(key))))


def _details(goal: Mapping[str, Any]) -> list[str]:
    # ``text`` sometimes holds a required cast/use action; ignoring it loses
    # mechanics even when a perfectly good NPC/object label is available.
    out, seen = [], set()
    for field in ("note", "text", "click"):
        text = visible_text(goal.get(field))
        if text and not _is_label(text, goal) and _normal(text) not in seen:
            out.append(text)
            seen.add(_normal(text))
    return out


def _documented_dwarf_taming(goal: Mapping[str, Any], source_commit: str | None) -> bool:
    # The pinned DSL deliberately encodes taming credit as `kill`. Its three
    # Dun Morogh notes put the explicit rod action AFTER the creature's name.
    # Do not infer taming from the database's generic kill-credit objective.
    quest = goal.get("quest") or goal.get("questID")
    return (source_commit == PINNED_COMMIT and quest in _DWARF_TAMING_TARGETS
            and (goal.get("t") or goal.get("action")) == "kill" and goal.get("oi") == 1
            and goal.get("npc") == _DWARF_TAMING_TARGETS[quest]
            and any(_DWARF_TAMING_NOTE.search(text) for text in _details(goal)))


def instruction_verb(goal: Mapping[str, Any], *, source_commit: str | None = PINNED_COMMIT) -> str | None:
    """An explicit source instruction may correct a display verb, never ``t``."""
    if _documented_dwarf_taming(goal, source_commit) or (
            (goal.get("t") or goal.get("action")) == "kill" and any(_TAMING.search(text) for text in _details(goal))):
        return "Domestica"
    return None


def _present_detail(text: str, action: str) -> str:
    # Translate only explicit leading action syntax, not entity/spell names or
    # arbitrary English prose. The original note/text fields are retained.
    if action == "kill" and _TAMING.search(text):
        text = re.sub(r"^Tame\s+con\s+(?:el|la)\s+", "Usa ", text, flags=re.IGNORECASE)
        if text.startswith("Usa "):
            return _sentence(text + " para domesticar al objetivo")
    match = re.fullmatch(r"Cast\s+(.+?)\s+(?:on the|on|en el|en la|sobre)\s+(.+)", text, re.IGNORECASE)
    if match:
        return f"Lanza {_quote(match[1])} sobre {_quote(match[2].rstrip('.'))}."
    if text.startswith("/sit "):
        rest = re.sub(r"^(?:by|por)\s+", "junto a ", text[5:], flags=re.IGNORECASE)
        return _sentence("Escribe /sit " + rest)
    replacements = ((r"^Next:\s*", "Después: "), (r"^Boat\s+(?:to|a)\s+", "Barco a "),
                    (r"^Cast\s+", "Lanza "), (r"^Use\s+", "Usa "), (r"^Fill\s+", "Llena "))
    for pattern, replacement in replacements:
        if re.search(pattern, text):
            return _sentence(re.sub(pattern, replacement, text, count=1))
    return _sentence(text)


def _quest(goal: Mapping[str, Any]) -> str:
    title = _name(goal, "title")
    if title:
        return _quote(title)
    quest_id = goal.get("quest") or goal.get("questID")
    return f"la misión {quest_id}" if isinstance(quest_id, int) and not isinstance(quest_id, bool) else "esta misión"


def _narm_hint(goal: Mapping[str, Any], source_commit: str | None) -> str | None:
    if source_commit == PINNED_COMMIT and goal.get("quest") == 1783:
        return _NARM_HINTS.get(goal.get("t"))
    return None


def instruction_for(goal: Mapping[str, Any], zone_name: str | None = None, *, source_commit: str | None = PINNED_COMMIT) -> str:
    """Return concrete guidance supported by this goal's authored data only."""
    if not isinstance(goal, Mapping):
        raise TypeError("A goal must be a mapping")
    hint = _narm_hint(goal, source_commit)
    if hint:
        return hint
    action = goal.get("t") or goal.get("action") or "note"
    npc, item = _name(goal, "npcName"), _name(goal, "itemName")
    obj, target = _name(goal, "objName", "objectName"), _name(goal, "target")
    location = _name(goal, "location")
    details = _details(goal)
    quest = _quest(goal)
    count = _quantity(goal)
    if action == "accept":
        if goal.get("item") or item:
            label = _quote(item) if item else f"el objeto {goal['item']}"
            base = f"Si tienes {label} en tus bolsas, haz clic derecho en él para iniciar {quest}."
        elif obj:
            base = f"Interactúa con {_quote(obj)} y acepta {quest}."
        elif npc:
            base = f"Habla con {_quote(npc)} y acepta {quest}."
        else:
            base = f"Acepta {quest}; esta guía no especifica quién la ofrece."
    elif action == "turnin":
        if npc:
            base = f"Habla con {_quote(npc)} y entrega {quest}."
        elif obj:
            base = f"Interactúa con {_quote(obj)} para entregar {quest}."
        else:
            base = f"Revisa en tu registro dónde entregar {quest}; la guía no identifica al destinatario."
    elif action == "kill":
        verb = instruction_verb(goal, source_commit=source_commit) or "Derrota"
        label = _quote(target or npc) if target or npc else "los enemigos del objetivo indicado en el registro"
        if _documented_dwarf_taming(goal, source_commit):
            base = (f"Domestica a {label}{count} usando la «Fusta de domador» que te entrega «Grif Corazón Salvaje». "
                    "Después vuelve a Grif para entregar la misión.")
        else:
            base = f"{verb} a {label}{count}."
    elif action == "collect":
        label = _quote(item) if item else "los objetos del objetivo indicado en el registro"
        sources = list(dict.fromkeys(filter(None, (visible_text(goal.get("from")), visible_text(goal.get("fromAlso"))))))
        source = " o ".join(_quote(name) for name in sources)
        if source and goal.get("fromKind") == "npc":
            base = f"Recoge {label}{count} del botín de {source}."
        elif (source and goal.get("fromKind") == "object") or obj:
            base = f"Interactúa con {source or _quote(obj)} para reunir {label}{count}."
        else:
            base = f"Reúne {label}{count}."
            if source:
                base += f" Procedencia indicada por la guía: {source}."
    elif action in ("complete", "objective"):
        documented = (DOCUMENTED_INSTRUCTIONS.get(goal.get("quest") or goal.get("questID"))
                      if not goal.get("oi") and source_commit == PINNED_COMMIT else None)
        if documented:
            base = documented
        elif details:
            base = f"Para {quest}, sigue esta indicación de la guía:"
        else:
            base = f"Abre {quest} en el registro y sigue los objetivos que indique el juego."
            if obj or target:
                base += f" Objetivo indicado: {_quote(obj or target)}."
    elif action == "interact":
        # Cast instructions are more specific than the generic interact type.
        if any(re.match(r"^(?:Cast|Lanza|Usa|Use|Canaliza)\b", text, re.IGNORECASE) for text in details):
            base = f"Acción indicada para {quest}:" if goal.get("quest") or goal.get("questID") else "Acción indicada:"
        else:
            base = f"Interactúa con {_quote(obj or npc or target)}." if obj or npc or target else "Interactúa con el objeto indicado en el registro de esta misión."
    elif action == "use":
        label = _quote(item) if item else (f"el objeto {goal['item']}" if goal.get("item") else "el objeto indicado por la misión")
        base = f"Usa {label}" + (f" sobre {_quote(target or obj)}" if target or obj else "") + "."
    elif action == "talk":
        base = f"Habla con {_quote(npc or target)}." if npc or target else "Habla con el personaje indicado por la misión."
    elif action == "buy":
        label = _quote(item) if item else "el objeto indicado por la guía"
        base = f"Compra {label}{count}" + (f" a {_quote(npc)}" if npc else "") + "."
    elif action == "sethome":
        who = _quote(npc) if npc else "el tabernero"
        base = f"Habla con {who}" + (f" en {_quote(location)}" if location else "") + " y elige fijar allí tu hogar."
    elif action == "hearth":
        base = (f"Comprueba que tu piedra de hogar está vinculada a {_quote(location)} y úsala para regresar allí."
                if location else "Usa tu piedra de hogar para regresar al lugar al que esté vinculada.")
    elif action == "getfp":
        who = _quote(npc) if npc else "el maestro de vuelo"
        base = f"Habla con {who}" + (f" en {_quote(location)}" if location else "") + " y aprende la ruta de vuelo."
    elif action == "fly":
        origin = visible_text(goal.get("from"))
        who = _quote(npc) if npc else "un maestro de vuelo"
        base = f"Habla con {who}" + (f" en {_quote(origin)}" if origin else "") + ", abre el mapa de vuelos y selecciona "
        base += _quote(location) + "." if location else "el destino indicado por la guía."
    elif action == "train":
        profession = _name(goal, "profName", "skill")
        if profession:
            profession = _PROFESSIONS.get(profession, profession)
            base = f"Visita a {_quote(npc)}" if npc else f"Visita a un instructor de {_quote(profession)}"
            base += f" y revisa el aprendizaje de {_quote(profession)}."
        else:
            base = (f"Visita a {_quote(npc)}" if npc else "Visita al instructor de tu clase") + " y revisa las habilidades disponibles."
    elif action == "vendor":
        who = _quote(npc) if npc else "un vendedor"
        base = f"Abre el comercio con {who} para vender; repara tu equipo si ofrece reparación."
    elif action == "level":
        level = _count(goal.get("level") or goal.get("n"))
        base = f"Gana experiencia hasta alcanzar el nivel {level}." if level else "Gana la experiencia indicada por este paso."
    elif action == "goto":
        destination = location or visible_text(goal.get("text")) or obj
        if destination and re.match(r"^(?:Boat|Barco)\s+(?:a|to)\b", destination, re.IGNORECASE):
            base = _sentence(re.sub(r"^(?:Boat|Barco)\s+(?:a|to)\s+", "Toma el barco a ", destination, flags=re.IGNORECASE))
            details = [text for text in details if _normal(text) != _normal(destination)]
        else:
            base = f"Dirígete al punto de la ruta: {_quote(destination)}." if destination else "Dirígete al punto de paso indicado por la ruta."
            if destination:
                details = [text for text in details if _normal(text) != _normal(destination)]
    elif action == "note":
        base = "" if details else (_name(goal, "text", "note", "title") or "Consulta la indicación de este paso antes de continuar.")
    else:
        base = "Consulta la indicación de este paso en la guía."
    parts = [base] if base else []
    # The document caller supplies a zone only when its map/name pair is
    # evidenced. Never print raw Era percentages as if they were live ones.
    if zone_name and goal.get("map") is not None and action not in ("fly", "hearth", "level", "note"):
        parts.append(f"Zona: {visible_text(zone_name)}.")
    parts.extend(_present_detail(text, action) for text in details)
    hint = visible_text(goal.get("navigationHint"))
    if hint and _normal(hint) not in {_normal(text) for text in details}:
        parts.append("Acceso o lugar: " + _sentence(hint))
    if goal.get("group"):
        group = _count(goal["group"])
        parts.append(f"La guía recomienda un grupo de {group}." if group else "La guía recomienda hacerlo en grupo.")
    if goal.get("optional") is True:
        parts.insert(0, "Opcional.")
    return "\n".join(parts)


def enrich_goal(goal: Mapping[str, Any], zone_name: str | None = None, *, source_commit: str | None = PINNED_COMMIT) -> dict[str, Any]:
    result = deepcopy(dict(goal))
    result["instruction"] = instruction_for(goal, zone_name, source_commit=source_commit)
    if _narm_hint(goal, source_commit):
        result["instructionAsHint"] = True
    else:
        result.pop("instructionAsHint", None)
    verb = instruction_verb(goal, source_commit=source_commit)
    if verb:
        result["instructionVerb"] = verb
    elif result.get("instructionVerb") == "Domestica":
        result.pop("instructionVerb")
    # The old crate step contradicts the separately sourced reputation guide.
    # Retain its raw note/text for audit; suppress its unsafe display only for
    # these two reviewed crate quests, never arbitrary other context.
    replaces = (source_commit == PINNED_COMMIT and (goal.get("t") or goal.get("action")) in ("accept", "turnin", "complete", "objective")
                and not goal.get("oi") and (goal.get("quest") or goal.get("questID")) in (91899, 91904))
    if replaces:
        result["instructionReplacesContext"] = True
    else:
        result.pop("instructionReplacesContext", None)
    return result


def enrich_document(document: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(document))
    guides = result.get("guides")
    if not isinstance(guides, list):
        raise ValueError("Expected a guides array")
    provenance = document.get("provenance", {})
    source_commit = provenance.get("commit") if isinstance(provenance, Mapping) else None
    names: dict[Any, set[str]] = {}
    for guide in guides:
        if guide.get("zone") is not None and (name := visible_text(guide.get("zoneName"))):
            names.setdefault(guide["zone"], set()).add(name)
    for guide in guides:
        for step in guide.get("steps", []):
            enriched = []
            for goal in step.get("goals", []):
                candidates = names.get(goal.get("map"), set())
                zone = next(iter(candidates)) if len(candidates) == 1 else None
                enriched.append(enrich_goal(goal, zone, source_commit=source_commit))
            step["goals"] = enriched
    return result


def audit_document(document: Mapping[str, Any]) -> dict[str, Any]:
    goals = [goal for guide in document["guides"] for step in guide["steps"] for goal in step["goals"]]
    return {
        "guides": len(document["guides"]), "goals": len(goals),
        "withoutNote": sum(not visible_text(goal.get("note")) for goal in goals),
        "withoutNoteOrText": sum(not (visible_text(goal.get("note")) or visible_text(goal.get("text"))) for goal in goals),
        "redundantLabelNotes": sum(bool(note := visible_text(goal.get("note"))) and _is_label(note, goal) for goal in goals),
        "englishOrMixedMarkers": {field: sum(bool(_ENGLISH.search(visible_text(goal.get(field)))) for goal in goals)
                                  for field in ("note", "text")},
        "explicitTaming": sum(instruction_verb(goal) == "Domestica" for goal in goals),
        "actions": dict(sorted(Counter(goal.get("t") or goal.get("action") for goal in goals).items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--output", type=Path, help="Write an enriched copy; never changes --input implicitly")
    mode.add_argument("--check", action="store_true", help="Fail if --input needs deterministic enrichment")
    args = parser.parse_args(argv)
    document = json.loads(args.input.read_text(encoding="utf-8-sig"))
    enriched = enrich_document(document)
    if args.check:
        if enriched != document:
            print("Instruction enrichment is missing or stale; generate a new copy with --output.")
            return 1
        print("Verified deterministic guide instructions.")
    elif args.output:
        args.output.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {audit_document(document)['goals']} instructions to {args.output}")
    else:
        print(json.dumps(audit_document(document), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
