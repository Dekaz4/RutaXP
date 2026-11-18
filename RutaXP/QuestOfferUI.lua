local _, ns = ...

local events = CreateFrame("Frame")
local mode, offeredID, contact, pending, refreshHooked
local detail, panelHidden, displayed
local cards = {}

local function questID()
    if not GetQuestID then return nil end
    local ok, id = pcall(GetQuestID)
    if ok and not (issecretvalue and issecretvalue(id)) and type(id) == "number"
        and id > 0 and id % 1 == 0 then return id end
end

local function hide()
    if displayed then displayed:Hide(); displayed = nil end
end

local function close()
    mode, offeredID, contact, pending = nil, nil, nil, false
    events:SetScript("OnUpdate", nil)
    hide()
end

local white = {1, 1, 1}
local colors = {
    ahora = {0.55, 1, 0.68}, ["después"] = {1, 0.85, 0.54},
    opcional = {0.67, 0.83, 1}, fuera = {0.88, 0.88, 0.88},
}

local function present()
    if mode == "QUEST_DETAIL" then return detail end
    if mode == "GOSSIP_SHOW" then return GossipFrame end
    if mode == "QUEST_GREETING" then return QuestFrameGreetingPanel or QuestFrame end
end

local function currentContext()
    if ns.GetNPCQuestContext then return ns:GetNPCQuestContext(contact, mode, offeredID) end
end

local function render(parent, panel, text, kind, marker)
    local card = cards[parent]
    if not card then
        card = CreateFrame("Frame", nil, parent)
        cards[parent] = card
        card:SetClampedToScreen(true)
        card:EnableMouse(false)
        local bg = card:CreateTexture(nil, "BACKGROUND")
        bg:SetAllPoints()
        bg:SetColorTexture(0.045, 0.06, 0.09, 0.96)
        card.label = card:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
        card.label:SetPoint("TOPLEFT", 8, -6)
        card.label:SetJustifyH("LEFT")
        card.label:SetWordWrap(true)
    end
    if displayed ~= card then hide() end
    displayed = card
    local width = marker and 240 or 210
    local screenWidth = UIParent:GetWidth() * UIParent:GetEffectiveScale() / panel:GetEffectiveScale()
    local right = screenWidth - (panel:GetRight() or screenWidth)
    local left = panel:GetLeft() or 0
    card:ClearAllPoints()
    if right < width + 5 and left > right then
        card:SetPoint("TOPRIGHT", panel, "TOPLEFT", -5, -34)
    else
        card:SetPoint("TOPLEFT", panel, "TOPRIGHT", 5, -34)
    end
    card.label:SetWidth(width - 16)
    card.label:SetTextColor(unpack(colors[kind] or white))
    card.label:SetText("|cffffd075RutaXP|r  " .. text)
    card.marker = marker
    if marker then
        if not card.button then
            card.button = CreateFrame("Button", nil, card, "UIPanelButtonTemplate")
            card.button:SetPoint("BOTTOMLEFT", 7, 5)
            card.button:SetHeight(22)
            card.button:SetScript("OnClick", function()
                local panelNow = present()
                if displayed ~= card or panelNow ~= parent or not parent:IsVisible() then return end
                local _, live = currentContext()
                if not live or live ~= card.marker then return end
                local point = ns:ResolveWaypointPoint(live)
                local name = live.objName or live.npcName
                if point then ns:MarkMapDestination(point, name)
                else ns:Print("El juego aún no puede situar «" .. name .. "» en el mapa.") end
            end)
        end
        local name = marker.objName or ""
        card.button:SetText(name:lower():find("libro", 1, true) and "Marcar el libro" or "Marcar en el mapa")
        card.button:SetWidth(width - 14)
        card.button:Show()
    elseif card.button then
        card.button:Hide()
    end
    card:SetSize(width, math.max(16, card.label:GetStringHeight()) + 12 + (marker and 28 or 0))
    card:Show()
end

local function draw()
    local parent = present()
    if not parent or not parent:IsVisible() then
        if mode == "QUEST_DETAIL" and panelHidden then close() else hide() end
        return
    end
    local text, kind, marker
    if mode == "QUEST_DETAIL" then
        local id = questID()
        if not id or (offeredID and id ~= offeredID) or not ns.GetQuestOfferAdvice then hide(); return end
        offeredID = id
        text, kind = ns:GetQuestOfferAdvice(id)
        local contextText, contextMarker = currentContext()
        if contextText then text, marker = contextText, contextMarker end
    else
        text, marker = currentContext()
    end
    if type(text) ~= "string" or text == "" then hide(); return end
    local panel = mode == "GOSSIP_SHOW" and GossipFrame or QuestFrame or parent
    render(parent, panel, text, kind, marker)
end

local function nextFrame()
    events:SetScript("OnUpdate", nil)
    pending = false
    if mode then draw() end
end

local function queue()
    if mode and not pending then
        pending = true
        events:SetScript("OnUpdate", nextFrame)
    end
end

local function bindPanel()
    if not detail and QuestFrameDetailPanel then
        detail = QuestFrameDetailPanel
        detail:HookScript("OnShow", function() if mode == "QUEST_DETAIL" then panelHidden = false; queue() end end)
        detail:HookScript("OnHide", function() if mode == "QUEST_DETAIL" then panelHidden = true; hide(); queue() end end)
    end
end

for _, event in ipairs({"QUEST_DETAIL", "QUEST_FINISHED", "QUEST_PROGRESS", "QUEST_COMPLETE",
    "QUEST_ACCEPTED", "QUEST_GREETING", "GOSSIP_SHOW", "GOSSIP_CLOSED", "PLAYER_LEAVING_WORLD",
    "QUEST_LOG_UPDATE", "PLAYER_LEVEL_UP", "ADDON_LOADED", "DISPLAY_SIZE_CHANGED", "UI_SCALE_CHANGED"}) do
    pcall(events.RegisterEvent, events, event)
end

events:SetScript("OnEvent", function(_, event, arg1, arg2)
    if event == "QUEST_DETAIL" or event == "QUEST_GREETING" or event == "GOSSIP_SHOW" then
        hide()
        mode, offeredID, panelHidden = event, event == "QUEST_DETAIL" and questID() or nil, false
        contact = ns.GetQuestContactNPC and ns:GetQuestContactNPC()
        bindPanel()
        if not refreshHooked and hooksecurefunc and ns.RefreshUI then
            hooksecurefunc(ns, "RefreshUI", queue)
            refreshHooked = true
        end
        queue()
    elseif mode then
        if event == "ADDON_LOADED" then
            bindPanel()
            queue()
        elseif event == "QUEST_LOG_UPDATE" or event == "PLAYER_LEVEL_UP"
            or event == "DISPLAY_SIZE_CHANGED" or event == "UI_SCALE_CHANGED" then
            queue()
        elseif event == "QUEST_ACCEPTED" then
            local id = arg2 or arg1
            if not id or (issecretvalue and issecretvalue(id)) or not offeredID or id == offeredID then close() end
        elseif event ~= "GOSSIP_CLOSED" or mode == "GOSSIP_SHOW" then
            close()
        end
    end
end)
