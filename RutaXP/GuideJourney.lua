local _, ns = ...
local view = {}
ns.GuideJourney = view

local env, settings, engine, arrow, target, current, groupStep
local loggedIn, initialized, shown, refreshPending
local title, subtitle, status, stepIndex, stepCount, progressText
local scroll, scrollChild, styledHUD, trackerHint
local original = ns.OriginalGuidePresentation
local originWorld, originNorth, originWest, lastDirections
local function finite(n)
    if issecretvalue and issecretvalue(n) then return false end
    return type(n) == "number" and n == n and math.abs(n) < math.huge
end

local compassKey, finalTarget, distanceText, nearYards, lastRotation, boundTexture
local lastWorldBearing, steeringFrom, steeringStarted
local fullTurn, minimumTurn = 2 * math.pi, math.rad(2.8)
local steeringDuration = .18
-- Journey uses a single distance for its arrival sprite, distance label and
-- minimap. Its minimap radius is much larger than the 1.5-yard arrival radius.
local passingNode = 1.500001

local function compassFacing()
    local angle = GetPlayerFacing and GetPlayerFacing()
    if finite(angle) then return angle end
end

local function shortestTurn(from, to)
    return (to - from + math.pi) % fullTurn - math.pi
end

local function resetSteering()
    lastRotation, lastWorldBearing, steeringFrom, steeringStarted = nil, nil, nil, nil
end

function view:SetCompassTarget(key, isFinal, totalYards, steeringChanged, segmentYards)
    if key ~= compassKey or (isFinal ~= finalTarget and not steeringChanged) then
        resetSteering()
    elseif steeringChanged and lastWorldBearing then
        steeringFrom, steeringStarted = lastWorldBearing, GetTime()
    end
    compassKey, finalTarget = key, isFinal
    distanceText = finite(totalYards) and totalYards >= 0 and ns.FormatArrowDistances(segmentYards, totalYards) or nil
    nearYards = nil
end

local function bindCompassRotation()
    local hud = _G.RutaXPJourneyScreenArrow
    local texture = hud and hud.arrowTexture
    if not texture or texture == boundTexture then return end
    boundTexture = texture
    resetSteering()
    local draw = texture.SetRotation
    texture.SetRotation = function(self, angle)
        if not finite(angle) then return end
        local facing = compassFacing()
        if steeringFrom and facing then
            local progress = math.max(0, (GetTime() - steeringStarted) / steeringDuration)
            if progress < 1 then
                -- Ease the change in the path bearing. The current player
                -- facing still reaches the arrow on every draw.
                angle = angle + shortestTurn(angle + facing, steeringFrom) * (1 - progress)
            else
                steeringFrom, steeringStarted = nil, nil
            end
        end
        if lastRotation and math.abs(shortestTurn(lastRotation, angle)) < minimumTurn then return end
        lastRotation = angle
        lastWorldBearing = facing and angle + facing
        draw(self, angle)
    end
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
        IsTomTomSupportEnabled=no,
        GetArrowScale=function()
            -- Journey has created its HUD by the time it reads the scale for the first draw.
            bindCompassRotation()
            return (settings.arrowScale or 1) * (ns.ArrowStyles and ns.ArrowStyles:GetScale() or 1)
        end,
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
    addon.GetDistanceInYards = function(x, y, tx, ty)
        local yards = ((tx-x)^2 + (ty-y)^2)^0.5
        if finalTarget == false and yards <= 1.5 then
            nearYards = yards
            return passingNode
        end
        nearYards = nil
        return yards
    end
    local spanish = GetLocale() == "esES" or GetLocale() == "esMX"
    env.FormatJourneyDistance = function(yards)
        -- Journey clears the numbers on a missing position. Restore them even
        -- when the first good sample rounds to the same number as the last.
        local hud = _G.RutaXPJourneyScreenArrow
        if hud and not hud.container:IsShown() then hud.lastDistText = nil end
        return distanceText or ns.FormatArrowDistances(nil, (yards == passingNode and nearYards) or yards)
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

