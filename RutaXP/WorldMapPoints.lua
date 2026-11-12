local _, ns = ...

-- Atlas names from Forever's map legend. The numeric fallbacks are Blizzard
-- tracking textures for clients that don't list a particular minimap filter.
local categories = {
    {key="turnin", label="Entregas de la guía", legend="TurnInQuest", atlas="UI-QuestPoi-QuestBangTurnIn", back="UI-QuestPoi-QuestNumber"},
    {key="accept", label="Misiones para aceptar", legend="LocalStoryQuest", atlas="QuestNormal"},
    {key="objective", label="Objetivos de la guía", legend="InProgressQuest", atlas="Quest-In-Progress-Icon-yellow", back="UI-QuestPoi-QuestNumber"},
    {key="flight", label="Maestros de vuelo", legend="FlightMaster", atlas="FlightPath"},
    {key="inn", label="Posadas", tracking="Innkeeper", texture=136458},
    {key="trainer", label="Instructores de tu clase", tracking="TrainerClass", texture=136455},
    {key="repair", label="Reparaciones", tracking="Repair", texture=136465},
    {key="bank", label="Bancos", tracking="Banker", texture=136453},
    {key="auction", label="Casas de subastas", tracking="Auctioneer", texture=136452},
    {key="mailbox", label="Buzones", tracking="Mailbox", texture=136459},
    {key="vendor", label="Otros vendedores", texture=132060, defaultOff=true},
}
local byKey = {}
for order, category in ipairs(categories) do
    category.order = order
    byKey[category.key] = category
end
-- A destination explicitly requested with «Mapa» is independent of POI filters.
byKey.destination = {label="Destino de RutaXP", atlas="Waypoint-MapPin-Untracked", order=0}

local map, provider, queued, disabledFlightProvider, destination
local frames, used = {}, 0

local function enabled(key)
    local saved = ns.char and ns.char.mapPointFilters
    if type(saved) == "table" and type(saved[key]) == "boolean" then return saved[key] end
    return not byKey[key].defaultOff
end

local function toggle(key)
    if not ns.char then return end
    local value = not enabled(key)
    if type(ns.char.mapPointFilters) ~= "table" then ns.char.mapPointFilters = {} end
    ns.char.mapPointFilters[key] = value
    ns:RefreshMapPoints()
end

local function drawMenu(_, root)
    local menu = root:CreateButton("Puntos de interés de RutaXP")
    for _, category in ipairs(categories) do
        menu:CreateCheckbox(category.label, enabled, toggle, category.key)
    end
    -- Forever includes the dungeon entrance provider but omits its checkbox.
    -- Let that provider draw the real, clickable entrance when data exists.
    if C_CVar and C_CVar.GetCVar and C_CVar.SetCVar and DungeonEntranceDataProviderMixin
        and C_CVar.GetCVar("showDungeonEntrancesOnMap") ~= nil then
        local function showing() return C_CVar.GetCVar("showDungeonEntrancesOnMap") == "1" end
        menu:CreateCheckbox("Entradas de mazmorras", showing, function()
            C_CVar.SetCVar("showDungeonEntrancesOnMap", showing() and "0" or "1")
        end)
    end
end

local function trackingTextures()
    local textures = {}
    if C_Minimap and C_Minimap.GetTrackingFilter and C_Minimap.GetTrackingInfo and C_Minimap.GetNumTrackingTypes then
        for i = 1, C_Minimap.GetNumTrackingTypes() do
            local filter = C_Minimap.GetTrackingFilter(i)
            local info = C_Minimap.GetTrackingInfo(i)
            if filter and filter.filterID and info and info.texture and info.texture ~= 0 then
                textures[filter.filterID] = info.texture
            end
        end
    end
    return textures
end

local function tooltip(frame)
    if not (GameTooltip and frame.points) then return end
    GameTooltip:SetOwner(frame, "ANCHOR_RIGHT")
    for i, point in ipairs(frame.points) do
        if i == 1 then GameTooltip:SetText(point.name) else GameTooltip:AddLine(point.name, 1, .82, 0, true) end
        local label = byKey[point.category].label
        GameTooltip:AddLine(point.detail and (label .. " · " .. point.detail) or label, 1, 1, 1, true)
    end
    GameTooltip:Show()
end

local function hideTooltip(frame)
    if GameTooltip and GameTooltip:IsOwned(frame) then GameTooltip:Hide() end
end

