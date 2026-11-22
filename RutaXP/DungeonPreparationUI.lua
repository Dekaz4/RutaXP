local _, ns = ...
local ui = {}
ns.DungeonPreparationUI = ui

local selectedKey, selected, options
local rowHeight = 30
local renderMenu
local defaultAngle = 135
local backdrop = ns.JourneyCardBackdrop or BACKDROP_GLUE_TOOLTIP_16_16 or {
    bgFile="Interface\\Tooltips\\UI-Tooltip-Background", edgeFile="Interface\\Tooltips\\UI-Tooltip-Border",
    edgeSize=16, insets={left=4,right=4,top=4,bottom=4},
}
local function skin(frame, gold)
    if not frame.SetBackdrop then return end
    frame:SetBackdrop(backdrop)
    if ns.StyleJourneyCard then ns.StyleJourneyCard(frame,gold)
    else
        frame:SetBackdropColor(.03,.025,.018,.98)
        frame:SetBackdropBorderColor(gold and .78 or .64,gold and .73 or .64,gold and .56 or .64)
    end
end

local function header(frame, title)
    local bar = CreateFrame("Frame",nil,frame,BackdropTemplateMixin and "BackdropTemplate" or nil)
    bar:SetPoint("TOPLEFT",17,-3)
    bar:SetPoint("TOPRIGHT",-3,-3)
    bar:SetHeight(38)
    skin(bar,true)
    local emblem = bar:CreateTexture(nil,"OVERLAY")
    if ns.SetJourneyEmblem then ns.SetJourneyEmblem(emblem)
    else emblem:SetTexture("Interface\\Icons\\INV_Misc_Key_03") end
    emblem:SetSize(36,36)
    emblem:SetPoint("CENTER",bar,"LEFT",5,0)
    local heading = bar:CreateFontString(nil,"OVERLAY","GameFontNormal")
    heading:SetPoint("LEFT",27,0)
    heading:SetText(title)
    local close = CreateFrame("Button",nil,bar,"UIPanelCloseButton")
    close:SetSize(25,25)
    close:SetPoint("RIGHT",-4,0)
    close:SetScript("OnClick", function() frame:Hide() end)
end

local function placeButton(button, angle)
    local radians = math.rad(angle)
    button:ClearAllPoints()
    button:SetPoint("CENTER", Minimap, "CENTER",
        (Minimap:GetWidth() / 2 + 2) * math.cos(radians),
        (Minimap:GetHeight() / 2 + 2) * math.sin(radians))
end

