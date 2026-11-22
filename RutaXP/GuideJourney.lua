local _, ns = ...
local view = {}
ns.GuideJourney = view

local env, settings, engine, arrow, target, current, groupStep
local loggedIn, initialized, shown, refreshPending
local title, subtitle, status, stepIndex, stepCount, progressText
local scroll, scrollChild, compassHint
local original = ns.OriginalGuidePresentation
local originWorld, originNorth, originWest, lastDirections
local function finite(n)
    if issecretvalue and issecretvalue(n) then return false end
    return type(n) == "number" and n == n and math.abs(n) < math.huge
end

local function compassFacing()
    local angle = GetPlayerFacing and GetPlayerFacing()
    if finite(angle) then return angle end
end

local function sampleOrigin()
    originWorld, originNorth, originWest = nil, nil, nil
    local map = C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")
    local pos = finite(map) and C_Map.GetPlayerMapPosition and C_Map.GetPlayerMapPosition(map, "player")
    if not pos then return end
    local x,y = pos:GetXY()
    if not finite(x) or not finite(y) then return end
    local world, p = C_Map.GetWorldPosFromMapPos(map, CreateVector2D(x,y))
    if not p then return end
    local north,west = p:GetXY()
    if finite(world) and finite(north) and finite(west) then originWorld, originNorth, originWest = world,north,west end
end

-- Both ends of Journey's bearing must be in the same coordinate system.
-- Forever may report a phased instance ID or no native player position even
-- when the player's location on the zone map is usable. Keep the live native
-- sample for smooth movement whenever it agrees with the mapped position.
local function compassPosition(unit)
    local x,y,z,world
    if UnitPosition then x,y,z,world = UnitPosition(unit) end
    if unit == "player" and originWorld and (not finite(world) or world ~= originWorld or not finite(x) or not finite(y)
        or (x-originNorth)^2 + (y-originWest)^2 > 10000) then
        return originNorth, originWest, nil, originWorld
    end
    if finite(x) and finite(y) and finite(world) then return x,y,z,world end
end

local anchors = {CENTER=true, TOP=true, BOTTOM=true, LEFT=true, RIGHT=true,
    TOPLEFT=true, TOPRIGHT=true, BOTTOMLEFT=true, BOTTOMRIGHT=true}
local function placeCompass()
    local saved = settings.HUDArrowLocation
    if not (type(saved) == "table" and anchors[saved[1]] and anchors[saved[3]]
        and finite(saved[4]) and finite(saved[5])) then
        local old = original and ns.char.arrowPosition
        if old and anchors[old.point] and anchors[old.relativePoint] and finite(old.x) and finite(old.y) then
            saved = {old.point, "UIParent", old.relativePoint, old.x, old.y}
        else
            saved = {"CENTER", "UIParent", "TOP", 0, -110}
        end
        settings.HUDArrowLocation = saved
    end
    -- Journey anchors its artwork to a 1x1 draggable point. Clamp the whole
    -- compass and label after changing monitor resolution or UI scale.
    local w,h = UIParent:GetWidth(), UIParent:GetHeight()
    if w <= 0 or h <= 0 then return end
    local relative = saved[3]
    local ax = relative:find("LEFT") and 0 or relative:find("RIGHT") and w or w/2
    local ay = relative:find("BOTTOM") and 0 or relative:find("TOP") and h or h/2
    local mx,my = math.min(70,w/2),math.min(80,h/2)
    saved[4] = math.max(mx,math.min(w-mx,ax+saved[4]))-ax
    saved[5] = math.max(my,math.min(h-my,ay+saved[5]))-ay
end
local function arrowEnabled()
    if original then return ns.char and ns.char.arrow ~= false end
    return shown
end
local function noop() end
local function yes() return true end
local function no() return false end
local function openLibrary() ns:OpenGuideLibrary() end

