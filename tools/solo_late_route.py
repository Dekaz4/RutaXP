"""Reviewed solo alternatives on the pinned Alliance route from Tanaris to level 60.

Run after the guide revisions/locations and before regenerating instructions. Nothing
here adds, moves or retires a goal. Quest log state and bag counts stay with the client.
"""

ALLIANCE = "forever/alliance/"
TANARIS = "40-50/04-tanaris"
HINTERLANDS = "40-50/05-the-hinterlands"
UNGORO = "40-50/07-un-goro-crater"
STEPPES = "50-60/01-burning-steppes"
WINTERSPRING = "50-60/03-winterspring"
PLAGUELANDS = "50-60/04-western-plaguelands"
SILITHUS = "50-60/05-silithus"
FINAL = "50-60/06-silithus"

# All three Alliance cloth officers in the published route ask for 60 pieces per
# donation. The runecloth quests additionally require three actual earlier turn-ins.
CLOTH = {
    7791: 2592, 7793: 4306, 7794: 4338, 7795: 14047,  # Stormwind
    7802: 2592, 7803: 4306, 7804: 4338, 7805: 14047,  # Ironforge
    7807: 2592, 7808: 4306, 7809: 4338, 7811: 14047,  # Gnomeregan
}
DONATIONS = {quest: {str(item): 60} for quest, item in CLOTH.items()}
FRAGMENT = {"10593": 1}

# Each mapping is limited to the named chapter. Counts for the two scourgestone
# sizes and Salfa are confirmed by the Forever quest records 5402, 5509 and 8469
# (https://zephras.com/forever/enUS/quest/5402/ etc.). Other item counts are
# explicit in the pinned SendaFH guide and its quest data.
QUESTS = {
    TANARIS: {1560: None},  # Long escort from Thistleshrub Valley to the coast.
    HINTERLANDS: {2601: {"8394": 10, "8396": 2}, 2603: {"8396": 10, "8391": 2}},
    UNGORO: {},
    STEPPES: {3501: FRAGMENT, 4283: {"11467": 50}},
    WINTERSPRING: {8469: {"21383": 5}, 5509: {"12841": 10}, 5510: {"12840": 20}},
    PLAGUELANDS: {
        5402: {"12840": 20}, 5403: {"12841": 10},
        # Secondary cauldron material donations. Keep all four keys, returns and
        # the final reward (5237). Only these extra jobs use Arcane Quickeners.
        5218: None, 5221: None, 5224: None,
        7725: {"18956": 10}, 7726: {"18958": 6},  # Zorbin's refills, not his first quests.
    },
    SILITHUS: {**DONATIONS, 7261: None},  # Standalone detour to the Alterac Valley entrance.
    FINAL: {
        **DONATIONS,
        5242: None,  # A second journey to the back of Shadow Hold to kill three named enemies.
        8323: {"20404": 10},  # Surplus texts for Ortell, after Bor's original ten.
    },
}

# Actual spawn records in the pinned SendaFH Codex. The frame is explicit:
# the carrion grub uses the live Plaguelands map, the others use Era coordinates.
# The level requirement stays in place and responds to the player's real XP.
HUNTS = {
    (UNGORO, 50): (1449, 63.1, 17.4, "e", "Gorilas de la Meseta Roca de Hierro",
        "Caza gorilas en la meseta, cerca de donde encontraste a Memo 01. Si llevas «Los simios de Un'Goro», recoge las pelambres que caigan. Evita el fondo de la cueva de U'cha."),  # NPC 6514
    (UNGORO, 51): (1449, 60.7, 38.9, "e", "Camino de Torwa",
        "Desde el Refugio de Marshal avanza hacia el sureste. Caza diemetradones jóvenes de nivel 49–50 al cruzar la selva oriental camino de Torwa."),  # NPC 9162
    (WINTERSPRING, 54): (1452, 66.4, 41.5, "e", "Los cuernos de Umi",
        "Los cuernos de Umi los sueltan las matriarcas y los patriarcas. Cuando los tengas, si falta experiencia, caza los yetis Cardo Nevado de nivel 55–56 en esas mismas colinas."),  # NPC 7458
    (SILITHUS, 57): (1423, 14.3, 67.9, "l", "Al salir de la cripta",
        "Sal de la cripta y sigue hacia el oeste por el sur de las Tierras de la Peste del Este. Caza larvas carroñeras de nivel 54–55 en campo abierto antes de usar la piedra a Trinquete."),  # NPC 8603
}


def _mark(goal, items=None):
    goal["levelingDetour"] = True
    if items:
        goal["detourItems"] = dict(items)


