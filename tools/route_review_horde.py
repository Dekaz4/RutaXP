"""Reviewed Horde leveling decisions for the pinned Forever routes."""

PREFIX = "forever/horde/"

# Each comparison uses the author's actual quest actions, excluding quests that
# ForeverLevel describes as skipped or as a gap in its own route.
CHAPTERS = (
    ("orc-troll/01-durotar", "troll", "Coinciden el inicio 4641, los jabalíes 788 y la misión de Forever 97279."),
    ("tauren/01-mulgore", "tauren", "Ambas rutas reúnen las entregas de 747, 752 y 750 al principio de Mulgore."),
    ("undead/01-tirisfal-glades", "undead", "El itinerario de réprobos también encadena 363 y 364 e incluye 3901."),
    ("skyborne/01-zephras-isle", "skyborne-horde", "La ruta específica de esta raza permite contrastar la salida de Thendal y el traslado a Kalimdor."),
    ("orc-troll/02-the-barrens", "orc", "842, 844 y 871 se agrupan al inicio. Los objetivos de 875 sirven para ganar la experiencia que falte."),
    ("02-the-barrens", "orc", "Contraste del primer circuito de El Cruce con 870, 844 y 867."),
    ("03-silverpine-forest", "undead", "La ruta de réprobos incluye 477, 428 y 437. La visita de farmeo al lago solo sirve mientras falte experiencia."),
    ("04-the-barrens", "orc", "La guía orca mantiene 1511 y reparte el tramo de Los Baldíos entre los niveles 13 y 25."),
    ("05-stonetalon-mountains", "orc", "El recorrido externo incluye 6383, 1092 y 6393 en su circuito de Sierra Espolón."),
    ("06-hillsbrad-foothills", "undead", "La ruta externa pasa por 5881 y 1094. El itinerario local dedica más misiones a esta zona."),
    ("07-ashenvale", "undead", "Coinciden 6562, 25 y 4865 en el recorrido por Vallefresno."),
    ("30-40/01-desolace", "orc", "Coinciden 1431 y 1434. La guía orca también hace la escolta móvil 5821 hacia el nivel 33."),
    ("30-40/02-stranglethorn-vale", "orc", "Mantiene las cacerías 187 y 568. La misión del libro 338 figura como hueco, sin entrega programada."),
    ("30-40/03-arathi-highlands", "orc", "676, 701 y 678 forman parte de su circuito por Arathi hacia el nivel 38."),
    ("30-40/04-dustwallow-marsh", "tauren", "La guía tauren también hace la cadena del escudo 1251, 1321 y 1323, más tarde en su recorrido."),
    ("40-50/01-stranglethorn-vale", "orc", "La vuelta por Bahía del Botín coincide en 348, 597 y 584."),
    ("40-50/02-feralas", "orc", "Coinciden las entregas 2864, 8366 y 2979 entre Tanaris y Feralas."),
    ("40-50/03-feralas", "tauren", "La guía tauren incluye 1424, 1429 y 1170 en sus circuitos del tramo 40–50."),
    ("40-50/04-tanaris", "skyborne-horde", "Coinciden las misiones 2781 y 7723. La ruta externa hace la escolta 1560 al nivel 52."),
    ("40-50/05-the-hinterlands", "orc", "Se conservan 2742, 7844 y 7849, también programadas en la visita orca a Tierras del Interior."),
    ("40-50/06-azshara", "undead", "También aparecen 2782, 3542 y 7732. Comparamos las entregas iniciales con sus repeticiones de materiales."),
    ("50-60/01-un-goro-crater", "skyborne-horde", "Coinciden 3881, 3844 y 974 en el circuito de Un’Goro."),
    ("50-60/02-felwood", "tauren", "También incluye 5021, 5543 y 4102 en su vuelta por Frondavil y las Tierras de la Peste."),
    ("50-60/03-winterspring", "tauren", "Coinciden 6605, 4521 y 8464, esta última la primera visita de trabajo para Salfa."),
    ("50-60/04-azshara", "troll", "La ruta trol conserva 8276, 3444 y 3505 en sus viajes de niveles altos."),
    ("50-60/05-eastern-plaguelands", "skyborne-horde", "Las entregas 5281, 6133 y 4741 se encuentran también en la ruta externa."),
    ("50-60/06-silithus", "troll", "Coinciden 1124, 8281 y 5098. Se distingue el primer lote de textos de Ortell de la repetición 8323."),
    ("50-60/07-felwood", "orc", "La guía externa hace 6605, 4741 y 6031. La última salida a ganar experiencia solo tiene sentido antes del nivel 60."),
)
REFERENCES = {PREFIX + slug: [(f"https://getforeverlevel.com/{race}/", reason)]
              for slug, race, reason in CHAPTERS}
