local _, ns = ...
ns.GuideTravelRoutes = ns.GuideTravelRoutes or {}
local routes = ns.GuideTravelRoutes
local prefix = "forever/alliance/"
local west = ns.WestfallTravelLegs

-- Coordinates: SendaFH 5d207e2, Nav/TravelData.lua (taxi, docks and
-- portals), tools/lib/travel/crossings.json (road passes), and the NPC /
-- object positions in the corresponding compiled Forever guide. The first
-- actionable step can be on a different continent from the guide title.
local function stop(id, map, x, y, radius, title, text, frame)
    return { id = id, map = map, x = x, y = y, f = frame or "e", radius = radius,
        title = title, text = text }
end

local function cross(leg)
    leg.boundary = true
    return leg
end

local function board(leg)
    leg.transport = true
    return cross(leg)
end

local function link(source, destination, legs, arrivalGoals)
    routes[prefix .. source] = { destination = prefix .. destination, legs = legs, arrivalGoals = arrivalGoals }
end

-- The Alliance landing nodes. Some settlements have a second, hostile
-- flight master; in particular the two Gadgetzan nodes are far apart.
local nodes = {
    stormwind = {1453, 66.30, 62.67, "Ventormenta"},
    sentinel = {1436, 56.57, 52.67, "Colina del Centinela"},
    ironforge = {1455, 55.89, 47.87, "Forjaz"},
    menethil = {1437, 9.52, 59.66, "Puerto de Menethil"},
    thelsamar = {1432, 33.94, 50.79, "Thelsamar"},
    darkshire = {1431, 77.59, 44.38, "Villa Oscura"},
    bootybay = {1434, 27.53, 77.67, "Bahía del Botín"},
    auberdine = {1439, 36.40, 45.62, "Auberdine"},
    astranaar = {1440, 34.50, 48.02, "Astranaar"},
    thalanaar = {1444, 89.46, 45.87, "Thalanaar"},
    theramore = {1445, 67.46, 51.20, "Theramore"},
    nijel = {1443, 64.67, 10.44, "Punta de Nijel"},
    gadgetzan = {1446, 50.95, 29.33, "Gadgetzan"},
    feathermoon = {1444, 30.26, 43.32, "Bastión Plumaluna"},
    aerie = {1425, 11.11, 46.09, "Pico Nidal"},
    moonglade = {1450, 47.91, 67.11, "Claro de la Luna"},
    chillwind = {1422, 42.95, 84.95, "Campamento del Orvallo"},
    lightshope = {1423, 81.52, 59.23, "Capilla de la Esperanza de la Luz"},
    thorium = {1427, 37.89, 30.43, "Puesto del Torio"},
    ratchet = {1413, 63.12, 37.11, "Trinquete"},
}

local function flight(from, to, shortcut)
    local a, b = nodes[from], nodes[to]
    local text = "Habla con el maestro de vuelo de " .. a[4] .. " y elige «" .. b[4] .. "»."
    local leg = board(stop(from .. "-to-" .. to, a[1], a[2], a[3], 28, "Vuelo a " .. b[4],
        shortcut and (shortcut .. " " .. text) or text))
    leg.taxiLanding = {map = b[1], x = b[2], y = b[3], f = "e", radius = 65, title = b[4]}
    return leg
end

local function landing(key, text)
    local n = nodes[key]
    return stop("landing-" .. key, n[1], n[2], n[3], 60, "Llegada a " .. n[4],
        text or ("Reuníos junto al maestro de vuelo de " .. n[4] .. "."))
end

local darnPortal = board(stop("darn-portal", 1457, 29.13, 41.21, 20, "Portal a Rut'theran",
    "Cruza el portal bajo el árbol del oeste de Darnassus para bajar a la aldea portuaria."))
local rutShip = board(stop("rut-auber", 1438, 54.79, 97.17, 30, "Barco a Auberdine",
    "Sigue el muelle hasta el barco de Auberdine. Sube y desembarca en Costa Oscura."))
