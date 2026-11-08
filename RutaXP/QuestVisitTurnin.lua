local _, ns = ...

-- Reviewed courier hand-ins. Approving a quest for early pickup alone does
-- not authorize finishing a timed, escort or PvP quest during another visit.
local courierRecipient = {
    [36] = 235,  -- Verna's recipe to Salma Saldean
    [109] = 234, -- Report to Gryan Stoutmantle
}

local function readyForNPC(questID, npcReady)
    if issecretvalue and issecretvalue(npcReady) then return false end
    if npcReady ~= nil then return npcReady == true end
    local api = C_QuestLog and C_QuestLog.IsComplete
    if type(api) ~= "function" then return false end
    local ok, value = pcall(api, questID)
    return ok and not (issecretvalue and issecretvalue(value)) and value == true
end

local function plannedContact(self, step, state, npcID)
    for i, goal in ipairs(step.goals or {step}) do
        local action = goal.t or goal.action
        if goal.npc == npcID and (action == "accept" or action == "turnin") and (goal.quest or goal.questID) then
            local status = self:GetGoalStatus(goal, step, state, i)
            -- A player can accept the scheduled quest first and still have
            -- the recipient's window open on this same step.
            if status == "active" or status == "done" then return true end
        end
    end
    return false
end

function ns:CanHandInDuringVisit(questID, npcID, npcReady)
    if issecretvalue and (issecretvalue(questID) or issecretvalue(npcID)) then return false end
    if type(npcID) ~= "number" or courierRecipient[questID] ~= npcID
        or not self.earlyQuestOffers or self.earlyQuestOffers[questID] ~= true then return false end
    local char = self.char
    local guide = char and self.guides[char.activeGuide]
    -- Reading the existing progress directly avoids initializing or migrating a save.
    local state = guide and char.progress and char.progress[guide.id]
    local cursor = state and state.cursor
    local step = type(cursor) == "number" and guide.steps[cursor]
    if not step or state.review or (self.GetGuideTravel and self:GetGuideTravel())
        or (guide.faction and guide.faction ~= UnitFactionGroup("player"))
        or not self:MatchesConditions(guide) or not self:MatchesConditions(guide.only)
        or not self:MatchesConditions(step.only) then return false end
    if not self:IsQuestActive(questID) or self:IsQuestDelivered(questID)
        or not readyForNPC(questID, npcReady) or not plannedContact(self, step, state, npcID)
        or self:ShouldWaitForEarlyQuest(step) then return false end
    for s = cursor + 1, #guide.steps do
        local later = guide.steps[s]
        for i, goal in ipairs(later.goals or {later}) do
            if (goal.t or goal.action) == "turnin" and (goal.quest or goal.questID) == questID
                and goal.npc == npcID and self:GetGoalStatus(goal, later, state, i) == "active" then return true end
        end
    end
    return false
end
