local _, ns = ...
local R = ns.TravelRouting
local TRAM, TELDRASSIL, TREETOP = 369, 1438, "teldrassil-treetop"
local walkSpeed, flightSpeed = 7, 32
local localWalkingRange = 2500 -- Retain authored waypoints for nearby itineraries.
local cached, coordinates = {}, setmetatable({}, {__mode="k"})
local flightDistances = {}
local arrivals = {}
local estimates = {}

-- Keep physical connections separate from the directed services that this
-- character has actually been offered at a flight master.
local function networkFor(faction, party, zone)
    local roads = R.Network(faction)
    if not roads then return end
    local result = {}
    for node, exits in pairs(roads) do
        local list = {}
        for i, e in ipairs(exits) do list[i] = e end
        result[node] = list
    end
    local factionMask = faction == "Alliance" and 1 or 2
    local nodes = ns.GuideTaxiNodes or {}
    local function allowed(n) return n and (n.mask == 3 or n.mask == factionMask) end
    for origin, offers in pairs(ns.char and ns.char.observedTaxiRoutes or {}) do
        local from = nodes[origin]
        if allowed(from) and type(offers) == "table" then
            for destination, offered in pairs(offers) do
                local to = nodes[destination]
                if offered == true and allowed(to) and from.continent == to.continent and from.map ~= to.map
                    and (not party or ns.FlightNavigation:CanPlanConnection(origin, destination, party, from.map==zone)) then
                    local exits = result[from.map] or {}
                    exits[#exits+1] = {kind="flight", from=from, to=to, target=to.map,
                        id="flight-"..origin.."-"..destination}
                    result[from.map] = exits
                end
            end
        end
    end
    return result
end

local function world(p)
    if coordinates[p] then return unpack(coordinates[p]) end
    local c,n,w
    local era = ns.mapFrames and ns.mapFrames.era and ns.mapFrames.era[p.map]
    if p.f == "e" and era then
        c = era.c
        n = era.top + (era.bottom-era.top)*p.y/100
        w = era.left + (era.right-era.left)*p.x/100
    else
        local point = p.mapID and p or ns:ResolveWaypointPoint(p)
        if point and ns.GetWaypointWorldPosition then c,n,w = ns:GetWaypointWorldPosition(point) end
    end
    if c and n and w then coordinates[p]={c,n,w}; return c,n,w end
end

local function yards(a,b)
    local c,n,w = world(a)
    local c2,n2,w2 = world(b)
    if c and c == c2 then return math.sqrt((n-n2)^2+(w-w2)^2) end
end

local function flightDistance(e)
    local faction = UnitFactionGroup("player")
    local key=faction..":"..e.from.id
    local distances=flightDistances[key]
    if not distances then
        distances={[e.from.id]=0}
        local open={[e.from.id]=0}
        local paths,nodes=ns.GuideTaxiPaths or {},ns.GuideTaxiNodes or {}
        local mask=faction=="Alliance" and 1 or 2
        while next(open) do
            local closest,best
            for id,d in pairs(open) do if not best or d<best then closest,best=id,d end end
            open[closest]=nil
            for id,length in pairs(paths[closest] or {}) do
                local n=nodes[id]
                if n and (n.mask==3 or n.mask==mask) and best+length<(distances[id] or math.huge) then
                    distances[id],open[id]=best+length,best+length
                end
            end
        end
        flightDistances[key]=distances
    end
    return distances[e.to.id] or yards(e.from,e.to)
end

local function transferSeconds(e)
    if e.kind == "flight" then
        return 8 + (flightDistance(e) or 3200)/flightSpeed
    end
    return (e.duration or 3) + (e.wait or 0)/2
end

