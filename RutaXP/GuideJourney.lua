local _, ns = ...
local view = {}
ns.GuideJourney = view

local env, settings, engine, arrow, target, current, groupStep
local loggedIn, initialized, shown, refreshPending
local title, subtitle, status, stepIndex, stepCount
local scroll, scrollChild
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
        IsScreenArrowEnabled=function() return shown and target ~= nil end,
        IsTomTomSupportEnabled=no, GetArrowScale=function() return settings.arrowScale or 1 end,
        GetArrowTextScale=function() return settings.arrowTextScale or 1 end,
    }
    env.GuideNavigationService = {
        IsGuideSet=function() return groupStep ~= nil end,
        GetStep=function() return groupStep end,
        IsInstanceStep=no, IsManualOverrideEnabled=no, SetManualOverrideEnabled=noop, SetSeeking=noop,
        HasNextStep=function() return current ~= nil and
            (stepIndex < stepCount or (current.next and current.next ~= "")) end,
        HasPreviousStep=function() return current ~= nil and stepIndex > 1 end,
        SetStepToPrevious=function() if current then engine.Advance(-1) end end,
        SetStepToNext=function() if current then engine.Advance(1) end end,
    }
    env.HeaderService = {
        GetHeaderTitles=function() return title, subtitle end,
        GetStepText=function() return current and (stepIndex .. "/" .. stepCount) end,
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
    env.FormatJourneyStep = function(value) return (spanish and "Paso " or "Step ") .. value end
    return env
end

function view:Available()
    return not not (env and env.UI and env.UI.GetComponent("TaskDetailContainers") and env.addon.CreateArrow)
end

local function manualClick(button)
    local task = button.row
    if not task then return end
    if status == "journal" and task.questID then
        ns.GuideCarryover.OpenQuest(task.questID)
    elseif current and task.manual then
        engine.ToggleTask(task)
    end
end

local function displayTaskTip(button)
    local row = button.row
    if not row then return end
    local text
    if status == "journal" and row.questID then
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
    if row.checked then
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
    icon:EnableMouse(not not (row.manual or (status == "journal" and row.questID)))
    icon:Show()
end

local function clearArrow()
    if arrow and target then arrow:ClearTarget() end
    target = nil
end

local function updateArrow()
    if not initialized or not shown then clearArrow(); return end
    local waypoint
    if status == "journal" then waypoint = ns.GuideCarryover.Waypoint
    elseif current then waypoint = engine.Waypoint end
    if not waypoint then clearArrow(); return end
    local map, x, y, label = waypoint()
    if type(map) ~= "number" or type(x) ~= "number" or type(y) ~= "number" or
        x < 0 or x > 1 or y < 0 or y > 1 then clearArrow(); return end
    local world, point = C_Map.GetWorldPosFromMapPos(map, {x=x, y=y})
    local _, _, _, playerWorld = UnitPosition("player")
    -- World yards have independent origins on each continent. Never point
    -- across the sea by subtracting coordinates from two different worlds.
    if not point or not world or playerWorld ~= world then clearArrow(); return end
    if not target or target.map ~= map or target.x ~= x or target.y ~= y then
        clearArrow()
        arrow:SetTarget(x,y,map,false)
        target = {map=map, x=x, y=y}
    end
    arrow.screenLabel = label or title
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
    if not loggedIn or not view:Available() or not ns.GuideEngine or not ns.char then return false end
    if not engine then
        engine = ns.GuideEngine
        engine.Subscribe(function() refreshPending = true end)
    end
    if not engine.Ready() then return false end
    ns.char.journeyDisplay = ns.char.journeyDisplay or {}
    settings = ns.char.journeyDisplay
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
        title, subtitle = "RutaXP", "Guías de RestedXP"
        rows = {{text=(waiting and message) or "Pulsa el nombre de la guía para elegir una."}}
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
    settings.hidden, shown = false, true
    self:Refresh()
    return true
end

function view:Hide()
    if not init() then return false end
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
    elseif target or (shown and (current or status == "journal")) then updateArrow() end
end)