-- Journey's drawing components render either the character's carried-over
-- quests or the already evaluated, localized RestedXP steps.
function RutaXPJourneyEnvironment()
    if env then return env end
    local _, addon = RutaXPModuleContext("Journey")
    env = setmetatable({addon=addon, addonName="RutaXPJourney"}, {__index=_G})
    env.UnitPosition = compassPosition
    env.GetPlayerFacing = compassFacing
    env.I = setmetatable({}, {__index=function(t, key)
        local suffix = key:match("%.%w+$") and "" or ".blp"
        local path = "Interface\\AddOns\\RutaXP\\Modules\\Journey\\images\\" .. key .. suffix
        t[key] = path
        return path
    end})
    env.Brand = {headerLogo="JourneyLogoMed.png", headerLogoHC="JourneyLogoMed.png",
        headerIconBorderHidden=true, headerIconSize=58, headerIconOffsetX=-2}
    env.HardcoreService = {IsHardcoreEnabled=no}
    env.State = {
        IsGuideShown=function() return shown end, IsHiddenInInstances=no, IsWindowLocked=no,
        IsInvertedModeEnabled=no, IsStepIDEnabled=yes,
        GetGuideScale=function() return settings.scale or 1.2 end,
        GetWindowLocation=function()
            local point = settings.WindowLocation
            if point then point[2] = "UIParent" end
            return point
        end,
        IsScreenArrowEnabled=function() return arrowEnabled() and target ~= nil end,
        IsTomTomSupportEnabled=no, GetArrowScale=function() return settings.arrowScale or 1 end,
        GetArrowTextScale=function() return settings.arrowTextScale or 1 end,
    }
    env.GuideNavigationService = {
        IsGuideSet=function() return groupStep ~= nil end,
        GetStep=function() return groupStep end,
        IsInstanceStep=no, IsManualOverrideEnabled=no, SetManualOverrideEnabled=noop, SetSeeking=noop,
        HasNextStep=function()
            if original then return current and original.CanAdvance(1) end
            return current ~= nil and (stepIndex < stepCount or (current.next and current.next ~= ""))
        end,
        HasPreviousStep=function()
            if original then return current and original.CanAdvance(-1) end
            return current ~= nil and stepIndex > 1
        end,
        SetStepToPrevious=function() if current then engine.Advance(-1) end end,
        SetStepToNext=function() if current then engine.Advance(1) end end,
    }
    env.HeaderService = {
        GetHeaderTitles=function() return title, subtitle end,
        GetStepText=function() return current and (progressText or stepIndex .. "/" .. stepCount) end,
    }
    env.Hyperlinks = {
        OnHyperlinkClick=function(frame, link, text, button) SetItemRef(link, text, button, frame) end,
        OnHyperlinkEnter=function(frame, link)
            GameTooltip:SetOwner(frame, "ANCHOR_CURSOR")
            if not pcall(GameTooltip.SetHyperlink, GameTooltip, link) then GameTooltip:Hide() end
        end,
        OnHyperlinkLeave=GameTooltip_Hide, OnLeaveTooltipFunc=GameTooltip_Hide,
    }
    addon.GetDistanceInYards = function(x, y, tx, ty) return ((tx-x)^2 + (ty-y)^2)^0.5 end
    local spanish = GetLocale() == "esES" or GetLocale() == "esMX"
    env.FormatJourneyDistance = function(yards)
        if not spanish then return math.floor(yards+0.5) .. " yd" end
        local metres = yards * 0.9144
        if metres >= 1000 then return string.format("%.1f km", metres/1000) end
        return math.floor(metres+0.5) .. " m"
    end
    env.FormatJourneyStep = function(value)
        if original then return value end
        return (spanish and "Paso " or "Step ") .. value
    end
    return env
end

function view:Available()
    return not not (env and env.UI and env.UI.GetComponent("TaskDetailContainers") and env.addon.CreateArrow)
end

local function manualClick(button, mouseButton)
    local task = button.row
    if not task then return end
    if original then
        original.ClickTask(task, mouseButton)
    elseif status == "journal" and task.questID then
        ns.GuideCarryover.OpenQuest(task.questID)
    elseif current and task.manual then
        engine.ToggleTask(task)
    end
end

local function displayTaskTip(button)
    local row = button.row
    if not row then return end
    local text
    if original then
        text = row.details or row.text
    elseif status == "journal" and row.questID then
        text = "Ver esta misión en el diario"
    elseif current and row.manual then
        text = row.checked and "Volver a marcar como pendiente" or "Marcar esta tarea"
    else
        return
    end
    GameTooltip:SetOwner(button, "ANCHOR_RIGHT")
    GameTooltip:SetText(text)
    GameTooltip:Show()
end

