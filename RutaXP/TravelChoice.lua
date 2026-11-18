local _, ns = ...
local Choice = {}
ns.TravelChoice = Choice

local work = {kill=true, collect=true, complete=true, objective=true, interact=true, use=true, talk=true}
local transports = {boat=true, fly=true, hearth=true}
local function read(fn, ...)
    if type(fn) ~= "function" then return end
    local ok, value = pcall(fn, ...)
    if ok and not (issecretvalue and issecretvalue(value)) then return value end
end

local function mapTitle(map)
    local info = read(C_Map and C_Map.GetMapInfo, map)
    return info and info.name
end

local function title(goal)
    return read(C_QuestLog and C_QuestLog.GetTitleForQuestID, goal.quest) or goal.title or ("Misión " .. goal.quest)
end

local function applies(entry)
    return (not entry.faction or entry.faction == UnitFactionGroup("player"))
        and ns:MatchesConditions(entry) and ns:MatchesConditions(entry.only)
end

local function referenceLevel()
    local level = read(UnitLevel, "player")
    if type(level) ~= "number" or level <= 0 then return end
    local duo = ns.Duo and ns.Duo:GetContext()
    if duo and duo.enabled and duo.known and duo.online and duo.sameParty and duo.partnerHeaderFresh
        and duo.groupSize == 2 and type(duo.partnerLevel) == "number" and duo.partnerLevel > 0 then
        return math.min(level, duo.partnerLevel), true
    end
    return level, false
end

local function legacyKind(goal)
    if goal.t ~= "goto" or not goal.text or not goal.map or not goal.x or not goal.y then return end
    local text = goal.text:lower()
    if text:match("^boat ") or text:match("^barco ") then return "boat" end
    if text:find("zeppelin", 1, true) then return "zeppelin" end
    if text:match("^portal ") then return "portal" end
    if text:match("^tren ") or text:match("^tram ") then return "tram" end
end

local function firstDeparture(step)
    for _, goal in ipairs(step and step.goals or {}) do
        if transports[goal.t] or legacyKind(goal) then return true end
    end
end

local function goalMap(goal)
    return goal.map or (goal.waypoint and goal.waypoint.mapID)
end

