"""Quest-level review of the four Alliance starts and six shared early chapters."""

ALLIANCE = "forever/alliance/"
TELDRASSIL = ALLIANCE + "nightelf/01-teldrassil"
DUN_MOROGH = ALLIANCE + "dwarf-gnome/01-dun-morogh"
ELWYNN = ALLIANCE + "human/01-elwynn-forest"
ZEPHRAS = ALLIANCE + "skyborne/01-zephras-isle"
WESTFALL = ALLIANCE + "02-westfall"
DARKSHORE = ALLIANCE + "03-darkshore"
REDRIDGE = ALLIANCE + "04-redridge-mountains"
DUSKWOOD = ALLIANCE + "05-duskwood"
ASHENVALE = ALLIANCE + "06-ashenvale"
NEEDLES = ALLIANCE + "07-thousand-needles"

MASTERY = "https://forevermastery.com/en/guides/leveling/"
BIND = "https://bindonforever.com/leveling"
QUEST = "https://zephras.com/forever/enUS/quest/"
REFERENCES = {
    TELDRASSIL: [(MASTERY + "teldrassil", "Contraste de las variantes de Ban'ethil y las entregas en Dolanaar.")],
    DUN_MOROGH: [(MASTERY + "dun-morogh", "Se compararon los rodeos hasta los depósitos de Félix y las cacerías de jabalíes.")],
    ELWYNN: [(MASTERY + "elwynn-forest", "Recogidas aleatorias de los Defias y las entregas en Villadorada."),
             (MASTERY + "westfall", "Se comprobó en qué visita a los Cejade se entrega la escritura de Elwynn.")],
    ZEPHRAS: [(BIND, "La ruta específica de los Skyborne sale de la isla por Dalaran y Ventormenta hacia Páramos de Poniente."),
              ("https://polestar.guide/guides/alliance/skyborne/01-zephras-isle", "Referencia de la misma familia de guías para las misiones exclusivas de la isla.")],
    WESTFALL: [(MASTERY + "westfall", "La avena, el reloj y la escritura coinciden en la primera visita a los Cejade.")],
    DARKSHORE: [(MASTERY + "darkshore", "La variante rápida prescinde de escoltas largas en el extremo sur de la zona.")],
    REDRIDGE: [(MASTERY + "redridge-mountains", "Compara la visita a Fangore con la escolta de Keeshan al fondo de la zona de orcos.")],
    DUSKWOOD: [(MASTERY + "duskwood", "Se revisaron la compra del tubo de bronce y los libros que se entregan en Ventormenta.")],
    ASHENVALE: [(MASTERY + "darkshore", "El recorrido vecino omite la escolta de Kerlonian al salir hacia Vallefresno."),
                (MASTERY + "ashenvale-alliance", "Trabajos alrededor de la Atalaya de Maestra y conexiones de Vallefresno."),
                (MASTERY + "stonetalon-mountains-alliance", "Las entregas en Espolón se compararon con el recorrido de Kaela a Gaxim.")],
    NEEDLES: [(MASTERY + "thousand-needles-alliance", "Distingue los objetivos del norte y los basiliscos del sur."),
              (MASTERY + "wetlands", "Contraste con las tareas de Los Humedales que se pueden hacer antes del barco."),
              ("https://polestar.guide/guides/alliance/30-40/03-ashenvale", "Otra edición de la ruta del autor visita las Salinas más adelante.")],
}


def note(decision, reason, url):
    return {"decision": decision, "reason": reason, "url": url}


