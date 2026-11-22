local _, ns = ...
local tracking = RutaXPWorldMapTracking
local map, provider, pending, callbackAPI
local pins, used = {}, 0
local hiddenFlights = setmetatable({}, {__mode = "k"})
local continentMaps = {[0] = 1415, [1] = 1414}
local fallback = {
    auctioneer="Auctioneer", banker="Banker", battlemaster="BattleMaster", innkeeper="Innkeeper",
    mailbox="Mailbox", classTrainer="Class", profTrainer="Profession", repair="Repair",
    stable="StableMaster", flight="FlightMaster",
}

local function xy(point)
    if point then
        if point.GetXY then return point:GetXY() end
        return point.x, point.y
    end
end

local function bounds(id, cache)
    if cache[id] == nil then
        local area
        if C_Map.GetWorldPosFromMapPos and CreateVector2D then
            local c, topLeft = C_Map.GetWorldPosFromMapPos(id, CreateVector2D(0, 0))
            local c2, bottomRight = C_Map.GetWorldPosFromMapPos(id, CreateVector2D(1, 1))
            local n, w = xy(topLeft)
            local s, e = xy(bottomRight)
            if c and c == c2 and n and w and s and e and w ~= e and n ~= s then area = {c,n,w,s,e} end
        end
        cache[id] = area or false
    end
    return cache[id]
end

local function fraction(area, c, n, w)
    if area and area[1] == c then
        return (w - area[3]) / (area[5] - area[3]), (n - area[2]) / (area[4] - area[2])
    end
end

-- GetMapRectOnMap also works on Azeroth, where a single set of world-yard
-- bounds cannot represent both continents. Cache rectangles for this draw.
local function project(view, source, x, y, c, n, w)
    local areas = view.areas
    if c then
        if source == view.id or view.global then
            local area = bounds(source, areas)
            local fx, fy = fraction(area, c, n, w)
            x, y = fx or x, fy or y
        elseif view.area then
            return fraction(view.area, c, n, w)
        end
    end
    if source == view.id then return x, y end
    if not x then return end
    local rect = view.rects[source]
    if rect == nil then
        local l, r, t, b
        if C_Map.GetMapRectOnMap then l, r, t, b = C_Map.GetMapRectOnMap(source, view.id) end
        rect = (l and r and t and b and r > l and b > t) and {l,r,t,b} or false
        view.rects[source] = rect
    end
    if rect then return rect[1] + x*(rect[2]-rect[1]), rect[3] + y*(rect[4]-rect[3]) end
    if not view.global then
        local area = bounds(source, areas)
        if area then
            return fraction(view.area, area[1], area[2]+y*(area[4]-area[2]), area[3]+x*(area[5]-area[3]))
        end
    end
end

local function enter(pin)
    GameTooltip:SetOwner(pin, "ANCHOR_RIGHT")
    GameTooltip:AddLine(pin.name, 1, 0.82, 0)
    if pin.label and pin.label ~= pin.name then GameTooltip:AddLine(pin.label, 1, 1, 1) end
    if pin.detail then GameTooltip:AddLine(pin.detail, 0.85, 0.85, 0.85) end
    tracking.ServiceMembersTooltip(pin)
    GameTooltip:Show()
end

local function add(view, key, info, name, detail, x, y)
    if not x or not y or x < 0 or x > 1 or y < 0 or y > 1 then return end
    used = used + 1
    local pin = pins[used]
    if not pin then
        pin = CreateFrame("Button", nil, map:GetCanvas())
        pin:SetSize(tracking.ServicePinSize, tracking.ServicePinSize)
        pin:SetMouseClickEnabled(false)
        pin:SetMouseMotionEnabled(true)
        pin.icon = pin:CreateTexture(nil, "ARTWORK")
        pin.icon:SetAllPoints()
        pin:SetScript("OnEnter", enter)
        pin:SetScript("OnLeave", GameTooltip_Hide)
        pins[used] = pin
    end
    pin.x, pin.y, pin.key = x, y, key
    pin.name, pin.label, pin.detail = name, info.name, detail
    pin:SetFrameLevel(view.level)
    local fallbackTexture = "Interface\\Minimap\\Tracking\\" .. fallback[key]
    if pin.icon:SetTexture(info.texture or fallbackTexture) == false then pin.icon:SetTexture(fallbackTexture) end
    pin:Show()
