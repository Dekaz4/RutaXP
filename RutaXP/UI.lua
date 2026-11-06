local _, ns = ...

local UI_MEDIA = "Interface\\AddOns\\RutaXP\\Media\\UI\\"
local GOLD = { 0.95, 0.78, 0.42 }
local SKY = { 0.58, 0.80, 1.00 }
local GREEN = { 0.42, 0.88, 0.62 }
local MUTED = { 0.64, 0.72, 0.82 }
local TEXT_MAIN = { 0.95, 0.96, 0.98 }

local ACTION_ICONS = {
    accept = { icon = "icon-accept", color = { 1.00, 0.84, 0.42 } },
    turnin = { icon = "icon-turnin", color = { 0.42, 0.88, 0.62 } },
    complete = { icon = "icon-complete", color = { 0.96, 0.75, 0.35 } },
    kill = { icon = "icon-kill", color = { 0.98, 0.52, 0.44 } },
    collect = { icon = "icon-collect", color = { 0.78, 0.68, 1.00 } },
    goto = { icon = "icon-goto", color = { 0.96, 0.68, 0.52 } },
    talk = { icon = "icon-talk", color = { 0.58, 0.80, 1.00 } },
    interact = { icon = "icon-interact", color = { 0.88, 0.80, 0.64 } },
    use = { icon = "icon-use", color = { 0.78, 0.68, 1.00 } },
    sethome = { icon = "icon-sethome", color = { 0.58, 0.80, 1.00 } },
    hearth = { icon = "icon-hearth", color = { 0.58, 0.80, 1.00 } },
    getfp = { icon = "icon-getfp", color = { 0.60, 0.88, 0.52 } },
    fly = { icon = "icon-fly", color = { 0.60, 0.88, 0.52 } },
    train = { icon = "icon-train", color = { 0.58, 0.80, 1.00 } },
    buy = { icon = "icon-buy", color = { 0.95, 0.78, 0.42 } },
    vendor = { icon = "icon-vendor", color = { 0.95, 0.78, 0.42 } },
    level = { icon = "icon-level", color = { 0.96, 0.97, 0.99 } },
    note = { icon = "icon-note", color = { 0.64, 0.72, 0.82 } },
}

