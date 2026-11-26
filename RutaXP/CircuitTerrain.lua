local _, ns = ...
local Terrain = {}
ns.CircuitTerrain = Terrain

-- One optional stop at a time. Keep the ordinary guide and its arrow active
-- while Shortest Path Forever prices the three legs on its walking mesh.
local current
local function finite(n)
    return not (issecretvalue and issecretvalue(n)) and type(n) == "number" and n == n and math.abs(n) < math.huge
end

local function samePlace(a, b, radius)
    return a and b and (a.x-b.x)^2 + (a.y-b.y)^2 <= radius^2
        and (not a.z or not b.z or math.abs(a.z-b.z) <= 15)
end

local function worldPoint(point, continent)
    local map, x, y = ns:GetWaypointWorldPosition(point)
    if map == continent and finite(x) and finite(y) then
        return {x=x, y=y, z=finite(point.z) and point.z or nil}
    end
end

local function forget()
    local previous = current
    current = nil
    if previous and previous.job then previous.engine.Cancel(previous.job) end
end

local function finish(request, extra)
    if current ~= request or request.extra ~= nil then return end
    request.job, request.extra = nil, extra
    if ns.LocalCircuit then ns.LocalCircuit:Invalidate() end
    if ns.TravelChoice then ns.TravelChoice.at = nil end
    -- Refresh outside the path callback. Its queue may still be unwinding.
    if ns.RefreshUI and C_Timer and C_Timer.After then
        C_Timer.After(0, function() if current == request and ns.char then ns:RefreshUI() end end)
    end
end

local function measure(request)
    local engine, map = request.engine, request.map
    local function secondLeg(costs)
        if current ~= request or request.extra ~= nil then return end
        if type(costs) ~= "table" or not finite(costs[1]) or not finite(costs[2]) then
            finish(request, math.huge)
            return
        end
        local ok, job = pcall(engine.FindCost, map, request.stop, request.anchor, function(cost)
            finish(request, finite(cost) and costs[1] + cost - costs[2] or math.huge)
        end, false)
        if not ok then finish(request, math.huge)
        elseif request.extra == nil then request.job = job end
    end
    local ok, job = pcall(engine.FindMany, map, request.start, {request.stop, request.anchor}, secondLeg, false)
    if not ok then finish(request, math.huge)
    elseif request.extra == nil and not request.job then request.job = job end
    if request.extra == nil and C_Timer and C_Timer.After then
        C_Timer.After(16, function()
            if current == request and request.extra == nil then
                if request.job then engine.Cancel(request.job) end
                finish(request, math.huge)
            end
        end)
    end
end

function Terrain:Check(key, stopPoint, anchorPoint, allowance)
    local engine = RutaXPPathEngine
    if not key or not stopPoint or not anchorPoint or not engine or not engine.FindMany
        or not engine.FindCost or not engine.Cancel or not engine.Available then return end
    local map, px, py, zone = ns:GetPlayerWorldPosition()
    if not finite(map) or not finite(px) or not finite(py) or stopPoint.mapID ~= zone
        or anchorPoint.mapID ~= zone or not engine.Available(map) then return end
    local start = {x=px, y=py}
    if UnitPosition then
        local x,y,z,instance = UnitPosition("player")
        if finite(instance) and instance ~= map then return end
        if finite(x) and finite(y) and instance == map then
            local native = {x=x,y=y,z=finite(z) and z ~= 0 and z or nil}
            if not samePlace(start, native, 100) then return end
            start = native
        end
    end
    local stop, anchor = worldPoint(stopPoint, map), worldPoint(anchorPoint, map)
    if not stop or not anchor then return end
    if current and current.key == key and current.map == map and samePlace(current.start,start,100)
        and samePlace(current.stop,stop,8) and samePlace(current.anchor,anchor,8) then
        if current.extra ~= nil then return current.extra <= (allowance or 140) end
        return
    end
    forget()
    if ns.Walking and ns.Walking.pending then return end
    local request = {key=key, map=map, engine=engine, start=start, stop=stop, anchor=anchor}
    current = request
    measure(request)
    if request.extra ~= nil then return request.extra <= (allowance or 140) end
end

local events = CreateFrame("Frame")
for _, event in ipairs({"PLAYER_LEAVING_WORLD", "ZONE_CHANGED_NEW_AREA", "PLAYER_DEAD", "PLAYER_REGEN_DISABLED"}) do
    events:RegisterEvent(event)
end
events:SetScript("OnEvent", forget)
