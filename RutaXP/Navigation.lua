local _, ns = ...

-- Forever uses the Mainline C_Map API. World X points north and world Y
-- points west; GetPlayerFacing is in radians, increasing towards the west.
-- Guide targets use C_Map's frame. Terrain turns carry their native world
-- point and use UnitPosition only when its instance matches that continent.
local METRES_PER_YARD = 0.9144
local SAMPLE_INTERVAL = 0.1 -- Target sampling; the faceted arrow still rotates every frame.
local TWO_PI = 2 * math.pi
local DIAL = 56
local CLOSE_RANGE = 220
local CONTACT_RANGE = 40 -- yards
local NAV_MEDIA = "Interface\\AddOns\\RutaXP\\Media\\Nav\\"

local function number(value)
    if issecretvalue and issecretvalue(value) then return false end
    return type(value) == "number" and value == value and math.abs(value) < math.huge
end

local function safe(api, ...)
    if type(api) ~= "function" then return nil end
    local ok, first, second, third, fourth = pcall(api, ...)
    if ok then return first, second, third, fourth end
end

local function validPoint(point)
    return type(point) == "table" and number(point.mapID) and point.mapID > 0
        and number(point.x) and point.x >= 0 and point.x <= 1
        and number(point.y) and point.y >= 0 and point.y <= 1
end

local function restrictedMap(mapID)
    local info = safe(C_Map and C_Map.GetMapInfo, mapID)
    local types = Enum and Enum.UIMapType
    return info and types and (info.mapType == types.Dungeon or info.mapType == types.Micro)
end

local function questPoint(questID, action)
    -- A live quest waypoint is appropriate for doing the quest. Acceptance
    -- steps use their authored/learned NPC location. A COMPLETED quest's
    -- waypoint is the game's own turn-in location, so turn-ins use it too.
    local wanted = action == "complete" or action == "objective"
        or (action == "turnin" and safe(C_QuestLog and C_QuestLog.IsComplete, questID) == true)
    if questID and wanted then
        local mapID, x, y = safe(C_QuestLog and C_QuestLog.GetNextWaypoint, questID)
        local point = { mapID = mapID, x = x, y = y, dynamic = true, source = "game" }
        if validPoint(point) then return point end
    end
end

local function worldPoint(mapID, point)
    local continent, position = safe(C_Map and C_Map.GetWorldPosFromMapPos, mapID, point)
    if not number(continent) or not position then return nil end
    local north, west = safe(position.GetXY, position)
    if number(north) and number(west) then return continent, north, west end
end

local function framedPoint(mapID, x, y, frame)
    if not (number(mapID) and mapID > 0 and number(x) and number(y)
        and x >= 0 and x <= 100 and y >= 0 and y <= 100) then return nil end
    if frame ~= "e" then return { mapID = mapID, x = x / 100, y = y / 100 } end
    -- Imported Classic Era percentages are NOT Forever percentages. Recover
    -- the original world point from its documented Era rectangle first.
    local bounds = ns.mapFrames and ns.mapFrames.era and ns.mapFrames.era[mapID]
    if not (bounds and number(bounds.c) and number(bounds.top) and number(bounds.bottom)
        and number(bounds.left) and number(bounds.right)) then return nil end
    local north = bounds.top + (bounds.bottom - bounds.top) * y / 100
    local west = bounds.left + (bounds.right - bounds.left) * x / 100
    local vector = safe(CreateVector2D, north, west)
    local liveMap, livePosition = safe(C_Map and C_Map.GetMapPosFromWorldPos, bounds.c, vector, mapID)
    if livePosition then
        local liveX, liveY = safe(livePosition.GetXY, livePosition)
        local point = { mapID = liveMap, x = liveX, y = liveY }
        if validPoint(point) then return point end
    end
    -- Same conversion using the live map's world rectangle when the reverse
    -- API cannot supply a point. Never substitute unconverted Era values.
    local topLeft = safe(CreateVector2D, 0, 0)
    local bottomRight = safe(CreateVector2D, 1, 1)
    if not topLeft or not bottomRight then return nil end
    local c1, top, left = worldPoint(mapID, topLeft)
    local c2, bottom, right = worldPoint(mapID, bottomRight)
    if c1 ~= bounds.c or c2 ~= bounds.c or not top or not bottom
        or top == bottom or left == right then return nil end
    local point = { mapID = mapID, x = (west - left) / (right - left), y = (north - top) / (bottom - top) }
    return validPoint(point) and point or nil
end

-- Public conversion for authored transit points. `map` uses 0-100 source
-- percentages and optional Era frame f="e"; `mapID` uses live 0-1 values.
function ns:ResolveWaypointPoint(raw)
    if type(raw) ~= "table" then return nil end
    local point
    if validPoint(raw) then
        point = {}
        for key, value in pairs(raw) do point[key] = value end
    else
        point = framedPoint(raw.map or raw.mapID, raw.x, raw.y, raw.f)
    end
    if point then
        if number(raw.z) then point.z = raw.z end
        if number(raw.radius) and raw.radius > 0 then point.radius = raw.radius end
    end
    return point
end

local function token(value)
    return tostring(value or ""):lower():gsub("[%s_%-]", "")
