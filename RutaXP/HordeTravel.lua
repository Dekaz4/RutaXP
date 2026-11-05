local _, ns = ...

-- Geography: pinned SendaFH 5d207e2, Nav/TravelData.lua (Horde taxi nodes,
-- zeppelin platforms, docks and inns), tools/lib/travel/crossings.json
-- (Carbonite-Classic 4d06280), and guides/forever/horde. Quest NPCs use the
-- corresponding shipped guide coordinates. "e" is Era, "f" is Forever.
ns.GuideTravelRoutes = ns.GuideTravelRoutes or {}
local prefix = "forever/horde/"

local function pin(id, map, x, y, title, text, radius, frame)
    return { id = id, map = map, x = x, y = y, f = frame or "e",
        radius = radius or 35, title = title, text = text }
end

local function crossing(id, map, x, y, title, text)
    local leg = pin(id, map, x, y, title, text, 30)
    leg.boundary = true
    return leg
end

local function board(id, map, x, y, title, text, frame)
    local leg = pin(id, map, x, y, title, text, 24, frame)
    leg.boundary, leg.transport = true, true
    return leg
end

-- TaxiNodes: use the faction's own boarding point, including in neutral towns.
local flights = {
    undercity = {1458, 63.09, 48.32, "Entrañas"},
    tarren = {1424, 60.21, 18.75, "Molino Tarren"},
    booty = {1434, 26.82, 77.00, "Bahía del Botín"},
    gromgol = {1434, 32.51, 29.28, "Grom'gol"},
    orgrimmar = {1454, 45.28, 63.75, "Orgrimmar"},
    freewind = {1441, 45.02, 49.13, "Poblado Viento Libre"},
    shadowprey = {1443, 21.56, 74.04, "Aldea Cazasombras"},
    gadgetzan = {1446, 51.62, 25.52, "Gadgetzan"},
    mojache = {1444, 75.43, 44.31, "Campamento Mojache"},
    everlook = {1452, 60.49, 36.34, "Vista Eterna"},
    stonard = {1435, 46.05, 54.68, "Rocal"},
    zoram = {1440, 12.19, 33.77, "Avanzada de Zoram'gar"},
    chapel = {1423, 80.12, 57.05, "Capilla de la Esperanza de la Luz"},
    thorium = {1427, 34.83, 30.58, "Puesto del Torio"},
    revantusk = {1425, 81.70, 81.89, "Poblado Sañadiente"},
    taurajo = {1413, 44.46, 59.10, "Campamento Taurajo"},
    marshals = {1449, 45.30, 5.97, "Refugio de Marshal"},
    ratchet = {1413, 63.12, 37.11, "Trinquete"},
}

local function fly(origin, destination)
    local a, b = flights[origin], flights[destination]
    local depart = board("fly-" .. origin .. "-" .. destination, a[1], a[2], a[3],
        "Vuelo a " .. b[4], "Habla con el maestro de vuelo de " .. a[4] .. " y elige " .. b[4] .. ".")
    depart.taxiLanding = {map = b[1], x = b[2], y = b[3], f = "e", radius = 55, title = b[4]}
    return {
        depart,
        pin("land-" .. destination, b[1], b[2], b[3], "Llegada a " .. b[4],
            "Al aterrizar en " .. b[4] .. ", continúa desde el maestro de vuelo.", 55),
    }
end

