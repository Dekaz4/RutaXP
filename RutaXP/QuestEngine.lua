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
    if self.turnedIn[id] == true then return true end
    -- A repeat in the live log still needs its current objectives, even
    -- when the client retains a historical completion flag.
    if self:IsQuestActive(id) then return false end
    return read(C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted, id) == true
        or read(IsQuestFlaggedCompleted, id) == true
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
    cached = { stepOf = {}, accepts = {}, preOf = {}, work = {}, titles = {} }
    for s, step in ipairs(guide.steps) do
        cached.stepOf[step] = s
        for g, goal in ipairs(step.goals or {}) do
            local q = goal.quest or goal.questID
            if q and goal.title then cached.titles[q] = goal.title end
            local kind = goal.t or goal.action
            if q and (kind == "collect" or kind == "kill" or kind == "complete" or kind == "objective"
                or kind == "interact" or kind == "use") then
                cached.work[q] = cached.work[q] or {}
                table.insert(cached.work[q], { s=s, g=g, step=step, goal=goal })
            end
            if q and (goal.t or goal.action) == "accept" then
                cached.accepts[q] = cached.accepts[q] or {}
                table.insert(cached.accepts[q], { s = s, g = g, step = step, goal = goal })
                if type(goal.parent) == "number" and goal.parent > 0 then
                    cached.preOf[goal.parent] = cached.preOf[goal.parent] or {}
                    table.insert(cached.preOf[goal.parent], q)
                end
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

local professionNames = { [129]="Primeros auxilios", [164]="Herrería", [165]="Peletería", [171]="Alquimia",
    [182]="Herboristería", [185]="Cocina", [186]="Minería", [197]="Sastrería", [202]="Ingeniería",
    [333]="Encantamiento", [356]="Pesca", [393]="Desuello" }
local function finiteNumber(value)
    return not (issecretvalue and issecretvalue(value)) and type(value) == "number"
        and value == value and math.abs(value) < math.huge
end
local function ownProfessionRequirement(goal)
    if not goal then return nil end
    local requirement = type(goal.requiresSkill) == "table" and goal.requiresSkill
    if not requirement and not goal.profLine then return nil end
    local id = requirement and requirement.id or goal.profLine
    local rank = requirement and requirement.rank or goal.profRank or 1
    return { id=id, rank=rank, name=professionNames[id] or (requirement and requirement.name) or goal.profName or "la profesión indicada" }
end
function ns:GetGoalProfessionRequirement(goal, step)
    local requirement = ownProfessionRequirement(goal) or ownProfessionRequirement(step)
    if requirement then return requirement end
    local id = goal and (goal.quest or goal.questID)
    local guide = self.char and self.guides[self.char.activeGuide]
    local layout = id and getGuideLayout(self, guide)
    for _, entry in ipairs(layout and layout.accepts[id] or {}) do
        if self:MatchesConditions(entry.step.only) and self:MatchesConditions(entry.goal.only) then
            requirement = ownProfessionRequirement(entry.goal) or ownProfessionRequirement(entry.step)
            if requirement then return requirement end
        end
    end
end

-- Never infer a partner's professions. A nil rank is unreadable, while zero
-- requires a readable, complete local enumeration or an explicit skill record.
function ns:InvalidateProfessionRequirements()
    self.professionRanks = nil
    if self.DuoPlanner and self.DuoPlanner.Invalidate then self.DuoPlanner:Invalidate() end
