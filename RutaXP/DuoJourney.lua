local _, ns = ...
-- Checkpoints are observations, never a source of quest completion or peer progress.
local Journey = {}
ns.DuoJourney = Journey
local HISTORY_LIMIT, QUEST_LIMIT, OBJECTIVE_LIMIT, AUTO_INTERVAL = 20, 48, 32, 300
local STOP_TITLES = { vendor = "Vaciar bolsas", repair = "Reparar equipo", rest = "Recuperar maná",
    trainer = "Revisar instructor y talentos", meeting = "Reuniros" }
local STATE_NAMES = { [0] = "no la lleva", [1] = "en curso", [2] = "lista para entregar", [3] = "entregada" }

local function safe(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, a, b = pcall(fn, ...)
    if ok and not (issecretvalue and issecretvalue(a)) then return a, b end
end
local function number(value)
    if issecretvalue and issecretvalue(value) then return nil end
    if type(value) == "number" and value == value and math.abs(value) < math.huge then return value end
end
local function integer(value, low, high)
    local n = number(value)
    if n and n == math.floor(n) and n >= low and n <= high then return n end
end
local function text(value, limit)
    if type(value) == "string" and value ~= "" and #value <= (limit or 200) and not value:find("[%c|]") then return value end
end
local function canonical(value)
    value = text(value, 128)
    if not value then return nil end
    value = value:gsub("%s", ""):lower()
    if value == "" then return nil end
    if not value:find("-", 1, true) then
        local realm = text(safe(GetNormalizedRealmName) or safe(GetRealmName), 80)
        if not realm then return nil end
        value = value .. "-" .. realm:gsub("%s", ""):lower()
    end
    return value:match("^.+%-.+$") and value or nil
end
local function stamp() return number(safe(GetServerTime)) or number(safe(time)) or 0 end
local function context()
    local ctx = ns.Duo and safe(ns.Duo.GetContext, ns.Duo)
    return type(ctx) == "table" and ctx or {}
end
local function partnerName(ctx)
    return canonical(ctx and ctx.partnerName or (ns.Duo and ns.Duo.partnerName))
end
local function connected(ctx)
    return ctx.enabled == true and ctx.known == true and ctx.online == true and ctx.sameParty == true and partnerName(ctx) ~= nil
end
local function count(t) local n = 0; for _ in pairs(t) do n = n + 1 end; return n end
local function sortedIDs(t)
    local result = {}; for id in pairs(t) do result[#result + 1] = id end
    table.sort(result); return result
end
local function questCopy(raw)
    if type(raw) ~= "table" or raw.basic or raw.known == false then return nil end
    local state = integer(raw.state, 0, 3)
    if not state then return nil end
    local result = { state = state, known = true, done = integer(raw.done, 0, 100), total = integer(raw.total, 0, 100),
        mask = integer(raw.mask, 0, 4294967295), objectives = {} }
    for i = 1, OBJECTIVE_LIMIT do
        local objective = type(raw.objectives) == "table" and raw.objectives[i]
        if type(objective) == "table" then
            local current, total = number(objective.current), number(objective.total)
            if current and (current < 0 or current > 1000000000) then current = nil end
            if total and (total <= 0 or total > 1000000000) then total = nil end
            result.objectives[i] = { index = i, known = objective.known == true and current ~= nil and total ~= nil,
                current = current, total = total,
                finished = type(objective.finished) == "boolean" and objective.finished or nil }
            -- Lua's and/or idiom would erase an observed false value.
            if objective.finished == false then result.objectives[i].finished = false end
        elseif result.total and i <= result.total and result.mask then
            result.objectives[i] = { index = i, known = false, finished = math.floor(result.mask / 2 ^ (i - 1)) % 2 == 1 }
        end
    end
    return result
end
local function snapshotCopy(raw)
    if type(raw) ~= "table" then return nil end
    local guideID, cursor = text(raw.guideID), integer(raw.cursor, 1, 100001)
    if not guideID or not cursor then return nil end
    local result = { guideID = guideID, cursor = cursor, review = raw.review == true or nil,
        routeRevision = integer(raw.routeRevision, 1, 100001),
        level = integer(raw.level, 1, 100), mapID = integer(raw.mapID, 1, 100000), known = raw.known == true,
        quests = {}, trackedQuestIDs = {} }
    local tracked = {}
    local function track(id)
        id = integer(id, 1, 10000000)
        if id and not tracked[id] and #result.trackedQuestIDs < QUEST_LIMIT then
            tracked[id] = true; result.trackedQuestIDs[#result.trackedQuestIDs + 1] = id
        end
    end
    for _, id in ipairs(type(raw.trackedQuestIDs) == "table" and raw.trackedQuestIDs or {}) do track(id) end
    for id, quest in pairs(type(raw.quests) == "table" and raw.quests or {}) do
        local key = integer(type(id) == "string" and tonumber(id) or id, 1, 10000000)
        if key and count(result.quests) < QUEST_LIMIT then track(key); result.quests[key] = questCopy(quest) end
    end
    return result
end
local function recordCopy(raw)
    if type(raw) ~= "table" then return nil end
    local name, own = canonical(raw.partnerName), snapshotCopy(raw.localSnapshot)
    local id = integer(raw.id, 1, 1000000000000)
    if not name or not own or not id then return nil end
    return { id = id, partnerName = name, savedAt = number(raw.savedAt) or 0,
        automatic = raw.automatic == true, localSnapshot = own, partnerSnapshot = snapshotCopy(raw.partnerSnapshot) }
end
local function localRoute()
    local guide = ns.char and ns.guides and ns.guides[ns.char.activeGuide]
    local state = guide and type(ns.char.progress) == "table" and ns.char.progress[guide.id]
    return guide, type(state) == "table" and state or nil
end
local function allowed(guide)
    if not guide or guide.temporary or guide.recovery then return false end
    if guide.faction and guide.faction ~= safe(UnitFactionGroup, "player") then return false end
    if ns.MatchesConditions and not safe(ns.MatchesConditions, ns, { classes = guide.classes, races = guide.races }) then return false end
    return true
end
local function localQuest(id)
    return questCopy(ns.Duo and safe(ns.Duo.GetLocalQuest or ns.Duo.LocalQuest, ns.Duo, id))
end
local function remoteCheckpoint(ctx)
    if not connected(ctx) then return nil end
    local data = ns.Duo and safe(ns.Duo.GetPartnerCheckpoint, ns.Duo)
    if type(data) == "table" and data.known == true then return data end
end
local function remoteQuest(id, ctx, data)
    if not connected(ctx) then return nil end
    return questCopy((data and type(data.quests) == "table" and data.quests[id])
        or (ns.Duo and safe(ns.Duo.GetPartnerQuest, ns.Duo, id)))
end
local function title(id) return safe(ns.GetQuestTitle, ns, id) or ("Misión " .. id) end

function Journey:Store()
    if not ns.char then return nil end
    if self.store and self.owner == ns.char then return self.store end
    local previous = ns.char.duoJourney
    local old = type(previous) == "table" and previous or {}
    local store = { version = 1, history = {}, sequence = integer(old.sequence, 0, 1000000000000) or 0,
        lastPartner = canonical(old.lastPartner), recovered = old.recovered == true or (previous ~= nil and type(previous) ~= "table") }
    local history = type(old.history) == "table" and old.history or {}
    if old.history ~= nil and type(old.history) ~= "table" then store.recovered = true end
    for i = math.max(1, #history - HISTORY_LIMIT + 1), #history do
        local record = recordCopy(history[i])
        if record then
            store.history[#store.history + 1] = record
            store.sequence = math.max(store.sequence, record.id)
        else store.recovered = true end
    end
    if type(old.stop) == "table" and STOP_TITLES[old.stop.kind] and canonical(old.stop.partnerName) then
        store.stop = { kind = old.stop.kind, partnerName = canonical(old.stop.partnerName), ready = false,
            startedAt = number(old.stop.startedAt) or 0 }
    end
    ns.char.duoJourney, self.store, self.owner = store, store, ns.char
    return store
end
function Journey:GetCheckpoint(index, name)
    local store = self:Store()
    if not store then return nil end
    if index ~= nil then
        index = integer(tonumber(index), 1, #store.history)
        return index and store.history[index] or nil
    end
    name = canonical(name) or partnerName(context()) or store.lastPartner
    for i = #store.history, 1, -1 do
        if store.history[i].partnerName == name then return store.history[i] end
    end
end
function Journey:SaveCheckpoint(automatic)
    local store, ctx = self:Store(), context()
    if not store then return false, "El personaje aún no está cargado." end
    if not connected(ctx) then return false, "Hace falta un compañero de RutaXP conectado y confirmado para guardar un punto conjunto." end
    local guide, state = localRoute()
    if not allowed(guide) then return false, "Selecciona una guía local compatible y estable antes de guardar." end
    local remote, ids = remoteCheckpoint(ctx), {}
    local currentIDs = ns.Duo and safe(ns.Duo.GetQuestIDs, ns.Duo) or {}
    for _, id in ipairs(type(currentIDs) == "table" and currentIDs or {}) do
        if integer(id, 1, 10000000) and count(ids) < QUEST_LIMIT then ids[id] = true end
    end
    for id in pairs(remote and type(remote.quests) == "table" and remote.quests or {}) do
        if integer(id, 1, 10000000) and count(ids) < QUEST_LIMIT then ids[id] = true end
    end
    local own = { known = true, guideID = guide.id, cursor = integer(state and state.cursor, 1, #guide.steps + 1) or 1,
        review = state and state.review == true or nil,
        routeRevision = integer(state and state.routeRevision, 1, 100001) or integer(guide.routeRevision, 1, 100001),
        level = integer(safe(UnitLevel, "player"), 1, 100),
        mapID = integer(safe(C_Map and C_Map.GetBestMapForUnit, "player"), 1, 100000), quests = {}, trackedQuestIDs = {} }
    local friend = { known = true, guideID = text(ctx.guideID) or text(remote and remote.guideID) or "unknown",
        cursor = integer(ctx.cursor, 1, 100001) or integer(remote and remote.cursor, 1, 100001) or 1,
        level = integer(ctx.partnerLevel, 1, 100), mapID = integer(ctx.partnerMapID, 1, 100000), quests = {}, trackedQuestIDs = {} }
    for _, id in ipairs(sortedIDs(ids)) do
        if #own.trackedQuestIDs >= QUEST_LIMIT then break end
        -- Retain the identity even when neither client can read this quest.
        -- Assigning a nil observation alone would erase it from SavedVariables.
        own.trackedQuestIDs[#own.trackedQuestIDs + 1] = id
        friend.trackedQuestIDs[#friend.trackedQuestIDs + 1] = id
        own.quests[id], friend.quests[id] = localQuest(id), remoteQuest(id, ctx, remote)
    end
    store.sequence = store.sequence % 1000000000000 + 1
    local record = { id = store.sequence, savedAt = stamp(), partnerName = partnerName(ctx),
        automatic = automatic == true, localSnapshot = own, partnerSnapshot = friend }
    store.history[#store.history + 1] = record
    while #store.history > HISTORY_LIMIT do table.remove(store.history, 1) end
    store.lastPartner = record.partnerName
    self.autoElapsed = 0
    return true, record
end
function Journey:ResumeCheckpoint(index)
    local record = self:GetCheckpoint(index)
    if not record then return false, "No hay un punto conjunto guardado para esta pareja." end
    local ctx = context()
    if ctx.sameParty and partnerName(ctx) ~= record.partnerName then return false, "Este punto pertenece a otra pareja." end
    local own = record.localSnapshot
    local guide = ns.guides and ns.guides[own.guideID]
    if not allowed(guide) then return false, "La guía local del punto no está instalada o no coincide con tu personaje." end
    ns.char.progress = type(ns.char.progress) == "table" and ns.char.progress or {}
    if type(ns.char.progress[guide.id]) ~= "table" then
        -- Only our own saved cursor can initialize missing local progress.
        local cursor = ns.GetGuideCursorForRevision and ns:GetGuideCursorForRevision(guide.id, own.cursor, own.routeRevision) or own.cursor
        ns.char.progress[guide.id] = { cursor = math.min(cursor, #guide.steps + 1), confirmed = {}, review = true,
            routeRevision = guide.routeRevision }
    end
    ns.char.activeGuide = guide.id
    self:Store().lastPartner = record.partnerName
    -- Merely select the route: do not rewind existing progress or auto-confirm.
    if ns.RefreshUI then ns:RefreshUI() end
    if ns.UpdateNavigation then ns:UpdateNavigation() end
    return true, "Guía local seleccionada. Se conserva tu progreso actual; revisa las diferencias antes de continuar."
end

local function changed(before, after)
    if not before or not after then return false end
    if before.state ~= after.state then return true end
    for i = 1, OBJECTIVE_LIMIT do
        local a, b = before.objectives[i], after.objectives[i]
        if a and b and ((a.finished ~= nil and b.finished ~= nil and a.finished ~= b.finished)
            or (a.known and b.known and a.total == b.total and a.current ~= b.current)) then return true end
    end
    return false
end
function Journey:GetCatchUp(index)
    local record = self:GetCheckpoint(index)
    local result = { available = record ~= nil, known = false, localChanges = {}, partnerChanges = {}, missing = {}, quests = {}, unknownCount = 0 }
    if not record then result.status = "no_checkpoint"; return result end
    local ctx, store = context(), self:Store()
    local live = connected(ctx) and partnerName(ctx) == record.partnerName
    result.partnerName, result.checkpoint, result.known = record.partnerName, record, live
    local remote = live and remoteCheckpoint(ctx) or nil
    local guide, state = localRoute()
    if guide and (guide.id ~= record.localSnapshot.guideID or (state and state.cursor or 1) ~= record.localSnapshot.cursor) then
        result.localChanges[#result.localChanges + 1] = { kind = "route", text = "Tu selección o paso local cambió desde el punto guardado; no prueba que las misiones estén hechas." }
    end
    local oldFriend = record.partnerSnapshot
    if live and oldFriend and (ctx.guideID ~= oldFriend.guideID or ctx.cursor ~= oldFriend.cursor) then
        result.partnerChanges[#result.partnerChanges + 1] = { kind = "route", text = "La selección o el paso del amigo cambió; se comprueban sus misiones por separado." }
    end
    local ids = {}
    for _, id in ipairs(record.localSnapshot.trackedQuestIDs or {}) do if count(ids) < QUEST_LIMIT then ids[id] = true end end
    for _, id in ipairs(oldFriend and oldFriend.trackedQuestIDs or {}) do if count(ids) < QUEST_LIMIT then ids[id] = true end end
    for id in pairs(record.localSnapshot.quests) do if count(ids) < QUEST_LIMIT then ids[id] = true end end
    for id in pairs(oldFriend and oldFriend.quests or {}) do if count(ids) < QUEST_LIMIT then ids[id] = true end end
    for _, id in ipairs(sortedIDs(ids)) do
        local mine, friend = localQuest(id), live and remoteQuest(id, ctx, remote) or nil
        local item = { questID = id, title = title(id), localState = mine and mine.state, localKnown = mine ~= nil,
            partnerState = friend and friend.state, partnerKnown = friend ~= nil }
        result.quests[#result.quests + 1] = item
        if changed(record.localSnapshot.quests[id], mine) then
            result.localChanges[#result.localChanges + 1] = { kind = "quest", questID = id, text = item.title .. ": tu estado cambió desde el punto guardado." }
        end
        if oldFriend and changed(oldFriend.quests[id], friend) then
            result.partnerChanges[#result.partnerChanges + 1] = { kind = "quest", questID = id, text = item.title .. ": el estado del amigo cambió desde el punto guardado." }
        end
        local incomplete = not friend or not mine
        if mine and friend then
            if mine.state ~= friend.state then
                local owner = mine.state < friend.state and "local" or "partner"
                result.missing[#result.missing + 1] = { questID = id, owner = owner, kind = "quest",
                    text = item.title .. ": tú " .. STATE_NAMES[mine.state] .. "; amigo " .. STATE_NAMES[friend.state] .. ". Revisad aceptar, objetivos y entrega por separado." }
            elseif mine.state == 1 then
                local hasObjectives = false
                for i = 1, OBJECTIVE_LIMIT do
                    local a, b = mine.objectives[i], friend.objectives[i]
                    local owner
                    if a or b then hasObjectives = true end
                    if a and b then
                        if a.known and b.known and a.total == b.total and a.current ~= b.current then owner = a.current < b.current and "local" or "partner"
                        elseif a.finished ~= nil and b.finished ~= nil and a.finished ~= b.finished then owner = a.finished and "partner" or "local" end
                    end
                    if (a or b) and not (a and b and ((a.finished == true and b.finished == true)
                        or (a.known and b.known and a.total == b.total))) then incomplete = true end
                    if owner then
                        result.missing[#result.missing + 1] = { questID = id, objective = i, owner = owner, kind = "objective",
                            text = item.title .. " · objetivo " .. i .. ": " .. (owner == "local" and "tú llevas menos progreso observado" or "el amigo lleva menos progreso observado") .. "." }
                    end
                end
                if not hasObjectives then incomplete = true end
            end
        end
        if incomplete then result.unknownCount = result.unknownCount + 1 end
    end
    result.status = not live and "offline" or (#result.missing > 0 and "different")
        or ((result.unknownCount > 0 or #result.quests == 0) and "unknown") or "aligned"
    result.recovered = store.recovered
    return result
end
function Journey:GetCheckpointReport(index)
    local catch = self:GetCatchUp(index)
    if not catch.available then return "Todavía no hay un punto conjunto para esta pareja. Guardad cuando los dos estéis conectados y con RutaXP confirmado." end
    local record, lines = catch.checkpoint, {}
    local guide = ns.guides and ns.guides[record.localSnapshot.guideID]
    lines[#lines + 1] = "Punto conjunto con " .. record.partnerName .. " · " .. (guide and guide.title or record.localSnapshot.guideID) .. " · tu paso guardado " .. record.localSnapshot.cursor
    lines[#lines + 1] = "Se conservan hasta veinte puntos. Reanudar selecciona tu guía y conserva el progreso que hayas hecho después. El paso del amigo nunca se copia."
    if not catch.known then lines[#lines + 1] = "Compañero sin datos actuales. Se conserva la fotografía guardada, pero no se da por hecho que siga igual." end
    if #catch.localChanges > 0 then lines[#lines + 1] = "Tus cambios observados: " .. #catch.localChanges end
    if #catch.partnerChanges > 0 then lines[#lines + 1] = "Cambios observados del amigo: " .. #catch.partnerChanges end
    for i = 1, math.min(16, #catch.missing) do lines[#lines + 1] = "• " .. catch.missing[i].text end
    if catch.status == "aligned" then lines[#lines + 1] = "No hay diferencias en las misiones de esta fotografía. No representa todo el registro de misiones." end
    if #catch.quests == 0 then lines[#lines + 1] = "La fotografía no conserva observaciones de misiones comparables. No se puede confirmar que los registros coincidan." end
    if catch.unknownCount > 0 then lines[#lines + 1] = "Misiones con datos actuales incompletos: " .. catch.unknownCount .. ". Esperad a sincronizar; no se consideran completadas." end
    if catch.recovered then lines[#lines + 1] = "Se recuperaron puntos válidos de datos guardados incompletos." end
    return table.concat(lines, "\n\n")
end

function Journey:GetStops()
    local ctx, proposals = context(), {}
    local name, live = partnerName(ctx), connected(ctx)
    local record = self:GetCheckpoint(nil, name)
    local function add(kind, owner, explanation, coordinated)
        for _, old in ipairs(proposals) do if old.kind == kind and old.owner == owner then return end end
        proposals[#proposals + 1] = { kind = kind, owner = owner, title = STOP_TITLES[kind], text = explanation, coordinated = coordinated }
    end
    local peer = live and remoteCheckpoint(ctx)
    if peer and STOP_TITLES[peer.stopKind] then add(peer.stopKind, "partner", "Tu amigo propone esta parada. Puedes unirte; no se ejecuta ninguna acción automáticamente.", true) end
    local function inspect(data, owner, baseline)
        if type(data) ~= "table" or data.known ~= true then return end
        local who = owner == "local" and "Tú" or "Tu amigo"
        local free = integer(data.freeSlots, 0, 1000)
        if free and free <= 2 then add("vendor", owner, who .. (free == 0 and ": bolsas llenas." or (": quedan " .. free .. " huecos de bolsa."))) end
        local durability = number(data.durabilityPercent)
        if durability and durability >= 0 and durability <= 25 then add("repair", owner, string.format("%s: durabilidad observada %.0f%%. Buscad un reparador.", who, durability)) end
        local mana = number(data.manaPercent)
        if mana and mana >= 0 and mana <= 20 then add("rest", owner, string.format("%s: maná observado %.0f%%. Acordad descansar en un lugar seguro.", who, mana)) end
        local level = integer(data.level, 1, 100)
        if level and baseline and baseline.level and level > baseline.level then
            add("trainer", owner, who .. ": nivel " .. level .. " (antes " .. baseline.level .. "). Revisad habilidades y talentos disponibles para su clase; no se presupone una compra.")
        end
    end
    inspect(ns.Duo and safe(ns.Duo.GetLocalSupplies, ns.Duo), "local", record and record.localSnapshot)
    if live then inspect(ns.Duo and safe(ns.Duo.GetPartnerSupplies, ns.Duo), "partner", record and record.partnerSnapshot) end
    return proposals
end
function Journey:SetStop(kind)
    local store, ctx = self:Store(), context()
    if not store or not connected(ctx) then return false, "Hace falta un compañero conectado y confirmado para proponer una parada conjunta." end
    if not STOP_TITLES[kind] then return false, "Elige una parada disponible." end
    store.stop = { kind = kind, partnerName = partnerName(ctx), ready = false, startedAt = stamp() }
    return true
end
function Journey:BeginStop(index)
    local proposal = self:GetStops()[tonumber(index) or 0]
    if not proposal then return false, "La propuesta de parada ya no está disponible." end
    return self:SetStop(proposal.kind)
end
function Journey:SetStopReady(value)
    local store, ctx = self:Store(), context()
    if not store or not store.stop or store.stop.partnerName ~= partnerName(ctx) or not connected(ctx) then
        return false, "No hay una parada activa con un compañero confirmado."
    end
    store.stop.ready = value == true
    return true
end
function Journey:EndStop()
    local store = self:Store()
    if not store or not store.stop then return false, "No tienes una parada activa." end
    store.stop = nil
    return true
end
function Journey:GetStopStatus()
    local store, ctx = self:Store(), context()
    local own = store and store.stop
    local live = connected(ctx)
    if own and partnerName(ctx) and own.partnerName ~= partnerName(ctx) then own = nil end
    local peer = live and remoteCheckpoint(ctx)
    local peerKind = (peer and STOP_TITLES[peer.stopKind] and peer.stopKind) or nil
    local same = own and peerKind == own.kind
    return { active = own ~= nil or peerKind ~= nil, kind = own and own.kind or peerKind,
        title = STOP_TITLES[own and own.kind or peerKind], localActive = own ~= nil,
        localReady = own and own.ready == true or false, partnerReady = same and peer.stopReady == true or false,
        partnerKind = peerKind, known = live and peer ~= nil, partnerName = own and own.partnerName or partnerName(ctx),
        bothReady = live and same and own.ready == true and peer.stopReady == true or false }
end
function Journey:GetStopReport()
    local status = self:GetStopStatus()
    if not status.active then
        local stops = self:GetStops()
        if #stops == 0 then return "Sin paradas propuestas por los datos disponibles. Las necesidades desconocidas no se consideran resueltas." end
        local lines = { "Paradas propuestas (tú decides cuándo acordarlas):" }
        for i, item in ipairs(stops) do lines[#lines + 1] = i .. ". " .. item.title .. " · " .. item.text end
        return table.concat(lines, "\n\n")
    end
    local lines = { "Parada: " .. (status.title or "Revisar"), "Tú: " .. (status.localReady and "listo" or "pendiente") .. " · amigo: " .. (status.partnerReady and "listo" or "sin confirmar") }
    if status.bothReady then lines[#lines + 1] = "Ambos habéis marcado listos para esta parada. Decidid cuándo continuar."
    elseif not status.known then lines[#lines + 1] = "Falta confirmación reciente del compañero."
    elseif not status.localActive then lines[#lines + 1] = "Tu amigo propone esta parada. Únete si estáis de acuerdo."
    elseif status.partnerKind and status.partnerKind ~= status.kind then lines[#lines + 1] = "El amigo tiene otra parada seleccionada; acordad la misma." end
    lines[#lines + 1] = "Proponer, marcar listo o terminar una parada no vende, compra, repara, gasta talentos ni mueve la guía."
    return table.concat(lines, "\n\n")
end
function Journey:GetReport() return self:GetCheckpointReport() .. "\n\n" .. self:GetStopReport() end
function Journey:Tick(elapsed)
    if not self:Store() then return end
    local ctx = context()
    if not connected(ctx) then self.autoPartner, self.autoElapsed = nil, 0; return end
    local name = partnerName(ctx)
    if self.autoPartner ~= name then
        self.autoPartner, self.autoElapsed = name, 0
        if not self:GetCheckpoint(nil, name) then self:SaveCheckpoint(true) end
        return
    end
    self.autoElapsed = (self.autoElapsed or 0) + math.min(60, math.max(0, number(elapsed) or 0))
    if self.autoElapsed >= AUTO_INTERVAL then self:SaveCheckpoint(true) end
end
function Journey:Initialize()
    if self.initialized then return end
    if not self:Store() then return end
    self.initialized = true
    if ns.Duo and ns.Duo.RegisterCheckpointProvider then
        ns.Duo:RegisterCheckpointProvider(function()
            local name = canonical(ns.Duo.partnerName)
            local record = self:GetCheckpoint(nil, name)
            local stop = self:Store().stop
            if not name or (stop and stop.partnerName ~= name) then stop = nil end
            return { checkpointID = record and tostring(record.id) or "none",
                guideID = record and record.localSnapshot.guideID, cursor = record and record.localSnapshot.cursor,
                stopKind = stop and stop.kind or "none", stopReady = stop and stop.ready == true or false }
        end)
    end
    self.frame = CreateFrame("Frame")
    self.frame:RegisterEvent("PLAYER_LOGOUT")
    self.frame:SetScript("OnEvent", function() self:SaveCheckpoint(true) end)
end
