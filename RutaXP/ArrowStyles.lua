local ADDON, ns = ...
local A = {}
ns.ArrowStyles = A

local media = "Interface\\AddOns\\" .. ADDON .. "\\Media\\Nav\\quest-"
local styles = {
    { "direction", "Misión" }, { "gold", "Dorada" }, { "forge", "Forja" },
    { "leaf", "Hoja" }, { "crystal", "Cristal" }, { "bone", "Hueso" },
    { "alliance", "Alianza" },
}
local textures = {}
for _, style in ipairs(styles) do
    textures[style[1]] = media .. style[1] .. ".tga"
end

local function metres(yards)
    if (issecretvalue and issecretvalue(yards)) or type(yards) ~= "number"
        or not (yards >= 0 and yards < math.huge) then return nil end
    return math.floor(yards * 0.9144 + 0.5)
end

function ns.FormatArrowDistances(segmentYards, totalYards)
    local total = metres(totalYards)
    if not total then return "" end
    local segment = metres(segmentYards)
    if segment and segment < total then
        return segment .. " m / " .. total .. " m"
    end
    return total .. " m"
end

local function settings()
    if type(ns.char) == "table" and type(ns.char.arrowAppearance) == "table" then
        return ns.char.arrowAppearance
    end
end

local function selectedStyle()
    local data = settings()
    return data and textures[data.style] and data.style or "direction"
end

local function sizePercent()
    local data = settings()
    local size = data and tonumber(data.size)
    if not size or size ~= size then return 100 end
    return math.max(60, math.min(200, math.floor(size / 10 + 0.5) * 10))
end

function A:GetTexture() return textures[selectedStyle()] end
function A:GetScale() return sizePercent() / 100 end
function A:ShowsText()
    local data = settings()
    return not data or data.showText ~= false
end

local listeners = setmetatable({}, {__mode = "k"})
local function save(key, value)
    if type(ns.char) ~= "table" then return end
    if not settings() then ns.char.arrowAppearance = {} end
    ns.char.arrowAppearance[key] = value
    A:Refresh()
end

-- Both the native arrow and Journey already implement dragging. Hook their
-- mouse scripts only once and discard the click when the client starts a drag.
function A:Attach(frame, refreshCallback)
    if not frame then return end
    if listeners[frame] ~= nil then
        listeners[frame] = refreshCallback or false
        return
    end
    listeners[frame] = refreshCallback or false
    local pressed = false
    frame:HookScript("OnMouseDown", function(_, button) pressed = button == "LeftButton" end)
    frame:HookScript("OnDragStart", function() pressed = false end)
    frame:HookScript("OnHide", function() pressed = false end)
    frame:HookScript("OnMouseUp", function(_, button)
        local clicked = pressed and button == "LeftButton"
        pressed = false
        if clicked then A:Toggle() end
    end)
    if refreshCallback then refreshCallback(frame) end
end

