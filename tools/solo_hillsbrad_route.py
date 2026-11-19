"""Reviewed quest stops for the Alliance visit to Hillsbrad and Bartolo's hand-in."""

HILLSBRAD = "forever/alliance/30-40/01-hillsbrad-foothills"
ARATHI = "forever/alliance/30-40/05-arathi-highlands"

# QuestAvailable_Forever lists the same two pickups for 510 and 511:
# https://github.com/wheelbarrel00/EverythingQuests/blob/9c1ce1e44238d8c6c8ca36d8f49836fde70b564f/Data/QuestAvailable_Forever.lua
# The Corrahn table (186420) is at 47.94, 82.15 on Era map 1416.
# Converted using MapFrames.era to Hillsbrad (1424), the frame of the
# existing 1738 pickup at Sofera. Navigation interprets all spots on goal.map.
CORRAHN_DOCUMENTS = {"x": 50.80, "y": 20.32, "object": 186420}

# SendaFH_QuestDB/Quests.lua #565, also recorded in the Forever quest journal.
# https://zephras.com/forever/enUS/quest/565/
BARTOLO_ITEMS = {"2997": 1, "2321": 1, "3719": 1, "3720": 10}


def apply_hillsbrad_detours(document):
    """Enrich existing objectives in place, preserving saved step and goal indices."""
    for guide in document["guides"]:
        if guide["id"] not in (HILLSBRAD, ARATHI):
            continue
        for step in guide["steps"]:
            is_yeti_stop = any(goal.get("quest") == 565 and goal["t"] == "collect"
                               for goal in step["goals"])
            for goal in step["goals"]:
                quest = goal.get("quest")
                if quest == 565 or (is_yeti_stop and goal["t"] == "note" and "Bartolo" in goal.get("text", "")):
                    goal["levelingDetour"] = True
                    goal["detourItems"] = dict(BARTOLO_ITEMS)
                    if goal["t"] == "note":
                        goal["detourQuest"] = 565
                        goal["text"] = ("Bartolo pide una capa de montañero, una madeja de paño de lana, "
                                        "un hilo refinado y 10 pieles de yeti. Entrégaselos juntos en Costasur.")
                if guide["id"] == HILLSBRAD and quest in (510, 511) and goal["t"] == "accept":
                    if (goal.get("object"), goal.get("map"), goal.get("f")) != (1738, 1424, "e"):
                        raise ValueError("Review the Syndicate Documents location before adding the Corrahn table")
                    spots = goal.setdefault("spots", [])
                    if CORRAHN_DOCUMENTS not in spots:
                        spots.append(dict(CORRAHN_DOCUMENTS))
                    step["note"] = ("En la Daga de Corrahn, busca los papeles sobre la mesa del campamento. "
                                    "Acepta allí «Documentos de planificación» y «Una carta cifrada». "
                                    "Si no encuentras los papeles, hay otra mesa en el campamento del nordeste. "
                                    "Los ladrones y asaltantes de ambos campamentos cuentan para «Hermandad de asesinos».")
    return document