local auberSW = board(stop("auber-sw", 1439, 30.53, 40.88, 30, "Barco a Ventormenta",
    "Sigue el embarcadero de Auberdine hasta el muelle de Ventormenta y sube al barco."))
local swAuber = board(stop("sw-auber", 1453, 21.78, 56.86, 30, "Barco a Auberdine",
    "Baja las escaleras del puerto y espera en el muelle señalado. Toma el barco a Auberdine.", "f"))
local menThera = board(stop("men-thera", 1437, 4.74, 63.76, 30, "Barco a Theramore",
    "Ve al muelle del sur del Puerto de Menethil y sube al barco con destino a Theramore."))
local theraMen = board(stop("thera-men", 1445, 71.73, 56.66, 30, "Barco al Puerto de Menethil",
    "Ve al extremo del muelle de Theramore y toma el barco a Los Humedales."))
local coastShip = board(stop("coast-ship", 1444, 43.13, 42.76, 32, "Barco a Bastión Plumaluna",
    "En el embarcadero de la Costa Olvidada toma el barco a la isla. Baja al llegar al muelle del bastión."))
local moonPier = stop("moon-pier", 1444, 31.01, 39.51, 40, "Muelle de Bastión Plumaluna",
    "Desembarca y sigue la pasarela hacia el bastión.")
local lochBad = cross(stop("loch-pass", 1432, 47.19, 80.82, 38, "Paso a Tierras Inhóspitas",
    "Sigue el camino al sur del lago y cruza el paso abierto entre las montañas."))
local badLochSide = stop("bad-north", 1418, 49.36, 7.97, 65, "Entrada norte de Tierras Inhóspitas",
    "Baja por el paso hasta el camino de Tierras Inhóspitas.")
local raceway = stop("mirage", 1441, 78.06, 77.13, 62, "Circuito del Espejismo",
    "Cruza las Salinas en dirección al circuito. Fizzle Pernolatón está en el campamento de la pista.")

local westfall = "02-westfall"
local darkshore = "03-darkshore"
local redridge = "04-redridge-mountains"
local duskwood = "05-duskwood"
local ashenvale = "06-ashenvale"
local thousandNeedles = "07-thousand-needles"
local hillsbrad30 = "30-40/01-hillsbrad-foothills"
local desolace30 = "30-40/02-desolace"
local ashenvale30 = "30-40/03-ashenvale"
local stranglethorn30 = "30-40/04-stranglethorn-vale"
local arathi30 = "30-40/05-arathi-highlands"
local badlands30 = "30-40/06-badlands"
local stranglethorn40 = "40-50/01-stranglethorn-vale"
local badlands40 = "40-50/02-badlands"
local feralas40 = "40-50/03-feralas"
local tanaris40 = "40-50/04-tanaris"
local hinterlands40 = "40-50/05-the-hinterlands"
local searing40 = "40-50/06-searing-gorge"
local ungoro40 = "40-50/07-un-goro-crater"
local burning50 = "50-60/01-burning-steppes"
local felwood50 = "50-60/02-felwood"
local winterspring50 = "50-60/03-winterspring"
local plaguelands50 = "50-60/04-western-plaguelands"
local silithus50 = "50-60/05-silithus"
local silithusFinal = "50-60/06-silithus"

local function viaElwynn(legs)
    -- Mercaderes -> puerta -> Villadorada -> Arroyoeste -> puente -> colina.
    for i = 7, #west do legs[#legs + 1] = west[i] end
    return legs
end
link("dwarf-gnome/01-dun-morogh", westfall, west)
link("human/01-elwynn-forest", westfall, viaElwynn({}))
link("nightelf/01-teldrassil", westfall, viaElwynn({darnPortal, rutShip, auberSW}))
link("skyborne/01-zephras-isle", westfall, viaElwynn({
    board(stop("skycutter", 2521, 65.81, 83.44, 40, "Zepelín hacia Dalaran",
        "En la torre al sur de Valanaar, sube al zepelín y baja junto al lago de Dalaran.", "f")),
    board(stop("sky-portal", 1416, 12.04, 56.21, 20, "Portal a Ventormenta",
        "Usa el portal junto a Denaaris en el campamento del Kirin Tor.")),
}))