local function card(kind, parent, gold)
    local frame = CreateFrame(kind, nil, parent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    if frame.SetBackdrop then
        frame:SetBackdrop(ns.JourneyCardBackdrop)
        ns.StyleJourneyCard(frame, gold)
    end
    return frame
end

local function label(parent, text, font)
    local region = parent:CreateFontString(nil, "OVERLAY", font or "GameFontHighlight")
    region:SetText(text)
    return region
end

local function sizeButton(parent, text, amount)
    local button = card("Button", parent)
    button:SetSize(32, 26)
    label(button, text, "GameFontNormalLarge"):SetPoint("CENTER")
    button:SetHighlightTexture("Interface\\QuestFrame\\UI-QuestTitleHighlight", "ADD")
    button:SetScript("OnClick", function() save("size", math.max(60, math.min(200, sizePercent() + amount))) end)
    return button
end

local function render(panel)
    local selected = selectedStyle()
    for i, style in ipairs(styles) do
        local button = panel.styles[i]
        local active = style[1] == selected
        ns.StyleJourneyCard(button, active)
        button.check:SetShown(active)
        if active then
            button.label:SetTextColor(1, 0.82, 0.16)
        else
            button.label:SetTextColor(1, 1, 1)
        end
    end
    local size = sizePercent()
    panel.percent:SetText(size .. "%")
    panel.smaller:SetEnabled(size > 60)
    panel.larger:SetEnabled(size < 200)
    panel.showText:SetChecked(A:ShowsText())
end

function A:Refresh()
    if self.panel and self.panel:IsShown() then render(self.panel) end
    for frame, callback in pairs(listeners) do
        if callback then callback(frame) end
    end
end

local function createPanel()
    local panel = CreateFrame("Frame", "RutaXPArrowStylePanel", UIParent)
    panel:SetSize(408, 339)
    panel:SetPoint("CENTER")
    panel:SetClampedToScreen(true)
    panel:SetFrameStrata("DIALOG")
    panel:SetToplevel(true)
    panel:EnableMouse(true)
    panel:SetMovable(true)
    panel:RegisterForDrag("LeftButton")
    panel:SetScript("OnDragStart", function(self) self:StartMoving() end)
    panel:SetScript("OnDragStop", function(self) self:StopMovingOrSizing() end)
    if UISpecialFrames then table.insert(UISpecialFrames, "RutaXPArrowStylePanel") end

    local header = card("Frame", panel, true)
    header:SetPoint("TOPLEFT", 24, -4)
    header:SetPoint("TOPRIGHT", -4, -4)
    header:SetHeight(48)
    label(header, "Brújula de RutaXP", "GameFontNormalLarge"):SetPoint("LEFT", 42, 0)
    local emblem = header:CreateTexture(nil, "OVERLAY")
    emblem:SetPoint("CENTER", header, "LEFT", 6, 0)
    ns.SetJourneyEmblem(emblem)
    local close = CreateFrame("Button", nil, header, "UIPanelCloseButton")
    close:SetPoint("RIGHT", -4, 0)
    close:SetScript("OnClick", function() panel:Hide() end)

    local gallery = card("Frame", panel)
    gallery:SetPoint("TOPLEFT", 8, -56)
    gallery:SetPoint("TOPRIGHT", -4, -56)
    gallery:SetHeight(184)
    label(gallery, "Estilo de flecha", "GameFontNormal"):SetPoint("TOPLEFT", 14, -11)
    panel.styles = {}
    for i, style in ipairs(styles) do
        local key = style[1]
        local button = card("Button", gallery)
        button:SetSize(92, 70)
        button:SetPoint("TOPLEFT", 10 + ((i-1) % 4) * 95, -33 - math.floor((i-1)/4) * 72)
        button.icon = button:CreateTexture(nil, "ARTWORK")
        button.icon:SetSize(40, 40)
        button.icon:SetPoint("TOP", 0, -7)
        button.icon:SetTexture(textures[key])
        button.label = label(button, style[2])
        button.label:SetPoint("BOTTOM", 0, 9)
        button.check = button:CreateTexture(nil, "OVERLAY")
        button.check:SetSize(18, 18)
        button.check:SetPoint("TOPRIGHT", -4, -4)
        button.check:SetTexture("Interface\\Buttons\\UI-CheckBox-Check")
        button:SetHighlightTexture("Interface\\QuestFrame\\UI-QuestTitleHighlight", "ADD")
        button:SetScript("OnClick", function() save("style", key) end)
        panel.styles[i] = button
    end

    local options = card("Frame", panel)
    options:SetPoint("TOPLEFT", 8, -244)
    options:SetPoint("BOTTOMRIGHT", -4, 4)
    label(options, "Tamaño de la flecha", "GameFontNormal"):SetPoint("TOPLEFT", 16, -18)
    panel.larger = sizeButton(options, "+", 10)
    panel.larger:SetPoint("TOPRIGHT", -12, -10)
    panel.percent = label(options, "", "GameFontHighlight")
    panel.percent:SetPoint("RIGHT", panel.larger, "LEFT", -4, 0)
    panel.percent:SetWidth(44)
    panel.smaller = sizeButton(options, "−", -10)
    panel.smaller:SetPoint("RIGHT", panel.percent, "LEFT", -4, 0)
    local showText = CreateFrame("CheckButton", nil, options, "UICheckButtonTemplate")
    showText:SetSize(26, 26)
    showText:SetPoint("BOTTOMLEFT", 11, 14)
    label(showText, "Mostrar distancias"):SetPoint("LEFT", showText, "RIGHT", 3, 0)
    showText:SetHitRectInsets(0, -152, 0, 0)
    showText:SetScript("OnClick", function(self) save("showText", not not self:GetChecked()) end)
    panel.showText = showText
    return panel
end

function A:Toggle()
    if self.panel and self.panel:IsShown() then
        self.panel:Hide()
    else
        self.panel = self.panel or createPanel()
        render(self.panel)
        self.panel:Show()
    end
end