-- Combine adjoining stretches while preserving each leg's stable ID.
local function legs(...)
    local result = {}
    for i = 1, select("#", ...) do
        local stretch = select(i, ...)
        if stretch.id then result[#result + 1] = stretch
        else
            for _, leg in ipairs(stretch) do result[#result + 1] = leg end
        end
    end
    return result
end

local function link(source, destination, itinerary, arrivalGoals, arrivalGoalsByStep)
    ns.GuideTravelRoutes[prefix .. source] = { destination = prefix .. destination,
        legs = itinerary, arrivalGoals = arrivalGoals, arrivalGoalsByStep = arrivalGoalsByStep }
end

local crossroads = pin("crossroads", 1413, 51.50, 30.34, "El Cruce",
    "Entra en El Cruce y reúnete con Devrak, el maestro de vuelo.", 75)
local razor = pin("razor-hill", 1411, 51.51, 41.64, "Cerrotajo",
    "Sigue la carretera hasta Cerrotajo, donde se cruzan los caminos del centro de Durotar.", 85)
local westBridge = crossing("southfury-west", 1411, 37.20, 43.00, "Puente hacia Los Baldíos",
    "Desde Cerrotajo toma la carretera al oeste. Cruza el puente sobre el río Furia del Sur.")
local farWatch = pin("far-watch", 1413, 61.10, 21.30, "Puesto de Vanguardia",
    "Desde el puente, pasa el puesto y sigue el camino hacia el suroeste en dirección a El Cruce.", 75)
local orgGate = crossing("orgrimmar-gate", 1411, 45.54, 12.28, "Puerta de Orgrimmar",
    "Sigue el camino hasta la puerta principal y entra en el Valle de la Fuerza.")
local orgWindRider = pin("doras", 1454, 45.12, 63.89, "Torre de Doras",
    "Sube a la torre del Valle de la Fuerza. Doras está en la plataforma de los jinetes del viento.")
local undercityExit = crossing("undercity-lift", 1458, 66.01, 36.85, "Ascensor de Entrañas",
    "Desde el centro, sube por el ascensor y sal al patio de las Ruinas de Lordaeron.")
local tirisfalToDurotar = {
    board("zep-uc-org", 1420, 60.74, 58.87, "Zepelín a Orgrimmar",
        "Sube a la torre al salir de las ruinas. Confirma Orgrimmar con el maestro de zepelines y embarca."),
    pin("durotar-landing", 1411, 50.82, 13.54, "Desembarca en Durotar",
        "Baja del zepelín y desciende por la torre.", 55),
}
local mulgoreRoad = {
    pin("bloodhoof", 1412, 45.93, 64.16, "Poblado Pezuña de Sangre",
        "Toma el camino que pasa por el poblado y sigue hacia el este, en dirección a Los Baldíos.", 115, "f"),
    crossing("mulgore-pass", 1412, 68.59, 60.59, "Paso a Los Baldíos",
        "Sigue la carretera por la abertura entre las montañas hasta entrar en Los Baldíos."),
    pin("taurajo-road", 1413, 44.46, 59.10, "Camino del Campamento Taurajo",
        "Cerca del campamento, toma el Camino del Oro hacia el norte y síguelo hasta El Cruce.", 115),
    crossroads,
}

-- The four racial chapters have different exits and the orc/troll opening
-- has a separate Barrens chapter before the shared one.
link("orc-troll/01-durotar", "orc-troll/02-the-barrens", legs(razor, westBridge, farWatch,
    pin("sergra", 1413, 52.23, 31.01, "Sergra en El Cruce",
        "Sigue la carretera hasta El Cruce. Sergra está dentro del poblado.", 65)))
link("tauren/01-mulgore", "02-the-barrens", legs(
    crossing("bluff-lift", 1456, 35.69, 63.08, "Baja de Cima del Trueno",
        "Toma el ascensor del suroeste hasta el camino de Mulgore."), mulgoreRoad))
link("undead/01-tirisfal-glades", "02-the-barrens", legs(undercityExit, tirisfalToDurotar,
    razor, westBridge, farWatch, crossroads))
link("skyborne/01-zephras-isle", "02-the-barrens", legs(
    board("valanaar-airship", 2521, 57.92, 80.78, "Dirigible de Valanaar",
        "Sube al dirigible de la Horda en el suroeste de Valanaar y baja en Mulgore.", "f"),
    pin("mulgore-airship-landing", 1412, 33.40, 22.50, "Desembarca en Mulgore",
        "Baja junto a Alaana y toma el camino hacia el sur.", 65, "f"), mulgoreRoad))
link("orc-troll/02-the-barrens", "02-the-barrens", legs(
    pin("crossroads-north", 1413, 51.60, 28.40, "Entrada de El Cruce",
        "Desde el norte de Los Baldíos sigue el Camino del Oro hasta El Cruce.", 95), crossroads))

link("02-the-barrens", "03-silverpine-forest", legs(
    crossing("southfury-east", 1413, 60.80, 19.80, "Puente a Durotar",
        "Sal de El Cruce por la carretera noreste. En el Puesto de Vanguardia cruza el puente a Durotar."),
    razor, orgGate, orgWindRider))
link("03-silverpine-forest", "04-the-barrens", legs(fly("orgrimmar", "ratchet"),
    pin("mebok", 1413, 62.37, 37.62, "Mebok en Trinquete",
        "Desde el vuelo, entra en el poblado y busca a Mebok.", 38)), {1})
-- QuestDB/Npcs.lua #8582 places Kadrak at 48.1,5.4 in the Barrens (also
-- projected as 68.6,89.1 on Ashenvale). The tower precedes the zone change.
link("04-the-barrens", "05-stonetalon-mountains", legs(crossroads,
    pin("morshan-road", 1413, 48.44, 11.33, "Carretera de Mor'shan",
        "Sal de El Cruce por la carretera norte. Sigue por la Empalizada de Mor'shan hacia Vallefresno."),
    pin("kadrak", 1413, 48.10, 5.40, "Torre de Kadrak",
        "Sube a la torre de vigilancia de la empalizada para encontrar a Kadrak.", 35)))
link("05-stonetalon-mountains", "06-hillsbrad-foothills", legs(
    crossing("silverpine-hillsbrad", 1421, 66.36, 79.80, "Salida a Trabalomas",
        "En el sur de Bosque de Argénteos, sigue la carretera que gira al este hacia Trabalomas."),
    pin("southpoint-tower", 1424, 20.79, 47.40, "Torre Austral",
        "Pasa junto a la torre y continúa al este. Al acercarte al río toma la carretera que sube a Molino Tarren.", 75),
    pin("lydon", 1424, 61.44, 19.06, "Molino Tarren",
        "Entra en Molino Tarren y busca al boticario Lydon.", 55)))
link("06-hillsbrad-foothills", "07-ashenvale", legs(fly("ratchet", "zoram"),
    pin("jeneu", 1440, 11.56, 34.29, "Je'neu en Zoram'gar",
        "Desde el vuelo, entra en la avanzada de la costa y acércate a Je'neu Sancrea.")), {1})
link("07-ashenvale", "30-40/01-desolace", legs(fly("freewind", "orgrimmar"),
    pin("craven", 1454, 51.30, 45.90, "Craven en La Calle Mayor",
        "Baja de la torre y sigue por La Calle Mayor hasta Craven Drok.")), {1})

local gromgolTower = pin("gromgol-uc-platform", 1434, 31.54, 29.36, "Torre de Grom'gol",
    "Sube a la torre del oeste del campamento. La guía indica qué transporte te corresponde según tu clase.", 24)
link("30-40/01-desolace", "30-40/02-stranglethorn-vale", legs(fly("tarren", "undercity"), undercityExit,
    board("zep-uc-gromgol", 1420, 61.78, 59.18, "Zepelín a Grom'gol",
        "Sube a la torre del zepelín a Grom'gol. Comprueba el destino antes de embarcar."),
    pin("gromgol-arrival", 1434, 31.54, 29.36, "Desembarca en Grom'gol",
        "Baja del zepelín y desciende por la torre al campamento.", 35),
    pin("thysta", 1434, 32.54, 29.35, "Campamento Grom'gol",
        "Reúnete con Thysta junto al maestro de vuelo del campamento.", 35)), {1})
link("30-40/02-stranglethorn-vale", "30-40/03-arathi-highlands",
    legs(fly("booty", "gromgol"), gromgolTower), {1, 2})
link("30-40/03-arathi-highlands", "30-40/04-dustwallow-marsh", legs(fly("ratchet", "taurajo"),
    crossing("dustwallow-road", 1413, 49.53, 78.41, "Carretera a Marjal Revolcafango",
        "Desde Taurajo sigue el Camino del Oro al sur. En el desvío toma la carretera del este hacia el marjal."),
    pin("shady-rest", 1445, 29.70, 47.64, "Posada Reposo Umbrío",
        "Al entrar al marjal, detente en la posada quemada junto a la carretera.", 45)), {1})
link("30-40/04-dustwallow-marsh", "40-50/01-stranglethorn-vale", legs(fly("shadowprey", "ratchet"),
    board("ratchet-boat", 1413, 63.35, 38.45, "Barco a Bahía del Botín",
        "Ve hasta el extremo del muelle de Trinquete. Espera el barco y baja en Bahía del Botín."),
    pin("booty-dock", 1434, 26.35, 73.56, "Muelle de Bahía del Botín",
        "Desembarca y sigue las pasarelas de madera hacia la posada.", 45),
    pin("fin-fizracket", 1434, 27.61, 76.74, "Fin en Bahía del Botín",
        "Sigue la pasarela hasta Fin junto a las casas del puerto.")), {1}, {[2] = {1}})

link("40-50/01-stranglethorn-vale", "40-50/02-feralas", legs(fly("stonard", "gromgol"),
    board("zep-gromgol-org", 1434, 31.43, 29.91, "Zepelín a Orgrimmar",
        "En la torre de Grom'gol embarca en el zepelín a Orgrimmar."),
    pin("durotar-gromgol-landing", 1411, 50.69, 12.89, "Desembarca en Durotar",
        "Baja de la torre y sigue el camino hacia la puerta de Orgrimmar.", 50),
    orgGate, pin("org-gate-inside", 1454, 52.49, 84.40, "Valle de la Fuerza",
        "Entra por la puerta principal. Dentro de Orgrimmar, la guía te indicará el instructor de tu clase.", 65)),
    {1}, {[2] = {1}})
link("40-50/02-feralas", "40-50/03-feralas", legs(fly("gromgol", "stonard"),
    pin("stonard-inn", 1435, 45.16, 56.66, "Posada de Rocal",
        "Baja del vuelo y entra en la posada de Rocal para hablar con el tabernero.", 20)))
link("40-50/03-feralas", "40-50/04-tanaris", legs(fly("mojache", "gadgetzan"),
    pin("gadgetzan-inn", 1446, 52.51, 27.91, "Posada de Gadgetzan",
        "Entra en Gadgetzan y reúnete en la posada.", 45)), {1})
link("40-50/04-tanaris", "40-50/05-the-hinterlands", legs(fly("thorium", "stonard"),
    crossing("blasted-road", 1435, 33.83, 66.07, "Paso a Las Tierras Devastadas",
        "Desde Rocal sigue la carretera al oeste y toma el ramal sur hacia Las Tierras Devastadas."),
    pin("drazial", 1419, 50.55, 14.20, "Campamento de Drazial",
        "Sigue el camino desde la frontera hasta Drazial y Lynnore.", 45)), {1})
link("40-50/05-the-hinterlands", "40-50/06-azshara", legs(fly("revantusk", "undercity"),
    pin("oran", 1458, 73.06, 32.85, "Oran en Entrañas",
        "Desde el centro de Entrañas, sigue el pasillo hacia el Barrio de la Magia y busca a Oran.")), {1})
link("40-50/06-azshara", "50-60/01-un-goro-crater", legs(
    crossing("ungoro-ramp", 1446, 27.08, 57.20, "Bajada al Cráter de Un'Goro",
        "Desde el Pilar Partido ve al oeste hasta la rampa del borde del cráter. Sigue las curvas hasta abajo."),
    pin("ungoro-ramp-base", 1449, 71.44, 77.23, "Pie de la rampa de Un'Goro",
        "Desde la entrada sureste, sigue el borde oriental hacia el norte.", 80),
    pin("marshal-refuge", 1449, 43.95, 7.14, "Refugio de Marshal",
        "Al llegar al borde norte, síguelo al oeste hacia las cuevas del refugio. Sube al campamento.", 60)))

link("50-60/01-un-goro-crater", "50-60/02-felwood", legs(fly("chapel", "undercity"), undercityExit,
    crossing("bulwark-east", 1420, 84.09, 70.49, "El Baluarte",
        "Sal de las ruinas y sigue la carretera del este por el Baluarte hacia las Tierras de la Peste del Oeste."),
    pin("janice", 1422, 38.40, 54.05, "Granja de Piedramácula",
        "Sigue la carretera hasta la primera granja. Janice espera en la casa.", 38)), {1})
link("50-60/02-felwood", "50-60/03-winterspring", legs(
    crossing("timbermaw", 1448, 64.97, 8.36, "Túnel del Bastión Fauces de Madera",
        "Entra junto a Nafien. Dentro sigue el túnel hacia Cuna del Invierno, sin atacar a los fúrbolgs."),
    pin("timbermaw-exit", 1452, 27.96, 34.56, "Salida a Cuna del Invierno",
        "Sal del túnel y sigue la carretera al este hacia Vista Eterna.", 70),
    pin("everlook-town", 1452, 61.35, 38.97, "Vista Eterna",
        "Entra en la ciudad goblin y reúnete en la posada.", 55)))
link("50-60/03-winterspring", "50-60/04-azshara", legs(fly("everlook", "orgrimmar"),
    pin("jesrimon", 1454, 55.52, 34.08, "Jes'rimon en Orgrimmar",
        "Sigue los carteles hacia la Calle de las Sombras y reúnete con Jes'rimon.", 32)))
link("50-60/04-azshara", "50-60/05-eastern-plaguelands", legs(fly("undercity", "chapel"),
    pin("chapel-inn", 1423, 71.80, 48.52, "Capilla de la Esperanza de la Luz",
        "Baja del vuelo y reúnete con el tabernero de la capilla.", 40, "f")), {1})
link("50-60/05-eastern-plaguelands", "50-60/06-silithus", legs(fly("mojache", "marshals"),
    crossing("silithus-pass", 1449, 29.43, 22.42, "Paso a Silithus",
        "Desde el refugio, baja al cráter. Ve hacia el suroeste y toma el sendero que sube entre las montañas."),
    pin("valors-rest", 1451, 81.87, 18.93, "Sosiego del Valor",
        "Al salir del paso, baja al cementerio y busca a Layo entre las tumbas.", 55)))
link("50-60/06-silithus", "50-60/07-felwood", legs(tirisfalToDurotar, orgGate,
    pin("vehena", 1454, 37.70, 87.90, "Vehena en Orgrimmar",
        "Desde la entrada sigue los carteles hacia el Valle de los Espíritus para encontrar a Vehena.", 36)))
