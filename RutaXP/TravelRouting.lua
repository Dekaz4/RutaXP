local _, ns = ...
local routing = {}
ns.TravelRouting = routing
local TRAM = 369
local TELDRASSIL, TREETOP = 1438, "teldrassil-treetop"
local known = { [TRAM] = true }
local graph = { Alliance = {}, Horde = {} }

local function value(fn, index, ...)
    if type(fn) ~= "function" then return end
    local result = { pcall(fn, ...) }
    if not result[1] then return end
    local a, b = result[index + 1], result[index + 2]
    if issecretvalue and (issecretvalue(a) or issecretvalue(b)) then return end
    return a, b
end

local function registerLegs(legs)
    for _, leg in ipairs(legs) do known[leg.map or leg.instanceID] = true end
end
for _, route in pairs(ns.GuideTravelRoutes) do
    registerLegs(route.legs)
    for _, variant in ipairs(route.variants or {}) do registerLegs(variant.legs) end
end
-- Map 1438 covers two disconnected surfaces. SendaFH's only road on
-- this map is the upper gate to Darnassus. The boats and portal serve
-- Rut'theran below. Keep both in the graph with their real map coordinates.
local function nodeFor(pin, kind)
    if pin.map == TELDRASSIL and (kind == "road" or pin.treetop) then return TREETOP end
    return pin.map or pin.instanceID
end