end

local function includes(list, value)
    if not list then return true end
    local wanted = token(value)
    if wanted == "scourge" then wanted = "undead" end
    if type(list) ~= "table" then list = { list } end
    for _, item in ipairs(list) do
        local key = token(item)
        if key == "scourge" then key = "undead" end
        if key == wanted then return true end
    end
    return false
end

local function candidateMatches(candidate, goal)
    local objectiveIndex = candidate.objectiveIndex
    if goal and number(objectiveIndex) and objectiveIndex >= 1 then
        local objectives = safe(C_QuestLog and C_QuestLog.GetQuestObjectives, goal.quest or goal.questID)
        local objective = type(objectives) == "table" and objectives[objectiveIndex]
        -- Missing objective data is unknown, never proof of completion.
        if type(objective) == "table" and objective.finished == true then return false end
    end
    local faction = safe(UnitFactionGroup, "player")
    local code = faction == "Alliance" and "A" or faction == "Horde" and "H" or nil
    if candidate.faction and candidate.faction ~= "AH" and candidate.faction ~= code then return false end
    if ns.MatchesConditions then
        return ns:MatchesConditions({ races = candidate.races, classes = candidate.classes })
    end
    local _, race = safe(UnitRace, "player")
    local _, class = safe(UnitClass, "player")
    return includes(candidate.races, race) and includes(candidate.classes, class)
end

local function pointWorld(point)
    local native = point.walking == true and point.walkingWorld
    if type(native) == "table" and number(native.continent) and number(native.north) and number(native.west) then
        return native.continent, native.north, native.west
    end
    local vector = safe(CreateVector2D, point.x, point.y)
    if not vector then return nil end
    return worldPoint(point.mapID, vector)
end

local function nativePlayerPosition(continent)
    -- Walking checks the map/native phase alignment before emitting a turn.
    -- Keep its exact path node and the moving player in that same frame.
    local north, west, _, instance = safe(UnitPosition, "player")
    if number(continent) and number(instance) and instance == continent and number(north) and number(west) then
        return north, west
    end
end

function ns:GetWaypointWorldPosition(point)
    if validPoint(point) then return pointWorld(point) end
end

-- Keep a normalized map position alongside each exact native terrain turn.
-- Map APIs need percentages; arrow steering retains walkingWorld instead.
function ns:WorldToWaypoint(continent, north, west, mapID)
    if not number(continent) or not number(north) or not number(west) then return nil end
    local vector = safe(CreateVector2D, north, west)
    local liveMap, position = safe(C_Map and C_Map.GetMapPosFromWorldPos, continent, vector, mapID)
    if position then
        local x, y = safe(position.GetXY, position)
        local point = {mapID=liveMap,x=x,y=y}
        if validPoint(point) then return point end
    end
    if not mapID then return nil end
    local c1, top, left = worldPoint(mapID, safe(CreateVector2D,0,0))
    local c2, bottom, right = worldPoint(mapID, safe(CreateVector2D,1,1))
    if c1~=continent or c2~=continent or not top or not bottom or top==bottom or left==right then return nil end
    local point = {mapID=mapID,x=(west-left)/(right-left),y=(north-top)/(bottom-top)}
    return validPoint(point) and point or nil
end

local function playerWorld()
    local map = safe(C_Map and C_Map.GetBestMapForUnit, "player")
    if not number(map) then return nil end
    local position = safe(C_Map.GetPlayerMapPosition, map, "player")
    if not position then return nil end
    local continent, north, west = worldPoint(map, position)
    return continent, north, west, map
end

ns.GetPlayerWorldPosition = playerWorld

-- Among several authored spots, point to the closest one. A small hysteresis
-- (25 yards) prevents the arrow from flickering between two similar spots.
local function nearestPoint(goal, list)
    if #list <= 1 then return list[1] end
    local pc, pn, pw = playerWorld()
    if not pc then return list[1] end
    local best, bestIndex, bestDist, current, currentDist
    for index, point in ipairs(list) do
        local c, n, w = pointWorld(point)
        if c == pc then
            local d = math.sqrt((n - pn) ^ 2 + (w - pw) ^ 2)
            if not bestDist or d < bestDist then best, bestIndex, bestDist = point, index, d end
            if index == goal._rxpSpot then current, currentDist = point, d end
        end
    end
    if current and bestDist and currentDist - bestDist < 25 then return current end
    if best then
        goal._rxpSpot = bestIndex
        return best
    end
    return list[1]
end

-- Exact NPC positions. Authored guide coordinates are approximate (converted
-- from Classic Era), so whenever the player talks to an NPC the real position
-- (the player is within ~5 yards of it) is saved and preferred from then on.
local function npcIDFromGUID(guid)
    if type(guid) ~= "string" or (issecretvalue and issecretvalue(guid)) then return nil end
    local id = guid:match("^Creature%-%d+%-%d+%-%d+%-%d+%-(%d+)%-")
        or guid:match("^Vehicle%-%d+%-%d+%-%d+%-%d+%-(%d+)%-")
    return id and tonumber(id) or nil
end

