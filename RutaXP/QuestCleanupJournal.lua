local _, ns = ...

local unreadable = "El cliente no ha podido verificar el estado de esta misión."
local incomplete = "No se ha podido leer todo el diario. Vuelve a intentarlo cuando se actualice."

local function public(value)
    if issecretvalue and issecretvalue(value) then error(unreadable, 0) end
    return value
end

local function integer(value)
    public(value)
    if type(value) ~= "number" or value < 0 or value >= math.huge or value ~= math.floor(value) then
        error(unreadable, 0)
    end
    return value
end

local function boolean(value)
    if type(public(value)) ~= "boolean" then error(unreadable, 0) end
    return value
end

local function hasObjectiveProgress(id)
    local count = integer(C_QuestLog.GetNumQuestObjectives(id))
    local objectives = public(C_QuestLog.GetQuestObjectives(id))
    if count == 0 or type(objectives) ~= "table" or #objectives ~= count then return nil end
    local known = true
    for i = 1, count do
        local objective = public(objectives[i])
        if boolean(objective.finished) or integer(objective.numFulfilled) > 0 then return true end
        if integer(objective.numRequired) == 0 then known = false end
    end
    if known then return false end
end

local function readState(row, info, classHeader)
    local id = row.id
    row.canAbandon = boolean(C_QuestLog.CanAbandonQuest(id))
    row.complete = boolean(C_QuestLog.IsComplete(id))
    local ready = public(C_QuestLog.ReadyForTurnIn(id))
    if ready ~= nil and boolean(ready) then row.complete = true end
    if row.complete then return "Lista para entregar." end
    if not row.canAbandon then return "El juego impide abandonar esta misión." end
    if classHeader then return "Misión de clase." end
    if row.internal or boolean(info.isStory) or integer(public(info.campaignID) or 0) > 0 then
        return "Misión especial, de historia o interna del juego."
    end
    local tag = public(C_QuestLog.GetQuestTagInfo(id))
    if tag and integer(public(tag.tradeskillLineID) or 0) > 0 then return "Misión de profesión." end
    if GetQuestLogSpecialItemInfo and public(GetQuestLogSpecialItemInfo(row.index)) then
        return "Tiene un objeto de misión asociado."
    end
    row.hasProgress = hasObjectiveProgress(id)
    if row.hasProgress == nil then return "El cliente no muestra un progreso verificable." end
    if row.hasProgress then return "Ya tienes progreso en sus objetivos." end
end

local function readJournal()
    local entries, total = C_QuestLog.GetNumQuestLogEntries()
    integer(entries)
    integer(total)
    local rows, seen = {}, {}
    local journalSlots = 0
    local class, token
    if UnitClass then class, token = UnitClass("player") end
    public(class)
    public(token)
    local male = LOCALIZED_CLASS_NAMES_MALE and LOCALIZED_CLASS_NAMES_MALE[token]
    local female = LOCALIZED_CLASS_NAMES_FEMALE and LOCALIZED_CLASS_NAMES_FEMALE[token]
    local header, classHeader
    -- Forever filters collapsed headers when drawing buttons. GetInfo still
    -- enumerates their quests, so scanning does not change the player's journal.
    for index = 1, entries do
        local info = public(C_QuestLog.GetInfo(index))
        local title = public(info.title)
        if type(title) ~= "string" or title == "" then return nil, incomplete end
        if boolean(info.isHeader) then
            header = title
            classHeader = title == class or title == male or title == female
        else
            local id = integer(info.questID)
            if id == 0 or seen[id] then return nil, incomplete end
            seen[id] = true
            local row = { id = id, index = index, title = title, header = header }
            row.internal = boolean(info.isHidden) or boolean(info.isInternalOnly)
                or boolean(info.isTask) or boolean(info.isBounty)
            if not row.internal then journalSlots = journalSlots + 1 end
            local ok, reason = pcall(readState, row, info, classHeader)
            if ok then row.protectedReason = reason else row.protectedReason = unreadable end
            rows[#rows + 1] = row
        end
    end
    -- Internal entries must never compensate for a missing player quest.
    if journalSlots ~= total then return nil, incomplete end
    return rows
end

function ns:GetQuestCleanupJournal()
    local ok, rows, reason = pcall(readJournal)
    if ok and rows then return rows end
    return nil, reason or incomplete
end