local actionIcons = {
    accept="Interface\\GossipFrame\\AvailableQuestIcon", turnin="Interface\\GossipFrame\\ActiveQuestIcon",
    complete="Interface\\Icons\\INV_Misc_Note_01", collect="Interface\\Icons\\INV_Misc_Bag_08",
    fly="Interface\\Minimap\\Tracking\\FlightMaster", fp="Interface\\Minimap\\Tracking\\FlightMaster",
    train="Interface\\GossipFrame\\TrainerGossipIcon", vendor="Interface\\GossipFrame\\VendorGossipIcon",
    hs="Interface\\Icons\\INV_Misc_Rune_01", home="Interface\\Icons\\INV_Misc_Rune_01",
}

local taskRenderer = {IsDimmable=yes}
function taskRenderer:Render(task, container)
    local row = task.row
    container.task = task
    container.text:SetText(row.text)
    container.text:Show()
    container.button:Hide()
    local icon = container.icon
    local action = row.activity and row.activity.action
    if action then
        local width = container.frame:GetWidth() - 12
        local textWidth = container.text.GetUnboundedStringWidth and container.text:GetUnboundedStringWidth()
            or container.text:GetStringWidth()
        if width > 0 and textWidth <= width and not row.text:find("\n", 1, true) then
            -- Journey's own button component also participates in its row
            -- layout. Keep longer instructions in the wrapping text region.
            local button = container.button
            button.row = row
            button:SetText(row.text)
            button:SetScript("OnClick", manualClick)
            button:SetScript("OnEnter", displayTaskTip)
            button:SetScript("OnLeave", GameTooltip_Hide)
            container:SetButtonColor("FF497BB1")
            container.frame.row = nil
            container.frame:EnableMouse(false)
            container.text:Hide()
            icon:Hide()
            button:Show()
            return
        end
        container.text:SetText("|cffffdf85" .. row.text .. "|r")
    end
    if row.texture then
        icon.texture:SetTexture(row.texture)
    elseif row.checked then
        icon.texture:SetTexture("Interface\\Buttons\\UI-CheckBox-Check")
    elseif row.manual then
        icon.texture:SetTexture("Interface\\Buttons\\UI-CheckBox-Up")
    else
        icon.texture:SetTexture(actionIcons[row.element and row.element.tag] or "Interface\\GossipFrame\\GossipGossipIcon")
    end
    icon.texture:SetSize(16, 16)
    icon:SetSize(16, 16)
    icon.row = row
    icon:SetScript("OnClick", manualClick)
    icon:SetScript("OnEnter", displayTaskTip)
    icon:SetScript("OnLeave", GameTooltip_Hide)
    if original then
        icon:RegisterForClicks("LeftButtonUp", "RightButtonUp")
        container.frame.row = row
        container.frame:EnableMouse(not not (row.frame or action))
        container.frame:SetScript("OnMouseUp", manualClick)
    end
    icon:EnableMouse(not not (row.frame or action or row.manual or (status == "journal" and row.questID)))
    icon:Show()
end

local function clearArrow()
    if arrow and target then arrow:ClearTarget() end
    target = nil
end

-- Waiting for a boat or leaving combat has no directional target. Keep the
-- original short instruction at the compass without displaying a stale arrow.
local function updateCompassHint(reason)
    if not original then return end
    local hint = initialized and not target and arrowEnabled() and (reason or original.TravelHint())
    if not hint or hint == "" then
        if compassHint then compassHint:Hide() end
        return
    end
    if not compassHint then
        compassHint = UIParent:CreateFontString(nil, "OVERLAY", "GameFontNormal")
        compassHint:SetTextColor(1, .70, .33)
    end
    compassHint:ClearAllPoints()
    local hud = _G.RutaXPJourneyScreenArrow
    local saved = settings.HUDArrowLocation
    if hud then
        compassHint:SetPoint("TOP", hud, "BOTTOM", 0, 4)
    elseif saved then
        compassHint:SetPoint(saved[1], UIParent, saved[3], saved[4], saved[5])
    else
        compassHint:SetPoint("CENTER", UIParent, "CENTER", 300, 0)
    end
    compassHint:SetText(hint)
    compassHint:Show()
end