local function distanceYards(a, b)
    local c1, n1, w1 = pointWorld(a)
    local c2, n2, w2 = pointWorld(b)
    if c1 and c1 == c2 then return math.sqrt((n1 - n2) ^ 2 + (w1 - w2) ^ 2) end
end

function ns:LearnNpcPosition(npcID)
    if not (npcID and self.db) then return end
    if safe(IsInInstance) then return end
    local here = self.PlayerPoint and self:PlayerPoint()
    if not (here and validPoint(here)) or restrictedMap(here.mapID) then return end
    if type(self.db.npcSpots) ~= "table" then self.db.npcSpots = {} end
    local old = self.db.npcSpots[npcID]
    local _, build = safe(GetBuildInfo)
    local entry = { map = here.mapID, x = here.x, y = here.y, n = 1, verified = true, build = build }
    if type(old) == "table" and old.map == here.mapID and number(old.x) and number(old.y) then
        local d = distanceYards({ mapID = old.map, x = old.x, y = old.y }, here)
        if d and d <= 40 then
            -- Average several visits: removes the few yards of interaction range.
            local n = math.min(tonumber(old.n) or 1, 4)
            entry.x = (old.x * n + here.x) / (n + 1)
            entry.y = (old.y * n + here.y) / (n + 1)
            entry.n = n + 1
        end
    end
    self.db.npcSpots[npcID] = entry
end

local function learnedPoint(goal)
    local spots = ns.db and ns.db.npcSpots
    local spot = type(spots) == "table" and goal.npc and spots[goal.npc]
    if type(spot) ~= "table" or not spot.verified then return nil end
    local _, build = safe(GetBuildInfo)
    if not spot.build or not build or spot.build ~= build then return nil end
    local point = { mapID = spot.map, x = spot.x, y = spot.y, source = "learned" }
    return validPoint(point) and point or nil
end

-- Blizzard's own "available quest" marker on the map, throttled and cached.
local markerCache = {}
local function availablePoint(goal)
    if not (goal.quest and goal.map and C_QuestLog and C_QuestLog.GetQuestsOnMap) then return nil end
    local now = type(GetTime) == "function" and GetTime() or 0
    local key = goal.quest .. ":" .. goal.map
    local cached = markerCache[key]
    if cached and now - cached.time < 3 then return cached.point end
    local point
    local list = safe(C_QuestLog.GetQuestsOnMap, goal.map)
    if type(list) == "table" then
        for _, item in ipairs(list) do
            if type(item) == "table" and item.questID == goal.quest and number(item.x) and number(item.y) then
                local candidate = { mapID = goal.map, x = item.x, y = item.y, dynamic = true, source = "game" }
                if validPoint(candidate) then point = candidate end
                break
            end
        end
    end
    markerCache[key] = { time = now, point = point }
    return point
end

local learner = CreateFrame("Frame")
for _, event in ipairs({ "GOSSIP_SHOW", "QUEST_DETAIL", "QUEST_PROGRESS", "QUEST_COMPLETE",
    "QUEST_GREETING", "MERCHANT_SHOW", "TRAINER_SHOW" }) do
    pcall(learner.RegisterEvent, learner, event)
end
learner:SetScript("OnEvent", function()
    -- A selected target can be far away and unrelated to the open dialog.
    -- Only the NPC actually being interacted with can teach a position.
    local id = npcIDFromGUID(safe(UnitGUID, "npc"))
    if id then ns:LearnNpcPosition(id) end
end)

