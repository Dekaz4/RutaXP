local _, ns = ...

-- The original tracker has already resolved travel, quest prerequisites,
-- manual omissions and the active duo view. Present that same decision.
local source = {}
ns.OriginalGuidePresentation = source
local parkedParent, point

function source.Ready()
    return ns.char and ns.tracker and ns.window
end

function source.Current()
    local guide, _, state
    if ns.GetDisplayedCurrent and not ns:GetGuideTravel() then
        guide, _, state = ns:GetDisplayedCurrent()
    else
        guide, _, state = ns:GetCurrent()
    end
    if guide then return guide, state.cursor end
end

function source.Headings()
    local progress = ns.trackerProgress:GetText()
    local planner = ns.DungeonPlanner
    if planner and planner:IsDetouring() then
        local title, subtitle = planner:Heading()
        if title then return title, subtitle, progress and ("Ruta · " .. progress) end
    end
    return ns.trackerTitle:GetText(), ns.trackerStep:GetText(), progress
end

function source.TrackerShown()
    return ns.char.tracker and not ns.window:IsShown()
end

function source.SetTracker(enabled)
    ns.char.tracker = enabled
    if enabled then ns.window:Hide() end
    ns:RefreshUI()
end

function source.CanAdvance(delta)
    local button = delta == 1 and ns.trackerNext or ns.trackerPrevious
    return button and button.isEnabled
end

function source.Advance(delta)
    local button = delta == 1 and ns.trackerNext or ns.trackerPrevious
    if button and button.isEnabled then button:GetScript("OnClick")(button, "LeftButton") end
end

function source.AddActivities(rows)
    local planner = ns.DungeonPlanner
    if not planner then return end
    for _, entry in ipairs(planner:Rows()) do
        rows[#rows+1] = {text=entry.text, step="activities", texture=entry.texture,
            activity=entry, details=entry.details}
    end
end

function source.Tasks()
    local result, upcomingRows = {}, {}
    local detour = ns.DungeonPlanner and ns.DungeonPlanner:IsDetouring()
    if detour then source.AddActivities(result) end
    local count = #result
    for i, frame in ipairs(ns.trackerRows) do
        if frame:IsShown() then
            local text = frame.goalTitle
            if frame.goalSub and frame.goalSub ~= "" then text = text .. "\n" .. frame.goalSub end
            local upcoming = i > ns.trackerCurrentCount
            if upcoming and i == ns.trackerCurrentCount + 1 then
                text = ns.trackerUpcomingLabel:GetText() .. "\n" .. text
            end
            local group = upcoming and upcomingRows or result
            group[#group+1] = {text=text, step=upcoming and 2 or 1, texture=frame.icon:GetTexture(),
                frame=not frame.preview and frame or nil, details=frame.goalDetails,
                goalTitle=frame.goalTitle, goalIndex=frame.goalIndex, stepKey=ns.lastStepKey}
        end
    end
    if #result == count and ns.trackerText:IsShown() then result[#result+1] = {text=ns.trackerText:GetText()} end
    if not detour then source.AddActivities(result) end
    for _, row in ipairs(upcomingRows) do result[#result+1] = row end
    return result
end

function source.ClickTask(row, button)
    if row.activity then
        if row.activity.action and button == "LeftButton" then ns.DungeonPlanner:Click(row.activity) end
        return
    end
    local frame = row.frame
    if frame and frame:IsShown() and row.stepKey == ns.lastStepKey and
        frame.goalIndex == row.goalIndex and frame.goalTitle == row.goalTitle then
        frame:GetScript("OnClick")(frame, button)
    end
end

function source.Waypoint()
    if not ns.char.arrow then return end
    local planner = ns.DungeonPlanner
    if planner and planner:IsDetouring() then return planner:Waypoint() end
    local nav = ns.navigationFrame
    if not point or not nav or not nav:IsShown() or not nav.arrow:IsShown() then return end
    return point.mapID, point.x, point.y, nav.hint:GetText() or ""
end

function source.TravelHint()
    local planner = ns.DungeonPlanner
    if planner and planner:IsDetouring() then return planner:Hint() end
    local nav = ns.navigationFrame
    if nav and nav:IsShown() and not nav.arrow:IsShown() then return nav.hint:GetText() end
end

-- Read the sampled turn from the navigation engine. Asking for a second
-- resolution here would advance its walking planner twice per sample.
local resolve = ns.GetArrowWaypoint
function ns:GetArrowWaypoint(...)
    point = resolve(self, ...)
    return point
end

local function park(frame)
    if frame and frame:GetParent() ~= parkedParent then frame:SetParent(parkedParent) end
end

function source.PresentWithJourney()
    if parkedParent then return end
    parkedParent = CreateFrame("Frame", nil, UIParent)
    parkedParent:Hide()
    park(ns.tracker)
    park(ns.navigationFrame)
    -- The updater is a separate frame. Keep it running even while the
    -- original compass and tracker are parented under the hidden frame.
    hooksecurefunc(ns, "CreateNavigation", function() park(ns.navigationFrame) end)
end

function source.Subscribe(refresh)
    hooksecurefunc(ns, "RefreshUI", refresh)
end
