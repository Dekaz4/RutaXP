local _, ns = ...
local focus, byQuest = {}, nil
ns.WorldQuestFocus = focus
local lastProgress, observed, ignored = {}, nil, nil

local function index()
    if byQuest then return byQuest end
    byQuest = {}
    for _, id in ipairs(ns.order) do
        local guide = ns.guides[id]
        if not guide.temporary and not guide.recovery then
            for si, step in ipairs(guide.steps) do
                for gi, goal in ipairs(step.goals or {step}) do
                    local q = goal.quest or goal.questID
                    local kind = goal.t or goal.action
                    if q and kind ~= "accept" and kind ~= "note" then
                        local entries = byQuest[q] or {}
                        byQuest[q] = entries
                        entries[#entries+1] = {guide=guide, step=step, si=si, gi=gi, goal=goal}
                    end
                end
            end
        end
    end
    return byQuest
end

function focus.Match(id, current, map)
    if not id or not ns.RestedQuestState.Active(id) then return end
    local ready = ns.RestedQuestState.Ready(id)
    local objectives = C_QuestLog.GetQuestObjectives and C_QuestLog.GetQuestObjectives(id)
    local best, score = nil, -math.huge
    for _, entry in ipairs(index()[id] or {}) do
        local g, s, goal = entry.guide, entry.step, entry.goal
        local objective = objectives and objectives[goal.oi or goal.objective]
        if ((goal.t or goal.action) == "turnin") == ready and not (objective and objective.finished)
            and (not g.faction or g.faction == "Both" or g.faction == "Neutral" or g.faction == UnitFactionGroup("player"))
            and ns:MatchesConditions(g.only) and ns:MatchesConditions(s.only) and ns:MatchesConditions(goal.only) then
            local rank = (g == current and 100 or 0) + ((goal.map or s.map or g.zone) == map and 50 or 0)
            if g == current then rank = rank - math.min(40, math.abs(entry.si - ns:GetProgress(g.id).cursor)) end
            if rank > score then best, score = entry, rank end
        end
    end
    return best
end

-- Choose a first cursor from real journal work in the recommended chapter.
-- This is only used when the character has no RutaXP chapter to restore.
function focus.StartingStep(guide)
    if not (C_QuestLog.GetInfo and C_QuestLog.GetNumQuestLogEntries) then return end
    local map = C_Map.GetBestMapForUnit("player")
    local best, bestScore
    for i = 1, C_QuestLog.GetNumQuestLogEntries() do
        local info = C_QuestLog.GetInfo(i)
        if info and not info.isHeader and info.questID then
            local match = focus.Match(info.questID, guide, map)
            if match and match.guide == guide then
                local rank = (match.goal.map or match.step.map or guide.zone) == map and 2 or 1
                if not best or rank > bestScore or rank == bestScore and match.si < best then
                    best,bestScore = match.si,rank
                end
            end
        end
    end
    return best
end

local function reportable(id)
    return type(id) == "number" and not (issecretvalue and issecretvalue(id)) and id > 0
end

-- A changing quantity identifies the quest even when several are watched.
-- Loading a character or expanding a journal header is not an objective gain.
function focus.Observe()
    if not (C_QuestLog.GetInfo and C_QuestLog.GetNumQuestLogEntries and C_QuestLog.GetQuestObjectives) then return end
    local changed, active = nil, {}
    for i = 1, C_QuestLog.GetNumQuestLogEntries() do
        local info = C_QuestLog.GetInfo(i)
        local id = info and not info.isHeader and info.questID
        if reportable(id) then
            local quantities = {}
            for n, obj in ipairs(C_QuestLog.GetQuestObjectives(id) or {}) do
                local value = obj.numFulfilled
                if not (issecretvalue and issecretvalue(value)) then
                    quantities[n] = tonumber(value) or (obj.finished and 1 or 0)
                    if lastProgress[id] and lastProgress[id][n] and quantities[n] > lastProgress[id][n] then changed = id end
                end
            end
            active[id] = quantities
        end
    end
    lastProgress = active
    if changed then observed, ignored = changed, nil end
end

function focus.Current()
    local super = C_SuperTrack and C_SuperTrack.GetSuperTrackedQuestID and C_SuperTrack.GetSuperTrackedQuestID()
    for _, id in ipairs({observed or 0, reportable(super) and super or 0}) do
        if id > 0 and id ~= ignored and ns.RestedQuestState.Active(id) then
            local current, step, state = ns:GetCurrent()
            local goal = step and ns:GetActiveGoal(step, state)
            if goal and (goal.quest or goal.questID) == id then return end
            local match = focus.Match(id, current, C_Map.GetBestMapForUnit("player"))
            if match or (ns.DungeonQuestData.restedWorld or {})[id] then return id, match end
        end
    end
end

function focus.Clear(id)
    ignored = id
    observed = nil
end

function focus.Point(id, match)
    local map, x, y
    if C_QuestLog.GetNextWaypoint then map, x, y = C_QuestLog.GetNextWaypoint(id) end
    if map and x and y and not (issecretvalue and (issecretvalue(map) or issecretvalue(x) or issecretvalue(y)))
        and map > 0 and x >= 0 and x <= 1 and y >= 0 and y <= 1 then return {mapID=map,x=x,y=y} end
    if match then
        local point = ns:GetGoalWaypoint(match.goal)
        if point then return point end
    end
    local targets = ns.DungeonQuestData.restedTargets
    local route = targets and targets[id]
    if not route then return end
    local kind = ns.RestedQuestState.Ready(id) and "turnin" or "work"
    local point = route[kind]
    if point and (not point.faction or point.faction == UnitFactionGroup("player")) then
        if point.objectiveIndex then
            local objectives = C_QuestLog.GetQuestObjectives and C_QuestLog.GetQuestObjectives(id)
            local objective = objectives and objectives[point.objectiveIndex]
            if not objective or objective.finished then return end
        end
        return ns:ResolveWaypointPoint(point)
    end
end