end
function ns:GetProfessionRank(id)
    if not finiteNumber(id) or id <= 0 or id ~= math.floor(id) then return nil end
    local now = read(GetTime) or 0
    local cache = self.professionRanks
    if not cache or now < cache.at or now - cache.at >= 5 then
        cache = { at=now, values={} }; self.professionRanks = cache
    end
    local cached = cache.values[id]
    if cached ~= nil then return cached ~= false and cached or nil end
    local function remember(rank)
        if rank == nil then cache.values[id] = false else cache.values[id] = rank end
        return rank
    end
    local function rankOf(info)
        if type(info) ~= "table" or (issecretvalue and issecretvalue(info)) then return nil end
        local rank, maximum = info.rank, info.maxRank
        if finiteNumber(rank) and rank >= 0 and finiteNumber(maximum) and maximum >= rank then return rank end
    end
    local rank = rankOf(read(C_SkillInfo and C_SkillInfo.GetSkillLineInfoByID, id))
    if rank ~= nil then return remember(rank) end
    if type(GetProfessions) == "function" and type(GetProfessionInfo) == "function" then
        local results = { pcall(GetProfessions) }
        if results[1] then
            local complete = true
            for index = 2, 7 do
                local slot = results[index]
                if issecretvalue and issecretvalue(slot) then complete = false
                elseif slot ~= nil then
                    if not finiteNumber(slot) then complete = false
                    else
                        local _, _, skillRank, _, _, _, skillID = read(GetProfessionInfo, slot)
                        if not finiteNumber(skillID) or not finiteNumber(skillRank) or skillRank < 0 then complete = false
                        elseif skillID == id then return remember(skillRank) end
                    end
                end
            end
            if complete then return remember(0) end
        end
    end
    local count = read(C_SkillInfo and C_SkillInfo.GetNumSkillLines)
    if finiteNumber(count) and count >= 0 and count <= 1000 and count == math.floor(count) then
        local complete = true
        for index = 1, count do
            local info = read(C_SkillInfo and C_SkillInfo.GetSkillLineInfo, index)
            if type(info) ~= "table" then complete = false
            elseif issecretvalue and (issecretvalue(info.skillID) or issecretvalue(info.isHeader) or issecretvalue(info.isExpanded)) then complete = false
            elseif info.isHeader then
                -- A collapsed category can hide a learned skill; do not
                -- expand the user's skill window just to manufacture certainty.
                if info.isExpanded ~= true then complete = false end
            elseif info.skillID == id then
                rank = rankOf(info)
                if rank ~= nil then return remember(rank) end
                complete = false
            elseif not finiteNumber(info.skillID) then complete = false end
        end
        if complete then return remember(0) end
    end
    return remember(nil)
end
function ns:CheckGoalProfession(goal, step)
    local requirement = self:GetGoalProfessionRequirement(goal, step)
    if not requirement then return true end
    local id = goal and (goal.quest or goal.questID)
    if id and (self:IsQuestActive(id) or self:IsQuestDelivered(id)) then return true end
    local rank = self:GetProfessionRank(requirement.id)
    local needed = requirement.rank
    if not finiteNumber(needed) or needed < 1 or rank == nil then
        return nil, "No se puede comprobar " .. requirement.name
    end
    if rank < needed then
        return false, "Requiere " .. requirement.name .. (needed > 1 and (" (" .. needed .. ")") or "")
    end
    return true
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

local function questWorkReason(goal, id)
    if read(C_QuestLog and C_QuestLog.IsComplete, id) == true then return "Objetivos completados" end
    local oi = goal.oi or goal.objective
    if oi then
        local objectives = read(C_QuestLog and C_QuestLog.GetQuestObjectives, id)
        local finished = objectives and objectives[oi] and objectives[oi].finished
        if not (issecretvalue and issecretvalue(finished)) and finished == true then return "Objetivo completado" end
    elseif (goal.t or goal.action) == "collect" and goal.item and goal.count and itemCount(goal.item) >= goal.count then
        return "Objetos reunidos"
    end
end

local function questLabel(layout, id, fallback)
    local live = read(C_QuestLog and C_QuestLog.GetTitleForQuestID, id)
    return type(live) == "string" and live ~= "" and live
        or (layout and layout.titles[id]) or fallback or ("Misión " .. tostring(id))
end

