local _, ns = ...
local tracking = RutaXPWorldMapTracking
local mapNamespace, groups, scheduled
local layoutDirty, lastWorldScale = true, nil
local PIN_SIZE, SPACING = 18, 20
tracking.ServicePinSize = PIN_SIZE

-- Keep each town service readable in screen units. Nearby providers of the
-- same service share a tooltip. Different services keep their native icons.
local order = {flight=0, innkeeper=1, mailbox=2, repair=3, banker=4, auctioneer=5,
    classTrainer=6, profTrainer=7, stable=8, battlemaster=9}
local offsets = {{0, 0}}
for radius = 1, 3 do
    for y = -radius, radius do
        for x = -radius, radius do
            if math.max(math.abs(x), math.abs(y)) == radius then
                offsets[#offsets+1] = {x*SPACING, y*SPACING}
            end
        end
    end
end
table.sort(offsets, function(a, b)
    local da, db = a[1]^2 + a[2]^2, b[1]^2 + b[2]^2
    if da ~= db then return da < db end
    if a[2] ~= b[2] then return a[2] < b[2] end
    return a[1] < b[1]
end)

local function remember(grid, x, y, entry)
    local col, row = math.floor(x/SPACING), math.floor(y/SPACING)
    grid[col] = grid[col] or {}
    local cell = grid[col][row] or {}
    grid[col][row] = cell
    cell[#cell+1] = {x=x, y=y, entry=entry}
end

local function neighbour(grid, x, y, distance, key)
    local col, row = math.floor(x/SPACING), math.floor(y/SPACING)
    for i = col-1, col+1 do
        local column = grid[i]
        if column then
            for j = row-1, row+1 do
                local cell = column[j]
                if cell then
                    for _, other in ipairs(cell) do
                        if (not key or key == other.entry.key) and
                            math.abs(x-other.x) < distance and math.abs(y-other.y) < distance then
                            return other.entry
                        end
                    end
                end
            end
        end
    end
end

function tracking.PlaceServices(entries)
    table.sort(entries, function(a,b)
        if a.key ~= b.key then return order[a.key] < order[b.key] end
        if a.x ~= b.x then return a.x < b.x end
        if a.y ~= b.y then return a.y < b.y end
        return (a.name or "") < (b.name or "")
    end)
    local sites, occupied = {}, {}
    for _, entry in ipairs(entries) do
        local x, y = entry.x, entry.y
        if entry.key == "flight" then
            remember(occupied, x, y, entry)
            entry.dx, entry.dy = 0, 0
        else
            local same = neighbour(sites, x, y, PIN_SIZE, entry.key)
            if same then
                same.members = same.members or {}
                same.members[#same.members+1] = entry
            else
                remember(sites, x, y, entry)
                for _, offset in ipairs(offsets) do
                    if not neighbour(occupied, x+offset[1], y+offset[2], PIN_SIZE) then
                        entry.dx, entry.dy = offset[1], offset[2]
                        break
                    end
                end
                entry.dx, entry.dy = entry.dx or 0, entry.dy or 0
                remember(occupied, x+entry.dx, y+entry.dy, entry)
            end
        end
    end
end

function tracking.ServiceMembersTooltip(pin)
    if not pin.serviceMembers then return end
    local function line(name, detail)
        return detail and detail ~= "" and (name .. " · " .. detail) or name
    end
    local own = line(pin.name or pin.data[5], pin.detail or (pin.data and pin.data[7]))
    local printed = {[own]=true}
    for _, member in ipairs(pin.serviceMembers) do
        local label = line(member.name, member.detail)
        if not printed[label] then
            GameTooltip:AddLine(label, 0.9, 0.9, 0.9)
            printed[label] = true
        end
    end
end

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
    tracking.ServiceMembersTooltip(pin)
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
            if not u and C_Map and C_Map.GetMapPosFromWorldPos and CreateVector2D then
                -- The continent may be unavailable during prebuild. The zone
                -- itself can still project a known world position onto its art.
                local ok, liveMap, pos = pcall(C_Map.GetMapPosFromWorldPos, era[1], CreateVector2D(north, west), mapID)
                if ok and liveMap == mapID and pos then
                    local l, r, t, b = stitch.Rect(mapID)
                    if l then
                        local zoneX, zoneY = pos:GetXY()
                        u, v = l + zoneX*(r-l), t + zoneY*(b-t)
                    end
                end
            end
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
    layoutDirty = true
end

local function showing()
    if WorldMapFrame and WorldMapFrame:IsShown() then return true end
    local mod = mapNamespace:GetModule("worldmap")
    return mod.PadViewOn and mod.PadViewOn()
end

function tracking.LayoutStitched()
    if not groups or not showing() then return end
    local stitch = mapNamespace.MapStitch
    local root = stitch.Root and stitch.Root()
    if not root then return end
    local width, height = stitch.Size()
    local frame
    for _, group in pairs(groups) do
        if group.enabled and group.set then frame = group.set.frame; break end
    end
    if not frame or not width or not height then return end
    local scale = root:GetEffectiveScale() / (frame:GetEffectiveScale() * (stitch.iconScale or 1))
    if scale <= 0 or (not layoutDirty and lastWorldScale == scale) then return end
    lastWorldScale, layoutDirty = scale, false
    width, height = width*scale, height*scale
    local entries = {}
    local flight = stitch.GetPinSet("flight")
    if flight and flight.frame:IsShown() then
        for _, pin in ipairs(flight.pins) do
            if pin:IsShown() then entries[#entries+1] = {key="flight", x=pin.u*width, y=pin.v*height} end
        end
    end
    for key, group in pairs(groups) do
        if group.enabled then
            for _, pin in ipairs(group.set.pins) do
                entries[#entries+1] = {pin=pin, key=key, x=pin.u*width, y=pin.v*height,
                    name=pin.data[5], detail=pin.data[7]}
            end
        end
    end
    tracking.PlaceServices(entries)
    for _, entry in ipairs(entries) do
        local pin = entry.pin
        if pin then
            pin.serviceMembers = entry.members
            pin:SetShown(entry.dx ~= nil)
            if entry.dx then
                pin:ClearAllPoints()
                pin:SetPoint("CENTER", pin.anchor, "TOPLEFT", entry.dx, -entry.dy)
            end
        end
    end
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
    tracking.LayoutStitched()
end

function tracking.Refresh(openMap)
    if mapNamespace ~= openMap then groups, layoutDirty, lastWorldScale = nil, true, nil end
    mapNamespace = openMap
    local stitch = openMap.MapStitch
    if not stitch.IsBuilt() or not showing() then return end
    groups = groups or index()
    if not groups then return end
    for key, group in pairs(groups) do
        local info = tracking.Info(key)
        local enabled = info and info.active or false
        if enabled ~= group.enabled then layoutDirty = true end
        group.enabled = enabled
        if group.enabled then
            group.set = group.set or stitch.PinSet("rutaxp_service_" .. key, 1, 5)
            local fallback = "Interface\\Minimap\\Tracking\\" .. icons[key]
            local texture = info.texture or fallback
            if not group.look or group.look.texture ~= texture then
                if group.look then
                    stitch.ClearPinSet(group.set)
                    group.next, group.seen = 1, {}
                end
                group.look = {texture = texture, fallback = fallback, size = PIN_SIZE}
            end
        end
        if group.set and group.set.on ~= group.enabled then stitch.SetPinSetOn(group.set, group.enabled) end
    end
    if not scheduled then build() end
end

function tracking.OnChanged()
    layoutDirty = true
    if mapNamespace and showing() then mapNamespace:GetModule("worldmap"):Refresh() end
end