def apply_late_detours(document):
    """Annotate the reviewed snapshot in place. Old saves retain identical goal keys."""
    for guide in document["guides"]:
        chapter = guide["id"].removeprefix(ALLIANCE)
        if chapter not in QUESTS:
            continue
        quests = QUESTS[chapter]
        for step in guide["steps"]:
            for goal in step["goals"]:
                action = goal["t"]
                quest = goal.get("quest")
                hunt = HUNTS.get((chapter, goal.get("level"))) if action == "level" else None
                if hunt:
                    map_id, x, y, frame, title, note = hunt
                    goal.update(map=map_id, x=x, y=y, f=frame, note=note)
                    step.update(title=title, note=note)
                if chapter == UNGORO and quest == 4290 and action == "accept":
                    # The earlier-offer catalog already allows 4289 from level 47.
                    # Keep its normal pickup and all three pelt records in their slots.
                    step["note"] = ("Baja la rampa hasta Torwa, al sureste del cráter. Si te ofrece «Los simios de Un'Goro» "
                                    "y tienes sitio en el diario, acéptala también. Pasarás junto a los gorilas al visitar a Memo 01.")
                if quest in quests:
                    _mark(goal, quests[quest])
                if chapter == STEPPES and action == "fly" and goal["location"] == "Castillo de Nethergarde":
                    _mark(goal, FRAGMENT)
                    goal["detourQuest"] = 3501
                if chapter == SILITHUS and action == "fly" and goal["location"] == "Costasur":
                    _mark(goal)
                    goal["detourQuest"] = 7261
                if chapter == PLAGUELANDS and action == "buy" and goal.get("item") == 13320:
                    _mark(goal)
                if chapter == FINAL and action == "note" and step["title"] in (
                    "La Masacre (opcional)", "Scholomance (opcional)",
                ):
                    _mark(goal)
                if chapter == FINAL and action == "level" and goal["level"] == 59:
                    # The remaining turn-ins and pickups have no level-59 prerequisite.
                    _mark(goal)
                    step["title"] = "Osos de Cuna del Invierno"
                    step["note"] = "Puedes continuar hacia Aldea Estrella Fugaz y ganar experiencia con las entregas que quedan."
                if chapter == FINAL and action == "level" and goal["level"] == 60:
                    # The former Terrordale Spirits are summoned by the paladin-only
                    # Exorcism Censer (quest 7640). NPC 1816 is a normal outdoor
                    # level 55–56 bear in the pinned Codex. Use the same hunting
                    # ground and Era frame as Alliance quest 4985 in Western Plaguelands.
                    step["title"] = "El último tramo hasta el nivel 60"
                    step["note"] = ("Si ya tienes lista «Una Peste en la Cruzada», compara la experiencia de la entrega con lo que te falta. "
                                    "Cuando baste para llegar al 60, lleva el barril a Nathaniel Dumah en el Campamento del Orvallo. "
                                    "Los osos están en el bosque al sur de la granja de El Tormento.")
                    goal.update(map=1422, x=55.16, y=64.54, f="e",
                                note="Si te falta experiencia, caza osos pardos malsanos de nivel 55–56 en las Tierras de la Peste del Oeste. Atrae uno cada vez.")
                if chapter == TANARIS and quest == 2781 and action == "accept":
                    # Both objects start quest 2781. The Codex puts 150075 outside
                    # Gadgetzan, the next stop even for a player who skipped Tooga.
                    step["title"] = "Cartel de Gadgetzan"
                    goal.update(object=150075, map=1446, x=51.8, y=27.0, f="e",
                                note="Lee el cartel junto a Gadgetzan al volver para las entregas.")
                    goal.pop("z", None)  # This height belonged to the Steamwheedle poster.

            # Mixed bundles retain their normal travel, primary quests and class visits.
            # Their earlier tips instructed everyone to buy the optional supplies.
            ids = {goal.get("quest") for goal in step["goals"]}
            if chapter == PLAGUELANDS and 5219 in ids and any(g["t"] == "buy" for g in step["goals"]):
                step["note"] = "Con la llave de Piedra Mácula entregada, recoge el encargo de Llanto de Dalson. Compra un acelerador solo si quieres hacer también la entrega de materiales del primer caldero."
            if chapter == PLAGUELANDS and 5225 in ids and any(g["t"] == "buy" for g in step["goals"]):
                step["note"] = "La ruta continúa con la llave de la Gangrena de Gahrron. Si haces las entregas de materiales opcionales, compra los dos aceleradores al salir. Caducan en 30 minutos."
            if chapter == FINAL and 7795 in ids:
                step["note"] = "Vuelve a la Aldea Rut'theran y regresa en barco a Ventormenta por Auberdine. Fija tu hogar y visita al instructor. Clavicus acepta lotes de 60 unidades de tela si ya los llevas."
            if chapter == FINAL and 7811 in ids:
                step["note"] = "Toma el Tranvía Subterráneo a Forjaz y visita a Laris. Bubulo y Mistina aceptan por separado lotes de 60 unidades de tela si ya los llevas."
