local _, ns = ...

-- The original tracker has already resolved travel, quest prerequisites,
-- manual omissions and the active duo view. Present that same decision.
local source = {}
ns.OriginalGuidePresentation = source
local parkedParent, point, sampledActivity

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

-- These values belong to the same RefreshUI sample as the native text and
-- click target. Journey can style them without querying the quest log again.
local function public(value,kind)
    if issecretvalue and issecretvalue(value) then return end
    if type(value)==kind then return value end
end

local function describeRow(row,item,action)
    local goal=item.goal or {}
    row.action,row.status,row.isCurrent=action,item.status,item.isCurrent
    row.questID=item.questID or goal.quest or goal.questID
    row.questTitle=item.questTitle or (row.questID and goal.title)
    row.targetName,row.itemName=item.targetName or goal.target,item.itemName or goal.itemName
    row.npcName,row.objectName=item.npcName,item.objectName
    if not item.contactResolved then
        row.npcName=row.npcName or goal.npcName
        row.objectName=row.objectName or goal.objName or goal.objectName
    end
    row.placeName=item.placeName or goal.location
    row.npcReaction,row.targetReaction=goal.npcReaction,goal.targetReaction
    row.stepIndex,row.workStep,row.turninStep=item.stepIndex,item.workStep,item.turninStep
    row.preview,row.questPlan=item.preview,item.questPlan
    local raw=public(item.questObjectives,"table")
    if raw then
        for index,obj in ipairs(raw) do
            if (not item.objectiveIndex or index==item.objectiveIndex) and public(obj,"table") then
                local text,finished=public(obj.text,"string"),public(obj.finished,"boolean")
                local have,total=public(obj.numFulfilled,"number"),public(obj.numRequired,"number")
                if text or have or total or finished~=nil then
                    row.objectives=row.objectives or {}
                    row.objectives[#row.objectives+1]={index=index,text=text,have=have,total=total,finished=finished}
                end
            end
        end
    end
    return row
end

function source.AddActivities(rows)
    local planner = ns.DungeonPlanner
    if not planner then return end
    for _, entry in ipairs(planner:Rows()) do
        rows[#rows+1] = describeRow({text=entry.text, step="activities", texture=entry.texture,
            activity=entry, details=entry.details},entry,entry.questAction)
    end
end

function source.Tasks()
    local result, upcomingRows = {}, {}
    local detour = ns.DungeonPlanner and ns.DungeonPlanner:IsDetouring()
    local directions = source.TravelText()
    if directions then result[1] = {text=directions, step=detour and "activities" or 1} end
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
            local item=frame.presentationItem or {}
            local row=describeRow({text=text, step=upcoming and 2 or 1, texture=frame.icon:GetTexture(),
                frame=not frame.preview and frame or nil, details=frame.goalDetails,
                goalTitle=frame.goalTitle, goalSub=frame.goalSub, goalIndex=frame.goalIndex, stepKey=ns.lastStepKey},
                item,item.action)
            row.preview,row.questPlan=frame.preview,frame.questPlan
            if frame.icon.GetVertexColor then
                local r,g,b,a=frame.icon:GetVertexColor()
                if type(r)=="number" and type(g)=="number" and type(b)=="number" then row.iconColor={r,g,b,a} end
            end
            group[#group+1] = row
        end
    end
    if #result == count and ns.trackerText:IsShown() then result[#result+1] = {text=ns.trackerText:GetText()} end
    if not detour then source.AddActivities(result) end
    for _, row in ipairs(upcomingRows) do result[#result+1] = row end
    return result
end

local function currentActivitySample(planner)
    return sampledActivity and planner:RouteKey() == sampledActivity and
        (not point or point.activityDestination and point.activityKey == sampledActivity)
end

local function travelView()
    local planner = ns.DungeonPlanner
    if planner and planner:IsDetouring() then
        if currentActivitySample(planner) and ns.GetDestinationTravelView then return ns:GetDestinationTravelView() end
        if planner.TravelView then return planner:TravelView() end
    elseif ns.GetDestinationTravelView then return ns:GetDestinationTravelView() end
end

local function hasText(text) return type(text) == "string" and text ~= "" and text end

function source.TravelText()
    local leg = travelView()
    local planner = ns.DungeonPlanner
    local activity = planner and planner:IsDetouring()
    local notice
    if point and point.navigationBlocked and (not leg or leg.point) and
        ((not activity and not point.activityDestination) or (activity and currentActivitySample(planner))) then
        notice = hasText(point.navigationNotice) or hasText(point.navigationHint)
    end
    if leg then
        local text = hasText(leg.text) or hasText(leg.title)
        if hasText(leg.title) and text ~= leg.title then text = leg.title .. "\n" .. text end
        if text and notice and notice ~= text then return text .. "\n" .. notice end
        return text or notice
    end
    return notice
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
    local activity = planner and planner:IsDetouring()
    if activity and not currentActivitySample(planner) then
        local map, x, y, title, leg = planner:Waypoint()
        if leg and not leg.point then return end
        return map, x, y, leg and (hasText(leg.shortText) or leg.title) or title
    end
    local leg = travelView()
    if leg and not leg.point then return end
    local nav = ns.navigationFrame
    if not point or (point.activityDestination and not activity) then return end
    if point.navigationBlocked then
        if point.navigationBearing then
            return point.mapID, point.x, point.y, hasText(point.navigationBearingText) or "Rumbo orientativo"
        end
        return
    end
    local hint = leg and (hasText(leg.shortText) or leg.title) or (nav and hasText(nav.hint:GetText()))
    return point.mapID, point.x, point.y, hint or (activity and planner:Hint()) or hasText(point.navigationNotice) or "",
        point.walking and point.walkingWorld or nil
end

function source.TravelHint()
    local leg = travelView()
    local planner = ns.DungeonPlanner
    local activity = planner and planner:IsDetouring()
    if point and point.navigationBlocked and (not leg or leg.point) and
        ((not activity and not point.activityDestination) or (activity and currentActivitySample(planner))) then
        return hasText(point.navigationHint) or hasText(point.navigationNotice)
    end
    if leg then return hasText(leg.shortText) or hasText(leg.title) or hasText(leg.text) end
    if activity then return planner:Hint() end
    local nav = ns.navigationFrame
    if nav and nav:IsShown() and not nav.arrow:IsShown() then
        return hasText(nav.hint:GetText()) or hasText(nav.navigationReason) or hasText(nav.statusText)
    end
end

-- Read the sampled turn from the navigation engine. Asking for a second
-- resolution here would advance its walking planner twice per sample.
local resolve = ns.GetArrowWaypoint
function ns:GetArrowWaypoint(...)
    local resolved = resolve(self, ...)
    point = resolved and resolved.source ~= "corpse" and resolved or nil
    local planner = self.DungeonPlanner
    sampledActivity = planner and planner.RouteKey and planner:RouteKey()
    return resolved
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
