local _, ns = ...

-- Grouped routes retain the author's objectives and their ordering. A visit
-- does not finish until every applicable, required objective is satisfied.
local basicComplete, basicSync = ns.IsStepComplete, ns.Sync
local basicNext, basicObjectives = ns.Next, ns.GetObjectives
local basicSelect = ns.SelectGuide

local function read(api, ...)
    if type(api) ~= "function" then return nil end
    local ok, a, b, c, d, e, f, g, h = pcall(api, ...)
    if not ok then return nil end
    local function readable(value)
        if issecretvalue and issecretvalue(value) then return nil end
        return value
    end
    return readable(a), readable(b), readable(c), readable(d), readable(e), readable(f), readable(g), readable(h)
end

local function token(value)
    value = tostring(value or ""):lower():gsub("[%s_%-]", "")
    if value == "undead" then return "scourge" end
    if value:find("skyborne", 1, true) then return "skyborne" end
    return value
end

local function matches(values, actual)
    if not values or #values == 0 then return true end
    local included, found = false, false
    for _, value in ipairs(values) do
        if value:sub(1, 1) == "!" then
            if token(value:sub(2)) == actual then return false end
        else
            included = true
            if token(value) == actual then found = true end
        end
    end
    return not included or found
end

function ns:MatchesConditions(only)
    if not only then return true end
    local _, class = UnitClass("player")
    local _, race = UnitRace("player")
    return matches(only.classes, token(class)) and matches(only.races, token(race))
        and matches(only.factions, token(UnitFactionGroup("player")))
end

function ns:IsQuestDelivered(id)
    return self.turnedIn[id] or read(C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted, id)
        or read(IsQuestFlaggedCompleted, id) or false
end

function ns:IsQuestActive(id)
    return read(C_QuestLog and C_QuestLog.IsOnQuest, id) == true
end

local function itemCount(id)
    return read(C_Item and C_Item.GetItemCount, id, false) or read(GetItemCount, id, false) or 0
end

local function confirmationKey(state, index, stepIndex)
    return tostring(stepIndex or (state and state.cursor) or 1) .. ":" .. tostring(index)
end

local function hasOnlyNotes(self, step)
    if not step or not step.goals then return false end
    for _, item in ipairs(step.goals) do
        local kind = item.t or item.action
        if kind ~= "note" and self:MatchesConditions(item.only) then return false end
    end
    return true
end

-- Classic / Forever trivial (grey) quest threshold
local function isQuestTrivial(qlvl, playerLevel)
    qlvl = tonumber(qlvl)
    playerLevel = tonumber(playerLevel) or 1
    if not qlvl or playerLevel <= 1 then return false end
    local diff
    if playerLevel <= 5 then diff = 0
    elseif playerLevel <= 39 then diff = playerLevel - math.floor(playerLevel / 10) - 5
    elseif playerLevel <= 59 then diff = playerLevel - math.floor(playerLevel / 5) - 1
    else diff = playerLevel - 9 end
    return qlvl <= diff
end

-- Build a per-guide layout cache: where each quest is accepted and what quests
-- are prerequisites for non-trivial quests later in the guide.
local guideCache = setmetatable({}, { __mode = "k" })
local function getGuideLayout(self, guide)
    if not guide or not guide.steps then return nil end
    local cached = guideCache[guide]
    if cached then return cached end
    cached = { stepOf = {}, accepts = {}, preOf = {} }
    for s, step in ipairs(guide.steps) do
        cached.stepOf[step] = s
        for g, goal in ipairs(step.goals or {}) do
            local q = goal.quest or goal.questID
            if q and (goal.t or goal.action) == "accept" then
                cached.accepts[q] = cached.accepts[q] or {}
                table.insert(cached.accepts[q], { s = s, g = g, step = step, goal = goal })
                for _, pre in ipairs(goal.pre or {}) do
                    cached.preOf[math.abs(pre)] = cached.preOf[math.abs(pre)] or {}
                    table.insert(cached.preOf[math.abs(pre)], q)
                end
                for _, pre in ipairs(goal.preAll or {}) do
                    cached.preOf[math.abs(pre)] = cached.preOf[math.abs(pre)] or {}
                    table.insert(cached.preOf[math.abs(pre)], q)
                end
            end
        end
    end
    guideCache[guide] = cached
    return cached
end

local function isNeededForHigherQuest(self, _, questID)
    if not questID then return false end
    -- A prerequisite in another zone/class guide still matters. Preserve
    -- every known required follow-up, even when it is grey as well.
    for _, route in pairs(self.guides) do
        if not route.faction or route.faction == UnitFactionGroup("player") then
            local layout = getGuideLayout(self, route)
            for _, followUp in ipairs(layout and layout.preOf[questID] or {}) do
                for _, entry in ipairs(layout.accepts[followUp] or {}) do
                    if not entry.goal.optional and self:MatchesConditions(entry.step.only)
                        and self:MatchesConditions(entry.goal.only) then return true end
                end
            end
        end
    end
    return false
end

