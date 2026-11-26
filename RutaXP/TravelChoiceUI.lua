local _, ns = ...

-- Keep only the chosen quest IDs and the original departure. The guide cursor,
-- objective counters and the partner's route are still owned by their engines.
local function sameDeparture(saved, guide, state)
    return type(saved) == "table" and saved.guideID == guide.id
        and saved.revision == (guide.routeRevision or 1) and saved.cursor == state.cursor
        and type(saved.quests) == "table" and type(saved.key) == "string"
end
local function saveChoice(char, guide, state, key, quests)
    local saved = {key=key, guideID=guide.id, revision=guide.routeRevision or 1,cursor=state.cursor,quests=quests}
    char.localTravelChoice = saved
    return saved
end

function ns:GetTravelComparison()
    if not self.TravelChoice or not self.char then return end
    local guide, step, state = self:GetCurrent()
    if not guide or not state or state.review or guide.recovery then return end
    local travel = self.GetGuideTravel and self:GetGuideTravel()
    local saved = self.char.localTravelChoice
    if saved and not sameDeparture(saved, guide, state) then
        self.char.localTravelChoice = nil
        saved = nil
    end
    local choice = self.TravelChoice:GetRecommendation(guide, step, state, travel, saved and saved.key)
    if not choice then return end
    local shared = self.DuoAuto and self.DuoAuto:GetSharedView()
    if shared and shared.following then return end
    if self.Duo and self.Duo:GetMeetingWaypoint() then return end
    if self.DuoPlanner and self.DuoPlanner.focus and self.DuoPlanner:GetNavigationOverride() then return end
    if not saved and next(choice.enRoute or {}) and self.char.auto and not (self.char.duo and self.char.duo.enabled)
        and not (self.IsRecoveringCorpse and self:IsRecoveringCorpse())
        and not (self.DungeonPlanner and self.DungeonPlanner:IsDetouring())
        and not (InCombatLockdown and InCombatLockdown()) and self.char.dismissedTravelChoice ~= choice.key then
        local quests = {}
        for id in pairs(choice.enRoute) do quests[id] = true end
        saved = saveChoice(self.char,guide,state,choice.key,quests)
        saved.actions = choice.enRoute
    end
    if not saved then return choice end
    if saved.key ~= choice.key then
        self.char.localTravelChoice = nil
        return choice
    end
    for _, entry in ipairs(choice.localGoals or {}) do
        local expected = saved.actions and saved.actions[entry.quest]
        local action = entry.goal.t == "kill" and "kill:"..(entry.goal.oi or 1) or entry.goal.t
        if saved.quests[entry.quest] and entry.point and (not expected or expected == action) then return choice, entry end
    end
    -- Journal data and map positions can be briefly unavailable after a reload.
    -- A turn-in/removal or a changed departure ends the saved choice.
    return choice
end

function ns:ChooseLocalQuests(key)
    local choice = self:GetTravelComparison()
    if not choice or choice.key ~= key or not choice.localGoals or not choice.localGoals[1] then return false end
    local guide, _, state = self:GetCurrent()
    local quests = {}
    for _, entry in ipairs(choice.localGoals) do
        if entry.quest and entry.point then quests[entry.quest] = true end
    end
    if not next(quests) then return false end
    saveChoice(self.char,guide,state,key,quests)
    self:RefreshUI()
    self:UpdateNavigation()
    return true
end

function ns:ResumeTravelChoice(key)
    local saved = self.char and self.char.localTravelChoice
    if type(saved) ~= "table" or saved.key ~= key then return false end
    self.char.localTravelChoice, self.char.dismissedTravelChoice = nil, key
    self:RefreshUI()
    self:UpdateNavigation()
    return true
end

function ns:GetLocalTravelPoint(entry)
    if not entry or not entry.point then return end
    local p = {}
    for k, v in pairs(entry.point) do p[k] = v end
    p.goal, p.label = entry.goal, entry.title
    p.guideID, p.stepIndex, p.goalIndex = entry.guide.id, entry.stepIndex, entry.index
    p.source = "local-travel-choice"
    p.targetKey = table.concat({p.source, p.guideID, p.stepIndex, p.goalIndex}, ":")
    return p
end

local journal = CreateFrame("Frame")
journal:RegisterEvent("QUEST_REMOVED")
journal:RegisterEvent("QUEST_TURNED_IN")
journal:RegisterEvent("QUEST_LOG_UPDATE")
journal:SetScript("OnEvent", function(_, event, questID)
    local saved = ns.char and ns.char.localTravelChoice
    if type(saved) ~= "table" or type(saved.quests) ~= "table" then return end
    if event == "QUEST_LOG_UPDATE" then
        for id, action in pairs(saved.actions or {}) do
            local index = type(action) == "string" and tonumber(action:match("^kill:(%d+)$"))
            if index and C_QuestLog and C_QuestLog.GetQuestObjectives then
                local ok, finished = pcall(function()
                    local obj = (C_QuestLog.GetQuestObjectives(id) or {})[index]
                    return C_QuestLog.IsComplete(id) or (obj and obj.finished)
                end)
                if ok and not (issecretvalue and issecretvalue(finished)) and finished == true then saved.quests[id] = nil end
            end
        end
    elseif saved.quests[questID] then
        saved.quests[questID] = nil
    end
    if not next(saved.quests) then ns.char.localTravelChoice = nil end
end)
