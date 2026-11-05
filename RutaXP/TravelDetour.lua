local _, ns = ...
local routing = ns.TravelRouting

-- Match only authored taxi departures. A missing flight path does not imply
-- that two points on the same map are connected: Feathermoon is an island.
-- Ferry ends are SendaFH Nav/TravelData.lua boat-feathermoon; the Crossroads
-- is Horde taxi node 25. The roads are described by the corresponding guides.
local localRoads = {
    ["fly-booty-gromgol"] = {
        instructions = "Sal de Bahía del Botín por el túnel. Sigue la carretera al norte y toma el ramal oeste a Grom'gol.",
    },
    ["fly-ratchet-taurajo"] = {
        {id = "gold-road", map = 1413, f = "e", x = 51.50, y = 30.41, radius = 75,
            title = "Camino del Oro", text = "Sal de Trinquete por la carretera oeste hacia El Cruce."},
        instructions = "Desde El Cruce sigue el Camino del Oro al sur hasta el Campamento Taurajo.",
    },
    ["feathermoon-to-thalanaar"] = {
        {id = "island-ferry", map = 1444, f = "e", x = 31.01, y = 39.51, radius = 32, boundary = true,
            title = "Barco a la costa de Feralas", text = "Embarca en el muelle de Plumaluna y baja en la Costa Olvidada."},
        {id = "coast-ferry", map = 1444, f = "e", x = 43.13, y = 42.76, radius = 58,
            title = "Costa Olvidada", text = "Desembarca y busca la carretera de Feralas."},
        instructions = "Sigue la carretera hacia el este por Feralas, rodea el Campamento Mojache y continúa hasta Thalanaar.",
    },
}

local function destinationLeg(taxi)
    local landing = taxi.taxiLanding
    local road = localRoads[taxi.id]
    return { id = "ground-" .. taxi.id, map = landing.map, x = landing.x, y = landing.y, f = landing.f,
        radius = landing.radius, title = landing.title,
        text = road and road.instructions or ("Sigue el camino hasta el maestro de vuelo de " .. landing.title .. " para retomar el recorrido.") }
end

local available = {}
function ns:CanGroundDetour(taxi, zone, sample)
    if not taxi.taxiLanding or taxi.map ~= zone or not routing.Near(taxi, sample) then return false end
    if zone == taxi.taxiLanding.map then return localRoads[taxi.id] ~= nil end
    local key = table.concat({UnitFactionGroup("player") or "", zone, taxi.taxiLanding.map}, ":")
    if available[key] == nil then
        available[key] = routing.Rejoin({taxi.taxiLanding}, zone, sample) ~= nil
    end
    return available[key]
end

function ns:BeginGroundDetour()
    self:UpdateGuideTravel()
    local view = self:GetGuideTravel()
    local option = view and view.groundOption
    local trip = option and self.char.guideTrips and self.char.guideTrips[option.source]
    if not trip or trip.ready or trip.skipped or view.waiting then return false end
    trip.groundDetour = {id = option.leg, index = option.index}
    self:Sync()
    return true
end

local function localLeg(taxi, finish, saved, zone, sample)
    local road = localRoads[taxi.id]
    if not road or #road == 0 then return finish end
    local path = {}
    for _, leg in ipairs(road) do path[#path + 1] = leg end
    path[#path + 1] = finish
    local index, near = routing.Locate(path, zone, saved.localIndex, sample)
    if not index then return end
    if near and not path[index].boundary and index < #path then index = index + 1 end
    saved.localIndex = index
    return path[index]
end

-- Only the walker's private instruction changes. The shared checkpoint
-- stays at the departure until they have physically reached the taxi stop.
function ns:GetGroundDetour(source, legs, trip, zone, sample)
    local saved = trip.groundDetour
    if not saved then return end
    local taxi = type(saved) == "table" and legs[saved.index]
    if not taxi or taxi.id ~= saved.id or not taxi.taxiLanding or not legs[saved.index + 1] then
        trip.groundDetour = nil
        return
    end
    local finish = destinationLeg(taxi)
    if zone == finish.map and routing.Near(finish, sample) and not routing.OnTaxi() then
        trip.groundDetour = nil
        trip.reached = math.max(trip.reached or 0, saved.index)
        trip.index = saved.index + 1
        trip.leg = legs[trip.index].id
        return
    end
    local leg
    if zone == finish.map then
        leg = localLeg(taxi, finish, saved, zone, sample)
    elseif zone then
        leg = routing.Rejoin({finish}, zone, sample)
    end
    local near = leg and leg.boundary and routing.Near(leg, sample)
    if near then saved.crossing = leg.text end
    local point = leg and not near and self:ResolveWaypointPoint(leg)
    local id = taxi.id .. "/ground/" .. (leg and leg.id or "transfer")
    if point then point.source, point.targetKey, point.label = "guide-travel", source .. ":" .. id, leg.title end
    return {id = id, index = saved.index, total = #legs, title = leg and leg.title or "En tránsito",
        text = leg and leg.text or saved.crossing or "Sal al exterior para retomar el camino.",
        point = point or nil}
end
