local _, ns = ...
local tracking = RutaXPWorldMapTracking
local mapNamespace, groups, scheduled

local icons = {
    auctioneer = "Auctioneer", banker = "Banker", battlemaster = "BattleMaster",
    innkeeper = "Innkeeper", mailbox = "Mailbox", classTrainer = "Class",
    profTrainer = "Profession", repair = "Repair", stable = "StableMaster",
}

local function enter(pin)
    local row = pin.data
    GameTooltip:SetOwner(pin, "ANCHOR_RIGHT")
    GameTooltip:AddLine(row[5], 1, 0.82, 0)
    local info = tracking.Info(row[1])
    if info and info.name and info.name ~= row[5] then
        GameTooltip:AddLine(info.name, 1, 1, 1)
    end
    if row[7] and row[7] ~= "" then GameTooltip:AddLine(row[7], 0.85, 0.85, 0.85) end
    GameTooltip:Show()
end

local function worldPoint(stitch, mapID, row)
    local x, y = row[3] / 100, row[4] / 100
    if row[8] then
        local era = ns.worldMapServiceEra[mapID]
        if era then
            local north = era[2] + y * (era[4] - era[2])
            local west = era[3] + x * (era[5] - era[3])
            local u, v = stitch.FromYards(era[1], north, west)
            return u, v, era[1], north, west
        end
    else
        local left, right, top, bottom = stitch.Rect(mapID)
        if left then
            local u, v = left + x * (right - left), top + y * (bottom - top)
            if row[9] and mapNamespace.Safe and C_Map and C_Map.GetWorldPosFromMapPos then
                local continent, pos = C_Map.GetWorldPosFromMapPos(mapID, CreateVector2D(x, y))
                if pos then return u, v, continent, mapNamespace.Safe.XY(pos) end
            end
            return u, v
        end
    end
end

local function index()
    local side = UnitFactionGroup("player")
    local _, class = UnitClass("player")
    if not class or (side ~= "Alliance" and side ~= "Horde") then return end
    local faction = side == "Horde" and "H" or "A"
    local result = {}
    for key in pairs(icons) do result[key] = {points = {}, next = 1, seen = {}} end
    for mapID, rows in pairs(ns.worldMapServiceData) do
        for _, row in ipairs(rows) do
            if (row[2] == faction or row[2] == "AH") and (not row[6] or row[6] == class) then
                local points = result[row[1]].points
                points[#points + 1] = {mapID, row}
            end
        end
    end
    return result
end

local function add(stitch, group, point)
    local mapID, row = point[1], point[2]
    local u, v, continent, north, west = worldPoint(stitch, mapID, row)
    if not u or not v then return end
    -- Each map rounds its own percentages. A city and its parent zone can
    -- report the same NPC several yards apart. Keep different NPCs distinct.
    local id = row[9] or string.format("%s/%.5f/%.5f", row[5], u, v)
    local places = group.seen[id]
    if not places then places = {}; group.seen[id] = places end
    for _, p in ipairs(places) do
        if p.u == u and p.v == v then return end
        if p.map ~= mapID and p.continent == continent and north and west and p.north and p.west
            and (north - p.north)^2 + (west - p.west)^2 <= 15^2 then return end
    end
    places[#places + 1] = {map = mapID, u = u, v = v, continent = continent, north = north, west = west}
    local pin = stitch.AddPin(group.set, u, v, group.look, row)
    pin:SetScript("OnEnter", enter)
    pin:SetScript("OnLeave", GameTooltip_Hide)
end

local function showing()
    if WorldMapFrame and WorldMapFrame:IsShown() then return true end
    local mod = mapNamespace:GetModule("worldmap")
    return mod.PadViewOn and mod.PadViewOn()
end

-- The first visit can enable hundreds of services. Spread button creation
-- over frames. OpenMap culls pins against the viewport as the map is panned.
local function build()
    scheduled = false
    if not showing() then return end
    local stitch = mapNamespace.MapStitch
    local remaining = 32
    for _, group in pairs(groups) do
        while group.enabled and group.next <= #group.points do
            add(stitch, group, group.points[group.next])
            group.next = group.next + 1
            remaining = remaining - 1
            if remaining == 0 then
                scheduled = true
                C_Timer.After(0, build)
                return
            end
        end
    end
end

function tracking.Refresh(openMap)
    mapNamespace = openMap
    local stitch = openMap.MapStitch
    if not stitch.IsBuilt() or not showing() then return end
    groups = groups or index()
    if not groups then return end
    for key, group in pairs(groups) do
        local info = tracking.Info(key)
        group.enabled = info and info.active or false
        if group.enabled then
            group.set = group.set or stitch.PinSet("rutaxp_service_" .. key, 1, 3)
            local fallback = "Interface\\Minimap\\Tracking\\" .. icons[key]
            local texture = info.texture or fallback
            if not group.look or group.look.texture ~= texture then
                if group.look then
                    stitch.ClearPinSet(group.set)
                    group.next, group.seen = 1, {}
                end
                group.look = {texture = texture, fallback = fallback, size = 16}
            end
        end
        if group.set and group.set.on ~= group.enabled then stitch.SetPinSetOn(group.set, group.enabled) end
    end
    if not scheduled then build() end
end

function tracking.OnChanged()
    if mapNamespace and showing() then mapNamespace:GetModule("worldmap"):Refresh() end
end