local function newFrame(canvas)
    local frame = CreateFrame("Frame", nil, canvas)
    frame.background = frame:CreateTexture(nil, "BACKGROUND")
    frame.background:SetAllPoints()
    frame.icon = frame:CreateTexture(nil, "ARTWORK")
    frame.icon:SetAllPoints()
    frame:SetMouseClickEnabled(false)
    frame:SetMouseMotionEnabled(true)
    frame:SetScript("OnEnter", tooltip)
    frame:SetScript("OnLeave", hideTooltip)
    return frame
end

local function setIcon(frame, point, textures)
    local category = byKey[point.category]
    local focused = point.category == "destination"
    local size = focused and 30 or 20
    frame:SetSize(size, size)
    local levels = map.GetPinFrameLevelsManager and map:GetPinFrameLevelsManager()
    if levels then
        local layer = focused and "PIN_FRAME_LEVEL_WAYPOINT_LOCATION" or "PIN_FRAME_LEVEL_FLIGHT_POINT"
        frame:SetFrameLevel(levels:GetValidFrameLevel(layer, 1))
    end
    local definition = category.legend and MapLegendPinDefinitions and MapLegendPinDefinitions[category.legend]
    local atlas = definition and definition.Atlas or category.atlas
    local back = definition and definition.BackgroundAtlas or category.back
    if back then frame.background:SetAtlas(back) end
    frame.background:SetShown(back ~= nil)
    if atlas then
        frame.icon:SetAtlas(atlas)
    else
        local filter = point.tracking or category.tracking
        local id = filter and Enum and Enum.MinimapTrackingFilter and Enum.MinimapTrackingFilter[filter]
        frame.icon:SetTexture(textures[id] or category.texture)
        frame.icon:SetTexCoord(0, 1, 0, 1)
    end
end

local function positionFrames()
    local canvas = map:GetCanvas()
    local scale = map.GetCanvasScale and map:GetCanvasScale() or 1
    if scale <= 0 then return end
    local width, height = canvas:GetWidth(), canvas:GetHeight()
    for i = 1, used do
        local frame = frames[i]
        local point = frame.points[1]
        frame:SetScale(1 / scale)
        frame:ClearAllPoints()
        frame:SetPoint("CENTER", canvas, "TOPLEFT", point.x * width * scale, -point.y * height * scale)
    end
end

local function usable(value)
    return not (issecretvalue and issecretvalue(value)) and type(value) == "number" and value >= 0 and value <= 1
end

