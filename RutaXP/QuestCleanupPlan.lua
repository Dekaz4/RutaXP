local _, ns = ...

local function applies(self, value, faction)
    if value.faction and value.faction ~= faction then return false end
    if (value.classes or value.races or value.factions) and not self:MatchesConditions(value) then return false end
    if type(value.class) == "string" and not self:MatchesConditions({classes={value.class}}) then return false end
    if type(value.class) == "table" and not self:MatchesConditions({classes=value.class}) then return false end
    return self:MatchesConditions(value.only)
end

local function classSpecific(row)
    return row.class or row.classes or row.only and row.only.classes
end

local function specialQuest(guide, step, goal)
    if classSpecific(guide) or classSpecific(step) or classSpecific(goal) then return "Misión de clase." end
    if goal.profLine or goal.requiresSkill or step.profLine or step.requiresSkill then return "Misión de profesión." end
    if goal.important or goal.reward or goal.rewardItem or goal.rewards then return "Recompensa o misión destacada en la guía." end
    if (goal.t or goal.action) == "accept" and goal.item then return "Se inicia con un objeto." end
end

-- The catalogue and its prerequisite edges are static during a session. Keep
-- cursors, quest progress, item counts and solo settings out of this index.
local cache
local function catalog(self, faction, race, class)
    if cache and cache.faction == faction and cache.race == race and cache.class == class
        and cache.count == #self.order and cache.data == self.QuestCleanupData then
        local unchanged = true
        for _, id in ipairs(self.order) do
            if cache.refs[id] ~= self.guides[id] then unchanged = false; break end
        end
        if unchanged then return cache end
    end
    local result = {faction=faction, race=race, class=class, data=self.QuestCleanupData, count=#self.order,
        refs={}, guides={}, rows={}, children={}, parents={}, special={}}
    local function edge(child, parent)
        if type(parent) ~= "number" or parent == 0 then return end
        parent = math.abs(parent)
        result.parents[child] = result.parents[child] or {}
        result.parents[child][parent] = true
        result.children[parent] = result.children[parent] or {}
        result.children[parent][child] = true
    end
    local function indexRow(id, guide, step, goal, si, gi)
        if not id then return end
        local rows = result.rows[id] or {}
        result.rows[id] = rows
        rows[#rows+1] = {guide=guide, step=step, goal=goal, si=si, gi=gi}
        result.special[id] = result.special[id] or specialQuest(guide, step, goal)
        edge(id, goal.parent)
        for _, field in ipairs({"pre","preAll","chainStarted","soloAfter"}) do
            for _, pre in ipairs(goal[field] or {}) do edge(id, pre) end
        end
        for _, alternative in ipairs(goal.closedBy or {}) do
            result.special[alternative] = result.special[alternative] or "Forma parte de una elección de cadena."
        end
        if goal.closedBy then result.special[id] = result.special[id] or "Forma parte de una elección de cadena." end
    end
    for _, guideID in ipairs(self.order) do
        local guide = self.guides[guideID]
        result.refs[guideID] = guide
        if guide and not guide.recovery and not guide.temporary and applies(self, guide, faction) then
            result.guides[guideID] = guide
            for si, step in ipairs(guide.steps) do
                if applies(self, step, faction) then
                    for gi, goal in ipairs(step.goals or {step}) do
                        if applies(self, goal, faction) then
                            local direct = goal.quest or goal.questID
                            indexRow(direct, guide, step, goal, si, gi)
                            for _, field in ipairs({"workForQuest","groupVisitFor","visitQuest","detourQuest"}) do
                                if goal[field] ~= direct then indexRow(goal[field], guide, step, goal, si, gi) end
                            end
                            for _, offer in ipairs(goal.detourOffers or {}) do
                                if applies(self, offer, faction) then indexRow(offer.quest, guide, step, offer, si, gi) end
                            end
                        end
                    end
                end
            end
        end
    end
    for child, parents in pairs(self.QuestCleanupData.prerequisites) do
        for _, parent in ipairs(parents) do edge(child, parent) end
    end
    cache = result
    return result
end

local function remainingChapters(self, index, start)
    local cursors, queue = {}, {start}
    local position = 1
    while position <= #queue do
        local guide = queue[position]
        position = position + 1
        if not cursors[guide.id] then
            if not guide.steps[1] or not guide.steps[1].goals then return end
            local saved = self.char.progress[guide.id]
            if saved and (saved.review or type(saved.cursor) ~= "number" or saved.cursor < 1
                or saved.cursor > #guide.steps+1 or saved.cursor ~= math.floor(saved.cursor)) then return end
            cursors[guide.id] = saved and saved.cursor or 1
            local links = guide.nextChoices or guide.next
            if type(links) == "string" then links = {links} end
            for _, target in ipairs(links or {}) do
                if not self.guides[target] then return end
                if index.guides[target] and not cursors[target] then queue[#queue+1] = index.guides[target] end
            end
        end
    end
    return cursors
end

local function omission(self, row, inLog)
    local goal = row.goal
    local reason = self:GetLevelingDetourReason(goal)
    if reason then return reason end
    reason = self:GetGroupDeferralReason(goal, row.step, row.guide, row.gi, inLog)
    if reason then return reason end
    -- The engine continues ordinary optional objectives once accepted.
    if goal.optional and not inLog and not self.char.optional then return "Opcional desactivada." end
end

local function closure(edges, reached, pendingQuest)
    local stack = {}
    for id in pairs(reached) do stack[#stack+1] = id end
    while #stack > 0 do
        local id = table.remove(stack)
        for other in pairs(edges[id] or {}) do
            if not reached[other] and pendingQuest(other) then
                reached[other] = true
                stack[#stack+1] = other
            end
        end
    end
end

function ns:GetQuestCleanupPlan()
    local char = self.char
    local guide = char and self.guides[char.activeGuide]
    if not guide or guide.temporary or guide.recovery or not char.progress then return nil, "Selecciona tu guía de leveo." end
    if not self.QuestCleanupData or not self.QuestCleanupData.ordinary or not self.QuestCleanupData.prerequisites then
        return nil, "Faltan los datos de misiones de RutaXP."
    end
    local _, class = UnitClass("player")
    local _, race = UnitRace("player")
    local faction = UnitFactionGroup("player")
    if not class or not race or not faction or not applies(self, guide, faction) then return nil, "Revisa la guía activa para tu personaje." end
    local journal, errorText = self:GetQuestCleanupJournal()
    if not journal then return nil, errorText end
    local index = catalog(self, faction, race, class)
    local cursors = remainingChapters(self, index, guide)
    if not cursors then return nil, "Necesitas una ruta completa y salir de la revisión de pasos." end
    local plan = {guideID=guide.id, step=cursors[guide.id], candidates={}, kept={}, review={}}
    local logged, relevant, keep, proposed, review = {}, {}, {}, {}, {}
    local duo = char.duo and char.duo.enabled and self.Duo
    local function pending(id) return logged[id] ~= nil or not self:IsQuestDelivered(id) end
    for _, entry in ipairs(journal) do
        local id = entry.id
        logged[id], relevant[id] = entry, true
        local reason = entry.protectedReason
        if entry.complete then reason = "Lista para entregar."
        elseif entry.hasProgress then reason = "Ya tienes progreso en sus objetivos."
        elseif entry.canAbandon ~= true then reason = reason or "El cliente no confirma que se pueda abandonar." end
        if not reason and duo then
            local shared = duo:GetPartnerQuest(id)
            if shared and (shared.state == 1 or shared.state == 2) then reason = "También está en el diario de tu compañero." end
        end
        if not reason and self.GetLevelingQuestRewardInfo and self:GetLevelingQuestRewardInfo(id) then reason = "Recompensa útil para tu personaje." end
        keep[id] = reason or index.special[id]
    end
    -- Only ask live policy questions for quests which can affect this journal.
    -- This includes indirect dependencies through quests outside the itinerary.
    closure(index.children, relevant, pending)
    for id in pairs(relevant) do
        local onRoute, needed, excluded = false, false, nil
        for _, row in ipairs(index.rows[id] or {}) do
            local cursor = cursors[row.guide.id]
            if cursor and row.si >= cursor then
                onRoute = true
                excluded = omission(self, row, logged[id] ~= nil)
                if not excluded then needed = true; break end
            end
        end
        if needed then keep[id] = keep[id] or "Se usa en un paso pendiente de la guía."
        elseif logged[id] and not keep[id] then
            if onRoute then proposed[id] = excluded
            elseif self.QuestCleanupData.ordinary[id] then proposed[id] = "Misión ordinaria fuera de los pasos pendientes."
            else review[id] = "Fuera de la ruta pendiente y sin clasificación suficiente." end
        end
    end
    local required = {}
    for id in pairs(keep) do required[id] = true end
    for id in pairs(review) do required[id] = true end
    closure(index.parents, required, pending)
    for _, entry in ipairs(journal) do
        local id, list, reason = entry.id
        if keep[id] then list, reason = plan.kept, keep[id]
        elseif review[id] then list, reason = plan.review, review[id]
        elseif required[id] then list, reason = plan.kept, "Requisito de una misión que se conserva."
        else list, reason = plan.candidates, proposed[id] end
        list[#list+1] = {id=id, title=entry.title, reason=reason}
    end
    return plan
end
