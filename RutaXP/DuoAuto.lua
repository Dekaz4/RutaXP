local _, ns = ...
-- A shared view never replaces GetCurrent or a character's saved progress.
local Auto = { elapsed = 0, serial = 0, phase = "idle" }
ns.DuoAuto = Auto
local function read(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, a, b, c = pcall(fn, ...)
    if not ok then return nil end
    if issecretvalue then
        if issecretvalue(a) then a = nil end
        if issecretvalue(b) then b = nil end
        if issecretvalue(c) then c = nil end
    end
    return a, b, c
end
local function timeNow() return read(GetTime) or 0 end
local function integer(value, maximum)
    if issecretvalue and issecretvalue(value) then return nil end
    if type(value) == "number" and value == math.floor(value) and value >= 1 and value <= (maximum or 100001) then return value end
end
local function settings()
    local value = ns.Duo and ns.Duo:Settings()
    if value and value.autoPair == nil then value.autoPair = true end
    return value
end
local function context() return ns.Duo and ns.Duo:GetContext() or {} end
local function validPair(ctx)
    local mine, partner = read(UnitFactionGroup, "player"), read(UnitFactionGroup, "party1")
    return ctx.sameParty == true and ctx.online == true and ctx.groupSize == 2
        and type(mine) == "string" and mine ~= "Neutral" and mine == partner
        and type(ctx.ownName) == "string" and type(ctx.partnerName) == "string"
end
local function compatible(ctx)
    return validPair(ctx) and ctx.known == true and ctx.partnerAutoCompatible == true and ctx.partnerAutoPair == true
end
local function peerKey(ctx) return tostring(ctx.partnerNonce) .. ":" .. tostring(ctx.partnerAutoEpoch or 0) end
local function current()
    if ns.GetCurrent then return ns:GetCurrent() end
end
local function coordinator(ctx)
    if not ctx.ownName or not ctx.partnerName then return nil end
    return ctx.ownName < ctx.partnerName and ctx.ownName or ctx.partnerName
end
local function refresh()
    if ns.Duo and ns.Duo.NavigationChanged then ns.Duo:NavigationChanged() end
end
function Auto:_ClearAgreement()
    self.pending, self.agreement, self.lastQueued = nil, nil, nil
    if ns.Duo and ns.Duo.ClearAutoMessages then ns.Duo:ClearAutoMessages() end
end
function Auto:_Restore(keepSettings)
    local value = settings()
    local lease = value and value.autoSession
    if lease and not keepSettings then
        value.enabled, value.wait, ns.char.auto = lease.enabled == true, lease.wait == true, lease.auto == true
    end
    for id, previous in pairs(lease and lease.reviews or {}) do
        local state = ns.char.progress and ns.char.progress[id]
        if type(state) == "table" and state.cursor == previous.cursor and previous.review == true then state.review = true end
    end
    if value then value.autoSession = nil end
    self:_ClearAgreement()
    self.phase, self.reason = "idle", nil
    if ns.Duo then ns.Duo.lastSentHeader = nil end
    refresh()
end
function Auto:SetEnabled(value)
    local config = settings()
    if not config then return false, "El personaje todavía no está cargado" end
    config.autoPair = value == true
    if config.autoPair then config.autoEpoch = (tonumber(config.autoEpoch) or 0) % 1000000000 + 1 end
    if not config.autoPair then self:_Restore(false) end
    if ns.Duo then ns.Duo.lastSentHeader = nil end
    self.elapsed = 1
    refresh()
    return true
end
function Auto:UseManualMode(reason)
    local config = settings()
    if not config then return false end
    config.autoPair = false
    self:_Restore(true)
    self.phase, self.reason = "manual", reason or "Has elegido el control manual"
    return true
end
function Auto:_Begin(ctx)
    local config = settings()
    if config.autoSession then return end
    config.autoSession = { partnerName = ctx.partnerName, enabled = config.enabled == true,
        wait = config.wait == true, auto = ns.char.auto == true, activated = false }
    config.enabled = true -- Discovery only; legacy peers cannot enable wait/auto.
    self.phase = "probing"
    if ns.Duo then ns.Duo.lastSentHeader = nil end
end
function Auto:_Plan(id)
    local planner = ns.DuoPlanner
    if not planner then return nil, "Esperando el plan compartido" end
    local plan, reason
    if id and planner.ValidateAutomaticGuide then
        local valid
        valid, reason, plan = read(planner.ValidateAutomaticGuide, planner, id)
        if valid ~= true then return nil, reason or "La guía no está comprobada para ambos" end
    elseif not id and planner.GetAutomaticPlan then plan, reason = read(planner.GetAutomaticPlan, planner) end
    local ctx = context()
    if type(plan) ~= "table" or plan.verified ~= true or type(plan.guideID) ~= "string"
        or not ns.guides or not ns.guides[plan.guideID]
        or not integer(plan.referenceCursor) or not integer(plan.ownCursor)
        or (plan.partnerCursor ~= nil and not integer(plan.partnerCursor))
        or (plan.referenceName ~= ctx.ownName and plan.referenceName ~= ctx.partnerName) then
        return nil, reason or "Faltan datos comprobados de los dos personajes"
    end
    if id and plan.guideID ~= id then return nil, "La validación no corresponde a esta guía" end
    return plan
end
local function samePacket(a, b)
    return a and b and a.transaction == b.transaction and a.guideID == b.guideID
        and a.reference == b.reference and a.cursor == b.cursor
end
function Auto:_ReferenceName(packet, ctx)
    local first = coordinator(ctx)
    return packet.reference == 0 and first or (first == ctx.ownName and ctx.partnerName or ctx.ownName)
end
function Auto:_ValidatePacket(packet, ctx, alreadyAccepted)
    local plan, reason = self:_Plan(packet.guideID)
    if not plan then return nil, reason end
    if not alreadyAccepted and (plan.referenceName ~= self:_ReferenceName(packet, ctx) or plan.referenceCursor ~= packet.cursor) then
        return nil, "Los dos planes todavía no coinciden; esperamos datos recientes"
    end
    return plan
end
function Auto:_Queue(kind, packet, phase)
    local values = { transaction = packet.transaction, guideID = packet.guideID,
        reference = packet.reference, cursor = packet.cursor, phase = phase }
    if ns.Duo and ns.Duo:QueueAutoMessage(kind, values) then self.lastQueued = timeNow(); return true end
    return false
end
function Auto:_Apply(plan)
    local guide = ns.guides[plan.guideID]
    if not guide then return false end
    ns.char.progress = ns.char.progress or {}
    local own = ns.char.progress[guide.id]
    if type(own) ~= "table" then
        -- Only our own observed projection may initialize a new route.
        local cursor = plan.ownCursorObserved == true and plan.ownCursor or 1
        ns.char.progress[guide.id] = { cursor = math.min(cursor, #guide.steps + 1), confirmed = {} }
        own = ns.char.progress[guide.id]
    end
    local lease = settings().autoSession
    if own.review and lease then
        lease.reviews = lease.reviews or {}
        if not lease.reviews[guide.id] then lease.reviews[guide.id] = { cursor = own.cursor, review = true } end
        own.review = nil
    end
    ns.char.activeGuide = guide.id
    if ns.Duo then ns.Duo.lastSentHeader = nil end
    return true
end
function Auto:OnProtocol(kind, packet)
    local config, ctx = settings(), context()
    if not config or not config.autoPair or not compatible(ctx) or not config.autoSession
        or packet.sender ~= ctx.partnerName or packet.nonce ~= ctx.partnerNonce then return false end
    local leader = coordinator(ctx)
    if kind == "A" then
        if leader ~= ctx.partnerName then return false end
        if packet.phase == 0 then
            local plan, reason = self:_ValidatePacket(packet, ctx)
            if not plan then self.reason = reason; self:_Queue("P", packet, 0); return true end
            self.pending = { packet = packet, nonce = peerKey(ctx), started = timeNow(), plan = plan, accepted = true }
            self.phase, self.reason = "negotiating", "Confirmando la misma guía y al personaje rezagado"
            self:_Queue("P", packet, 1)
        elseif packet.phase == 1 then
            if self.agreement and samePacket(self.agreement.packet, packet) then self:_Queue("P", packet, 2); return true end
            if not self.pending or not self.pending.accepted or not samePacket(self.pending.packet, packet) then return false end
            local plan, reason = self:_ValidatePacket(packet, ctx, true)
            if not plan then self.reason = reason; self:_Queue("P", packet, 0); self.pending = nil; return true end
            if not self:_Apply(plan) then return false end
            self.agreement = { packet = packet, nonce = peerKey(ctx), confirmed = true }
            self.pending, self.phase, self.reason = nil, "active", nil
            self:_Queue("P", packet, 2)
        else return false end
    elseif kind == "P" then
        if leader ~= ctx.ownName or not self.pending or not samePacket(self.pending.packet, packet) then return false end
        if packet.phase == 0 then
            self:_ClearAgreement(); self.phase, self.reason, self.retryAt = "waiting", "Los planes no coinciden todavía", timeNow() + 10
        elseif packet.phase == 1 then
            local plan, reason = self:_ValidatePacket(packet, ctx)
            if not plan then self:_ClearAgreement(); self.reason, self.retryAt = reason, timeNow() + 5; return true end
            if not self:_Apply(plan) then return false end
            self.pending.committing, self.pending.started = true, timeNow()
            self.phase, self.reason = "committing", "Aplicando el acuerdo en ambos personajes"
            self:_Queue("A", packet, 1)
        elseif packet.phase == 2 then
            if not self.pending.committing then return false end
            self.agreement = { packet = packet, nonce = peerKey(ctx), confirmed = true }
            self.pending, self.phase, self.reason = nil, "active", nil
        else return false end
    else return false end
    refresh()
    return true
end
function Auto:Tick(elapsed)
    if not self.initialized then return end
    self.elapsed = self.elapsed + (type(elapsed) == "number" and math.max(0, elapsed) or 0)
    if self.elapsed < 1 then return end
    self.elapsed = 0
    local config, ctx = settings(), context()
    if not config then return end
    local lease = config.autoSession
    if not config.autoPair or not validPair(ctx) or (lease and lease.partnerName ~= ctx.partnerName) then
        if lease then self:_Restore(false) end
        self.phase = config.autoPair and "idle" or "manual"
        return
    end
    if not lease then self:_Begin(ctx); lease = config.autoSession end
    if not compatible(ctx) then
        if ctx.known and (not ctx.partnerAutoCompatible or not ctx.partnerAutoPair) then
            if lease.activated then config.wait, ns.char.auto, lease.activated = lease.wait, lease.auto, false; self:_ClearAgreement() end
            self.phase, self.reason = "probing", "El compañero necesita RutaXP 0.5 y el modo automático activado"
        else self.phase, self.reason = "probing", "Buscando RutaXP compatible en tu compañero" end
        return
    end
    if self.agreement and self.agreement.nonce ~= peerKey(ctx) then self:_ClearAgreement() end
    if self.pending and self.pending.nonce ~= peerKey(ctx) then self:_ClearAgreement() end
    if not lease.activated then
        config.enabled, config.wait, ns.char.auto, lease.activated = true, true, true, true
    end
    if self.agreement then
        if ns.char.activeGuide ~= self.agreement.packet.guideID then
            self:UseManualMode("Has cambiado de guía manualmente")
        end
        return
    end
    if self.pending then
        if timeNow() - self.pending.started > 20 then self:_ClearAgreement(); self.retryAt = timeNow() + 5; self.reason = "Volviendo a comprobar el acuerdo"; return end
        if not self.lastQueued or timeNow() - self.lastQueued >= 3 then
            if coordinator(ctx) == ctx.ownName then self:_Queue("A", self.pending.packet, self.pending.committing and 1 or 0)
            else self:_Queue("P", self.pending.packet, 1) end
        end
        return
    end
    if coordinator(ctx) ~= ctx.ownName then self.phase, self.reason = "negotiating", "Esperando la propuesta común del compañero"; return end
    if self.retryAt and timeNow() < self.retryAt then return end
    local plan, reason = self:_Plan()
    if not plan then self.phase, self.reason = "waiting", reason; return end
    self.serial = self.serial + 1
    local packet = { transaction = tostring(ns.Duo.nonce):sub(1, 24) .. "_" .. self.serial,
        guideID = plan.guideID, reference = plan.referenceName == coordinator(ctx) and 0 or 1, cursor = plan.referenceCursor }
    self.pending = { packet = packet, nonce = peerKey(ctx), started = timeNow(), plan = plan }
    self.phase, self.reason = "negotiating", "Proponiendo una guía comprobada para ambos"
    self:_Queue("A", packet, 0)
end
function Auto:GetSharedView()
    local config, ctx = settings(), context()
    local agreed = self.agreement
    if not config or not config.autoPair or not agreed or not agreed.confirmed or not compatible(ctx)
        or agreed.nonce ~= peerKey(ctx) then return nil end
    local id = agreed.packet.guideID
    local guide, _, own = current()
    if not guide or guide.id ~= id or ctx.guideID ~= id or not own or not integer(own.cursor) or not integer(ctx.cursor) then return nil end
    local shared = math.min(own.cursor, ctx.cursor)
    local finished = shared > #guide.steps
    return { guideID = id, guide = guide, step = guide.steps[shared], sharedCursor = shared,
        ownCursor = own.cursor, partnerCursor = ctx.cursor, following = own.cursor > shared,
        completed = finished,
        reason = finished and "Guía compartida completada; la siguiente necesita un plan comprobado para ambos"
            or (own.cursor > shared and "Acompañando al personaje rezagado; tu progreso se conserva" or "Mismo paso compartido") }
end
function Auto:_IndividualStep(step)
    local guide, currentStep, state = current()
    if not guide then return false end
    step = step or currentStep
    local duo = ns.Duo
    if duo and duo.AppliesToPartner then
        if not duo:AppliesToPartner(guide) or not duo:AppliesToPartner(guide.only)
            or (step and not duo:AppliesToPartner(step.only)) then return true end
        local individual, shared = false, false
        for _, goal in ipairs(step and step.goals or { step or {} }) do
            if not goal.only or not ns.MatchesConditions or ns:MatchesConditions(goal.only) then
                if duo:AppliesToPartner(goal.only) then shared = true else individual = true end
            end
        end
        if individual and not shared then return true end
    end
    if state and ns.DuoPlanner and ns.DuoPlanner.GetSharedStepStatus then
        local info = read(ns.DuoPlanner.GetSharedStepStatus, ns.DuoPlanner, guide.id, state.cursor)
        if type(info) == "table" and info.individualOnly == true then return true end
    end
    return false
end
function Auto:ShouldWaitForStep(step)
    local config, ctx = settings(), context()
    local lease = config and config.autoSession
    if not config or not config.autoPair or not lease or (not lease.activated and not compatible(ctx)) then return false end
    local _, activeStep = current()
    if step and step ~= activeStep then return false end
    if self:IsIndependentPhase(step) then return false end
    if not compatible(ctx) then return true, "Esperando confirmación reciente del compañero" end
    local view = self:GetSharedView()
    if not view then return true, "Acordando la guía común sin alterar el progreso" end
    if view.following then return true, view.reason end
    return false
end
function Auto:IsIndependentPhase(step)
    local config = settings()
    local lease = config and config.autoSession
    if not config or not config.autoPair or not lease or not lease.activated then return false end
    if self:_IndividualStep(step) then return true end
    return self.pending == nil and self.agreement == nil
end
function Auto:ShouldPauseAutomation()
    local wait, reason = self:ShouldWaitForStep()
    if wait then return true, reason end
    local config = settings()
    local _, _, state = current()
    if config and config.autoPair and config.autoSession and config.autoSession.activated and state and state.review then
        return true, "Revisión manual conservada"
    end
    return false
end
function Auto:GetNavigationOverride()
    local view = self:GetSharedView()
    if not view or not view.following or not ns.DuoPlanner or not ns.DuoPlanner.GetSharedWaypoint then return nil end
    local point = read(ns.DuoPlanner.GetSharedWaypoint, ns.DuoPlanner, view.guideID, view.sharedCursor)
    if type(point) ~= "table" then return nil end
    local copy = {}; for key, value in pairs(point) do copy[key] = value end
    copy.source, copy.duoFollow = "duo-follow", true
    return copy
end
function Auto:GetStatus()
    local config, ctx = settings(), context()
    local view = self:GetSharedView()
    local enabled = config and config.autoPair == true or false
    local text = not enabled and "Automático al agruparse: desactivado" or self.reason
        or (view and view.reason) or "Automático al agruparse: esperando una pareja de la misma facción"
    return { enabled = enabled, active = view ~= nil, phase = self.phase, text = text, reason = text,
        partnerName = ctx.partnerName, coordinator = coordinator(ctx), following = view and view.following == true or false,
        guideID = view and view.guideID, sharedCursor = view and view.sharedCursor }
end
function Auto:Initialize()
    if self.initialized or not settings() then return end
    -- A saved lease survives reload so temporary auto settings never become
    -- the restored preferences. A new nonce still requires a new agreement.
    self.initialized, self.elapsed = true, 1
    local config = settings()
    config.autoEpoch = (tonumber(config.autoEpoch) or 0) % 1000000000 + 1
    if ns.Duo then ns.Duo.lastSentHeader = nil end
    self:Tick(0)
end
