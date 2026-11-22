local _, ns = ...
if ns.FlightNavigation then return end

-- Connectivity belongs to the open flight master. GetTaxiNodesForMap only
-- describes the map; it cannot establish a usable route. API contract:
-- Gethe/wow-ui-source 4cd0ab752a77164f654ccbca9d0c1fe8dafceebe,
-- Blizzard_APIDocumentationGenerated/TaxiMapDocumentation.lua (Forever 70888).
-- Observe the player's choices only. This module never calls TakeTaxiNode.
local F = {}
ns.FlightNavigation = F
local R = ns.TravelRouting
local function read(fn, ...)
    if type(fn) ~= "function" then return end
    local ok, a, b = pcall(fn, ...)
    if not ok or (issecretvalue and (issecretvalue(a) or issecretvalue(b))) then return end
    return a, b
end
local function number(v)
    return not (issecretvalue and issecretvalue(v)) and type(v) == "number"
        and v == v and math.abs(v) < math.huge
end
local function text(v)
    return not (issecretvalue and issecretvalue(v)) and type(v) == "string" and v ~= "" and v or nil
end
local function copy(t)
    local out = {}; for k, v in pairs(t) do out[k] = v end; return out
end
local function short(name)
    local prefix = text(name) and name:match("^[^,]+")
    return prefix and prefix:lower():gsub("^%s+", ""):gsub("%s+$", "") or nil
end
local function factionCode()
    local faction = read(UnitFactionGroup, "player")
    return faction == "Alliance" and "A" or faction == "Horde" and "H"
