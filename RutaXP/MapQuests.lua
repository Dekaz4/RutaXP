local _, ns = ...

local work = {collect=true, kill=true, complete=true, objective=true, interact=true,
    use=true, talk=true, buy=true, ["goto"]=true, travel=true}

local function read(api, ...)
    if type(api) ~= "function" then return nil end
    local ok, value = pcall(api, ...)
    if ok and not (issecretvalue and issecretvalue(value)) then return value end
end

local function onMap(raw, mapID)
    return raw and (raw.map or raw.mapID) == mapID
end

local function applies(self, entry, faction)
    return (not entry.faction or entry.faction == faction)
        and (not (entry.races or entry.classes or entry.factions) or self:MatchesConditions(entry))
        and self:MatchesConditions(entry.only)
end

local function onViewedMap(goal, mapID)
    if onMap(goal, mapID) or onMap(goal.waypoint, mapID) then return true end
    for _, candidate in ipairs(goal.candidates or {}) do
        if onMap(candidate, mapID) then return true end
    end
    return false
end

local function candidateApplies(self, candidate, faction, objectives)
    local side = faction == "Alliance" and "A" or faction == "Horde" and "H"
    if candidate.faction and candidate.faction ~= "AH" and candidate.faction ~= side
        and candidate.faction ~= faction then return false end
    local obj = type(objectives) == "table" and objectives[candidate.objectiveIndex]
    return not (type(obj) == "table" and not (issecretvalue and issecretvalue(obj))
        and not (issecretvalue and issecretvalue(obj.finished)) and obj.finished == true)
        and self:MatchesConditions(candidate) and self:MatchesConditions(candidate.only)
end

function ns:GetMapQuestPoints(mapID)
    local points, seen = {}, {}
    local char = self.char
    local guide = char and self.guides[char.activeGuide]
    local state = guide and char.progress and char.progress[guide.id]
    local faction = UnitFactionGroup("player")
    if not state or not applies(self, guide, faction) then return points end
    local cursor = state.cursor or 1
    if self.DuoAuto and self.DuoAuto.agreement then
        local view = self.DuoAuto:GetSharedView()
        if view and view.guideID == guide.id and view.following then cursor = view.sharedCursor end
    end
    local journal = {}
    local function add(raw, goal, id, category, detail)
        if not onMap(raw, mapID) then return end
        local p = self:ResolveWaypointPoint(raw)
        if not p or p.mapID ~= mapID then return end
        local key = table.concat({category, id, goal.oi or goal.objective or "", detail or "",
            math.floor(p.x*10000+.5), math.floor(p.y*10000+.5)}, "|")
        if seen[key] then return end
        seen[key] = true
        points[#points+1] = {category=category, questID=id, name=self:GetGoalTitle(goal),
            detail=detail, x=p.x, y=p.y}
    end
    local function visit(goal, step, si, gi)
        local id, action = goal.quest or goal.questID, goal.t or goal.action
        if not id or not (action == "accept" or action == "turnin" or work[action])
            or not onViewedMap(goal, mapID) or not applies(self, goal, faction) then return end
        if goal.navigationMode == "ability" or goal.navigationMode == "escort"
            or goal.navigationMode == "inventory" and (not goal.candidates or #goal.candidates == 0) then return end
        local q = journal[id]
        if not q then
            local active = self:IsQuestActive(id)
            q = {active=active, ready=active and read(C_QuestLog and C_QuestLog.IsComplete, id) == true}
            journal[id] = q
        end
        local category
        if action == "accept" then
            -- Only show pickups scheduled now or approved for the next visit.
            if q.active or si ~= cursor and not (si == cursor+1 and goal.npc and self.GetPlannedPickupAtNPC
                and self:GetPlannedPickupAtNPC(id, goal.npc, mapID)) then return end
            category = "accept"
        elseif not q.active then return
        elseif action == "turnin" then
            if not q.ready then return end
            category = "turnin"
        else
            if q.ready then return end
            category = "objective"
        end
        if self:GetGoalStatus(goal, step, state, gi, guide) ~= "active" then return end
        local detail = goal.npcName or goal.objName or goal.objectName or goal.target or goal.itemName
        if goal.waypoint or goal.x and goal.y then
            add(goal.waypoint or goal, goal, id, category, detail)
        else
            if goal.candidates and q.objectives == nil then
                q.objectives = read(C_QuestLog and C_QuestLog.GetQuestObjectives, id) or false
            end
            for _, candidate in ipairs(goal.candidates or {}) do
                if onMap(candidate, mapID) and candidateApplies(self, candidate, faction, q.objectives) then
                    add(candidate, goal, id, category, candidate.npcName or candidate.objName or detail)
                end
            end
        end
    end
    for si, step in ipairs(guide.steps) do
        if applies(self, step, faction) then
            for gi, goal in ipairs(step.goals or {step}) do visit(goal, step, si, gi) end
        end
    end
    return points
end
