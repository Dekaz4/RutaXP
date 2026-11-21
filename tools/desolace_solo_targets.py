"""Hunting areas on the Alliance route through central Desolace.

Coordinates are recorded Desolace spawns in QuestieDB, data/Forever/foreverNpcDB.lua,
commit e1652ce62113c152da682baf2d6fb85f1396bcfb. The item sources are in the
pinned SendaFH_QuestDB/Items.lua, entries 6067, 6248 and 6249.
"""

CHAPTER = "forever/alliance/30-40/02-desolace"

# Each point is a spawn of the named creature, not the average of mixed packs.
# On the west approach the level 34–35 lashers already drop the venom. On the
# east/southeast route the level 30–31 snappers give the same quest credit.
LASHERS = (
    (40.39, 40.83), (44.12, 45.51), (45.24, 47.94), (42.68, 50.14), (41.80, 57.33),
    (55.48, 45.70), (57.10, 48.48), (58.51, 54.37), (60.83, 54.52), (62.72, 48.33),
)
SNAPPERS = (
    (53.15, 68.88), (56.00, 64.65), (59.45, 64.24), (64.05, 63.80),
    (59.86, 33.48), (63.60, 37.61), (54.32, 22.04), (65.68, 26.83), (71.12, 33.22),
)
AGED_KODOS = (
    (49.36, 41.23), (49.37, 40.17), (50.51, 56.63), (51.95, 56.10),
    (53.65, 56.69), (52.61, 57.46), (48.29, 60.25), (50.82, 61.17), (52.24, 60.64),
)
# Level 30–31 Kolkar Centaurs and Scouts (4632/4633). Other clans can drop
# the same ears, but their camps do not belong to the authored Kolkar visit.
KOLKAR = (
    (68.55, 52.17), (68.70, 50.00), (68.67, 47.94), (69.35, 46.87), (68.62, 45.66),
)


def set_hunting_area(goal, points):
    goal.update(map=1443, x=points[0][0], y=points[0][1], f="e",
                spots=[{"x": x, "y": y} for x, y in points[1:]])


def apply_desolace_targets(document):
    for guide in document["guides"]:
        if guide["id"] != CHAPTER:
            continue
        for step in guide["steps"]:
            for goal in step["goals"]:
                if goal["t"] != "collect":
                    continue
                target = (goal.get("quest"), goal.get("item"))
                if target == (1459, 6248):
                    set_hunting_area(goal, LASHERS + SNAPPERS)
                    goal["from"], goal["fromAlso"] = "Azotador Scorpashi", "Sacudidor Scorpashi"
                elif target == (1459, 6249):
                    set_hunting_area(goal, AGED_KODOS)
                elif target == (1387, 6067):
                    set_hunting_area(goal, KOLKAR)
                    goal.update(fromKind="npc", fromAlso="Explorador Kolkar")
                    goal["from"] = "Centauro Kolkar"
                    step["note"] = ("En el borde suroeste del poblado encontrarás centauros y exploradores Kolkar "
                                    "de nivel 30–31. Recoge las 15 orejas y guárdalas para el cabo Melkins en Punta de Nijel.")
