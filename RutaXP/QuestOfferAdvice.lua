local _, ns = ...

local ELWYNN = "forever/alliance/human/01-elwynn-forest"
local WESTFALL = "forever/alliance/02-westfall"
local humanRogue = {classes = {"ROGUE"}, races = {"Human"}}
local questRowsByGuide = setmetatable({}, {__mode = "k"})

-- Index chapters as needed, including temporary recovery guides and the
-- old one-action-per-step format. Player conditions are evaluated on lookup.
local function rowsFor(guide, questID)
    local rows = questRowsByGuide[guide]
    if not rows then
        rows = {}
        for si, step in ipairs(guide.steps) do
            for gi, goal in ipairs(step.goals or {step}) do
                local id = goal.quest or goal.questID
                if id then
                    rows[id] = rows[id] or {}
                    table.insert(rows[id], {s = si, g = gi, step = step, goal = goal})
                end
            end
        end
        questRowsByGuide[guide] = rows
    end
    return rows[questID]
end

local function applies(self, value)
    if value.faction and value.faction ~= UnitFactionGroup("player") then return false end
    if value.classes or value.races or value.factions then
        if not self:MatchesConditions(value) then return false end
    end
    return self:MatchesConditions(value.only)
end

local function currentAdvice(self, row, state)
    local status, reason = self:GetGoalStatus(row.goal, row.step, state, row.g)
    if status == "blocked" then return reason, "estado" end
    if status == "skip" and reason ~= "Opcional desactivado" then return reason, "estado" end
    if status == "done" then return reason, "estado" end
    if row.goal.optional then return "Opcional en este paso.", "opcional" end
    return "Acéptala ahora para seguir este paso.", "ahora"
end

local function visitPaused(self, state)
    if self.GetGuideTravel and self:GetGuideTravel() then return "Estás de viaje entre capítulos." end
    if state.review then return "Estás revisando un paso anterior." end
    if self.DuoAuto and self.DuoAuto.agreement then
        local view = self.DuoAuto:GetSharedView()
        if view and view.following then return "Estás acompañando a tu compañero." end
    end
end

local function needsQuest(self, goal, id)
    if goal.parent == id then return true end
    for _, pre in ipairs(goal.preAll or {}) do if math.abs(pre) == id then return true end end
    local oneOf = false
    for _, pre in ipairs(goal.pre or {}) do
        if self:IsQuestDelivered(math.abs(pre)) then return false end
        if math.abs(pre) == id then oneOf = true end
    end
    return oneOf
end

local function validQuest(id)
    return not (issecretvalue and issecretvalue(id)) and type(id) == "number"
        and id > 0 and id < math.huge and id == math.floor(id)
end

local function plannedAcceptance(self, guide, questID, firstStep, saved, requireActive)
    local found = false
    for _, row in ipairs(rowsFor(guide, questID) or {}) do
        if (row.goal.t or row.goal.action) == "accept" and applies(self, row.step) and applies(self, row.goal) then
            found = true
            if row.s >= firstStep then
                local rowState = {cursor = row.s, skipped = saved and saved.skipped, confirmed = saved and saved.confirmed}
                if not requireActive or self:GetGoalStatus(row.goal, row.step, rowState, row.g) == "active" then
                    return row, true
                end
            end
        end
    end
    return nil, found
end

-- Query only the active route and its single compatible successor. A local
-- cursor gives the quest engine the target row when checking a different
-- chapter, without changing activeGuide or initializing the successor's save.
local function plannedOffer(self, guide, state, id, requireActive)
    local row, found = plannedAcceptance(self, guide, id, state.cursor + 1, state, requireActive)
    if found then return row, guide end
    local successor = self:GetLinkedGuide(guide)
    if not successor or not applies(self, successor) then return end
    local saved = self.char.progress[successor.id]
    if saved and (saved.review or type(saved.cursor) ~= "number") then return end
    row = plannedAcceptance(self, successor, id, saved and saved.cursor or 1, saved, requireActive)
    return row, successor
end

local function earlyEnabled(self, guide, state)
    if not guide.steps[state.cursor] or visitPaused(self, state) then return false end
    if self:ShouldWaitForEarlyQuest(guide.steps[state.cursor]) then return false end
    return self.GetEarlyQuestSpace and self:GetEarlyQuestSpace() == true
end