local function edge(network, kind, a, b)
    known[a.map], known[b.map] = true, true
    local node = nodeFor(a, kind)
    local exits = network[node] or {}
    network[node] = exits
    exits[#exits + 1] = { kind = kind, from = a, to = b, target = nodeFor(b, kind) }
end
for _, c in ipairs(ns.GuideTravelConnections) do
    for faction, network in pairs(graph) do
        if c.mask == 3 or (faction == "Alliance" and c.mask == 1) or (faction == "Horde" and c.mask == 2) then
            edge(network, c.kind, c.a, c.b)
            if not c.oneWay then edge(network, c.kind, c.b, c.a) end
        end
    end
end

function routing.Zone()
    if value(GetInstanceInfo, 8) == TRAM or value(UnitPosition, 4, "player") == TRAM then return TRAM end
    local zone = value(GetRealZoneText, 1) or value(GetZoneText, 1)
    if zone and zone == value(C_Map and C_Map.GetAreaInfo, 1, 2257) then return TRAM end
    if value(IsInInstance, 1) then return end
    local map = value(C_Map and C_Map.GetBestMapForUnit, 1, "player")
    for _ = 1, 6 do
        if not map or map == 0 then break end
        if known[map] and map ~= TRAM then return map end
        local info = value(C_Map and C_Map.GetMapInfo, 1, map)
        map = info and info.parentMapID
    end
    if zone and zone ~= "" then
        for id in pairs(known) do
            local info = value(C_Map and C_Map.GetMapInfo, 1, id)
            if id ~= TRAM and info and info.name == zone then return id end
        end
    end
end

-- One world sample for all candidate legs in this tick. Era and live points
-- can coexist on the same map (particularly the Forever-only harbours).
function routing.Sample(map)
    if not map or map == TRAM then return end
    local raw = value(C_Map and C_Map.GetPlayerMapPosition, 1, map, "player")
    if not raw then return end
    local continent, world = value(C_Map.GetWorldPosFromMapPos, 1, map, raw)
    if not world then return end
    local north, west = value(world.GetXY, 1, world)
    if type(north) ~= "number" or type(west) ~= "number" then return end
    local bounds = ns.mapFrames and ns.mapFrames.era[map]
    return function(leg)
        local n, w
        if leg.map == map and leg.x and leg.y then
            if leg.f == "e" then
                if bounds and bounds.c == continent then
                    n = bounds.top + (bounds.bottom - bounds.top) * leg.y / 100
                    w = bounds.left + (bounds.right - bounds.left) * leg.x / 100
                end
            else
                local vector = value(CreateVector2D, 1, leg.x / 100, leg.y / 100)
                local c, p = value(C_Map.GetWorldPosFromMapPos, 1, map, vector)
                if c == continent and p then n, w = value(p.GetXY, 1, p) end
            end
        end
        if type(n) ~= "number" or type(w) ~= "number" then return nil, nil, math.huge end
        n, w = n - north, w - west
        return n, w, n * n + w * w
    end
end

function routing.Near(leg, sample)
    return sample and select(3, sample(leg)) <= (leg.radius or 30)^2
end

-- Observed positions in the compiled Teldrassil guide: upper quest NPCs
-- are at 1255.9 yd and higher, Rut'theran NPCs at 12.9–23.6 yd. Use the
-- localized subzone first. If neither that nor a reliable height is
-- available, recognize only actual settlement, gate and transport pins.
local islandLandmarks = {
    {36.32, 54.38, TREETOP}, -- Darnassus gate (Carbonite)
    {55.10, 56.90, TREETOP}, -- Dolanaar (exploration guide)
    {55.62, 59.79, TREETOP}, -- Dolanaar inn
    {55.60, 90.90, TELDRASSIL}, -- Rut'theran Village (exploration guide)
    {55.87, 89.34, TELDRASSIL}, -- Portal
    {58.40, 93.93, TELDRASSIL}, -- Flight master
    {54.79, 97.17, TELDRASSIL}, -- Auberdine ferry
}
local function currentNode(zone, sample)
    if zone ~= TELDRASSIL then return zone end
    local area = value(GetSubZoneText, 1)
    if not area or area == "" then area = value(GetMinimapZoneText, 1) end
    if area and area ~= "" then
        if area == value(C_Map and C_Map.GetAreaInfo, 1, 702) then return TELDRASSIL end
        if area == value(C_Map and C_Map.GetAreaInfo, 1, 186) then return TREETOP end
    end
    if sample then
        for _, spot in ipairs(islandLandmarks) do
            if routing.Near({map = zone, f = "e", x = spot[1], y = spot[2], radius = 65}, sample) then
                return spot[3]
            end
        end
    end
    local height, continent = value(UnitPosition, 3, "player")
    if continent == 1 and type(height) == "number" then
        if height >= 1255.9 then return TREETOP end
        if height <= 23.6 then return TELDRASSIL end
    end
end

-- Once at the pier, keep the boarding instruction over the water. Never
-- use the sea corridor itself as proof that the player has disembarked.
function routing.BetweenStops(a, b, sample)
    if not sample or a.map ~= b.map then return false end
    local n, w = sample(a)
    local bn, bw = sample(b)
    if not n or not bn then return false end
    local dn, dw = bn-n, bw-w
    local length = dn*dn + dw*dw
    if length == 0 then return false end
    local t = -(n*dn + w*dw) / length
    return t > 0 and t < 1 and (n+t*dn)^2 + (w+t*dw)^2 < 180^2
end

-- Never project a walk across a flight, a portal, or two separate visits
-- to the same map. A later visit can be recognized by physical proximity.
function routing.Locate(legs, zone, saved, sample)
    local first, last, chosen, best
    local current = currentNode(zone, sample)
    if not current then return end
    local i = 1
    while i <= #legs do
        local start, node = i, nodeFor(legs[i])
        while i < #legs and not legs[i].boundary and nodeFor(legs[i+1]) == node do i = i + 1 end
        if node == current then
            local distance = math.huge
            for k = start, i do
                if sample then distance = math.min(distance, select(3, sample(legs[k]))) end
            end
            local preferred = saved and start <= saved and saved <= i
            -- Keep the current visit until there is evidence of a different
            -- one. Exact landings on the same map beat a distant departure.
            local score = distance
            if preferred then score = math.min(distance, 160^2) end
            if not first or score < best or (score == best and preferred) then
                first, last, chosen, best = start, i, preferred and saved or start, score
            end
        end
        i = i + 1
    end
    if not first then return end
    if not sample then return chosen end
    for k = last, chosen, -1 do
        local leg = legs[k]
        local n, w, d = sample(leg)
        if d <= (leg.radius or 30)^2 then return k, true end
        if n and k > chosen then
            local prev = legs[k-1]
            local pn, pw = sample(prev)
            if pn then
                local dn, dw = n-pn, w-pw
                local length = dn*dn + dw*dw
                if length > 0 then
                    local t = -(pn*dn + pw*dw) / length
                    local radius = math.max(prev.radius or 30, leg.radius or 30)
                    if t > 0 and t < 1 and (pn+t*dn)^2 + (pw+t*dw)^2 <= radius^2 then return k end
                end
            end
        end
    end
    return chosen
end

local directions = {
    boat = "Espera en este muelle y toma el barco hacia ",
    zeppelin = "Sube a la torre y toma el zepelín hacia ",
    tram = "Entra en la estación y toma el tren hacia ",
    portal = "Atraviesa el portal hacia ",
    road = "Sigue la carretera y cruza el paso hacia ",
}
-- Search from the player's zone. The returned departure always belongs to
-- the current map, including after a hearthstone or an unexpected boat.
function routing.Rejoin(legs, zone, sample, reached)
    local network = graph[UnitFactionGroup("player")]
    local current = currentNode(zone, sample)
    if zone == TELDRASSIL and network == graph.Horde then
        return {id = "teldrassil-horde", title = "Sal de Teldrassil",
            text = "Estás en territorio de la Alianza. Usa tu piedra de hogar para retomar la ruta de la Horda."}
    elseif not current and zone == TELDRASSIL then
        return {id = "teldrassil-level", title = "Salida de Teldrassil",
            text = "Si estás en la copa, sigue la carretera hasta la puerta de Darnassus. Si estás en la aldea del puerto, acércate al portal de Rut'theran para retomar la flecha."}
    end
    if not network or not network[current] then return end
    local targets = {}
    for i = math.min((reached or 0) + 1, #legs), #legs do
        if legs[i].map then targets[nodeFor(legs[i])] = true end
    end
    local queue, seen = {}, { [current] = true }
    local exits = {}
    for i, e in ipairs(network[current]) do exits[i] = e end
    if sample then
        table.sort(exits, function(a,b) return select(3,sample(a.from)) < select(3,sample(b.from)) end)
    end
    for _, e in ipairs(exits) do
        if not seen[e.target] then
            seen[e.target] = true
            queue[#queue + 1] = { node = e.target, first = e }
        end
    end
    local head = 1
    while head <= #queue do
        local entry = queue[head]
        if targets[entry.node] then
            local e = entry.first
            local info = value(C_Map and C_Map.GetMapInfo, 1, e.to.map)
            local name = info and info.name or "la siguiente zona"
            if e.target == 1457 then name = "Darnassus"
            elseif e.target == TELDRASSIL then name = "Rut'theran"
            elseif e.target == TREETOP then name = "la copa de Teldrassil" end
            return { map = zone, x = e.from.x, y = e.from.y, f = e.from.f, radius = 32, boundary = true,
                id = "rejoin-" .. zone .. "-" .. e.to.map, title = "Hacia " .. name,
                text = directions[e.kind] .. name .. "." }
        end
        for _, e in ipairs(network[entry.node] or {}) do
            if not seen[e.target] then
                seen[e.target] = true
                queue[#queue+1] = { node = e.target, first = entry.first }
            end
        end
        head = head + 1
    end
end

function routing.OnTaxi()
    local flying = value(UnitOnTaxi, 1, "player")
    return flying == true or flying == 1
end
