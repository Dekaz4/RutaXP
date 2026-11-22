local _, ns = ...

-- Forever adaptation of IsOnQuest, IsQuestComplete and IsQuestTurnedIn from
-- RestedXP/RXPGuides functions.lua, cbe05e351e083108d08b35908347952fb0eaf06e.
-- CC BY-NC-SA 4.0. See Licenses/RestedXP-Quest-State.txt.
-- Short event windows cover the delay between an interaction and the query
-- APIs. Completion is always for the current character.
local state, accepted, delivered = {}, {}, {}
ns.RestedQuestState = state

local function recent(timestamps, id, seconds)
    local at = timestamps[id]
    if at and GetTime() - at < seconds then return true end
    timestamps[id] = nil
    return false
end

function state.Active(id)
    if ns:IsQuestActive(id) then accepted[id] = nil; return true end
    return recent(accepted, id, 2)
end

function state.Ready(id)
    local complete = C_QuestLog.IsComplete and C_QuestLog.IsComplete(id)
    return not (issecretvalue and issecretvalue(complete)) and (complete == true or complete == 1)
end

function state.Delivered(id)
    if recent(delivered, id, 5) then return true end
    return ns:IsQuestDelivered(id)
end

local events = CreateFrame("Frame")
for _, name in ipairs({"QUEST_ACCEPTED", "QUEST_TURNED_IN", "QUEST_REMOVED"}) do events:RegisterEvent(name) end
events:SetScript("OnEvent", function(_, event, first, second)
    local id = event == "QUEST_ACCEPTED" and (second or first) or first
    if type(id) ~= "number" or (issecretvalue and issecretvalue(id)) then return end
    if event == "QUEST_ACCEPTED" then accepted[id], delivered[id] = GetTime(), nil
    elseif event == "QUEST_TURNED_IN" then delivered[id], accepted[id] = GetTime(), nil
    else accepted[id] = nil end
end)