local function panel(parent, width, height, bgR, bgG, bgB, bgA)
    local frame = CreateFrame("Frame", nil, parent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    frame:SetSize(width, height)
    frame:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
    frame:SetBackdropColor(bgR or 0.045, bgG or 0.065, bgB or 0.10, bgA or 0.95)
    frame:SetBackdropBorderColor(0.22, 0.28, 0.38, 0.95)
    return frame
end

local function label(parent, font, text, x, y, width, color)
    local item = parent:CreateFontString(nil, "OVERLAY", font or "GameFontNormal")
    item:SetPoint("TOPLEFT", x, y)
    if width then item:SetWidth(width) end
    item:SetJustifyH("LEFT")
    item:SetJustifyV("TOP")
    item:SetText(text or "")
    if color then item:SetTextColor(unpack(color)) end
    return item
end

-- Modern flat button replacing ugly red Blizzard UIPanelButtonTemplate
local function flatButton(parent, text, width, height, x, y, action, accent)
    local btn = CreateFrame("Button", nil, parent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    btn:SetSize(width, height or 24)
    btn:SetPoint("TOPLEFT", x, y)
    btn:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
    btn.isAccent = accent
    btn.isEnabled = true
    local lbl = btn:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    lbl:SetPoint("CENTER", 0, 0)
    lbl:SetText(text or "")
    btn.label = lbl

    local function paint(hover)
        if not btn.isEnabled then
            btn:SetBackdropColor(0.06, 0.08, 0.11, 0.65)
            btn:SetBackdropBorderColor(0.15, 0.18, 0.24, 0.65)
            lbl:SetTextColor(0.42, 0.46, 0.52)
        elseif btn.isAccent then
            btn:SetBackdropColor(hover and 0.30 or 0.22, hover and 0.24 or 0.17, hover and 0.12 or 0.08, 0.98)
            btn:SetBackdropBorderColor(0.95, 0.78, 0.42, hover and 1 or 0.85)
            lbl:SetTextColor(1, 0.88, 0.58)
        else
            btn:SetBackdropColor(hover and 0.15 or 0.09, hover and 0.20 or 0.12, hover and 0.28 or 0.18, 0.95)
            btn:SetBackdropBorderColor(hover and 0.45 or 0.24, hover and 0.54 or 0.30, hover and 0.68 or 0.42, 0.95)
            lbl:SetTextColor(0.90, 0.93, 0.98)
        end
    end
    paint(false)

    function btn:SetText(newText)
        self.text = newText
        lbl:SetText(newText or "")
    end
    function btn:GetText()
        return self.text or lbl:GetText() or ""
    end
    function btn:SetEnabled(enabled)
        self.enabled = not not enabled
        self.isEnabled = self.enabled
        paint(false)
    end

    btn:SetScript("OnEnter", function() if btn.isEnabled then paint(true) end end)
    btn:SetScript("OnLeave", function() paint(false) end)
    btn:SetScript("OnClick", function(self, ...)
        if self.isEnabled and action then action(self, ...) end
    end)
    return btn
end

local function advanceGuide(button)
    if button.groundDetour then
        ns:BeginGroundDetour()
    elseif button.startsTravelHere then
        local ok, reason = ns:StartTravelHere()
        if not ok and reason then ns:Print(reason) end
    elseif button.continuesGuide then
        local ok, reason = ns:ContinueGuide()
        if not ok and reason then ns:Print(reason) end
    else
        ns:Next()
    end
end

local function skipShownStep(button)
    if button.skipsTravel then
        ns:SkipGuideTravel()
    elseif ns.SkipStep then
        ns:SkipStep()
    else
        ns:Next()
    end
end

local function moveable(frame, key, defaultPoint, defaultX, defaultY)
    frame:SetMovable(true)
    frame:SetClampedToScreen(true)
    frame:EnableMouse(true)
    local saved = ns.char[key]
    local anchors = { TOPLEFT = true, TOP = true, TOPRIGHT = true, LEFT = true,
        CENTER = true, RIGHT = true, BOTTOMLEFT = true, BOTTOM = true, BOTTOMRIGHT = true }
    if type(saved) ~= "table" or not anchors[saved.point] or not anchors[saved.relativePoint]
        or type(saved.x) ~= "number" or type(saved.y) ~= "number"
        or saved.x ~= saved.x or saved.y ~= saved.y then saved = nil end
    frame:SetPoint(saved and saved.point or defaultPoint, UIParent,
        saved and saved.relativePoint or defaultPoint, saved and saved.x or defaultX, saved and saved.y or defaultY)
    local bar = CreateFrame("Frame", nil, frame)
    bar:SetPoint("TOPLEFT", 0, 0)
    bar:SetPoint("TOPRIGHT", -88, 0)
    bar:SetHeight(34)
    bar:EnableMouse(true)
    bar:RegisterForDrag("LeftButton")
    bar:SetScript("OnDragStart", function() frame.isMoving = true; frame:StartMoving() end)
    bar:SetScript("OnDragStop", function()
        frame:StopMovingOrSizing()
        frame.isMoving = nil
        local point, _, relativePoint, x, y = frame:GetPoint()
        ns.char[key] = { point = point, relativePoint = relativePoint, x = x, y = y }
    end)
end

function ns:ToggleWindow()
    if self.window:IsShown() then self.window:Hide() else self.window:Show() end
    self:RefreshUI()
end

function ns:CreateUI()
    self.rows = {}
    local frame = panel(UIParent, 840, 560, 0.04, 0.06, 0.095, 0.98)
    self.window = frame
    frame:SetFrameStrata("DIALOG")
    frame:SetScale(math.min(1, UIParent:GetWidth() / 880, UIParent:GetHeight() / 600))
    moveable(frame, "windowPosition", "CENTER", 0, 0)
    frame:Hide()

    -- Top gold accent line & header band
    local topAccent = frame:CreateTexture(nil, "OVERLAY")
    topAccent:SetColorTexture(0.95, 0.78, 0.42, 0.9)
    topAccent:SetPoint("TOPLEFT", 1, -1)
    topAccent:SetPoint("TOPRIGHT", -1, -1)
    topAccent:SetHeight(2)

    local headerBand = frame:CreateTexture(nil, "BACKGROUND")
    if headerBand.SetTexture then headerBand:SetTexture(UI_MEDIA .. "band-stars") end
    headerBand:SetPoint("TOPLEFT", 1, -3)
    headerBand:SetPoint("TOPRIGHT", -1, -3)
    headerBand:SetHeight(48)
    if headerBand.SetVertexColor then headerBand:SetVertexColor(0.12, 0.20, 0.32, 0.85) end

    label(frame, "GameFontNormalLarge", "RUTA|cfff5f7faXP|r", 20, -15, nil, GOLD)
    self.recordingLabel = label(frame, "GameFontHighlightSmall", "", 125, -18, 420, MUTED)

    -- Zone auto-detect & Talent Guides buttons in header
    self.talentsButton = flatButton(frame, "Talentos (N)", 106, 24, 462, -13, function()
        if self.Talents and self.Talents.TogglePanel then
            self.Talents.TogglePanel()
        end
    end)

    self.zoneDetectButton = flatButton(frame, "Detectar guía de mi zona actual", 220, 24, 575, -13, function()
        if self.DetectZoneGuide then self:DetectZoneGuide(false) end
    end, true)

    local close = flatButton(frame, "×", 26, 24, 804, -13, function()
        frame:Hide()
        self:RefreshUI()
    end)

    -- Left column: Guide Browser
    label(frame, "GameFontHighlightSmall", "SELECCIONA TU ZONA / RUTA", 20, -62, 260, GOLD)
    local search = CreateFrame("EditBox", nil, frame, "InputBoxTemplate")
    self.search = search
    search:SetSize(248, 24)
    search:SetPoint("TOPLEFT", 25, -82)
    search:SetAutoFocus(false)
    search:SetMaxLetters(80)
    search:SetScript("OnEscapePressed", function(box) box:ClearFocus() end)
    search:SetScript("OnEnterPressed", function(box) box:ClearFocus() end)
    search:SetScript("OnTextChanged", function() self:RefreshGuideList() end)

    self.factionButton = flatButton(frame, "Ver: mi facción", 254, 24, 20, -114, function()
        self.char.allFactions = not self.char.allFactions
        self:RefreshGuideList()
    end)
    label(frame, "GameFontDisableSmall", "Filtra por zona o nivel (ej. Elwynn, 12, Poniente)", 22, -143, 254)

    local scroll = CreateFrame("ScrollFrame", nil, frame, "UIPanelScrollFrameTemplate")
    self.listScroll = scroll
    scroll:SetPoint("TOPLEFT", 20, -164)
    scroll:SetSize(236, 332)
    if scroll.SetClipsChildren then scroll:SetClipsChildren(true) end
    local content = CreateFrame("Frame", nil, scroll)
    content:SetSize(236, 332)
    self.listContent = content
    scroll:SetScrollChild(content)
    self.noResults = label(content, "GameFontHighlight", "No hay guías con este filtro.", 8, -12, 215, MUTED)
    self.guideCount = label(frame, "GameFontHighlightSmall", "", 20, -506, 254, MUTED)

    -- Right column: Active Guide & Current Step
    local detail = panel(frame, 524, 434, 0.065, 0.09, 0.135, 0.98)
    self.detail = detail
    detail:SetPoint("TOPLEFT", 296, -62)

    self.guideKind = label(detail, "GameFontHighlightSmall", "", 18, -14, 488, GOLD)
    self.guideTitle = label(detail, "GameFontNormalLarge", "", 18, -34, 488, TEXT_MAIN)
    self.guideTitle:SetHeight(32)
    self.guideSummary = label(detail, "GameFontHighlightSmall", "", 18, -68, 488, MUTED)
    self.guideSummary:SetHeight(42)

    local progress = CreateFrame("StatusBar", nil, detail)
    self.progressBar = progress
    progress:SetPoint("TOPLEFT", 18, -118)
    progress:SetSize(488, 6)
    progress:SetStatusBarTexture("Interface\\Buttons\\WHITE8X8")
    progress:SetStatusBarColor(unpack(GOLD))
    progress:SetMinMaxValues(0, 1)
    local background = progress:CreateTexture(nil, "BACKGROUND")
    background:SetAllPoints()
    background:SetColorTexture(0.14, 0.18, 0.25, 1)

    self.stepCount = label(detail, "GameFontHighlightSmall", "", 18, -134, 488, SKY)
    self.stepTitle = label(detail, "GameFontNormalLarge", "", 18, -154, 488, TEXT_MAIN)
    self.stepTitle:SetHeight(34)

    local stepScroll = CreateFrame("ScrollFrame", nil, detail, "UIPanelScrollFrameTemplate")
    self.stepScroll = stepScroll
    stepScroll:SetPoint("TOPLEFT", 18, -194)
    stepScroll:SetSize(465, 182)
    if stepScroll.SetClipsChildren then stepScroll:SetClipsChildren(true) end
    local stepContent = CreateFrame("Frame", nil, stepScroll)
    stepContent:SetSize(465, 182)
    stepScroll:SetScrollChild(stepContent)
    self.stepContent = stepContent
    self.stepText = label(stepContent, "GameFontHighlight", "", 0, 0, 455)
    self.stepText:SetSpacing(4)

    self.previousButton = flatButton(detail, "< Anterior", 96, 26, 18, -392, function() self:Previous() end)
    self.nextButton = flatButton(detail, "Siguiente >", 126, 26, 120, -392, advanceGuide, true)
    self.skipButton = flatButton(detail, "Saltar paso", 96, 26, 252, -392, skipShownStep)
    self.mapButton = flatButton(detail, "Marcar mapa", 92, 26, 354, -392, function() self:Navigate() end)
    flatButton(detail, "Reiniciar", 64, 26, 452, -392, function()
        local guide = self:GetCurrent()
        if guide then StaticPopup_Show("RUTAXP_RESET_GUIDE", guide.title, nil, guide.id) end
    end)

    -- Bottom checkboxes
    local auto = CreateFrame("CheckButton", nil, frame, "UICheckButtonTemplate")
    self.autoCheck = auto
    auto:SetSize(24, 24)
    auto:SetPoint("TOPLEFT", 296, -504)
    label(frame, "GameFontHighlightSmall", "Automático (misiones y avance)", 322, -510, 185)
    auto:SetScript("OnClick", function(box)
        if self.UseManualDuoMode then self:UseManualDuoMode("Avance automático cambiado manualmente") end
        self.char.auto = box:GetChecked() and true or false; self:Sync()
    end)

    local track = CreateFrame("CheckButton", nil, frame, "UICheckButtonTemplate")
    self.trackCheck = track
    track:SetSize(24, 24)
    track:SetPoint("TOPLEFT", 508, -504)
    label(frame, "GameFontHighlightSmall", "Panel en pantalla", 534, -510, 110)
    track:SetScript("OnClick", function(box) self.char.tracker = box:GetChecked() and true or false; self:RefreshUI() end)

    local arrow = CreateFrame("CheckButton", nil, frame, "UICheckButtonTemplate")
    self.arrowCheck = arrow
    arrow:SetSize(24, 24)
    arrow:SetPoint("TOPLEFT", 644, -504)
    label(frame, "GameFontHighlightSmall", "Flecha guía", 670, -510, 75)
    arrow:SetScript("OnClick", function(box)
        self.char.arrow = box:GetChecked() and true or false
        if self.UpdateNavigation then self:UpdateNavigation() end
        self:RefreshUI()
    end)

    local optional = CreateFrame("CheckButton", nil, frame, "UICheckButtonTemplate")
    self.optionalCheck = optional
    optional:SetSize(24, 24)
    optional:SetPoint("TOPLEFT", 740, -504)
    label(frame, "GameFontHighlightSmall", "Opcionales", 766, -510, 80)
    optional:SetScript("OnClick", function(box) self.char.optional = box:GetChecked() and true or false; self:Sync() end)

    label(frame, "GameFontDisableSmall", "Acepta y entrega misiones automáticamente al hablar con NPCs (mantén Shift para pausar).", 300, -536, 520)

    self:CreateTracker()
    StaticPopupDialogs.RUTAXP_RESET_GUIDE = {
        text = "¿Reiniciar el progreso de «%s» para este personaje?", button1 = "Reiniciar", button2 = "Cancelar",
        OnAccept = function(_, id) ns:ResetGuide(id) end, timeout = 0, whileDead = true, hideOnEscape = true,
        preferredIndex = 3,
    }
end

---------------------------------------------------------------------------
-- Compact On-Screen Tracker (RestedXP / SendaFH style, positioned on LEFT)
---------------------------------------------------------------------------

function ns:CreateTracker()
    local frame = panel(UIParent, 324, 210, 0.04, 0.06, 0.095, 0.94)
    self.tracker = frame
    self.trackerRows = {}
    frame:SetFrameStrata("MEDIUM")
    frame:SetScale(math.min(1, UIParent:GetWidth() / 360, UIParent:GetHeight() / 280))
    -- Placed on TOPLEFT by default so it NEVER overlaps WoW's right-side Quest Tracker!
    moveable(frame, "trackerPosition", "TOPLEFT", 24, -135)

    -- Top gold accent rule
    local topRule = frame:CreateTexture(nil, "OVERLAY")
    topRule:SetColorTexture(0.95, 0.78, 0.42, 0.9)
    topRule:SetPoint("TOPLEFT", 1, -1)
    topRule:SetPoint("TOPRIGHT", -1, -1)
    topRule:SetHeight(2)

    -- Night sky header band
    local band = frame:CreateTexture(nil, "BACKGROUND")
    if band.SetTexture then band:SetTexture(UI_MEDIA .. "band") end
    band:SetPoint("TOPLEFT", 1, -3)
    band:SetPoint("TOPRIGHT", -1, -3)
    band:SetHeight(32)
    if band.SetVertexColor then band:SetVertexColor(0.11, 0.19, 0.30, 0.9) end

    -- Guide title & zone header on the left
    self.trackerTitle = label(frame, "GameFontHighlightSmall", "", 10, -10, 178, GOLD)
    self.trackerTitle:SetHeight(16)

    -- Compact top-right buttons: [N] [Zona] [Guías] [×]
    self.trackerTalentBtn = flatButton(frame, "N", 22, 20, 193, -7, function()
        if self.Talents and self.Talents.TogglePanel then
            self.Talents.TogglePanel()
        end
    end)
    self.trackerZoneBtn = flatButton(frame, "Zona", 42, 20, 218, -7, function()
        if self.DetectZoneGuide then self:DetectZoneGuide(false) end
    end, true)
    self.trackerGuidesBtn = flatButton(frame, "Guías", 44, 20, 262, -7, function()
        self.window:Show()
        self:RefreshUI()
    end)
    self.trackerCloseBtn = flatButton(frame, "×", 16, 20, 307, -7, function()
        self.char.tracker = false
        self:RefreshUI()
    end)

    -- Progress bar right below header band
    local tProg = CreateFrame("StatusBar", nil, frame)
    self.trackerBar = tProg
    tProg:SetPoint("TOPLEFT", 1, -34)
    tProg:SetSize(322, 3)
    tProg:SetStatusBarTexture("Interface\\Buttons\\WHITE8X8")
    tProg:SetStatusBarColor(unpack(GOLD))
    tProg:SetMinMaxValues(0, 1)
    local tProgBg = tProg:CreateTexture(nil, "BACKGROUND")
    tProgBg:SetAllPoints()
    tProgBg:SetColorTexture(0.12, 0.16, 0.22, 1)

    -- Step header: NPC/Place title on left + "Paso X/Y" on right
    self.trackerStep = label(frame, "GameFontNormal", "", 10, -43, 224, SKY)
    self.trackerStep:SetHeight(18)
    self.trackerProgress = label(frame, "GameFontDisableSmall", "", 234, -45, 80, MUTED)
    self.trackerProgress:SetJustifyH("RIGHT")

    -- Only the goals scroll; the header and action buttons stay accessible.
    self.trackerScroll = CreateFrame("ScrollFrame", nil, frame)
    self.trackerScroll:SetPoint("TOPLEFT", 0, -66); self.trackerScroll:SetSize(324, 100)
    self.trackerContent = CreateFrame("Frame", nil, self.trackerScroll)
    self.trackerContent:SetSize(324, 100)
    self.trackerContent:SetPoint("TOPLEFT", 0, 0)
    self.trackerScroll:SetScrollChild(self.trackerContent)
    if self.trackerScroll.SetClipsChildren then self.trackerScroll:SetClipsChildren(true) end
    self.trackerScrollThumb = frame:CreateTexture(nil, "OVERLAY")
    self.trackerScrollThumb:SetColorTexture(0.95, 0.78, 0.42, 0.7)
    self.trackerScrollThumb:SetWidth(3); self.trackerScrollThumb:Hide()
    self.trackerUpcomingLabel = label(self.trackerContent, "GameFontDisableSmall", "PRÓXIMAS MISIONES · vista previa", 10, 0, 304, MUTED)
    self.trackerUpcomingLabel:SetHeight(18); self.trackerUpcomingLabel:Hide()

    -- Fallback text for simple/finished steps
    self.trackerText = label(self.trackerContent, "GameFontHighlightSmall", "", 10, 0, 304, TEXT_MAIN)
    self.trackerText:SetSpacing(3)

    -- Grow the pool as needed: large steps are no longer cut off at six goals.
    self.CreateTrackerRow = function(_, i)
        local row = CreateFrame("Button", nil, self.trackerContent, BackdropTemplateMixin and "BackdropTemplate" or nil)
        row:SetSize(308, 36)
        if row.RegisterForClicks then row:RegisterForClicks("LeftButtonUp", "RightButtonUp") end
        row:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })

        local mark = row:CreateTexture(nil, "OVERLAY")
        mark:SetPoint("TOPLEFT", 1, -1)
        mark:SetPoint("BOTTOMLEFT", 1, 1)
        mark:SetWidth(3)
        row.mark = mark

        local icon = row:CreateTexture(nil, "ARTWORK")
        icon:SetSize(16, 16)
        icon:SetPoint("TOPLEFT", 10, -8)
        row.icon = icon

        row.title = label(row, "GameFontHighlightSmall", "", 32, -7, 268, TEXT_MAIN)
        row.title:SetSpacing(2)
        row.sub = label(row, "GameFontHighlightSmall", "", 32, -23, 268, { 0.72, 0.80, 0.90 })
        row.sub:SetSpacing(2)
        row.sub:ClearAllPoints()
        row.sub:SetPoint("TOPLEFT", row.title, "BOTTOMLEFT", 0, -4)

        row:SetScript("OnEnter", function(item)
            item:SetBackdropBorderColor(0.95, 0.78, 0.42, 0.9)
            if GameTooltip then
                GameTooltip:SetOwner(item, "ANCHOR_LEFT")
                GameTooltip:SetText(item.goalTitle or "Objetivo", 1, 0.84, 0.45)
                if item.goalSub then GameTooltip:AddLine(item.goalSub, 0.82, 0.88, 0.95, true) end
                if item.goalDetails and item.goalDetails ~= item.goalSub then
                    GameTooltip:AddLine(item.goalDetails, 0.75, 0.82, 0.90, true)
                end
                GameTooltip:AddLine(item.questPlan and "Plan del diario: informa de próximos pasos sin cambiar la misión de la flecha."
                    or item.preview and "Vista previa: primero termina el paso actual. No modifica tu progreso."
                    or item.omitted and "Clic der.: volver a incluir este objetivo"
                    or item.blocked and "Clic izq.: retomar el requisito pendiente · Clic der.: omitir"
                    or "Clic izq.: marcar destino · Clic der.: omitir o quitar la marca manual", 0.58, 0.80, 1.0, true)
                GameTooltip:Show()
            end
        end)
        row:SetScript("OnLeave", function(item)
            item:SetBackdropBorderColor(unpack(item.borderColor or { 0.16, 0.22, 0.30, 0.85 }))
            if GameTooltip then GameTooltip:Hide() end
        end)
        row:SetScript("OnClick", function(item, mouseBtn)
            if item.preview then return end
            if mouseBtn == "RightButton" and self.ToggleGoalConfirm and item.goalIndex then
                self:ToggleGoalConfirm(item.goalIndex)
            elseif item.blocked and self.Recovery and self.Recovery.StartForGoal then
                local ok, reason = self.Recovery:StartForGoal(item.goalIndex)
                if not ok and reason then self:Print(reason) end
            else
                self:Navigate()
            end
        end)
        row:Hide()
        self.trackerRows[i] = row
    end
    for i = 1, 6 do self:CreateTrackerRow(i) end

    -- Bottom action bar (repositioned dynamically as height changes)
    self.trackerPrevious = flatButton(frame, "<", 32, 22, 8, -178, function() self:Previous() end)
    self.trackerNext = flatButton(frame, "Siguiente >", 126, 22, 44, -178, advanceGuide, true)
    self.trackerSkip = flatButton(frame, "Saltar", 72, 22, 174, -178, skipShownStep)
    self.trackerMap = flatButton(frame, "Mapa", 66, 22, 250, -178, function() self:Navigate() end)
    if self.CreateTrackerLayout then self:CreateTrackerLayout() end