local function renderOption()
    local choice = options and options[selected]
    ui.name:SetText(choice and choice.name or "Elegir mazmorra")
    ui.previous:SetShown(choice ~= nil and #options > 1)
    ui.next:SetShown(choice ~= nil and #options > 1)
    ui.previous:SetEnabled(choice ~= nil and selected > 1)
    ui.next:SetEnabled(choice ~= nil and selected < #options)
    local available = choice and choice.available
    ui.prepare:SetEnabled(choice and (available or choice.finished) or false)
    ui.prepare:SetText(available and (choice.finished and "Guiar las entregas" or choice.deferred and "Retomar preparación" or "Preparar mazmorra")
        or choice and choice.finished and "Ir por libre" or "Preparar mazmorra")
    ui.tasks:SetText(choice and (available and table.concat(choice.tasks, "\n\n") or choice.reason)
        or "Ahora mismo no hay misiones de mazmorra pendientes que puedas preparar. Puedes seguir con tu guía de mundo abierto.")
    ui.content:SetHeight(math.max(1, ui.tasks:GetStringHeight() + 8))
end

function ui:RefreshIfShown()
    local showDetail = self.frame and self.frame:IsShown()
    local showMenu = self.menu and self.menu:IsShown()
    if not showDetail and not showMenu then return end
    options = ns.DungeonPlanner:CatalogOptions()
    selected = 1
    for i, choice in ipairs(options) do
        if choice.key == selectedKey then selected = i; break end
    end
    if showDetail then
        renderOption()
        if not options[selected] or options[selected].key ~= selectedKey then self.scroll:SetVerticalScroll(0) end
        selectedKey = options[selected] and options[selected].key
    end
    if showMenu then renderMenu() end
end

local function changeOption(delta)
    local index = selected + delta
    if not options[index] then return end
    selected = index
    selectedKey = options[index].key
    renderOption()
    ui.scroll:SetVerticalScroll(0)
end

local function makePanel()
    local frame = CreateFrame("Frame", "RutaXPDungeonPreparationFrame", UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    ui.frame = frame
    frame:SetSize(372, 318)
    frame:SetPoint("CENTER")
    frame:SetFrameStrata("DIALOG")
    frame:SetClampedToScreen(true)
    frame:EnableMouse(true)
    frame:SetMovable(true)
    frame:RegisterForDrag("LeftButton")
    frame:SetScript("OnDragStart", frame.StartMoving)
    frame:SetScript("OnDragStop", frame.StopMovingOrSizing)
    skin(frame)
    header(frame,"Misiones de mazmorra")
    if UISpecialFrames then table.insert(UISpecialFrames, "RutaXPDungeonPreparationFrame") end
    local function button(label, width, height, callback)
        local b = CreateFrame("Button", nil, frame, BackdropTemplateMixin and "BackdropTemplate" or nil)
        skin(b, label == "Preparar mazmorra")
        local caption = b:CreateFontString(nil,"OVERLAY","GameFontHighlight")
        caption:SetPoint("CENTER")
        if b.SetFontString then b:SetFontString(caption) end
        if b.SetNormalFontObject then
            b:SetNormalFontObject("GameFontHighlight")
            b:SetHighlightFontObject("GameFontNormal")
            b:SetDisabledFontObject("GameFontDisable")
        end
        b:SetHighlightTexture("Interface\\QuestFrame\\UI-QuestTitleHighlight")
        b:SetSize(width, height)
        b:SetText(label)
        b:SetScript("OnClick", callback)
        return b
    end
    ui.previous = button("<", 25, 22, function() changeOption(-1) end)
    ui.previous:SetPoint("TOPLEFT", 13, -53)
    ui.next = button(">", 25, 22, function() changeOption(1) end)
    ui.next:SetPoint("TOPRIGHT", -13, -53)
    local selector = button("", 279, 33, function(b) ui:Toggle(b) end)
    ui.selector = selector
    selector:SetPoint("TOP", 0, -48)
    local name = selector:CreateFontString(nil, "OVERLAY", "GameFontNormal")
    ui.name = name
    name:SetPoint("TOPLEFT", 7, -2)
    name:SetPoint("BOTTOMRIGHT", -22, 2)
    local arrow = selector:CreateTexture(nil, "ARTWORK")
    arrow:SetTexture("Interface\\ChatFrame\\UI-ChatIcon-ScrollDown-Up")
    arrow:SetSize(16, 16)
    arrow:SetPoint("RIGHT", -5, 0)

    local scroll = CreateFrame("ScrollFrame", nil, frame, "UIPanelScrollFrameTemplate")
    ui.scroll = scroll
    scroll:SetPoint("TOPLEFT", 18, -90)
    scroll:SetPoint("BOTTOMRIGHT", -32, 49)
    local content = CreateFrame("Frame", nil, scroll)
    ui.content = content
    content:SetSize(317, 1)
    scroll:SetScrollChild(content)
    local tasks = content:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
    ui.tasks = tasks
    tasks:SetPoint("TOPLEFT", 0, -2)
    tasks:SetWidth(317)
    tasks:SetJustifyH("LEFT")
    tasks:SetWordWrap(true)

    ui.prepare = button("Preparar mazmorra", 180, 26, function()
        local choice = options and options[selected]
        if choice then
            local started
            if choice.available then started = ns.DungeonPlanner:StartPreparation(choice.key)
            elseif choice.finished then started = ns.DungeonPlanner:Repeat(choice.key) end
            if started then frame:Hide(); return end
        end
        ui:RefreshIfShown()
    end)
    ui.prepare:SetPoint("BOTTOM", 0, 13)
    frame:SetScript("OnShow", function() ui:RefreshIfShown() end)
    frame:SetScript("OnHide", function()
        if ui.menu and ui.menu.anchor == ui.selector then ui.menu:Hide() end
    end)
    frame:Hide()
end

local function preview(row)
    selectedKey = row.key
    ui.menu:Hide()
    if not ui.frame then makePanel() end
    if ui.frame:IsShown() then ui:RefreshIfShown() else ui.frame:Show() end
    ui.scroll:SetVerticalScroll(0)
end

local function makeMenu()
    local menu = CreateFrame("Frame", "RutaXPDungeonGuideMenu", UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    ui.menu, ui.menuRows = menu, {}
    menu:SetWidth(368)
    menu:SetFrameStrata("FULLSCREEN_DIALOG")
    menu:SetClampedToScreen(true)
    menu:EnableMouse(true)
    skin(menu)
    header(menu,"Guías de mazmorra")
    local scroll = CreateFrame("ScrollFrame",nil,menu,"UIPanelScrollFrameTemplate")
    ui.menuScroll, menu.scroll = scroll,scroll
    scroll:SetPoint("TOPLEFT",10,-45)
    scroll:SetPoint("BOTTOMRIGHT",-31,9)
    if scroll.SetClipsChildren then scroll:SetClipsChildren(true) end
    local content = CreateFrame("Frame",nil,scroll)
    menu.content = content
    content:SetSize(327,rowHeight)
    scroll:SetScrollChild(content)
    menu.empty = content:CreateFontString(nil,"OVERLAY","GameFontHighlightSmall")
    menu.empty:SetPoint("LEFT",3,0)
    menu.empty:SetText("No hay guías de mazmorra disponibles.")
    if UISpecialFrames then table.insert(UISpecialFrames, "RutaXPDungeonGuideMenu") end
    pcall(menu.RegisterEvent, menu, "GLOBAL_MOUSE_DOWN")
    menu:SetScript("OnEvent", function()
        if menu:IsShown() and menu.IsMouseOver and not menu:IsMouseOver()
            and not (menu.anchor and menu.anchor:IsMouseOver()) then menu:Hide() end
    end)
    menu:Hide()
end

renderMenu = function()
    local menu, content = ui.menu, ui.menu.content
    local slots = math.min(11, math.max(1, math.floor((UIParent:GetHeight()-64)/rowHeight)))
    local visible = math.max(1,math.min(slots,#options))
    menu:SetHeight(54 + visible*rowHeight)
    content:SetHeight(math.max(1,#options)*rowHeight)
    menu.empty:SetShown(#options==0)
    for i, choice in ipairs(options) do
        local row = ui.menuRows[i]
        if not row then
            row = CreateFrame("Button",nil,content)
            ui.menuRows[i] = row
            row:SetPoint("TOPLEFT",0,-(i-1)*rowHeight)
            row:SetSize(327,rowHeight)
            row:SetHighlightTexture("Interface\\QuestFrame\\UI-QuestTitleHighlight")
            row.label = row:CreateFontString(nil,"OVERLAY","GameFontHighlight")
            row.label:SetPoint("TOPLEFT",4,-1)
            row.label:SetPoint("BOTTOMRIGHT",-57,1)
            row.label:SetJustifyH("LEFT")
            row.level = row:CreateFontString(nil,"OVERLAY","GameFontHighlightSmall")
            row.level:SetPoint("RIGHT",-3,0)
            row:SetScript("OnClick",preview)
        end
        row.key = choice.key
        row.label:SetText(choice.name)
        if choice.key == selectedKey then row.label:SetTextColor(1,.83,.25)
        elseif choice.available then row.label:SetTextColor(1,1,1)
        else row.label:SetTextColor(.68,.67,.63) end
        row.level:SetText(choice.minLevel and (choice.minLevel..(choice.maxLevel and ("–"..choice.maxLevel) or "+")) or "")
        row:Show()
    end
    for i=#options+1,#ui.menuRows do ui.menuRows[i]:Hide() end
    local maxScroll = math.max(0,(#options-visible)*rowHeight)
    ui.menuScroll:SetVerticalScroll(math.min(ui.menuScroll:GetVerticalScroll(),maxScroll))
end

function ui:Toggle(anchor)
    if not self.menu then makeMenu() end
    local menu = self.menu
    anchor = anchor or self.button
    if menu:IsShown() and menu.anchor == anchor then menu:Hide(); return end
    menu.anchor = anchor
    local x,y = anchor:GetCenter()
    local scale = anchor:GetEffectiveScale()/UIParent:GetEffectiveScale()
    local right = (x or 0)*scale < UIParent:GetWidth()/2
    local up = (y or 0)*scale < UIParent:GetHeight()/2
    local side = right and "LEFT" or "RIGHT"
    local edge = up and "BOTTOM" or "TOP"
    menu:ClearAllPoints()
    if anchor == self.selector then
        menu:SetPoint(edge..side,anchor,(up and "TOP" or "BOTTOM")..side,0,up and 2 or -2)
    else
        menu:SetPoint(edge..side,anchor,edge..(right and "RIGHT" or "LEFT"),right and 3 or -3,0)
    end
    GameTooltip:Hide()
    menu:Show()
    self:RefreshIfShown()
    local row = anchor == self.selector and selected or 1
    self.menuScroll:SetVerticalScroll(math.min((row-1)*rowHeight,
        math.max(0,#options*rowHeight-(menu:GetHeight()-54))))
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
        GameTooltip:AddLine("Clic para elegir una guía de mazmorra.", 1, 1, 1, true)
        GameTooltip:AddLine("Arrastra para mover el icono.", .75, .75, .75)
        GameTooltip:Show()
    end)
    b:SetScript("OnLeave", GameTooltip_Hide)
    b:SetScript("OnDragStart", function()
        b.dragged = true
        if ui.menu then ui.menu:Hide() end
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
