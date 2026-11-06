local _, ns = ...

-- Westfall revision 2 moves Alba's mine investigation after its two real
-- prerequisites. Stored indices must continue to refer to the same actions.
local WEST = "forever/alliance/02-westfall"
local REVISION = 2
local CHAIN = { [92742] = true, [92744] = true, [92745] = true }
local steps = { 1, 2, 3, 4, 5, 8, 9, 6, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23 }
local special = { ["1:11"] = "7:3", ["12:5"] = "7:1", ["12:6"] = "7:2",
    ["12:7"] = "13:5", ["12:8"] = "13:6", ["12:9"] = "13:7" }

local function copy(value, seen)
    if type(value) ~= "table" then return value end
    seen = seen or {}
    if seen[value] then return seen[value] end
    local result = {}
    seen[value] = result
    for key, item in pairs(value) do result[key] = copy(item, seen) end
    return result
end

local function stepIndex(value)
    local index = tonumber(value) or 1
    return steps[index] or index
end

-- Historical checkpoints retain their original revision. Only their own
-- cursor is translated when missing local progress is explicitly restored.
function ns:GetGuideCursorForRevision(id, cursor, revision)
    local guide = self.guides[id]
    if id == WEST and guide and guide.routeRevision == REVISION and (tonumber(revision) or 1) < REVISION then
        return stepIndex(cursor)
    end
    return cursor
end

local function goalKey(key)
    if type(key) ~= "string" then return key end
    if special[key] then return special[key] end
    local step, goal = key:match("^(%d+):(%d+)$")
    return step and (tostring(stepIndex(step)) .. ":" .. goal) or key
end

local function remapMarks(marks)
    if type(marks) ~= "table" then return marks end
    local result = {}
    for key, value in pairs(marks) do result[goalKey(key)] = value end
    return result
end

local waypointPattern = WEST:gsub("(%W)", "%%%1") .. ":(%d+):(%d+)"
local function waypointKey(key)
    if type(key) ~= "string" then return key end
    return (key:gsub(waypointPattern, function(step, goal)
        return WEST .. ":" .. goalKey(step .. ":" .. goal)
    end))
end

local function remapWaypoints(saved)
    if type(saved) ~= "table" then return end
    for _, field in ipairs({ "ownRoutes", "entries" }) do
        if type(saved[field]) == "table" then
            local remapped = {}
            for key, value in pairs(saved[field]) do
                if type(value) == "table" then
                    if field == "ownRoutes" then value.id = waypointKey(value.id)
                    else value.targetKey = waypointKey(value.targetKey) end
                end
                remapped[waypointKey(key)] = value
            end
            saved[field] = remapped
        end
    end
    if type(saved.active) == "table" then
        for _, field in ipairs({ "key", "route", "entryKey" }) do
            saved.active[field] = waypointKey(saved.active[field])
        end
    end
end

local function readBoolean(api, ...)
    if type(api) ~= "function" then return nil end
    local ok, value = pcall(api, ...)
    if not ok or (issecretvalue and issecretvalue(value)) or type(value) ~= "boolean" then return nil end
    return value
end

local function questState(id)
    local active = readBoolean(C_QuestLog and C_QuestLog.IsOnQuest, id)
    local delivered = readBoolean(C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted, id)
    if delivered == nil then delivered = readBoolean(IsQuestFlaggedCompleted, id) end
    if active == nil or delivered == nil then return nil end
    if active and readBoolean(C_QuestLog and C_QuestLog.IsComplete, id) == nil then return nil end
    return { active = active, delivered = ns.turnedIn[id] == true or (not active and delivered) }
end

