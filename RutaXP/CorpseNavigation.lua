local _, ns = ...

-- The client's corpse pin and a route objective are independent destinations.
-- Keep death coordinates in memory for this death only.
local diedAt, corpse, lookupMap, retryAt

local function known(v)
    return not (issecretvalue and issecretvalue(v))
end

local function call(api, ...)
    if type(api) == "function" then
        local ok, a, b = pcall(api, ...)
        if ok and known(a) and known(b) then return a, b end
    end
end

local function point(map, pos, y)
    local x = pos
    if type(pos) == "table" or type(pos) == "userdata" then
        if type(pos.GetXY) == "function" then x, y = call(pos.GetXY, pos)
        else x, y = pos.x, pos.y end
    end
    if known(x) and known(y) and type(x) == "number" and type(y) == "number"
        and x >= 0 and x <= 1 and y >= 0 and y <= 1 and (x ~= 0 or y ~= 0) then
        return {mapID=map, x=x, y=y, source="corpse"}
    end
end

local function playerMap()
    return call(C_Map and C_Map.GetBestMapForUnit, "player")
end

-- Movement as a ghost is never evidence of a completed visit or landing.
function ns:IsRecoveringCorpse()
    return call(UnitIsDeadOrGhost, "player") or call(UnitIsGhost, "player") or false
end

local function findCorpse(map)
    -- A cemetery can be across a zone boundary. Blizzard can still supply
    -- the body on their common parent map.
    for _ = 1, 5 do
        if not known(map) or type(map) ~= "number" or map <= 0 then break end
        local location = point(map, call(C_DeathInfo and C_DeathInfo.GetCorpseMapPosition, map))
        if location then return location end
        local info = call(C_Map and C_Map.GetMapInfo, map)
        if type(info) ~= "table" or not known(info.parentMapID) or info.parentMapID == map then break end
        map = info.parentMapID
    end
end

function ns:GetDeathNavigation()
    if not call(UnitIsGhost, "player") then
        if call(UnitIsDeadOrGhost, "player") then
            return nil, "Libera el espíritu para volver a tu cadáver"
        end
        return
    end
    local map, now = playerMap(), call(GetTime) or 0
    if map and (lookupMap ~= map or not retryAt or (not corpse and now >= retryAt)) then
        lookupMap, retryAt = map, now + 1
        corpse = findCorpse(map) or corpse
    end
    local target = corpse or diedAt
    return target, target and "Tu cadáver" or "Esperando la ubicación de tu cadáver"
end

local events = CreateFrame("Frame")
for _, name in ipairs({"PLAYER_DEAD", "PLAYER_ALIVE", "PLAYER_UNGHOST", "PLAYER_ENTERING_WORLD", "ZONE_CHANGED_NEW_AREA"}) do
    events:RegisterEvent(name)
end
events:SetScript("OnEvent", function(_, event)
    lookupMap, retryAt = nil, nil
    if event == "PLAYER_DEAD" then
        local map = playerMap()
        corpse, diedAt = nil, nil
        if type(map) == "number" and map > 0 then
            diedAt = point(map, call(C_Map.GetPlayerMapPosition, map, "player"))
        end
        if ns.Walking then ns.Walking:Clear() end
    elseif event == "PLAYER_UNGHOST" or
        (event == "PLAYER_ALIVE" and not call(UnitIsGhost, "player") and not call(UnitIsDeadOrGhost, "player")) then
        corpse, diedAt = nil, nil
    end
end)
