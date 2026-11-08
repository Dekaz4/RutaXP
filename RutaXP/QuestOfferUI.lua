local _, ns = ...

local events = CreateFrame("Frame")
local advice, label, detail, offeredID, pending, refreshHooked, panelHidden
local offering = false

local function questID()
    if not GetQuestID then return nil end
    local ok, id = pcall(GetQuestID)
    if ok and not (issecretvalue and issecretvalue(id)) and type(id) == "number"
        and id > 0 and id % 1 == 0 then return id end
end

local function hide()
    if advice then advice:Hide() end
end

local function close()
    offering, offeredID, pending = false, nil, false
    events:SetScript("OnUpdate", nil)
    hide()
end

local white = {1, 1, 1}
local colors = {
    ahora = {0.55, 1, 0.68}, ["después"] = {1, 0.85, 0.54},
    opcional = {0.67, 0.83, 1}, fuera = {0.88, 0.88, 0.88},
}

local function draw()
    local id = questID()
    if panelHidden and detail and not detail:IsVisible() then close(); return end
    if not id or (offeredID and id ~= offeredID) or not detail or not detail:IsVisible()
        or not ns.GetQuestOfferAdvice then hide(); return end
    offeredID = id
    local text, kind = ns:GetQuestOfferAdvice(id)
    if type(text) ~= "string" or text == "" then hide(); return end

    if not advice then
        advice = CreateFrame("Frame", nil, detail)
        advice:SetClampedToScreen(true)
        advice:EnableMouse(false)
        local bg = advice:CreateTexture(nil, "BACKGROUND")
        bg:SetAllPoints()
        bg:SetColorTexture(0.045, 0.06, 0.09, 0.96)
        label = advice:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
        label:SetPoint("TOPLEFT", 8, -6)
        label:SetJustifyH("LEFT")
        label:SetWordWrap(true)
    end
    local panel = QuestFrame or detail
    local width = 210
    -- Convert to the same scale even if a UI addon moves or scales the parchment.
    local screenWidth = UIParent:GetWidth() * UIParent:GetEffectiveScale() / panel:GetEffectiveScale()
    local right = screenWidth - (panel:GetRight() or screenWidth)
    local left = panel:GetLeft() or 0
    advice:ClearAllPoints()
    if right < width + 5 and left > right then
        advice:SetPoint("TOPRIGHT", panel, "TOPLEFT", -5, -34)
    else
        advice:SetPoint("TOPLEFT", panel, "TOPRIGHT", 5, -34)
    end
    label:SetWidth(width - 16)
    label:SetTextColor(unpack(colors[kind] or white))
    label:SetText("|cffffd075RutaXP|r  " .. text)
    advice:SetSize(width, math.max(16, label:GetStringHeight()) + 12)
    advice:Show()
end

local function nextFrame()
    events:SetScript("OnUpdate", nil)
    pending = false
    if offering then draw() end
end

local function queue()
    if offering and not pending then
        pending = true
        events:SetScript("OnUpdate", nextFrame)
    end
end

local function bindPanel()
    if not detail and QuestFrameDetailPanel then
        detail = QuestFrameDetailPanel
        detail:HookScript("OnShow", function() panelHidden = false; queue() end)
        detail:HookScript("OnHide", function() panelHidden = true; hide(); queue() end)
    end
end

for _, event in ipairs({"QUEST_DETAIL", "QUEST_FINISHED", "QUEST_PROGRESS", "QUEST_COMPLETE",
    "QUEST_ACCEPTED", "QUEST_GREETING", "GOSSIP_SHOW", "PLAYER_LEAVING_WORLD",
    "QUEST_LOG_UPDATE", "PLAYER_LEVEL_UP", "ADDON_LOADED", "DISPLAY_SIZE_CHANGED", "UI_SCALE_CHANGED"}) do
    pcall(events.RegisterEvent, events, event)
end

events:SetScript("OnEvent", function(_, event, arg1, arg2)
    if event == "QUEST_DETAIL" then
        local id = questID()
        if not id or id ~= offeredID then hide() end
        offering, offeredID, panelHidden = true, id, false
        bindPanel()
        if not refreshHooked and hooksecurefunc and ns.RefreshUI then
            hooksecurefunc(ns, "RefreshUI", queue)
            refreshHooked = true
        end
        queue()
    elseif offering then
        if event == "ADDON_LOADED" then
            bindPanel()
            queue()
        elseif event == "QUEST_LOG_UPDATE" or event == "PLAYER_LEVEL_UP"
            or event == "DISPLAY_SIZE_CHANGED" or event == "UI_SCALE_CHANGED" then
            queue()
        elseif event == "QUEST_ACCEPTED" then
            local id = arg2 or arg1
            if not id or (issecretvalue and issecretvalue(id)) or not offeredID or id == offeredID then close() end
        else
            close()
        end
    end
end)