local function prerequisiteReason(self, layout, goal, ids, alternatives)
    local labels = {}
    for _, value in ipairs(ids) do
        local id = math.abs(value)
        if not self:IsQuestDelivered(id) then
            labels[#labels + 1] = "«" .. questLabel(layout, id, (goal.preTitles or {})[id]) .. "»"
        end
    end
    if #labels == 1 then
        local id = math.abs(ids[1])
        for _, value in ipairs(ids) do if not self:IsQuestDelivered(math.abs(value)) then id = math.abs(value); break end end
        local ready = self:IsQuestActive(id) and read(C_QuestLog and C_QuestLog.IsComplete, id) == true
        return (ready and "Entrega primero " or "Completa y entrega primero ") .. labels[1]
    end
    if alternatives then
        return "Entrega una previa: " .. labels[1] .. (#labels == 2 and (" o " .. labels[2]) or (" u otras " .. (#labels - 1)))
    end
    return "Entrega primero " .. labels[1] .. " y " .. (#labels - 1) .. " previa(s) más"
end

local function omittedWork(self, layout, id, state, stepIndex, goalIndex)
    if not layout or not state then return false end
    for _, entry in ipairs(layout.work[id] or {}) do
        if (entry.s < stepIndex or entry.s == stepIndex and entry.g < goalIndex)
            and self:MatchesConditions(entry.step.only) and self:MatchesConditions(entry.goal.only) then
            local key = confirmationKey(state, entry.g, entry.s)
            if ((state.skipped and state.skipped[key]) or (state.confirmed and state.confirmed[key]))
                and not questWorkReason(entry.goal, id) then return true end
        end
    end
    return false
end

function ns:GetGoalStatus(goal, step, state, index)
    if not self:MatchesConditions(step and step.only) or not self:MatchesConditions(goal.only) then return "skip", "Otro personaje" end
    local guide = self.char and self.guides[self.char.activeGuide]
    local layout = guide and getGuideLayout(self, guide)
    local stepIndex = (layout and step and layout.stepOf[step]) or (state and state.cursor) or 1
    local action, id = goal.t or goal.action, goal.quest or goal.questID
    if not id and (action == "fly" or action == "goto" or action == "hearth") and self.IsTravelServiceComplete
        and self:IsTravelServiceComplete(guide, stepIndex, index) then return "done", "Llegada confirmada" end
    if id and self:IsQuestDelivered(id) then return "done", "Misión entregada" end
    local onQuest = id and self:IsQuestActive(id)
    local workDone = id and action ~= "accept" and action ~= "turnin" and questWorkReason(goal, id)
    -- Actual acceptance/objective credit supersedes an earlier manual skip.
    if onQuest and action == "accept" then return "done", "Aceptada" end
    if onQuest and workDone then return "done", workDone end
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
    -- A branch excluded at acceptance also excludes its later work/delivery.
    -- An actual quest in the log remains actionable, even if another branch exists.
    if not onQuest and (isClosedBranch(self, goal) or (id and action ~= "accept"
        and isClosedBranch(self, earlierAccept(self, layout, id, stepIndex, index)))) then
        return "skip", "Rama alternativa ya elegida"
    end
    if goal.optional and not (self.char and self.char.optional) and not onQuest then return "skip", "Opcional desactivado" end
    local profession, professionReason = self:CheckGoalProfession(goal, step)
    if profession == false then return "skip", professionReason end
    if profession == nil then return "blocked", professionReason end
    local playerLevel = UnitLevel("player") or 1
    if action == "accept" then
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
        -- A parent is an umbrella quest kept in the journal while its
        -- subquests are done. Its delivery is not an acceptance prerequisite.
        if goal.parent and not self:IsQuestActive(goal.parent) then
            local parentTitle = read(C_QuestLog and C_QuestLog.GetTitleForQuestID, goal.parent)
                or (goal.preTitles or {})[goal.parent] or ("Misión " .. tostring(goal.parent))
            return "blocked", "Acepta primero " .. parentTitle .. " y mantenla en tu diario"
        end
        for _, pre in ipairs(goal.preAll or {}) do
            if not self:IsQuestDelivered(math.abs(pre)) then
                return "blocked", prerequisiteReason(self, layout, goal, goal.preAll, false)
            end
        end
        if goal.pre and #goal.pre > 0 then
            local ready = false
            for _, pre in ipairs(goal.pre) do if self:IsQuestDelivered(math.abs(pre)) then ready = true; break end end
            if not ready then return "blocked", prerequisiteReason(self, layout, goal, goal.pre, true) end
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
        if action == "turnin" then
            if onQuest and read(C_QuestLog and C_QuestLog.IsComplete, id) == false
                and omittedWork(self, layout, id, state, stepIndex, index or 1) then
                return "blocked", "Retoma los objetivos pendientes de «" .. questLabel(layout, id, goal.title) .. "»"
            end
            return "active", "Entrega la misión al NPC"
        end
        if workDone then return "done", workDone end
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

-- During a town visit a rogue travelling alone can hand in a ready quest
-- to the NPC in front of them. Never pull an acceptance or an escort forward.
local function readyAtContact(self, step, state, first)
    local char = self.char
    if not state or state.review or not char or char.auto ~= true or not char.activeGuide
        or not char.activeGuide:match("^forever/alliance/") or (char.duo and char.duo.enabled)
        or read(IsInGroup) then return end
    local _, class = UnitClass("player")
    local _, race = UnitRace("player")
    if class ~= "ROGUE" or race ~= "Human" then return end
    local guid = read(UnitGUID, "npc")
    if not guid and read(CheckInteractDistance, "target", 3) == true then guid = read(UnitGUID, "target") end
    local contact = type(guid) == "string" and tonumber(guid:match("^Creature%-%d+%-%d+%-%d+%-%d+%-(%d+)%-"))
    if not contact or step.goals[first].npc == contact then return end
    for index = first + 1, #step.goals do
        local goal = step.goals[index]
        if goal.t ~= "accept" and goal.t ~= "turnin" then break end
        if goal.t == "turnin" and goal.npc == contact and goal.quest
            and self:IsQuestActive(goal.quest) and read(C_QuestLog and C_QuestLog.IsComplete, goal.quest) == true then
            local status, reason = self:GetGoalStatus(goal, step, state, index)
            if status == "active" then return goal, index, status, reason end
        end
    end
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
        if status ~= "done" and status ~= "skip" then
            if status == "active" and (goal.t == "accept" or goal.t == "turnin") and index < #step.goals then
                local nearby, row, ready, why = readyAtContact(self, step, state, index)
                if nearby then return nearby, row, ready, why end
            end
            return goal, index, status, reason
        end
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
        -- Optional errands can be switched off independently of a required
        -- journey (for example the tram with the optional parcels in Forjaz).
        if q and not goal.optional and self:MatchesConditions(goal.only) then
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
    if self.UpdateGuideTravel then self:UpdateGuideTravel() end
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
    if state and not step then return self:ContinueGuide() end
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

function ns:GetPreviousRestorableStep()
    local guide, _, state = self:GetCurrent()
    if not guide or state.cursor <= 1 then return end
    local stepIndex = state.cursor - 1
    local step = guide.steps[stepIndex]
    for index, goal in ipairs(step and step.goals or {}) do
        local key = confirmationKey(state, index, stepIndex)
        if (state.skipped and state.skipped[key])
            or ((goal.quest or goal.questID) and state.confirmed and state.confirmed[key]) then
            local status, reason = self:GetGoalStatus(goal, step, state, index)
            if status == "skip" and reason and reason:find("Omitido manualmente", 1, true) == 1 then return stepIndex end
        end
    end
end

function ns:RestoreStepOmissions(guide, state, stepIndex)
    local step = guide.steps[stepIndex]
    local restored = false
    for index, goal in ipairs(step and step.goals or {}) do
        local key = confirmationKey(state, index, stepIndex)
        if state.skipped and state.skipped[key] then
            state.skipped[key] = nil
            restored = true
        end
        -- Old quest confirmations represented manual omissions. Genuine
        -- service confirmations still record an action the player performed.
        if (goal.quest or goal.questID) and state.confirmed and state.confirmed[key] then
            state.confirmed[key] = nil
            restored = true
        end
    end
    return restored
end

-- Explicitly rejoin the unfinished quests that are actually in this
-- character's journal. Manual service confirmations and other guides stay
-- outside this operation, including tasks belonging only to the partner.
function ns:ResumePendingQuests()
    local guide, _, state = self:GetCurrent()
    if not guide then return false, "Selecciona una guía para buscar tus misiones pendientes." end
    if guide.recovery or guide.temporary then return false, "Vuelve a tu ruta para recuperar los objetivos omitidos." end
    if self.GetGuideTravel and self:GetGuideTravel() then return false, "Termina el viaje para retomar las misiones de esta guía." end
    local first, keys = nil, {}
    local observed = { cursor = state.cursor, confirmed = {}, skipped = {} }
    for stepIndex, step in ipairs(guide.steps) do
        if self:MatchesConditions(step.only) then
            for index, goal in ipairs(step.goals or {}) do
                local id = goal.quest or goal.questID
                if id and self:IsQuestActive(id) and self:MatchesConditions(goal.only) then
                    local status = self:GetGoalStatus(goal, step, observed, index)
                    if status ~= "done" and status ~= "skip" then
                        first = first or stepIndex
                        keys[#keys + 1] = confirmationKey(state, index, stepIndex)
                    end
                end
            end
        end
    end
    if not first then return false, "Tu diario no tiene objetivos pendientes que correspondan a esta guía." end
    for _, key in ipairs(keys) do
        if state.skipped then state.skipped[key] = nil end
        if state.confirmed then state.confirmed[key] = nil end
    end
    state.cursor, state.review, state.placed = first, nil, true
    if self.DuoAuto and self.DuoAuto.RefreshProgressAgreement then self.DuoAuto:RefreshProgressAgreement() end
    if self.Duo then
        self.Duo.lastSentHeader = nil
        if self.Duo.Resynchronize then self.Duo:Resynchronize() end
    end
    self:Sync()
    return true, "Retomadas tus misiones pendientes del diario en el paso " .. state.cursor .. "."
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
    if step and step ~= goal and not goal.instructionReplacesContext and not goal.instructionAsHint then
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
    if goal.instructionAsHint and type(goal.instruction) == "string" then return goal.instruction end
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
        local manualSkip = status == "skip" and reason and reason:find("Omitido manualmente", 1, true) == 1
        if status ~= "skip" or manualSkip or goal.t == "note" then
            local action = goal.t or goal.action or "goto"
            local id = goal.quest or goal.questID
            -- If an earlier objective in the same step for the same quest is still incomplete,
            -- hide the turnin row until that objective is done so the tracker stays clean.
            if action == "turnin" and id and pendingWorkByQuest[id] and status ~= "done" and index ~= currentIdx then
                -- Skip premature turnin row in the same step
            else
                if status ~= "done" and id and (action == "kill" or action == "collect" or action == "complete" or action == "objective" or action == "interact" or action == "use") then
                    pendingWorkByQuest[id] = true
                end
                local candidate = matchedCandidate(self, goal)
                local npcName = goal.npcName or (candidate and candidate.npcName)
                local objName = goal.objName or goal.objectName
                local subLines = {}

                if status == "done" then
                    -- Quest history can expose zeroed objective counters.
                    -- Show the proven result instead of those old counters.
                    subLines[#subLines + 1] = reason
                elseif action == "accept" or action == "turnin" or action == "talk" then
                    if npcName and not goal.instructionAsHint and not (action == "accept" and goal.item) then subLines[#subLines + 1] = "Habla con " .. npcName end
                else
                    local hasLiveObj = false
                    local objectives = id and read(C_QuestLog and C_QuestLog.GetQuestObjectives, id)
                    for oi, objective in ipairs(objectives or {}) do
                        if objective.text and objective.finished ~= true and (not goal.oi or goal.oi == oi) then
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
                if status ~= "done" and note and (index == currentIdx or #subLines == 0) then
                    subLines[#subLines + 1] = note
                end
                if (status == "blocked" or status == "manual") and reason and reason ~= note then
                    subLines[#subLines + 1] = reason
                end

                local details = self:GetGoalInstruction(goal, index == currentIdx and step or nil)
                if index == currentIdx and status == "active" and (action == "accept" or action == "turnin")
                    and self.GetRogueQuestRewardInfo then
                    local hint, rewards = self:GetRogueQuestRewardInfo(id, action)
                    if hint then
                        subLines[#subLines + 1] = hint
                        details = details and (details .. "\n" .. rewards) or rewards
                    end
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
                    details = details,
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
        local manualSkip = status == "skip" and reason and reason:find("Omitido manualmente", 1, true) == 1
        if status ~= "skip" or manualSkip or goal.t == "note" then
            if status == "done" and not state.review then
                skippedDone = skippedDone + 1
            else
                local color = status == "done" and "|cff7edd9c" or manualSkip and "|cff9ba8b8" or (index == current and "|cffffce72" or "|cffd5deeb")
                local marker = status == "done" and "[Hecho] " or manualSkip and "[Omitido] " or (index == current and "» " or "• ")
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
            local saved = self.char and self.char.progress and self.char.progress[guide.id]
            local allDone = (type(saved) == "table" and (tonumber(saved.cursor) or 0) > #guide.steps)
                or (totalQuests > 0 and doneQuests >= totalQuests)

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

function ns:GetNextGuides(guide)
    guide = guide or self:GetCurrent()
    local nextIDs = guide and (guide.nextChoices or guide.next)
    if type(nextIDs) == "string" then nextIDs = { nextIDs } end
    local results = {}
    if type(nextIDs) == "table" then
        for _, id in ipairs(nextIDs) do if self.guides[id] then results[#results + 1] = self.guides[id] end end
    end
    return results
end

local function uniqueSuccessor(self, guide)
    local result
    for _, candidate in ipairs(self:GetNextGuides(guide)) do
        if not candidate.temporary and not candidate.recovery
            and (not candidate.faction or candidate.faction == read(UnitFactionGroup, "player"))
            and self:MatchesConditions(candidate) and self:MatchesConditions(candidate.only) then
            if result and result ~= candidate then return nil, "Elige entre las rutas disponibles en Guías." end
            result = candidate
        end
    end
    if result then return result end
    if guide.next or guide.nextChoices then return nil, "No hay una guía enlazada disponible para tu personaje." end
    return nil, "Has llegado al final de esta ruta."
end

-- The link comes from the route author. Map and level recommendations are
-- deliberately separate, so a finished starter cannot send us back to itself.
function ns:GetLinkedGuide(guide)
    if not guide or guide.recovery or guide.temporary then return nil end
    local successor, reason = uniqueSuccessor(self, guide)
    local nextGuide, visited = successor, { [guide.id] = true }
    while nextGuide do
        if visited[nextGuide.id] then return nil, "El enlace es circular. Elige otra guía en Guías." end
        visited[nextGuide.id] = true
        nextGuide = uniqueSuccessor(self, nextGuide)
    end
    return successor, reason
end

function ns:GetGuideContinuation()
    local guide, step, state = self:GetCurrent()
    if not guide or step or not state or state.cursor <= #guide.steps then return nil, "Termina el paso actual para continuar." end
    if state.review then return nil, "Estás revisando la guía." end
    if guide.recovery or guide.temporary or (type(self.char.recovery) == "table" and self.char.recovery.active) then
        return nil, "Termina la recuperación para volver a tu guía."
    end
    local successor, reason = self:GetLinkedGuide(guide)
    if self.DuoAuto and self.DuoAuto.GetContinuationState then
        local managed, waitReason, canRequest = self.DuoAuto:GetContinuationState(guide)
        if managed then return canRequest and successor or nil, waitReason, true end
    end
    return successor, reason
end

-- Callers validate the route and any party agreement before committing.
-- Rendering and quest scans run after the caller has finished its transition.
function ns:ApplyGuideContinuation(target)
    if not target or self.guides[target.id] ~= target then return false end
    if self.RememberGuideTravel then self:RememberGuideTravel(self.char.activeGuide, target.id) end
    self.char.activeGuide = target.id
    self:GetProgress(target.id)
    if self.UpdateGuideTravel then self:UpdateGuideTravel() end
    if self.Duo then self.Duo.lastSentHeader = nil end
    return true
end

function ns:ContinueGuide()
    local guide = self:GetCurrent()
    local successor, reason, coordinated = self:GetGuideContinuation()
    if not successor then return false, reason end
    if coordinated then return self.DuoAuto:RequestContinuation(guide) end
    self:ApplyGuideContinuation(successor)
    self:Sync()
    return true
end

function ns:OnNavigationTick()
    if not self.char or not self.char.auto or (self.GetGuideTravel and self:GetGuideTravel()) then return end
    local _, step, state = self:GetCurrent()
    if not step or state.review then return end
    local goal = self:GetActiveGoal()
    -- On arrival a grouped goto is already satisfied, so GetActiveGoal
    -- no longer returns it. A waiting partner may still hold this step.
    if not goal and step.goals then
        if self:IsStepComplete(step, state) then self:Sync() end
    elseif goal and (goal.t == "goto" or goal.action == "goto" or goal.action == "travel")
        and self.IsAtWaypoint and self:IsAtWaypoint(goal) then self:Sync() end
end

---------------------------------------------------------------------------
-- Auto-accept & Auto-turnin (RestedXP style)
---------------------------------------------------------------------------

function ns:WantsQuest(action, questID)
    if self.GetGuideTravel and self:GetGuideTravel() then return false end
    if not finiteNumber(questID) or questID <= 0 then return false end
    local guide, step, state = self:GetCurrent()
    if not guide or not step or not state or state.review or not self:MatchesConditions(step.only) then return false end
    -- Current, unblocked objectives always take priority in an NPC menu.
    for index, goal in ipairs(step.goals or { step }) do
        if (goal.t or goal.action) == action and (goal.quest or goal.questID) == questID
            and self:GetGoalStatus(goal, step, state, index) == "active" then
            return true
        end
    end
    return false
end

function ns:GetEarlyQuestSpace()
    local limit = read(C_QuestLog and C_QuestLog.GetMaxNumQuestsCanAccept) or MAX_QUESTLOG_QUESTS
    local _, used = read(C_QuestLog and C_QuestLog.GetNumQuestLogEntries)
    if not finiteNumber(used) then _, used = read(GetNumQuestLogEntries) end
    -- The first return counts displayed rows, including zone headers. The
    -- second counts quests even if a zone is collapsed. Keep the last slot
    -- for a required pickup at the character's current step.
    return finiteNumber(limit) and limit > 0 and limit == math.floor(limit)
        and finiteNumber(used) and used >= 0 and used == math.floor(used) and limit - used >= 2
end

function ns:ShouldWaitForEarlyQuest(step)
    local duo = self.char and self.char.duo
    if duo and duo.autoSession and self.DuoAuto and self.DuoAuto:ShouldPauseAutomation() then return true end
    return duo and duo.enabled and duo.wait and self.Duo and self.Duo:ShouldWaitForStep(step) or false
end

function ns:GetQuestContactNPC()
    local guid = read(UnitGUID, "npc")
    return type(guid) == "string" and tonumber(guid:match("^Creature%-%d+%-%d+%-%d+%-%d+%-(%d+)%-"))
end

local function turninAtContact(self, id, ready)
    if self.GetGuideTravel and self:GetGuideTravel() then return false end
    if self:WantsQuest("turnin", id) then return true end
    if not self.CanHandInDuringVisit then return false end
    local npc = self:GetQuestContactNPC()
    return npc and self:CanHandInDuringVisit(id, npc, ready) or false
end

local function selectAvailable(self, count, getOffer, selectOffer)
    local early
    for i = 1, count do
        local id, selection = getOffer(i)
        if self:WantsQuest("accept", id) then
            read(selectOffer, selection)
            return
        end
        if not early and self.GetEarlyQuestOffer and self:GetEarlyQuestOffer(id) then early = selection end
    end
    if early then read(selectOffer, early) end
end

local function greetingOffer(index)
    local _, _, _, _, id = read(GetAvailableQuestInfo, index)
    return id, index
end

function ns:HandleQuestAutomation(event)
    if not self.char or not self.char.auto then return end
    local _, _, state = self:GetCurrent()
    if not state or state.review then return end
    if read(IsShiftKeyDown) then return end -- Hold Shift to pause automation

    if event == "QUEST_DETAIL" then
        local qid = read(GetQuestID)
        if not self:WantsQuest("accept", qid) and not (self.GetEarlyQuestOffer and self:GetEarlyQuestOffer(qid)) then return end
        if read(QuestFlagsPVP) then return end
        if read(QuestGetAutoAccept) then
            read(AcknowledgeAutoAcceptQuest)
        else
            read(AcceptQuest)
        end
    elseif event == "QUEST_PROGRESS" then
        local qid = read(GetQuestID)
        local ready = read(IsQuestCompletable)
        if (ready == true or ready == 1) and turninAtContact(self, qid, true) then read(CompleteQuest) end
    elseif event == "QUEST_COMPLETE" then
        local qid = read(GetQuestID)
        if not turninAtContact(self, qid, true) then return end
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
            if (isComplete == true or isComplete == 1) and turninAtContact(self, qid, true) then
                read(SelectActiveQuest, i)
                return
            end
        end
        selectAvailable(self, read(GetNumAvailableQuests) or 0, greetingOffer, SelectAvailableQuest)
    elseif event == "GOSSIP_SHOW" and C_GossipInfo then
        local active = read(C_GossipInfo.GetActiveQuests) or {}
        for _, info in ipairs(active) do
            if not (issecretvalue and issecretvalue(info.isComplete))
                and (info.isComplete == true or info.isComplete == 1) and turninAtContact(self, info.questID, true) then
                read(C_GossipInfo.SelectActiveQuest, info.questID)
                return
            end
        end
        local available = read(C_GossipInfo.GetAvailableQuests) or {}
        selectAvailable(self, #available, function(i)
            local id = available[i].questID
            return id, id
        end, C_GossipInfo.SelectAvailableQuest)
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
    "ZONE_CHANGED_NEW_AREA", "SKILL_LINES_CHANGED", "TRADE_SKILL_LIST_UPDATE", "PLAYER_ENTERING_WORLD"
}) do
    pcall(events.RegisterEvent, events, event)
end
events:SetScript("OnEvent", function(_, event, ...)
    if not ns.initialized then return end
    if event == "SKILL_LINES_CHANGED" or event == "TRADE_SKILL_LIST_UPDATE" or event == "PLAYER_ENTERING_WORLD" then
        ns:InvalidateProfessionRequirements()
    end
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
