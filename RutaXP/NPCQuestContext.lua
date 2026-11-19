local _, ns = ...

local function readable(fn, ...)
    if type(fn) ~= "function" then return end
    local ok, value = pcall(fn, ...)
    if ok and not (issecretvalue and issecretvalue(value)) then return value end
end

-- A nil result means the menu could not be read, not that it has no offers.
local function menuOffers(kind, detailID)
    local offers = {}
    if kind == "QUEST_DETAIL" then
        if not detailID or detailID ~= readable(GetQuestID) then return end
        offers[detailID] = true
    elseif kind == "QUEST_GREETING" then
        local count = readable(GetNumAvailableQuests)
        if type(count) ~= "number" or count < 0 or count > 100 then return end
        for i = 1, count do
            local ok, _, _, _, _, id = pcall(GetAvailableQuestInfo, i)
            if not ok or (issecretvalue and issecretvalue(id)) or type(id) ~= "number" or id <= 0 then return end
            offers[id] = true
        end
    elseif kind == "GOSSIP_SHOW" then
        local list = readable(C_GossipInfo and C_GossipInfo.GetAvailableQuests)
        if type(list) ~= "table" then return end
        for _, info in ipairs(list) do
            if (issecretvalue and issecretvalue(info)) or type(info) ~= "table" then return end
            local id = info.questID
            if (issecretvalue and issecretvalue(id)) or type(id) ~= "number" or id <= 0 then return end
            offers[id] = true
        end
    else
        return
    end
    return offers
end

function ns:IsQuestOnOpenMenu(id, npc)
    if not npc or self:GetQuestContactNPC() ~= npc then return false end
    for _, kind in ipairs({"QUEST_DETAIL", "GOSSIP_SHOW", "QUEST_GREETING"}) do
        local offers = menuOffers(kind, id)
        if offers and offers[id] then return true end
    end
    return false
end

local function journal(id)
    if ns.turnedIn[id] == true then return "delivered" end
    local active = readable(C_QuestLog and C_QuestLog.IsOnQuest, id)
    if active == true then
        if readable(C_QuestLog and C_QuestLog.IsComplete, id) == true then return "ready" end
        return "carried"
    end
    if active ~= false then return end
    local delivered = readable(C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted, id)
    if delivered == nil then delivered = readable(IsQuestFlaggedCompleted, id) end
    if delivered == true then return "delivered" end
    if delivered == false then return "missing" end
end

local function title(id, fallback)
    local name = readable(C_QuestLog and C_QuestLog.GetTitleForQuestID, id)
    return "«" .. (type(name) == "string" and name ~= "" and name or fallback or ("Misión " .. id)) .. "»"
end

