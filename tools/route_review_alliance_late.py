"""Reviewed Alliance 30–60 route choices, applied before rebuilding goal instructions."""

ALLIANCE = "forever/alliance/"
HILLS = "30-40/01-hillsbrad-foothills"
DESOLACE = "30-40/02-desolace"
ASHENVALE = "30-40/03-ashenvale"
JUNGLE = "30-40/04-stranglethorn-vale"
ARATHI = "30-40/05-arathi-highlands"
BADLANDS = "30-40/06-badlands"
JUNGLE_SOUTH = "40-50/01-stranglethorn-vale"
BADLANDS_EAST = "40-50/02-badlands"
FERALAS = "40-50/03-feralas"
TANARIS = "40-50/04-tanaris"
HINTERLANDS = "40-50/05-the-hinterlands"
GORGE = "40-50/06-searing-gorge"
CRATER = "40-50/07-un-goro-crater"
STEPPES = "50-60/01-burning-steppes"
FELWOOD = "50-60/02-felwood"
WINTERSPRING = "50-60/03-winterspring"
PLAGUE = "50-60/04-western-plaguelands"
SILITHUS = "50-60/05-silithus"
FINAL = "50-60/06-silithus"

SAGE = "https://www.sageguide.net/"
ENTOMOLOGY = "https://guide.wow4ever.se/en/quests/93176"
CONTRACT = "https://questing.wiki/wow-forever/quests/series/522/"
UMI = "https://zephras.com/forever/enUS/quest/5163/"
FEL_CRATERS = "https://zephras.com/forever/enUS/quest/5156/"
SPAWNS = ("https://github.com/julen92/SendaFH/blob/"
          "5d207e28e82e2c529143b21ace74fe88692f0067/addon/SendaFH_QuestDB/Npcs.lua")