local function wasRequiredEarlier(self, layout, id, stepIndex)
    for _, entry in ipairs(layout and layout.accepts[id] or {}) do
        if entry.s <= stepIndex and not entry.goal.optional and self:MatchesConditions(entry.step.only)
            and self:MatchesConditions(entry.goal.only) then return true end
    end
    return false
end

local function isClosedBranch(self, goal)
    for _, alternative in ipairs(goal and goal.closedBy or {}) do
        if self:IsQuestActive(alternative) or self:IsQuestDelivered(alternative) then return true end
    end
    return false
end

local function earlierAccept(self, layout, id, stepIndex, goalIndex)
    local found
    for _, entry in ipairs(layout and layout.accepts[id] or {}) do
        if (entry.s < stepIndex or entry.s == stepIndex and entry.g <= (goalIndex or 1))
            and self:MatchesConditions(entry.step.only) and self:MatchesConditions(entry.goal.only) then
            found = entry.goal
        end
    end
    return found
end

local function isAbsentCarriedQuest(self, goal, step, id)
    if not step or not step.goals then return false end
    local inStep = false
    for _, item in ipairs(step.goals) do
        if item == goal then inStep = true end
        if (item.t or item.action) == "accept" and (item.quest or item.questID) == id
            and self:MatchesConditions(item.only) then
            return false
        end
    end
    return inStep
end

local function matchedCandidate(self, goal)
    if goal and goal.candidates and self.GetGoalWaypoint then
        local point = read(self.GetGoalWaypoint, self, goal)
        if point and point.candidate then return point.candidate end
    end
    local faction = read(UnitFactionGroup, "player")
    local code = faction == "Alliance" and "A" or faction == "Horde" and "H" or nil
    for _, candidate in ipairs(goal and goal.candidates or {}) do
        local factionOk = not candidate.faction or candidate.faction == "AH" or candidate.faction == code
        if factionOk and self:MatchesConditions({ races = candidate.races, classes = candidate.classes }) then
            return candidate
        end
    end
end

