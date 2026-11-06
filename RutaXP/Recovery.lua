local _, ns = ...

-- Recovery is opt-in: inspecting a blocker never moves or edits the route.
-- Only authored quest actions enter the temporary guide; quest delivery is
-- always checked against the game before the original bookmark is resumed.
local R = {}
ns.Recovery = R
local TEMP_ID = "_recovery"
local MAX_DEPTH, MAX_QUESTS, MAX_STEPS, MAX_WORK = 24, 64, 200, 768

local function copy(value, seen, depth)
    local kind = type(value)
    if kind == "string" or kind == "boolean" or kind == "number" then return value end
    if kind ~= "table" or (depth or 0) > 24 then return nil end
    seen = seen or {}
    if seen[value] then return nil end
    seen[value] = true
    local out = {}
    for key, item in pairs(value) do
        if (type(key) == "string" or type(key) == "number") and key ~= "_rxpSpot" then
            out[key] = copy(item, seen, (depth or 0) + 1)
        end
    end
    seen[value] = nil
    return out
end

local function read(api, ...)
    if type(api) ~= "function" then return nil end
    local ok, value = pcall(api, ...)
    if ok and not (issecretvalue and issecretvalue(value)) then return value end
end

local function questID(goal)
    local id = goal and (goal.quest or goal.questID)
    return type(id) == "number" and id > 0 and id or nil
end

local function action(goal) return goal and (goal.t or goal.action) end
local function delivered(id) return ns.IsQuestDelivered and ns:IsQuestDelivered(id) or false end
local function active(id) return ns.IsQuestActive and ns:IsQuestActive(id) or false end
local function completed(id) return read(C_QuestLog and C_QuestLog.IsComplete, id) == true end
local function matches(only) return not ns.MatchesConditions or ns:MatchesConditions(only) end

local function title(id, fallback)
    local name = read(C_QuestLog and C_QuestLog.GetTitleForQuestID, id)
    return (type(name) == "string" and name ~= "" and name) or fallback or ("Misión " .. tostring(id))
end

local function compatibleGuide(guide)
    return guide and not guide.recovery and guide.id ~= TEMP_ID
        and (not guide.faction or guide.faction == UnitFactionGroup("player"))
        and matches(guide.only)
        and matches({ classes = guide.classes, races = guide.races, factions = guide.factions })
end