local function updateTarget()
    if not initialized or not arrowEnabled() then clearArrow(); return end
    local waypoint
    if original then waypoint = original.Waypoint
    elseif status == "journal" then waypoint = ns.GuideCarryover.Waypoint
    elseif current then waypoint = engine.Waypoint end
    if not waypoint then clearArrow(); return end
    local map, x, y, label = waypoint()
    if not finite(map) or not finite(x) or not finite(y) or
        x < 0 or x > 1 or y < 0 or y > 1 then clearArrow(); return end
    local world, point = C_Map.GetWorldPosFromMapPos(map, CreateVector2D(x, y))
    sampleOrigin()
    local px, py, _, playerWorld = compassPosition("player")
    -- World yards have independent origins on each continent. Never point
    -- across the sea by subtracting coordinates from two different worlds.
    if not point or not finite(world) or not finite(px) or not finite(py) or not finite(playerWorld) then
        clearArrow(); return "Esperando la posición en el mapa"
    end
    if playerWorld ~= world then clearArrow(); return "Destino en otro continente" end
    if not compassFacing() then clearArrow(); return "Esperando la orientación del personaje" end
    if not target or target.map ~= map or target.x ~= x or target.y ~= y or arrow.mapID ~= map then
        clearArrow()
        arrow:SetTarget(x,y,map,false,point)
        if arrow.mapID ~= map then return "Esperando la posición en el mapa" end
        target = {map=map, x=x, y=y}
    end
    arrow.screenLabel = label or title
end

local function updateArrow()
    if not initialized then return end
    local reason = updateTarget()
    updateCompassHint(reason)
    local directions = original and original.TravelText()
    if directions ~= lastDirections then
        lastDirections = directions
        refreshPending = true
    end
end

local function installScrollArea(components)
    local panel, header = components.GuideContainer.frame, components.Header.frame
    scroll = CreateFrame("ScrollFrame", nil, panel, "UIPanelScrollFrameTemplate")
    scroll:SetWidth(246)
    scroll:SetPoint("TOPLEFT", header, "BOTTOMLEFT", -20, 2)
    scroll:SetHeight(1)
    scrollChild = CreateFrame("Frame", nil, scroll)
    scrollChild:SetSize(244, 1)
    scroll:SetScrollChild(scrollChild)
    scroll:EnableMouseWheel(true)
    scroll:SetScript("OnMouseWheel", function(self, delta)
        self:SetVerticalScroll(math.max(0, math.min(self:GetVerticalScrollRange(), self:GetVerticalScroll()-delta*35)))
    end)
    -- Journey anchors the first group to its header. Anchor it inside the
    -- scroll child so long RestedXP steps stay navigable on smaller screens.
    local anchor = CreateFrame("Frame", nil, scrollChild)
    anchor:SetPoint("TOPLEFT", 20,-2)
    anchor:SetSize(220,1)
    return {GuideContainer={frame=scrollChild}, Header={frame=anchor}, TaskContainers=components.TaskContainers,
        ActionButtons={GetTaskgroupsButtonStatus=function() return {} end}}
end

local function init()
    if initialized then return true end
    if not loggedIn or not view:Available() or not (original or ns.GuideEngine) or not ns.char then return false end
    if not engine then
        engine = original or ns.GuideEngine
        engine.Subscribe(function() refreshPending = true end)
    end
    if not engine.Ready() then return false end
    ns.char.journeyDisplay = ns.char.journeyDisplay or {}
    settings = ns.char.journeyDisplay
    placeCompass()
    env.SavedVariables = settings
    shown = settings.hidden ~= true
    local ui = env.UI
    ui.CloseGuideMenu = noop
    ui.ToggleGuideMenu = openLibrary
    local groups = ui.GetComponent("TaskGroupContainers")
    local initGroups = groups.Init
    groups.Init = function(components) initGroups(installScrollArea(components)) end
    ui.Init()
    local panel, header = ui.GetComponent("GuideContainer").frame, ui.GetComponent("Header").frame
    local picker = CreateFrame("Button", nil, header)
    picker:SetPoint("TOPLEFT", header.Icon, "TOPLEFT")
    picker:SetPoint("BOTTOMRIGHT", header, "BOTTOMRIGHT", -45, 0)
    picker:RegisterForDrag("LeftButton")
    picker:SetScript("OnMouseDown", function(self) self.dragged = false end)
    picker:SetScript("OnDragStart", function(self)
        self.dragged = true
        panel:StartMoving()
    end)
    picker:SetScript("OnDragStop", function()
        panel:StopMovingOrSizing()
        local anchor, _, relative, x, y = panel:GetPoint()
        settings.WindowLocation = {anchor, "UIParent", relative, x, y}
    end)
    picker:SetScript("OnClick", function(self) if not self.dragged then openLibrary() end end)
    picker:SetScript("OnEnter", function(f) GameTooltip:SetOwner(f,"ANCHOR_TOP"); GameTooltip:SetText("Elegir guía"); GameTooltip:Show() end)
    picker:SetScript("OnLeave", GameTooltip_Hide)
    arrow = env.addon.CreateArrow(0,1,0)
    initialized = true
    engine.PresentWithJourney(true)
    return true
