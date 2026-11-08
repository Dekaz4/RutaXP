local _, ns = ...
local routing, routes = ns.TravelRouting, ns.GuideTravelRoutes
local DUN = "forever/alliance/dwarf-gnome/01-dun-morogh"
local WEST = "forever/alliance/02-westfall"
local incoming = {}
for source, route in pairs(routes) do
    local list = incoming[route.destination] or {}
    incoming[route.destination] = list
    list[#list + 1] = source
end
for _, list in pairs(incoming) do table.sort(list) end

local function itinerary(self, source)
    local route = routes[source]
    if route then
        for _, variant in ipairs(route.variants or {}) do
            if self:MatchesConditions(variant.only) then return variant end
        end
        return route
    end
end

function ns:RememberGuideTravel(source, dest)
    if source and routes[source] and routes[source].destination == dest then
        self.char.travelOrigins = self.char.travelOrigins or {}
        self.char.travelOrigins[dest] = source
    end
end

function ns:ResetGuideTravel(id)
    local trips = self.char.guideTrips
    if trips then
        trips[id] = nil
        for _, source in ipairs(incoming[id] or {}) do trips[source] = nil end
    end
    if id == DUN or id == WEST then self.char.westfallTravel = nil end
end

local function originFor(self, id)
    local char = self.char
    local origin = char.travelOrigins and char.travelOrigins[id]
    if origin and routes[origin] and routes[origin].destination == id then return origin end
    local fallback
    for _, source in ipairs(incoming[id] or {}) do
        local state, guide = char.progress[source], self.guides[source]
        if guide and type(state) == "table" and not state.review and (tonumber(state.cursor) or 1) > #guide.steps then
            if self:MatchesConditions(guide) and self:MatchesConditions(guide.only) then
                self:RememberGuideTravel(source, id)
                return source
            end
            fallback = fallback or source
        end
    end
    if fallback then self:RememberGuideTravel(fallback, id); return fallback end
    -- Preserve the existing trip in characters already on the 0.7.4 opener.
    if id == WEST and type(char.westfallTravel) == "table" then
        self:RememberGuideTravel(DUN, WEST)
        return DUN
    end
end

local function travelContext(self)
    local guide, _, state = self:GetCurrent()
    if not guide or state.review or guide.recovery or guide.temporary or
        (guide.faction and guide.faction ~= UnitFactionGroup("player")) then return end
    if state.cursor > #guide.steps then
        local route = routes[guide.id]
        local target = route and self.guides[route.destination]
        local dest = route and self.char.progress[route.destination]
        if target and self:MatchesConditions(target) and self:MatchesConditions(target.only) and (not dest or (type(dest) == "table"
            and not dest.review and (tonumber(dest.cursor) or 1) == 1)) then return guide.id, route.destination end
    elseif state.cursor == 1 then
        local source = originFor(self, guide.id)
        if source then return source, guide.id end
    end
end

local function signature(leg)
    return table.concat({leg.map, leg.f or "l", leg.x, leg.y}, ":")
end

local function savedTrip(self, source, journey)
    local char = self.char
    char.guideTrips = char.guideTrips or {}
    local saved = char.guideTrips[source]
    if not saved and routes[source].destination == WEST then
        saved = char.westfallTravel
        char.westfallTravel = nil
    end
    local endpoint = signature(journey.legs[#journey.legs])
    if type(saved) ~= "table" or (saved.endpoint and saved.endpoint ~= endpoint) then saved = {} end
    saved.endpoint = endpoint
    char.guideTrips[source] = saved
    return saved
end

local function waypoint(self, source, leg, hide)
    local point = not hide and leg.map and self:ResolveWaypointPoint(leg)
    if point then point.source, point.targetKey, point.label = "guide-travel", source .. ":" .. leg.id, leg.title end
    return point or nil
end

local function travelView(self, source, dest, journey, saved)
    local legs, duo = journey.legs, self.Duo
    local ctx = duo and duo:GetContext() or {}
    local settings = self.char.duo
    local together = ctx.sameParty and ctx.groupSize == 2 and settings and (settings.autoPair or (settings.enabled and settings.wait))
    local peerRoute = ctx.guideID and routes[ctx.guideID]
    if together and self.DuoAuto and self.DuoAuto.PersonalBranchReady and self.DuoAuto:PersonalBranchReady(source, dest, ctx) == false then
        return { title = "Espera a tu compañero", text = "Tu compañero está terminando su zona de inicio.", waiting = true }
    end
    if together and ctx.partnerHeaderFresh and not ctx.partnerReview and peerRoute and peerRoute.destination == dest
        and ctx.cursor and ctx.cursor <= #self.guides[ctx.guideID].steps then
        if self.char.activeGuide == ctx.guideID then return end -- The companion view shows the actual unfinished quest.
        if not saved.skipped then return {title = "Espera a tu compañero", text = "Tu compañero está terminando las misiones de la zona anterior.", waiting = true} end
    end
    local final = legs[#legs]
    local zone = routing.Zone()
    local sample = routing.Sample(zone)
    local atEnd = zone == final.map and not routing.OnTaxi() and routing.Near(final, sample)
    if atEnd then
        saved.ready, saved.reached, saved.leg = true, #legs, final.id
        saved.groundDetour, saved.transport = nil, nil
    end
    if saved.ready and together and not saved.localStart and not saved.skipped and saved.met ~= ctx.partnerName
        and zone and (zone ~= final.map or (sample and not atEnd)) then
        saved.ready, saved.reached, saved.index, saved.leg = nil, nil, nil, nil
    end
    if not saved.ready then
        if saved.skipped then return end
        if routing.OnTaxi() then return {id = "in-flight", title = "En vuelo", text = "Al aterrizar, sigue la flecha hasta la siguiente parada."} end
        local detour = self.GetGroundDetour and self:GetGroundDetour(source, legs, saved, zone, sample)
        if detour then return detour end
        local held = saved.checkpoint and legs[saved.checkpoint]
        if held and held.map == zone and routing.Near(held, sample) and together then
            local wait = duo:GetTravelWait(dest, source, saved.checkpoint, false, saved.endpoint)
            if wait then return {id = held.id, title = held.title, text = wait, waiting = true, index = saved.checkpoint, total = #legs} end
        else
            saved.checkpoint = nil
        end
        local cursor = saved.index
        if cursor and (not legs[cursor] or legs[cursor].id ~= saved.leg) then cursor = nil end
        if not cursor and saved.leg then
            for i, leg in ipairs(legs) do if leg.id == saved.leg then cursor = i; break end end
        end
        local index, near = routing.Locate(legs, zone, cursor, sample)
        if not index then
            local leg = zone and routing.Rejoin(legs, zone, sample, saved.reached)
            if leg then
                if leg.boundary and routing.Near(leg, sample) then saved.crossingText = leg.text end
                return { id = leg.id, title = leg.title, text = leg.text, point = waypoint(self, source, leg, routing.Near(leg, sample)) }
            end
            local prev = cursor and legs[cursor]
            local instruction = saved.crossingText or (prev and prev.boundary and prev.text)
            return { title = (prev and prev.boundary and prev.title) or final.title,
                text = instruction or ("Vuelve al exterior para retomar el viaje. " .. legs[1].text) }
        end
        saved.crossingText = nil
        local leg = legs[index]
        -- Only report checkpoints on the shared, authored itinerary. The
        -- rejoin search has no comparable leg indices between two players.
        saved.reached = near and index or index - 1
        if near and leg.transport then saved.transport = index end
        if saved.transport ~= index then saved.transport = nil end
        saved.leg, saved.index = leg.id, index
        if near and duo and duo.GetTravelWait then
            saved.checkpoint = index
            local wait = duo:GetTravelWait(dest, source, index, false, saved.endpoint)
            if wait then return {id = leg.id, title = leg.title, text = wait, waiting = true, index = index, total = #legs} end
        end
        if near and not leg.boundary and index < #legs and legs[index+1].map == zone then
            index = index + 1
            leg, near = legs[index], false
            saved.index, saved.leg = index, leg.id
        end
        local onFerry = saved.transport == index and not leg.taxiLanding and legs[index+1]
            and routing.BetweenStops(leg, legs[index+1], sample)
        if onFerry then saved.reached = index end
        return { id = leg.id, title = leg.title, text = leg.text, index = index, total = #legs,
            point = waypoint(self, source, leg, (leg.boundary and near) or onFerry),
            groundOption = self.CanGroundDetour and self:CanGroundDetour(leg, zone, sample) and {source = source, index = index, leg = leg.id} or nil }
    end
    if saved.skipped or saved.localStart then return end
    if atEnd and ctx.sameParty and ctx.groupSize == 2 and (ctx.enabled or (settings and settings.autoPair))
        and not ctx.partnerAutoCompatible and not duo:CanCommunicate() then
        return { title = final.title, waiting = true, localStart = true,
            text = "El juego impide sincronizar la llegada. Cuando estéis los dos aquí, pulsad «Empezar aquí» cada uno." }
    end
    if self.char.activeGuide == source then return end -- The negotiated handoff still owns this cursor.
    local wait = duo and duo.GetTravelWait and duo:GetTravelWait(dest, source, #legs, true, saved.endpoint)
    -- Once this pair has met, expiring network packets must not reopen the
    -- travel screen while they are doing the first quest.
    if ctx.partnerHeaderFresh and not wait and ctx.sameParty and settings and
        (settings.autoPair or (settings.enabled and settings.wait)) then saved.met = ctx.partnerName end
    if wait and (not saved.met or saved.met ~= ctx.partnerName) then
        return { title = final.title, waiting = true, text = wait }
    end
end

function ns:UpdateGuideTravel()
    local old = self.guideTravelView
    local source, dest = travelContext(self)
    local view
    if source then
        local journey = itinerary(self, source)
        view = travelView(self, source, dest, journey, savedTrip(self, source, journey))
        if view then
            view.source, view.destination = source, dest
            view.arrivalMap = journey.legs[#journey.legs].map
        end
    end
    self.guideTravelView = view
    if not old or not view then return old ~= view end
    return old.id ~= view.id or old.title ~= view.title or old.text ~= view.text or old.waiting ~= view.waiting
        or old.localStart ~= view.localStart or (old.point ~= nil) ~= (view.point ~= nil)
        or (old.groundOption ~= nil) ~= (view.groundOption ~= nil)
end

function ns:GetGuideTravel() return self.guideTravelView end

function ns:GetGuideTravelSignal()
    local source, dest = travelContext(self)
    local saved = source and self.char.guideTrips and self.char.guideTrips[source]
    if saved then return dest, saved.reached or 0, saved.ready == true, source, saved.endpoint end
end

function ns:IsTravelServiceComplete(guide, stepIndex, goalIndex)
    local source = guide and self.char.travelOrigins and self.char.travelOrigins[guide.id]
    local saved = source and self.char.guideTrips and self.char.guideTrips[source]
    if not saved or not saved.ready or not routes[source] or routes[source].destination ~= guide.id then return false end
    local journey = itinerary(self, source)
    local indices = journey and ((stepIndex == 1 and journey.arrivalGoals) or (journey.arrivalGoalsByStep and journey.arrivalGoalsByStep[stepIndex]))
    for _, i in ipairs(indices or {}) do if i == goalIndex then return true end end
    return false
end

function ns:SkipGuideTravel()
    local view = self:GetGuideTravel()
    local source = travelContext(self)
    if not view or view.waiting or not source then return false end
    self.char.guideTrips[source].skipped = true
    self:Sync()
    return true
end

function ns:StartTravelHere()
    self:UpdateGuideTravel()
    local view = self:GetGuideTravel()
    local source, dest = travelContext(self)
    if not source or not view or not view.localStart then return false end
    local successor = self.guides[dest]
    if self.char.activeGuide == source and self:GetLinkedGuide(self.guides[source]) ~= successor then return false end
    self.char.guideTrips[source].localStart = true
    if self.char.activeGuide == source then
        if self.DuoAuto then self.DuoAuto:ClearTravelAgreement() end
        self:ApplyGuideContinuation(successor)
    end
    self:Sync()
    return true
end
