-- OpenMap draws its own map. Read the same selections and textures used by
-- Blizzard’s minimap menu, including when the player is in a different zone.
local _, ns = ...
local tracking = {}
RutaXPWorldMapTracking = tracking

local filters = {
    auctioneer = "Auctioneer",
    banker = "Banker",
    battlemaster = "Battlemaster",
    innkeeper = "Innkeeper",
    mailbox = "Mailbox",
    classTrainer = "TrainerClass",
    profTrainer = "TrainerProfession",
    repair = "Repair",
    stable = "Stablemaster",
    flight = "TaxiNode",
    lowLevelQuests = "TrivialQuests",
}

local snapshot, writingAll, filterButton, menuRefreshPending, lastAreaScope

local function onlyMyZone()
    return ns ~= nil and ns.char ~= nil and ns.char.mapOnlyMyZone == true
end

local function mapInfo(mapID)
    if type(mapID) == "number" and not (issecretvalue and issecretvalue(mapID))
        and mapID > 0 and C_Map and C_Map.GetMapInfo then
        return C_Map.GetMapInfo(mapID)
    end
end

-- Nil is the unfiltered map, false is an active filter awaiting a zone.
-- The character's area is independent of the map opened or panned to with M.
function tracking.GetAreaScope()
    if not onlyMyZone() then return nil end
    local types = Enum and Enum.UIMapType
    local mapID = C_Map and C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")
    for _ = 1, 16 do
        local info = mapInfo(mapID)
        if not info or not info.mapType or not types then break end
        if info.mapType == types.Zone or info.mapType == types.Dungeon then return mapID end
        if info.mapType ~= types.Micro then break end
        mapID = info.parentMapID
    end
    return false
end

function tracking.IsMapInArea(mapID, scope)
    if scope == nil then return true end
    if not scope then return false end
    for _ = 1, 16 do
        if mapID == scope then return true end
        local info = mapInfo(mapID)
        if not info then break end
        mapID = info.parentMapID
    end
    return false
end

local positionMap, positionBounds

function tracking.IsWorldPositionInArea(continent, north, west, scope)
    if scope == nil then return true end
    if not scope or not (continent and north and west and C_Map and C_Map.GetWorldPosFromMapPos and CreateVector2D) then return false end
    -- Flight masters may be reported on a continent map, so compare in the
    -- same world coordinates used when drawing them.
    if positionMap ~= scope or not positionBounds then
        positionMap, positionBounds = scope, nil
        local world, corner = C_Map.GetWorldPosFromMapPos(scope, CreateVector2D(0, 0))
        local otherWorld, opposite = C_Map.GetWorldPosFromMapPos(scope, CreateVector2D(1, 1))
        if world and world == otherWorld and corner and opposite then
            local n, w = corner:GetXY()
            local s, e = opposite:GetXY()
            if n ~= s and w ~= e then
                positionBounds = {world, math.min(n,s), math.max(n,s), math.min(w,e), math.max(w,e)}
            end
        end
    end
    local box = positionBounds
    return box ~= nil and box[1] == continent and north >= box[2] and north <= box[3] and west >= box[4] and west <= box[5]
end

function tracking.IsPositionInArea(mapID, x, y, scope)
    if tracking.IsMapInArea(mapID, scope) then return true end
    local types, info = Enum and Enum.UIMapType, mapInfo(mapID)
    if not (scope and info and types and (info.mapType == types.Continent or info.mapType == types.World)
        and x and y and C_Map.GetWorldPosFromMapPos and CreateVector2D) then return false end
    local world, point = C_Map.GetWorldPosFromMapPos(mapID, CreateVector2D(x, y))
    if not point then return false end
    local north, west = point:GetXY()
    return tracking.IsWorldPositionInArea(world, north, west, scope)
end

local function refreshArea()
    local scope = tracking.GetAreaScope()
    if scope == lastAreaScope then return end
    lastAreaScope = scope
    if tracking.OnChanged then tracking.OnChanged() end
end

local function setOnlyMyZone(enabled)
    if not (ns and ns.char) or enabled == onlyMyZone() then return end
    ns.char.mapOnlyMyZone = enabled or nil
    lastAreaScope = tracking.GetAreaScope()
    if tracking.OnChanged then tracking.OnChanged() end
end

local function toggleArea()
    setOnlyMyZone(not onlyMyZone())
    return MenuResponse.Refresh
end

function tracking.Read()
    local entries = {}
    local enum = Enum and Enum.MinimapTrackingFilter
    if enum and C_Minimap and C_Minimap.GetNumTrackingTypes
        and C_Minimap.GetTrackingFilter and C_Minimap.GetTrackingInfo then
        local byID = {}
        for key, field in pairs(filters) do
            if enum[field] then byID[enum[field]] = key end
        end
        for index = 1, C_Minimap.GetNumTrackingTypes() do
            local filter = C_Minimap.GetTrackingFilter(index)
            local key = filter and byID[filter.filterID]
            if key then
                local info = C_Minimap.GetTrackingInfo(index)
                if info and type(info.active) == "boolean" then
                    entries[key] = {active = info.active, name = info.name, texture = info.texture, index = index}
                end
            end
        end
    end
    snapshot = entries
    return entries