local function arrivalOffer(self, id, trip, guide, cursor)
    if guide.id ~= trip.destination and (guide.id ~= trip.source or cursor <= #guide.steps) then return end
    local target = self.guides[trip.destination]
    if trip.waiting or not target or not applies(self, target) or not trip.arrivalMap
        or self.TravelRouting.OnTaxi() or self.TravelRouting.Zone() ~= trip.arrivalMap then return end
    local saved = self.char.progress[target.id]
    if saved and (saved.review or saved.cursor ~= 1) then return end
    local row = plannedAcceptance(self, target, id, 1, saved, true)
    if not row or row.goal.map ~= trip.arrivalMap or not row.goal.npc or row.goal.npc ~= self:GetQuestContactNPC() then return end
    -- While travelling, the shared travel checkpoint owns the wait. The
    -- destination's first quest step has not started for either player yet.
    if self.DuoAuto and self.DuoAuto:ShouldPauseAutomation() then return end
    if self:GetEarlyQuestSpace() then return "Cógela de camino. La harás en " .. target.title .. ".", "ahora" end
end

local function booksAdvice(self)
    if self:MatchesConditions(humanRogue) then
        return "Opcional · Lleva los dos libros de Jaspe a Paxton para elegir una daga.", "opcional"
    end
    return "Opcional · Lleva los dos libros de Jaspe a Paxton en Villanorte.", "opcional"
end

-- Advice only for a profitable, usable offer whose place in the route is
-- established. The caller still owns all NPC and journal actions.
local function earlyOffer(self, id)
    if not validQuest(id) then return nil end
    if id ~= 91777 and not (self.earlyQuestOffers and self.earlyQuestOffers[id] == true) then return nil end
    local char = self.char
    local guide = char and self.guides[char.activeGuide]
    local state = guide and char.progress and char.progress[guide.id]
    if not state or type(state.cursor) ~= "number" or state.review or guide.temporary or guide.recovery or not applies(self, guide)
        or self:IsQuestActive(id) or self:IsQuestDelivered(id) then return nil end
    local trip = self.GetGuideTravel and self:GetGuideTravel()
    if id == 91777 then
        if guide.id == ELWYNN and char.optional and IsInGroup and IsInGroup() == true and self:IsQuestDelivered(91775)
            and earlyEnabled(self, guide, state) then return booksAdvice(self) end
        return nil
    end
    if trip then return arrivalOffer(self, id, trip, guide, state.cursor) end
    local row, target = plannedOffer(self, guide, state, id, true)
    if not row or not earlyEnabled(self, guide, state) then return nil end
    if target == guide then return "Puedes cogerla ahora para el paso " .. row.s .. ".", "ahora" end
    if id == 109 and target.id == WESTFALL then return "Cógela para entregarla al llegar a Gryan en Páramos de Poniente.", "ahora" end
    return "Puedes cogerla ahora para " .. target.title .. ".", "ahora"
end

function ns:GetEarlyQuestOffer(id)
    if self.char and self.char.auto == true then return earlyOffer(self, id) end
end

function ns:GetQuestOfferAdvice(questID)
    if not validQuest(questID) then return nil end
    if self:IsQuestActive(questID) then return "Ya la tienes en el diario.", "estado" end
    local char = self.char
    local guide = char and self.guides[char.activeGuide]
    if not guide then return "Selecciona una guía para ver cuándo aceptarla.", "estado" end
    if not applies(self, guide) then return "El capítulo activo es para otro personaje.", "estado" end
    if guide.id == ELWYNN and questID == 91777 then
        return booksAdvice(self)
    end
    if self:IsQuestDelivered(questID) then return "Ya la has entregado.", "estado" end
    -- GetProgress (also used by GetCurrent) may initialize, migrate or clamp a save.
    local state = char.progress and char.progress[guide.id]
    local cursor = state and state.cursor
    if type(cursor) ~= "number" or cursor < 1 then return "La guía está cargando tu progreso.", "estado" end
    local early, kind = earlyOffer(self, questID)
    if early and self.GetGuideTravel and self:GetGuideTravel() then return early, kind end
    local step = guide.steps[cursor]
    if step and applies(self, step) then
        for gi, goal in ipairs(step.goals or {step}) do
            if (goal.t or goal.action) == "accept" and applies(self, goal) and needsQuest(self, goal, questID)
                and self:GetGoalStatus(goal, step, state, gi) == "blocked" then
                local pause = visitPaused(self, state)
                if pause then return "Esta misión es una previa del paso " .. cursor .. ".", "estado" end
                return "Acéptala para desbloquear el paso " .. cursor .. ".", "ahora"
            end
        end
    end
    local rows = rowsFor(guide, questID)
    local later, earlier, omitted, uses
    for _, row in ipairs(rows or {}) do
        if applies(self, row.step) and applies(self, row.goal) then
            if (row.goal.t or row.goal.action) == "accept" then
                if row.s == cursor then
                    local text, kind = currentAdvice(self, row, state)
                    if kind == "ahora" then
                        local pause = visitPaused(self, state)
                        if pause then return pause, "estado" end
                    end
                    return text, kind
                end
                local key = row.s .. ":" .. row.g
                if (state.skipped and state.skipped[key]) or (state.confirmed and state.confirmed[key]) then
                    omitted = row
                elseif row.s > cursor then
                    later = later or row
                else
                    earlier = row
                end
            elseif row.s >= cursor then
                uses = uses or row
            end
        end
    end
    if early then return early, kind end
    if later then
        if later.goal.optional then return "Opcional en el paso " .. later.s .. ".", "opcional" end
        return "Espera al paso " .. later.s .. " para aceptarla.", "después"
    end
    if omitted then return "La omitiste en el paso " .. omitted.s .. ".", "estado" end
    if earlier then return "Acéptala si quieres retomar el paso " .. earlier.s .. ".", "estado" end
    if uses then return "La guía cuenta con esta misión en el paso " .. uses.s .. ".", "estado" end
    if self.earlyQuestOffers and self.earlyQuestOffers[questID] then
        local row, nextGuide = plannedOffer(self, guide, state, questID)
        if row and nextGuide ~= guide then return "La guía la recoge en " .. nextGuide.title .. " (paso " .. row.s .. ").", "después" end
    end
    return "Fuera de este capítulo. Puedes seguir sin aceptarla.", "fuera"
end
