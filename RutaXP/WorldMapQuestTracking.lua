local tracking = RutaXPWorldMapTracking

-- Blizzard's quest offer provider uses isHidden and the TrivialQuests
-- tracking filter for these offers. The map API supplies the player's
-- available quests, including other zones, without scanning nearby NPCs.
function tracking.IsLowOffer(offer)
    return offer.isHidden or offer.isTrivial or
        (C_QuestLog and C_QuestLog.IsQuestTrivial and C_QuestLog.IsQuestTrivial(offer.questID))
end

local function available(q)
    if not q.questID or q.inProgress or q.isQuestStart == false or not tracking.IsLowOffer(q) then return false end
    if type(q.x) ~= "number" or type(q.y) ~= "number" or
        q.x <= 0 or q.x > 1 or q.y <= 0 or q.y > 1 then return false end
    local floor = Enum and Enum.QuestLineFloorLocation
    if q.floorLocation and q.floorLocation ~= (floor and floor.Same or 2) then return false end
    if C_QuestLog then
        if C_QuestLog.IsOnQuest and C_QuestLog.IsOnQuest(q.questID) then return false end
        if C_QuestLog.IsQuestFlaggedCompleted and C_QuestLog.IsQuestFlaggedCompleted(q.questID)
            and not (q.isDaily or q.isRepeatable or (C_QuestLog.IsRepeatableQuest and
            C_QuestLog.IsRepeatableQuest(q.questID))) then return false end
    end
    return true
end

-- An offer may appear on both a city's map and its surrounding zone.
local function mark(positions, id, u, v)
    if not u or not v then return end
    local points = positions[id]
    if not points then points = {}; positions[id] = points end
    for i = 1, #points, 2 do
        if math.abs(u - points[i]) < 0.0004 and math.abs(v - points[i+1]) < 0.0004 then return end
    end
    points[#points + 1] = u
    points[#points + 1] = v
    return true
end

-- OpenMap leaves Blizzard's real pins on its host map except in the
-- controller view. Reserve only offers that are actually visible there.
local function nativePins(map, mod)
    local positions = {}
    if not map or not map.EnumeratePinsByTemplate or (mod.PadViewOn and mod.PadViewOn()) then return positions end
    local host = map:GetMapID()
    if not host then return positions end
    for _, template in ipairs({"QuestOfferPinTemplate", "StorylineQuestPinTemplate"}) do
        for pin in map:EnumeratePinsByTemplate(template) do
            if pin.questID and pin.GetPosition and pin:IsShown() then
                local x, y = pin:GetPosition()
                if x and y then mark(positions, pin.questID, mod.ToWorld(host, x, y)) end
            end
        end
    end
    return positions
end

local look = {atlas="TrivialQuests", texture="Interface\\GossipFrame\\AvailableQuestIcon", size=19}
local generation, set, requested = 0, nil, {}

function tracking.QuestOfferEvent(event, requestRequired)
    -- A normal QUESTLINE_UPDATE is the response to a request. Requesting
    -- again on every response would make every map trigger a new world scan.
    if (event == "QUESTLINE_UPDATE" and requestRequired) or event == "QUEST_ACCEPTED" or
        event == "QUEST_TURNED_IN" or event == "QUEST_REMOVED" or event == "PLAYER_LEVEL_UP" then
        requested = {}
    end
end

-- Forever combines quest lines, force-visible quests and task offers. Use its
-- own filters with the remote map as the context for account/zone overrides.
local function offerProvider()
    if not (QuestOfferDataProviderMixin and QuestOfferDataProviderMixin.GetAllQuestOffersForMap) then return end
    local view = { GetMapID=function(self) return self.mapID end }
    local provider = setmetatable({ GetMap=function() return view end }, {__index=QuestOfferDataProviderMixin})
    if provider.CacheFilterSettings then provider:CacheFilterSettings() end
    return provider, view
end

function tracking.RefreshQuestOffers(ns, mod, map, getMaps, enterOffer)
    generation = generation + 1
    local current = generation
    local stitch = ns.MapStitch
    if not stitch.IsBuilt() then return end
    local function visible()
        return (map and map:IsShown() and mod.IsStitched()) or (mod.PadViewOn and mod.PadViewOn())
    end
    if not (tracking.Get("lowLevelQuests") and C_QuestLine and C_QuestLine.GetAvailableQuestLines and visible()) then
        if set then stitch.SetPinSetOn(set, false) end
        return
    end
    set = set or stitch.PinSet("rutaxp_service_lowLevelQuests", 0, 4)
    local scope = tracking.GetAreaScope()
    local maps, seenMaps = {}, {}
    if scope and stitch.Rect(scope) then
        maps[1], seenMaps[scope] = scope, true
    end
    for _, mapID in ipairs(getMaps()) do
        if not seenMaps[mapID] and tracking.IsMapInArea(mapID, scope) then
            maps[#maps + 1], seenMaps[mapID] = mapID, true
        end
    end
    if #maps == 0 then
        stitch.SetPinSetOn(set, false)
        return
    end
    if scope ~= nil then stitch.SetPinSetOn(set, false) end
    local index, found = 1, {}
    local provider, view = offerProvider()
    local function readMore()
        if current ~= generation or not visible() then return end
        for _ = 1, 3 do
            local mapID = maps[index]
            if not mapID then
                local seen = nativePins(map, mod)
                stitch.ClearPinSet(set)
                local info = tracking.Info("lowLevelQuests")
                local icon = info and info.texture and {texture=info.texture, size=19} or look
                for _, point in ipairs(found) do
                    local q = point.offer
                    if mark(seen, q.questID, point.u, point.v) then
                        local pin = stitch.AddPin(set, point.u, point.v, icon,
                            {id=q.questID, name=q.questName, line=q.questLineName})
                        pin:SetScript("OnEnter", enterOffer)
                        pin:SetScript("OnLeave", GameTooltip_Hide)
                    end
                end
                stitch.SetPinSetOn(set, true)
                return
            end
            index = index + 1
            if C_QuestLine.RequestQuestLinesForMap and not requested[mapID] then
                requested[mapID] = true
                C_QuestLine.RequestQuestLinesForMap(mapID)
            end
            local offers
            if provider then
                view.mapID = mapID
                offers = provider:GetAllQuestOffersForMap(mapID)
            else
                offers = C_QuestLine.GetAvailableQuestLines(mapID)
            end
            if offers then
                for _, q in pairs(offers) do
                    if available(q) and (not provider or not provider.ShouldAddQuestOffer or
                        provider:ShouldAddQuestOffer(q, mapID)) then
                        local u, v = mod.ToWorld(mapID, q.x, q.y)
                        if u and v then found[#found + 1] = {offer=q, u=u, v=v} end
                    end
                end
            end
        end
        C_Timer.After(0, readMore)
    end
    readMore()
end