end

local function layout()
    if used == 0 then return end
    local canvas = map:GetCanvas()
    local width, height = canvas:GetWidth(), canvas:GetHeight()
    local scale = map:GetCanvasScale() or 1
    if scale <= 0 or width <= 0 or height <= 0 then return end
    local entries = {}
    if map.EnumeratePinsByTemplate then
        for flight in map:EnumeratePinsByTemplate("FlightPointPinTemplate") do
            if flight:IsShown() and flight.GetPosition then
                local x, y = flight:GetPosition()
                if x and y then entries[#entries+1] = {key="flight", x=x*width*scale, y=y*height*scale} end
            end
        end
    end
    for i = 1, used do
        local pin = pins[i]
        entries[#entries+1] = {pin=pin, key=pin.key, x=pin.x*width*scale, y=pin.y*height*scale,
            name=pin.name, detail=pin.detail}
    end
    tracking.PlaceServices(entries)
    for _, entry in ipairs(entries) do
        local pin = entry.pin
        if pin then
            pin.serviceMembers = entry.members
            pin:SetShown(entry.dx ~= nil)
            if entry.dx then
                pin:SetScale(1 / scale)
                pin:ClearAllPoints()
                pin:SetPoint("CENTER", canvas, "TOPLEFT", entry.x+entry.dx, -(entry.y+entry.dy))
            end
        end
    end
end

local function hideFrom(first)
    for i = first, #pins do pins[i]:Hide() end
end

local function services(view, faction, class)
    local seen = {}
    for source, rows in pairs(ns.worldMapServiceData) do
        for _, row in ipairs(rows) do
            local info = tracking.Info(row[1])
            if info and info.active and (row[2] == faction or row[2] == "AH")
                and (not row[6] or row[6] == class) then
                local x, y = row[3]/100, row[4]/100
                local era = row[8] and ns.worldMapServiceEra[source]
                local area = era or bounds(source, view.areas)
                local c, n, w
                if area then c, n, w = area[1], area[2]+y*(area[4]-area[2]), area[3]+x*(area[5]-area[3]) end
                x, y = project(view, source, x, y, c, n, w)
                if x and y and x >= 0 and x <= 1 and y >= 0 and y <= 1 then
                    -- Some cities and their parent zones both list the same NPC.
                    local id = row[1] .. "/" .. (row[9] or row[5])
                    local sites, duplicate = seen[id], false
                    if not sites then sites = {}; seen[id] = sites end
                    for _, p in ipairs(sites) do
                        if (x == p.x and y == p.y) or (p.map ~= source and n and p.n and p.c == c and
                            (n-p.n)^2+(w-p.w)^2 <= 225) then duplicate = true; break end
                    end
                    if not duplicate then
                        sites[#sites+1] = {map=source, c=c, n=n, w=w, x=x, y=y}
                        add(view, row[1], info, row[5], row[7], x, y)
                    end
                end
            end
        end
    end
end

local function nativeFlights(enabled)
    local shown = {}
    if map.EnumeratePinsByTemplate then
        for pin in map:EnumeratePinsByTemplate("FlightPointPinTemplate") do
            local poi = pin.poiInfo
            if poi and poi.nodeID then
                if enabled == false and pin:IsShown() then
                    pin:Hide()
                    hiddenFlights[pin] = poi.nodeID
                elseif enabled ~= false and hiddenFlights[pin] == poi.nodeID then pin:Show() end
                if enabled ~= false then hiddenFlights[pin] = nil end
                if pin:IsShown() then shown[poi.nodeID] = true end
            end
        end
    end
    return shown
end

local function flights(view, openMap, side, class)
    local info = tracking.Info("flight")
    local occupied = nativeFlights(info and info.active)
    if not info or not info.active then return end
    local factions = Enum and Enum.FlightPathFaction
    local opposite = factions and (side == "Alliance" and factions.Horde or factions.Alliance)
    if C_TaxiMap and C_TaxiMap.GetTaxiNodesForMap then
        local function read(source)
            for _, node in ipairs(C_TaxiMap.GetTaxiNodesForMap(source) or {}) do
                if node.nodeID and not occupied[node.nodeID] and (not opposite or node.faction ~= opposite) then
                    local x, y = xy(node.position)
                    if x and y then
                        x, y = project(view, source, x, y)
                        if x and y and x >= 0 and x <= 1 and y >= 0 and y <= 1 then
                            add(view, "flight", info, node.name, nil, x, y)
                            occupied[node.nodeID] = true
                        end
                    end
                end
            end
        end
        read(view.id)
        for _, id in pairs(continentMaps) do if id ~= view.id then read(id) end end
    end
    local factionBit = side == "Horde" and 2 or 1
    for id, node in pairs(openMap and openMap.MapFlights and openMap.MapFlights.nodes or {}) do
        if not occupied[id] and (node[5] == factionBit or node[5] == 3) and (not node[6] or node[6] == class) then
            local source = continentMaps[node[2]]
            if source then
                local x, y = project(view, source, nil, nil, node[2], node[3], node[4])
                add(view, "flight", info, node[1], nil, x, y)
            end
        end
    end
end

local external, externalOffersDirty, hookedModule = nil, true, nil
local function syncExternal(openMap, mod)
    local stitch = openMap.MapStitch
    if not stitch.IsBuilt() then return end
    if hookedModule ~= mod and hooksecurefunc then
        hookedModule = mod
        -- OpenMap also refreshes these after its options or Questie data change.
        for _, method in ipairs({"RefreshTownsfolk", "RefreshFlightsFound"}) do
            if mod[method] then hooksecurefunc(mod, method, tracking.RefreshNative) end
        end
    end
    tracking.Refresh(openMap)
    -- Route-clickable flight pins belong to OpenMap. Keep them with their
    -- tooltips while applying the game's tracking icon and selected state.
    for key in pairs(fallback) do
        local info = tracking.Info(key)
        local set = stitch.GetPinSet(key == "flight" and "flight" or "tf_" .. key)
        if set and info then
            if key == "flight" then
                local visible = info.active and not stitch.WorldPinsHidden("flight")
                set.frame:SetShown(visible)
                if visible then
                    for _, pin in ipairs(set.pins) do
                        if not pin:IsShown() then pin:Show() end
                        if info.texture and pin.trackingTexture ~= info.texture then
                            stitch.Look(pin.Icon, {texture=info.texture})
                            stitch.Look(pin.Highlight, {texture=info.texture})
                            if pin.shadow then stitch.Look(pin.shadow, {texture=info.texture}); pin.shadow:SetVertexColor(0,0,0) end
                            pin.trackingTexture = info.texture
                        end
                    end
                end
            elseif set.on then stitch.SetPinSetOn(set, false) end
        end
    end
    if externalOffersDirty and tracking.RefreshQuestOffers then
        externalOffersDirty = false
        local function maps()
            local ids = {}
            for _, zone in ipairs(C_Map.GetMapChildrenInfo(stitch.WORLD, Enum.UIMapType.Zone, true) or {}) do
                if stitch.Rect(zone.mapID) then ids[#ids+1] = zone.mapID end
            end
            return ids
        end
        local function offer(pin)
            GameTooltip:SetOwner(pin, "ANCHOR_RIGHT")
            GameTooltip:SetText(pin.data.name or "?", 1, 0.82, 0)
            if pin.data.line then GameTooltip:AddLine(pin.data.line) end
            GameTooltip:Show()
        end
        tracking.RefreshQuestOffers(openMap, mod, map, maps, offer)
    end
end

local function render()
    pending = false
    used = 0
    local id = map and map:IsShown() and map:GetMapID()
    if not id then hideFrom(1); return end
    local embedded = ns.GetEmbeddedModule and ns.GetEmbeddedModule("OpenMap")
    local openMap = embedded or _G.OpenMap
    local mod = openMap and openMap.GetModule and openMap:GetModule("worldmap")
    if mod and mod.IsStitched and mod.IsStitched() then
        hideFrom(1)
        local tracked = tracking.Get("flight")
        -- OpenMap owns the interactive flight markers on its stitched canvas.
        -- Some host maps independently create a second, native flight pin.
        nativeFlights(tracked and not openMap.MapFlights)
        if openMap.MapStitch then
            if embedded then
                -- OpenMap can finish building before M opens. Its townsfolk
                -- refresh deliberately defers service creation while hidden.
                tracking.Refresh(openMap)
            else
                external = openMap
                syncExternal(openMap, mod)
            end
        end
        return
    end
    external, externalOffersDirty = nil, true
    local side = UnitFactionGroup("player")
    local _, class = UnitClass("player")
    local mapInfo = C_Map.GetMapInfo(id)
    local types = Enum and Enum.UIMapType
    if not mapInfo or (side ~= "Alliance" and side ~= "Horde") or not class or
        (types and (mapInfo.mapType == types.Dungeon or mapInfo.mapType == types.Orphan)) then
        hideFrom(1)
        return
    end
    local levels = map.GetPinFrameLevelsManager and map:GetPinFrameLevelsManager()
    local level = levels and levels:GetValidFrameLevel("PIN_FRAME_LEVEL_AREA_POI", 1)
    local view = {id=id, areas={}, rects={}, level=level or map:GetCanvas():GetFrameLevel()+12,
        global=types and (mapInfo.mapType == types.World or mapInfo.mapType == types.Cosmic)}
    if not view.global then view.area = bounds(id, view.areas) end
    services(view, side == "Alliance" and "A" or "H", class)
    flights(view, openMap, side, class)
    hideFrom(used+1)
    layout()
end

function tracking.RefreshNative()
    if not map or not map:IsShown() or pending then return end
    pending = true
    C_Timer.After(0, render)
end

local previousChanged = tracking.OnChanged
function tracking.OnChanged(...)
    if previousChanged then previousChanged(...) end
    externalOffersDirty = true
    tracking.RefreshNative()
end

local function attach()
    if not provider and WorldMapFrame and WorldMapFrame.AddDataProvider and MapCanvasDataProviderMixin then
        map = WorldMapFrame
        provider = CreateFromMixins(MapCanvasDataProviderMixin)
        function provider:RemoveAllData() used = 0; hideFrom(1) end
        function provider:OnMapChanged() self:RemoveAllData(); tracking.RefreshNative() end
        function provider:OnHide() self:RemoveAllData(); externalOffersDirty = true end
        provider.RefreshAllData = tracking.RefreshNative
        function provider:OnShow()
            tracking.Read()
            tracking.RefreshNative()
        end
        provider.OnCanvasScaleChanged = layout
        provider.OnCanvasSizeChanged = layout
        map:AddDataProvider(provider)
        tracking.RefreshNative()
    end
    if map then tracking.AttachFilterButton(map) end
    local api = _G.OpenMapAPI
    if api and api.RegisterCallback and callbackAPI ~= api then
        callbackAPI = api
        api.RegisterCallback(tracking, "OpenMap_StitchedChanged", function()
            externalOffersDirty = true
            tracking.RefreshNative()
        end)
        -- Stock OpenMap can change flight visibility when the zoom passes a
        -- threshold, without changing its host map or refreshing providers.
        api.RegisterCallback(tracking, "OpenMap_ViewChanged", function()
            if external then tracking.RefreshNative() end
            if tracking.LayoutStitched then tracking.LayoutStitched() end
        end)
    end
end

local events = CreateFrame("Frame")
for _, event in ipairs({"PLAYER_LOGIN", "ADDON_LOADED", "PLAYER_ENTERING_WORLD", "QUESTLINE_UPDATE",
    "QUEST_ACCEPTED", "QUEST_REMOVED", "QUEST_TURNED_IN", "PLAYER_LEVEL_UP", "TAXI_NODE_STATUS_CHANGED"}) do
    events:RegisterEvent(event)
end
events:SetScript("OnEvent", function(_, event, value)
    if event == "ADDON_LOADED" and value ~= "Blizzard_WorldMap" and value ~= "Blizzard_Menu"
        and value ~= "OpenMap" and value ~= "RutaXP" then return end
    if event == "PLAYER_LOGIN" or event == "PLAYER_ENTERING_WORLD" or event == "ADDON_LOADED" then
        attach()
        tracking.RefreshNative()
    elseif event == "TAXI_NODE_STATUS_CHANGED" then tracking.RefreshNative()
    elseif external then
        if tracking.QuestOfferEvent then tracking.QuestOfferEvent(event, value) end
        externalOffersDirty = true
        tracking.RefreshNative()
    end
end)
