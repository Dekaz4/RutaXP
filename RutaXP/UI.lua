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
    boat = { icon = "icon-goto", color = { 0.58, 0.80, 1.00 } },
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

local function selectorCard(frame, gold)
    frame:SetBackdrop(ns.JourneyCardBackdrop or BACKDROP_GLUE_TOOLTIP_16_16 or {
        bgFile = "Interface\\Tooltips\\UI-Tooltip-Background",
        edgeFile = "Interface\\Tooltips\\UI-Tooltip-Border", edgeSize = 16,
        insets = {left=4, right=4, top=4, bottom=4},
    })
    if ns.StyleJourneyCard then
        ns.StyleJourneyCard(frame, gold)
    else
        frame:SetBackdropColor(0.025, 0.021, 0.014, 0.97)
        frame:SetBackdropBorderColor(gold and 0.78 or 0.66, gold and 0.73 or 0.66, gold and 0.56 or 0.66)
    end
end

-- Modern flat button replacing ugly red Blizzard UIPanelButtonTemplate
local function flatButton(parent, text, width, height, x, y, action, accent)
    local btn = CreateFrame("Button", nil, parent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    btn:SetSize(width, height or 24)
    btn:SetPoint("TOPLEFT", x, y)
    if parent.selectorSkin then selectorCard(btn, accent)
    else btn:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 }) end
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
        elseif parent.selectorSkin then
            btn:SetBackdropColor(hover and 0.13 or 0.04, hover and 0.10 or 0.035, hover and 0.05 or 0.025, 0.98)
            btn:SetBackdropBorderColor(hover and 0.95 or 0.59, hover and 0.78 or 0.57, hover and 0.42 or 0.52, 1)
            lbl:SetTextColor(1, hover and 0.86 or 0.95, hover and 0.56 or 0.85)
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
    if button.circuitKey then
        ns:DeferLocalCircuitStop(button.circuitKey)
    elseif button.resumeTravelChoice then
        ns:ResumeTravelChoice(button.resumeTravelChoice)
    elseif button.flightGround then
        ns.FlightNavigation:BeginGround()
    elseif button.groundDetour then
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
    selectorCard(frame)
    frame.selectorSkin = true
    frame:SetFrameStrata("DIALOG")
    frame:SetScale(math.min(1, UIParent:GetWidth() / 880, UIParent:GetHeight() / 600))
    moveable(frame, "windowPosition", "CENTER", 0, 0)
    frame:Hide()

    local header = panel(frame, 804, 48)
    header:SetPoint("TOPLEFT", 30, -5)
    selectorCard(header, true)
    header.selectorSkin = true
    local emblem = header:CreateTexture(nil, "OVERLAY")
    emblem:SetPoint("CENTER", header, "LEFT", 3, 0)
    if ns.SetJourneyEmblem then ns.SetJourneyEmblem(emblem)
    else emblem:SetSize(34, 34); emblem:SetTexture("Interface\\Icons\\INV_Misc_Map_01") end
    label(header, "GameFontNormalLarge", "Rutas de leveo", 39, -6, 360, GOLD)
    self.recordingLabel = label(header, "GameFontHighlightSmall", "", 40, -27, 368, TEXT_MAIN)

    -- Zone auto-detect & Talent Guides buttons in header
    self.talentsButton = flatButton(header, "Talentos (N)", 106, 26, 432, -11, function()
        if self.Talents and self.Talents.TogglePanel then
            self.Talents.TogglePanel()
        end
    end)

    self.zoneDetectButton = flatButton(header, "Detectar guía de mi zona", 220, 26, 545, -11, function()
        if self.DetectZoneGuide then self:DetectZoneGuide(false) end
    end, true)

    flatButton(header, "×", 26, 26, 770, -11, function()
        frame:Hide()
        self:RefreshUI()
    end)

    -- Left column: Guide Browser
    local browser = panel(frame, 278, 494)
    browser:SetPoint("TOPLEFT", 8, -58)
    selectorCard(browser)
    browser.selectorSkin = true
    label(browser, "GameFontNormal", "Buscar una guía", 12, -10, 254, GOLD)
    local search = CreateFrame("EditBox", nil, browser, "InputBoxTemplate")
    self.search = search
    search:SetSize(248, 24)
    search:SetPoint("TOPLEFT", 17, -32)
    search:SetAutoFocus(false)
    search:SetMaxLetters(80)
    search:SetScript("OnEscapePressed", function(box) box:ClearFocus() end)
    search:SetScript("OnEnterPressed", function(box) box:ClearFocus() end)
    search:SetScript("OnTextChanged", function()
        self.listScroll:SetVerticalScroll(0)
        self:RefreshGuideList()
    end)

    self.factionButton = flatButton(browser, "Mi facción", 254, 24, 12, -66, function()
        self.char.allFactions = not self.char.allFactions
        self.listScroll:SetVerticalScroll(0)
        self:RefreshGuideList()
    end)

    local scroll = CreateFrame("ScrollFrame", nil, browser, "UIPanelScrollFrameTemplate")
    self.listScroll = scroll
    scroll:SetPoint("TOPLEFT", 12, -98)
    scroll:SetSize(236, 365)
    if scroll.SetClipsChildren then scroll:SetClipsChildren(true) end
    local content = CreateFrame("Frame", nil, scroll)
    content:SetSize(236, 365)
    self.listContent = content
    scroll:SetScrollChild(content)
    self.noResults = label(content, "GameFontHighlight", "No hay guías con este filtro.", 8, -12, 215, MUTED)
    self.guideCount = label(browser, "GameFontHighlightSmall", "", 12, -472, 254, MUTED)
    frame:SetScript("OnShow", function() self.revealActiveGuide = true end)
    self.revealActiveGuide = true

    -- Right column: Active Guide & Current Step
    local detail = panel(frame, 524, 434, 0.065, 0.09, 0.135, 0.98)
    self.detail = detail
    selectorCard(detail, true)
    detail.selectorSkin = true
    detail:SetPoint("TOPLEFT", 296, -62)

    self.guideTitle = label(detail, "GameFontNormalLarge", "", 18, -12, 488, GOLD)
    self.guideKind = label(detail, "GameFontHighlightSmall", "", 18, -43, 488, TEXT_MAIN)
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
    self.localTravelButton = flatButton(detail, "Hacer misiones cercanas", 174, 21, 330, -127,
        function(button) self:ChooseLocalQuests(button.choiceKey) end)
    self.localTravelButton:Hide()
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
    optional:SetScript("OnClick", function(box)
        self.char.optional = box:GetChecked() and true or false
        if self.Adaptation then self.Adaptation:Invalidate() end
        self:ClearDeferredGroupMapPin()
        self:Sync()
    end)

    local group = CreateFrame("CheckButton", nil, frame, "UICheckButtonTemplate")
    self.groupQuestCheck = group
    group:SetSize(24, 24)
    group:SetPoint("TOPLEFT", 296, -530)
    label(frame, "GameFontHighlightSmall", "Incluir misiones de grupo", 322, -536, 175)
    group:SetScript("OnClick", function(box) self:SetIncludeGroupQuests(box:GetChecked() and true or false) end)
    label(frame, "GameFontDisableSmall", "Mantén Mayús al hablar para pausar la recogida automática.", 507, -536, 316)

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
                GameTooltip:AddLine(item.choiceKey and "Clic para seguir estas misiones antes de viajar."
                    or item.localObjective and "Clic para marcar este objetivo en el mapa."
                    or item.questPlan and "Plan del diario: informa de próximos pasos sin cambiar la misión de la flecha."
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
            if item.choiceKey then
                if mouseBtn ~= "RightButton" then self:ChooseLocalQuests(item.choiceKey) end
                return
            end
            if item.localObjective then
                if mouseBtn ~= "RightButton" then self:Navigate() end
                return
            end
            if item.preview then return end
            if mouseBtn == "RightButton" and self.ToggleGoalConfirm and item.goalIndex then
                self:ToggleGoalConfirm(item.goalIndex)
            elseif item.blocked and self.Recovery and self.Recovery.StartForGoal then
                local ok, reason = self.Recovery:StartForGoal(item.goalIndex)
                if not ok and reason then self:Print(reason) end
            else
                self:Navigate(item.goalIndex)
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
    local query = self.search:GetText() or ""
    local guides = self:GetVisibleGuides(query, self.char.allFactions)
    self.factionButton:SetText(self.char.allFactions and "Facción: todas" or "Facción: la mía")
    self.noResults:SetShown(#guides == 0)
    local rowStride, viewportHeight = 58, self.listScroll:GetHeight()
    local contentHeight = math.max(viewportHeight, #guides * rowStride)
    self.listContent:SetHeight(contentHeight)
    local playerMap = C_Map and C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")
    local activeTop

    for index, guide in ipairs(guides) do
        local row = self.rows[index]
        if not row then
            row = CreateFrame("Button", nil, self.listContent, BackdropTemplateMixin and "BackdropTemplate" or nil)
            row:SetSize(232, 55)
            selectorCard(row)
            row.title = label(row, "GameFontHighlight", "", 10, -8, 212)
            row.title:SetHeight(28)
            row.meta = label(row, "GameFontHighlightSmall", "", 10, -36, 212, MUTED)
            row:SetScript("OnClick", function(item) self:SelectGuide(item.guideID) end)
            row:SetScript("OnEnter", function(item) item:SetBackdropBorderColor(unpack(GOLD)) end)
            row:SetScript("OnLeave", function(item) item:SetBackdropBorderColor(unpack(item.borderColor)) end)
            self.rows[index] = row
        end
        row.guideID = guide.id
        row:ClearAllPoints()
        local top = (index - 1) * rowStride
        row:SetPoint("TOPLEFT", 0, -top)
        local inZone = playerMap and guide.zone == playerMap
        local active = guide.id == self.char.activeGuide
        row.title:SetText(guide.title)
        row.title:SetTextColor(unpack(active and GOLD or TEXT_MAIN))
        local state = self:GetProgress(guide.id)
        local levels = guide.minLevel and ("Niv. " .. guide.minLevel .. "–" .. (guide.maxLevel or "?")) or "Guía"
        local pct = math.min(100, math.floor((state.cursor - 1) / math.max(1, #guide.steps) * 100))
        local metaText = levels .. (pct > 0 and (" · " .. pct .. "%") or "")
        if inZone then metaText = "|cff6be09eTu zona|r · " .. metaText end
        if active then metaText = "|cffffcf52Activa|r · " .. metaText; activeTop = top end
        row.meta:SetText(metaText)
        row:SetBackdropColor(active and 0.16 or 0.035, active and 0.12 or 0.032, active and 0.045 or 0.025, 1)
        row.borderColor = active and GOLD or inZone and GREEN or {0.48, 0.46, 0.42}
        row:SetBackdropBorderColor(unpack(row.borderColor))
        row:Show()
    end
    for index = #guides + 1, #self.rows do self.rows[index]:Hide() end
    local offset = self.listScroll:GetVerticalScroll()
    if activeTop and not query:find("%S") and (self.revealActiveGuide or self.listGuideID ~= self.char.activeGuide) then
        if activeTop < offset then offset = activeTop
        elseif activeTop + rowStride > offset + viewportHeight then offset = activeTop + rowStride - viewportHeight end
    end
    self.listScroll:SetVerticalScroll(math.min(offset, contentHeight - viewportHeight))
    self.revealActiveGuide, self.listGuideID = false, self.char.activeGuide
    self.guideCount:SetText(#guides == #self.order and (#guides .. " guías") or string.format("%d de %d guías", #guides, #self.order))
end

function ns:RefreshUI()
    if not self.window then return end
    if self.window:IsShown() then self:RefreshGuideList() else self.revealActiveGuide = true end
    self.autoCheck:SetChecked(self.char.auto)
    self.trackCheck:SetChecked(self.char.tracker)
    if self.arrowCheck then self.arrowCheck:SetChecked(self.char.arrow ~= false) end
    if self.optionalCheck then self.optionalCheck:SetChecked(self.char.optional and true or false) end
    if self.groupQuestCheck then self.groupQuestCheck:SetChecked(self.char.includeGroupQuests == true) end

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
    if not guide then self.displayedCircuitStop = nil; self.detail:Hide(); self.tracker:Hide(); return end
    self.detail:Show()
    local choice, localObjective
    if not sharedView and self.GetTravelComparison then choice, localObjective = self:GetTravelComparison() end
    local circuit = not localObjective and not choice and not travel and not sharedView and self.GetLocalCircuitStop
        and self:GetLocalCircuitStop(step)
    self.displayedCircuitStop = circuit or nil
    local sideTrip = circuit and not circuit.authored
    local localTitle, localQuestTitle, localHint
    if localObjective then
        local goal = localObjective.goal
        localTitle,localQuestTitle = self:GetGoalTitle(goal,true)
        localHint = self:GetGoalHint(goal) or goal.target or goal.itemName or goal.objName
        local npc = localObjective.point.candidateName or goal.npcName
        if not localHint and npc then localHint = goal.t == "turnin" and ("Habla con " .. npc) or npc end
    end
    self.localTravelButton.choiceKey = choice and choice.key
    self.localTravelButton:SetShown(choice and not localObjective and choice.localGoals and choice.localGoals[1] ~= nil or false)

    local faction = guide.faction == "Alliance" and "Alianza" or guide.faction == "Horde" and "Horda" or "Ambas facciones"
    local category = guide.zoneName or guide.kind
    local kind = category and category ~= guide.title and (category .. " · " .. faction) or faction
    if guide.minLevel then kind = kind .. " · Niveles " .. guide.minLevel .. "–" .. (guide.maxLevel or "?") end
    if self.window:IsShown() and self.GetGuideQuestStats then
        local doneQ, totalQ = self:GetGuideQuestStats(guide)
        if totalQ > 0 then kind = kind .. " · " .. doneQ .. "/" .. totalQ .. " misiones hechas" end
    end
    self.guideKind:SetText(kind)
    self.guideTitle:SetText(guide.title)
    self.guideSummary:SetText(guide.summary ~= guide.title and guide.summary or "")

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

    self.stepCount:SetText(travelProgress or managed and "Fin de la ruta" or complete and ("Recorrido completado · " .. #guide.steps .. " pasos") or
        ("Paso " .. state.cursor .. " de " .. #guide.steps .. (state.review and " · En revisión" or "")))
    self.stepTitle:SetText(step and step.title or localFinish or "¡Has completado esta zona!")
    if sharedView then self.stepCount:SetText("Paso " .. state.cursor .. " de " .. #guide.steps .. " · Tu progreso: " .. sharedView.ownCursor) end

    local waypoint
    if localObjective then waypoint = self:GetLocalTravelPoint(localObjective)
    elseif travel then waypoint = travel.point
    elseif self.GetStepWaypoint then waypoint = self:GetStepWaypoint(step, nil, {})
    else waypoint = step and step.waypoint end
    local objectives = travel and "" or self:GetObjectives(step)
    local sharedItems = sharedView and self.GetFollowingGoalItems and self:GetFollowingGoalItems(sharedView)
    if sharedView then objectives = self:GetFollowingObjectives(sharedItems) end
    local text
    if step then
        local blocks = {}
        local body = step.text or step.note
        if body and body ~= "" and body ~= step.title and not objectives:find(body, 1, true) then
            blocks[#blocks + 1] = "|cffdbd5c8" .. body .. "|r"
        end
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
    if choice then
        text = localObjective and (localTitle .. (localHint and ("\n" .. localHint) or "") .. "\n\n" .. choice.summary)
            or (choice.summary .. "\n\n" .. text)
        if localObjective then self.stepTitle:SetText("Mis misiones cercanas") end
    elseif sideTrip then
        self.stepTitle:SetText(circuit.step.title)
        text = self:GetGoalTitle(circuit.goal, true) .. "\n" .. circuit.reason
    elseif circuit then
        text = circuit.reason .. "\n\n" .. text
    end
    self.stepText:SetText(text)
    self.stepContent:SetHeight(math.max(182, self.stepText:GetStringHeight() + 12))
    local stepKey = guide.id .. ":" .. (travel and ("travel:" .. travel.title) or state.cursor)
    if sideTrip then stepKey = stepKey .. ":" .. circuit.key end
    if self.lastStepKey ~= stepKey then self.stepScroll:SetVerticalScroll(0); self.lastStepKey = stepKey end

    local editSteps = not travel and not sharedView
    local restorePrevious = self.GetPreviousRestorableStep and self:GetPreviousRestorableStep()
    local canGoBack = not sideTrip and not localObjective and not travel and (restorePrevious or editSteps and state.cursor > 1)
    self.previousButton:SetEnabled(canGoBack)
    local flight = editSteps and self.FlightNavigation and self.FlightNavigation:CurrentView()
    if waypoint and not waypoint.flightNavigation then flight = nil end
    for _, button in ipairs({self.nextButton, self.trackerNext}) do
        button.circuitKey = sideTrip and circuit.key or nil
        button.resumeTravelChoice = localObjective and choice.key
        button.continuesGuide = continuation ~= nil
        button.startsTravelHere = travel and travel.waiting and travel.localStart == true
        button.groundDetour = travel and travel.groundOption ~= nil
        button.flightGround = flight and flight.canGround == true
        button:SetText(sideTrip and "Seguir el paso" or localObjective and "Retomar viaje" or (button.flightGround or button.groundDetour) and "Ir sin vuelo" or button.startsTravelHere and "Empezar aquí"
            or complete and "Continuar" or "Siguiente >")
        button:SetEnabled(localObjective or button.groundDetour or button.startsTravelHere or editSteps and not complete or continuation ~= nil)
    end
    for _, button in ipairs({self.skipButton, self.trackerSkip}) do
        button.skipsTravel = travel ~= nil
        button:SetText(travel and "Omitir viaje" or button == self.skipButton and "Saltar paso" or "Saltar")
        button:SetEnabled(not sideTrip and not localObjective and (travel and not travel.waiting or editSteps and not complete))
    end
    self.mapButton:SetEnabled(waypoint and true or false)
    self.mapButton:SetText(waypoint and "Marcar mapa" or "Sin pin")

    -- Update Compact Tracker
    local lvlBadge = guide.minLevel and (" (" .. guide.minLevel .. "–" .. (guide.maxLevel or "?") .. ")") or ""
    self.trackerTitle:SetText(guide.title .. lvlBadge)
    local partnerVisit = sharedView and step and step.only and not self:MatchesConditions(step.only)
    self.trackerStep:SetText(sideTrip and circuit.step.title or localObjective and "Mis misiones cercanas" or partnerVisit and ("Tu amigo · " .. step.title) or step and step.title or localFinish or "¡Zona completada!")
    self.trackerProgress:SetText(travelProgress or managed and "Dúo" or complete and "Completada" or ("Paso " .. state.cursor .. "/" .. #guide.steps))
    if sharedView then self.trackerProgress:SetText((partnerVisit and "Amigo " or "Juntos ") .. state.cursor .. " · Tú " .. sharedView.ownCursor) end

    local shownStep = sideTrip and circuit.step or step
    local goalItems = sharedItems or ((not travel and shownStep and self.GetStepGoalItems) and self:GetStepGoalItems(shownStep, state) or {})
    if circuit then
        local selected
        for _, item in ipairs(goalItems) do
            if item.index == circuit.index and item.goal == circuit.goal then
                selected = item
                break
            end
        end
        if sideTrip then
            if not selected then
                local goal = circuit.goal
                local title, questTitle = self:GetGoalTitle(goal, true)
                selected = {goal=goal, action=goal.t, title=title, questTitle=questTitle, status="active",
                    subtitle=self:GetGoalHint(goal), details=self:GetGoalInstruction(goal)}
            end
            selected.index, selected.isCurrent, selected.localObjective = nil, true, true
            goalItems = {selected}
        end
        if selected then
            selected.subtitle = selected.subtitle and (selected.subtitle .. "\n" .. circuit.reason) or circuit.reason
        end
    elseif localObjective then
        goalItems = {{action=localObjective.goal.t, title=localTitle, questTitle=localQuestTitle, goal=localObjective.goal,
            npcName=localObjective.point.candidateName or localObjective.goal.npcName, isCurrent=true,
            subtitle=localHint, details=self:GetGoalInstruction(localObjective.goal), localObjective=true}}
    elseif choice then
        local canStay = choice.localGoals and choice.localGoals[1] ~= nil
        local items = {{action="note", title=canStay and (choice.preferLocal and "Hacer misiones cercanas · Recomendado"
            or "Hacer misiones cercanas") or "Antes de viajar",
            subtitle=choice.summary, choiceKey=canStay and choice.key or nil, preview=not canStay}}
        if travel then
            items[2] = {action="goto", title=travel.title, subtitle=travel.text, isCurrent=true}
        else
            for _, item in ipairs(goalItems) do items[#items + 1] = item end
        end
        goalItems = items
    end
    local displayItems = {}
    for _, item in ipairs(goalItems) do displayItems[#displayItems + 1] = item end
    local expanded = self.char.trackerSize or self.tracker.isResizing
    local preview, planned = {}, 0
    local previewGetter = self.GetTrackerPlannedUpcomingItems or self.GetTrackerUpcomingItems
    if not localObjective and not travel and previewGetter then
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
            row.presentationItem = item
            local meta = ACTION_ICONS[item.action] or ACTION_ICONS.goto
            local omitted = item.status == "skip" and item.reason
                and item.reason:find("^Omitido manualmente") ~= nil
            row.goalIndex = item.index
            row.choiceKey, row.localObjective = item.choiceKey, item.localObjective
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