function ns:RepairWestfallMigration()
    local char = self.char
    local state = char and char.progress and char.progress[WEST]
    local guide = self.guides[WEST]
    if not guide or not state or not state.routeRepairPending then return false end
    -- A deferred read must never pull a player out of another selected route.
    if char.activeGuide ~= WEST or (char.recovery and char.recovery.active) then return false end
    local observed = {}
    for id in pairs(CHAIN) do
        observed[id] = questState(id)
        if not observed[id] then return false end
    end
    state.routeRepairPending = nil
    -- Holding the investigation already proves it was unlocked. Do not reopen
    -- its older prerequisites because of incomplete historical API data.
    if observed[92745].active or observed[92745].delivered then return false end
    local first
    local real = { cursor = state.cursor, confirmed = {}, skipped = {} }
    for step, visit in ipairs(guide.steps) do
        for index, goal in ipairs(visit.goals or {}) do
            local id = goal.quest or goal.questID
            if CHAIN[id] and self:MatchesConditions(visit.only) and self:MatchesConditions(goal.only) then
                local status = self:GetGoalStatus(goal, visit, real, index)
                if status ~= "done" and status ~= "skip" then
                    local key = tostring(step) .. ":" .. tostring(index)
                    if state.skipped then state.skipped[key] = nil end
                    if state.confirmed then state.confirmed[key] = nil end
                    first = first or step
                end
            end
        end
    end
    if not first then return false end
    state.cursor, state.review, state.placed = first, nil, true
    if self.DuoAuto and self.DuoAuto.RefreshProgressAgreement then self.DuoAuto:RefreshProgressAgreement() end
    if self.Duo then self.Duo.lastSentHeader = nil end
    self:Print("Corregido el orden de Alba: la guía retoma los requisitos pendientes y conserva tu progreso.")
    return true
end

local function oldMineRecovery(saved)
    if type(saved) ~= "table" or not saved.active or type(saved.bookmark) ~= "table"
        or saved.bookmark.guideID ~= WEST then return false end
    if saved.requestedQuestID == 92745 then return true end
    for _, id in ipairs(saved.requiredQuestIDs or {}) do if id == 92745 then return true end end
    return false
end

function ns:MigrateGuideProgress()
    local char, guide = self.char, self.guides[WEST]
    if not char or not guide or guide.routeRevision ~= REVISION then return end
    local state = char.progress[WEST]
    if type(state) ~= "table" or (tonumber(state.routeRevision) or 1) >= REVISION then return end
    local saved = type(char.recovery) == "table" and char.recovery or nil
    local bookmark = saved and type(saved.bookmark) == "table" and saved.bookmark.guideID == WEST and saved.bookmark or nil
    local recovery = oldMineRecovery(saved) and saved or nil
    local oldCursor = tonumber(bookmark and bookmark.cursor or state.cursor) or 1
    char.guideMigrationBackups = char.guideMigrationBackups or {}
    local backupKey = WEST .. ":" .. REVISION
    if not char.guideMigrationBackups[backupKey] then
        char.guideMigrationBackups[backupKey] = { progress = copy(state), activeGuide = char.activeGuide,
            recovery = bookmark and copy(saved), recoveryProgress = bookmark and copy(char.progress._recovery),
            waypoints = copy(char.waypoints), duoReview = copy(char.duo and char.duo.autoSession
                and char.duo.autoSession.reviews and char.duo.autoSession.reviews[WEST]) }
    end
    state.cursor = stepIndex(state.cursor)
    state.confirmed, state.skipped = remapMarks(state.confirmed), remapMarks(state.skipped)
    state.routeRevision = REVISION
    if bookmark then bookmark.cursor = stepIndex(bookmark.cursor) end
    remapWaypoints(char.waypoints)
    local lease = char.duo and char.duo.autoSession
    if lease and lease.reviews and type(lease.reviews[WEST]) == "table" then
        lease.reviews[WEST].cursor = stepIndex(lease.reviews[WEST].cursor)
    end
    if recovery then
        state.cursor, state.review = recovery.bookmark.cursor, recovery.bookmark.review
        char.activeGuide, char.recovery = WEST, nil
    end
    -- Completed chapters and their outgoing journeys keep the completed
    -- cursor. Merely having an inactive bookmark never changes selection.
    if oldCursor >= 6 and oldCursor <= 21 then
        state.routeRepairPending = true
        self:RepairWestfallMigration()
    end
end

local events = CreateFrame("Frame")
for _, event in ipairs({ "PLAYER_ENTERING_WORLD", "QUEST_LOG_UPDATE", "QUEST_DATA_LOAD_RESULT" }) do events:RegisterEvent(event) end
events:SetScript("OnEvent", function()
    if ns.initialized and ns:RepairWestfallMigration() then ns:Sync() end
end)
