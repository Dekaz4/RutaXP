local _, ns = ...
local engine, resume, journey = ns.GuideEngine, ns.GuideResume, ns.GuideJourney
local panel, offset, matches = nil, 0, {}
local loggedIn
local rowCount = 8

local function plain(text)
    return ((text or ""):gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", ""))
end

local accents = {["á"]="a", ["é"]="e", ["í"]="i", ["ó"]="o", ["ú"]="u",
    ["ü"]="u", ["ñ"]="n", ["Á"]="a", ["É"]="e", ["Í"]="i", ["Ó"]="o", ["Ú"]="u", ["Ü"]="u", ["Ñ"]="n"}
local function searchText(text)
    return (plain(text):gsub("[\195][\128-\191]", accents)):lower()
end

local function title(guide) return plain(guide.displayname or guide.name) end
local function group(guide) return plain(guide.groupdisplayname or guide.group) end

function ns.ShowGuidePanel()
    if journey:Available() then
        journey:Show()
    else
        local rxp = ns.GetEmbeddedModule("RXPGuides")
        if rxp and rxp.RXPFrame then
            rxp.isHidden = false
            rxp.RXPFrame:Show()
        end
    end
end

function ns.ToggleGuidePanel()
    local rxp = ns.GetEmbeddedModule("RXPGuides")
    if not rxp then ns:Print("Instala la suite de RutaXP para abrir las guías."); return end
    if journey:Available() then
        if journey:IsShown() then
            journey:Hide()
        else ns.ShowGuidePanel() end
    elseif rxp.RXPFrame and rxp.RXPFrame:IsShown() then
        rxp.isHidden = true
        rxp.RXPFrame:Hide()
    else ns.ShowGuidePanel() end
end

local function draw()
    local active = engine.Current()
    local status, description = resume.Status()
    panel.status:SetText(description or "")
    offset = math.max(0, math.min(offset, #matches - rowCount))
    for i, row in ipairs(panel.rows) do
        local guide = matches[offset + i]
        row.guide = guide
        if guide then
            local selected = active and active.key == guide.key and active.key ~= nil and
                status ~= "pending" and status ~= "unavailable"
            row.title:SetText(title(guide))
            row.group:SetText(group(guide))
            row:SetShown(true)
            if selected then row:LockHighlight() else row:UnlockHighlight() end
        else row:Hide() end
    end
    if #matches == 0 then
        panel.empty:SetText(engine.Ready() and "Ninguna guía coincide con la búsqueda." or "Cargando las guías…")
    end
    panel.empty:SetShown(#matches == 0)
    panel.previous:SetEnabled(offset > 0)
    panel.next:SetEnabled(offset + rowCount < #matches)
    panel.counter:SetText(#matches > 0 and string.format("%d–%d / %d", offset+1, math.min(offset+rowCount,#matches),#matches) or "")
end

local function filter(reset)
    if not panel or not panel:IsShown() then return end
    if reset then offset = 0 end
    matches = {}
    local query = searchText(panel.search:GetText())
    for _, guide in ipairs(engine.Catalog() or {}) do
        if query == "" or searchText(title(guide) .. " " .. group(guide)):find(query, 1, true) then
            matches[#matches+1] = guide
        end
    end
    draw()
end

local function page(amount) offset = offset + amount; draw() end

function ns.ActivateZoneGuide()
    if not ns.GetEmbeddedModule("RXPGuides") then ns:Print("Instala la suite de RutaXP para abrir las guías."); return end
    local _, message, found = resume.UseZone()
    if not found then
        if panel and panel:IsShown() then panel.status:SetText(message) else ns:Print(message) end
    else
        if panel then panel:Hide() end
        ns.ShowGuidePanel()
    end
end

local function choose(row)
    if not row.guide then return end
    if resume.SelectManually(row.guide) then
        panel:Hide()
        ns.ShowGuidePanel()
    else
        panel.status:SetText("La guía todavía no se ha podido abrir.")
    end
end

local function button(parent, label, width, action)
    local b = CreateFrame("Button", nil, parent, "UIPanelButtonTemplate")
    b:SetSize(width, 23)
    b:SetText(label)
    b:SetScript("OnClick", action)
    return b
end

local function createPanel()
    panel = CreateFrame("Frame", "RutaXPGuideLibrary", UIParent, "BasicFrameTemplateWithInset")
    panel:SetSize(450, 421)
    panel:SetPoint("CENTER")
    panel:SetFrameStrata("DIALOG")
    panel:SetClampedToScreen(true)
    panel:EnableMouse(true)
    panel:SetMovable(true)
    panel:RegisterForDrag("LeftButton")
    panel:SetScript("OnDragStart", panel.StartMoving)
    panel:SetScript("OnDragStop", panel.StopMovingOrSizing)
    panel.TitleText:SetText("RutaXP · Biblioteca de guías")
    table.insert(UISpecialFrames, "RutaXPGuideLibrary")

    local search = CreateFrame("EditBox", nil, panel, "SearchBoxTemplate")
    search:SetSize(253, 24)
    search:SetPoint("TOPLEFT", 23, -35)
    search:SetAutoFocus(false)
    search:SetScript("OnEscapePressed", function(self) self:ClearFocus() end)
    search:HookScript("OnTextChanged", function() filter(true) end)
    panel.search = search
    button(panel, "Seguir mi zona", 139, ns.ActivateZoneGuide):SetPoint("TOPRIGHT", -16, -35)

    panel.status = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    panel.status:SetPoint("TOPLEFT", 17, -67)
    panel.status:SetWidth(415)
    panel.status:SetJustifyH("LEFT")
    panel.rows = {}
    for i = 1, rowCount do
        local row = CreateFrame("Button", nil, panel)
        row:SetPoint("TOPLEFT", 14, -102 - (i-1)*34)
        row:SetSize(421, 33)
        row:SetHighlightTexture("Interface\\QuestFrame\\UI-QuestTitleHighlight", "ADD")
        row.title = row:CreateFontString(nil, "OVERLAY", "GameFontNormal")
        row.group = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        for _, text in ipairs({row.title, row.group}) do text:SetWidth(408); text:SetJustifyH("LEFT"); text:SetWordWrap(false) end
        row.title:SetPoint("TOPLEFT", 5, -2)
        row.group:SetPoint("TOPLEFT", 5, -17)
        row:SetScript("OnClick", choose)
        panel.rows[i] = row
    end
    panel.empty = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    panel.empty:SetPoint("CENTER")
    panel.previous = button(panel, "<", 38, function() page(-rowCount) end)
    panel.previous:SetPoint("BOTTOMLEFT", 16, 14)
    panel.next = button(panel, ">", 38, function() page(rowCount) end)
    panel.next:SetPoint("BOTTOMRIGHT", -16, 14)
    panel.counter = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    panel.counter:SetPoint("BOTTOM", 0, 20)
    panel:EnableMouseWheel(true)
    panel:SetScript("OnMouseWheel", function(_, delta) page(-delta*3) end)
    panel:SetScript("OnShow", function() filter(true) end)
end

function ns.OpenGuideLibrary()
    if not panel then createPanel() end
    panel:Show()
    filter(true)
end

function ns.OnGuideResumeChanged()
    if not loggedIn then return end
    filter(false)
    if journey:Available() then journey:Refresh() end
end

local login = CreateFrame("Frame")
login:RegisterEvent("PLAYER_LOGIN")
login:SetScript("OnEvent", function(self)
    self:UnregisterEvent("PLAYER_LOGIN")
    loggedIn = true
    engine.Subscribe(function() filter(false) end)
end)