function ns:GetGoalWaypoint(goal)
    if type(goal) ~= "table" then return nil end
    -- These actions follow an item, a personal ability or a moving escort.
    -- A static NPC/start marker would send the player away from the action.
    if goal.navigationMode == "ability" or goal.navigationMode == "escort" then return nil end
    if goal.navigationMode == "inventory" and (type(goal.candidates) ~= "table" or #goal.candidates == 0) then return nil end
    if goal.waypoint then return validPoint(goal.waypoint) and goal.waypoint or nil end
    local point
    if goal.t == "turnin" then point = questPoint(goal.quest, "turnin") end
    if not point and goal.t == "accept" then point = availablePoint(goal) end
    if not point then point = learnedPoint(goal) end
    if not point then
        local list = {}
        local main = framedPoint(goal.map, goal.x, goal.y, goal.f)
        if main then list[#list + 1] = main end
        for _, spot in ipairs(goal.spots or {}) do
            if not spot.alt then
                local item = framedPoint(goal.map, spot.x, spot.y, goal.f)
                if item then list[#list + 1] = item end
            end
        end
        point = nearestPoint(goal, list)
        if point then point.source = "guide" end
    end
    if not point then
        local candidates = {}
        for _, candidate in ipairs(goal.candidates or {}) do
            if candidateMatches(candidate, goal) then
                local candidatePoint = framedPoint(candidate.map, candidate.x, candidate.y, candidate.f)
                local currentMap = safe(C_Map and C_Map.GetBestMapForUnit, "player")
                if candidatePoint and currentMap and candidatePoint.mapID ~= currentMap
                    and (safe(IsInInstance) or restrictedMap(currentMap) or restrictedMap(candidatePoint.mapID)) then
                    candidatePoint = nil
                end
                if candidatePoint then
                    candidatePoint.candidate = candidate
                    candidatePoint.candidateName = candidate.npcName
                    candidates[#candidates + 1] = candidatePoint
                end
            end
        end
        point = nearestPoint(goal, candidates)
        if point then point.source = "guide" end
    end
    if not point and goal.navigationMode ~= "inventory" then point = questPoint(goal.quest, goal.t) end
    if point then
        point.goal = goal
        point.radius = number(goal.r) and goal.r > 0 and goal.r or (goal.t == "goto" and 8 or nil)
        if number(goal.z) then point.z = goal.z end
    end
    return point
end

function ns:GetBaseStepWaypoint(step)
    if not step then return nil end
    if step.waypoint then return validPoint(step.waypoint) and step.waypoint or nil end
    if step.goals then
        local goal, status
        if self.GetActiveGoal then
            local index
            goal, index, status = self:GetActiveGoal(step)
        else goal = step.goals[1] end
        -- Never point at a later NPC while the current objective is a service
        -- without coordinates, or a prerequisite is blocking the route.
        if status == "blocked" then return nil end
        return self:GetGoalWaypoint(goal)
    end
    if step.t then return self:GetGoalWaypoint(step) end
    return questPoint(step.questID, step.action)
end

function ns:GetStepWaypoint(step, travel)
    if travel == nil and self.GetGuideTravel then travel = self:GetGuideTravel() end
    if travel then return travel.point end
    local base = self:GetBaseStepWaypoint(step)
    if self.Recovery and self.Recovery.GetNavigationOverride then
        local override = safe(self.Recovery.GetNavigationOverride, self.Recovery)
        if validPoint(override) then return override end
    end
    if self.Duo and self.Duo.GetMeetingWaypoint then
        local meeting = safe(self.Duo.GetMeetingWaypoint, self.Duo)
        if validPoint(meeting) then return meeting end
    end
    if self.DuoPlanner and self.DuoPlanner.GetNavigationOverride then
        local focus = safe(self.DuoPlanner.GetNavigationOverride, self.DuoPlanner)
        if validPoint(focus) then
            if self.Waypoints and self.Waypoints.ResolveTarget then
                return self.Waypoints:ResolveTarget({base=focus,goal=focus.goal or {t="accept",quest=focus.questID,map=focus.mapID},
                    key="pickup:"..tostring(focus.questID),source=focus.source or "duo-difference"})
            end
            return focus
        end
    end
    if self.DuoAuto and self.DuoAuto.GetSharedView then
        local view = self.DuoAuto:GetSharedView()
        if view and view.following then
            local follow = safe(self.DuoAuto.GetNavigationOverride, self.DuoAuto)
            -- A missing peer target must not fall back to our future quest.
            if not validPoint(follow) then return nil end
            if self.Waypoints and self.Waypoints.ResolveTarget then
                local guide = self.guides[view.guideID]
                local shared = guide and guide.steps[view.sharedCursor]
                local goal = follow.goal or (shared and shared.goals and shared.goals[follow.goalIndex])
                return self.Waypoints:ResolveTarget({base=follow,goal=goal,guide=guide,step=shared,guideID=view.guideID,
                    stepIndex=view.sharedCursor,goalIndex=follow.goalIndex,review=false,source="duo-follow",
                    key="follow:"..view.guideID..":"..view.sharedCursor..":"..tostring(follow.goalIndex)})
            end
            return follow
        end
    end
    if step and step.goals and self.GetActiveGoal then
        local _, _, status = self:GetActiveGoal(step)
        if status == "blocked" then return nil end
    end
    if self.Waypoints and self.Waypoints.Resolve then
        local goal = step
        if step and step.goals and self.GetActiveGoal then goal = self:GetActiveGoal(step) end
        return self.Waypoints:Resolve(step, goal, base)
    end
    return base
end

-- Keep terrain steering separate from the semantic target used by the map
-- and quest engine. Reaching a bend must never finish the real travel goal.
function ns:GetArrowWaypoint(step, travel)
    local point = self:GetStepWaypoint(step, travel)
    if self.Walking then return self.Walking:Resolve(point) end
    return point
end

-- Returns straight-line distance in YARDS, then the normalized screen-right
-- and screen-up components relative to the character's facing, plus raw dNorth/dWest.
function ns:GetWaypointVector(point)
    if not validPoint(point) then return nil, "Sin destino disponible" end
    if not (C_Map and C_Map.GetBestMapForUnit and C_Map.GetPlayerMapPosition
        and C_Map.GetWorldPosFromMapPos and CreateVector2D) then
        return nil, "Posición no disponible"
    end
    local playerMap = safe(C_Map.GetBestMapForUnit, "player")
    if not number(playerMap) then return nil, "Posición no disponible" end
    local inInstance = safe(IsInInstance)
    if point.mapID ~= playerMap and (inInstance or restrictedMap(playerMap) or restrictedMap(point.mapID)) then
        return nil, "Destino en otro mapa"
    end
    local playerPosition = safe(C_Map.GetPlayerMapPosition, playerMap, "player")
    if not playerPosition then return nil, "Posición no disponible" end
    local originContinent, playerNorth, playerWest = worldPoint(playerMap, playerPosition)
    local targetContinent, targetNorth, targetWest = pointWorld(point)
    if not originContinent or not targetContinent then return nil, "Posición no disponible" end
    if originContinent ~= targetContinent then return nil, "Destino en otro continente" end
    if point.walking == true then
        local nativeNorth, nativeWest = nativePlayerPosition(targetContinent)
        if nativeNorth then playerNorth, playerWest = nativeNorth, nativeWest end
    end

    local north, west = targetNorth - playerNorth, targetWest - playerWest
    local distance = math.sqrt(north * north + west * west)
    if distance < 0.01 then return distance, 0, 1, north, west end
    local facing = safe(GetPlayerFacing)
    if not number(facing) then return distance, nil, nil, north, west end
    local sine, cosine = math.sin(facing), math.cos(facing)
    local right = (north * sine - west * cosine) / distance
    local forward = (north * cosine + west * sine) / distance
    return distance, right, forward, north, west
end

function ns:GetWaypointHeightDifference(point)
    if not point or not number(point.z) then return nil end
    local _, _, height, instance = safe(UnitPosition, "player")
    local continent = pointWorld(point)
    -- Only native player height uses Forever's 0 sentinel; target z=0 is valid.
    if number(height) and height ~= 0 and number(instance) and instance == continent then return point.z - height end
end

function ns:IsAtWaypoint(step)
    -- Quest/travel completion always measures the actual guide destination.
    -- Reaching an itinerary entry or recovery marker cannot complete it.
    local point = self:GetBaseStepWaypoint(step)
    if not point then return false end
    local distance = self:GetWaypointVector(point)
    if point.z then
        local delta = self:GetWaypointHeightDifference(point)
        if not delta or math.abs(delta) > 8 then return false end
    end
    local radius = number(step.radius) and step.radius > 0 and step.radius or point.radius or 20
    return distance ~= nil and distance <= radius
end

local function outlinedText(parent, font, y, width, size)
    local item = parent:CreateFontString(nil, "OVERLAY", font)
    item:SetPoint("TOP", 0, y)
    item:SetWidth(width)
    item:SetJustifyH("CENTER")
    item:SetJustifyV("TOP")
    if item.GetFont and item.SetFont then
        local fontPath, fontSize = item:GetFont()
        if fontPath then item:SetFont(fontPath, size or fontSize or 12, "OUTLINE") end
    end
    if item.SetShadowColor then
        item:SetShadowColor(0, 0, 0, 0.9)
        item:SetShadowOffset(1, -1)
    end
    return item
end

local ANCHORS = { TOPLEFT = true, TOP = true, TOPRIGHT = true, LEFT = true,
    CENTER = true, RIGHT = true, BOTTOMLEFT = true, BOTTOM = true, BOTTOMRIGHT = true }

local function applyArrowRotation(frame, angle)
    if frame.body and frame.body.SetRotation then frame.body:SetRotation(angle) end
    if frame.facet and frame.facet.SetRotation then frame.facet:SetRotation(angle) end
    if frame.glow and frame.glow.SetRotation then frame.glow:SetRotation(angle) end
end

function ns:CreateNavigation()
    if self.navigationFrame or not self.char then return end
    local frame = CreateFrame("Frame", nil, UIParent)
    self.navigationFrame = frame
    frame:SetSize(210, 114)
    frame:SetFrameStrata("MEDIUM")
    frame:SetClampedToScreen(true)
    frame:SetMovable(true)
    frame:EnableMouse(true)
    frame:RegisterForDrag("LeftButton")

    local saved = self.char.arrowPosition
    if type(saved) == "table" and ANCHORS[saved.point] and ANCHORS[saved.relativePoint]
        and number(saved.x) and number(saved.y) then
        frame:SetPoint(saved.point, UIParent, saved.relativePoint, saved.x, saved.y)
    else
        frame:SetPoint("TOP", UIParent, "TOP", 0, -95)
    end

    frame:SetScript("OnDragStart", function(item) item:StartMoving() end)
    frame:SetScript("OnDragStop", function(item)
        item:StopMovingOrSizing()
        local point, _, relativePoint, x, y = item:GetPoint()
        self.char.arrowPosition = { point = point, relativePoint = relativePoint, x = x, y = y }
    end)

    -- Subtle hover glow behind the arrow when hovering with mouse
    local hoverBg = frame:CreateTexture(nil, "BACKGROUND")
    if hoverBg.SetTexture then hoverBg:SetTexture(NAV_MEDIA .. "glow") end
    hoverBg:SetSize(84, 84)
    hoverBg:SetPoint("TOP", 0, 10)
    if hoverBg.SetVertexColor then hoverBg:SetVertexColor(1, 0.82, 0.45, 0.22) end
    hoverBg:Hide()
    frame.hoverBg = hoverBg

    frame:SetScript("OnEnter", function(item)
        hoverBg:Show()
        if not GameTooltip then return end
        GameTooltip:SetOwner(item, "ANCHOR_BOTTOM")
        GameTooltip:SetText("Flecha de RutaXP", 1, 0.82, 0.45)
        if item.navigationReason then GameTooltip:AddLine(item.navigationReason, 0.85, 0.88, 0.92, true) end
        GameTooltip:AddLine("Arrastra con clic izquierdo para moverla.", 0.85, 0.88, 0.92, true)
        GameTooltip:Show()
    end)
    frame:SetScript("OnLeave", function()
        hoverBg:Hide()
        if GameTooltip then GameTooltip:Hide() end
    end)

    local arrow = CreateFrame("Frame", nil, frame)
    arrow:SetSize(DIAL, DIAL)
    arrow:SetPoint("TOP", 0, -2)
    frame.arrow = arrow

    -- Soft ambient halo behind the arrow
    local halo = arrow:CreateTexture(nil, "BACKGROUND")
    if halo.SetTexture then halo:SetTexture(NAV_MEDIA .. "glow") end
    halo:SetSize(DIAL * 1.35, DIAL * 1.35)
    halo:SetPoint("CENTER")
    if halo.SetBlendMode then halo:SetBlendMode("ADD") end
    frame.halo = halo

    -- Directional glow rotated with the arrow
    local glow = arrow:CreateTexture(nil, "BACKGROUND", nil, 1)
    if glow.SetTexture then glow:SetTexture(NAV_MEDIA .. "arrow-glow") end
    glow:SetSize(DIAL * 1.25, DIAL * 1.25)
    glow:SetPoint("CENTER")
    if glow.SetBlendMode then glow:SetBlendMode("ADD") end
    frame.glow = glow

    -- High-resolution faceted arrow body + bevel overlay rotated continuously on GPU
    local body = arrow:CreateTexture(nil, "ARTWORK")
    if body.SetTexture then body:SetTexture(NAV_MEDIA .. "arrow") end
    body:SetAllPoints()
    frame.body = body

    local facet = arrow:CreateTexture(nil, "OVERLAY")
    if facet.SetTexture then facet:SetTexture(NAV_MEDIA .. "arrow-facet") end
    facet:SetAllPoints()
    frame.facet = facet

    -- Arrival ring when within target radius
    local ring = arrow:CreateTexture(nil, "ARTWORK")
    if ring.SetTexture then ring:SetTexture(NAV_MEDIA .. "arrived") end
    ring:SetSize(DIAL, DIAL)
    ring:SetPoint("CENTER")
    ring:Hide()
    frame.ring = ring

    frame.distance = outlinedText(frame, "GameFontNormalLarge", -60, 200, 15)
    frame.destination = outlinedText(frame, "GameFontHighlightSmall", -78, 206, 11)
    frame.roadside = outlinedText(frame, "GameFontHighlightSmall", 0, 220, 11)
    frame.roadside:ClearAllPoints()
    frame.roadside:SetPoint("TOP", frame.destination, "BOTTOM", 0, -2)
    frame.roadside:SetTextColor(0.55, 1, 0.68)
    frame:Hide()

    local updater = CreateFrame("Frame")
    self.navigationUpdater = updater
    local elapsedTime = 0
    local pulse = 0
    updater:SetScript("OnUpdate", function(_, elapsed)
        elapsedTime = elapsedTime + elapsed
        if elapsedTime >= SAMPLE_INTERVAL then
            elapsedTime = 0
            self:UpdateNavigation()
            if self.OnNavigationTick then self:OnNavigationTick() end
        end
        -- Per-frame rotation using the LIVE player position and facing, so the
        -- arrow never lags behind while running or strafing.
        if frame:IsShown() and frame.arrow:IsShown() then
            if frame.arrived then
                pulse = pulse + elapsed
                local s = 1 + 0.06 * math.sin(pulse * 4)
                frame.ring:SetSize(DIAL * s, DIAL * s)
            else
                local facing = safe(GetPlayerFacing)
                if number(facing) then
                    local dNorth, dWest = frame.dNorth, frame.dWest
                    local nativeNorth, nativeWest
                    if frame.useNativePosition then nativeNorth, nativeWest = nativePlayerPosition(frame.targetContinent) end
                    if nativeNorth then
                        dNorth, dWest = frame.targetNorth - nativeNorth, frame.targetWest - nativeWest
                    elseif frame.targetContinent and frame.playerMap then
                        local position = safe(C_Map and C_Map.GetPlayerMapPosition, frame.playerMap, "player")
                        if position then
                            local c, n, w = worldPoint(frame.playerMap, position)
                            if c == frame.targetContinent then
                                dNorth, dWest = frame.targetNorth - n, frame.targetWest - w
                            end
                        end
                    end
                    if dNorth and dWest then
                        local angle = (math.atan2(dWest, dNorth) - facing) % TWO_PI
                        applyArrowRotation(frame, angle)
                    end
                end
            end
        end
    end)
end

function ns:UpdateNavigation()
    if not self.char then return end
    if not self.navigationFrame then self:CreateNavigation() end
    local frame = self.navigationFrame
    if not frame then return end
    frame.navigationState, frame.navigationReason = nil, nil
    if self.char.arrow == false then
        if self.Walking then self.Walking:Clear() end
        frame.dNorth, frame.dWest = nil, nil
        frame:Hide()
        return
    end
    local guide, step, state = self:GetCurrent()
    local travel = self.GetGuideTravel and self:GetGuideTravel()
    local point = self:GetArrowWaypoint(step, travel or false)
    if frame.roadside and self.GetNearbyQuestOfferHint then
        local hint = self:GetNearbyQuestOfferHint(guide, step, state, travel)
        if hint ~= frame.roadsideText then
            frame.roadside:SetText(hint or "")
            frame.roadsideText = hint
        end
    end
    if travel then step = travel end
    if not step and not point then
        if self.Walking then self.Walking:Clear() end
        frame.dNorth, frame.dWest = nil, nil
        frame:Hide()
        return
    end
    frame:Show()

    if travel and not point then
        -- The tram and partner waits have instructions but no walkable target.
        frame.dNorth, frame.dWest, frame.targetContinent, frame.arrived = nil, nil, nil, false
        frame.arrow:Hide()
        frame.navigationState = travel.waiting and "waiting" or "instruction"
        frame.navigationReason = travel.text
        frame.distance:SetText(travel.title)
        frame.destination:SetText(travel.text)
        return
    end
    local activeGoal = point and point.goal or (step and step.goals and self.GetActiveGoal and self:GetActiveGoal(step))
    local goalTitle = activeGoal and self.GetGoalTitle and self:GetGoalTitle(activeGoal)
    local stepTitle = step and step.title
    local subText = (stepTitle and goalTitle and stepTitle ~= goalTitle)
        and (goalTitle .. "\n|cff9fb0c7" .. stepTitle .. "|r")
        or (goalTitle or stepTitle or "Siguiente destino")

    if point and point.intermediate then
        subText = string.format("|cffffce72Punto %d/%d: %s|r\n%s", point.pointIndex, point.pointCount,
            point.routeLabel or "Paso intermedio", goalTitle or stepTitle or "Objetivo de la guía")
    end
    if point and (point.source == "duo-meeting" or point.source == "duo-difference") then
        subText = "|cffffce72" .. (point.label or point.title or "Punto de dúo") .. "|r\nVolver a la misión: Dúo > Reunión"
    end
    if point and (point.source == "duo-follow" or point.targetSource == "duo-follow") and not point.intermediate then
        subText = "|cffffce72" .. (point.label or point.title or "Acompaña al compañero") .. "|r\nTu progreso propio se conserva"
    end
    local distance, right, forward, dNorth, dWest
    if point and not point.navigationBlocked then
        distance, right, forward, dNorth, dWest = self:GetWaypointVector(point)
    end
    local goal = point and point.goal
    local contact = goal and (point.candidateName or goal.npcName)
    local questTarget = point and (point.source == "guide" or point.source == "game" or point.source == "learned")
    if distance and distance <= CONTACT_RANGE and questTarget and not point.intermediate
        and (not point.walking or point.walkingFinal) and contact and (goal.t == "accept" or goal.t == "turnin") then
        subText = "|cffffce72Habla con " .. contact .. "|r\n" .. (goalTitle or stepTitle or "")
    elseif point and point.walking then
        local target = point.walkingGoal
        local label = target and (target.routeLabel or target.label or target.goalTitle) or goalTitle or stepTitle
        subText = string.format("|cffffce72Camino por terreno · tramo %d/%d|r\n%s", math.max(1,point.walkingIndex-1),
            math.max(1,point.walkingCount-1),label or "Sigue el siguiente giro")
    end
    if point and not point.walking and point.navigationNotice then
        subText = subText .. "\n|cff9fb0c7" .. point.navigationNotice .. "|r"
    end

    if not point then
        frame.dNorth, frame.dWest, frame.targetContinent = nil, nil, nil
        frame.arrow:Hide()
        local action = activeGoal and (activeGoal.t or activeGoal.action)
        local anywhere = { hearth="Usa tu piedra de hogar", level="Gana experiencia", note="Indicaciones de la guía" }
        local message = anywhere[action]
        if activeGoal and activeGoal.navigationMode == "inventory" then message = "Usa los objetos de la misión en tus bolsas"
        elseif activeGoal and activeGoal.navigationMode == "ability" then message = "Usa la habilidad indicada en la guía"
        elseif activeGoal and activeGoal.navigationMode == "escort" then message = "Sigue y protege al personaje de la escolta" end
        if action == "accept" and activeGoal.item then message = "Abre el objeto en tus bolsas" end
        if activeGoal and step and step.goals and self.GetActiveGoal then
            local _, _, status, reason = self:GetActiveGoal(step)
            if status == "blocked" then
                message, frame.navigationState = "Requisito pendiente", "blocked"
                frame.navigationReason = reason
                subText = reason or goalTitle or stepTitle
            end
        end
        if not activeGoal and step and step.goals and self.GetActiveGoal then
            -- A resolved local visit has no NPC left to navigate to. Waiting
            -- for the peer does not mean that its coordinates are missing.
            local waiting, reason, waitKind
            if self.DuoAuto and self.DuoAuto.ShouldWaitForStep then
                waiting, reason = safe(self.DuoAuto.ShouldWaitForStep, self.DuoAuto, step)
            end
            if not waiting and self.Duo then
                local status = self.Duo.GetStepWaitStatus and safe(self.Duo.GetStepWaitStatus, self.Duo, step)
                if type(status) == "table" then
                    waiting, reason, waitKind = status.waiting == true, status.reason, status.unknown and "sync" or status.kind
                elseif self.Duo.ShouldWaitForStep then
                    waiting, reason = safe(self.Duo.ShouldWaitForStep, self.Duo, step)
                end
            end
            if waiting then
                message = waitKind == "sync" and "Sincronizando misiones" or "Esperando al compañero"
                frame.navigationReason = type(reason) == "string" and reason ~= "" and reason or message
                frame.navigationState = "waiting"
            else
                local view = self.DuoAuto and safe(self.DuoAuto.GetSharedView, self.DuoAuto)
                local _, currentStep, state = self:GetCurrent()
                if view and view.following then
                    message, frame.navigationState = "Destino del compañero todavía no disponible", "waiting"
                elseif currentStep == step and state and state.review then
                    message, frame.navigationState = "Paso completado · revisión manual", "review"
                elseif self.char.auto == false then
                    message, frame.navigationState = "Paso completado · pulsa Siguiente para continuar", "manual"
                else
                    message, frame.navigationState = "Paso completado", "complete"
                end
            end
        end
        frame.navigationState = frame.navigationState or (message and "instruction" or "missing")
        frame.navigationReason = frame.navigationReason or message or "Sin coordenadas para esta acción"
        frame.distance:SetText("|cffffb468" .. (message or "Sin coordenadas para esta acción") .. "|r")
        frame.destination:SetText(subText)
        return
    end
    if point.navigationBlocked then
        frame.dNorth, frame.dWest, frame.targetContinent = nil, nil, nil
        frame.arrow:Hide()
        frame.distance:SetText("|cffffb468" .. (point.navigationNotice or "Calculando camino…") .. "|r")
        frame.destination:SetText(goalTitle or stepTitle or "Destino de la guía")
        return
    end

    frame.dNorth, frame.dWest = dNorth, dWest
    frame.targetContinent, frame.targetNorth, frame.targetWest = pointWorld(point)
    frame.useNativePosition = point.walking == true
    frame.playerMap = safe(C_Map and C_Map.GetBestMapForUnit, "player")
    if not distance then
        frame.targetContinent = nil
        frame.arrow:Hide()
        frame.distance:SetText("|cffffb468" .. (right or "En otra zona") .. "|r")
        frame.destination:SetText(subText)
        return
    end

    local metres = (point.walkingDistance or distance) * METRES_PER_YARD
    local radius = step and number(step.radius) and step.radius > 0 and step.radius or point.radius or 20
    local inRange = distance <= radius
    -- The arrow keeps pointing until you are practically on top of the spot;
    -- "inRange" (quest radius) only changes colour and text.
    local heightDelta = self:GetWaypointHeightDifference(point)
    local arrived = distance <= 4 and (not point.walking or point.walkingFinal)
        and (not point.z or (heightDelta and math.abs(heightDelta) <= 8))
    frame.arrived = arrived

    -- Smooth color transition from warm gold (far) to emerald green (close)
    local t = 1 - (distance - radius) / CLOSE_RANGE
    if t < 0 then t = 0 elseif t > 1 then t = 1 end
    t = t * t * (3 - 2 * t)
    local r = 0.96 + (0.42 - 0.96) * t
    local g = 0.68 + (0.88 - 0.68) * t
    local b = 0.36 + (0.62 - 0.36) * t

    if point.intermediate and point.waiting and distance <= radius then
        frame.distance:SetText("|cffffb468" .. point.waiting .. "|r")
    elseif heightDelta and distance <= radius and math.abs(heightDelta) > 8 then
        frame.distance:SetText(heightDelta > 0 and "|cffffb468El objetivo está más arriba|r" or "|cffffb468El objetivo está más abajo|r")
    elseif arrived then
        frame.distance:SetText("|cff6be09e¡Has llegado!|r")
    else
        local distStr = metres >= 1000 and string.format("%.1f km", metres / 1000)
            or metres < 20 and string.format("%.1f m", metres)
            or string.format("%d m", math.floor(metres + 0.5))
        frame.distance:SetText(distStr)
        if frame.distance.SetTextColor then frame.distance:SetTextColor(r, g, b) end
    end
    frame.destination:SetText(subText)

    if right == nil or forward == nil then
        frame.arrow:Hide()
        return
    end

    frame.arrow:Show()
    if arrived then
        frame.body:Hide()
        frame.facet:Hide()
        frame.glow:Hide()
        frame.ring:Show()
        if frame.ring.SetVertexColor then frame.ring:SetVertexColor(0.42, 0.88, 0.62, 1) end
        if frame.halo.SetVertexColor then frame.halo:SetVertexColor(0.42, 0.88, 0.62, 0.45) end
    else
        frame.ring:Hide()
        frame.body:Show()
        frame.facet:Show()
        frame.glow:Show()
        local angle = (-math.atan2(right, forward)) % TWO_PI
        applyArrowRotation(frame, angle)
        if frame.body.SetVertexColor then frame.body:SetVertexColor(r, g, b, 1) end
        if frame.glow.SetVertexColor then frame.glow:SetVertexColor(r, g, b, 0.45) end
        if frame.halo.SetVertexColor then frame.halo:SetVertexColor(r, g, b, 0.32) end
    end
end