function ns:GetGoalStatus(goal, step, state, index)
    if not self:MatchesConditions(step and step.only) or not self:MatchesConditions(goal.only) then return "skip", "Otro personaje" end
    local guide = self.char and self.guides[self.char.activeGuide]
    local layout = guide and getGuideLayout(self, guide)
    local stepIndex = (layout and step and layout.stepOf[step]) or (state and state.cursor) or 1
    local action, id = goal.t or goal.action, goal.quest or goal.questID
    if id and self:IsQuestDelivered(id) then return "done", "Misión entregada" end
    local key = confirmationKey(state, index, stepIndex)
    if state and state.skipped and state.skipped[key] then return "skip", "Omitido manualmente" end
    if state and state.confirmed and state.confirmed[key] then
        -- Older versions stored skipped quest goals as confirmations. Keep
        -- their navigation effect without claiming that a quest was done.
        if id then return "skip", "Omitido manualmente (versión anterior)" end
        return "done", "Confirmado manualmente"
    end
    if action == "note" then
        if hasOnlyNotes(self, step) then return "manual", "Confirma tras leer la nota" end
        return "skip", "Información"
    end
    local onQuest = id and self:IsQuestActive(id)
    -- A branch excluded at acceptance also excludes its later work/delivery.
    -- An actual quest in the log remains actionable, even if another branch exists.
    if not onQuest and (isClosedBranch(self, goal) or (id and action ~= "accept"
        and isClosedBranch(self, earlierAccept(self, layout, id, stepIndex, index)))) then
        return "skip", "Rama alternativa ya elegida"
    end
    if goal.optional and not (self.char and self.char.optional) and not onQuest then return "skip", "Opcional desactivado" end
    local playerLevel = UnitLevel("player") or 1
    if action == "accept" then
        if onQuest then return "done", "Aceptada" end
        -- Grey is an XP classification, not proof that a quest/reward is
        -- expendable. This policy is off by default and protects known
        -- cross-guide chains and class-specific objectives when enabled.
        if self.char and self.char.skipTrivial == true and id and goal.qlvl
            and not goal.class
            and not (goal.only and goal.only.classes and #goal.only.classes > 0)
            and not (step and step.only and step.only.classes and #step.only.classes > 0)
            and not goal.important and not goal.reward and not goal.rewardItem
            and isQuestTrivial(goal.qlvl, playerLevel) and not isNeededForHigherQuest(self, guide, id) then
            return "skip", "Omitida por tu opción de misiones grises"
        end
        if goal.minLevel and playerLevel < goal.minLevel then
            return "blocked", "Requiere nivel " .. goal.minLevel
        end
        for _, pre in ipairs(goal.preAll or {}) do
            if not self:IsQuestDelivered(math.abs(pre)) then return "blocked", "Primero entrega la misión previa" end
        end
        if goal.pre and #goal.pre > 0 then
            local ready = false
            for _, pre in ipairs(goal.pre) do if self:IsQuestDelivered(math.abs(pre)) then ready = true; break end end
            if not ready then return "blocked", "Falta una misión previa de esta cadena" end
        end
        return "active", "Acepta la misión"
    end
    if id then
        -- Carried quests can be absent on an alternative starting route.
        -- An abandoned/omitted quest must not be falsely marked delivered.
        if not onQuest and isAbsentCarriedQuest(self, goal, step, id) then
            if wasRequiredEarlier(self, layout, id, stepIndex) then
                return "blocked", "La misión requerida no está en tu diario; vuelve a aceptarla o revisa el paso anterior"
            end
            return "skip", "La misión no está en tu diario"
        end
        if action == "turnin" then return "active", "Entrega la misión al NPC" end
        if read(C_QuestLog and C_QuestLog.IsComplete, id) == true then return "done", "Objetivos completados" end
        local oi = goal.oi or goal.objective
        if oi then
            local objectives = read(C_QuestLog and C_QuestLog.GetQuestObjectives, id)
            if objectives and objectives[oi] and objectives[oi].finished then return "done", "Objetivo completado" end
        elseif action == "collect" and goal.item and goal.count and itemCount(goal.item) >= goal.count then
            return "done", "Objetos reunidos"
        end
        return "active", "Completa el objetivo de la misión"
    end
    if action == "level" then
        if playerLevel >= (goal.level or goal.n or 1000) then return "done", "Nivel alcanzado" end
        return "active", "Alcanza el nivel indicado antes de continuar"
    elseif action == "collect" or action == "buy" then
        if goal.item and itemCount(goal.item) >= (goal.count or 1) then return "done", "Objetos en la mochila" end
        return "active", "Consigue los objetos indicados"
    elseif action == "goto" then
        if self.IsAtWaypoint and self:IsAtWaypoint(goal) then return "done", "Has llegado" end
        return "active", "Llega al destino de la flecha"
    end
    return "manual", "Confirma al terminar esta acción"
end

function ns:GetActiveGoal(step, state)
    if not step then
        _, step, state = self:GetCurrent()
    elseif not state and self.char then
        local _, currentStep, currentState = self:GetCurrent()
        if currentStep == step then state = currentState end
    end
    if not step then return nil end
    if not step.goals then return step, 1, "active" end
    for index, goal in ipairs(step.goals) do
        local status, reason = self:GetGoalStatus(goal, step, state, index)
        if status ~= "done" and status ~= "skip" then return goal, index, status, reason end
    end
end

function ns:IsStepComplete(step, stateOverride)
    if not step or not step.goals then return basicComplete(self, step) end
    local _, _, state = self:GetCurrent()
    state = stateOverride or state
    if not self:MatchesConditions(step.only) then return true end
    local hasOpenNonService = false
    local hasOpenService = false
    local questGoalsCount = 0
    local skippedQuestGoals = 0
    for index, goal in ipairs(step.goals) do
        local status = self:GetGoalStatus(goal, step, state, index)
        local q = goal.quest or goal.questID
        if q and self:MatchesConditions(goal.only) then
            questGoalsCount = questGoalsCount + 1
            if status == "skip" then skippedQuestGoals = skippedQuestGoals + 1 end
        end
        if status ~= "done" and status ~= "skip" then
            if q or goal.t == "level" then
                hasOpenNonService = true
            else
                hasOpenService = true
            end
        end
    end
    if hasOpenNonService then return false end
    if hasOpenService then
        -- If this step had quest goals and every single quest in it was skipped
        -- (e.g. outleveled grey quests or absent carried quests), do not stop for
        -- an auxiliary train/sethome/goto attached to those skipped quests.
        if questGoalsCount > 0 and skippedQuestGoals == questGoalsCount then
            return true
        end
        return false
    end
    return true
end

-- Only a resolved prefix proves that a route can advance. An unrelated quest
-- delivered later in the route says nothing about unfinished earlier chains.
function ns:PlaceInGuide(guide, state)
    if not guide or not state or state.review or not (self.char and self.char.auto) then return end
    if guide.status ~= "beta" or #guide.steps < 5 then return end
    while guide.steps[state.cursor] and self:IsStepComplete(guide.steps[state.cursor], state) do
        state.cursor = state.cursor + 1
    end
end

function ns:Sync()
    local guide, _, state = self:GetCurrent()
    if guide and state and not state.placed and not state.review and self.char and self.char.auto then
        state.placed = true
        self:PlaceInGuide(guide, state)
    end
    basicSync(self)
    if self.UpdateNavigation then self:UpdateNavigation() end
end

function ns:Next()
    local _, step, state = self:GetCurrent()
    if not step or not step.goals or state.review then return basicNext(self) end
    local goal, index, status = self:GetActiveGoal()
    if goal then
        local field = status == "manual" and not (goal.quest or goal.questID) and "confirmed" or "skipped"
        state[field] = state[field] or {}
        state[field][confirmationKey(state, index)] = true
    end
    -- A manual confirmation is also useful with automatic advancement off.
    if self:IsStepComplete(step) then state.cursor = state.cursor + 1 end
    self:Sync()
end

-- Toggle or skip a specific goal row by clicking on it in the tracker
function ns:ToggleGoalConfirm(index)
    local _, step, state = self:GetCurrent()
    if not step or not step.goals or not index or not step.goals[index] then return end
    local key = confirmationKey(state, index)
    local goal = step.goals[index]
    state.confirmed = state.confirmed or {}
    state.skipped = state.skipped or {}
    if state.confirmed[key] or state.skipped[key] then
        state.confirmed[key] = nil
        state.skipped[key] = nil
    else
        local status = self:GetGoalStatus(goal, step, state, index)
        if status == "done" or status == "skip" then return end
        local field = status == "manual" and not (goal.quest or goal.questID) and "confirmed" or "skipped"
        state[field][key] = true
    end
    state.review = nil
    self:Sync()
end

-- Skip the entire current step with 1 click
function ns:SkipStep()
    local guide, step, state = self:GetCurrent()
    if not guide or not step then return end
    if step.goals then
        state.skipped = state.skipped or {}
        for index, goal in ipairs(step.goals) do
            local status = self:GetGoalStatus(goal, step, state, index)
            if status ~= "done" and status ~= "skip" then
                state.skipped[confirmationKey(state, index)] = true
            end
        end
    end
    state.cursor = math.min(state.cursor + 1, #guide.steps + 1)
    state.review = nil
    self:Sync()
end

function ns:GetGoalTitle(goal)
    local action = goal.t or goal.action
    local verbs = { accept = "Acepta", turnin = "Entrega", complete = "Completa", kill = "Derrota",
        collect = "Reúne", goto = "Ve a", talk = "Habla con", interact = "Interactúa con",
        use = "Usa", sethome = "Hogar en", hearth = "Piedra de hogar a",
        getfp = "Ruta de vuelo en", fly = "Vuela a", train = "Entrena habilidades", buy = "Compra",
        vendor = "Vende y repara", level = "Sube a nivel", note = "Nota" }
    local title
    if goal.quest or goal.questID then
        local id = goal.quest or goal.questID
        title = read(C_QuestLog and C_QuestLog.GetTitleForQuestID, id) or goal.title or ("Misión " .. id)
    else
        local candidate = matchedCandidate(self, goal)
        title = goal.title or goal.itemName or goal.npcName or (candidate and candidate.npcName)
            or goal.objName or goal.objectName or goal.location or goal.text
    end
    if action == "level" then title = tostring(goal.level or goal.n or "?") end
    if action == "train" and goal.class then title = "de tu clase" end
    local verb = goal.instructionVerb
    if not verb and action == "kill" and type(goal.note) == "string" and goal.note:match("^Habla con ") then verb = "Habla con" end
    return (verb or verbs[action] or action or "Objetivo") .. (title and (": " .. title) or "")
end

-- Clean redundant prefix from a note when it starts with the same item/target/NPC name
local function cleanNote(note, ...)
    if type(note) ~= "string" or note == "" then return nil end
    local trimmed = note
    for i = 1, select("#", ...) do
        local prefix = select(i, ...)
        if type(prefix) == "string" and prefix ~= "" then
            if trimmed:lower() == prefix:lower() then return nil end
            local pLen = #prefix
            if trimmed:sub(1, pLen):lower() == prefix:lower() then
                local rest = trimmed:sub(pLen + 1):gsub("^[,%.%s%-:]+", "")
                if rest ~= "" then
                    trimmed = rest:sub(1, 1):upper() .. rest:sub(2)
                else
                    return nil
                end
            end
        end
    end
    return trimmed
end

-- Authored mechanics can live on the goal or its containing step. Keep both
-- visible without changing completion, conditions or the selected objective.
function ns:GetGoalInstruction(goal, step)
    if type(goal) ~= "table" then return nil end
    local parts = {}
    local function append(text, context)
        if type(text) ~= "string" or not text:match("%S") then return end
        for _, part in ipairs(parts) do
            if part == text or part:find(text, 1, true) then return end
        end
        parts[#parts + 1] = (context and "En este paso: " or "") .. text
    end
    if goal.instruction then append(goal.instruction)
    else
        append(cleanNote(goal.note, goal.itemName, goal.target, goal.npcName, goal.objName or goal.objectName))
        append(goal.text)
    end
    append(goal.navigationHint)
    if step and step ~= goal and goal.instructionReplacesContext ~= true then
        append(step.note, true)
        append(step.text, true)
        for _, context in ipairs(step.goals or {}) do
            if context ~= goal and context.t == "note" then
                append(context.note, true)
                append(context.text, true)
            end
        end
    end
    return #parts > 0 and table.concat(parts, "\n") or nil
end

local shortHints = {
    [99159]="Recoge 14 leños de los troncos caídos alrededor del lago de Refugio Pinobruma.",
    [96606]="Escribe /sit junto a la hoguera hasta recibir el beneficio de descanso.",
    [96608]="Escribe /sit junto a la hoguera hasta recibir el beneficio de descanso.",
    [95998]="Escribe /sit junto a la hoguera hasta recibir el beneficio de descanso.",
    [96101]="Escribe /sit junto a la hoguera hasta recibir el beneficio de descanso.",
    [96604]="Escribe /sit junto a la hoguera hasta recibir el beneficio de descanso.",
    [96607]="Escribe /sit junto a la hoguera hasta recibir el beneficio de descanso.",
    [98326]="Consigue 1 Sack of Fish.", [1440]="Rescata a Dalinda Malem.", [99134]="Motiva a 5 Deathguards.",
    [1046]="Necesitas la calavera de Ran y la Vara de transformación de Dartol en tus bolsas.",
    [5149]="Combina la cabeza y las dos partes de la muñeca desde tus bolsas.",
    [5051]="Combina las dos mitades del talismán en tus bolsas.",
    [3786]="Cultiva 10 Mañagrana con la Faltriquera de siempre verde.",
    [3804]="Cultiva la Mañagrana que pida la misión con la Faltriquera de siempre verde.",
    [91899]="Comprueba la caja sellada 248765 y sus materiales antes de entregarla.",
    [91904]="Comprueba la caja sellada 248770 y sus materiales antes de entregarla.",
    [6022]="Tritura 7 Caña viva con Mano y almirez antes de 10 minutos.",
    [94568]="Habla con Talaanis Shadowsong.", [92640]="Habla con Valennia, Ayessa y Elaadrin.",
    [6001]="Usa Polvo lunar Cenarion, derrota a Garraluna y habla con su espíritu.",
    [6002]="Usa Polvo lunar Cenarion, derrota a Garraluna y habla con su espíritu.",
    [96873]="Desencanta Hexed Pendant para reunir 3 Luminous Residue (requiere Encantamiento).",
    [92474]="Usa la habilidad Walk on Air.",
}
function ns:GetGoalHint(goal)
    if type(goal) ~= "table" then return nil end
    local action = goal.t or goal.action
    local hint = (action == "complete" or action == "objective") and shortHints[goal.quest or goal.questID]
    if action == "accept" and goal.item then hint = "Abre " .. (goal.itemName or "el objeto de misión") .. " en tus bolsas para aceptarla." end
    if goal.navigationMode == "escort" then hint = "Sigue y protege al personaje hasta terminar la escolta." end
    hint = hint or cleanNote(goal.note, goal.itemName, goal.target, goal.npcName, goal.objName or goal.objectName) or goal.text
    if type(hint) ~= "string" or not hint:match("%S") then return nil end
    -- Keep the familiar one-line hint; full mechanics remain in the tooltip.
    hint = hint:gsub("%s+", " ")
    if #hint > 160 then
        local words, length = {}, 0
        for word in hint:gmatch("%S+") do
            if length + #word + 1 > 156 then break end
            words[#words + 1], length = word, length + #word + 1
        end
        hint = table.concat(words, " ") .. "…"
    end
    return hint
end

-- Structured list of visible goals for the current step so UI can render clean interactive rows
function ns:GetStepGoalItems(step, state)
    if not step then return {} end
    if not state then _, _, state = self:GetCurrent() end
    if not step.goals then
        return { {
            index = 1,
            goal = step,
            action = step.action or "goto",
            status = self:IsStepComplete(step) and "done" or "active",
            isCurrent = true,
            title = step.title or "Objetivo",
            subtitle = step.text or step.note,
        } }
    end
    local _, currentIdx = self:GetActiveGoal(step, state)
    local items = {}
    local doneItems = {}
    local pendingWorkByQuest = {}

    for index, goal in ipairs(step.goals) do
        local status, reason = self:GetGoalStatus(goal, step, state, index)
        if status ~= "skip" or goal.t == "note" then
            local action = goal.t or goal.action or "goto"
            local id = goal.quest or goal.questID
            -- If an earlier objective in the same step for the same quest is still incomplete,
            -- hide the turnin row until that objective is done so the tracker stays clean.
            if action == "turnin" and id and pendingWorkByQuest[id] and status ~= "done" then
                -- Skip premature turnin row in the same step
            else
                if status ~= "done" and id and (action == "kill" or action == "collect" or action == "complete" or action == "objective" or action == "interact" or action == "use") then
                    pendingWorkByQuest[id] = true
                end
                local candidate = matchedCandidate(self, goal)
                local npcName = goal.npcName or (candidate and candidate.npcName)
                local objName = goal.objName or goal.objectName
                local subLines = {}

                if action == "accept" or action == "turnin" or action == "talk" then
                    if npcName and not (action == "accept" and goal.item) then subLines[#subLines + 1] = "Habla con " .. npcName end
                else
                    local hasLiveObj = false
                    local objectives = id and read(C_QuestLog and C_QuestLog.GetQuestObjectives, id)
                    for oi, objective in ipairs(objectives or {}) do
                        if objective.text and not objective.finished and (not goal.oi or goal.oi == oi) then
                            subLines[#subLines + 1] = objective.text
                            hasLiveObj = true
                        end
                    end
                    if not hasLiveObj then
                        if goal.target and goal.target ~= npcName then
                            subLines[#subLines + 1] = goal.target .. (goal.count and (" (x" .. goal.count .. ")") or "")
                        elseif goal.itemName then
                            subLines[#subLines + 1] = goal.itemName .. (goal.count and (" (x" .. goal.count .. ")") or "")
                        elseif objName then
                            subLines[#subLines + 1] = objName
                        elseif npcName then
                            subLines[#subLines + 1] = npcName
                        end
                    end
                end

                local note = self:GetGoalHint(goal)
                if note and npcName and note:gsub("[%.%s]+$", "") == "Habla con " .. npcName then note = nil end
                if note and (index == currentIdx or #subLines == 0) then
                    subLines[#subLines + 1] = note
                end
                if (status == "blocked" or status == "manual") and reason and reason ~= note then
                    subLines[#subLines + 1] = reason
                end

                local entry = {
                    index = index,
                    goal = goal,
                    action = action,
                    status = status,
                    reason = reason,
                    isCurrent = (index == currentIdx),
                    title = self:GetGoalTitle(goal),
                    subtitle = #subLines > 0 and table.concat(subLines, "\n") or nil,
                    details = self:GetGoalInstruction(goal, index == currentIdx and step or nil),
                }
                if status == "done" then
                    doneItems[#doneItems + 1] = entry
                else
                    items[#items + 1] = entry
                end
            end
        end
    end
    -- Discard already completed quests from cluttering the active step view
    -- (only show done items if the entire step is being reviewed manually).
    if #items == 0 then return doneItems end
    return items, #doneItems
end

function ns:GetObjectives(step)
    if not step or not step.goals then return basicObjectives(self, step) end
    local _, _, state = self:GetCurrent()
    local _, current = self:GetActiveGoal(step, state)
    local lines = {}
    local skippedDone = 0
    for index, goal in ipairs(step.goals) do
        local status, reason = self:GetGoalStatus(goal, step, state, index)
        if status ~= "skip" or goal.t == "note" then
            if status == "done" and not state.review then
                skippedDone = skippedDone + 1
            else
                local color = status == "done" and "|cff7edd9c" or (index == current and "|cffffce72" or "|cffd5deeb")
                local marker = status == "done" and "[Hecho] " or (index == current and "» " or "• ")
                lines[#lines + 1] = color .. marker .. self:GetGoalTitle(goal) .. "|r"
                if index == current then
                    local candidate = matchedCandidate(self, goal)
                    local npcName = goal.npcName or (candidate and candidate.npcName)
                    local objName = goal.objName or goal.objectName
                    local action = goal.t or goal.action or "goto"
                    if npcName and not goal.instruction then lines[#lines + 1] = "   |cff8ec5ffHabla con: " .. npcName .. "|r" end
                    if action ~= "accept" and action ~= "turnin" then
                        local id = goal.quest or goal.questID
                        local objectives = id and read(C_QuestLog and C_QuestLog.GetQuestObjectives, id)
                        local hasLiveObj = false
                        for oi, objective in ipairs(objectives or {}) do
                            if objective.text and (not goal.oi or goal.oi == oi) then
                                lines[#lines + 1] = "   • " .. objective.text
                                hasLiveObj = true
                            end
                        end
                        if not hasLiveObj and not goal.instruction then
                            if goal.target then lines[#lines + 1] = "   |cffff9e80Objetivo: " .. goal.target .. (goal.count and (" (x" .. goal.count .. ")") or "") .. "|r" end
                            if goal.itemName then lines[#lines + 1] = "   |cffc9b3ffObjeto: " .. goal.itemName .. (goal.count and (" (x" .. goal.count .. ")") or "") .. "|r" end
                            if objName then lines[#lines + 1] = "   |cffe6cfa8Interactúa: " .. objName .. "|r" end
                        end
                    end
                    local note = self:GetGoalInstruction(goal, step)
                    if note then lines[#lines + 1] = "   |cff9fb0c7" .. note .. "|r" end
                    if status == "blocked" or status == "manual" then lines[#lines + 1] = "   |cffffb468" .. reason .. "|r" end
                    if goal.group then lines[#lines + 1] = "   |cffffb468Se recomienda grupo" .. (type(goal.group) == "number" and (" de " .. goal.group) or "") .. ".|r" end
                end
            end
        end
    end
    if skippedDone > 0 and #lines > 0 then
        lines[#lines + 1] = "|cff6c7a89(" .. skippedDone .. (skippedDone == 1 and " misión ya completada descartada" or " misiones ya completadas descartadas") .. ")|r"
    end
    return table.concat(lines, "\n")
end

-- Count how many quests in a guide are already completed vs total applicable quests
function ns:GetGuideQuestStats(guide)
    if not guide or not guide.steps then return 0, 0, 0 end
    local seen, done, active, total = {}, 0, 0, 0
    for _, step in ipairs(guide.steps) do
        if self:MatchesConditions(step.only) and step.goals then
            for _, goal in ipairs(step.goals) do
                local q = goal.quest or goal.questID
                if q and not seen[q] and not goal.optional and self:MatchesConditions(goal.only) then
                    seen[q] = true
                    total = total + 1
                    if self:IsQuestDelivered(q) then
                        done = done + 1
                    elseif self:IsQuestActive(q) then
                        active = active + 1
                    end
                end
            end
        end
    end
    return done, total, active
end

function ns:GetRecommendedGuide()
    local level, best, score = UnitLevel("player") or 1, nil, -math.huge
    local _, race = UnitRace("player")
    local mapID = read(C_Map and C_Map.GetBestMapForUnit, "player")
    local zoneText = (read(GetRealZoneText) or ""):lower()

    for _, guide in ipairs(self:GetVisibleGuides("", false)) do
        local rating = -1000
        if guide.status == "beta" then
            local low, high = guide.minLevel or 1, guide.maxLevel or 60
            local inZone = (mapID and guide.zone == mapID)
                or (zoneText ~= "" and ((guide.zoneName and guide.zoneName:lower() == zoneText) or guide.title:lower() == zoneText))
            local doneQuests, totalQuests, activeQuests = self:GetGuideQuestStats(guide)
            local allDone = totalQuests > 0 and doneQuests >= totalQuests

            rating = level >= low and level <= high and 100 or -math.abs(level - low) * 4
            if inZone and not allDone then
                rating = rating + 260
            end
            if activeQuests > 0 and not allDone then
                rating = rating + 140 + activeQuests * 35
            end
            if guide.races and matches(guide.races, token(race)) then
                rating = rating + 35
            elseif guide.races then
                -- If the player is physically in another race's starting zone (e.g. Dwarf in Elwynn)
                -- or has active quests there, allow that zone's guide to win!
                if inZone or activeQuests > 0 then
                    rating = rating - 10
                else
                    rating = rating - 200
                end
            end
            if level == low then rating = rating + 5 end
            if allDone then rating = rating - 500 end
        end
        if rating > score then best, score = guide, rating end
    end
    return best
end

function ns:DetectZoneGuide(silent)
    local guide = self:GetRecommendedGuide()
    if not guide then
        if not silent then self:Print("No se ha encontrado una guía para tu zona actual.") end
        return nil
    end
    local state = self:GetProgress(guide.id)
    state.review = nil
    state.placed = false
    self:SelectGuide(guide.id)
    local _, step, newState = self:GetCurrent()
    if not silent then
        local doneQ, totalQ = self:GetGuideQuestStats(guide)
        local extra = totalQ > 0 and (" · " .. doneQ .. "/" .. totalQ .. " misiones completadas") or ""
        self:Print("Zona detectada: «" .. guide.title .. "» (Paso " .. math.min(newState.cursor, #guide.steps) .. "/" .. #guide.steps .. extra .. ").")
    end
    return guide, step, newState
end

function ns:SelectGuide(id)
    local guide = self.guides[id]
    if guide and guide.steps[1] and guide.steps[1].goals then
        local faction = UnitFactionGroup("player")
        if guide.faction and guide.faction ~= faction then
            self:Print("Esta ruta pertenece a la otra facción. Puedes consultarla; elige una de tu facción para jugarla.")
        end
        local state = self:GetProgress(id)
        state.placed = false
    end
    basicSelect(self, id)
end

function ns:GetNextGuides()
    local guide = self:GetCurrent()
    local nextIDs = guide and (guide.nextChoices or guide.next)
    if type(nextIDs) == "string" then nextIDs = { nextIDs } end
    local results = {}
    for _, id in ipairs(nextIDs or {}) do if self.guides[id] then results[#results + 1] = self.guides[id] end end
    return results
end

function ns:OnNavigationTick()
    if not self.char or not self.char.auto then return end
    local _, step, state = self:GetCurrent()
    if not step or state.review then return end
    local goal = self:GetActiveGoal()
    if goal and (goal.t == "goto" or goal.action == "goto" or goal.action == "travel")
        and self.IsAtWaypoint and self:IsAtWaypoint(goal) then self:Sync() end
end

---------------------------------------------------------------------------
-- Auto-accept & Auto-turnin (RestedXP style)
---------------------------------------------------------------------------

function ns:WantsQuest(action, questID)
    if type(questID) ~= "number" or questID <= 0 then return false end
    local guide, step, state = self:GetCurrent()
    if not guide or not step or not state or state.review or not self:MatchesConditions(step.only) then return false end
    -- NPC dialogs authorize only active objectives of this visit. Merely
    -- appearing somewhere in a future route does not authorize accepting it.
    for index, goal in ipairs(step.goals or { step }) do
        if (goal.t or goal.action) == action and (goal.quest or goal.questID) == questID
            and self:GetGoalStatus(goal, step, state, index) == "active" then
            return true
        end
    end
    return false
end

function ns:HandleQuestAutomation(event)
    if not self.char or not self.char.auto then return end
    local _, _, state = self:GetCurrent()
    if not state or state.review then return end
    if read(IsShiftKeyDown) then return end -- Hold Shift to pause automation

    if event == "QUEST_DETAIL" then
        local qid = read(GetQuestID)
        if not self:WantsQuest("accept", qid) then return end
        if read(QuestFlagsPVP) then return end
        if read(QuestGetAutoAccept) then
            read(AcknowledgeAutoAcceptQuest)
        else
            read(AcceptQuest)
        end
    elseif event == "QUEST_PROGRESS" then
        local qid = read(GetQuestID)
        if not self:WantsQuest("turnin", qid) then return end
        if read(IsQuestCompletable) then
            read(CompleteQuest)
        end
    elseif event == "QUEST_COMPLETE" then
        local qid = read(GetQuestID)
        if not self:WantsQuest("turnin", qid) then return end
        local choices = read(GetNumQuestChoices)
        if type(choices) ~= "number" or choices < 0 then return end
        if choices > 1 then
            self:Print("Elige tu recompensa para entregar la misión.")
            return
        end
        local money = read(GetQuestMoneyToGet)
        if type(money) ~= "number" or money > 0 then return end
        read(GetQuestReward, choices == 1 and 1 or 0)
    elseif event == "QUEST_GREETING" then
        local numActive = read(GetNumActiveQuests) or 0
        for i = 1, numActive do
            local _, isComplete = read(GetActiveTitle, i)
            local qid = read(GetActiveQuestID, i)
            if isComplete and self:WantsQuest("turnin", qid) then
                read(SelectActiveQuest, i)
                return
            end
        end
        local numAvailable = read(GetNumAvailableQuests) or 0
        for i = 1, numAvailable do
            local _, _, _, _, qid = read(GetAvailableQuestInfo, i)
            if self:WantsQuest("accept", qid) then
                read(SelectAvailableQuest, i)
                return
            end
        end
    elseif event == "GOSSIP_SHOW" and C_GossipInfo then
        local active = read(C_GossipInfo.GetActiveQuests) or {}
        for _, info in ipairs(active) do
            if info.isComplete and self:WantsQuest("turnin", info.questID) then
                read(C_GossipInfo.SelectActiveQuest, info.questID)
                return
            end
        end
        local available = read(C_GossipInfo.GetAvailableQuests) or {}
        for _, info in ipairs(available) do
            if self:WantsQuest("accept", info.questID) then
                read(C_GossipInfo.SelectAvailableQuest, info.questID)
                return
            end
        end
    end
end

-- Service steps use observable UI actions or an explicit confirmation. Merely
-- reaching an NPC never completes a quest, combat objective or a turn-in.
local function atService(self, goal)
    local candidate = matchedCandidate(self, goal)
    local expected = goal.npc or (candidate and candidate.npc)
    if expected then
        local guid = read(UnitGUID, "npc")
        local id = type(guid) == "string" and tonumber(guid:match("%-(%d+)%-[^%-]+$"))
        return id == expected
    end
    return self.IsAtWaypoint and self:IsAtWaypoint(goal) or false
end

function ns:ObserveService(event, first, _, spellID)
    local goal, index, status = self:GetActiveGoal()
    local _, step, state = self:GetCurrent()
    if not goal or not step.goals or state.review or status ~= "manual" then return end
    local action, accepted = goal.t, false
    if action == "sethome" and event == "HEARTHSTONE_BOUND" then
        accepted = atService(self, goal)
        if not accepted and goal.location then
            local bound = read(GetBindLocation)
            accepted = type(bound) == "string" and bound:lower() == goal.location:lower()
        end
    elseif action == "getfp" and event == "NEW_TAXI_PATH" then accepted = atService(self, goal)
    -- Opening a merchant or trainer proves neither a sale/repair nor learning
    -- all requested skills. Those actions retain their explicit confirmation.
    elseif action == "talk" and (event == "GOSSIP_SHOW" or event == "QUEST_GREETING") then
        accepted = atService(self, goal)
    elseif action == "use" and event == "UNIT_SPELLCAST_SUCCEEDED" and first == "player" and goal.item then
        local api = C_Item and C_Item.GetItemSpell or GetItemSpell
        if api then
            local ok, _, itemSpell = pcall(api, goal.item)
            accepted = ok and itemSpell == spellID
        end
    end
    if accepted then
        state.confirmed = state.confirmed or {}
        state.confirmed[confirmationKey(state, index)] = true
    end
end

local events = CreateFrame("Frame")
for _, event in ipairs({
    "BAG_UPDATE_DELAYED", "HEARTHSTONE_BOUND", "NEW_TAXI_PATH", "TAXIMAP_OPENED",
    "MERCHANT_SHOW", "TRAINER_SHOW", "GOSSIP_SHOW", "QUEST_GREETING", "QUEST_DETAIL",
    "QUEST_PROGRESS", "QUEST_COMPLETE", "UNIT_SPELLCAST_SUCCEEDED",
    "ZONE_CHANGED_NEW_AREA"
}) do
    pcall(events.RegisterEvent, events, event)
end
events:SetScript("OnEvent", function(_, event, ...)
    if not ns.initialized then return end
    if event == "ZONE_CHANGED_NEW_AREA" then
        local guide, _, state = ns:GetCurrent()
        if state then state.placed = false end
        -- A route may intentionally cross zone borders for an NPC or class
        -- chain. Keep its progress; /rutaxp zona remains an explicit choice.
    end
    ns:ObserveService(event, ...)
    ns:HandleQuestAutomation(event)
    ns:Sync()
end)