-- Search by arrival point, not only by zone. Two docks in the same zone
-- can be on opposite shores. Include the walk to the first stop and from
-- the last stop to the actual NPC. Transit timetable costs are estimates.
local function firstLeg(network,start,finish,sample,destination,departure)
    if not network then return end
    local pending, costs = {}, {}
    local best, answer, usesFlight = math.huge, nil, false
    local function push(e,seconds,first,flight)
        if seconds < best and seconds < (costs[e] or math.huge) then
            costs[e]=seconds
            pending[#pending+1]={edge=e,seconds=seconds,first=first or e,flight=flight or e.kind=="flight"}
        end
    end
    for _,e in ipairs(network[start] or {}) do
        if not departure or (e.kind == departure.kind and e.to.map == departure.destination
            and (yards(e.from,departure.departure) or math.huge) < 75) then
            local distance = sample and select(3,sample(e.from))
            local access = distance and distance < math.huge and math.sqrt(distance)/walkSpeed or 120
            push(e,access+transferSeconds(e))
        end
    end
    while #pending > 0 do
        local index=1
        for i=2,#pending do if pending[i].seconds < pending[index].seconds then index=i end end
        local job = pending[index]
        pending[index]=pending[#pending]; pending[#pending]=nil
        if job.seconds >= best then break end
        local e = job.edge
        if job.seconds == costs[e] then
            if e.target == finish then
                local total = job.seconds + (yards(e.to,destination) or 0)/walkSpeed
                if total < best then best,answer,usesFlight=total,job.first,job.flight end
            else
                for _,nextEdge in ipairs(network[e.target] or {}) do
                    local access = (yards(e.to,nextEdge.from) or 840)/walkSpeed
                    push(nextEdge,job.seconds+access+transferSeconds(nextEdge),job.first,job.flight)
                end
            end
        end
    end
    return answer,best,usesFlight
end

local function localChapterTrip(fixed,start,finish,here,destination)
    if not fixed or not fixed[start] or not fixed[finish] then return true end
    if destination.source=="itinerary" then
        local distance = yards(here,destination)
        if not distance or distance <= localWalkingRange then return true end
    end
    -- Adjacent zones can use their authored walk. Even a short trip across
    -- multiple zones needs each road entrance as a local destination.
    for _, e in ipairs(fixed[start]) do
        if e.kind == "road" and e.target == finish then return true end
    end
    return false
end

local function targetNode(zone, point)
    if zone ~= TELDRASSIL then return zone end
    -- Rut'theran is the small southern island. Compare in the documented
    -- Era rectangle even when the client uses a different display crop.
    local era = ns.mapFrames and ns.mapFrames.era[TELDRASSIL]
    local c,n,w = world(point)
    if era and c == era.c then
        local x,y = (w-era.left)/(era.right-era.left), (n-era.top)/(era.bottom-era.top)
        if x >= .51 and x <= .61 and y >= .865 then return TELDRASSIL end
        return TREETOP
    end
end

-- Same graph and units as the compass, from the current position to the
-- actual work site. A boat or tram remains available in the no-flight route.
function R.EstimateJourney(point, zone, party, channel, departure)
    if not point or not point.mapID or not zone then return end
    local sample = R.Sample(zone)
    local start, finish = R.CurrentNode(zone, sample), targetNode(R.KnownZone(point.mapID) or point.mapID, point)
    if not sample or not start or not finish or start == finish then return end
    local faction = UnitFactionGroup("player")
    local roads = R.Network(faction)
    if not roads then return end
    local time = GetTime and GetTime() or 0
    local here = ns:PlayerPoint()
    local revision = ns.FlightNavigation and ns.FlightNavigation.routeRevision or 0
    local peerRevision = party and ns.Duo.taxiRevision or 0
    local peer = party and (party.known and party.partnerHeaderFresh and party.partnerNonce or "?")
    channel = channel or "quest"
    local last = estimates[channel]
    local departureKey = departure and departure.key
    if last and last.owner==ns.char and last.start==start and last.map==point.mapID and last.x==point.x and last.y==point.y
        and last.revision==revision and last.peer==peer and last.peerRevision==peerRevision and last.departure==departureKey
        and here and last.here and time >= last.at and time-last.at<12 and (yards(here,last.here) or math.huge)<35 then
        return last.result
    end
    local edge, seconds, flight = firstLeg(networkFor(faction, party, zone),start,finish,sample,point,departure)
    if not edge then return end
    local ground = seconds
    if flight then
        local _, secondsWithoutFlights = firstLeg(roads,start,finish,sample,point,departure)
        ground = secondsWithoutFlights
    end
    local result = {seconds=seconds, entry=edge.from, usesFlight=flight, groundSeconds=ground and ground < math.huge and ground or nil}
    estimates[channel] = {owner=ns.char,start=start,map=point.mapID,x=point.x,y=point.y,departure=departureKey,
        revision=revision,peer=peer,peerRevision=peerRevision,here=here,at=time,result=result}
    return result
end

function R.AuthoredFlightSeconds(origin, landing, goal, zone)
    if not goal then return end
    local catalog = ns.GuideTaxiNodes or {}
    local from, to = catalog[origin], catalog[landing]
    local sample = from and from.map == zone and R.Sample(zone)
    local distance = sample and select(3,sample(from))
    local exit = to and yards(to,goal)
    if distance and distance < math.huge and exit and to.map == goal.mapID then
        return math.sqrt(distance)/walkSpeed + transferSeconds({kind="flight",from=from,to=to}) + exit/walkSpeed
    end
end

function R.DetourBeforeDeparture(point, entry)
    local here = ns:PlayerPoint()
    if not here or not point or not entry or point.mapID ~= here.mapID or entry.map ~= here.mapID then return end
    local a,b,c = yards(here,point),yards(point,entry),yards(here,entry)
    if a and b and c then return math.max(0, a+b-c)/walkSpeed end
end

local function mapName(map)
    local info = C_Map and C_Map.GetMapInfo and C_Map.GetMapInfo(map)
    return info and info.name or "la siguiente zona"
end

local function view(kind,state,short,text,point)
    return {kind=kind,state=state,title=short,shortText=short,text=text or short,point=point}
end

local function instruction(e,zone,at,saved)
    local name = e.to.name or mapName(e.to.map)
    local origin = e.from.name or mapName(e.from.map)
    if e.kind == "flight" then
        local title = (at and "Vuela a " or "Ve al maestro de vuelo de ") .. (at and name or origin)
        return title, "Habla con el maestro de vuelo en "..origin.." y elige «"..name.."» en el mapa de vuelos."
    elseif e.kind == "road" then
        return "Cruza hacia "..name, "Sigue el camino hasta el paso que comunica con "..name.."."
    elseif e.kind == "portal" then
        return "Atraviesa el portal a "..name, "En "..origin..", usa el portal hacia "..name.."."
    elseif e.kind == "tram" then
        return (at and "Toma el tranvía a " or "Ve al tranvía hacia ")..name, "Entra en la estación de "..origin.." y toma el tranvía a "..name.."."
    elseif e.kind == "zeppelin" then
        return (at and "Espera el zepelín a " or "Ve a la torre de ")..(at and name or origin),
            "Sube a la torre de "..origin..", toma el zepelín hacia "..name.." y baja al llegar."
    end
    if e.stop and zone == e.stop.map and saved then
        return "Quédate a bordo en "..e.stop.name, "Esta es la escala de "..e.stop.name..". Quédate en el mismo barco hasta "..name.."."
    end
    local text = "Embarca en "..origin.." hacia "..name.."."
    if e.stop then text = text.." Quédate a bordo en "..e.stop.name.."." end
    return (at and "Espera el barco a " or "Ve al muelle de ")..(at and name or origin), text.." Desembarca en "..name.."."
end

local function transport(e) return e.kind=="boat" or e.kind=="zeppelin" or e.kind=="tram" end

local function portKey(e)
    return e.id and e.id..":"..e.from.map
end

local function nearStop(p,sample,radius)
    return sample and select(3,sample(p)) <= radius^2
end

local function roadKey(e)
    return table.concat({e.from.map,e.from.x,e.from.y,e.to.map,e.to.x,e.to.y},":")
end

local function roadExitPoint(self,e,c,n,w)
    local map=e.from.map
    local point=self:WorldToWaypoint(c,n,w,map)
    if point and point.mapID==map then return point end
    -- Some clients answer the reverse lookup with the neighbouring zone
    -- despite the requested map. Its live rectangle may still contain the exit.
    local c1,top,left=self:GetWaypointWorldPosition({mapID=map,x=0,y=0})
    local c2,bottom,right=self:GetWaypointWorldPosition({mapID=map,x=1,y=1})
    if c1==c and c2==c and top~=bottom and left~=right then
        local x,y=(w-left)/(right-left),(n-top)/(bottom-top)
        if x>=0 and x<=1 and y>=0 and y<=1 then return {mapID=map,x=x,y=y} end
    end
    -- The adjacent exit is a verified point on this road and continent.
    return self:ResolveWaypointPoint(e.to)
end

local function crossingView(self,e,saved,sample)
    local c,n,w = world(e.from)
    local c2,n2,w2 = world(e.to)
    local point
    if c and c == c2 then
        local dn,dw = n2-n,w2-w
        local length = math.sqrt(dn*dn+dw*dw)
        if sample then
            local sn,sw = sample(e.from)
            if sn then
                -- sn/sw point from player to entry. Keep the exit while
                -- walking forward, even after leaving the entry's 30 yards.
                local along = length > 0 and -(sn*dn+sw*dw)/length or 0
                local sideways = length > 0 and math.abs(sn*dw-sw*dn)/length or math.sqrt(sn*sn+sw*sw)
                if along < -95 or sideways > 95 + math.min(length*.15,75) then return end
                local exitDistance = (sn+dn)^2+(sw+dw)^2
                if exitDistance <= 10^2 or along >= length then saved.atRoadExit = true
                elseif exitDistance > 30^2 and along < length-20 then saved.atRoadExit = nil end
            end
        end
        if not saved.atRoadExit then
            point = roadExitPoint(self,e,c,n2,w2)
        end
    elseif sample then
        local _,_,distance = sample(e.from)
        if distance < math.huge and distance > 95^2 then return end
    end
    local name = e.to.name or mapName(e.to.map)
    local title = "Cruza hacia "..name
    local text = "Sigue la carretera hacia "..name.." hasta que cambie la zona."
    if point then
        point.label,point.source = title,"destination-travel"
        point.targetKey = saved.key..":"..roadKey(e)..":exit"
    end
    return view("road","crossing",title,text,point)
end

local function startCrossing(self,e,saved,sample)
    saved.road, saved.atRoadExit = roadKey(e), nil
    return crossingView(self,e,saved,sample)
end

-- The map can change well out at sea. The landing, another known inland
-- crossing/flight master, or the quest location itself is positive evidence
-- that the player can continue on land after a missed sample or hearthstone.
local function onArrivalSide(edge,network,sample,destination)
    if not sample then return false end
    if nearStop(edge.to,sample,65) then return true end
    local zone=edge.to.map
    if destination.mapID==zone and nearStop({map=zone,x=destination.x*100,y=destination.y*100},sample,50) then return true end
    for _,exit in ipairs(network[edge.target] or {}) do
        if exit.kind=="road" and nearStop(exit.from,sample,60) then return true end
    end
    for _,node in pairs(ns.GuideTaxiNodes or {}) do
        if node.map==zone and nearStop(node,sample,55) then return true end
    end
    -- Hearthstoning to an inn can bypass the destination dock entirely.
    return IsResting and IsResting()==true
end

local function routeState(self, channel, key)
    if not self.char then return {key=key} end
    local trips=self.char.destinationTrips
    if type(trips) ~= "table" then trips={}; self.char.destinationTrips=trips end
    if type(trips[channel]) ~= "table" or trips[channel].key ~= key then trips[channel]={key=key} end
    return trips[channel]
end

-- Active channel and chapter channel may be sampled in the same frame by
-- the hidden native tracker and Journey. Each owns only its own passage.
function ns:RouteDestination(destination,key,channel)
    if not destination or not destination.mapID then return destination end
    channel = channel or "activity"
    local actual = C_Map and C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")
    local zone = R.Zone()
    local finish = R.KnownZone(destination.mapID) or destination.mapID
    local saved = routeState(self, channel, tostring(key or "")..":"..destination.mapID)
    local target = targetNode(finish,destination)
    local sample = zone and R.Sample(zone)
    local start = R.CurrentNode(zone,sample)
    local faction = UnitFactionGroup("player")
    local fixed = R.Network(faction)
    local now=GetTime and GetTime() or 0
    local held
    if saved.board and fixed then
        for _,e in ipairs(fixed[saved.origin] or {}) do
            if portKey(e)==saved.board then held=e; break end
        end
    end
    local notice=arrivals[channel]
    local arrival=notice and notice.owner==self.char and notice.key==saved.key and notice.map==zone
        and now>=notice.at and now-notice.at<8 and notice.text or nil
    if held then
        local name = held.to.name or mapName(held.to.map)
        if zone == held.to.map then
            if not onArrivalSide(held,fixed,sample,destination) then
                return nil,view(held.kind,"crossing","Espera a llegar a "..name,"Baja cuando el transporte llegue a "..name..".")
            end
            arrival = "Has llegado a "..name
            arrivals[channel]={owner=self.char,key=saved.key,map=zone,at=now,text=arrival}
            saved.board,saved.origin=nil,nil
        elseif zone == TRAM or not zone or zone == held.from.map or (held.stop and zone==held.stop.map) then
            local short,text = instruction(held,zone,true,true)
            if zone==TRAM then short,text="Sigue en el tranvía a "..name,"Baja en la estación de "..name.." y sal al exterior."
            elseif not zone then short,text="Continúa hacia "..name,"Permanece a bordo hasta llegar a "..name.."." end
            local stopover = held.stop and zone==held.stop.map
            -- Walking back into town or teleporting inland must release a
            -- stale boarding instruction. Near the vessel keep it stable.
            local pier = stopover and held.stop or held.from
            local inland = zone==pier.map and sample and select(3,sample(pier)) > 1100^2
            if not inland then
                return nil,view(held.kind,stopover and "stopover" or "boarding",short,text)
            end
            saved.board,saved.origin=nil,nil
        else saved.board,saved.origin=nil,nil end
    end
    if R.OnTaxi() then
        saved.road,saved.atRoadExit=nil,nil
        return nil,view("flight","flying","Espera a aterrizar", "Estás en vuelo. Al aterrizar se recalculará el siguiente tramo.")
    end
    if saved.road and zone then
        for _,e in ipairs(fixed and fixed[start] or {}) do
            if e.kind=="road" and roadKey(e)==saved.road then
                local crossing=crossingView(self,e,saved,sample)
                if crossing then return crossing.point,crossing end
                break
            end
        end
        saved.road,saved.atRoadExit=nil,nil
        cached[channel]=nil
    end
    if (actual==destination.mapID or zone==finish) and (zone~=TELDRASSIL or start==target) then
        saved.started=nil
        return destination,arrival and view("arrival","arrived",arrival,"Sigue la flecha hasta tu objetivo.",destination) or nil
    end
    local party = self.FlightNavigation and self.FlightNavigation:SharedTravelParty()
    if channel=="chapter" and not saved.started and zone and zone~=TRAM and start~=TREETOP and finish~=TELDRASSIL then
        local here=self.PlayerPoint and self:PlayerPoint()
        local c = here and world(here)
        local destC=world(destination)
        if c and destC and c==destC and localChapterTrip(fixed,start,target,here,destination) then
            -- Keep authored local walks, but hand off to the forward exit
            -- when that walk reaches the actual road into its next zone.
            for _,e in ipairs(fixed and fixed[start] or {}) do
                if e.kind=="road" and e.target==target and nearStop(e.from,sample,30) then
                    local crossing=startCrossing(self,e,saved,sample)
                    return crossing.point,crossing
                end
            end
            local shortcut
            -- Nearby final objectives still use the local road. Compare a distant
            -- quest across the border when this character has observed flights.
            if here and destination.source ~= "itinerary" and (yards(here,destination) or 0) >= localWalkingRange
                and self.char and type(self.char.observedTaxiRoutes) == "table" and next(self.char.observedTaxiRoutes) then
                local estimate = R.EstimateJourney(destination,zone,party,"chapter")
                shortcut = estimate and estimate.usesFlight and estimate.groundSeconds
                    and estimate.seconds + 60 < estimate.groundSeconds * .75
            end
            if not shortcut then return destination end
        end
    end
    saved.started=true
    if not zone or not target then
        return nil,view("travel","unknown","Espera a recuperar tu posición","Al volver al exterior, la flecha indicará la siguiente parada.")
    end
    if not start then
        return nil,view("travel","unknown","Ubica la salida de la zona","Acércate a un camino o un punto de transporte para retomar el recorrido.")
    end
    local c = cached[channel]
    local revision = self.FlightNavigation and self.FlightNavigation.routeRevision or 0
    local peerRevision = party and self.Duo.taxiRevision or 0
    local peer = party and (party.known and party.partnerHeaderFresh and party.partnerNonce or "?")
    if not c or c.owner~=self.char or c.key~=saved.key or c.start~=start or c.target~=target or c.revision~=revision
        or c.peer~=peer or c.peerRevision~=peerRevision
        or now-c.at >= 8 or now<c.at or c.x~=destination.x or c.y~=destination.y then
        local network=networkFor(faction,party,zone)
        local first
        if zone==TRAM and faction=="Alliance" then
            local best=math.huge
            for _,city in ipairs({1453,1455}) do
                local _,cost=firstLeg(network,city,target,nil,destination)
                if city==finish then cost=0 end
                if cost and cost < best then best,first=cost,{kind="tram",from={map=TRAM},to={map=city}} end
            end
        else first=firstLeg(network,start,target,sample,destination) end
        c={owner=self.char,key=saved.key,start=start,target=target,revision=revision,peer=peer,peerRevision=peerRevision,at=now,
            x=destination.x,y=destination.y,edge=first}
        cached[channel]=c
    end
    local e=c.edge
    if not e then
        return nil,view("travel","unavailable","Trayecto sin confirmar","No se conoce una conexión desde aquí hasta "..mapName(finish)..".")
    end
    if zone==TRAM then
        return nil,view("tram","boarding","Toma el tranvía a "..mapName(e.to.map),"Baja en "..mapName(e.to.map).." y sal por la estación.")
    end
    local at = R.Near({map=zone,x=e.from.x,y=e.from.y,f=e.from.f,radius=(e.kind=="flight" and 12 or 30)},sample)
    if at and e.kind=="road" then
        local crossing=startCrossing(self,e,saved,sample)
        return crossing.point,crossing
    end
    local title,text=instruction(e,zone,at)
    if arrival then text=arrival..". "..text end
    if at and transport(e) then saved.board,saved.origin=portKey(e),start end
    local point
    if not at then point=self:ResolveWaypointPoint(e.from) end
    if point then
        point.label,point.source=title,"destination-travel"
        point.targetKey=saved.key..":"..(e.kind=="road" and roadKey(e)..":entry" or portKey(e) or (e.from.map..":"..e.from.x..":"..e.from.y))
    end
    return point,view(e.kind,at and "boarding" or "approach",title,text,point)
end

function ns:GetDestinationTravelView()
    return self.destinationTravelView
end