local catalogCache
local function catalog()
    local _, class = UnitClass("player")
    local _, race = UnitRace("player")
    local identity = tostring(class) .. ":" .. tostring(race) .. ":" .. tostring(UnitFactionGroup("player"))
    if catalogCache and catalogCache.identity == identity and catalogCache.count == #ns.order then
        local same = true
        for _, id in ipairs(ns.order) do if catalogCache.guides[id] ~= ns.guides[id] then same = false; break end end
        if same then return catalogCache.index end
    end
    local byQuest = {}
    local guideRefs = {}
    for guideOrder, guideID in ipairs(ns.order or {}) do
        local guide = ns.guides[guideID]
        guideRefs[guideID] = guide
        if compatibleGuide(guide) then
            local perGuide, sequence = {}, 0
            for stepIndex, step in ipairs(guide.steps or {}) do
                local goals = step.goals or { step }
                for goalIndex, goal in ipairs(goals) do
                    sequence = sequence + 1
                    local id = questID(goal)
                    if id and matches(step.only) and matches(goal.only) then
                        perGuide[id] = perGuide[id] or {}
                        perGuide[id][#perGuide[id] + 1] = {
                            goal = goal, step = step, guideID = guideID, stepIndex = stepIndex,
                            goalIndex = goalIndex, sequence = sequence, guideOrder = guideOrder,
                        }
                    end
                end
            end
            for id, records in pairs(perGuide) do
                byQuest[id] = byQuest[id] or {}
                byQuest[id][#byQuest[id] + 1] = records
            end
        end
    end
    catalogCache = { identity = identity, count = #ns.order, guides = guideRefs, index = byQuest }
    return byQuest
end

local function emptyPlan() return { order = {}, quests = {}, cost = 0 } end

local function merge(into, other)
    for _, id in ipairs(other.order) do
        if not into.quests[id] then
            into.order[#into.order + 1] = id
            into.quests[id] = other.quests[id]
            into.cost = into.cost + #other.quests[id].records
        end
    end
    return #into.order <= MAX_QUESTS
end

local function closed(goal)
    for _, id in ipairs(goal.closedBy or {}) do
        if active(math.abs(id)) or delivered(math.abs(id)) then return true end
    end
    return false
end

local resolve
local function prerequisites(goal, ctx, path, depth)
    for id, name in pairs(goal.preTitles or {}) do if type(name) == "string" then ctx.names[id] = name end end
    if goal.parent and not active(goal.parent) then
        local npc
        for _, records in ipairs(ctx.catalog[goal.parent] or {}) do
            for _, record in ipairs(records) do
                if action(record.goal) == "accept" then
                    npc = record.goal.npcName or record.goal.objName
                    if npc then break end
                end
            end
            if npc then break end
        end
        return nil, "Acepta primero " .. title(goal.parent, ctx.names[goal.parent])
            .. (npc and (" con " .. npc) or "") .. " y mantenla en tu diario."
    end
    local plan = emptyPlan()
    for _, value in ipairs(goal.preAll or {}) do
        local id = math.abs(value)
        if not delivered(id) then
            local dependency, reason = resolve(id, ctx, path, depth + 1)
            if not dependency then return nil, reason end
            if not merge(plan, dependency) then return nil, "La cadena supera el límite de recuperación." end
        end
    end
    local alternatives, satisfied = goal.pre or {}, false
    for _, value in ipairs(alternatives) do if delivered(math.abs(value)) then satisfied = true; break end end
    if #alternatives > 0 and not satisfied then
        local best, lastReason
        for _, value in ipairs(alternatives) do
            local dependency, reason = resolve(math.abs(value), ctx, path, depth + 1)
            if dependency then
                local candidate = emptyPlan()
                merge(candidate, plan)
                if merge(candidate, dependency) and (not best or candidate.cost < best.cost) then best = candidate end
            else lastReason = reason end
        end
        if not best then return nil, lastReason or "Ninguna misión previa alternativa tiene una ruta disponible." end
        plan = best
    end
    return plan
end

resolve = function(id, ctx, path, depth)
    if delivered(id) then return emptyPlan() end
    if depth > MAX_DEPTH or ctx.work >= MAX_WORK then return nil, "La cadena supera el límite de búsqueda; revísala manualmente." end
    if path[id] then return nil, "La cadena contiene un ciclo de requisitos en " .. title(id, ctx.names[id]) .. "." end
    if ctx.memo[id] then return ctx.memo[id] end
    ctx.work = ctx.work + 1
    local groups = ctx.catalog[id]
    if not groups then return nil, "No hay acciones de una guía compatible para " .. title(id, ctx.names[id]) .. ". Consulta su diario o instructor." end
    local nextPath = copy(path)
    nextPath[id] = true
    local best, lastReason
    for _, records in ipairs(groups) do
        local starts = {}
        for index, record in ipairs(records) do
            if action(record.goal) == "accept" then starts[#starts + 1] = index end
        end
        -- A quest already in the log can be recovered even if the compatible
        -- source has only its objectives and hand-in.
        if active(id) and #starts == 0 then starts[1] = 1 end
        for _, first in ipairs(starts) do
            local accept = action(records[first].goal) == "accept" and records[first].goal or nil
            local enoughLevel = not accept or not accept.minLevel or (UnitLevel("player") or 1) >= accept.minLevel
            local profession, professionReason = true, nil
            if accept and ns.CheckGoalProfession then
                profession, professionReason = ns:CheckGoalProfession(accept, records[first].step)
            end
            local finish
            for index = first, #records do
                if action(records[index].goal) == "turnin" then finish = index; break end
                if index > first and action(records[index].goal) == "accept" then break end
            end
            if profession ~= true then
                lastReason = professionReason or "La profesión requerida no está confirmada."
            elseif not enoughLevel then
                lastReason = "Requiere nivel " .. accept.minLevel .. " para " .. title(id, accept.title) .. "."
            elseif accept and not active(id) and closed(accept) then
                lastReason = "La rama de " .. title(id, accept.title) .. " está cerrada por otra misión activa o entregada."
            elseif not finish then
                lastReason = "La fuente de " .. title(id, accept and accept.title) .. " no incluye una entrega; no se puede reconstruir la cadena completa."
            else
                local plan, reason = emptyPlan()
                if accept and not active(id) then plan, reason = prerequisites(accept, ctx, nextPath, depth) end
                if plan then
                    local chosen, hasWork = {}, false
                    for index = first, finish do
                        local record = records[index]
                        local kind = action(record.goal)
                        if kind ~= "accept" and kind ~= "turnin" then hasWork = true end
                        if not (kind == "accept" and active(id)) and not (completed(id) and kind ~= "turnin") then
                            chosen[#chosen + 1] = record
                        end
                    end
                    if not hasWork and not completed(id) then
                        lastReason = "La fuente de " .. title(id, accept and accept.title) .. " no describe sus objetivos. Acéptala y consulta el diario; la entrega podrá recuperarse cuando el juego la marque completa."
                    else
                        plan.order[#plan.order + 1] = id
                        plan.quests[id] = { records = chosen, title = title(id, accept and accept.title) }
                        plan.cost = plan.cost + #chosen
                        if #plan.order <= MAX_QUESTS and (not best or plan.cost < best.cost) then best = plan end
                    end
                else lastReason = reason end
            end
        end
    end
    if best then ctx.memo[id] = best; return best end
    return nil, lastReason or ("No hay una aceptación y entrega compatibles para " .. title(id) .. ".")
end

-- Keep the author's ordering when several prerequisites share a route. Across
-- routes, prerequisites precede their dependants, with deterministic tie order.
local function compile(plan)
    local records, guideIDs = {}, {}
    for _, id in ipairs(plan.order) do
        for _, record in ipairs(plan.quests[id].records) do
            records[#records + 1] = record
            guideIDs[record.guideID] = true
        end
    end
    local guideCount = 0
    for _ in pairs(guideIDs) do guideCount = guideCount + 1 end
    if guideCount == 1 then
        local sourceOrder = {}
        for _, record in ipairs(records) do sourceOrder[#sourceOrder + 1] = record end
        table.sort(sourceOrder, function(a, b) return a.sequence < b.sequence end)
        local finished, causal = {}, true
        for _, record in ipairs(sourceOrder) do
            local goal, id = record.goal, questID(record.goal)
            if action(goal) == "accept" and not active(id) then
                for _, pre in ipairs(goal.preAll or {}) do
                    if not delivered(math.abs(pre)) and not finished[math.abs(pre)] then causal = false end
                end
                if goal.pre and #goal.pre > 0 then
                    local ready = false
                    for _, pre in ipairs(goal.pre) do
                        if delivered(math.abs(pre)) or finished[math.abs(pre)] then ready = true; break end
                    end
                    if not ready then causal = false end
                end
            elseif action(goal) == "turnin" then finished[id] = true end
        end
        -- A route cut can mention a prerequisite later than its dependent.
        -- Keep each quest's authored actions, but retain dependency order then.
        if causal then records = sourceOrder end
    end
    local steps = {}
    for _, record in ipairs(records) do
        local previous = steps[#steps]
        if not previous or previous.sourceGuideID ~= record.guideID or previous.sourceStep ~= record.stepIndex then
            previous = {
                title = record.step.title or plan.quests[questID(record.goal)].title,
                note = record.step.note or record.step.text,
                sourceGuideID = record.guideID, sourceStep = record.stepIndex, goals = {},
            }
            steps[#steps + 1] = previous
        end
        local goal = copy(record.goal)
        goal.optional = nil -- A selected prerequisite is required for this recovery.
        previous.goals[#previous.goals + 1] = goal
    end
    if #steps == 0 or #steps > MAX_STEPS then return nil, "La recuperación no tiene una secuencia de acciones utilizable." end
    return steps
end

local function makeEntry(goal, step, state, index, guide, ctx, reason)
    local id, kind = questID(goal), action(goal)
    local entry = { questID = id, title = title(id, goal.title), reason = reason,
        targetGuideID = guide.id, targetStep = state.cursor, goalIndex = index, missingQuestIDs = {} }
    if goal.minLevel and (UnitLevel("player") or 1) < goal.minLevel then
        entry.kind, entry.requiredLevel = "level", goal.minLevel
        entry.reason = "Necesitas nivel " .. goal.minLevel .. ". Continúa actividades o recorridos anteriores antes de aceptar esta misión."
        return entry
    end
    if ns.CheckGoalProfession then
        local eligible, professionReason = ns:CheckGoalProfession(goal, step)
        if eligible ~= true then
            entry.kind, entry.reason = "unresolved", professionReason
            return entry
        end
    end
    local plan, errorText
    if kind == "accept" then
        entry.kind = "prerequisite"
        if goal.parent and not active(goal.parent) then
            entry.missingQuestIDs[#entry.missingQuestIDs + 1] = goal.parent
        end
        for _, pre in ipairs(goal.preAll or {}) do
            if not delivered(math.abs(pre)) then entry.missingQuestIDs[#entry.missingQuestIDs + 1] = math.abs(pre) end
        end
        local ready = false
        for _, pre in ipairs(goal.pre or {}) do if delivered(math.abs(pre)) then ready = true; break end end
        if not ready then
            for _, pre in ipairs(goal.pre or {}) do entry.missingQuestIDs[#entry.missingQuestIDs + 1] = math.abs(pre) end
        end
        plan, errorText = prerequisites(goal, ctx, {}, 0)
    elseif id and kind == "turnin" and active(id) then
        entry.kind, entry.missingQuestIDs = "unfinished_quest", { id }
        plan, errorText = resolve(id, ctx, {}, 0)
    elseif id and not active(id) then
        entry.kind, entry.missingQuestIDs = "missing_quest", { id }
        plan, errorText = resolve(id, ctx, {}, 0)
    else
        entry.kind = "unresolved"
        errorText = reason or "Consulta el diario para resolver este requisito."
    end
    if plan and #plan.order > 0 then
        local steps
        steps, errorText = compile(plan)
        if steps then
            entry.plan = { steps = steps, requiredQuestIDs = copy(plan.order), cost = plan.cost }
            entry.requiredQuestIDs = copy(plan.order)
            local firstGoal = steps[1].goals[1]
            entry.action, entry.npcName = action(firstGoal), firstGoal.npcName or firstGoal.objName
            if ns.GetGoalWaypoint then entry.waypoint = read(ns.GetGoalWaypoint, ns, copy(firstGoal)) end
        end
    end
    if not entry.plan then
        entry.kind = entry.kind == "level" and entry.kind or "unresolved"
        entry.reason = errorText or reason or "No se puede reconstruir este requisito con las guías disponibles. Consulta el diario."
    end
    entry.missingQuestTitles = {}
    for _, missing in ipairs(entry.missingQuestIDs) do
        entry.missingQuestTitles[missing] = title(missing, (goal.preTitles or {})[missing] or ctx.names[missing])
    end
    return entry
end

function R:GetBlockers()
    local entries = {}
    if not (ns.char and ns.GetCurrent and ns.GetGoalStatus) then return entries end
    local guide, step, state = ns:GetCurrent()
    if not guide or not step or guide.recovery then return entries end
    local ctx
    for index, goal in ipairs(step.goals or { step }) do
        local status, reason = ns:GetGoalStatus(goal, step, state, index)
        if status == "blocked" then
            ctx = ctx or { catalog = catalog(), memo = {}, names = {}, work = 0 }
            entries[#entries + 1] = makeEntry(goal, step, state, index, guide, ctx, reason)
        end
    end
    return entries
end

local function removeTemporary()
    local guide = ns.guides[TEMP_ID]
    if not (guide and guide.recovery) then return end
    ns.guides[TEMP_ID] = nil
    for index = #ns.order, 1, -1 do if ns.order[index] == TEMP_ID then table.remove(ns.order, index) end end
    if ns.char and ns.char.progress then ns.char.progress[TEMP_ID] = nil end
end

local function validSaved(saved)
    if type(saved.bookmark) ~= "table" or type(saved.bookmark.guideID) ~= "string"
        or type(saved.requiredQuestIDs) ~= "table" or #saved.requiredQuestIDs == 0 or #saved.requiredQuestIDs > MAX_QUESTS
        or type(saved.guide) ~= "table" or type(saved.guide.steps) ~= "table"
        or #saved.guide.steps == 0 or #saved.guide.steps > MAX_STEPS then return false end
    for _, id in ipairs(saved.requiredQuestIDs) do if type(id) ~= "number" or id <= 0 then return false end end
    for _, step in ipairs(saved.guide.steps) do
        if type(step) ~= "table" or type(step.title) ~= "string" or type(step.goals) ~= "table"
            or #step.goals == 0 or #step.goals > 128 then return false end
        for _, goal in ipairs(step.goals) do
            if type(goal) ~= "table" or type(action(goal)) ~= "string" or not questID(goal) then return false end
        end
    end
    return true
end

function R:RestoreSaved()
    local saved = ns.char and ns.char.recovery
    if type(saved) ~= "table" or not saved.active then return false end
    if not validSaved(saved) then
        saved.reason, saved.status = "El marcador guardado no tiene una guía de recuperación válida.", "unresolved"
        return false
    end
    local existing = ns.guides[TEMP_ID]
    if existing and not existing.recovery then saved.reason = "El identificador de recuperación está ocupado."; return false end
    if not existing then
        local guide = copy(saved.guide)
        guide.id, guide.recovery, guide.temporary = TEMP_ID, true, true
        local ok, err = ns:RegisterGuide(guide)
        if not ok then saved.reason, saved.status = err, "unresolved"; return false end
    end
    return true
end

function R:Start(indexOrQuest)
    if not ns.char then return false, "El personaje todavía no se ha inicializado." end
    if type(ns.char.recovery) == "table" and ns.char.recovery.active then return false, "Ya hay una recuperación en curso. Reanúdala o vuelve a la guía original." end
    local entries = self:GetBlockers()
    local wanted = tonumber(indexOrQuest) or 1
    local entry = entries[wanted]
    if not entry then for _, candidate in ipairs(entries) do if candidate.questID == wanted then entry = candidate; break end end end
    if not entry then return false, "Este requisito ya no bloquea el paso actual. Actualiza la lista." end
    if not entry.plan then return false, entry.reason end
    if ns.guides[TEMP_ID] and not ns.guides[TEMP_ID].recovery then return false, "El identificador de recuperación está ocupado." end
    local guide, _, state = ns:GetCurrent()
    local temporary = { id = TEMP_ID, title = "Recuperación: " .. entry.title, kind = "Recuperación", status = "recovery",
        recovery = true, temporary = true, steps = copy(entry.plan.steps),
        summary = "Misiones previas de las guías incluidas. Al entregarlas volverás al punto guardado." }
    ns.char.recovery = {
        version = 1, active = true, status = "active", guide = copy(temporary),
        bookmark = { guideID = guide.id, cursor = state.cursor, review = state.review },
        requestedQuestID = entry.questID, requiredQuestIDs = copy(entry.plan.requiredQuestIDs),
    }
    removeTemporary()
    local ok, err = ns:RegisterGuide(temporary)
    if not ok then ns.char.recovery = nil; return false, err end
    ns.char.progress[TEMP_ID] = { cursor = 1, confirmed = {}, skipped = {} }
    ns.char.activeGuide = TEMP_ID
    ns:Sync()
    return true, self:GetStatus()
end

-- Tracker rows identify the local goal, not a quest number that could also
-- be interpreted as an index into a changed blocker list.
function R:StartForGoal(goalIndex)
    for index, entry in ipairs(self:GetBlockers()) do
        if entry.goalIndex == goalIndex then return self:Start(index) end
    end
    return false, "Este objetivo ya no tiene un requisito pendiente."
end

local function remaining(saved)
    local ids = {}
    for _, id in ipairs(type(saved.requiredQuestIDs) == "table" and saved.requiredQuestIDs or {}) do
        if type(id) == "number" and id > 0 and not delivered(id) then ids[#ids + 1] = id end
    end
    return ids
end

local function restoreBookmark(saved, status)
    local bookmark = saved.bookmark
    if not (bookmark and ns.guides[bookmark.guideID]) then
        saved.status, saved.reason = "unresolved", "La guía original ya no está disponible; se conserva tu marcador."
        return false, saved.reason
    end
    ns.char.activeGuide = bookmark.guideID
    local state = ns:GetProgress(bookmark.guideID)
    state.cursor = math.max(1, math.min(tonumber(bookmark.cursor) or 1, #ns.guides[bookmark.guideID].steps + 1))
    state.review = bookmark.review
    -- Do not replace progress tables: confirmations and explicit skips on the
    -- original route remain exactly where the player left them.
    ns.char.recovery = nil
    removeTemporary()
    R.lastStatus = { active = false, status = status, bookmark = copy(bookmark) }
    ns:Sync()
    return true, R.lastStatus
end

function R:Cancel()
    local saved = ns.char and ns.char.recovery
    if type(saved) ~= "table" or not saved.active then return false, "No hay una recuperación en curso." end
    return restoreBookmark(saved, "cancelled")
end

function R:Resume()
    local saved = ns.char and ns.char.recovery
    if type(saved) ~= "table" or not saved.active then return false, "No hay una recuperación en curso." end
    if not validSaved(saved) then return false, saved.reason or "La recuperación guardada está incompleta; vuelve a tu guía original." end
    local missing = remaining(saved)
    if #missing == 0 and #(saved.requiredQuestIDs or {}) > 0 then return restoreBookmark(saved, "completed") end
    if ns.char.activeGuide ~= TEMP_ID and ns.guides[TEMP_ID] then
        ns.char.activeGuide = TEMP_ID
        ns:Sync()
        return true, self:GetStatus()
    end
    saved.status = "active"
    local guide = ns.guides[TEMP_ID]
    local state = guide and ns:GetProgress(TEMP_ID)
    if state and state.cursor > #guide.steps then
        saved.status = "incomplete"
        saved.reason = "Todavía faltan entregas reales. Omitir los pasos no resuelve la cadena; revisa la recuperación o vuelve a tu guía original."
    end
    return false, saved.reason or "Completa y entrega las misiones indicadas antes de reanudar la ruta original."
end

function R:GetStatus()
    local saved = ns.char and ns.char.recovery
    if type(saved) ~= "table" or not saved.active then return self.lastStatus or { active = false, status = "idle" } end
    local missing = remaining(saved)
    return { active = true, status = saved.status or "active", reason = saved.reason,
        title = type(saved.guide) == "table" and saved.guide.title or nil,
        bookmark = type(saved.bookmark) == "table" and copy(saved.bookmark) or nil,
        requiredQuestIDs = copy(saved.requiredQuestIDs), remainingQuestIDs = missing,
        canResume = validSaved(saved) and #missing == 0,
        guideID = TEMP_ID, paused = ns.char.activeGuide ~= TEMP_ID }
end

function R:GetNavigationOverride()
    -- The selected temporary guide already uses the normal navigation engine.
    return nil
end

function R:GetReport()
    local status = self:GetStatus()
    if status.active then
        return status.reason or ((status.paused and "Recuperación en pausa: " or "Recuperación en curso: ")
            .. tostring(#(status.remainingQuestIDs or {})) .. " misión(es) previa(s) por entregar. "
            .. "Tu posición en la guía original sigue guardada.")
    end
    local blockers, lines = self:GetBlockers(), {}
    for index, entry in ipairs(blockers) do
        if index > 3 then break end
        lines[#lines + 1] = entry.title .. ": " .. (entry.reason or "Consulta el requisito de la misión.")
    end
    return #lines > 0 and table.concat(lines, "\n") or "No hay requisitos bloqueados en el paso actual."
end

function R:Initialize()
    self:RestoreSaved()
    if not self.hooked and type(ns.Sync) == "function" then
        self.hooked = true
        local sync = ns.Sync
        ns.Sync = function(self, ...)
            sync(self, ...)
            if not R.restoring then
                local saved = ns.char and ns.char.recovery
                if type(saved) == "table" and saved.active and ns.char.activeGuide == TEMP_ID then
                    R.restoring = true
                    R:Resume()
                    R.restoring = nil
                end
            end
        end
    end
    if ns.char and ns.char.activeGuide == TEMP_ID then self:Resume() end
end