end

local function prepareStep(rows)
    local step = {}
    local previous, group
    for _, row in ipairs(rows) do
        if type(row.text) == "string" and row.text:match("%S") then
            if not group or previous ~= row.step then
                group = {root=step,conditionPassed=true}
                step[#step+1] = group
                previous = row.step
            end
            group[#group+1] = {row=row,parent=group,taskType=taskRenderer,conditionPassed=true,completedPassed=row.checked}
        end
    end
    return step
end

function view:Refresh()
    refreshPending = false
    if not init() then return end
    if original then shown = original.TrackerShown() end
    local oldGuide, oldIndex, oldStatus = current, stepIndex, status
    local message
    if ns.GuideResume then status, message = ns.GuideResume.Status() end
    local waiting = status == "pending" or status == "unavailable"
    if status == "journal" or waiting then
        current, stepIndex = nil, nil
    else
        current, stepIndex = engine.Current()
    end
    stepIndex = tonumber(stepIndex) or 1
    stepCount = current and #current.steps or 0
    local rows
    if status == "journal" then
        title, subtitle = "Misiones en curso", "Continuar con tu diario"
        rows = ns.GuideCarryover.Rows()
    elseif not current then
        title, subtitle = "RutaXP", original and "Guías de leveo" or "Guías de RestedXP"
        rows = {{text=(waiting and message) or "Pulsa el nombre de la guía para elegir una."}}
        if original then original.AddActivities(rows) end
    elseif original then
        title, subtitle, progressText = original.Headings()
        rows = original.Tasks()
    else
        title = current.displayname or current.title or current.name
        subtitle = current.groupdisplayname or current.group
        rows = engine.Tasks()
    end
    groupStep = prepareStep(rows)
    env.UI.MarkDirty()
    env.UI.Update(0)
    if status == "journal" then
        env.UI.GetComponent("HeaderNextButton").frame:Hide()
        env.UI.GetComponent("HeaderBackButton").frame:Hide()
    end
    if shown then
        local height, groups = 0, env.UI.GetComponent("TaskGroupContainers")
        for i=1,#groupStep do
            local frame = groups.Get(i).frame
            if frame:IsShown() then height = height + frame:GetHeight() end
        end
        scrollChild:SetHeight(math.max(1,height))
        local limit = math.max(80, UIParent:GetHeight() * .42 / env.State.GetGuideScale())
        scroll:SetHeight(math.max(1, math.min(height,limit)))
        if scroll.ScrollBar then scroll.ScrollBar:SetShown(height > limit) end
        if current ~= oldGuide or stepIndex ~= oldIndex or status ~= oldStatus then scroll:SetVerticalScroll(0) end
    end
    updateArrow()
end

function view:Show()
    if not init() then return false end
    if original then original.SetTracker(true) end
    settings.hidden, shown = false, true
    self:Refresh()
    return true
end

function view:Hide()
    if not init() then return false end
    if original then original.SetTracker(false) end
    settings.hidden, shown = true, false
    self:Refresh()
    return true
end

function view:IsShown() return shown == true end

local driver = CreateFrame("Frame")
driver:RegisterEvent("PLAYER_LOGIN")
driver:RegisterEvent("PLAYER_ENTERING_WORLD")
driver:RegisterEvent("PLAYER_REGEN_ENABLED")
driver:RegisterEvent("ZONE_CHANGED_NEW_AREA")
driver:RegisterEvent("GROUP_ROSTER_UPDATE")
driver:SetScript("OnEvent", function(_, event)
    if event == "GROUP_ROSTER_UPDATE" and status ~= "journal" then return end
    if event == "PLAYER_LOGIN" or event == "PLAYER_ENTERING_WORLD" then loggedIn = true end
    if event == "ZONE_CHANGED_NEW_AREA" then clearArrow() end
    refreshPending = true
end)
local elapsed = 0
driver:SetScript("OnUpdate", function(_, dt)
    elapsed = elapsed + dt
    if elapsed < .2 then return end
    elapsed = 0
    if refreshPending and view:Available() then view:Refresh()
    elseif original or target or (compassHint and compassHint:IsShown()) or
        (arrowEnabled() and (current or status == "journal")) then updateArrow() end
end)
