local _, ns = ...

local DUN = "forever/alliance/dwarf-gnome/01-dun-morogh"
local WEST = "forever/alliance/02-westfall"
local TRAM = 369 -- Instance ID. The train has no usable outdoor waypoint.
local legs = ns.WestfallTravelLegs
local ranges, byID = {}, {}
for i, leg in ipairs(legs) do
    local zone = leg.map or leg.instanceID
    local range = ranges[zone] or { first = i }
    range.last, ranges[zone], byID[leg.id] = i, range, i
end

local function readable(v)
    if not (issecretvalue and issecretvalue(v)) then return v end
end

local function value(fn, index, ...)
    if type(fn) ~= "function" then return nil end
    local result = { pcall(fn, ...) }
    if not result[1] then return nil end
    return readable(result[index + 1]), readable(result[index + 2])
end

local function currentZone()
    if value(GetInstanceInfo, 8) == TRAM or value(UnitPosition, 4, "player") == TRAM then return TRAM end
    local zone = value(GetRealZoneText, 1) or value(GetZoneText, 1)
    local tramName = value(C_Map and C_Map.GetAreaInfo, 1, 2257)
    if zone and tramName and zone == tramName then return TRAM end
    if value(IsInInstance, 1) then return nil end
    local map = value(C_Map and C_Map.GetBestMapForUnit, 1, "player")
    for _ = 1, 6 do
        if not map or map == 0 then break end
        if map ~= TRAM and ranges[map] then return map end
        local info = value(C_Map.GetMapInfo, 1, map)
        map = info and info.parentMapID
    end
    if zone then
        for id in pairs(ranges) do
            if id ~= TRAM then
                local info = value(C_Map and C_Map.GetMapInfo, 1, id)
                if info and info.name == zone then return id end
            end
        end
    end
end

-- Compare positions in the same world frame. Classic percentages on their
-- own would turn a close approach on Forever into a missed waypoint.
local function playerOffset(map)
    local position = value(C_Map and C_Map.GetPlayerMapPosition, 1, map, "player")
    if not position then return end
    local continent, world = value(C_Map.GetWorldPosFromMapPos, 1, map, position)
    local bounds = ns.mapFrames and ns.mapFrames.era[map]
    if not world or not bounds or continent ~= bounds.c then return end
    local north, west = value(world.GetXY, 1, world)
    if type(north) ~= "number" or type(west) ~= "number" then return end
    return function(leg)
        local dn = bounds.top + (bounds.bottom - bounds.top) * leg.y / 100 - north
        local dw = bounds.left + (bounds.right - bounds.left) * leg.x / 100 - west
        return dn, dw, dn * dn + dw * dw
    end
end

local function locateLeg(range, saved, offset)
    local index = saved and saved >= range.first and saved <= range.last and saved or range.first
    if not offset then return index, false end
    -- Rejoin further down a known road after logging in, cutting a corner or
    -- taking a flight. Only project onto the actual road corridor.
    for i = range.last, index, -1 do
        local leg = legs[i]
        local north, west, distance2 = offset(leg)
        if distance2 <= leg.radius * leg.radius then
            if i == range.last then return i, true end
            return i + 1, false
        end
        if i > index then
            local prev = legs[i - 1]
            local pn, pw = offset(prev)
            local dn, dw = north - pn, west - pw
            local length2 = dn * dn + dw * dw
            if length2 > 0 then
                local t = -(pn * dn + pw * dw) / length2
                local n, w = pn + t * dn, pw + t * dw
                local corridor = math.max(prev.radius, leg.radius)
                if t > 0 and t < 1 and n * n + w * w <= corridor * corridor then return i, false end
            end
        end
    end
    return index, false
end

local function travelContext(self)
    local guide, _, state = self:GetCurrent()
    if not guide or state.review then return end
    if guide.id ~= DUN and guide.id ~= WEST then return end
    if UnitFactionGroup("player") ~= "Alliance" then return end
    if guide.id == WEST and state.cursor == 1 then return WEST end
    if guide.id == DUN and state.cursor > #guide.steps then
        local dest = self.char.progress[WEST]
        if not dest or (type(dest) == "table" and not dest.review and (tonumber(dest.cursor) or 1) == 1) then return DUN end
    end
end

