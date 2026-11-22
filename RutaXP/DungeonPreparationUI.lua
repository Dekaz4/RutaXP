local _, ns = ...
local ui = {}
ns.DungeonPreparationUI = ui

local selected, options
local defaultAngle = 135
local function placeButton(button, angle)
    local radians = math.rad(angle)
    button:ClearAllPoints()
    button:SetPoint("CENTER", Minimap, "CENTER",
        (Minimap:GetWidth() / 2 + 2) * math.cos(radians),
        (Minimap:GetHeight() / 2 + 2) * math.sin(radians))
end

local function renderOption()
    local choice = options and options[selected]
    ui.name:SetText(choice and choice.name or "Misiones disponibles")
    ui.previous:SetShown(choice ~= nil and #options > 1)
    ui.next:SetShown(choice ~= nil and #options > 1)
    ui.previous:SetEnabled(choice ~= nil and selected > 1)
    ui.next:SetEnabled(choice ~= nil and selected < #options)
    ui.prepare:SetEnabled(choice ~= nil)
    ui.prepare:SetText(choice and (choice.finished and "Guiar las entregas" or choice.deferred and "Retomar preparación")
        or "Preparar mazmorra")
    ui.tasks:SetText(choice and table.concat(choice.tasks, "\n\n")
        or "Ahora mismo no hay misiones de mazmorra pendientes que puedas preparar. Puedes seguir con tu guía de mundo abierto.")
    ui.content:SetHeight(math.max(1, ui.tasks:GetStringHeight() + 8))
end

function ui:RefreshIfShown()
    if not self.frame or not self.frame:IsShown() then return end
    local oldKey = options and options[selected] and options[selected].key
    options = ns.DungeonPlanner:PreparationOptions()
    selected = 1
    for i, choice in ipairs(options) do
        if choice.key == oldKey then selected = i; break end
    end
    renderOption()
    if not options[selected] or options[selected].key ~= oldKey then self.scroll:SetVerticalScroll(0) end
end

local function changeOption(delta)
    local index = selected + delta
    if not options[index] then return end
    selected = index
    renderOption()
    ui.scroll:SetVerticalScroll(0)
end

local function makePanel()
    local frame = CreateFrame("Frame", "RutaXPDungeonPreparationFrame", UIParent, "BasicFrameTemplateWithInset")
    ui.frame = frame
    frame:SetSize(340, 305)
    frame:SetPoint("CENTER")
    frame:SetFrameStrata("DIALOG")
    frame:SetClampedToScreen(true)
    frame:EnableMouse(true)
    frame:SetMovable(true)
    frame:RegisterForDrag("LeftButton")
    frame:SetScript("OnDragStart", frame.StartMoving)
    frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
    frame.TitleText:SetText("Misiones de mazmorra")
    if UISpecialFrames then table.insert(UISpecialFrames, "RutaXPDungeonPreparationFrame") end
    local name = frame:CreateFontString(nil, "ARTWORK", "GameFontNormalLarge")
    ui.name = name
    name:SetPoint("TOPLEFT", 42, -34)
    name:SetPoint("TOPRIGHT", -42, -34)
    name:SetHeight(34)

    local function button(label, width, height, callback)
        local b = CreateFrame("Button", nil, frame, "UIPanelButtonTemplate")
        b:SetSize(width, height)
        b:SetText(label)
        b:SetScript("OnClick", callback)
        return b
    end
    ui.previous = button("<", 25, 22, function() changeOption(-1) end)
    ui.previous:SetPoint("TOPLEFT", 13, -38)
    ui.next = button(">", 25, 22, function() changeOption(1) end)
    ui.next:SetPoint("TOPRIGHT", -13, -38)

    local scroll = CreateFrame("ScrollFrame", nil, frame, "UIPanelScrollFrameTemplate")
    ui.scroll = scroll
    scroll:SetPoint("TOPLEFT", 18, -72)
    scroll:SetPoint("BOTTOMRIGHT", -32, 49)
    local content = CreateFrame("Frame", nil, scroll)
    ui.content = content
    content:SetSize(282, 1)
    scroll:SetScrollChild(content)
    local tasks = content:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
    ui.tasks = tasks
    tasks:SetPoint("TOPLEFT", 0, -2)
    tasks:SetWidth(282)
    tasks:SetJustifyH("LEFT")
    tasks:SetWordWrap(true)

    ui.prepare = button("Preparar mazmorra", 180, 26, function()
        local choice = options and options[selected]
        if choice and ns.DungeonPlanner:StartPreparation(choice.key) then frame:Hide()
        else ui:RefreshIfShown() end
    end)
    ui.prepare:SetPoint("BOTTOM", 0, 13)
    frame:SetScript("OnShow", function() ui:RefreshIfShown() end)
    frame:SetScript("OnHide", function() options, selected = nil, nil end)
    frame:Hide()
end

function ui:Toggle()
    if not self.frame then makePanel() end
    self.frame:SetShown(not self.frame:IsShown())
end

local function savedAngle()
    return ns.char and tonumber(ns.char.dungeonPrepMinimapAngle) or defaultAngle
end

local function createButton()
    if ui.button or not Minimap then return end
    local b = CreateFrame("Button", "RutaXPDungeonPreparationMinimapButton", Minimap)
    ui.button = b
    b:SetSize(31, 31)
    b:SetFrameLevel(Minimap:GetFrameLevel() + 9)
    b:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
    local background = b:CreateTexture(nil, "BACKGROUND")
    background:SetSize(23, 23)
    background:SetPoint("CENTER")
    background:SetTexture("Interface\\Minimap\\UI-Minimap-Background")
    local icon = b:CreateTexture(nil, "ARTWORK")
    icon:SetSize(19, 19)
    icon:SetPoint("CENTER")
    icon:SetTexture("Interface\\Icons\\INV_Misc_Key_03")
    icon:SetTexCoord(.06, .94, .06, .94)
    local border = b:CreateTexture(nil, "OVERLAY")
    border:SetSize(53, 53)
    border:SetPoint("TOPLEFT")
    border:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder")
    b:RegisterForClicks("LeftButtonUp")
    b:RegisterForDrag("LeftButton")
    b:SetScript("OnMouseDown", function() b.dragged = false end)
    b:SetScript("OnClick", function() if not b.dragged then ui:Toggle() end end)
    b:SetScript("OnEnter", function()
        GameTooltip:SetOwner(b, "ANCHOR_LEFT")
        GameTooltip:SetText("Misiones de mazmorra")
        GameTooltip:AddLine("Clic para ver las previas y retomar una preparación.", 1, 1, 1, true)
        GameTooltip:AddLine("Arrastra para mover el icono.", .75, .75, .75)
        GameTooltip:Show()
    end)
    b:SetScript("OnLeave", GameTooltip_Hide)
    b:SetScript("OnDragStart", function()
        b.dragged = true
        GameTooltip:Hide()
        b:SetScript("OnUpdate", function()
            local mx, my = Minimap:GetCenter()
            if not mx then return end
            local x, y = GetCursorPosition()
            local scale = Minimap:GetEffectiveScale()
            b.angle = math.deg(math.atan2(y / scale - my, x / scale - mx))
            placeButton(b, b.angle)
        end)
    end)
    b:SetScript("OnDragStop", function()
        b:SetScript("OnUpdate", nil)
        if ns.char and b.angle then ns.char.dungeonPrepMinimapAngle = b.angle end
    end)
    placeButton(b, savedAngle())
    Minimap:HookScript("OnSizeChanged", function() placeButton(b, b.angle or savedAngle()) end)
    b:Show()
end

local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_LOGIN")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:SetScript("OnEvent", createButton)
