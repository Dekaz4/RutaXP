local _, ns = ...
local carry = {}
ns.GuideCarryover = carry

local live, firstID, focusID = {}, nil, nil
local sawUpdate, confirming, confirmed = false, nil, nil
local loading = "Esperando a que el juego cargue tus misiones en curso."

-- These records belong to this character. Neither a partner's progress nor
-- the old addon's log of accepted quests proves a quest is in today's diary.
local function journal()
    local api = C_QuestLog
    if not (api and api.GetNumQuestLogEntries and api.GetInfo) then return end
    local entries, expected = api.GetNumQuestLogEntries()
    if type(entries) ~= "number" or entries < 0 then return end
    local quests, count = {}, 0
    for index=1,entries do
        local info = api.GetInfo(index)
        if not info then return end
        if not info.isHeader then
            local id = info.questID
            if type(id) ~= "number" or id <= 0 or type(info.title) ~= "string" or info.title == "" then return end
            count = count + 1
            if not (info.isHidden or info.isInternalOnly or info.isTask or info.isBounty) then
                quests[id] = {id=id, index=index, title=info.title, objectives=api.GetQuestObjectives and api.GetQuestObjectives(id) or {},
                    ready=(api.ReadyForTurnIn and api.ReadyForTurnIn(id)) or (api.IsComplete and api.IsComplete(id))}
            end
        end
    end
    if type(expected) == "number" and count < expected then return end
    return quests
end

local function hasBoth(id)
    return GetNumGroupMembers and GetNumGroupMembers() == 2 and not (IsInRaid and IsInRaid())
        and (not UnitIsConnected or UnitIsConnected("party1"))
        and C_QuestLog.IsUnitOnQuest and C_QuestLog.IsUnitOnQuest("party1", id) == true
end

local function capture(char, chapter, quests)
    local here = ns.GuideResume.LegacyPosition(char)
    local order, batch = {}, {}
    local function rank(row, base)
        for j=2,#row do
            local id = row[j]
            if not order[id] then order[id] = base + j end
        end
    end
    if here then rank(here, 0) end
    local start = 1
    for i,row in ipairs(chapter) do if row == here then start = i; break end end
    for i=start,#chapter do rank(chapter[i], i*100+100) end
    for _,q in pairs(quests) do
        local relevant = order[q.id] or q.ready or hasBoth(q.id)
        for _,objective in ipairs(q.objectives) do
            if objective.finished or (tonumber(objective.numFulfilled) or 0)>0 then relevant = true; break end
        end
        if relevant then batch[#batch+1] = q.id end
    end
    if #batch == 0 then for id in pairs(quests) do batch[#batch+1] = id end end
    table.sort(batch, function(a,b)
        local left, right = order[a] or math.huge, order[b] or math.huge
        if left ~= right then return left < right end
        return quests[a].index < quests[b].index
    end)
    return batch
end

local function confirmEmpty(kind)
    if not sawUpdate then return false end
    if confirmed == kind then return true end
    if not confirming or confirming.kind ~= kind then
        local request = {kind=kind}
        confirming = request
        C_Timer.After(1, function()
            if confirming ~= request then return end
            confirmed = kind
            ns.GuideResume.Sync()
        end)
    end
    return false
end

function carry.Dismiss()
    if ns.char then ns.char.guideJournal = {done=true} end
    live, firstID, focusID, confirming, confirmed = {}, nil, nil, nil, nil
end

function carry.IsResuming()
    local char = ns.char
    if not char or (char.guideLink and char.guideLink.mode == "manual") then return false end
    if ns.GuideJourney and not ns.GuideJourney:Available() then return false end
    if char.guideJournal then return not char.guideJournal.done end
    return char.duo and char.duo.enabled and ns.legacyGuideAnchors and
        ns.legacyGuideAnchors[char.activeGuide] ~= nil or false
end

function carry.Check()
    if not carry.IsResuming() then return end
    local char = ns.char
    local state = char.guideJournal
    local ok, quests = pcall(journal)
    if not ok or not quests then
        confirming, confirmed = nil, nil
        return "pending", loading
    end
    if not state then
        if not next(quests) then
            if not confirmEmpty("initial") then return "pending", loading end
            carry.Dismiss()
            return
        end
        state = {ids=capture(char, ns.legacyGuideAnchors[char.activeGuide], quests)}
        char.guideJournal = state
    end
    local count
    live, firstID, count = quests, nil, 0
    for _,id in ipairs(state.ids) do
        if quests[id] then
            firstID = firstID or id
            count = count + 1
        end
    end
    if count == 0 then
        if not confirmEmpty("finished") then return "pending", loading end
        carry.Dismiss()
        return
    end
    confirming, confirmed = nil, nil
    if not live[focusID] then focusID = nil end
    return "journal", ("Misiones en curso (%d). Puedes seguirlas aquí o elegir una guía."):format(count)
end

function carry.Rows()
    local rows = {}
    local state = ns.char and ns.char.guideJournal
    for _,id in ipairs(state and state.ids or {}) do
        local q = live[id]
        if q then
            local suffix = q.ready and " · Lista para entregar" or ""
            if hasBoth(id) then suffix = suffix .. " · Activa para ambos" end
            rows[#rows+1] = {text=q.title .. suffix, questID=id}
            if not q.ready then
                for _,objective in ipairs(q.objectives) do
                    if type(objective.text) == "string" and objective.text ~= "" then
                        local text = objective.text
                        if type(objective.numRequired) == "number" and objective.numRequired > 1 and
                                type(objective.numFulfilled) == "number" and not text:match("%d+%s*/%s*%d+") then
                            text = ("%s (%d/%d)"):format(text, objective.numFulfilled, objective.numRequired)
                        end
                        rows[#rows+1] = {text=text, checked=objective.finished}
                    end
                end
            end
        end
    end
    return rows
end

function carry.OpenQuest(id)
    if not live[id] or not (ns.char.guideJournal and ns.char.guideJournal.ids) then return end
    local member = false
    for _,captured in ipairs(ns.char.guideJournal.ids) do if captured == id then member = true; break end end
    if not member then return end
    focusID = id
    if QuestMapFrame_OpenToQuestDetails then
        QuestMapFrame_OpenToQuestDetails(id)
    elseif QuestLogPopupDetailFrame_Show then
        QuestLogPopupDetailFrame_Show(id)
    elseif type(ShowUIPanel)=="function" and WorldMapFrame then
        ShowUIPanel(WorldMapFrame)
        if QuestMapFrame_ShowQuestDetails then QuestMapFrame_ShowQuestDetails(id) end
    end
end

function carry.Waypoint()
    local id = focusID or firstID
    if not (live[id] and C_QuestLog and C_QuestLog.GetNextWaypoint) then return end
    local map, x, y = C_QuestLog.GetNextWaypoint(id)
    if type(map)=="number" and map>0 and type(x)=="number" and x>=0 and x<=1
            and type(y)=="number" and y>=0 and y<=1 then return map, x, y, live[id].title end
end

local frame = CreateFrame("Frame")
frame:RegisterEvent("QUEST_LOG_UPDATE")
frame:SetScript("OnEvent", function() sawUpdate = true end)