-- Index once per immutable chapter, filtering character conditions at use time.
local indices = setmetatable({}, {__mode="k"})
local function indexFor(guide)
    if indices[guide] then return indices[guide] end
    local data = {quests={}, contacts={}}
    for si, step in ipairs(guide.steps) do
        for gi, goal in ipairs(step.goals or {step}) do
            local id = goal.quest or goal.questID
            if id then
                local row = {goal=goal, step=step, s=si, g=gi, action=goal.t or goal.action}
                local list = data.quests[id] or {}
                data.quests[id] = list
                list[#list+1] = row
                if goal.npc and row.action == "accept" then
                    list = data.contacts[goal.npc] or {}
                    data.contacts[goal.npc] = list
                    list[#list+1] = row
                end
            end
        end
    end
    indices[guide] = data
    return data
end

local function applicable(row)
    return ns:MatchesConditions(row.step.only) and ns:MatchesConditions(row.goal.only)
end

local function sourceFor(rows, guide, state)
    local source
    for _, row in ipairs(rows or {}) do
        if row.action == "accept" and applicable(row) then
            local goal = row.goal
            local status = ns:GetGoalStatus(goal, row.step, state, row.g, guide)
            if status == "active" then
                if goal.item or goal.navigationMode == "inventory" or not (goal.object or goal.npc) or not (goal.map and goal.x and goal.y)
                    or goal.candidates or goal.spots then return end
                if source and (source.object ~= goal.object or source.npc ~= goal.npc or source.map ~= goal.map
                    or source.x ~= goal.x or source.y ~= goal.y or source.f ~= goal.f) then return end
                source = source or goal
            end
        end
    end
    return source
end

local function hasReturn(rows, npc)
    for _, row in ipairs(rows or {}) do
        if row.action == "turnin" and applicable(row) and row.goal.npc == npc then return true end
    end
    return false
end

local function commonWork(rows, previous)
    local steps = {}
    for _, row in ipairs(rows or {}) do
        if (row.action == "collect" or row.action == "kill" or row.action == "complete") and applicable(row)
            and (not previous or previous[row.s]) then steps[row.s] = true end
    end
    return steps
end

local function parentAdvice(child, parents, offers, npc, guide, state, data, localErrandsOnly)
    local accept, carry, other = {}, {}, {}
    local marker, work, together, pending = nil, nil, true, 0
    for _, id in ipairs(parents) do
        if id <= 0 then return end
        local status = journal(id)
        if not status then return end
        if status ~= "delivered" then
            pending = pending + 1
            local rows = data.quests[id]
            local name = title(id, (child.preTitles or {})[id] or (rows and rows[1].goal.title))
            local here = hasReturn(rows, npc)
            work = commonWork(rows, work)
            if not here then together = false end
            if status == "ready" and here then
                other[#other+1] = "Entrega " .. name .. " aquí."
                together = false
            elseif status == "carried" or status == "ready" then
                carry[#carry+1] = name
            elseif offers[id] then
                -- The open menu proves an offer exists; keep manual choices,
                -- profession/class gates and optional/timed pickup rules.
                local _, kind = ns:GetQuestOfferAdvice(id)
                if kind ~= "ahora" then return end
                accept[#accept+1] = name
            else
                together = false
                local source = sourceFor(rows, guide, state)
                local place = source and (source.objName or source.npcName)
                if place and source.npc ~= npc then
                    if source.object then
                        other[#other+1] = "Busca «" .. place .. "» y acepta " .. name .. "."
                    else
                        other[#other+1] = "Acepta " .. name .. " con " .. place .. "."
                    end
                    if not marker or (source.object and not marker.object) then marker = source end
                else
                    other[#other+1] = "Te falta " .. name .. "."
                end
            end
        end
    end
    if pending == 0 then return end
    if localErrandsOnly and (not together or not work or not next(work) or #carry == 0 or #accept == 0) then return end
    local lines = {}
    if #accept > 0 then lines[#lines+1] = "Acepta " .. table.concat(accept, " y ") .. "." end
    if #carry > 0 then lines[#lines+1] = "Ya llevas " .. table.concat(carry, " y ") .. "." end
    for _, text in ipairs(other) do lines[#lines+1] = text end
    if together and pending > 1 and work and next(work) then
        lines[#lines+1] = "Hazlas juntas y vuelve aquí para entregarlas."
    end
    if not localErrandsOnly then
        lines[#lines+1] = pending == 1
            and ("Es una previa de " .. title(child.quest or child.questID, child.title) .. ".")
            or ("Son previas de " .. title(child.quest or child.questID, child.title) .. ".")
    end
    return table.concat(lines, " "), marker
end

local function readableRequirements(goal)
    for _, ids in ipairs({goal.preAll or {}, goal.pre or {}}) do
        for _, id in ipairs(ids) do
            if not journal(math.abs(id)) then return false end
        end
    end
    return not goal.parent or journal(goal.parent) ~= nil
end

-- Only a pending acceptance at this exact contact, or a follow-up of the
-- current visit's quests, can explain a missing offer.
function ns:GetNPCQuestContext(npc, kind, detailID)
    local guide = self.char and self.guides[self.char.activeGuide]
    local state = guide and self.char.progress and self.char.progress[guide.id]
    local step = state and guide.steps[state.cursor]
    if not npc or not step or state.review or self:GetQuestContactNPC() ~= npc
        or (guide.faction and guide.faction ~= UnitFactionGroup("player"))
        or not self:MatchesConditions(guide) or not self:MatchesConditions(guide.only)
        or not self:MatchesConditions(step.only) or (self.GetGuideTravel and self:GetGuideTravel()) then return end
    if self.DuoAuto and self.DuoAuto.agreement then
        local view = self.DuoAuto:GetSharedView()
        if view and view.following then return end
    end
    local offers = menuOffers(kind, detailID)
    if not offers then return end
    local data, current = indexFor(guide), {}
    for _, goal in ipairs(step.goals or {step}) do
        local id = goal.quest or goal.questID
        if id and self:MatchesConditions(goal.only) then current[id] = true end
    end
    local fallback
    for _, row in ipairs(data.contacts[npc] or {}) do
        local child = row.goal
        local id = child.quest or child.questID
        if row.s >= state.cursor and applicable(row) and journal(id) == "missing" and not offers[id] then
            local parents = child.preAll or (#(child.pre or {}) == 1 and child.pre) or {}
            local relevant = row.s == state.cursor
            local relatedDetail = false
            for _, pre in ipairs(parents) do
                relevant = relevant or current[pre]
                relatedDetail = relatedDetail or detailID == pre
            end
            if relevant and (not detailID or relatedDetail) then
                local status, reason = self:GetGoalStatus(child, row.step, state, row.g, guide)
                local localErrands = status == "skip" and self.GetGroupDeferralReason
                    and self:GetGroupDeferralReason(child, row.step, guide, row.g) ~= nil
                if (status == "blocked" or localErrands) and #parents > 0 then
                    local text, marker = parentAdvice(child, parents, offers, npc, guide, state, data, localErrands)
                    if text then return text, marker end
                end
                if not detailID and row.s == state.cursor and not fallback then
                    if status == "blocked" and readableRequirements(child) then
                        fallback = title(id, child.title) .. ". " .. reason
                    elseif status == "blocked" then
                        fallback = "No se han podido comprobar las previas de " .. title(id, child.title) .. "."
                    elseif status == "active" then fallback = "El NPC aún no ofrece " .. title(id, child.title) .. "." end
                end
            end
        end
    end
    return fallback
end
