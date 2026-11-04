local _, ns = ...

-- Local, bounded observations. These counters never complete or accept quests.
-- Map API contract: Blizzard_APIDocumentationGenerated/MapDocumentation.lua
-- in Gethe/wow-ui-source's Forever branch (GetWorldPosFromMapPos).
local Session = {}
ns.Session = Session
local HISTORY_LIMIT, QUEST_LIMIT, STEP_LIMIT, GUIDE_LIMIT = 20, 100, 256, 32

local function safe(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, a, b, c = pcall(fn, ...)
    if ok then return a, b, c end
end

local function number(value)
    if issecretvalue and issecretvalue(value) then return nil end
    if type(value) == "number" and value == value and math.abs(value) < math.huge then return value end
end

local function stamp() return number(safe(GetServerTime)) or number(safe(time)) or 0 end
local function clock() return number(safe(GetTime)) end
local function add(t, key, value) t[key] = (number(t[key]) or 0) + value end
local function size(t) local n = 0; for _ in pairs(t) do n = n + 1 end; return n end
local function metrics()
    return { activeSeconds=0, afkSeconds=0, pausedSeconds=0, unobservedSeconds=0,
        xp=0, activeXP=0, distanceYards=0, travelSeconds=0, taxiSeconds=0,
        deaths=0, quests=0, stepsAdvanced=0, samples=0, xpUncertain=0, unobservedXP=0 }
end

local function nonnegative(value) return math.max(0, number(value) or 0) end
local function cleanMetrics(source)
    local result = metrics()
    if type(source) == "table" then
        for key in pairs(result) do result[key] = nonnegative(source[key]) end
    end
    return result
end
local function cleanRecord(source)
    if type(source) ~= "table" or type(source.totals) ~= "table" then return nil end
    local result = { startedAt=nonnegative(source.startedAt), lastSeenAt=nonnegative(source.lastSeenAt),
        endedAt=number(source.endedAt), reason=type(source.reason) == "string" and source.reason or nil,
        levelStart=number(source.levelStart), totals=cleanMetrics(source.totals), byGuide={}, steps={}, quests={} }
    for id, data in pairs(type(source.byGuide) == "table" and source.byGuide or {}) do
        if type(id) == "string" and size(result.byGuide) < GUIDE_LIMIT + 1 then result.byGuide[id] = cleanMetrics(data) end
    end
    for key, data in pairs(type(source.steps) == "table" and source.steps or {}) do
        if type(key) == "string" and type(data) == "table" and size(result.steps) < STEP_LIMIT + 1 then
            result.steps[key] = { guideID=type(data.guideID) == "string" and data.guideID or "__sin_guia",
                cursor=math.max(1, number(data.cursor) or 1), activeSeconds=nonnegative(data.activeSeconds), visits=nonnegative(data.visits) }
        end
    end
    local quests = type(source.quests) == "table" and source.quests or {}
    for i = math.max(1, #quests - QUEST_LIMIT + 1), #quests do
        local data = quests[i]
        if type(data) == "table" and number(data.questID) then
            result.quests[#result.quests + 1] = { questID=data.questID, known=data.known == true and number(data.activeSeconds) ~= nil,
                activeSeconds=number(data.activeSeconds) and nonnegative(data.activeSeconds) or nil,
                startedGuideID=type(data.startedGuideID) == "string" and data.startedGuideID or nil,
                endedGuideID=type(data.endedGuideID) == "string" and data.endedGuideID or nil }
        end
    end
    return result
end

local function cleanStore(store)
    if (store.history ~= nil and type(store.history) ~= "table")
        or (store.questStarts ~= nil and type(store.questStarts) ~= "table") then store.recovered = true end
    store.activeClock = nonnegative(store.activeClock)
    store.paused = store.paused == true
    local history, original = {}, type(store.history) == "table" and store.history or {}
    for i = math.max(1, #original - HISTORY_LIMIT + 1), #original do
        local record = cleanRecord(original[i])
        if record then history[#history + 1] = record else store.recovered = true end
    end
    store.history = history
    if store.current ~= nil then
        local record = cleanRecord(store.current)
        if not record then store.recovered = true end
        store.current = record
    end
    local starts = {}
    for id, item in pairs(type(store.questStarts) == "table" and store.questStarts or {}) do
        local quest = (type(id) == "number" or type(id) == "string") and tonumber(id) or nil
        if quest and quest > 0 and type(item) == "table" and number(item.clock)
            and item.clock >= 0 and item.clock <= store.activeClock then
            starts[#starts + 1] = { id=quest, clock=item.clock, at=nonnegative(item.at),
                guideID=type(item.guideID) == "string" and item.guideID or "__sin_guia", removed=item.removed == true or nil }
        else store.recovered = true end
    end
    table.sort(starts, function(a, b) if a.clock == b.clock then return a.id < b.id end; return a.clock < b.clock end)
    store.questStarts = {}
    for i = math.max(1, #starts - QUEST_LIMIT + 1), #starts do
        local item = starts[i]
        store.questStarts[item.id] = { clock=item.clock, at=item.at, guideID=item.guideID, removed=item.removed }
    end
end

local function context()
    local id = ns.char and ns.char.activeGuide
    local guide = id and ns.guides and ns.guides[id]
    local state = id and ns.char.progress and ns.char.progress[id]
    return { id=guide and id or "__sin_guia", cursor=state and tonumber(state.cursor) or 1,
        review=state and state.review == true or false }
end

local function mode(self)
    if self.store.paused then return "pausedSeconds" end
    if safe(UnitIsAFK, "player") == true then return "afkSeconds" end
    return "activeSeconds"
end

local function worldPoint()
    local point = safe(ns.PlayerPoint, ns)
    if not point then
        local map = safe(C_Map and C_Map.GetBestMapForUnit, "player")
        local pos = map and safe(C_Map and C_Map.GetPlayerMapPosition, map, "player")
        local x, y
        if pos then x, y = safe(pos.GetXY, pos) end
        if x and y then point = { mapID=map, x=x, y=y } end
    end
    if not point or not number(point.mapID) or not number(point.x) or not number(point.y) then return nil end
    local vector = safe(CreateVector2D, point.x, point.y)
    local continent, pos
    if vector then continent, pos = safe(C_Map and C_Map.GetWorldPosFromMapPos, point.mapID, vector) end
    if not number(continent) or not pos then return nil end
    local north, west = safe(pos.GetXY, pos)
    if number(north) and number(west) then return { continent=continent, x=north, y=west } end
end

local function bucket(self, id)
    local all = self.current.byGuide
    if not all[id] and size(all) >= GUIDE_LIMIT then id = "__otras_guias" end
    if not all[id] then all[id] = metrics() end
    return all[id]
end

local function increase(self, key, value, id)
    add(self.current.totals, key, value)
    add(bucket(self, id or self.context.id), key, value)
end

local function stepBucket(self, where)
    local key = where.id .. ":" .. tostring(where.cursor)
    if not self.current.steps[key] and size(self.current.steps) >= STEP_LIMIT then key = "__otros_pasos" end
    if not self.current.steps[key] then
        self.current.steps[key] = { guideID=where.id, cursor=where.cursor, activeSeconds=0, visits=0 }
    end
    return self.current.steps[key]
end

local function newRecord(self)
    local record = { startedAt=stamp(), lastSeenAt=stamp(), levelStart=number(safe(UnitLevel, "player")),
        totals=metrics(), byGuide={}, steps={}, quests={} }
    self.store.current, self.current = record, record
    self.context, self.mode = context(), mode(self)
    self.lastMono, self.pending = clock(), 0
    self.point, self.wasTaxi, self.loading = nil, safe(UnitOnTaxi, "player") == true, false
    self.xpState, self.dead = nil, safe(UnitIsDeadOrGhost, "player") == true
    self.lastProgressClock = self.store.activeClock
    stepBucket(self, self.context).visits = 1
end

local function archive(self, reason)
    local record = self.store.current
    if type(record) ~= "table" then return end
    record.endedAt, record.reason = record.lastSeenAt or record.startedAt, reason
    self.store.history[#self.store.history + 1] = record
    while #self.store.history > HISTORY_LIMIT do table.remove(self.store.history, 1) end
    self.store.current, self.current = nil, nil
end

local function observeXP(self, activeWindow)
    local xp, maximum, level = number(safe(UnitXP, "player")), number(safe(UnitXPMax, "player")), number(safe(UnitLevel, "player"))
    if not xp or not maximum or not level then self.xpState = nil; return end
    local previous, gained = self.xpState, nil
    if previous then
        if level == previous.level and xp >= previous.xp then gained = xp - previous.xp
        elseif level == previous.level + 1 and previous.maximum > 0 then gained = previous.maximum - previous.xp + xp
        elseif level ~= previous.level or xp < previous.xp then increase(self, "xpUncertain", 1) end
    end
    self.xpState = { xp=xp, maximum=maximum, level=level }
    if gained and gained > 0 then
        increase(self, "xp", gained)
        if activeWindow == false then increase(self, "unobservedXP", gained)
        elseif self.mode == "activeSeconds" then increase(self, "activeXP", gained) end
        self.lastProgressClock = self.store.activeClock
    end
end

local function progressSignature(where)
    local guide = ns.guides and ns.guides[where.id]
    local step = guide and guide.steps and guide.steps[where.cursor]
    local pieces = {}
    for _, goal in ipairs(step and step.goals or {}) do
        local id = goal.quest or goal.questID
        if id then
            local list = safe(C_QuestLog and C_QuestLog.GetQuestObjectives, id)
            for index, item in ipairs(type(list) == "table" and list or {}) do
                pieces[#pieces + 1] = tostring(id) .. ":" .. index .. ":" .. tostring(item.numFulfilled) .. ":" .. tostring(item.finished)
            end
        end
    end
    return table.concat(pieces, "|")
end

function Session:Initialize()
    if self.initialized then return true end
    if not ns.char then return false end
    ns.char.sessions = type(ns.char.sessions) == "table" and ns.char.sessions or {}
    self.store = ns.char.sessions
    self.store.version = 1
    cleanStore(self.store)
    -- A reload/offline gap ends the old observation at its last saved sample,
    -- never at today's login time. Accepted quest timers use activeClock only.
    archive(self, "recarga o nueva entrada")
    newRecord(self)
    observeXP(self)
    self.initialized = true
    if CreateFrame and not self.frame then
        self.frame = CreateFrame("Frame")
        for _, event in ipairs({ "PLAYER_XP_UPDATE", "PLAYER_LEVEL_UP", "PLAYER_FLAGS_CHANGED", "QUEST_ACCEPTED",
            "QUEST_TURNED_IN", "QUEST_REMOVED", "QUEST_LOG_UPDATE", "QUEST_WATCH_UPDATE", "PLAYER_DEAD",
            "PLAYER_UNGHOST", "PLAYER_ALIVE", "PLAYER_ENTERING_WORLD", "PLAYER_LEAVING_WORLD", "PLAYER_LOGOUT", "UNIT_SPELLCAST_SUCCEEDED" }) do
            safe(self.frame.RegisterEvent, self.frame, event)
        end
        self.frame:SetScript("OnEvent", function(_, event, ...) if self.initialized then self:OnEvent(event, ...) end end)
    end
    return true
end

function Session:Tick(elapsed, force)
    if not self.initialized or not self.current then return end
    local now = clock()
    local dt = now and self.lastMono and now - self.lastMono or number(elapsed) or 0
    self.lastMono = now or self.lastMono
    if dt < 0 then self.point = nil; dt = 0 end
    self.pending = self.pending + dt
    if self.pending < 1 and not force then return end
    dt, self.pending = self.pending, 0
    if dt > 30 or self.loading then
        increase(self, "unobservedSeconds", dt)
        self.point = nil
    elseif dt > 0 then
        increase(self, self.mode, dt)
        if self.mode == "activeSeconds" then
            self.store.activeClock = self.store.activeClock + dt
            increase(self, "samples", 1)
            add(stepBucket(self, self.context), "activeSeconds", dt)
        end
        local taxi = safe(UnitOnTaxi, "player") == true
        if taxi and self.mode == "activeSeconds" then increase(self, "taxiSeconds", dt) end
        local point = not taxi and not self.wasTaxi and self.mode == "activeSeconds"
            and (not self.ignoreMovementUntil or not now or now >= self.ignoreMovementUntil) and worldPoint() or nil
        if point and self.point and dt <= 5 and point.continent == self.point.continent then
            local distance = ((point.x - self.point.x)^2 + (point.y - self.point.y)^2)^0.5
            -- Conservative ground-travel estimate; jumps/ports are discarded.
            if distance <= 30 * dt and distance > 0 then
                increase(self, "distanceYards", distance)
                if distance >= 1 then increase(self, "travelSeconds", dt) end
            end
        end
        self.point, self.wasTaxi = point, taxi
    end
    observeXP(self, not (dt > 30 or self.loading))
    local current = context()
    if current.id ~= self.context.id or current.cursor ~= self.context.cursor or current.review ~= self.context.review then
        if current.id == self.context.id and current.cursor > self.context.cursor and not current.review and not self.context.review then
            increase(self, "stepsAdvanced", 1)
        end
        self.context = current
        add(stepBucket(self, current), "visits", 1)
        self.lastProgressClock, self.progressSignature = self.store.activeClock, nil
    end
    if self.current.totals.samples % 10 == 0 or force then
        local signature = progressSignature(self.context)
        if self.progressSignature and signature ~= self.progressSignature then self.lastProgressClock = self.store.activeClock end
        self.progressSignature = signature
    end
    self.mode = mode(self)
    self.current.lastSeenAt = stamp()
end

function Session:OnEvent(event, first, second)
    if not self.initialized or not self.current then return end
    if event == "PLAYER_ENTERING_WORLD" or event == "PLAYER_LEAVING_WORLD"
        or (event == "UNIT_SPELLCAST_SUCCEEDED" and first == "player") then self.point = nil end
    self:Tick(0, true)
    if event == "PLAYER_DEAD" then
        if not self.dead then increase(self, "deaths", 1) end
        self.dead, self.point = true, nil
    elseif event == "PLAYER_UNGHOST" or event == "PLAYER_ALIVE" then self.dead = safe(UnitIsDeadOrGhost, "player") == true
    elseif event == "QUEST_ACCEPTED" then
        local id = number(second) or number(first)
        if id then
            self.store.questStarts[id] = { clock=self.store.activeClock, at=stamp(), guideID=self.context.id }
            if size(self.store.questStarts) > QUEST_LIMIT then
                local oldest, at
                for quest, item in pairs(self.store.questStarts) do
                    if not at or (item.clock or 0) < at then oldest, at = quest, item.clock or 0 end
                end
                if oldest then self.store.questStarts[oldest] = nil end
            end
        end
        self.lastProgressClock = self.store.activeClock
    elseif event == "QUEST_TURNED_IN" then
        local id = number(first)
        if id then
            increase(self, "quests", 1)
            local start = self.store.questStarts[id]
            local entry = { questID=id, known=type(start) == "table", endedGuideID=self.context.id }
            if start then entry.activeSeconds = math.max(0, self.store.activeClock - (start.clock or self.store.activeClock)); entry.startedGuideID = start.guideID end
            self.current.quests[#self.current.quests + 1] = entry
            while #self.current.quests > QUEST_LIMIT do table.remove(self.current.quests, 1) end
            self.store.questStarts[id] = nil
        end
        self.lastProgressClock = self.store.activeClock
    elseif event == "QUEST_REMOVED" then
        -- Do not erase the timer here: this event can precede TURNED_IN.
        local item = self.store.questStarts[number(first)]
        if item then item.removed = true end
    elseif event == "UNIT_SPELLCAST_SUCCEEDED" and first == "player" then
        -- Also covers short teleport spells; undercounts movement conservatively.
        self.point, self.ignoreMovementUntil = nil, (clock() or 0) + 2
    elseif event == "PLAYER_LEAVING_WORLD" then self.loading, self.point = true, nil
    elseif event == "PLAYER_ENTERING_WORLD" then self.loading, self.point, self.lastMono = false, nil, clock()
    elseif event == "PLAYER_LOGOUT" then archive(self, "salida") end
    if ns.Adaptation and ns.Adaptation.Invalidate then ns.Adaptation:Invalidate() end
end

function Session:SetPaused(paused)
    if not self.initialized then return false end
    self:Tick(0, true)
    self.store.paused = paused == true
    self.mode, self.point = mode(self), nil
    return self.store.paused
end

function Session:GetSummary()
    if not self.initialized then return { available=false, flags={} } end
    local record = self.current or self.store.history[#self.store.history]
    if not record then return { available=false, flags={} } end
    local result = { available=true, startedAt=record.startedAt, paused=self.store.paused == true, flags={}, historyCount=#self.store.history, byGuide=record.byGuide, recovered=self.store.recovered == true }
    for key, value in pairs(record.totals) do result[key] = value end
    result.xpPerHour = result.activeSeconds > 0 and result.activeXP * 3600 / result.activeSeconds or 0
    result.distanceMeters = result.distanceYards * 0.9144
    result.questTimings, result.stepTimings = record.quests, record.steps
    result.estimated = true
    if self.current and result.activeSeconds >= 600 and result.samples >= 60
        and self.store.activeClock - self.lastProgressClock >= 600 and not self.context.review then
        result.flags[#result.flags + 1] = { code="stuck", title="Revisar el paso actual", text="Diez minutos activos sin avance observado. Puede ser farmeo, espera o un requisito pendiente; revisa el registro antes de saltar nada." }
    end
    if result.activeSeconds >= 900 and result.samples >= 90 and result.travelSeconds >= 600
        and self.xpState and self.xpState.maximum > 0 and result.xpPerHour < self.xpState.maximum * 0.15 then
        result.flags[#result.flags + 1] = { code="travel_low_xp", title="Mucho recorrido y poca XP observada", text="Hay al menos quince minutos activos y diez de desplazamiento terrestre con poca XP. Puede ser un traslado necesario; revisa las entregas cercanas, sin abandonar cadenas de clase." }
    end
    return result
end

local function duration(seconds)
    return string.format("%d min %02d s", math.floor((seconds or 0)/60), math.floor((seconds or 0)%60))
end

function Session:GetReport()
    local s = self:GetSummary()
    if not s.available then return "Todavía no hay una sesión observada." end
    local lines = { "Sesión local de RutaXP", "Activo estimado: " .. duration(s.activeSeconds) .. " · AFK: " .. duration(s.afkSeconds) .. " · Pausa: " .. duration(s.pausedSeconds),
        string.format("XP observada: %d · XP/h activa estimada: %.0f", s.xp, s.xpPerHour),
        string.format("Recorrido terrestre estimado: %.0f m · Muertes observadas: %d", s.distanceMeters, s.deaths),
        string.format("Misiones entregadas observadas: %d · Avances de paso observados: %d", s.quests, s.stepsAdvanced),
        "Solo datos de este personaje; no se envían fuera del juego. Activo significa conectado sin AFK ni pausa, no atención medida.",
        "El recorrido excluye taxis, saltos de continente, cargas, saltos rápidos y muestras tras hechizos; puede quedarse corto. No incluye tiempo desconectado ni certifica una ruta optimizada o probada." }
    if s.unobservedSeconds > 0 then lines[#lines + 1] = "Intervalos sin medir: " .. duration(s.unobservedSeconds) end
    if s.xpUncertain > 0 then lines[#lines + 1] = "Hubo cambios de nivel/XP que no se pudieron reconstruir: no se inventó la XP intermedia." end
    if s.unobservedXP > 0 then lines[#lines + 1] = "XP ganada durante intervalos sin medir: " .. s.unobservedXP .. "; se excluye de la XP/h activa." end
    if s.recovered then lines[#lines + 1] = "Se encontraron observaciones antiguas inválidas; se recuperaron los datos utilizables sin tocar el progreso de las guías." end
    local guides = {}
    for id, data in pairs(s.byGuide or {}) do guides[#guides + 1] = { id=id, data=data } end
    table.sort(guides, function(a, b) return a.data.activeSeconds > b.data.activeSeconds end)
    if #guides > 0 then
        lines[#lines + 1] = "\nPor guía en esta sesión (XP atribuida a la guía seleccionada, no a una misión concreta):"
        for i = 1, math.min(10, #guides) do
            local item = guides[i]
            local guide = ns.guides and ns.guides[item.id]
            local title = guide and guide.title or (item.id == "__sin_guia" and "Sin guía seleccionada" or item.id == "__otras_guias" and "Otras guías" or item.id)
            lines[#lines + 1] = string.format("• %s: %s activa · %d XP · %d entregas", title, duration(item.data.activeSeconds), item.data.xp, item.data.quests)
        end
    end
    local quests, steps = {}, {}
    local function collect(record)
        for _, entry in ipairs(record.quests or {}) do
            if entry.known and number(entry.activeSeconds) then quests[#quests + 1] = entry end
        end
        for key, item in pairs(record.steps or {}) do
            if key ~= "__otros_pasos" then
                local target = steps[key] or { guideID=item.guideID, cursor=item.cursor, activeSeconds=0, visits=0 }
                target.activeSeconds = target.activeSeconds + (item.activeSeconds or 0)
                target.visits = target.visits + (item.visits or 0)
                steps[key] = target
            end
        end
    end
    for _, record in ipairs(self.store.history) do collect(record) end
    if self.current then collect(self.current) end
    table.sort(quests, function(a, b) return a.activeSeconds > b.activeSeconds end)
    lines[#lines + 1] = "\nEntregas con mayor tiempo observado (sesiones conservadas):"
    lines[#lines + 1] = "Tiempo activo transcurrido entre aceptar y entregar; incluye viajes y otras misiones, no tiempo exclusivo ni XP por misión."
    if #quests == 0 then lines[#lines + 1] = "Aún no hay entregas con el inicio observado." end
    for i = 1, math.min(10, #quests) do
        local item = quests[i]
        local title = safe(ns.GetQuestTitle, ns, item.questID) or ("Misión " .. tostring(item.questID))
        lines[#lines + 1] = string.format("• %s [%d]: %s", title, item.questID, duration(item.activeSeconds))
    end
    local orderedSteps = {}
    for _, item in pairs(steps) do orderedSteps[#orderedSteps + 1] = item end
    table.sort(orderedSteps, function(a, b) return a.activeSeconds > b.activeSeconds end)
    lines[#lines + 1] = "\nPasos con más tiempo seleccionado (sesiones conservadas):"
    lines[#lines + 1] = "Incluye revisión y tareas paralelas; visitas y tiempo no significan pasos completados."
    for i = 1, math.min(10, #orderedSteps) do
        local item = orderedSteps[i]
        local guide = ns.guides and ns.guides[item.guideID]
        local step = guide and guide.steps and guide.steps[item.cursor]
        lines[#lines + 1] = string.format("• %s · paso %s%s: %s · %d visitas", guide and guide.title or item.guideID,
            tostring(item.cursor), step and (" («" .. step.title .. "»)") or "", duration(item.activeSeconds), item.visits)
    end
    if #self.store.history > 0 then
        lines[#lines + 1] = "\nHistorial local (hasta veinte partidas; sin tiempo desconectado):"
        for i, record in ipairs(self.store.history) do
            lines[#lines + 1] = string.format("• Partida %d: %s activa · %d XP · %d entregas · %d muertes", i,
                duration(record.totals.activeSeconds), record.totals.xp, record.totals.quests, record.totals.deaths)
        end
    end
    for _, flag in ipairs(s.flags) do lines[#lines + 1] = flag.title .. ": " .. flag.text end
    return table.concat(lines, "\n")
end

function Session:Reset(all)
    if not self.initialized then return false end
    self:Tick(0, true)
    if all == true then self.store.history, self.store.questStarts, self.store.activeClock = {}, {}, 0
    else archive(self, "reiniciada") end
    newRecord(self)
    observeXP(self)
    return true
end