local function travelView(self)
    local context = travelContext(self)
    if not context then return end
    local char = self.char
    local saved = type(char.westfallTravel) == "table" and char.westfallTravel or nil
    local ctx = self.Duo and self.Duo:GetContext() or {}
    if context == DUN and ctx.partnerAutoCompatible and ctx.guideID == DUN and ctx.cursor and ctx.cursor <= #self.guides[DUN].steps then
        return -- The partner still has quests here; show their existing step.
    end
    local zone = (not saved or not saved.ready) and currentZone()
    if not saved then
        -- Other starting zones can link to Westfall. Only take over those
        -- characters once they enter the supported corridor.
        local origin = char.progress[DUN]
        if context == WEST and not zone and not (type(origin) == "table"
            and (tonumber(origin.cursor) or 0) > #self.guides[DUN].steps) then return end
        saved = {}
        char.westfallTravel = saved
    end
    if not saved.ready then
        if saved.skipped and zone ~= legs[#legs].map then return end
        if not zone then
            return { title = "Viaje a Colina del Centinela",
                text = "El viaje continúa desde Forjaz o Ventormenta. Al entrar en el recorrido, la flecha te señalará el siguiente punto." }
        end
        local index, near = locateLeg(ranges[zone], byID[saved.leg], zone ~= TRAM and playerOffset(zone))
        local leg = legs[index]
        saved.leg = leg.id
        if index == #legs and near then
            saved.ready = true
        else
            if saved.skipped then return end
            local point
            if leg.map and not (leg.boundary and near) then point = self:ResolveWaypointPoint(leg) end
            if point then
                point.source, point.targetKey, point.label = "guide-travel", "westfall-travel:" .. leg.id, leg.title
            end
            return { title = leg.title, text = leg.text, id = leg.id, index = index, total = #legs, point = point }
        end
    end
    if saved.skipped then return end
    local duo = char.duo
    if saved.localStart then return end
    -- Party messages can be restricted in Forever. Only offer a personal
    -- start on the actual hill when no fresh party confirmation is available.
    if ctx.sameParty and ctx.groupSize == 2 and (ctx.enabled or (duo and duo.autoPair))
        and not ctx.partnerAutoCompatible and not self.Duo:CanCommunicate()
        and currentZone() == legs[#legs].map then
        local last = legs[#legs]
        local offset = playerOffset(last.map)
        if offset and select(3, offset(last)) <= last.radius * last.radius then
            return { title = "Colina del Centinela", waiting = true, localStart = true,
                text = "El juego impide sincronizar la llegada. Si estáis los dos en la colina, pulsad «Empezar aquí» cada uno." }
        end
    end
    if context == DUN then return end -- Normal handoff handles automatic or manual consent.
    local wait = ctx.sameParty and ctx.groupSize == 2 and type(duo) == "table" and (duo.autoPair or (duo.enabled and duo.wait))
    local peerOnTrip = ctx.guideID == WEST or (ctx.guideID == DUN and ctx.cursor and ctx.cursor > #self.guides[DUN].steps)
    if not wait then self.westfallArrivedWith = nil; return end
    if ctx.partnerAutoCompatible and peerOnTrip and (ctx.partnerAtWestfall or (ctx.guideID == WEST and ctx.cursor and ctx.cursor > 1)) then
        self.westfallArrivedWith = ctx.partnerName
    end
    if self.westfallArrivedWith ~= ctx.partnerName then
        return { title = "Colina del Centinela", waiting = true,
            text = "Ya estás en la colina. Esperando la confirmación de llegada de tu compañero." }
    end
end

function ns:UpdateGuideTravel()
    local old = self.guideTravelView
    local view = travelView(self)
    self.guideTravelView = view
    if not old or not view then return old ~= view end
    return old.id ~= view.id or old.title ~= view.title or old.waiting ~= view.waiting or old.localStart ~= view.localStart
        or (old.point ~= nil) ~= (view.point ~= nil)
end

function ns:GetGuideTravel()
    return self.guideTravelView
end

function ns:GetWestfallTravelSignal()
    if not travelContext(self) then return end
    local saved = self.char.westfallTravel
    if type(saved) == "table" then return saved.ready == true and 1 or 0 end
end

function ns:SkipGuideTravel()
    local view = self:GetGuideTravel()
    if not view or view.waiting then return false end
    self.char.westfallTravel.skipped = true
    self:Sync()
    return true
end

function ns:StartTravelHere()
    self:UpdateGuideTravel()
    local view = self:GetGuideTravel()
    if not view or not view.localStart then return false end
    local successor = self.guides[WEST]
    if self.char.activeGuide == DUN and self:GetLinkedGuide(self.guides[DUN]) ~= successor then return false end
    self.char.westfallTravel.localStart = true
    if self.char.activeGuide == DUN then
        if self.DuoAuto then self.DuoAuto:ClearTravelAgreement() end
        self:ApplyGuideContinuation(successor)
    end
    self:Sync()
    return true
end
