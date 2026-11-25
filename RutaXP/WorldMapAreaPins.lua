local tracking = RutaXPWorldMapTracking

local nativeTemplates = {
    QuestOfferPinTemplate = true,
    StorylineQuestPinTemplate = true,
    DungeonEntrancePinTemplate = true,
}
local stitchedSets = {"questoffers", "dungeons", "boats", "zeppelins"}
local hiddenNative = setmetatable({}, {__mode = "k"})
local hiddenStitched = setmetatable({}, {__mode = "k"})
local nativeHooked = setmetatable({}, {__mode = "k"})
local stitchedHooked = setmetatable({}, {__mode = "k"})

local function readable(value)
    if not (issecretvalue and issecretvalue(value)) then return value end
end

local function showInArea(pin, inArea, hidden, identity)
    if inArea then
        if hidden[pin] == identity then pin:Show() end
        hidden[pin] = nil
    elseif pin:IsShown() then
        hidden[pin] = identity
        pin:Hide()
    end
end

local function filterNative(map, scope)
    if not map:IsShown() or not map.EnumeratePinsByTemplate then return end
    if scope == nil and not next(hiddenNative) then return end
    local mapID = map:GetMapID()
    if not mapID then return end
    local tracked = C_SuperTrack and C_SuperTrack.GetSuperTrackedQuestID
        and readable(C_SuperTrack.GetSuperTrackedQuestID())
    for template in pairs(nativeTemplates) do
        for pin in map:EnumeratePinsByTemplate(template) do
            local x, y
            if pin.GetPosition then x, y = pin:GetPosition() end
            x, y = readable(x), readable(y)
            local quest = readable(pin.questID)
            local poi = readable(pin.poiInfo)
            local id = quest or (poi and readable(poi.areaPoiID))
            -- A reused pin from another provider or map cannot inherit visibility.
            local identity = table.concat({template, mapID, id or "", x or "", y or ""}, "/")
            local inArea = (tracked and tracked ~= 0 and quest == tracked)
                or tracking.IsPositionInArea(mapID, x, y, scope)
            showInArea(pin, inArea, hiddenNative, identity)
        end
    end
end

local function stitchedRect(stitch, scope)
    if scope and stitch.Rect then
        local left, right, top, bottom = stitch.Rect(scope)
        if left and right and top and bottom then return {left, right, top, bottom} end
    end
end

local function filterStitchedPin(pin, set, scope, rect)
    local inArea = scope == nil or (rect and pin.u and pin.v
        and pin.u >= rect[1] and pin.u <= rect[2] and pin.v >= rect[3] and pin.v <= rect[4])
    showInArea(pin, inArea, hiddenStitched, set)
end

function tracking.FilterAreaPins(map, openMap)
    local scope = tracking.GetAreaScope()
    if not nativeHooked[map] and hooksecurefunc and map.AcquirePin and C_Timer and C_Timer.After then
        nativeHooked[map] = true
        local pending
        hooksecurefunc(map, "AcquirePin", function(_, template)
            if pending or not nativeTemplates[template] or tracking.GetAreaScope() == nil then return end
            pending = true
            C_Timer.After(0, function()
                pending = nil
                filterNative(map, tracking.GetAreaScope())
            end)
        end)
    end
    filterNative(map, scope)

    local stitch = openMap and openMap.MapStitch
    if not stitch or not stitch.GetPinSet then return end
    if not stitchedHooked[stitch] and hooksecurefunc and stitch.AddPin then
        stitchedHooked[stitch] = true
        hooksecurefunc(stitch, "AddPin", function(set)
            local pin = set and set.pins and set.pins[#set.pins]
            if not pin then return end
            local liveScope = tracking.GetAreaScope()
            -- OpenMap calls Show when checking out a pin from its pool.
            hiddenStitched[pin] = nil
            if liveScope == nil then return end
            for _, key in ipairs(stitchedSets) do
                if set == stitch.GetPinSet(key) then
                    filterStitchedPin(pin, set, liveScope, stitchedRect(stitch, liveScope))
                    return
                end
            end
        end)
    end
    if scope == nil and not next(hiddenStitched) then return end
    local rect = stitchedRect(stitch, scope)
    for _, key in ipairs(stitchedSets) do
        local set = stitch.GetPinSet(key)
        if set then
            for _, pin in ipairs(set.pins) do filterStitchedPin(pin, set, scope, rect) end
        end
    end
end