REFERENCES[PREFIX + "skyborne/01-zephras-isle"].append((
    "https://www.foreverwisp.com/guides/wow-forever-skyborne-horde-leveling-guide",
    "La guía de ForeverWisp confirma el inicio en Thendal, el paso por Valanaar y la salida a Mulgore.",
))
REFERENCES[PREFIX + "06-hillsbrad-foothills"].append((
    "https://bindonforever.com/leveling/horde",
    "La ruta de Bind on Forever también combina Laderas de Trabalomas con otros circuitos antes del nivel 30.",
))


def quest_url(quest):
    return f"https://zephras.com/forever/enUS/quest/{quest}/"


# These items can be accumulated outside of a second, dedicated farming trip.
MATERIALS = {
    2601: {8394: 10, 8396: 2}, 2603: {8396: 10, 8391: 2},
    7725: {18956: 10}, 7726: {18958: 6}, 8323: {20404: 10},
    8469: {21383: 5},
    5407: {12841: 10}, 5408: {12840: 20}, 5509: {12841: 10}, 5510: {12840: 20},
}
for ids, item in (
    ((7820, 7833, 7826), 2592), ((7821, 7834, 7827), 4306),
    ((7822, 7835, 7831), 4338), ((7836, 7824), 14047),
):
    MATERIALS.update({quest: {item: 60} for quest in ids})

PAGES = {338, 339, 340, 341, 342}
ESCORTS = {5821, 5943, 1560}
DETOURS = PAGES | ESCORTS | {5242, 6031}

# Existing travel rows whose only purpose is grinding at the following point.
GRIND_TRAVEL = {
    ("03-silverpine-forest", 19), ("40-50/05-the-hinterlands", 48),
    ("50-60/07-felwood", 60),
}

# Spawn clusters of the creatures already named by the authored route.
GRIND_SPOTS = {
    ("orc-troll/02-the-barrens", 16): (1413, 39.1, 15.0),
    ("04-the-barrens", 20): (1413, 44.0, 45.4),
    ("50-60/01-un-goro-crater", 52): (1449, 43.1, 20.8),
    ("50-60/02-felwood", 53): (1422, 50.4, 41.2),
    ("50-60/02-felwood", 54): (1448, 63.1, 8.2),
    ("50-60/03-winterspring", 55): (1452, 66.5, 34.9),
}

NOTES = {}


def record(slug, ids, decision, reason):
    for quest in ids:
        NOTES[(PREFIX + slug, quest)] = {"decision": decision, "reason": reason, "url": quest_url(quest)}


record("30-40/01-desolace", [5821], "Escolta opcional",
       "La caravana es móvil. Esperarla para comenzar la escolta puede retrasar las entregas fijas de Desolace.")
record("30-40/04-dustwallow-marsh", [5943], "Escolta opcional",
       "Es la segunda escolta de la caravana Gizelton. El circuito puede continuar si la caravana está fuera del puesto.")
record("40-50/04-tanaris", [1560], "Escolta opcional",
       "Tooga cruza Tanaris del suroeste al noreste. Se mantiene en el mismo paso la entrega independiente de 3520.")
record("30-40/02-stranglethorn-vale", sorted(PAGES), "Colección opcional",
       "El libro se divide en cuatro capítulos de páginas dispersas. Las cacerías vecinas se pueden completar en la misma visita.")
record("40-50/05-the-hinterlands", [2601, 2603], "Entrega con los materiales en la bolsa",
       "Los dos encargos compiten por partes de bestias. Se mantienen las otras tres misiones del campamento y se aprovechan los lotes completos.")
record("40-50/06-azshara", [7725, 7726], "Segunda entrega con el lote completo",
       "Tras el primer encargo de Zorbin se puede continuar con las demás misiones de la zona y aprovechar un segundo lote si ya se tiene.")
record("50-60/06-silithus", [8323], "Segunda entrega con el lote completo",
       "Ortell pide diez textos adicionales después de la primera entrega. Se puede continuar el circuito de Silithus.")
record("50-60/03-winterspring", [8469], "Entrega con cinco cuentas",
       "Tras la primera misión de Salfa se aprovechan las cuentas ya reunidas durante otras cacerías.")
record("50-60/07-felwood", [5242], "Combate opcional",
       "Completar el último encargo de Greta exige otra incursión en el Bastión de la Sombra y tres objetivos en su interior.")
record("50-60/02-felwood", [6025], "Farmeo previo opcional",
       "El requisito es nivel 50 y haber entregado 6023. Subir al 53 antes de la misión élite es una sugerencia del recorrido.")
for slug in ("50-60/02-felwood", "50-60/07-felwood"):
    record(slug, [6031], "Opcional por reputación",
           "Meilosh pide treinta paños rúnicos y reputación Amistoso con los Fauces de Madera para ofrecer el encargo.")
for slug in ("50-60/03-winterspring", "50-60/05-eastern-plaguelands", "50-60/06-silithus", "50-60/07-felwood"):
    record(slug, [5163], "Usar el yeti sobre tres amigos",
           "Umi pide asustar a Legacki, Roxio y Quixxil con su yeti mecánico. La primera interacción se hace en Vista Eterna al aceptar.")