end

function ns:RefreshGuideList()
    if not self.window then return end
    local guides = self:GetVisibleGuides(self.search:GetText(), self.char.allFactions)
    self.factionButton:SetText(self.char.allFactions and "Ver: todas las facciones" or "Ver: mi facción")
    self.noResults:SetShown(#guides == 0)
    self.listContent:SetHeight(math.max(332, #guides * 66))
    local playerMap = C_Map and C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")

    for index, guide in ipairs(guides) do
        local row = self.rows[index]
        if not row then
            row = CreateFrame("Button", nil, self.listContent, BackdropTemplateMixin and "BackdropTemplate" or nil)
            row:SetSize(232, 60)
            row:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
            row.title = label(row, "GameFontHighlight", "", 10, -8, 212)
            row.title:SetHeight(28)
            row.meta = label(row, "GameFontHighlightSmall", "", 10, -40, 212, MUTED)
            row:SetScript("OnClick", function(item) self:SelectGuide(item.guideID) end)
            row:SetScript("OnEnter", function(item) item:SetBackdropBorderColor(unpack(GOLD)) end)
            row:SetScript("OnLeave", function() self:RefreshGuideList() end)
            self.rows[index] = row
        end
        row.guideID = guide.id
        row:ClearAllPoints()
        row:SetPoint("TOPLEFT", 0, -((index - 1) * 66))
        local inZone = playerMap and guide.zone == playerMap
        row.title:SetText((inZone and "|cff6be09e★ |r" or "") .. guide.title)
        local state = self:GetProgress(guide.id)
        local levels = guide.minLevel and ("Niv. " .. guide.minLevel .. "–" .. (guide.maxLevel or "?")) or "Guía"
        local doneQ, totalQ = 0, 0
        if self.GetGuideQuestStats then doneQ, totalQ = self:GetGuideQuestStats(guide) end
        local pct = math.floor((state.cursor - 1) / #guide.steps * 100)
        local metaText = levels .. (totalQ > 0 and (" · " .. doneQ .. "/" .. totalQ .. " mis.") or (" · " .. pct .. "%"))
        if inZone then metaText = "|cff6be09eTu zona|r · " .. metaText end
        row.meta:SetText(metaText)
        local active = guide.id == self.char.activeGuide
        row:SetBackdropColor(active and 0.16 or 0.07, active and 0.14 or 0.095, active and 0.09 or 0.14, 1)
        if active then row:SetBackdropBorderColor(unpack(GOLD))
        elseif inZone then row:SetBackdropBorderColor(0.32, 0.68, 0.48, 0.9)
        else row:SetBackdropBorderColor(0.16, 0.21, 0.29, 1) end
        row:Show()
    end
    for index = #guides + 1, #self.rows do self.rows[index]:Hide() end
    self.listScroll:SetVerticalScroll(math.min(self.listScroll:GetVerticalScroll(), self.listScroll:GetVerticalScrollRange()))
    self.guideCount:SetText(#guides .. " guías disponibles · " .. #self.order .. " en total")
end

function ns:RefreshUI()
    if not self.window then return end
    self:RefreshGuideList()
    self.autoCheck:SetChecked(self.char.auto)
    self.trackCheck:SetChecked(self.char.tracker)
    if self.arrowCheck then self.arrowCheck:SetChecked(self.char.arrow ~= false) end
    if self.optionalCheck then self.optionalCheck:SetChecked(self.char.optional and true or false) end

    local currentZone = GetRealZoneText and GetRealZoneText() or nil
    local playerLevel = UnitLevel and UnitLevel("player") or 1
    if currentZone and currentZone ~= "" then
        self.recordingLabel:SetText("Estás en: |cffffce72" .. currentZone .. "|r · Nivel " .. tostring(playerLevel))
    else
        self.recordingLabel:SetText("Guías paso a paso con detección automática de zona")
    end

    local guide, step, state, sharedView
    local travel = self.GetGuideTravel and self:GetGuideTravel()
    if not travel and self.GetDisplayedCurrent then guide, step, state, sharedView = self:GetDisplayedCurrent()
    else guide, step, state = self:GetCurrent() end
    if travel then step = travel end
    self.currentDuoView = sharedView
    if not guide then self.detail:Hide(); self.tracker:Hide(); return end
    self.detail:Show()

    local faction = guide.faction == "Alliance" and "Alianza" or guide.faction == "Horde" and "Horda" or "Ambas facciones"
    local kind = (guide.zoneName or guide.kind or "Guía") .. " · " .. faction
    if guide.minLevel then kind = kind .. " · Niveles " .. guide.minLevel .. "–" .. (guide.maxLevel or "?") end
    if self.GetGuideQuestStats then
        local doneQ, totalQ = self:GetGuideQuestStats(guide)
        if totalQ > 0 then kind = kind .. " · " .. doneQ .. "/" .. totalQ .. " misiones hechas" end
    end
    self.guideKind:SetText(kind)
    self.guideTitle:SetText(guide.title)
    self.guideSummary:SetText(guide.summary or "")

    local complete = state.cursor > #guide.steps
    local continuation, reason, managed
    if complete and not sharedView and (not travel or travel.waiting) and self.GetGuideContinuation then
        continuation, reason, managed = self:GetGuideContinuation()
    end
    local localFinish = managed and "Tu parte está hecha"
    local travelProgress = travel and "Viaje"
    local ratio = math.max(0, math.min(1, (state.cursor - 1) / #guide.steps))
    if travel and travel.index and travel.total then
        travelProgress = "Viaje " .. travel.index .. "/" .. travel.total
        ratio = (travel.index - 1) / travel.total
    end
    self.progressBar:SetValue(ratio)
    if self.trackerBar then self.trackerBar:SetValue(ratio) end

    self.stepCount:SetText(travelProgress or managed and "DÚO" or complete and ("¡Recorrido completado! (" .. #guide.steps .. " pasos)") or
        ("PASO " .. state.cursor .. " DE " .. #guide.steps .. (state.review and " · Revisando paso anterior" or "")))
    self.stepTitle:SetText(step and step.title or localFinish or "¡Has completado esta zona!")
    if sharedView then self.stepCount:SetText("DÚO · PASO " .. state.cursor .. " DE " .. #guide.steps .. " · Tu progreso: " .. sharedView.ownCursor) end

    local waypoint
    if travel then waypoint = travel.point
    elseif self.GetStepWaypoint then waypoint = self:GetStepWaypoint(step)
    else waypoint = step and step.waypoint end
    local objectives = travel and "" or self:GetObjectives(step)
    local sharedItems = sharedView and self.GetFollowingGoalItems and self:GetFollowingGoalItems(sharedView)
    if sharedView then objectives = self:GetFollowingObjectives(sharedItems) end
    local text
    if step then
        local blocks = {}
        if sharedView then blocks[#blocks + 1] = "|cffffce72Acompañas al que va más atrás. Tu progreso propio se conserva en el paso " .. sharedView.ownCursor .. ".|r" end
        local body = step.text or step.note
        if body and body ~= "" then blocks[#blocks + 1] = "|cff9fb0c7" .. body .. "|r" end
        if objectives ~= "" then blocks[#blocks + 1] = objectives end
        if waypoint then
            blocks[#blocks + 1] = string.format("|cff6c7a89Coordenadas: %.1f, %.1f|r", waypoint.x * 100, waypoint.y * 100)
        end
        text = table.concat(blocks, "\n\n")
    else
        if sharedView then
            reason = "Esperando al compañero."
        end
        text = continuation and ("Continúa en |cffffce72" .. continuation.title .. "|r.")
            or reason or "Elige otra ruta en «Guías»."
    end
    self.stepText:SetText(text)
    self.stepContent:SetHeight(math.max(182, self.stepText:GetStringHeight() + 12))
    local stepKey = guide.id .. ":" .. (travel and ("travel:" .. travel.title) or state.cursor)
    if self.lastStepKey ~= stepKey then self.stepScroll:SetVerticalScroll(0); self.lastStepKey = stepKey end

    local editSteps = not travel and not sharedView
    local restorePrevious = self.GetPreviousRestorableStep and self:GetPreviousRestorableStep()
    local canGoBack = not travel and (restorePrevious or editSteps and state.cursor > 1)
    self.previousButton:SetEnabled(canGoBack)
    for _, button in ipairs({self.nextButton, self.trackerNext}) do
        button.continuesGuide = continuation ~= nil
        button.startsTravelHere = travel and travel.waiting and travel.localStart == true
        button.groundDetour = travel and travel.groundOption ~= nil
        button:SetText(button.groundDetour and "Ir sin vuelo" or button.startsTravelHere and "Empezar aquí"
            or complete and "Continuar" or "Siguiente >")
        button:SetEnabled(button.groundDetour or button.startsTravelHere or editSteps and not complete or continuation ~= nil)
    end
    for _, button in ipairs({self.skipButton, self.trackerSkip}) do
        button.skipsTravel = travel ~= nil
        button:SetText(travel and "Omitir viaje" or button == self.skipButton and "Saltar paso" or "Saltar")
        button:SetEnabled(travel and not travel.waiting or editSteps and not complete)
    end
    self.mapButton:SetEnabled(waypoint and true or false)
    self.mapButton:SetText(waypoint and "Marcar mapa" or "Sin pin")

    -- Update Compact Tracker
    local lvlBadge = guide.minLevel and (" (" .. guide.minLevel .. "–" .. (guide.maxLevel or "?") .. ")") or ""
    self.trackerTitle:SetText(guide.title .. lvlBadge)
    local partnerVisit = sharedView and step and step.only and not self:MatchesConditions(step.only)
    self.trackerStep:SetText(partnerVisit and ("Tu amigo · " .. step.title) or step and step.title or localFinish or "¡Zona completada!")
    self.trackerProgress:SetText(travelProgress or managed and "Dúo" or complete and "Completada" or ("Paso " .. state.cursor .. "/" .. #guide.steps))
    if sharedView then self.trackerProgress:SetText((partnerVisit and "Amigo " or "Juntos ") .. state.cursor .. " · Tú " .. sharedView.ownCursor) end

    local goalItems = sharedItems or ((not travel and step and self.GetStepGoalItems) and self:GetStepGoalItems(step, state) or {})
    local displayItems = {}
    for _, item in ipairs(goalItems) do displayItems[#displayItems + 1] = item end
    local expanded = self.char.trackerSize or self.tracker.isResizing
    local preview, planned = {}, 0
    local previewGetter = self.GetTrackerPlannedUpcomingItems or self.GetTrackerUpcomingItems
    if not travel and previewGetter then
        for _, item in ipairs(previewGetter(self, guide, state.cursor, 12)) do
            if expanded or item.questPlan then
                preview[#preview + 1] = item
                if item.questPlan then planned = planned + 1 end
            end
        end
    end
    if self.trackerUpcomingLabel then
        self.trackerUpcomingLabel:SetText(planned > 0 and "EN TU DIARIO · plan del recorrido" or "PRÓXIMAS MISIONES · vista previa")
    end
    self.trackerCurrentCount, self.trackerPreviewCount = #goalItems, #preview
    for _, item in ipairs(preview) do displayItems[#displayItems + 1] = item end
    if self.trackerDisplayKey ~= stepKey then
        self.trackerScroll:SetVerticalScroll(0); self.trackerDisplayKey = stepKey
    end
    if step and #displayItems > 0 then
        self.trackerText:SetText("")
        self.trackerText:Hide()
        local shownCount = #displayItems
        for i = 1, shownCount do
            local item = displayItems[i]
            if not self.trackerRows[i] then self:CreateTrackerRow(i) end
            local row = self.trackerRows[i]
            local meta = ACTION_ICONS[item.action] or ACTION_ICONS.goto
            local omitted = item.status == "skip" and item.reason
                and item.reason:find("^Omitido manualmente") ~= nil
            row.goalIndex = item.index
            row.goalTitle = omitted and ("Omitido · " .. item.title) or item.title
            row.omitted = omitted
            row.preview = item.preview == true
            row.blocked = not sharedView and not row.preview and item.status == "blocked"
            row.questPlan = item.questPlan == true
            local subtitle = item.subtitle
            if item.status ~= "done" and not row.preview and not sharedView and self.GetDuoGoalSuffix and step.goals and item.index then
                local suffix = self:GetDuoGoalSuffix(step.goals[item.index], step)
                if suffix and suffix ~= "" then subtitle = (subtitle and subtitle ~= "" and subtitle .. " · " or "") .. suffix end
            end
            row.goalSub = subtitle
            row.goalDetails = item.details
            if row.icon.SetTexture then
                row.icon:SetTexture(UI_MEDIA .. (item.status == "done" and "check" or meta.icon))
            end
            if row.icon.SetVertexColor then
                if item.status == "done" then
                    row.icon:SetVertexColor(unpack(GREEN))
                elseif omitted then
                    row.icon:SetVertexColor(unpack(MUTED))
                else
                    row.icon:SetVertexColor(unpack(meta.color))
                end
            end
            local titleColor = (row.preview or omitted) and "|cff9facbd" or item.status == "done" and "|cff6be09e"
                or (item.isCurrent and "|cffffe08c" or "|cffe8eef7")
            row.title:SetText(titleColor .. row.goalTitle .. "|r")
            local titleH = math.max(14, row.title:GetStringHeight() or 14)
            if subtitle and subtitle ~= "" then
                row.sub:SetText(subtitle)
                row.sub:Show()
                local subH = math.max(13, row.sub:GetStringHeight() or 13)
                row:SetHeight(math.max(40, titleH + subH + 17))
            else
                row.sub:SetText("")
                row.sub:Hide()
                row:SetHeight(math.max(28, titleH + 14))
            end
            if item.status == "done" then
                row.mark:SetColorTexture(unpack(GREEN))
                row:SetBackdropColor(0.05, 0.11, 0.09, 0.85)
                row.borderColor = { 0.18, 0.36, 0.26, 0.85 }
            elseif item.isCurrent and not omitted then
                row.mark:SetColorTexture(unpack(GOLD))
                row:SetBackdropColor(0.11, 0.14, 0.21, 0.95)
                row.borderColor = { 0.45, 0.38, 0.22, 0.95 }
            else
                row.mark:SetColorTexture(0.28, 0.36, 0.48, 0.8)
                row:SetBackdropColor(0.06, 0.085, 0.13, 0.88)
                row.borderColor = { 0.16, 0.22, 0.30, 0.85 }
            end
            row:SetBackdropBorderColor(unpack(row.borderColor))
            row:Show()
        end
        for i = shownCount + 1, #self.trackerRows do self.trackerRows[i]:Hide() end
    else
        for i = 1, #self.trackerRows do self.trackerRows[i]:Hide() end
        local trackerBody = step and (step.text or step.note or objectives or "") or text
        if step and objectives ~= "" and trackerBody ~= objectives then
            trackerBody = objectives .. "\n" .. trackerBody
        end
        self.trackerText:SetText(trackerBody)
        self.trackerText:Show()
    end
    if self.LayoutTracker then self:LayoutTracker() end
    self.trackerPrevious:SetEnabled(canGoBack)
    self.trackerMap:SetEnabled(waypoint and true or false)
    self.tracker:SetShown(self.char.tracker and not self.window:IsShown())
end
