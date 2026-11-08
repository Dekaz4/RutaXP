local _, ns = ...

local radiusSquared = 45 * 45 -- world yards
local sites, questsByGiver, indexedMap, guideCount
local lastGuide, lastStep, lastTravel, lastCheck, lastHint

-- Group by authored location before converting Era or Forever coordinates.
-- Distances within a map can then be tested without calling C_Map per NPC.
local function indexMap(self, map)
    if map == indexedMap and #self.order == guideCount then return end
    sites, questsByGiver, indexedMap, guideCount = {}, {}, map, #self.order
    local positions = {}
    local function add(goal, id, x, y, z)
        if not x or not y then return end
        local key = table.concat({goal.npc, goal.f or "", x, y, z or ""}, ":")
        local site = positions[key]
        if not site then
            site = {npc=goal.npc, name=goal.npcName, raw={map=map, f=goal.f, x=x, y=y, z=z}, quests={}}
            sites[#sites + 1] = site
            positions[key] = site
        end
        site.quests[id] = goal.title or self:GetQuestTitle(id)
        questsByGiver[goal.npc] = questsByGiver[goal.npc] or {}
        questsByGiver[goal.npc][id] = true
    end

    local faction = UnitFactionGroup("player")
    for _, id in ipairs(self.order) do
        local guide = self.guides[id]
        if not guide.temporary and not guide.recovery and (not guide.faction or guide.faction == faction)
            and self:MatchesConditions(guide) and self:MatchesConditions(guide.only) then
            for _, step in ipairs(guide.steps) do
                for _, goal in ipairs(step.goals or {step}) do
                    local quest = goal.quest or goal.questID
                    if goal.map == map and (goal.t or goal.action) == "accept" and goal.npc and goal.npcName
                        and self.earlyQuestOffers[quest] and self:MatchesConditions(goal.only)
                        and self:MatchesConditions(step.only) then
                        add(goal, quest, goal.x, goal.y, goal.z)
                        for _, spot in ipairs(goal.spots or {}) do
                            if not spot.alt then add(goal, quest, spot.x, spot.y, spot.z) end
                        end
                    end
                end
            end
        end
    end
end

function ns:IsKnownQuestGiverLocation(id, npc, map)
    if not self.earlyQuestOffers or not self.earlyQuestOffers[id] or not npc or not map then return false end
    indexMap(self, map)
    return questsByGiver[npc] and questsByGiver[npc][id] == true or false
end

-- These two characters share the same wagon and are already described as
-- one stop in Westfall's guide. Keep the familiar short wording.
local cartOrder = {36, 151, 64}
local cartLabels = {[36]="estofado", [151]="avena", [64]="reloj"}

local function offersAt(self, site, map, groups, distance)
    local cart = map == 1436 and (site.npc == 237 or site.npc == 238)
    local key = cart and "cart" or site.npc
    local group = groups[key] or {name=site.name, cart=cart, quests={}, distance=math.huge, count=0}
    for id, title in pairs(site.quests) do
        if not group.quests[id] then
            local offer, _, order, index = self:GetPlannedPickupAtNPC(id, site.npc, map)
            if offer then
                group.quests[id] = title
                group.count = group.count + 1
                order, index = order or math.huge, index or id
                if not group.first or order < group.order or (order == group.order and index < group.index) then
                    group.first, group.order, group.index = id, order, index
                end
            end
        end
        if group.quests[id] then group.distance = math.min(group.distance, distance) end
    end
    if group.first then
        groups[key] = group
        return group
    end
end

local function nearby(self, continent, north, west, map)
    local groups, best = {}
    indexMap(self, map)
    for _, site in ipairs(sites) do
        if site.continent == nil then
            site.point = self:ResolveWaypointPoint(site.raw)
            if site.point and site.point.mapID == map then
                site.continent, site.north, site.west = self:GetWaypointWorldPosition(site.point)
            end
        end
        local distance = site.continent == continent and ((north - site.north)^2 + (west - site.west)^2)
        if distance and distance <= radiusSquared then
            local height = self:GetWaypointHeightDifference(site.point)
            if not height or math.abs(height) <= 15 then
                local group = offersAt(self, site, map, groups, distance)
                if group and (not best or group.distance < best.distance) then best = group end
            end
        end
    end
    if not best then return end
    if best.cart then
        local names = {}
        for _, id in ipairs(cartOrder) do
            if best.quests[id] then names[#names + 1] = cartLabels[id] end
        end
        if #names > 0 then return "Habla con los Cejade · " .. table.concat(names, ", ") end
    end
    local extra = best.count > 1 and (" (+" .. (best.count - 1) .. ")") or ""
    return "Habla con " .. best.name .. " · " .. best.quests[best.first] .. extra
end

function ns:GetNearbyQuestOfferHint(guide, step, state, travel)
    if not guide or not state or state.review or (not step and not travel)
        or not self.GetPlannedPickupAtNPC or not self.earlyQuestOffers or (travel and travel.waiting) then return end
    local now = GetTime and GetTime()
    local destination = travel and travel.destination
    if now and lastCheck and now - lastCheck < 1 and lastGuide == guide and lastStep == step
        and lastTravel == destination then return lastHint end
    lastGuide, lastStep, lastTravel, lastCheck, lastHint = guide, step, destination, now, nil
    if not self.TravelRouting or self.TravelRouting.OnTaxi() then return end
    local continent, north, west, map = self:GetPlayerWorldPosition()
    if not north then return end
    lastHint = nearby(self, continent, north, west, map)
    return lastHint
end