# The named quest illustrates what is shared, where the authors differ and how
# this affects the local chapter. The full per-action comparison is generated
# from the independent, version-filtered Sage references alongside this module.
CHAPTERS = {
    HILLS: ("30-31_hillsbrad", 98059, "Condicionar la visita",
            "Sage reúne la colocación de la solicitud y el regreso a McManus en Costasur. El ayuntamiento solo sirve mientras la solicitud está pendiente."),
    DESOLACE: ("33-35_desolace", 1440, "Seguir a Dalinda",
               "Sage encadena la búsqueda de Tyranis y la salida con Dalinda. La flecha de escolta se activa al aceptar su misión."),
    ASHENVALE: ("29-30_wetlands", 324, "Conservar la cadena de Glorin",
                "Sage incluye las entregas de las dos partes en Los Humedales. La segunda aprovecha la visita al cofre tras completar la primera."),
    JUNGLE: ("32-33_stranglethorn", 185, "Conservar la cacería",
             "Sage acepta la primera cacería de tigres en el campamento de Nesingwary. El primer recorrido también permite avanzar las cacerías vecinas."),
    ARATHI: ("38-39_arathi", 681, "Compartir la visita a la granja",
             "La ruta de Sage incluye los dos tipos de bandidos de la Mansión Redilnorte. La visita también permite recoger el gorgojo si llevas el encargo de Amaryllis."),
    BADLANDS: ("39-40_badlands", 710, "Mantener las entregas de Lotwil",
               "Sage recorre las tres etapas de estudio elemental con Lotwil. Las entregas intermedias abren las etapas posteriores."),
    JUNGLE_SOUTH: ("40-42_stranglethorn", 608, "Conservar como opcional",
                   "Sage incluye el asalto a los barcos. En RutaXP queda a elección del jugador por las cubiertas con tripulación y los tres capitanes."),
    BADLANDS_EAST: ("46-46_hinterlands", 2880, "Mantener la primera entrega",
                    "Ambas rutas aprovechan los collares de las Tierras del Interior. La repetición posterior se ofrece si sobran otros cinco collares."),
    FERALAS: ("44-46_feralas", 2869, "Mantener la cadena de los naga",
              "Sage recoge las escamas de los Crestafuria y vuelve a la fortaleza. Entregarlas a Latronicus abre la misión de Lord Shalzaru."),
    TANARIS: ("43-44_tanaris", 1690, "Agrupar bandidos y bolsas de agua",
              "Sage reúne las bajas de los bandidos con las bolsas de agua de la misma zona. Se conserva la visita conjunta al este de Gadgetzan."),
    HINTERLANDS: ("46-46_hinterlands", 2877, "Conservar el recorrido",
                  "Sage también acaba con los dos tipos de babosas para Fraggar. El viaje al este reúne sus bajas antes de regresar a Pico Nidal."),
    GORGE: ("46-47_searing_gorge", 7727, "Agrupar las ofertas de la Hermandad",
            "Sage recoge varios encargos de la Hermandad del Torio antes de salir hacia sus objetivos en la Garganta de Fuego."),
    CRATER: ("51-53_un%27goro_crater", 4285, "Usar el crédito de cada pilón",
             "Sage visita los tres pilones dentro del circuito del cráter. Cada desvío depende de haber aceptado su propia misión en el Refugio de Marshal."),
    STEPPES: ("54-54_burning_steppes", 3824, "Conservar los encargos de las estepas",
              "Sage incluye la caza de Gor'tesh y la entrega a Oralius. Ese regreso desbloquea la misión en la que se exhibe la cabeza en Roca Machacamiedo."),
    FELWOOD: ("53-53_feralas,_felwood", 5156, "Condicionar los tres cráteres",
              "La visita por el valle forma parte de la misión de élite de los elementales. Al subir en solitario se pueden aprovechar los demás encargos de Frondavil."),
    WINTERSPRING: ("55-56_winterspring", 5163, "Asustar al primer amigo de Umi",
                   "La continuación del encargo de los yetis se reparte entre tres pueblos. Se usa el yeti mecánico en Legacki durante la parada en Vista Eterna."),
    PLAGUE: ("54-55_plaguelands", 5222, "Conservar la cadena de calderos",
             "Sage visita los calderos por orden de desbloqueo. La guía reserva las donaciones adicionales para quien tenga los materiales."),
    SILITHUS: ("58-59_silithus", 8280, "Agrupar las dos patrullas",
               "Sage incluye las primeras patrullas de Silithus. Agrupar sus objetivos con los del mismo sector permite volver al Fuerte Cenarion con varias entregas."),
    FINAL: ("56-57_plaguelands", 5903, "Mantener las entregas del encargo",
            "Sage incluye ambas partes del encargo de la Peste. El cierre en la ruta de RutaXP aprovecha otras entregas del mismo viaje."),
}
REFERENCES = {
    ALLIANCE + chapter: [(SAGE + page, reason)]
    for chapter, (page, _, _, reason) in CHAPTERS.items()
}
NOTES = {
    (ALLIANCE + chapter, quest): dict(decision=decision, reason=reason, url=SAGE + page)
    for chapter, (page, quest, decision, reason) in CHAPTERS.items()
}


def _evidence(chapter, quests, decision, reason, url):
    entry = (url, reason)
    if entry not in REFERENCES[ALLIANCE + chapter]:
        REFERENCES[ALLIANCE + chapter].append(entry)
    for quest in quests:
        NOTES[ALLIANCE + chapter, quest] = dict(decision=decision, reason=reason, url=url)


_evidence(HILLS, (98059,), "Visitar el ayuntamiento con la misión activa",
          "La solicitud sellada se deja en la mesa del ayuntamiento. La misión se devuelve a McManus en Costasur.",
          "https://zephras.com/forever/enUS/quest/98059/")
_evidence(HILLS, (555,), "Agrupar la entrega y la continuación con Farren",
          "OpenXP entrega primero la sopa al chef. En esta visita ya estás con Farren para entregar «Cambio de destino» y recoger «Nueva asignación», que se abre al entregarla. Después lleva la sopa al chef.",
          "https://github.com/mjared123/OpenXP/blob/b3f094095ceca7a5eee1d64b2851c861cf25ecf1/Guides/openxp/Alliance-30-40.lua#L836")
_evidence(ARATHI, (522, 523), "Evitar la espera por el asesino en Costasur",
          "El contrato del asesino abre la cadena del barón. El recorrido rápido cobra si llevas el objeto y continúa con los encargos del magistrado.",
          CONTRACT)
_evidence(JUNGLE_SOUTH, (624,), "Aprovechar el pergamino si ya lo llevas",
          "El pergamino comparte los barcos de los capitanes Velasangre. Quien omita ese asalto también puede evitar el abordaje para buscar el pergamino. La entrega bajo el puente sigue disponible al llevar el encargo.",
          "https://urgametips.com/wow-forever/quest-guides/cortello-riddle-ship-scroll-soggy-scroll-bridge/")