NOTES = {
    (TELDRASSIL, 2561): note("Conservar la vuelta a Oben",
        "La variante rápida omite al druida. Aquí ya estás dentro de Ban'ethil por las reliquias y entregas a Oben tanto la misión anterior como esta.", MASTERY + "teldrassil"),
    (DUN_MOROGH, 3361): note("Recoger los tres depósitos de paso",
        "La otra ruta descarta el recorrido de Félix. En este itinerario ya cazas troles y jabalíes junto a sus depósitos y vuelves a Yunquemar por otros encargos.", MASTERY + "dun-morogh"),
    (DUN_MOROGH, 317): note("Combinar las dos cacerías",
        "La otra ruta omite los suministros. Aquí los reúnes durante la cacería de jabalíes de la misión 384 y ya vuelves al almacén para la continuación.", MASTERY + "dun-morogh"),
    (ELWYNN, 184): note("Abrir la escritura si cae",
        "Es botín de los Defias. Abre el objeto si ya lo llevas mientras haces Elwynn y continúa hacia los Cejade.", QUEST + "184/"),
    (ZEPHRAS, 93319): note("Conservar el trabajo con los bandidos",
        "Recoges las piedras mientras haces las dos bajas del encargo 92517 en el mismo campamento. La élite Vulgara tiene su propio filtro.", QUEST + "93319/"),
    (ZEPHRAS, 94946): note("Conservar el traslado de salida",
        "La guía de Bind on Forever también enlaza el final de la isla con Dalaran y Ventormenta antes de continuar en Páramos de Poniente.", BIND),
    (WESTFALL, 64): note("Aceptar en la primera visita",
        "MacQuest y OpenXP recogen el reloj antes del encargo de Blanchy. Aquí ya estás con Verna para recoger el estofado y el encargo de Blanchy. Habla después con el granjero a su lado para aceptar el reloj y entregarle la escritura si la llevas. Todo cabe en la misma visita.", MASTERY + "westfall"),
    (WESTFALL, 184): note("Entregar durante la primera visita",
        "ForeverMastery omite la escritura. Al venir desde Elwynn con el objeto en la bolsa, tanto abrirlo como entregarlo al granjero se hace en la misma parada.", MASTERY + "westfall"),
    (DARKSHORE, 731): note("Escolta opcional en solitario",
        "El prospector puede sufrir varias oleadas de enemigos. Puedes entregar la misión anterior en la excavación y salir hacia las tortugas sin iniciar la escolta.", MASTERY + "darkshore"),
    (DARKSHORE, 945): note("Escolta opcional en solitario",
        "La ruta rápida también la omite. La escolta sale del cráter y la entrega queda en otro capítulo, en el santuario de Aessina.", MASTERY + "darkshore"),
    (REDRIDGE, 180): note("Aplazar el combate hasta nivel 24",
        "Fangore es de nivel 26 y vive rodeado de gnolls. A nivel 24 la diferencia se reduce a dos niveles. La caza de gnolls de la misión 91 sigue activa para los niveles inferiores.", QUEST + "180/"),
    (REDRIDGE, 219): note("Ofrecer la escolta desde nivel 24",
        "Keeshan tiene una escolta de nivel de misión 25. El recorrido rápido la descarta y el tranquilo la incluye más tarde. A nivel 24 ya puedes combinarla con la vuelta desde el valle.", MASTERY + "redridge-mountains"),
    (DUSKWOOD, 337): note("Abrir el libro si cae",
        "La ruta alternativa evita la entrega fuera de zona. Si te cae el libro en el cementerio, puedes abrirlo en cuanto lo tengas y entregarlo en la visita prevista a Ventormenta.", MASTERY + "duskwood"),
    (ASHENVALE, 337): note("Entregar el libro en la visita a Ventormenta",
        "La biblioteca de Ventormenta recibe el libro. El paso de entrega coincide con otras cuatro entregas en la ciudad.", QUEST + "337/"),
    (ASHENVALE, 945): note("Aprovechar la entrega lista",
        "El santuario de Aessina queda en el recorrido si terminaste la escolta en Costa Oscura.", QUEST + "945/"),
    (ASHENVALE, 5321): note("Escolta opcional en solitario",
        "Kerlonian se duerme en el camino. Puedes ir directamente a la Atalaya de Maestra para entregar La torre de Althalaxx. Si ya llegaste con él, conserva su entrega.", MASTERY + "darkshore"),
    (NEEDLES, 1175): note("Aplazar los basiliscos hasta nivel 32",
        "El último objetivo pide seis basiliscos del sur de nivel 34–35. El umbral recomendado de 32 deja una diferencia de dos a tres niveles. Las otras cuatro misiones del circuito siguen disponibles.", QUEST + "1175/"),
    (NEEDLES, 1110): note("Combinar con la fauna del norte",
        "Las piezas están en el suelo y se pueden recoger mientras se cazan animales. ForeverMastery las entrega antes de terminar todos los basiliscos.", MASTERY + "thousand-needles-alliance"),
}

# None means a standing solo detour. Integer thresholds are recommendations,
# separate from the server's minimum level for accepting the quest.
SOLO_DETOURS = {
    DARKSHORE: {731: None, 945: None},
    REDRIDGE: {180: 24, 219: 24},
    ASHENVALE: {5321: None, 945: None},
    NEEDLES: {1175: 32},
}

# Each pickup has a later delivery on an existing visit. Keep the default
# route moving until the quest-starting item is actually in the bags.
BAG_STARTERS = {
    ELWYNN: (184, 1972), WESTFALL: (184, 1972),
    DUSKWOOD: (337, 2794), ASHENVALE: (337, 2794),
}


def apply(document):
    for guide in document["guides"]:
        guide_id = guide["id"]
        if guide_id not in REFERENCES:
            continue
        detours = SOLO_DETOURS.get(guide_id, {})
        starter = BAG_STARTERS.get(guide_id)
        for step in guide["steps"]:
            for goal in step["goals"]:
                quest = goal.get("quest")
                action = goal["t"]
                if quest in detours:
                    goal["levelingDetour"] = True
                    if detours[quest] is not None:
                        goal["detourBelowLevel"] = detours[quest]
                if starter and (quest == starter[0] or goal.get("item") == starter[1]):
                    goal.update(levelingDetour=True, detourItems={str(starter[1]): 1})
                    if not quest:
                        goal["detourQuest"] = starter[0]
                if guide_id == DARKSHORE and quest == 731 and action == "accept":
                    step["note"] = "Entrega el encargo en la excavación. Si eliges escoltar al prospector, protégelo durante la búsqueda del fósil."
                elif guide_id == REDRIDGE and quest == 180 and action == "accept":
                    step["note"] = "Entrega «Una visita poco grata» a Martie. A partir de nivel 24 aprovecha el cartel del lago para recoger la recompensa por Fangore."
                elif guide_id == REDRIDGE and quest == 180 and action == "collect":
                    step["note"] = "Cruza el río al este y caza los gnolls del valle. Fangore está al norte, rodeado de escoltas. Para su recompensa conviene llegar con nivel 24 o más. Al sur quedan los orcos élite del fuerte."
                elif guide_id == NEEDLES and quest == 1175 and action == "kill":
                    step["note"] = "Recoge piezas de coche mientras cazas escórpidos, tortugas y buitres en el norte y el centro de las Salinas. Si vas a hacer «Un bache en la carretera», deja para el final los seis basiliscos de nivel 34–35 del extremo sur."
