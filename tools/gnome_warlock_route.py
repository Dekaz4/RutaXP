"""Class stops in the Alliance solo route, without adding a dedicated pet trip.

Sources: SendaFH's pinned class/warlock/{incubus,felhunter}-alliance guides,
https://www.icy-veins.com/wow-forever/warlock-class-quests and Blizzard's
November 9 Felsteed fix (hotfix article 24315281).
"""

ALLIANCE = "forever/alliance/"
SAYAAD_PARENTS = {1716: None, 1738: 1716, 1739: 1738, 65602: 1716, 65603: 65602}


def apply_gnome_warlock_route(document):
    for guide in document["guides"]:
        if not guide["id"].startswith(ALLIANCE):
            continue
        for step in guide["steps"]:
            for goal in step["goals"]:
                quest = goal.get("quest")
                action = goal["t"]
                if quest in SAYAAD_PARENTS:
                    # An active quest always passes soloAfter. Work and delivery
                    # follow the player's actual branch, including the incubus.
                    goal["detourOnly"] = {"classes": ["WARLOCK"], "races": ["Gnome"]}
                    if action == "accept":
                        parent = SAYAAD_PARENTS[quest]
                        if parent:
                            goal["soloAfter"] = [parent]
                        else:
                            goal["levelingDetour"] = True
                    else:
                        goal["soloAfter"] = [quest]
                if quest == 1716 and action == "accept":
                    goal["note"] = ("Gakin inicia la cadena de la súcubo y el íncubo. Para seguirla con tu "
                                    "gnomo en solitario, activa «Opcionales» o acepta esta misión en su taberna. "
                                    "Verás a Takar al pasar por Los Baldíos camino de Las Mil Agujas.")
                elif quest == 1716 and action == "turnin":
                    step["note"] = ("Habla con Takar al este del camino, al nordeste del Campamento Taurajo. "
                                    "Acércate por el este para evitar a los guardias de la Horda.")
                elif quest == 1738 and action == "accept":
                    goal["note"] = ("El duramen está en Vallefresno. Recógelo cuando la ruta vuelva a pasar "
                                    "por Astranaar camino de Desolace.")
                elif quest == 1738 and action == "collect":
                    step["note"] = ("Desde Astranaar, ve al árbol de las ruinas de Ordil'Aran y recoge el duramen. "
                                    "Si llevas «¿Qué es el amor?», encontrarás la figurilla en la casa al norte "
                                    "de la Atalaya de Maestra. Regresa hacia Astranaar para continuar el viaje.")
                elif quest == 1739 and action == "complete":
                    step["note"] = ("Baja a la cripta de El Cordero Degollado en el Barrio de los Magos. "
                                    "Gakin recibe los objetos y ofrece la invocación correspondiente a cada uno.")
                    goal["note"] = ("Usa el Núcleo de duramen en el círculo de la cripta, derrota a la súcubo "
                                    "y habla otra vez con Gakin.")
                elif quest == 65603 and action == "kill":
                    goal["note"] = "Usa la figurilla en el círculo de la cripta, derrota al íncubo y vuelve con Gakin."
                elif quest == 4488 and action == "accept":
                    goal["note"] = ("A nivel 40 esta cadena enseña Invocar malignoecus y equitación de aprendiz. "
                                    "Recoge el encargo de Demisette y entrégalo a Strahad en la visita a Trinquete.")
                elif quest == 4490 and action == "turnin":
                    goal["note"] = ("Habla con Strahad para aprender Invocar malignoecus. Si también quieres el "
                                    "manáfago, su cadena de nivel 30 pasa por Trinquete, Forjaz, Costasur, Las Mil "
                                    "Agujas y Los Humedales. Para un gnomo, Llago Llavenegra ofrece el encargo inicial en Forjaz.")
                elif action == "train" and goal.get("npc") == 7954 and step.get("only", {}).get("races") == ["Gnome"]:
                    step["note"] = ("Binjy enseña equitación en el depósito al este de Kharanos. Si eres brujo, "
                                    "la misión del malignoecus de nivel 40 ya incluye la equitación de aprendiz. "
                                    "Visita a Milli si quieres comprar un mecazancudo.")
    return document