local colors = {
    accept="ffffff00", turnin="ffffa500", objective="ff0084eb", item="ffe36ee4",
    friendly="ff9dff9d", hostile="ffff6363", neutral="ffffd100", unknown="ffe36ee4", place="ffffd100",
}
local journeyIcons = {
    accept={"QuestNormal", .85}, turnin={"QuestTurnin", .85},
    complete={"worldquest-icon-pvp-ffa", .75}, kill={"VignetteKill", 1.2},
    collect={"VignetteLoot", 1.2}, getfp={"FlightMaster", .9}, fly={"FlightMaster", .9},
    done={"Capacitance-General-WorkOrderCheckmark", 1.2}, blocked={"services-icon-warning", 1},
}
local contact = {accept=true,turnin=true,talk=true,train=true,vendor=true,fly=true,getfp=true,sethome=true}
local function coloredInstruction(row)
    local action = row.action
    if not action or not row.text or row.text:find("|", 1, true) then return row.text end
    local npcColor = colors[row.npcReaction] or (action == "kill" and colors.hostile)
        or (contact[action] and colors.friendly) or colors.unknown
    local targets = {
        {row.questTitle, colors[action] or colors.objective}, {row.npcName, npcColor},
        {row.itemName, colors.item}, {row.objectName, colors.item}, {row.placeName, colors.place},
        {row.targetName, colors[row.targetReaction] or (action == "kill" and colors.hostile)
            or (contact[action] and npcColor) or colors.item},
    }
    local text, parts, pos = row.text, {}, 1
    while pos <= #text do
        local first, last, color
        for _, token in ipairs(targets) do
            local name = token[1]
            if type(name) == "string" and name ~= "" then
                local at, finish = text:find(name, pos, true)
                -- Keep short names out of longer names (including UTF-8 letters).
                while at and (text:sub(at-1, at-1):match("[%w_\128-\255]") or text:sub(finish+1, finish+1):match("[%w_\128-\255]")) do
                    at, finish = text:find(name, finish+1, true)
                end
                if at and (not first or at < first or (at == first and finish > last)) then
                    first, last, color = at, finish, token[2]
                end
            end
        end
        if not first then parts[#parts+1] = text:sub(pos); break end
        parts[#parts+1] = text:sub(pos, first-1) .. "|c" .. color .. text:sub(first, last) .. "|r"
        pos = last+1
    end
    return table.concat(parts)
end

local function setTaskIcon(icon, row)
    local texture = icon.texture
    texture:SetVertexColor(1, 1, 1)
    texture:SetDesaturated(false)
    texture:SetTexCoord(0, 1, 0, 1)
    local style = journeyIcons[row.status] or journeyIcons[row.action]
    local atlas = style and C_Texture and C_Texture.GetAtlasInfo and C_Texture.GetAtlasInfo(style[1])
    if atlas and atlas.width and atlas.height and texture.SetAtlas then
        texture:SetAtlas(style[1], false)
        local scale = (14*style[2]-2)/math.max(atlas.width, atlas.height)
        texture:SetSize(atlas.width*scale, atlas.height*scale)
    else
        texture:SetTexture(row.texture or (row.checked and "Interface\\Buttons\\UI-CheckBox-Check")
            or (row.manual and "Interface\\Buttons\\UI-CheckBox-Up")
            or actionIcons[row.element and row.element.tag] or "Interface\\GossipFrame\\GossipGossipIcon")
        texture:SetSize(16, 16)
        if row.action and row.texture and row.iconColor then texture:SetVertexColor(unpack(row.iconColor)) end
    end
    if row.status == "skip" then texture:SetDesaturated(true) end
    icon:SetSize(16, 16)
end

local taskRenderer = {IsDimmable=yes}
function taskRenderer:Render(task, container)
    local row = task.row
    container.task = task
    container.text:SetText(coloredInstruction(row))
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
    setTaskIcon(icon, row)
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
    view:SetCompassTarget(nil, nil, nil)
    if arrow and target then arrow:ClearTarget() end
    target = nil
end

local turnPromptYards = 70

local function walkingInstruction(sample)
    local locale = GetLocale()
    local spanish = locale == "esES" or locale == "esMX"
    local turn = sample.walkingTurn
    local yards = sample.walkingTurnDistance
    if finite(yards) and (turn == "left" or turn == "right") then
        local instruction
        if spanish then
            local direction = turn == "left" and "a la izquierda" or "a la derecha"
            instruction = (yards <= turnPromptYards and "Gira " or "Sigue el camino · próximo giro ") .. direction
        else
            instruction = (yards <= turnPromptYards and "Turn " or "Follow the path · next turn ") .. turn
        end
        return instruction
    end
end

local function updateTarget(body, deathHint)
    if not initialized or not arrowEnabled() then clearArrow(); return end
    local map, x, y, label, walking, sample
    if deathHint then
        if not body then clearArrow(); return deathHint end
        map, x, y, label = body.mapID, body.x, body.y, deathHint
    else
        local waypoint
        if original then waypoint = original.Waypoint
        elseif status == "journal" then waypoint = ns.GuideCarryover.Waypoint
        elseif current then waypoint = engine.Waypoint end
        if not waypoint then clearArrow(); return end
        map, x, y, label, walking, sample = waypoint()
    end
    if not finite(map) or not finite(x) or not finite(y) or
        x < 0 or x > 1 or y < 0 or y > 1 then clearArrow(); return end
    if not original and not deathHint and not sample and ns.Walking and ns.Walking:IsEnabled() then
        sample = ns.Walking:Resolve({mapID=map, x=x, y=y, label=label, guideID=title, stepIndex=stepIndex,
            targetKey=table.concat({"journey", map, label or ""}, ":")})
        if not sample then clearArrow(); return end
        map, x, y, walking = sample.mapID, sample.x, sample.y, sample.walkingWorld
    end
    if sample and sample.navigationBlocked then
        clearArrow()
        return sample.navigationHint or sample.navigationNotice
    end
    local world, point
    if walking and finite(walking.continent) and finite(walking.north) and finite(walking.west) then
        -- Steering and UnitPosition use terrain yards. Reprojecting a short
        -- turn through the map can place it behind a player who has passed it.
        world, point = walking.continent, {x=walking.north, y=walking.west}
    else
        world, point = C_Map.GetWorldPosFromMapPos(map, CreateVector2D(x, y))
    end
    sampleOrigin()
    local px, py, _, playerWorld = compassPosition("player")
    -- World yards have independent origins on each continent. Never point
    -- across the sea by subtracting coordinates from two different worlds.
    if not point or not finite(world) or not finite(px) or not finite(py) or not finite(playerWorld) then
        clearArrow(); return "Esperando la posición en el mapa"
    end
    if playerWorld ~= world then clearArrow(); return "Destino en otro continente" end
    if not compassFacing() then clearArrow(); return "Esperando la orientación del personaje" end
    local segmentYards, totalYards
    if sample and sample.walking then
        totalYards = sample.walkingDistance
        if not sample.walkingFinal then segmentYards = sample.walkingTurnDistance or sample.walkingSegmentDistance end
    end
    local intermediate = sample and (sample.walking and not sample.walkingFinal
        or sample.intermediate and sample.pointIndex and sample.pointCount and sample.pointIndex < sample.pointCount)
    local key = sample and sample.walkingRouteKey
        or ((deathHint and "corpse" or "guide") .. "/" .. map .. "/" .. x .. "/" .. y)
    local changed = not target or arrow.mapID ~= map or arrow.worldTargetX ~= point.x or arrow.worldTargetY ~= point.y
    view:SetCompassTarget(key, not intermediate, totalYards, changed and sample and sample.walking, segmentYards)
    if changed then
        -- SetTarget replaces the current destination. ClearTarget also hides
        -- the HUD, which made it blink at every turn even on the same road.
        arrow:SetTarget(x,y,map,not not (intermediate or walking and target),point)
        if arrow.mapID ~= map then clearArrow(); return "Esperando la posición en el mapa" end
        target = true
    end
    arrow.screenLabel = ""
    if deathHint then return deathHint end
    if sample then
        local maneuver = sample.walking and walkingInstruction(sample)
        if maneuver then return maneuver end
        if sample.navigationNotice then return sample.navigationNotice end
        if label and label ~= "" and not label:match("^Tramo %d+/%d+$") then return label end
    end
end

-- Journey creates this frame on the first usable target. Bind it once, so
-- changing the appearance never needs to clear or recalculate that target.
local function bindCompassAppearance()
    local hud = _G.RutaXPJourneyScreenArrow
    local styles = ns.ArrowStyles
    if not styles or not hud or hud == styledHUD then return end
    styledHUD = hud
    -- Journey's second row normally sits below a destination name. Put the
    -- distance and its matching shadows directly under the pointer.
    hud.distLabel:ClearAllPoints()
    hud.distLabel:SetPoint("TOP", hud.label, "TOP", 0, 0)
    for index, shadow in ipairs(hud.distShadowContainer.labels) do
        shadow:ClearAllPoints()
        shadow:SetPoint("TOP", hud.shadowContainer.labels[index], "TOP", 0, 0)
    end
    styles:Attach(hud, function()
        hud.arrowTexture:SetTexture(styles:GetTexture())
        hud:SetScale(.6 * env.State.GetArrowScale())
        local visible = styles:ShowsText()
        for _, region in ipairs({hud.label, hud.distLabel, hud.shadowContainer, hud.distShadowContainer}) do
            if visible then region:Show() else region:Hide() end
        end
    end)
end

local function updateArrow(renderingTracker)
    if not initialized then return end
    bindCompassAppearance()
    local body, deathHint
    if ns.GetDeathNavigation and arrowEnabled() then body, deathHint = ns:GetDeathNavigation() end
    local reason = updateTarget(body, deathHint)
    local directions = original and not deathHint and original.TravelText() or nil
    local hint = reason or (not target and arrowEnabled() and original and original.TravelHint())
    if not hint or hint == "" or (directions and directions:find(hint, 1, true)) then hint = nil end
    if directions ~= lastDirections or hint ~= trackerHint then
        lastDirections, trackerHint = directions, hint
        if not renderingTracker then refreshPending = true end
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
    -- Journey updates the HUD from a separate driver. Its minimap arrow and
    -- nearby ping are siblings that it shows again whenever the target moves.
    local minimapLayers = CreateFrame("Frame", nil, UIParent)
    minimapLayers:Hide()
    arrow = env.addon.CreateArrow(0,1,0)
    arrow:SetParent(minimapLayers)
    arrow.ping:SetParent(minimapLayers)
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
            group[#group+1] = {row=row,parent=group,taskType=taskRenderer,conditionPassed=true,
                completedPassed=row.checked or row.status == "done"}
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
    updateArrow(true)
    if trackerHint then
        local first = rows[1]
        local index = 1
        while rows[index] and rows[index].step == first.step do index = index + 1 end
        table.insert(rows, index, {text=trackerHint, step=first and first.step})
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
driver:RegisterEvent("PLAYER_DEAD")
driver:RegisterEvent("PLAYER_ALIVE")
driver:RegisterEvent("PLAYER_UNGHOST")
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
    elseif original or target or trackerHint or
        (arrowEnabled() and (current or status == "journal" or (ns.IsRecoveringCorpse and ns:IsRecoveringCorpse()))) then updateArrow() end
end)
