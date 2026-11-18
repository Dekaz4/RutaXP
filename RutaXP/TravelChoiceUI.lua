local _, ns = ...

-- Keep only the chosen quest IDs and the original departure. The guide cursor,
-- objective counters and the partner's route are still owned by their engines.
local function sameDeparture(saved, guide, state)
    return type(saved) == "table" and saved.guideID == guide.id
        and saved.revision == (guide.routeRevision or 1) and saved.cursor == state.cursor
        and type(saved.quests) == "table" and type(saved.key) == "string"
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
    if not saved then return choice end
    if saved.key ~= choice.key then
        self.char.localTravelChoice = nil
        return choice
    end
    for _, entry in ipairs(choice.localGoals or {}) do
        if saved.quests[entry.quest] and entry.point then return choice, entry end
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
    self.char.localTravelChoice = {key=key, guideID=guide.id, revision=guide.routeRevision or 1,
        cursor=state.cursor, quests=quests}
    self:RefreshUI()
    self:UpdateNavigation()
    return true
end

function ns:ResumeTravelChoice(key)
    local saved = self.char and self.char.localTravelChoice
    if type(saved) ~= "table" or saved.key ~= key then return false end
    self.char.localTravelChoice = nil
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
journal:SetScript("OnEvent", function(_, _, questID)
    local saved = ns.char and ns.char.localTravelChoice
    if type(saved) ~= "table" or type(saved.quests) ~= "table" or not saved.quests[questID] then return end
    saved.quests[questID] = nil
    if not next(saved.quests) then ns.char.localTravelChoice = nil end
end)