end
local function forFaction(c, code) return not c.faction or c.faction == "AH" or c.faction == code end
local function destinations(goal)
    local ids, result = {}, {}
    local code = factionCode()
    for _, c in ipairs(goal and goal.candidates or {}) do
        if forFaction(c, code) then
            for _, id in ipairs(c.destinationNodes or {}) do ids[id] = true end
        end
    end
    for _, c in ipairs(goal and goal.candidates or {}) do
        if ids[c.flightNode] and forFaction(c, code) then
            result[#result + 1] = c
        end
    end
    return result, ids
end
local function keyFor(goal, guide, stepIndex, index)
    if not goal or goal.t ~= "fly" or not guide or not stepIndex or not index then return end
    local _, ids = destinations(goal)
    local ordered = {}; for id in pairs(ids) do ordered[#ordered + 1] = id end; table.sort(ordered)
    if #ordered == 0 then return end
    return table.concat({guide.id, guide.routeRevision or 1, stepIndex, index, table.concat(ordered, ",")}, ":")
end
local function storage()
    if not ns.char then return end
    local saved = ns.char.flightNavigation
    if type(saved) ~= "table" then saved = {}; ns.char.flightNavigation = saved end
    if type(saved.arrivals) ~= "table" then saved.arrivals = {} end
    return saved
end
local function context(goal)
    if not ns.char or not ns.GetCurrent or not ns.GetActiveGoal then return end
    if ns.GetGuideTravel and ns:GetGuideTravel() then return end
    local shared = ns.DuoAuto and ns.DuoAuto.GetSharedView and ns.DuoAuto:GetSharedView()
    if shared and shared.following then return end
    local guide, step, state = ns:GetCurrent()
    if not guide or not step or not state or state.review then return end
    local active, index = ns:GetActiveGoal(step, state)
    if not active or active.t ~= "fly" or (goal and goal ~= active) then return end
    local key = keyFor(active, guide, state.cursor, index)
    if not key then return end
    return {goal=active, guide=guide, step=step, progress=state, index=index, key=key}
end
local function near(point, zone, sample, radius)
    if not point or point.map ~= zone or not sample then return false end
    local p = copy(point); p.radius = radius or 45
    return R.Near(p, sample)
end
local function originCandidate(goal, origin, zone, sample)
    for _, c in ipairs(goal.candidates or {}) do
        if c.flightNode == origin and near(c, zone, sample, 100) then return c end
    end
end
local function arrival(ctx)
    if not ctx or not R or R.OnTaxi() or (ns.IsRecoveringCorpse and ns:IsRecoveringCorpse()) then return false end
    local zone = R.Zone(); local sample = R.Sample(zone)
    for _, landing in ipairs(destinations(ctx.goal)) do
        if near(landing, zone, sample) then
            local saved = storage()
            if saved.arrivals[ctx.key] then return false end
            local count = 0; for _ in pairs(saved.arrivals) do count = count + 1 end
            if count >= 128 then return false end
            saved.arrivals[ctx.key] = {destination=landing.flightNode}
            F.arrivalDirty = true
            if saved.ground and saved.ground.key == ctx.key then saved.ground = nil end
            return true
        end
    end
    return false
end

function F:IsComplete(goal, guide, stepIndex, index, state)
    if state and state.review then return false end
    local key = keyFor(goal, guide, stepIndex, index)
    local saved = ns.char and ns.char.flightNavigation
    local record = key and type(saved) == "table" and type(saved.arrivals) == "table" and saved.arrivals[key]
    local _, ids = destinations(goal)
    if type(record) == "table" and ids[record.destination] == true then return true end
    if not key or type(saved) ~= "table" or type(saved.arrivals) ~= "table" then return false end
    -- A guide repair can reopen an earlier visit after the player has left its
    -- landing point. Preserve a real arrival only through authored migrations
    -- identifying the same action and the exact same destination set.
    local prefix, target = guide.id .. ":", tostring(stepIndex) .. ":" .. tostring(index)
    local signature, current = key:match(":([%d,]+)$"), guide.routeRevision or 1
    for oldKey, oldRecord in pairs(saved.arrivals) do
        if type(oldKey) == "string" and oldKey:sub(1, #prefix) == prefix
            and type(oldRecord) == "table" and ids[oldRecord.destination] == true then
            local revision, step, goalIndex, oldSignature = oldKey:sub(#prefix + 1):match("^(%d+):(%d+):(%d+):([%d,]+)$")
            revision = tonumber(revision)
            local mapped = step and (step .. ":" .. goalIndex)
            if revision and revision < current and oldSignature == signature then
                for _ = 1, 20 do
                    local nextMigration
                    for _, migration in ipairs(guide.progressMigrations or {}) do
                        if migration.from == revision and migration.to > revision then nextMigration = migration; break end
                    end
                    if not nextMigration or (nextMigration.retiredGoalKeys or {})[mapped] then break end
                    mapped = (nextMigration.goalMap or {})[mapped] or mapped
                    revision = nextMigration.to
                    if revision == current and mapped == target then return true end
                    if revision >= current then break end
                end
            end
        end
    end
    return false
end

local function classify(slot, state)
    if not number(state) then state = nil end
    local enums = Enum and Enum.FlightPathState or {}
    local kind = number(slot) and read(TaxiNodeGetType, slot)
    if kind == "CURRENT" or state == (enums.Current or 0) then return "current" end
    if kind == "UNREACHABLE" or kind == "DISTANT" or kind == "NONE"
        or state == (enums.Unreachable or 2) then return "unavailable" end
    if kind == "REACHABLE" or state == (enums.Reachable or 1) then
        local routes = number(slot) and read(GetNumRoutes, slot)
        if number(routes) and routes == 0 then return "unavailable" end
        return "reachable"
    end
end

-- Journey planning can use a flight master visited outside an authored flight
-- step. Store only directed connections actually offered to this character.
local function rememberConnections(observation)
    if not ns.char or not observation.origin then return end
    local routes = ns.char.observedTaxiRoutes
    if type(routes) ~= "table" then routes = {}; ns.char.observedTaxiRoutes = routes end
    -- A legacy master may report only the current guide destination. Missing
    -- rows and unreadable states are not observations about any old route.
    local reachable = type(routes[observation.origin]) == "table" and routes[observation.origin] or {}
    for id, node in pairs(observation.nodes) do
        if node.slot and node.kind == "reachable" then reachable[id] = true
        elseif node.kind == "unavailable" then reachable[id] = nil end
    end
    routes[observation.origin] = reachable
    F.routeRevision = (F.routeRevision or 0) + 1
    F.lastTaxiVisit = observation
end

function F:HasObservedConnection(origin, destination)
    local routes = ns.char and ns.char.observedTaxiRoutes
    return type(routes) == "table" and type(routes[origin]) == "table" and routes[origin][destination] == true
end

function F:GetPlanningConnection(goal, zone)
    local landings, ids = destinations(goal)
    local map = landings[1] and landings[1].map
    if not map or map == zone then return end
    for _, landing in ipairs(landings) do if map ~= landing.map then return end end
    local sample, code = R.Sample(zone), factionCode()
    local origin, nearest = nil, math.huge
    for _, c in ipairs(goal.candidates or {}) do
        if sample and c.flightNode and not ids[c.flightNode] and c.map == zone and forFaction(c, code) then
            local _, _, distance = sample(c)
            if distance < nearest then origin, nearest = c.flightNode, distance end
        end
    end
    for _, landing in ipairs(landings) do
        if origin and self:HasObservedConnection(origin, landing.flightNode) then return map, true end
    end
    return map, false
end

function F:ObserveTaxi()
    self.observation, self.lastTaxiVisit, self.attempt, self.pendingError = nil, nil, nil, nil
    local ctx = context()
    if not ns.char or R.OnTaxi() then return end
    local map = read(GetTaxiMapID)
    local nodes = number(map) and read(C_TaxiMap and C_TaxiMap.GetAllTaxiNodes, map)
    local result = {key=ctx and ctx.key, owner=ns.char, nodes={}, slots={}, at=read(GetTime) or 0}
    if type(nodes) == "table" then
        for _, node in ipairs(nodes) do
            if type(node) == "table" and number(node.nodeID) then
                local slot = node.slotIndex
                if not number(slot) or slot < 1 or slot ~= math.floor(slot) then slot = nil end
                local kind = classify(slot, node.state)
                result.nodes[node.nodeID] = {kind=kind, name=text(node.name), slot=slot}
                if slot then result.slots[slot] = node.nodeID end
                if kind == "current" then
                    if result.origin and result.origin ~= node.nodeID then return end
                    result.origin = node.nodeID
                end
            end
        end
    elseif ctx then
        -- Older clients expose no node ID. Only identify this goal's exact
        -- destination name; never guess intermediate hubs from translated names.
        local count = read(NumTaxiNodes)
        if not number(count) or count < 1 or count > 1000 then return end
        local zone = R.Zone(); local sample = R.Sample(zone)
        local currentSlot, matches = nil, {}
        for slot = 1, count do
            local kind = read(TaxiNodeGetType, slot)
            if kind == "CURRENT" then
                if currentSlot then return end
                currentSlot = slot
            end
            if text(ctx.goal.location) and short(read(TaxiNodeName, slot)) == short(ctx.goal.location) then matches[#matches + 1] = slot end
        end
        if not currentSlot then return end
        for _, c in ipairs(ctx.goal.candidates or {}) do
            if near(c, zone, sample, 100) then
                if result.origin and result.origin ~= c.flightNode then return end
                result.origin = c.flightNode
            end
        end
        local landings = destinations(ctx.goal)
        if #landings == 1 and #matches == 1 then
            local slot = matches[1]; local id = landings[1].flightNode
            result.nodes[id] = {kind=classify(slot), name=read(TaxiNodeName, slot), slot=slot}
            result.slots[slot] = id
        end
    end
    rememberConnections(result)
    if not ctx then return end
    local zone = R.Zone(); local sample = R.Sample(zone)
    if result.origin and originCandidate(ctx.goal, result.origin, zone, sample) then self.observation = result end
end

local function snapshot(self, ctx, zone, sample)
    local observed = self.observation
    local time = read(GetTime) or 0
    if observed and observed.owner == ns.char and observed.key == ctx.key
        and time >= observed.at and time - observed.at <= 120
        and originCandidate(ctx.goal, observed.origin, zone, sample) then return observed end
    self.observation, self.attempt, self.pendingError = nil, nil, nil
end
local function endpoint(goal, zone, sample)
    local best, distance
    for _, landing in ipairs(destinations(goal)) do
        local hops = R.DistanceTo and R.DistanceTo(landing, zone, sample)
        if not best or (hops and (not distance or hops < distance)) then best, distance = landing, hops end
    end
    return best, distance
end
local function point(raw, goal, label, key)
    local p = raw and ns:ResolveWaypointPoint(raw)
    if p then p.goal, p.label, p.source, p.targetKey = goal, label, "flight-navigation", key end
    return p
end
local function groundPossible(landing, zone, sample)
    -- The general zone graph has no distinction between Feathermoon island
    -- and the mainland. Do not invent a walk across that water.
    if not landing or landing.flightNode == 31 then return false end
    local hops = R.DistanceTo and R.DistanceTo(landing, zone, sample)
    return hops ~= nil and (hops > 0 or landing.map ~= zone)
end
local function groundView(ctx, landing, zone, sample)
    local ground = storage().ground
    local hops = R.DistanceTo and R.DistanceTo(landing, zone, sample)
    local leg = hops == 0 and landing or R.Rejoin({landing}, zone, sample)
    if not leg then
        return {state="ground", title="Hacia " .. (ctx.goal.location or "el destino"), shortText="Retoma el camino",
            text=ground.crossing or ("Sal al exterior para retomar el trayecto hasta " .. (ctx.goal.location or "el destino") .. ".")}
    end
    if ground.crossingFrom ~= zone then ground.crossing, ground.crossingFrom = nil, nil end
    local atBoundary = leg.boundary and near(leg, zone, sample, leg.radius)
    if atBoundary then ground.crossing, ground.crossingFrom = leg.text, zone end
    local label = leg.title or ctx.goal.location or "Destino del viaje"
    return {state="ground", title=label, shortText=leg.boundary and leg.title or "Camino al destino",
        text=leg.text or ("Sigue el camino hasta el maestro de vuelo de " .. label .. "."),
        point=not atBoundary
            and point(leg, ctx.goal, label, ctx.key .. ":ground:" .. (leg.id or landing.flightNode)) or nil}
end

function F:GetView(goal, base)
    local ctx = context(goal)
    if not ctx then return end
    if R.OnTaxi() then return {state="flying", title="En vuelo", shortText="En vuelo", text="Espera a aterrizar para continuar."} end
    if arrival(ctx) or self:IsComplete(ctx.goal, ctx.guide, ctx.progress.cursor, ctx.index, ctx.progress) then
        return {state="arrived", title="Destino alcanzado", shortText="Has llegado", text="Has llegado al destino del viaje."}
    end
    local zone = R.Zone(); local sample = R.Sample(zone)
    local landing, hops = endpoint(ctx.goal, zone, sample)
    if not landing then return end
    local saved = storage()
    if saved.ground and saved.ground.key == ctx.key and saved.ground.destination == landing.flightNode then
        return groundView(ctx, landing, zone, sample)
    end
    local observed = snapshot(self, ctx, zone, sample)
    local name = ctx.goal.location or "el destino"
    base = base or (ns.GetGoalWaypoint and ns:GetGoalWaypoint(ctx.goal))
    local canGround = groundPossible(landing, zone, sample)
    local _, ids = destinations(ctx.goal)
    local allUnavailable = observed ~= nil
    for id in pairs(ids) do
        local record = observed and observed.nodes[id]
        if record and record.kind == "reachable" then
            local instruction = "El vuelo a " .. name .. " está disponible. Elígelo en el mapa de vuelos."
            if observed.origin == 26 and id == 28 then
                instruction = "Desde el icono verde de Auberdine, baja un poco y mira a la derecha. Elige «" ..
                    (record.name or name) .. "»."
            end
            return {state="available", title="Vuela a " .. name, shortText="Elige " .. name,
                text=instruction, point=base, canGround=canGround}
        end
        if not record or record.kind ~= "unavailable" then allUnavailable = false end
    end
    if allUnavailable then
        local hub, hubRecord, hubDistance
        for _, candidate in ipairs(ctx.goal.candidates or {}) do
            local record = observed.nodes[candidate.flightNode]
            if not ids[candidate.flightNode] and record and record.kind == "reachable" then
                -- DistanceTo uses the sample only to disambiguate disconnected
                -- Teldrassil surfaces; their destinations need a proper sample.
                local distance = candidate.map ~= 1438 and R.DistanceTo and R.DistanceTo(landing, candidate.map)
                if distance and hops and distance < hops and (not hubDistance or distance < hubDistance) then
                    hub, hubRecord, hubDistance = candidate, record, distance
                end
            end
        end
        if hub and text(hubRecord.name) then
            return {state="connection", title="Vuela a " .. hubRecord.name, shortText="Vuela a " .. hubRecord.name,
                text="Desde aquí no puedes volar a " .. name .. ". Vuela a " .. hubRecord.name ..
                    " y consulta allí la conexión para continuar.", point=base, canGround=canGround, intermediate=hub.flightNode}
        end
        return {state="unavailable", title="Vuelo no disponible", shortText="Sin conexión a " .. name,
            text="Desde este maestro no tienes conexión a " .. name .. (canGround and ". Pulsa «Ir sin vuelo» para seguir el camino." or ". Consulta otra conexión antes de continuar."),
            point=nil, canGround=canGround}
    end
    return {state="unknown", title="Vuela a " .. name, shortText="Consulta los vuelos",
        text="Habla con el maestro y comprueba el vuelo a " .. name .. ".", point=base, canGround=canGround}
end
function F:CurrentView() return self:GetView() end
function F:Resolve(goal, base)
    local view = self:GetView(goal, base)
    return view and view.point or nil, view ~= nil, view
end
function F:BeginGround()
    local ctx = context(); local view = ctx and self:GetView(ctx.goal)
    if not view or not view.canGround then return false end
    local zone = R.Zone(); local landing = endpoint(ctx.goal, zone, R.Sample(zone))
    storage().ground = {key=ctx.key, destination=landing.flightNode}
    if ns.Sync then ns:Sync() end
    return true
end

local function refresh() if ns.char and ns.Sync then ns:Sync() end end
local function now() return read(GetTime) or 0 end
local function freshVisit(self)
    local observed = self.lastTaxiVisit
    local t = now()
    if observed and observed.owner == ns.char and t >= observed.at and t - observed.at <= 120 then
        return observed
    end
end
function F:RecordAttempt(slot)
    self.attempt = nil
    if not number(slot) or slot < 1 or slot ~= math.floor(slot) then self.pendingError = nil; return end
    local observed = freshVisit(self)
    if not observed then self.pendingError = nil; return end
    local id = observed.slots[slot]
    if not id then self.pendingError = nil; return end
    self.attempt = {id=id, observation=observed, at=now()}
    self:ApplyRejection()
end
function F:ApplyRejection()
    local attempt, rejected = self.attempt, self.pendingError
    if not attempt or not rejected or rejected.observation ~= attempt.observation
        or math.abs(attempt.at - rejected.at) > .5 or now() - rejected.at > 1 then return end
    local node = attempt.observation.nodes[attempt.id]
    if node and node.kind ~= "current" then
        node.kind = "unavailable"
        local routes = ns.char and ns.char.observedTaxiRoutes
        if type(routes) == "table" and type(routes[attempt.observation.origin]) == "table" then
            routes[attempt.observation.origin][attempt.id] = nil
            self.routeRevision = (self.routeRevision or 0) + 1
        end
    end
    self.pendingError, self.attempt = nil, nil
    refresh()
end
function F:ObserveError(message)
    if not text(message) or not text(ERR_TAXINOSUCHPATH) or message ~= ERR_TAXINOSUCHPATH then return end
    local observed = freshVisit(self)
    if not observed then return end
    self.pendingError = {observation=observed, at=now()}
    -- The server error can be raised inside TakeTaxiNode, before its secure
    -- post-hook. Defer correlation so a preceding click is not blamed.
    if C_Timer and C_Timer.After then C_Timer.After(0, function() F:ApplyRejection() end) end
end
local hooked
local function installHook()
    if not hooked and type(TakeTaxiNode) == "function" and type(hooksecurefunc) == "function" then
        local ok = pcall(hooksecurefunc, "TakeTaxiNode", function(slot) F:RecordAttempt(slot) end)
        hooked = ok
    end
end
local frame = CreateFrame("Frame")
for _, event in ipairs({"TAXIMAP_OPENED", "TAXIMAP_CLOSED", "TAXI_NODE_STATUS_CHANGED", "NEW_TAXI_PATH", "UI_ERROR_MESSAGE", "UI_INFO_MESSAGE", "PLAYER_LOGIN"}) do
    pcall(frame.RegisterEvent, frame, event)
end
frame:SetScript("OnEvent", function(_, event, _, message)
    if event == "PLAYER_LOGIN" then installHook()
    elseif event == "TAXIMAP_CLOSED" then F.taxiOpen = false
    elseif event == "NEW_TAXI_PATH" then F.observation = nil
    elseif event == "TAXIMAP_OPENED" or (event == "TAXI_NODE_STATUS_CHANGED" and F.taxiOpen) then
        F.taxiOpen = true
        installHook(); F:ObserveTaxi(); refresh()
    elseif event == "UI_ERROR_MESSAGE" or event == "UI_INFO_MESSAGE" then F:ObserveError(message) end
end)
local elapsed = 0
frame:SetScript("OnUpdate", function(_, dt)
    elapsed = elapsed + dt
    if elapsed < .5 then return end
    elapsed = 0
    local ctx = context()
    if ctx and F.observation then
        local zone = R.Zone(); snapshot(F, ctx, zone, R.Sample(zone))
    elseif not ctx then F.observation = nil end
    arrival(ctx)
    if F.arrivalDirty then F.arrivalDirty = nil; refresh() end
end)
