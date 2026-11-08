local _, ns = ...

local ELWYNN = "forever/alliance/human/01-elwynn-forest"
local humanRogue = {classes = {"ROGUE"}, races = {"Human"}}
local indexedGuide, questRows

-- Index only the open chapter, including temporary recovery guides and the
-- old one-action-per-step format. Player conditions are evaluated on lookup.
local function rowsFor(guide, questID)
    if guide ~= indexedGuide then
        local rows = {}
        for si, step in ipairs(guide.steps) do
            for gi, goal in ipairs(step.goals or {step}) do
                local id = goal.quest or goal.questID
                if id then
                    rows[id] = rows[id] or {}
                    table.insert(rows[id], {s = si, g = gi, step = step, goal = goal})
                end
            end
        end
        indexedGuide, questRows = guide, rows
    end
    return questRows[questID]
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

function ns:GetQuestOfferAdvice(questID)
    if (issecretvalue and issecretvalue(questID)) or type(questID) ~= "number" or questID <= 0
        or questID ~= math.floor(questID) or questID == math.huge then return nil end
    if self:IsQuestActive(questID) then return "Ya la tienes en el diario.", "estado" end
    local char = self.char
    local guide = char and self.guides[char.activeGuide]
    if not guide then return "Selecciona una guía para ver cuándo aceptarla.", "estado" end
    if not applies(self, guide) then return "El capítulo activo es para otro personaje.", "estado" end
    if guide.id == ELWYNN and questID == 91777 then
        if self:MatchesConditions(humanRogue) then
            return "Opcional · Lleva los dos libros de Jaspe a Paxton para elegir una daga.", "opcional"
        end
        return "Opcional · Lleva los dos libros de Jaspe a Paxton en Villanorte.", "opcional"
    end
    if self:IsQuestDelivered(questID) then return "Ya la has entregado.", "estado" end
    -- GetProgress (also used by GetCurrent) may initialize, migrate or clamp a save.
    local state = char.progress and char.progress[guide.id]
    local cursor = state and state.cursor
    if type(cursor) ~= "number" or cursor < 1 then return "La guía está cargando tu progreso.", "estado" end
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
    if later then
        if later.goal.optional then return "Opcional en el paso " .. later.s .. ".", "opcional" end
        return "Espera al paso " .. later.s .. " para aceptarla.", "después"
    end
    if omitted then return "La omitiste en el paso " .. omitted.s .. ".", "estado" end
    if earlier then return "Acéptala si quieres retomar el paso " .. earlier.s .. ".", "estado" end
    if uses then return "La guía cuenta con esta misión en el paso " .. uses.s .. ".", "estado" end
    return "Fuera de este capítulo. Puedes seguir sin aceptarla.", "fuera"
end