_evidence(PLAGUE, (4971,), "Usar el objeto junto al silo",
          "El desplazador hace aparecer parásitos en los silos de Andorhal. Se contabilizan sus bajas en el diario y se omite el uso si ya están completas.",
          "https://zephras.com/forever/enUS/quest/4971/")
for chapter in (ARATHI, BADLANDS, JUNGLE_SOUTH):
    _evidence(chapter, (93176,), "Dejar la mascota como opcional",
              "La recompensa es una mascota y exige tres ejemplares en zonas distintas. Si aceptas la misión, cada captura se activa al pasar por su zona y la entrega se conserva cuando está lista.", ENTOMOLOGY)
_evidence(CRATER, (4285, 4287, 4288), "Visitar solo el pilón pendiente",
          "Sage agrupa los tres descubrimientos con los objetivos del cráter. Son tres misiones separadas y cada una tiene su propio crédito.",
          SAGE + CHAPTERS[CRATER][0])
_evidence(FELWOOD, (5156,), "Reservar los cráteres para la misión de élite",
          "Las visitas del valle y sus elementales forman parte de la misma misión de élite. También se comprueba al recorrer los tres puntos.", FEL_CRATERS)
for chapter in (WINTERSPRING, SILITHUS, FINAL):
    _evidence(chapter, (5163,), "Usar el yeti mecánico sobre el personaje",
              "La misión acredita por separado a Legacki, Roxio y Quixxil al asustarlos. La parada depende del crédito del personaje local.", UMI)

# Each anchor is an Era spawn recorded in the pinned database, on terrain
# already named by the original route. It only matters below the level gate.
LEVEL_HUNTS = {
    (FERALAS, 45): (1444, 52.6, 57.3, "Si te falta experiencia para el 45, caza yetis en la Vega Cicatriz Feral. Después vuelve a la costa para los encargos de Zorbin."),
    (CRATER, 48): (1446, 60.4, 24.3, "Si te falta experiencia para el 48, caza bandidos al este de Gadgetzan. Aprovecha sus bolsas de agua si aún llevas ese encargo."),
    (PLAGUE, 55): (1422, 52.8, 64.7, "Si te falta experiencia para el 55, caza necrófagos congeladores cerca del caldero de la granja de Mulgris."),
    (FINAL, 58): (1451, 33.3, 42.9, "Si te falta experiencia para el 58, caza los trituradores que recorren las dunas entre Colmen'Zora y el Fuerte Cenarion."),
}
for (chapter, level), (_, _, _, reason) in LEVEL_HUNTS.items():
    REFERENCES[ALLIANCE + chapter].append((SPAWNS, reason))

SPECIMENS = {
    (ARATHI, 217589): (2, "En la granja, derrota a los bandidos del Sindicato. Si tienes el encargo de Amaryllis, captura allí el gorgojo con el equipo de entomología."),
    (BADLANDS, 217590): (3, "Recoge los huesos de kodo entre los esqueletos cerca de Hornizz. Si tienes el encargo de Amaryllis, captura allí el Flesh Picker con el equipo de entomología."),
    (JUNGLE_SOUTH, 217588): (1, "La tarántula se encuentra al sureste del campamento de Nesingwary. Si tienes el encargo de Amaryllis, captúrala con el equipo de entomología al pasar."),
}
UMI_FRIENDS = {WINTERSPRING: (1, "Legacki"), SILITHUS: (2, "Roxio"), FINAL: (3, "Quixxil")}
PYLONS = {"Torre de cristal del Norte": 4285, "Torre de cristal del Este": 4287, "Torre de cristal del Oeste": 4288}