-- Compare visible native pins after Blizzard has refreshed its providers.
-- Keep a second objective of the same quest if it lies elsewhere on the map.
local function nativePositions()
    local result = {}
    if not map.EnumeratePinsByTemplate then return result end
    for _, template in ipairs({"QuestOfferPinTemplate", "QuestPinTemplate", "FlightPointPinTemplate"}) do
        for pin in map:EnumeratePinsByTemplate(template) do
            if pin:IsShown() then
                local x, y = pin:GetPosition()
                local key = template == "FlightPointPinTemplate" and "flight" or pin.questID
                if not (issecretvalue and issecretvalue(key)) and key and usable(x) and usable(y) then
                    local list = result[key] or {}
                    list[#list+1] = {x=x, y=y}
                    result[key] = list
                end
            end
        end
    end
    return result
end

local function covered(point, native)
    local list = native[point.questID or point.category]
    for _, other in ipairs(list or {}) do
        if math.abs(other.x - point.x) < .006 and math.abs(other.y - point.y) < .006 then return true end
    end
    return false
end

local function clearFrom(first)
    for i = first, used do
        local frame = frames[i]
        hideTooltip(frame)
        frame:Hide()
        frame.points = nil
    end
    used = first - 1
end

-- Flights may also be supplied by the map itself. Toggle that layer through
-- the canvas lifecycle so its original clickable pins return when selected.
local function applyFlightFilter()
    if not (map.dataProviders and map.RemoveDataProvider and FlightPointDataProviderMixin) then return end
    if enabled("flight") then
        if disabledFlightProvider then
            local original = disabledFlightProvider
            disabledFlightProvider = nil
            map:AddDataProvider(original)
            original:OnShow()
            original:RefreshAllData()
        end
    elseif not disabledFlightProvider then
        for dataProvider in pairs(map.dataProviders) do
            if dataProvider.RefreshAllData == FlightPointDataProviderMixin.RefreshAllData then
                dataProvider:OnHide()
                map:RemoveDataProvider(dataProvider)
                disabledFlightProvider = dataProvider
                break
            end
        end
    end
end

local function render()
    queued = false
    if not map:IsShown() or not ns.char then return end
    local mapID = map:GetMapID()
    if not mapID then clearFrom(1); return end
    applyFlightFilter()
    local native, groups, sites = nativePositions(), {}, {}
    local function addPoint(point)
        local key = math.floor(point.x * 1000 + .5) .. "/" .. math.floor(point.y * 1000 + .5)
        local group = sites[key]
        if not group then
            group = {}
            sites[key] = group
            groups[#groups+1] = group
        end
        group[#group+1] = point
    end
    local function include(points)
        for _, point in ipairs(points) do
            if byKey[point.category] and enabled(point.category) and usable(point.x) and usable(point.y)
                and not covered(point, native) then
                addPoint(point)
            end
        end
    end
    if destination and destination.mapID == mapID then addPoint(destination) end
    include(ns:GetMapServicePoints(mapID))
    if enabled("accept") or enabled("turnin") or enabled("objective") then include(ns:GetMapQuestPoints(mapID)) end
    local textures, canvas = trackingTextures(), map:GetCanvas()
    for i, group in ipairs(groups) do
        table.sort(group, function(a, b)
            if a.category ~= b.category then return byKey[a.category].order < byKey[b.category].order end
            return a.name < b.name
        end)
        local frame = frames[i] or newFrame(canvas)
        frames[i], frame.points = frame, group
        setIcon(frame, group[1], textures)
        frame:Show()
        if GameTooltip and GameTooltip:IsOwned(frame) then tooltip(frame) end
    end
    clearFrom(#groups + 1)
    positionFrames()
end

function ns:RefreshMapPoints()
    if not map or not map:IsShown() or queued then return end
    queued = true
    if C_Timer and C_Timer.After then C_Timer.After(0, render) else render() end
end

function ns:InitializeMapPoints()
    if provider then return end
    local host = WorldMapFrame
    if not (host and host.AddDataProvider and host.GetCanvas and host.GetMapID and MapCanvasDataProviderMixin
        and CreateFromMixins and Menu and Menu.ModifyMenu) then return end
    map = host
    provider = CreateFromMixins(MapCanvasDataProviderMixin)
    function provider:RemoveAllData() clearFrom(1) end
    function provider:OnMapChanged()
        self:RemoveAllData()
        ns:RefreshMapPoints()
    end
    function provider:RefreshAllData() ns:RefreshMapPoints() end
    provider.OnShow = provider.RefreshAllData
    function provider:OnHide()
        destination = nil
        self:RemoveAllData()
    end
    provider.OnCanvasScaleChanged = positionFrames
    provider.OnCanvasSizeChanged = positionFrames
    Menu.ModifyMenu("MENU_WORLD_MAP_TRACKING", drawMenu)
    map:AddDataProvider(provider)
    ns:RefreshMapPoints()
end

function ns:ClearMapDestination()
    if destination then
        destination = nil
        self:RefreshMapPoints()
    end
end

function ns:ShowMapDestination(point, label)
    if type(point) ~= "table" or not usable(point.x) or not usable(point.y)
        or type(point.mapID) ~= "number" or (issecretvalue and issecretvalue(point.mapID))
        or not (point.mapID > 0 and point.mapID < math.huge) then return false end
    if not OpenWorldMap and C_AddOns and C_AddOns.LoadAddOn then
        pcall(C_AddOns.LoadAddOn, "Blizzard_WorldMap")
    end
    self:InitializeMapPoints()
    if not provider or not OpenWorldMap or not self.char then return false end
    -- OpenWorldMap respects game restrictions and selects the map after OnShow.
    -- It has no return value, so verify the visible map before reporting success.
    local opened = pcall(OpenWorldMap, point.mapID)
    if not opened or not map:IsShown() or map:GetMapID() ~= point.mapID then
        self:ClearMapDestination()
        return false
    end
    destination = {category="destination", name=label or "Destino de la guía", mapID=point.mapID, x=point.x, y=point.y}
    render()
    return true
end

local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_LOGIN")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("TAXI_NODE_STATUS_CHANGED")
events:RegisterEvent("MINIMAP_UPDATE_TRACKING")
events:RegisterEvent("QUESTLINE_UPDATE")
events:RegisterEvent("QUEST_POI_UPDATE")
events:RegisterEvent("QUEST_WATCH_LIST_CHANGED")
events:RegisterEvent("CVAR_UPDATE")
events:SetScript("OnEvent", function(_, event, addon)
    if event == "PLAYER_LOGIN" or (event == "ADDON_LOADED" and addon == "Blizzard_WorldMap") then
        ns:InitializeMapPoints()
    elseif event ~= "ADDON_LOADED" then
        ns:RefreshMapPoints()
    end
end)
