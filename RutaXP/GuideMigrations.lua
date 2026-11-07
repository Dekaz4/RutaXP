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

local function migrationAt(guide, revision)
    for _, migration in ipairs(guide and guide.progressMigrations or {}) do
        if migration.from == revision and migration.to > revision then return migration end
    end
end

local function mapStep(migration, cursor)
    return (migration.stepMap or {})[tonumber(cursor)] or cursor
end

-- Historical checkpoints retain their original revision. Only their own
-- cursor is translated when missing local progress is explicitly restored.
function ns:GetGuideCursorForRevision(id, cursor, revision)
    local guide = self.guides[id]
    revision = tonumber(revision) or 1
    if id == WEST and guide and (guide.routeRevision or 1) >= REVISION and revision < REVISION then
        cursor, revision = stepIndex(cursor), REVISION
    end
    for _ = 1, 20 do
        local migration = migrationAt(guide, revision)
        if not migration then break end
        cursor, revision = mapStep(migration, cursor), migration.to
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
    if (tonumber(state.cursor) or 1) > #guide.steps then
        state.routeRepairPending = nil
        return false
    end
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

local function migrateWestfallLegacy(self)
    local char, guide = self.char, self.guides[WEST]
    if not char or not guide or (guide.routeRevision or 1) < REVISION then return end
    local state = char.progress[WEST]
    if type(state) ~= "table" or (tonumber(state.routeRevision) or 1) >= REVISION then return end
    local saved = type(char.recovery) == "table" and char.recovery or nil
    local bookmark = saved and type(saved.bookmark) == "table" and saved.bookmark.guideID == WEST and saved.bookmark or nil
    local recovery = oldMineRecovery(saved) and saved or nil
    local runningRecovery = bookmark and saved.active and char.activeGuide == "_recovery"
    local oldCursor = tonumber(runningRecovery and bookmark.cursor or state.cursor) or 1
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
        if runningRecovery then
            state.cursor, state.review = recovery.bookmark.cursor, recovery.bookmark.review
            char.activeGuide = WEST
        end
        char.recovery = nil
    end
    -- Completed chapters and their outgoing journeys keep the completed
    -- cursor. Merely having an inactive bookmark never changes selection.
    if oldCursor >= 6 and oldCursor <= 21 then
        state.routeRepairPending = true
    end
end

local function revisedKey(migration, key)
    if migration.retiredGoalKeys and migration.retiredGoalKeys[key] then return nil end
    return (migration.goalMap or {})[key] or key
end

local function revisedMarks(migration, marks)
    if type(marks) ~= "table" then return marks end
    local result = {}
    for key, value in pairs(marks) do
        local destination = revisedKey(migration, key)
        if destination then result[destination] = value end
    end
    return result
end

local function reviseWaypoints(saved, id, migration)
    if type(saved) ~= "table" then return end
    local pattern = id:gsub("(%W)", "%%%1") .. ":(%d+):(%d+)"
    local function key(value)
        if type(value) ~= "string" then return value end
        local retired = false
        local mapped = value:gsub(pattern, function(step, goal)
            local destination = revisedKey(migration, step .. ":" .. goal)
            if destination then return id .. ":" .. destination end
            retired = true
        end)
        if not retired then return mapped end
    end
    for _, field in ipairs({ "ownRoutes", "entries" }) do
        if type(saved[field]) == "table" then
            local mapped = {}
            for oldKey, value in pairs(saved[field]) do
                local newKey = key(oldKey)
                if newKey then
                    if type(value) == "table" then
                        if field == "ownRoutes" then value.id = key(value.id)
                        else value.targetKey = key(value.targetKey) end
                    end
                    mapped[newKey] = value
                end
            end
            saved[field] = mapped
        end
    end
    if type(saved.active) == "table" then
        for _, field in ipairs({ "key", "route", "entryKey" }) do
            local old = saved.active[field]
            saved.active[field] = key(old)
            if old and not saved.active[field] then saved.active = nil; break end
        end
    end
end

local function applyMigration(self, id, state, migration)
    local char = self.char
    local saved = type(char.recovery) == "table" and char.recovery or nil
    local bookmark = saved and type(saved.bookmark) == "table" and saved.bookmark.guideID == id and saved.bookmark
    local runningRecovery = bookmark and saved.active and char.activeGuide == "_recovery"
    local oldCursor = tonumber(runningRecovery and bookmark.cursor or state.cursor) or 1
    local affected = {}
    for _, q in ipairs(migration.affectedQuestIDs or {}) do affected[q] = true end
    char.guideMigrationBackups = char.guideMigrationBackups or {}
    local backupKey = id .. ":" .. migration.to
    if not char.guideMigrationBackups[backupKey] then
        char.guideMigrationBackups[backupKey] = { progress=copy(state), activeGuide=char.activeGuide,
            recovery=bookmark and copy(saved), recoveryProgress=bookmark and copy(char.progress._recovery),
            waypoints=copy(char.waypoints), duoReview=copy(char.duo and char.duo.autoSession
                and char.duo.autoSession.reviews and char.duo.autoSession.reviews[id]) }
    end
    state.cursor = mapStep(migration, state.cursor)
    state.confirmed, state.skipped = revisedMarks(migration, state.confirmed), revisedMarks(migration, state.skipped)
    state.routeRevision = migration.to
    if bookmark then bookmark.cursor = mapStep(migration, bookmark.cursor) end
    reviseWaypoints(char.waypoints, id, migration)
    local lease = char.duo and char.duo.autoSession
    if lease and lease.reviews and type(lease.reviews[id]) == "table" then
        lease.reviews[id].cursor = mapStep(migration, lease.reviews[id].cursor)
    end
    if bookmark and saved.active then
        local stale = affected[saved.requestedQuestID]
        for _, q in ipairs(saved.requiredQuestIDs or {}) do stale = stale or affected[q] end
        if stale then
            if runningRecovery then
                char.activeGuide = id
                state.cursor, state.review = bookmark.cursor, bookmark.review
            end
            char.recovery = nil
        end
    end
    -- Only affected chapters already reached by this character need repair.
    -- A completed chapter and its outgoing journey remain completed.
    if migration.firstAffectedStep and oldCursor >= migration.firstAffectedStep
        and oldCursor <= (migration.previousStepCount or 0) and next(affected) then
        state.requirementsRepair = state.requirementsRepair or {}
        for q in pairs(affected) do state.requirementsRepair[q] = true end
    end