link(westfall, darkshore, {
    flight("sentinel", "stormwind"), swAuber,
    landing("auberdine", "Al bajar del barco, sigue el embarcadero hasta el poblado y busca al maestro de vuelo."),
})
link(darkshore, redridge, {
    darnPortal, rutShip, auberSW,
    stop("baros", 1453, 57.74, 47.86, 45, "Baros Alexston en Ventormenta",
        "Desde el puerto, sube a la ciudad y busca a Baros Alexston en la plaza de la Catedral.", "f"),
})
link(redridge, duskwood, {
    stop("three-corners", 1433, 11.9, 73.3, 66, "Cruce de Tres Caminos",
        "Sal de Villa del Lago hacia el oeste hasta el cruce de Tres Caminos. Toma la carretera del sur.", "f"),
    cross(stop("duskwood-road", 1433, 7.10, 89.26, 36, "Camino del Bosque del Ocaso",
        "Continúa por la carretera del sur hasta cruzar al Bosque del Ocaso.")),
    landing("darkshire", "Sigue la carretera hasta Villa Oscura. Felicia Maline cuida los grifos al este del pueblo."),
})
link(duskwood, ashenvale, {
    -- The last class trainer is in Stormwind for most classes. Shamans are
    -- in Ironforge. Both pick up the same journey at their actual location.
    west[3], west[4], west[5], swAuber,
    landing("auberdine", "Baja del barco y sigue el muelle hasta el poblado. Aquí empieza el tramo de vuestra clase."),
})
link(ashenvale, thousandNeedles, {flight("stormwind", "darkshire"), landing("darkshire")}, {1})
link(thousandNeedles, hillsbrad30, {
    -- The source ends with a hearth. The walk is the way back when somebody
    -- skipped that action, changed their bind or has the stone on cooldown.
    cross(stop("great-lift", 1441, 31.92, 24.22, 38, "Gran Elevador a Los Baldíos",
        "Si tu piedra marca la taberna Aguahonda, úsala. A pie, vuelve por el cañón hacia el noroeste y sube en el Gran Elevador.")),
    cross(stop("dustwallow-road", 1413, 49.53, 78.41, 38, "Carretera a Marjal Revolcafango",
        "Desde el elevador sigue la carretera hacia el norte. Toma el desvío al este hacia Marjal Revolcafango.")),
    theraMen,
    stop("stoutfist", 1437, 9.86, 57.49, 50, "Castillo de Menethil",
        "Desde la taberna o el muelle, entra en el castillo y busca al capitán Puñorrecio."),
})
link(hillsbrad30, desolace30, {flight("ironforge", "menethil"), landing("menethil")}, {1})
link(desolace30, ashenvale30, {flight("nijel", "astranaar"), landing("astranaar")}, {1})
link(ashenvale30, stranglethorn30, {flight("menethil", "ironforge"), landing("ironforge")}, {1})
link(stranglethorn30, arathi30, {flight("bootybay", "darkshire"), landing("darkshire")}, {1})
link(arathi30, badlands30, {
    lochBad, badLochSide,
    stop("hammertoe", 1418, 53.42, 43.39, 55, "Excavación de Piemartillo",
        "Sigue el camino hacia el sur hasta el campamento de la excavación. Busca al prospector Ryedol."),
})
link(badlands30, stranglethorn40, {
    flight("nijel", "theramore"),
    stop("morgan", 1445, 66.34, 45.47, 47, "Taberna de Theramore",
        "Desde los grifos, entra en la taberna de Theramore. Allí está Morgan Stern."),
})
link(stranglethorn40, badlands40, {west[1], west[2], flight("ironforge", "thelsamar"), landing("thelsamar")}, {1})

