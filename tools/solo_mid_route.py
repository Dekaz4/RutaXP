"""Low-yield Alliance stops from Desolace to Feralas, applied on every import.

Route and item evidence come from the Polestar guides and SendaFH_QuestDB/Quests.lua
at 5d207e28e82e2c529143b21ace74fe88692f0067. The Stranglethorn guide for Horde
explicitly describes the same Barnil pages as incidental drops. QuestDB
lists all fifteen pages across four chapters. EverythingQuests records #338 as
their active parent in Source/quest_requirements_evidence.json.
"""

ALLIANCE = "forever/alliance/"

# Each entry covers the whole quest in that chapter. The two crafted-item
# commissions finish at the issuing NPC. Picking them up empty-handed creates
# an errand to find or buy the craft. A finished quest is still worth handing in.
DETOURS = {
    "30-40/02-desolace": {5821},                    # Moving caravan, wave escort at 32
    "30-40/04-stranglethorn-vale": {338, 339, 340, 341, 342, 635},
    "30-40/05-arathi-highlands": {635},              # Pendant carried from Stranglethorn
    "30-40/06-badlands": {5943, 716},               # Other leg of the Gizelton caravan
    "40-50/01-stranglethorn-vale": {608, 1203},      # 45–48 captains aboard crewed ships
    "40-50/02-badlands": {2881},                    # Five spare necklaces for reputation
    "40-50/03-feralas": {7735},                     # Rare hide during the regular #7733 hunt
}

# Item quantities use quest records from the pinned database. The five necklaces
# for the *repeat* are confirmed by https://zephras.com/forever/enUS/quest/2881/.
HAND_IN_ITEMS = {
    635: {"4614": 1},
    716: {"2868": 1},
    1203: {"3853": 1},
    2881: {"9259": 5},
    7735: {"18969": 1},
}


def apply_singing_blue_shards(guide):
    """Use the level 34–35 basilisk camps shared by both Stranglethorn chapters."""
    for step in guide["steps"]:
        for goal in step["goals"]:
            if goal.get("quest") != 605 or goal["t"] not in ("collect", "turnin"):
                continue
            goal["collectThenDeliver"] = True
            if goal["t"] == "turnin":
                continue
            # Forever QuestDB/Npcs.lua, NPC 689, map 1434 in Era coordinates.
            # Item 3918 also drops from stronger basilisks further south.
            goal.update({
                "from": "Basilisco Espina de Cristal", "fromKind": "npc",
                "map": 1434, "f": "e", "x": 24.2, "y": 17.5,
                "spots": [{"x": 24.2, "y": 17.5, "r": 74}, {"x": 26.7, "y": 18.3, "r": 31}],
                "note": "Derrota basiliscos Espina de Cristal en la costa noroeste y recoge sus fragmentos.",
            })
            if guide["id"].startswith(ALLIANCE):
                step.update(title="Basiliscos de la costa noroeste", note=goal["note"])
            else:
                step.update(title="Basiliscos y aldea Sangrapellejo",
                            note="Recoge fragmentos de los basiliscos en la costa noroeste y orejas de los trols en la aldea cercana.")


def apply_quae_handoff(document):
    """Reuse Phin's original offer when the Arathi visit needs its missing introduction."""
    guides = {guide["id"]: guide for guide in document["guides"]}
    arathi = guides.get(ALLIANCE + "30-40/05-arathi-highlands")
    hillsbrad = guides.get(ALLIANCE + "30-40/01-hillsbrad-foothills")
    if not arathi or not hillsbrad:
        return
    phin, = (row for step in hillsbrad["steps"] for row in step["goals"]
             if row.get("quest") == 659 and row["t"] == "accept" and row.get("npc") == 2711)
    stages = [659, 658, 657, 660, 661]
    for step in arathi["steps"]:
        for row in step["goals"]:
            quest = row.get("quest")
            if quest not in stages[:-1]:
                continue
            row["laterStages"] = stages[stages.index(quest) + 1:]
            if quest == 659 and row["t"] == "turnin":
                row["pickupIfMissing"] = {key: phin[key] for key in
                    ("t", "quest", "title", "npc", "npcName", "minLevel", "qlvl", "map", "f", "x", "y", "z")}
                row["pickupIfMissing"].update(
                    routeHeading="Phin Odelic · Costasur",
                    note="Recoge la primera parte en Costasur. Después llévala a Quae en la Granja Go’shek.",
                )


def apply_mid_detours(document):
    """Mark reviewed objectives in place without moving or completing any action."""
    apply_quae_handoff(document)
    for guide in document["guides"]:
        if guide["id"] in (ALLIANCE + "30-40/04-stranglethorn-vale", "forever/horde/30-40/02-stranglethorn-vale"):
            apply_singing_blue_shards(guide)
        chapter = guide["id"].removeprefix(ALLIANCE)
        if chapter not in DETOURS:
            continue
        for step in guide["steps"]:
            for goal in step["goals"]:
                quest = goal.get("quest")
                if quest in DETOURS[chapter]:
                    goal["levelingDetour"] = True
                    if quest in HAND_IN_ITEMS:
                        goal["detourItems"] = HAND_IN_ITEMS[quest].copy()
                elif chapter == "40-50/02-badlands":
                    if quest == 706 and goal["t"] in ("collect", "turnin"):
                        # Preserve the pickup to allow incidental quest-item drops.
                        goal.update(levelingDetour=True, detourItems={"4612": 1})
                    elif goal["t"] == "level" and goal.get("level") == 43:
                        # SendaFH_QuestDB/Npcs.lua, Scalding Whelp 2725. This is
                        # a recorded whelp location, independent of the rare heart.
                        goal.update(map=1418, x=71.2, y=52.7, f="e",
                                    note="Busca crías abrasadoras en el Barranco Lethlor. Evita los guardianes de élite.")
                        step["note"] = ("Si te falta experiencia para el 43, derrota crías abrasadoras. "
                                        "Si cae el corazón, llévaselo a Sigrun. Al alcanzar el nivel puedes continuar.")
                elif chapter == "40-50/03-feralas":
                    if goal["t"] == "collect" and goal.get("item") == 18969:
                        goal.update(levelingDetour=True, detourQuest=7735,
                                    detourItems=HAND_IN_ITEMS[7735].copy())
                    # The northern Tanaris dungeon is an alternative for a group.
                    # Zorbin's real level-45 gate comes next and stays in place.
                    elif (goal["t"] == "goto" and goal.get("map") == 1446
                          and goal.get("area") == 978 and goal.get("text") == "Zul'Farrak"):
                        goal["levelingDetour"] = True
                if chapter == "30-40/04-stranglethorn-vale" and quest == 338 and goal["t"] == "accept":
                    step["note"] = ("Acepta la cacería de panteras de Sir S. J. Erlgadin. "
                                    "Guarda las páginas que encuentres al derrotar humanoides. "
                                    "Si quieres completar el libro de Barnil, activa «Opcionales».")
    return document