def apply(document):
    """Enrich existing actions in place. Action identity and player saves stay valid."""
    for guide in document["guides"]:
        chapter = guide["id"].removeprefix(ALLIANCE)
        if chapter not in CHAPTERS or not guide["id"].startswith(ALLIANCE):
            continue
        for step in guide["steps"]:
            for goal in step["goals"]:
                kind, quest, name = goal["t"], goal.get("quest"), goal.get("text")
                if chapter == HILLS and kind == "use" and quest == 98059:
                    goal.update(workForQuest=quest, note="Junto a la mesa de contabilidad del ayuntamiento, haz clic derecho en la solicitud de tu mochila o escribe «/use item:279386» en el chat.")
                    step["note"] = "La flecha señala el edificio. Vuelve con el capitán McManus en Costasur cuando el diario registre la entrega de la solicitud."
                elif kind == "goto":
                    if chapter == DESOLACE and name == "Fuera de Fortaleza del Hacha de Trueno":
                        goal.update(workForQuest=1440, note="Acompaña a Dalinda fuera de la fortaleza hasta que aparezca el crédito de la escolta.")
                    elif chapter == CRATER and name in PYLONS:
                        goal.update(workForQuest=PYLONS[name], note="Inspecciona el pilón hasta que el diario registre el descubrimiento.")
                    elif chapter == FELWOOD and name in ("Primer cráter", "Segundo cráter", "Tercer cráter"):
                        goal.update(workForQuest=5156, workVisit=True, note="Pasa por el cráter mientras buscas a los elementales de la misión.")
                        step["note"] = "Con la misión de los elementales, recorre los tres cráteres del valle y completa las bajas que te falten."
                elif chapter == ARATHI and (quest in (522, 523) or goal.get("item") == 3668 or goal.get("npc") == 2434):
                    goal["levelingDetour"] = True
                    if quest in (522, 523):
                        goal["detourItems"] = {"3668" if quest == 522 else "3626": 1}
                    elif goal.get("item") == 3668:
                        goal.update(detourQuest=522, detourItems={"3668": 1})
                    if goal.get("npc") == 2434:
                        step["note"] = "Si encuentras al asesino en Costasur, recoge y abre el contrato. Puedes seguir con las entregas al magistrado en esta misma visita."
                elif (chapter, goal.get("npc")) in SPECIMENS and kind == "kill":
                    objective, note = SPECIMENS[chapter, goal["npc"]]
                    goal.update(workForQuest=93176, workForObjective=objective, reviewedVerb="Captura",
                                note="Abre el equipo de entomología de Amaryllis y usa la herramienta correspondiente sobre el ejemplar.")
                    step["note"] = note
                elif quest == 93176 and kind == "accept":
                    goal.update(levelingDetour=True, note="Si quieres la mascota, guarda el equipo de entomología de Amaryllis. Podrás usarlo al pasar por Arathi, Desolace y Tuercespina.")
                elif quest == 93176 and kind == "turnin":
                    goal["levelingDetour"] = True
                elif chapter == JUNGLE_SOUTH and goal.get("item") == 4056 and kind in ("collect", "accept"):
                    goal.update(levelingDetour=True, detourItems={"4056": 1})
                    if kind == "collect":
                        goal["detourQuest"] = 624
                        step["note"] = "Si embarcas para enfrentarte a los capitanes, busca el pergamino de Cortello a bordo. Si ya lo llevas, léelo para iniciar la misión."
                elif chapter == PLAGUE and kind == "use" and goal.get("item") == 12627:
                    goal.update(workForQuest=4971, workForObjective=1,
                                note="Usa el desplazador junto a un silo de Andorhal. Derrota a los parásitos que aparezcan hasta completar las diez bajas.")
                elif chapter in UMI_FRIENDS and (quest == 5163 and kind == "kill" or goal.get("item") == 12928 and kind == "use"):
                    index, friend = UMI_FRIENDS[chapter]
                    goal["note"] = f"Selecciona a {friend} y usa el Yeti mecánico de Umi desde la mochila."
                    if kind == "kill":
                        goal["reviewedVerb"] = "Asusta"
                    else:
                        goal.update(workForQuest=5163, workForObjective=index)
                elif chapter == WINTERSPRING and kind == "note" and "Templo Sumergido" in (name or ""):
                    goal.update(levelingDetour=True, text="Si ya tienes grupo, puedes ganar experiencia en el Templo Sumergido antes de volver a Vista Eterna.")
                elif kind == "level" and (chapter, goal["level"]) in LEVEL_HUNTS:
                    map_id, x, y, note = LEVEL_HUNTS[chapter, goal["level"]]
                    goal.update(map=map_id, x=x, y=y, f="e", note=note)
                    if chapter == FERALAS:
                        step["note"] = "Toma el barco a la Costa Olvidada. " + note
                    elif chapter == FINAL:
                        step["note"] = note + " En el fuerte, Mar'alith ofrece «Queridísima Natalia» a partir del 58."
    return document