link(badlands40, feralas40, {
    flight("theramore", "nijel"),
    cross(stop("desolace-south", 1443, 40.91, 90.72, 42, "Paso del sur a Feralas",
        "Desde Punta de Nijel baja a la carretera y síguela hacia el sur. Cruza a Feralas por el paso junto al poblado Gelkis.")),
    coastShip, moonPier, landing("feathermoon", "Desde el embarcadero avanza hacia el sur, hasta los hipogrifos de Bastión Plumaluna."),
})
link(feralas40, tanaris40, {
    coastShip, moonPier, flight("feathermoon", "thalanaar"), landing("thalanaar"),
    cross(stop("feralas-east", 1444, 89.10, 41.14, 42, "Entrada a Las Mil Agujas",
        "Desde Thalanaar toma el camino hacia Las Mil Agujas.")),
    stop("needles-west", 1441, 7.98, 10.93, 68, "Camino de Las Mil Agujas",
        "Sigue la carretera principal del cañón hacia el sureste y entra en las Salinas."),
    raceway,
})
link(tanaris40, hinterlands40, {
    flight("ironforge", "aerie"),
    stop("fraggar", 1425, 14.83, 44.57, 55, "Fraggar Mantrueno en Pico Nidal",
        "Desde los grifos, sigue el camino del asentamiento enano hasta Fraggar Mantrueno."),
})
link(hinterlands40, searing40, {
    board(stop("darn-return", 1457, 29.13, 41.21, 20, "Regresa a Thelsamar",
        "Usa tu piedra si está ligada a Thelsamar. Para volver en barco, cruza el portal a Rut'theran.")),
    rutShip,
    board(stop("auber-men", 1439, 32.34, 44.13, 30, "Barco al Puerto de Menethil",
        "Toma el barco de Los Humedales. Si hace escala en Costasur, sigue a bordo hasta Menethil.")),
    flight("menethil", "thelsamar"),
    lochBad, badLochSide,
    cross(stop("searing-pass", 1418, 1.09, 62.92, 42, "Paso a la Garganta de Fuego",
        "Ve hacia el oeste y rodea Kargath por el sur. Sube por el paso de montaña hasta la Garganta de Fuego.")),
    landing("thorium", "Sigue el camino que sube al Puesto del Torio y reúnete junto a Lanie Reed."),
})
link(searing40, ungoro40, {
    flight("thorium", "thelsamar", "Puedes usar la piedra si está ligada a Thelsamar."),
    flight("thelsamar", "menethil"), menThera,
    flight("theramore", "gadgetzan"), landing("gadgetzan"),
}, {1})
link(ungoro40, burning50, {flight("ironforge", "menethil"), landing("menethil")}, {1})
link(burning50, felwood50, {darnPortal, rutShip, flight("auberdine", "astranaar"), landing("astranaar")}, {1})
link(felwood50, winterspring50, {
    cross(stop("timbermaw", 1448, 64.97, 8.36, 38, "Túnel del Bastión Fauces de Madera",
        "Desde Frondavil sigue la carretera al norte. Entra en el túnel y toma la salida este hacia Cuna del Invierno.")),
    stop("winter-mouth", 1452, 27.96, 34.56, 60, "Salida a Cuna del Invierno",
        "Al salir del túnel, sigue la carretera hacia el este hasta Vista Eterna."),
    stop("jessica", 1452, 61.28, 38.98, 55, "Vista Eterna",
        "Entra en el poblado y ve al edificio donde esperan Jessica Rutagrana y Gregor Pedragris."),
})
link(winterspring50, plaguelands50, {flight("lightshope", "chillwind"), landing("chillwind")}, {1})
link(plaguelands50, silithus50, {
    flight("moonglade", "ratchet", "Puedes usar la piedra si está ligada a Trinquete."),
    flight("ratchet", "gadgetzan"), landing("gadgetzan"),
}, {1})
link(silithus50, silithusFinal, {
    flight("lightshope", "bootybay", "Usa la piedra si está ligada a Trinquete. Para volver en barco, empieza por este vuelo."),
    board(stop("booty-ratchet", 1434, 26.35, 73.56, 30, "Barco a Trinquete",
        "Sube al barco del muelle de Bahía del Botín y desembarca en Trinquete.")),
    flight("ratchet", "astranaar"), landing("astranaar"),
}, {1})