end

function tracking.Info(key)
    return (snapshot or tracking.Read())[key]
end

-- False means the player unchecked the filter. Nil means it is unavailable.
function tracking.Get(key)
    local entry = tracking.Info(key)
    if entry then return entry.active end
end

local function refresh()
    if writingAll then return end
    local previous = snapshot or {}
    local current = tracking.Read()
    for key in pairs(filters) do
        local old, new = previous[key], current[key]
        if (not old) ~= (not new) or (old and new and
            (old.active ~= new.active or old.name ~= new.name or old.texture ~= new.texture)) then
            if tracking.OnChanged then tracking.OnChanged() end
            if filterButton and filterButton:IsMenuOpen() and not menuRefreshPending then
                menuRefreshPending = true
                C_Timer.After(0, function()
                    menuRefreshPending = false
                    if filterButton:IsMenuOpen() then filterButton:GenerateMenu() end
                end)
            end
            return
        end
    end
end

local function clearFilters()
    refresh()
    -- SetTracking can synchronously fire MINIMAP_UPDATE_TRACKING. Apply the
    -- visible service/quest choices as one edit without touching tracking spells.
    writingAll = true
    local ok, err = pcall(function()
        for _, info in pairs(snapshot) do
            if info.active then C_Minimap.SetTracking(info.index, false) end
        end
    end)
    writingAll = false
    setOnlyMyZone(false)
    refresh()
    if not ok then error(err, 0) end
    return MenuResponse.Refresh
end

local function toggle(key)
    local active = tracking.Get(key)
    if active ~= nil then tracking.Set(key, not active) end
    return MenuResponse.Refresh
end

local function filterMenu(_, root)
    refresh()
    root:CreateButton(UNCHECK_ALL or "Desmarcar todo", clearFilters)
    root:CreateCheckbox("Solo mi zona", onlyMyZone, toggleArea)
    local choices = {}
    for key, info in pairs(snapshot) do choices[#choices+1] = {key=key, info=info} end
    table.sort(choices, function(a, b) return a.info.index < b.info.index end)
    if #choices == 0 then
        root:CreateTitle("El seguimiento aún no está disponible")
        return
    end
    for _, choice in ipairs(choices) do
        local info = choice.info
        local row = root:CreateCheckbox(info.name, tracking.Get, toggle, choice.key)
        if info.texture then
            row:AddInitializer(function(button)
                local icon = button:AttachTexture()
                icon:SetSize(18,18)
                icon:SetPoint("RIGHT")
                icon:SetTexture(info.texture)
                button.fontString:SetPoint("RIGHT", icon, "LEFT", -4, 0)
                return button.fontString:GetUnboundedStringWidth()+62, 20
            end)
        end
    end
end

function tracking.AttachFilterButton(map)
    if filterButton or not (map.ScrollContainer and MenuUtil and AnchorUtil) then return end
    local view = map.ScrollContainer
    filterButton = CreateFrame("DropdownButton", "RutaXPWorldMapFiltersButton", map, "UIPanelButtonTemplate")
    filterButton:SetSize(76, 22)
    filterButton:SetPoint("TOPRIGHT", view, "TOPRIGHT", -10, -6)
    filterButton:SetFrameLevel(math.min(view:GetFrameLevel()+9300, 9950))
    filterButton:SetText("Filtros")
    filterButton:SetMenuAnchor(AnchorUtil.CreateAnchor("TOPRIGHT", filterButton, "BOTTOMRIGHT", 0, -2))
    filterButton:SetupMenu(filterMenu)
    filterButton:HookScript("OnHide", function(self) self:CloseMenu() end)
end

-- Called only when the player changes a filter in OpenMap. Spell and service
-- tracking entries share the same list, whose indices can change on SPELLS_CHANGED.
function tracking.Set(key, enabled)
    if type(enabled) ~= "boolean" or not (C_Minimap and C_Minimap.SetTracking) then return false end
    refresh()
    local entry = snapshot[key]
    if not entry then return false end
    if entry.active ~= enabled then
        C_Minimap.SetTracking(entry.index, enabled)
        refresh()
    end
    return true
end

local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:RegisterEvent("ZONE_CHANGED")
events:RegisterEvent("ZONE_CHANGED_INDOORS")
events:RegisterEvent("ZONE_CHANGED_NEW_AREA")
events:RegisterEvent("SPELLS_CHANGED")
events:RegisterEvent("MINIMAP_UPDATE_TRACKING")
events:RegisterEvent("CVAR_UPDATE")
events:SetScript("OnEvent", function(_, event, cvar)
    if event:find("^ZONE_CHANGED") then refreshArea()
    elseif event ~= "CVAR_UPDATE" or cvar == "minimapTrackedInfov4" then
        refresh()
        if event == "PLAYER_ENTERING_WORLD" then refreshArea() end
    end
end)