end

local function unlockedParents(self, guide, observed)
    local requiredByChild, protected = {}, {}
    for _, step in ipairs(guide.steps) do
        if self:MatchesConditions(step.only) then
            for _, goal in ipairs(step.goals or {}) do
                local id = goal.quest or goal.questID
                local child = observed[id]
                if (goal.t or goal.action) == "accept" and child and (child.active or child.delivered)
                    and self:MatchesConditions(goal.only) then
                    local required = {}
                    for _, parent in ipairs(goal.preAll or {}) do
                        if parent > 0 then required[parent] = true end
                    end
                    if goal.pre and #goal.pre == 1 and goal.pre[1] > 0 then required[goal.pre[1]] = true end
                    -- Repeated applicable acceptances can have alternatives.
                    -- Only a parent required by every such acceptance is proven.
                    if requiredByChild[id] then
                        for parent in pairs(requiredByChild[id]) do
                            if not required[parent] then requiredByChild[id][parent] = nil end
                        end
                    else requiredByChild[id] = required end
                end
            end
        end
    end
    for _, parents in pairs(requiredByChild) do
        for parent in pairs(parents) do
            if observed[parent] and not observed[parent].active then protected[parent] = true end
        end
    end
    return protected
end

function ns:RepairGuideRequirements()
    local char = self.char
    local id = char and char.activeGuide
    local guide, state = id and self.guides[id], id and char.progress[id]
    if not guide or type(state) ~= "table" or type(state.requirementsRepair) ~= "table"
        or (char.recovery and char.recovery.active) then return false end
    -- Completion can happen while the client is still withholding quest data.
    -- A later response must not reopen the chapter or its outgoing journey.
    if (tonumber(state.cursor) or 1) > #guide.steps then
        state.requirementsRepair = nil
        return false
    end
    local observed = {}
    for q in pairs(state.requirementsRepair) do
        observed[q] = questState(q)
        if not observed[q] then return false end
    end
    -- A real unlocked child proves its mandatory prerequisites were met even
    -- if older completion flags are missing. This only prevents migration
    -- rewind: it never invents delivery flags or hides an active parent quest.
    local protected = unlockedParents(self, guide, observed)
    local first
    local clean = { cursor=state.cursor, confirmed={}, skipped={} }
    for si, step in ipairs(guide.steps) do
        for gi, goal in ipairs(step.goals or {}) do
            local quest = goal.quest or goal.questID
            if state.requirementsRepair[quest] and not protected[quest] then
                local status = self:GetGoalStatus(goal, step, clean, gi)
                if status ~= "done" and status ~= "skip" then
                    local key = si .. ":" .. gi
                    if state.confirmed then state.confirmed[key] = nil end
                    if state.skipped then state.skipped[key] = nil end
                    first = first or si
                end
            end
        end
    end
    state.requirementsRepair = nil
    if not first then return false end
    -- Another chain repair may already have restored an earlier pending visit.
    -- A moved delivery ahead of that visit must never advance past it.
    state.cursor, state.review, state.placed = math.min(tonumber(state.cursor) or first, first), nil, true
    if self.DuoAuto and self.DuoAuto.RefreshProgressAgreement then self.DuoAuto:RefreshProgressAgreement() end
    if self.Duo then self.Duo.lastSentHeader = nil end
    self:Print("La guía conserva el recorrido y recupera las tareas pendientes de la cadena corregida.")
    return true
end

function ns:MigrateGuideProgress()
    if not self.char then return end
    migrateWestfallLegacy(self)
    for id, guide in pairs(self.guides) do
        local state = self.char.progress[id]
        if type(state) == "table" then
            for _ = 1, 20 do
                local migration = migrationAt(guide, tonumber(state.routeRevision) or 1)
                if not migration then break end
                applyMigration(self, id, state, migration)
            end
        end
    end
    self:RepairWestfallMigration()
    self:RepairGuideRequirements()
end

local events = CreateFrame("Frame")
for _, event in ipairs({ "PLAYER_ENTERING_WORLD", "QUEST_LOG_UPDATE", "QUEST_DATA_LOAD_RESULT" }) do events:RegisterEvent(event) end
events:SetScript("OnEvent", function()
    if not ns.initialized then return end
    local changed = ns:RepairWestfallMigration()
    changed = ns:RepairGuideRequirements() or changed
    if changed then ns:Sync() end
end)
