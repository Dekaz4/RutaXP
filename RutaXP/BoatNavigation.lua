local _, ns = ...
local B, R = {}, ns.TravelRouting
ns.BoatNavigation = B

local function read(fn, ...)
    if type(fn) ~= "function" then return end
    local ok, value = pcall(fn, ...)
    if ok and not (issecretvalue and issecretvalue(value)) then return value end
end
local function finite(v)
    return not (issecretvalue and issecretvalue(v)) and type(v) == "number"
        and v == v and math.abs(v) < math.huge
end
local function valid(p)
    return type(p) == "table" and finite(p.map) and finite(p.x) and finite(p.y)
        and p.x >= 0 and p.x <= 100 and p.y >= 0 and p.y <= 100
end
local function signature(p)
    return table.concat({p.map, p.f or "l", p.x, p.y, p.radius or 25}, ",")
end
local function keyFor(goal, guide, stepIndex, index)
    if not goal or goal.t ~= "boat" or not guide or not stepIndex or not index
        or not valid(goal.departure) or not valid(goal.arrival) then return end
    return table.concat({guide.id, guide.routeRevision or 1, stepIndex, index,
        signature(goal.departure), signature(goal.arrival)}, ":")
end
local function sameJourney(oldKey, key, guide)
    if not key or type(oldKey) ~= "string" then return false end
    if oldKey == key then return true end
    local prefix = guide.id .. ":"
    if oldKey:sub(1, #prefix) ~= prefix then return false end
    local revision, si, gi, signature = oldKey:sub(#prefix + 1):match("^(%d+):(%d+):(%d+):(.+)$")
    local current, targetStep, targetGoal, targetSignature = key:sub(#prefix + 1):match("^(%d+):(%d+):(%d+):(.+)$")
    revision, current = tonumber(revision), tonumber(current)
    if not revision or not current or signature ~= targetSignature then return false end
    local slot, target = si .. ":" .. gi, targetStep .. ":" .. targetGoal
    -- A real arrival or transport phase survives only an explicit mapping of
    -- the same boat action with unchanged departure and land-arrival points.
    for _ = 1, 20 do
        if revision == current then return slot == target end
        local nextRevision
        for _, migration in ipairs(guide.progressMigrations or {}) do
            if migration.from == revision and migration.to > revision then
                if migration.retiredGoalKeys and migration.retiredGoalKeys[slot] then return false end
                slot = migration.goalMap and migration.goalMap[slot]
                if not slot then return false end
                nextRevision = migration.to
                break
            end
        end
        if not nextRevision then return false end
        revision = nextRevision
    end
    return false
end
local function storage()
    if not ns.char then return end
    if type(ns.char.boatNavigation) ~= "table" then ns.char.boatNavigation = {} end
    local saved = ns.char.boatNavigation
    if type(saved.arrivals) ~= "table" then saved.arrivals = {} end
    return saved
end
function B:IsComplete(goal, guide, stepIndex, index, state)
    if state and state.review then return false end
    local key = keyFor(goal, guide, stepIndex, index)
    local saved = ns.char and ns.char.boatNavigation
    if not key or type(saved) ~= "table" or type(saved.arrivals) ~= "table" then return false end
    for oldKey, complete in pairs(saved.arrivals) do
        if complete == true and sameJourney(oldKey, key, guide) then return true end
    end
    return false
end
local function context(goal)
    if not ns.char or not ns.GetCurrent or not ns.GetActiveGoal then return end
    if ns.GetGuideTravel and ns:GetGuideTravel() then return end
    local shared = ns.DuoAuto and ns.DuoAuto.GetSharedView and ns.DuoAuto:GetSharedView()
    if shared and shared.following then return end
    local guide, step, state = ns:GetCurrent()
    if not guide or not step or not state then return end
    local active, index = ns:GetActiveGoal(step, state)
    if not active or active.t ~= "boat" or (goal and goal ~= active) then return end
    return {goal=active, guide=guide, step=step, progress=state, index=index,
        key=keyFor(active, guide, state.cursor, index)}
end
local function near(p, zone, sample)
    return valid(p) and p.map == zone and sample and R.Near(p, sample)
end
local function point(p, ctx, label, phase)
    local result = valid(p) and ns:ResolveWaypointPoint(p)
    if result then
        result.goal, result.label, result.source = ctx.goal, label, "boat-navigation"
        result.targetKey, result.boatNavigation = (ctx.key or "boat") .. ":" .. phase, true
        result.radius = p.radius or 25
    end
    return result
end
local function arrived(ctx, zone, sample)
    -- Forever 70888 exposes no documented public on-ship predicate. A dock
    -- position (even after the map changes) cannot prove disembarkation.
    -- The authored arrival is on land, beyond the vessel's footprint.
    if not ctx.key or read(UnitOnTaxi, "player") ~= false or read(UnitIsDeadOrGhost, "player") ~= false
        or not near(ctx.goal.arrival, zone, sample) then return false end
    local saved = storage()
    if saved.arrivals[ctx.key] then return false end
    local count = 0; for _ in pairs(saved.arrivals) do count = count + 1 end
    if count >= 128 then return false end
    saved.arrivals[ctx.key] = true
    if sameJourney(saved.boarding, ctx.key, ctx.guide) then saved.boarding = nil end
    if sameJourney(saved.landing, ctx.key, ctx.guide) then saved.landing = nil end
    B.arrivalDirty = true
    return true
end
local function viewFor(ctx, observe, reviewPhase)
    if not ctx then return end
    if not ctx.key then return {state="unavailable", shortText="Trayecto no disponible",
        text="Este trayecto necesita un muelle de salida y un punto de llegada en tierra."} end
    local zone, name = R.Zone(), ctx.goal.location or "el destino"
    local sample = R.Sample(zone)
    if observe and arrived(ctx, zone, sample) then
        return {state="arrived", shortText="Has llegado", text="Has desembarcado en " .. name .. "."}
    end
    if R.OnTaxi() then return {state="flying", shortText="Espera a aterrizar", text="Al aterrizar, retoma el trayecto a " .. name .. "."} end
    local saved = reviewPhase or (observe and storage()) or (ns.char and ns.char.boatNavigation) or {}
    local trackPhase = observe or reviewPhase ~= nil
    if zone == ctx.goal.arrival.map then
        local atDock = near(ctx.goal.arrivalDock, zone, sample)
        if atDock and trackPhase then saved.landing = ctx.key end
        if sameJourney(saved.boarding, ctx.key, ctx.guide)
            and not sameJourney(saved.landing, ctx.key, ctx.guide) and not atDock then
            return {state="crossing", shortText="Espera a que atraque el barco",
                text="Permanece a bordo hasta que el barco atraque en " .. name .. ". Después baja por el muelle y sigue la flecha."}
        end
        return {state="landing", shortText="Desembarca y sigue la flecha",
            text="Baja del barco y sigue el muelle hacia el maestro de vuelo de " .. name .. ". La guía continúa al llegar a tierra.",
            point=point(ctx.goal.arrival, ctx, "Desembarca en " .. name, "landing")}
    end
    if zone == ctx.goal.departure.map then
        -- The source's verified land point is separate from the moving ship.
        -- Distance from the pier alone would also match a boat sailing away.
        local backOnLand = near(ctx.goal.departureLand, zone, sample)
        if trackPhase and sameJourney(saved.boarding, ctx.key, ctx.guide) and backOnLand then
            saved.boarding = nil
        end
        local atDock = near(ctx.goal.departure, zone, sample)
        if atDock and trackPhase then saved.boarding, saved.landing = ctx.key, nil end
        if atDock or (sameJourney(saved.boarding, ctx.key, ctx.guide) and not backOnLand) then
            return {state="boarding", shortText="Espera el barco a " .. name,
                text="Espera en este muelle y sube al barco hacia " .. name .. ". Permanece a bordo hasta llegar; después baja y sigue la flecha."}
        end
        return {state="approach", shortText="Ve al muelle de salida",
            text=ctx.goal.note or ("Ve al muelle y toma el barco hacia " .. name .. "."),
            point=point(ctx.goal.departure, ctx, "Muelle hacia " .. name, "departure")}
    end
    if not zone then
        return {state="crossing", shortText="Continúa el viaje en barco",
            text="Permanece a bordo hasta " .. name .. ". Al desembarcar, sigue la flecha hacia tierra."}
    end
    local leg = R.Rejoin({ctx.goal.arrival}, zone, sample)
    return {state="rejoin", shortText=leg and leg.title or "Retoma el viaje",
        text=leg and leg.text or ("Vuelve al exterior para retomar el trayecto a " .. name .. "."),
        point=leg and not (leg.boundary and near(leg, zone, sample)) and point(leg, ctx, leg.title, "rejoin") or nil}
end
function B:GetView(goal)
    local ctx = context(goal)
    if not ctx then return end
    if ctx.progress.review then
        -- Manual review still needs boarding continuity while the vessel
        -- moves. Keep that phase in memory, never in character progress.
        if not self.reviewPhase or self.reviewPhase.owner ~= ns.char or self.reviewPhase.key ~= ctx.key then
            self.reviewPhase = {owner=ns.char, key=ctx.key}
        end
        return viewFor(ctx, false, self.reviewPhase)
    end
    self.reviewPhase = nil
    return viewFor(ctx, true)
end
function B:GetSharedView(goal, guide, stepIndex, index)
    local key = keyFor(goal, guide, stepIndex, index)
    if not key then return end
    if self:IsComplete(goal, guide, stepIndex, index) then
        return {state="waiting", shortText="Espera a tu compañero", text="Ya has llegado. Espera a que tu compañero desembarque."}
    end
    return viewFor({goal=goal, guide=guide, index=index, key=key}, false)
end
function B:CurrentView() return self:GetView() end
function B:Resolve(goal)
    local view = self:GetView(goal)
    return view and view.point or nil, view ~= nil, view
end

local elapsed = 0
function B:Tick(dt)
    elapsed = elapsed + dt
    if elapsed < .5 then return end
    elapsed = 0
    local view = self:CurrentView()
    if not view then self.reviewPhase = nil end
    local changed = view and view.state ~= B.lastState
    B.lastState = view and view.state or nil
    if self.arrivalDirty or changed then
        self.arrivalDirty = nil
        if ns.char and ns.Sync then ns:Sync() end
    end
end
local frame = CreateFrame("Frame")
frame:SetScript("OnUpdate", function(_, dt) B:Tick(dt) end)