record("tauren/01-mulgore", [99411], "Completar durante la vuelta por Pezuña de Sangre",
       "Está disponible desde el nivel 5. Kyle ronda el poblado y se le da carne tierna de zancudo.")
record("undead/01-tirisfal-glades", [99152, 99153], "Hacer en la segunda visita a Bandarion",
       "Piden nivel 10. La ruta de ForeverLevel las hace al 13, tras hablar con Leonid. Pueden hacerlas todas las clases de réprobo.")
for slug, ids in {
    "50-60/01-un-goro-crater": [5407, 5408, 5509, 5510],
    "50-60/02-felwood": [5407, 5408],
}.items():
    record(slug, ids, "Entregar las piedras acumuladas",
           "Estas entregas de reputación piden un lote completo de piedras del mismo tipo. Se aprovechan las bajas del recorrido.")
for slug, ids in {
    "50-60/03-winterspring": [7820, 7821, 7822, 7833, 7834, 7835, 7826, 7827, 7831],
    "50-60/04-azshara": [7833, 7834, 7835, 7836, 7826, 7827, 7831, 7824],
    "50-60/05-eastern-plaguelands": [7820, 7821, 7822],
    "50-60/07-felwood": [7836, 7824],
}.items():
    record(slug, ids, "Aprovechar la donación en la visita",
           "El intendente pide sesenta piezas del mismo paño. La visita sirve cuando ya se lleva el lote.")


def apply(document):
    for guide in document["guides"]:
        if not guide["id"].startswith(PREFIX):
            continue
        slug = guide["id"][len(PREFIX):]
        for step in guide["steps"]:
            goals = step["goals"]
            level = next((g["level"] for g in goals if g["t"] == "level"), None)
            key = (slug, level)
            travel = next((g for g in goals if g["t"] == "goto"), None)
            for goal in goals:
                quest, kind = goal.get("quest"), goal["t"]
                if quest in MATERIALS:
                    goal["levelingDetour"] = True
                    goal["detourItems"] = {str(item): count for item, count in MATERIALS[quest].items()}
                elif quest in DETOURS:
                    goal["levelingDetour"] = True
                if quest == 6031:
                    goal.pop("detourItems", None)
                    goal["note"] = ("Meilosh ofrece este encargo al alcanzar Amistoso con los Fauces de Madera. "
                                    "Lleva treinta paños rúnicos si quieres hacer la entrega.")
                if key in GRIND_TRAVEL:
                    if kind == "goto":
                        goal["untilLevel"] = level
                    elif kind == "level" and travel:
                        goal.update({k: travel[k] for k in ("map", "x", "y", "f")})
                if kind == "level" and key in GRIND_SPOTS:
                    goal["map"], goal["x"], goal["y"] = GRIND_SPOTS[key]
                    goal["f"] = "e"
                if key == ("50-60/02-felwood", 53) and kind == "level":
                    goal["levelingDetour"] = True
                if slug == "50-60/07-felwood" and step["title"] == "Dungeon en lugar de farmeo" and kind == "note":
                    goal["levelingDetour"] = True
                if kind == "goto" and any(g.get("quest") == 8469 and g["t"] == "complete" for g in goals):
                    goal.update(levelingDetour=True, workForQuest=8469, workForObjective=1)
                if quest == 5163:
                    if kind == "kill":
                        goal["reviewedVerb"] = "Asusta"
                        goal["note"] = f"Selecciona a {goal['target']} y usa el yeti mecánico de Umi desde las bolsas."
                    elif kind == "accept":
                        goal["note"] = "Antes de salir de Vista Eterna, selecciona a Legacki y usa el yeti mecánico de Umi."
                if kind == "note" and any(g.get("quest") == 5163 and g["t"] == "accept" for g in goals):
                    goal["text"] = ("Sigue la flecha hasta Legacki, en Vista Eterna. Usa el yeti mecánico de Umi "
                                    "sobre ella. Conserva el yeti para Roxio en Gadgetzan y Quixxil en Un’Goro.")
                    goal.update(map=1452, x=61.5, y=38.6, f="e", workForQuest=5163, workForObjective=1)
                if quest == 99411 and kind == "complete":
                    goal["note"] = ("Consigue carne tierna de zancudo al este de Pezuña de Sangre. "
                                    "Busca a Kyle mientras corre por el poblado y usa la carne sobre él.")
            if any(g.get("quest") == 1560 and g["t"] == "accept" for g in goals):
                step["title"] = "Tooga y Puerto Bonvapor"
                step["note"] = ("Si has reunido los espíritus de los estriadores, entrégalos a Yeh'kinya en Puerto Bonvapor. "
                                "Si eliges escoltar a Tooga, acompáñalo hasta Torta en esa misma costa.")