-- Several older chapters encode the pier as a walking waypoint. Require the
-- authored transport, its verified departure position AND a next stop on the
-- matching arrival map. Menethil's northern pier serves two destinations.
local function legacyDestination(guide, si, gi, origin, goal, kind)
    if goal.map ~= origin then return end
    local nextMap
    for s = si, math.min(si+1, #guide.steps) do
        local step = guide.steps[s]
        if applies(step) then
            for i = s == si and gi+1 or 1, #(step.goals or {}) do
                local nextGoal = step.goals[i]
                if applies(nextGoal) then
                    nextMap = goalMap(nextGoal)
                    if nextMap then break end
                end
            end
        end
        if nextMap then break end
    end
    if not nextMap or nextMap == origin then return end
    local faction = read(UnitFactionGroup, "player") == "Alliance" and 1 or 2
    for _, crossing in ipairs(ns.GuideTravelConnections or {}) do
        if crossing.kind == kind and (crossing.mask == 3 or crossing.mask == faction) then
            local from, to = crossing.a, crossing.b
            if to.map == origin and not crossing.oneWay then from, to = to, from end
            if from.map == origin and to.map == nextMap and from.f == goal.f and
                (from.x-goal.x)^2 + (from.y-goal.y)^2 <= .6^2 then return nextMap end
        end
    end
end

local function journey(guide, step, state, travel, origin)
    if travel then
        local destination = ns.guides[travel.destination]
        local route = ns.GuideTravelRoutes[travel.source]
        if not destination or not route or travel.waiting or not travel.point then return end
        for _, variant in ipairs(route.variants or {}) do
            if ns:MatchesConditions(variant.only) then route = variant; break end
        end
        local first = route.legs and route.legs[1]
        if not first or first.map ~= origin or travel.arrivalMap == origin then return end
        local key = table.concat({travel.source, travel.destination, origin}, ":")
        return {key=key, guide=destination, start=1, destination=travel.arrivalMap, kind="chapter"}
    end
    if not firstDeparture(step) then return end
    local goal, index, status = ns:GetActiveGoal(step, state)
    if not goal or status ~= "active" and status ~= "manual" then return end
    local kind = legacyKind(goal) or goal.t
    local destination, flight, label
    if goal.t == "boat" then
        if not goal.departure or goal.departure.map ~= origin then return end
        local phase = ns.BoatNavigation:GetSharedView(goal, guide, state.cursor, index)
        if phase and phase.state ~= "approach" then return end
        destination = goal.arrival and goal.arrival.map
        -- The published Menethil excursion continues to the Great Lift. A
        -- connection seen from Theramore (32) to Thalanaar (31) can shorten
        -- that land leg. It says nothing about flying between continents.
        if guide.id == "forever/alliance/07-thousand-needles" and origin == 1437 and destination == 1445 then
            flight = ns.FlightNavigation and ns.FlightNavigation:HasObservedConnection(32, 31)
        end
    elseif goal.t == "fly" then
        destination, flight = ns.FlightNavigation:GetPlanningConnection(goal, origin)
    elseif goal.t == "goto" and kind ~= goal.t then
        destination = legacyDestination(guide, state.cursor, index, origin, goal, kind)
        label = goal.text:match("^[Bb]oat a (.+)$") or goal.text:match("^[Bb]arco a (.+)$")
    else
        -- A hearth item alone does not identify the character's bind point.
        return
    end
    if not destination or destination == origin then return end
    return {key=table.concat({guide.id, guide.routeRevision or 1, state.cursor, index, origin}, ":"),
        guide=guide, start=state.cursor, first=index+1, destination=destination, flight=flight, kind=kind,
        label=label or goal.location}
end

-- Index authored positions once per zone. Evaluate actual work and delivery
-- state only for quests carried by this character, including later chapters.
local index = {}
local function localIndex(zone)
    if index.zone == zone and index.count == #ns.order then return index.rows end
    local rows = {}
    for _, guideID in ipairs(ns.order) do
        local guide = ns.guides[guideID]
        if guide and not guide.recovery and not guide.temporary and applies(guide) then
            for si, step in ipairs(guide.steps or {}) do
                if applies(step) then
                    for gi, goal in ipairs(step.goals or {}) do
                        if goal.quest and (goal.t == "turnin" or work[goal.t]) and applies(goal) then
                            local onMap = goalMap(goal) == zone
                            if not onMap then
                                for _, candidate in ipairs(goal.candidates or {}) do
                                    if candidate.map == zone then onMap = true; break end
                                end
                            end
                            -- An unpositioned hand-in can still have a live
                            -- destination supplied by the client's quest map.
                            if onMap or goal.t == "turnin" and not goalMap(goal) then
                                rows[#rows+1] = {guide=guide, step=step, goal=goal, stepIndex=si, index=gi}
                            end
                        end
                    end
                end
            end
        end
    end
    index = {zone=zone, count=#ns.order, rows=rows}
    return rows
end

local function enemyRange(id, active)
    -- Required kill objectives all matter. For alternative sources of one
    -- dropped item use the least demanding documented source.
    local hardest, easiest
    local objectives = active and read(C_QuestLog and C_QuestLog.GetQuestObjectives, id)
    for _, enemy in ipairs((ns.travelEnemyLevels or {})[id] or {}) do
        local objective = type(objectives) == "table" and objectives[enemy.oi]
        if not (objective and read(function() return objective.finished end) == true) then
            if enemy.required then
                if not hardest or enemy.min > hardest.min then hardest = enemy end
            elseif not easiest or enemy.min < easiest.min then easiest = enemy end
        end
    end
    return hardest or easiest
end

local function nearby(zone, level, duo, savedQuests)
    local best, journal = {}, {}
    for _, row in ipairs(localIndex(zone)) do
        local goal = row.goal
        local id = goal.quest
        if journal[id] == nil then
            local active = ns:IsQuestActive(id)
            local complete = active and read(C_QuestLog and C_QuestLog.IsComplete, id)
            journal[id] = false
            if active and type(complete) == "boolean" and not ns:IsQuestDelivered(id) then
                local peer = duo and ns.Duo:GetPartnerQuest(id)
                if not duo or peer and not peer.basic and peer.state == (complete and 2 or 1) then
                    journal[id] = complete and "turnin" or "work"
                end
            end
        end
        if goal.t == "turnin" and journal[id] == "turnin" or work[goal.t] and journal[id] == "work" then
            local state = ns.char.progress and ns.char.progress[row.guide.id]
            local enemy = work[goal.t] and enemyRange(id, true)
            if (not enemy or enemy.min < level+3)
                and ns:GetGoalStatus(goal, row.step, state, row.index, row.guide) == "active" then
                local point = ns:GetGoalWaypoint(goal)
                local distance = point and point.mapID == zone and ns:GetWaypointVector(point)
                if type(distance) == "number" and (distance <= 1800 or savedQuests and savedQuests[id])
                    and (not best[id] or distance < best[id].distance) then
                    best[id] = {quest=id, goal=goal, step=row.step, guide=row.guide, index=row.index,
                        stepIndex=row.stepIndex, title=title(goal), point=point, distance=distance}
                end
            end
        end
    end
    local rows = {}
    for _, row in pairs(best) do rows[#rows+1] = row end
    table.sort(rows, function(a,b)
        if a.distance == b.distance then return a.quest < b.quest end
        return a.distance < b.distance
    end)
    return rows
end

local function destinationBlock(trip, zone, level)
    local available, seen, goals = {}, {}, {}
    local hard, hardGoal
    local state = ns.char.progress and ns.char.progress[trip.guide.id]
    for si = trip.start, math.min(#trip.guide.steps, trip.start+8) do
        local step = trip.guide.steps[si]
        if applies(step) then
            for gi = si == trip.start and (trip.first or 1) or 1, #(step.goals or {}) do
                local goal = step.goals[gi]
                local kind = legacyKind(goal)
                if si ~= trip.start and (transports[goal.t] or kind and
                    legacyDestination(trip.guide, si, gi, goal.map, goal, kind)) then
                    return goals, hard, hardGoal
                end
                local id = goal.quest
                if id and goalMap(goal) ~= zone and applies(goal) and not ns:IsQuestDelivered(id) then
                    local active = ns:IsQuestActive(id)
                    local status = ns:GetGoalStatus(goal, step, state, gi, trip.guide)
                    if goal.t == "accept" and status == "active" and level >= (goal.minLevel or 1) then available[id] = true end
                    local ready = active and read(C_QuestLog and C_QuestLog.IsComplete, id)
                    if goalMap(goal) and not seen[id] and
                        (work[goal.t] and (active and ready == false and status == "active"
                            or not active and available[id] and status ~= "skip" and status ~= "done")
                        or goal.t == "turnin" and ready == true and status == "active") then
                        seen[id] = true
                        goals[#goals+1] = {id=id, title=title(goal), map=goalMap(goal)}
                        local enemy = work[goal.t] and enemyRange(id, active)
                        if enemy and enemy.min >= level+3 and (not hard or enemy.min > hard.min) then
                            hard, hardGoal = enemy, title(goal)
                        end
                    end
                end
            end
        end
    end
    return goals, hard, hardGoal
end

local function compare(trip, zone, level, duo, savedQuests)
    local localGoals = nearby(zone, level, duo, savedQuests)
    local dest, hard, hardTitle = destinationBlock(trip, zone, level)
    if #localGoals == 0 and not hard then return end
    -- Prefer a long transfer once its block is substantially larger than
    -- the work already in the journal. A confirmed flight reduces that cost.
    local localWeight = trip.flight and 1 or 2
    local prefer = #localGoals > 0 and (hard ~= nil or #localGoals * localWeight >= #dest)
    local destination = trip.label or mapTitle(trip.destination) or "el destino"
    local names = {}
    for i=1,math.min(#localGoals,2) do names[i] = localGoals[i].title end
    local localText = #localGoals == 0 and (duo and "No hay objetivos cercanos confirmados en ambos diarios"
            or "No hay objetivos cercanos confirmados en tu diario")
        or #localGoals == 1 and "Tienes 1 misión cercana" or ("Tienes %d misiones cercanas"):format(#localGoals)
    if duo and #localGoals > 0 then localText = localText .. " en ambos diarios" end
    local details = {localText .. (#names > 0 and (" (" .. table.concat(names, ", ") .. ")") or "") .. "."}
    local destMap = dest[1] and dest[1].map
    for _, entry in ipairs(dest) do if entry.map ~= destMap then destMap = nil; break end end
    local place = destMap and mapTitle(destMap)
    local destinationText = #dest == 1 and "1 misión prevista" or ("%d misiones previstas"):format(#dest)
    details[#details+1] = (place and ("En " .. place) or "Tras el viaje") .. " hay " .. destinationText .. "."
    if hard then
        details[#details+1] = ("%s incluye %s de nivel %d–%d."):format(hardTitle, hard.label, hard.min, hard.max)
    end
    if trip.flight then
        details[#details+1] = trip.kind == "boat" and "Tienes observado el vuelo de Theramore a Thalanaar."
            or "El maestro de salida ya te ofreció el vuelo."
    elseif trip.kind == "fly" or trip.flight == false then
        details[#details+1] = "Todavía no hay un vuelo confirmado para ese trayecto."
    end
    if duo then details[#details+1] = "El de menor nivel del dúo está en " .. level .. "." end
    return {key=trip.key, originMap=zone, summary=table.concat(details, " "), localGoals=localGoals,
        localCount=#localGoals, destinationGoals=dest, destinationCount=#dest, level=level,
        hardTitle=hardTitle, hardLevel=hard and hard.min, preferLocal=prefer,
        localTitle=mapTitle(zone) or "Esta zona", destinationTitle=destination, flightConfirmed=trip.flight == true}
end

function Choice:GetRecommendation(guide, step, state, travel, activeKey)
    if not guide or not state or state.review or not ns.char or guide.recovery or guide.temporary or
        (not travel and not firstDeparture(step)) then return end
    local zone = ns.TravelRouting.Zone()
    if not zone or ns.TravelRouting.OnTaxi() then return end
    local trip = journey(guide, step, state, travel, zone)
    if not trip then return end
    if activeKey ~= trip.key then activeKey = nil end
    local level, duo = referenceLevel()
    if not level then return end
    local now = read(GetTime)
    local saved = activeKey and ns.char.localTravelChoice
    local savedQuests = type(saved) == "table" and saved.key == trip.key and saved.quests
    local key = table.concat({trip.key, level, tostring(duo), tostring(trip.flight), tostring(activeKey),
        tostring(ns.char.includeGroupQuests), tostring(ns.char.optional), tostring(ns.char.skipTrivial)}, "|")
    if now and self.key == key and self.at and now >= self.at and now-self.at < 2 then return self.view end
    self.view, self.key, self.at = compare(trip, zone, level, duo, savedQuests), key, now
    return self.view
end

local events = CreateFrame("Frame")
for _, event in ipairs({"QUEST_LOG_UPDATE","QUEST_ACCEPTED","QUEST_TURNED_IN","PLAYER_ENTERING_WORLD","GROUP_ROSTER_UPDATE"}) do
    events:RegisterEvent(event)
end
events:SetScript("OnEvent", function() Choice.at = nil end)
