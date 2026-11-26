local _, ns = ...
local Circuit = {}
ns.LocalCircuit = Circuit

-- A circuit borrows an action from this chapter. Only the original cursor
-- advances the chapter. Rows from later steps can also provide evidence that
-- two journal objectives can be credited during the same encounter.
local work = {kill=true, collect=true}
local normal = {kill=true, collect=true, turnin=true, accept=true, complete=true, getfp=true,
    sethome=true, vendor=true, train=true, buy=true}
local lookAhead = 6
local closeCamp = 125 -- yards between objectives worked during one visit
local nearContact = 12
local indexedGuide, byMap
local cache
local rejected = {}

local function read(fn, ...)
    if type(fn) ~= "function" then return end
    local ok, value = pcall(fn, ...)
    if ok and not (issecretvalue and issecretvalue(value)) then return value end
end

local function number(value)
    return not (issecretvalue and issecretvalue(value)) and type(value) == "number"
        and value == value and math.abs(value) < math.huge
end

local function distance(a, b)
    return math.sqrt((a.north-b.north)^2 + (a.west-b.west)^2)
end

local function index(guide)
    if guide == indexedGuide then return byMap end
    indexedGuide, byMap, rejected = guide, {}, {}
    for si, step in ipairs(guide.steps) do
        for gi, goal in ipairs(step.goals or {step}) do
            if goal.quest and goal.map and (work[goal.t] or goal.t == "turnin" or goal.t == "accept")
                and not goal.navigationMode and not goal.optionalWhenOffered then
                local rows = byMap[goal.map] or {}
                byMap[goal.map] = rows
                rows[#rows+1] = {row=goal, step=step, stepIndex=si, index=gi,
                    key=table.concat({si,gi,goal.quest}, "/")}
            end
        end
    end
    return byMap
end

local function place(goal, here)
    local point = ns:GetGoalWaypoint(goal)
    if not point or point.mapID ~= here.map then return end
    local continent, north, west = ns:GetWaypointWorldPosition(point)
    if continent ~= here.continent or not number(north) or not number(west) then return end
    local node = {point=point, north=north, west=west}
    node.distance = distance(here, node)
    return node
end

local function progress(goal, journal)
    local obj = journal.objectives and journal.objectives[goal.oi or goal.objective or 1]
    local done = obj and read(function() return obj.numFulfilled end)
    local total = obj and read(function() return obj.numRequired end)
    if not number(total) or total < 1 then total = goal.count end
    if goal.t == "collect" and goal.item then
        local bag = read(C_Item and C_Item.GetItemCount, goal.item, false) or read(GetItemCount, goal.item, false)
        if number(bag) then done = math.max(number(done) and done or 0, bag) end
    end
    if number(total) and total > 0 and number(done) then return done, total end
end

local function creature(name)
    return name and ns.circuitCreatures and ns.circuitCreatures[name]
end

local function difficult(enemy, level)
    return enemy and (enemy.elite or enemy.min >= level+3 or enemy.max >= level+4)
end

local function enemyLevel(goal, level)
    local first
    if goal.t == "kill" then
        first = creature(goal.target)
        if first and goal.npc and first.id ~= goal.npc then first = nil end
    elseif goal.fromKind == "npc" then
        -- Navigation resolves the main camp and non-alt spots. A low-level
        -- alternate on another beach cannot make that destination safe.
        first = creature(goal.from)
        if not first then return nil, nil, true end
    elseif goal.fromKind == "object" then
        return
    else
        return nil, nil, true
    end
    if first then
        return first.max, difficult(first, level)
    end
    local best
    for _, enemy in ipairs((ns.travelEnemyLevels or {})[goal.quest] or {}) do
        if (not goal.oi or goal.oi == enemy.oi) and (goal.t ~= "kill" or goal.npc == enemy.mob)
            and (not best or enemy.max < best.max) then best = enemy end
    end
    return best and best.max, difficult(best, level), not best
end

-- Direction matters: we will fight the primary creature at the selected
-- stop. That creature can count as either source of an incidental objective.
local function sameEnemy(primary, other, level)
    local source, id
    if primary.t == "kill" then
        id, source = primary.npc, creature(primary.target)
        if source and source.id ~= id then source = nil end
    elseif primary.t == "collect" and primary.fromKind == "npc" then
        source = creature(primary.from)
        id = source and source.id
    else
        return false
    end
    if not id or difficult(source, level) then return false end
    if other.t == "kill" then return id == other.npc end
    if other.t ~= "collect" or other.fromKind ~= "npc" then return false end
    local function counts(label)
        local enemy = creature(label)
        return enemy and id == enemy.id
    end
    return counts(other.from) or counts(other.fromAlso)
end

local function activeJournal(id, journals)
    if not journals[id] then
        local active = ns:IsQuestActive(id)
        journals[id] = {active=active, ready=active and read(C_QuestLog and C_QuestLog.IsComplete, id),
            objectives=active and read(C_QuestLog and C_QuestLog.GetQuestObjectives, id)}
    end
    return journals[id]
end

local function plausible(ref, state)
    return ref.stepIndex >= state.cursor and ref.stepIndex <= state.cursor + lookAhead
end

local function confirmedOpportunity(goal, journal)
    if not journal.active then return false end
    if goal.t == "turnin" then return journal.ready == true or goal.collectThenDeliver end
    if not work[goal.t] or journal.ready ~= false or not journal.objectives or journal.objectives[2] then return false end
    local done, total = progress(goal, journal)
    return done and done > 0 and done < total and done >= total*.75 and total-done <= 2
end

local function localRow(ref, guide, state, here, journal)
    local goal = ref.row
    if not (ns:MatchesConditions(ref.step.only) and ns:MatchesConditions(goal.only))
        or (goal.faction and goal.faction ~= here.faction) or (ref.step.faction and ref.step.faction ~= here.faction)
        or (not journal.active and goal.t ~= "accept") or (journal.active and goal.t == "accept")
        or (goal.t == "accept" and (not plausible(ref,state) or not goal.npc
            or not (ns.earlyQuestOffers and ns.earlyQuestOffers[goal.quest]))) then return end
    local mark = ref.stepIndex .. ":" .. ref.index
    if (state.skipped and state.skipped[mark]) or (state.confirmed and state.confirmed[mark]) then return end
    local action, status, why = ns:GetActionableGoal(goal, ref.step, state, ref.index, guide)
    -- The paired collection and hand-in can have the same live phase. Use its
    -- authored row exactly once, retaining the actual phase as the destination.
    if action ~= goal then return end
    local incidental = status == "skip" and work[goal.t] and journal.active and goal.levelingDetour
        and why == ns:GetLevelingDetourReason(goal, true)
    if status ~= "active" and not incidental then return end
    local node = place(goal, here)
    if not node then return end
    if goal.t == "turnin" then
        if journal.ready ~= true and not goal.collectThenDeliver then return end
    elseif work[goal.t] then
        if journal.ready ~= false then return end
        node.done, node.total = progress(goal, journal)
        if node.done and node.done >= node.total then return end
        node.enemy, node.hard, node.unknownSource = enemyLevel(goal, here.level)
    elseif goal.t == "accept" then
        if node.distance > 45 or not ns.GetPlannedPickupAtNPC
            or not ns:GetPlannedPickupAtNPC(goal.quest, goal.npc, here.map) then return end
        local contact = ns.GetQuestContactNPC and ns:GetQuestContactNPC()
        if contact == goal.npc then
            if not ns:IsQuestOnOpenMenu(goal.quest, contact) then return end
        elseif node.point.source ~= "game" then
            -- A documented giver does not prove the offer is up at this visit.
            return
        end
    end
    node.goal, node.ref, node.incidental = goal, ref, incidental
    return node
end

local function workForPickup(goal, rows, nodes, state, level)
    for _, ref in ipairs(rows) do
        local future = ref.row
        if future.quest == goal.quest and work[future.t] and ns:MatchesConditions(future.only)
            and ns:MatchesConditions(ref.step.only) then
            for _, node in ipairs(nodes) do
                if plausible(node.ref,state) and work[node.goal.t] and not node.hard and not node.unknownSource
                    and not node.incidental and sameEnemy(node.goal,future,level) then return true end
            end
        end
    end
    return false
end

local function explain(node, nodes, level, baseHard)
    local goal = node.goal
    if goal.t == "accept" then
        return 72, "Recógela aquí para avanzar dos misiones con los mismos enemigos"
    end
    local nearby, shared, otherDelivery = 0, nil, nil
    for _, other in ipairs(nodes) do
        if goal.quest ~= other.goal.quest and distance(node,other) <= closeCamp then
            if goal.t == "turnin" and other.goal.t == "turnin" then otherDelivery = other.goal end
            if work[goal.t] and work[other.goal.t] then
                if sameEnemy(goal,other.goal,level) then shared = other end
                if not other.hard and not other.unknownSource and not other.incidental then nearby = nearby + 1 end
            end
        end
    end
    if goal.t == "turnin" then
        if otherDelivery then
            return 98, "Entrega también «" .. (otherDelivery.title or ns:GetQuestTitle(otherDelivery.quest)) .. "» en una sola visita"
        end
        return 47, "Entrega lista de camino"
    end
    if shared then
        local second = shared.goal
        local name = second.title or ns:GetQuestTitle(second.quest)
        if second.t == "collect" then return 83, "Estos enemigos también pueden dar botín para «" .. name .. "»" end
        return 86, "Las bajas también cuentan para «" .. name .. "»"
    end
    if node.done and node.done > 0 and node.done >= node.total * .6 and node.total-node.done <= 3 then
        local left = node.total-node.done
        if goal.t == "collect" then
            return 70, left == 1 and "Te falta un objeto de este campamento" or ("Te faltan " .. left .. " objetos en este campamento")
        end
        return 78, left == 1 and "Te falta una baja de camino" or ("Te faltan " .. left .. " bajas de camino")
    end
    if nearby > 0 then return 55, "Puedes avanzar varias misiones en esta zona" end
    if baseHard and node.enemy then return 54, "Objetivo cercano adecuado para tu nivel" end
end

local function result(node, reason, base)
    local ref = node.ref
    return {goal=node.goal, step=ref.step, stepIndex=ref.stepIndex, index=ref.index,
        key=ref.key, point=node.point, reason=reason, authored=node.goal == base}
end

local function validBookmark(guide, state)
    local saved = ns.char.localCircuit
    return type(saved) == "table" and saved.guide == guide.id and saved.cursor == state.cursor and saved
end

local function bookmark(guide, state)
    local saved = validBookmark(guide, state)
    if not saved then
        saved = {guide=guide.id, cursor=state.cursor}
        ns.char.localCircuit = saved
    end
    return saved
end

function Circuit:Invalidate() cache = nil end

function Circuit:Defer(guide, state, stop)
    if not stop or not stop.key then return end
    local saved = bookmark(guide, state)
    if type(saved.deferred) ~= "table" then saved.deferred = {} end
    saved.deferred[stop.key] = true
    saved.key, saved.quest = nil,nil
    self:Invalidate()
end

local function plan(guide, state, base, here)
    local anchor = place(base, here)
    if not anchor then return end
    local saved = validBookmark(guide, state)
    local rows = index(guide)[here.map] or {}
    local nodes, journals, localWork, baseNode, held = {}, {}, {}
    for _, ref in ipairs(rows) do
        local goal = ref.row
        if plausible(ref,state) and work[goal.t] and activeJournal(goal.quest,journals).active then
            localWork[#localWork+1] = goal
        end
    end
    for _, ref in ipairs(rows) do
        local goal = ref.row
        local inWindow = plausible(ref,state)
        local journal = activeJournal(goal.quest, journals)
        local confirmed = not inWindow and confirmedOpportunity(goal,journal)
        local consider = inWindow or confirmed or saved and saved.key and saved.quest == goal.quest
        if not consider and work[goal.t] then
            -- A later or earlier row only contributes incidental credit.
            -- Avoid looking up its status and waypoint otherwise.
            for _, primary in ipairs(localWork) do
                if goal.quest ~= primary.quest and sameEnemy(primary,goal,here.level) then consider = true; break end
            end
        end
        local eligible = consider and journal.active and goal.t ~= "accept"
        local node = eligible and localRow(ref, guide, state, here, journal)
        if node then
            if node.goal == base then baseNode = node end
            -- A simple nearly-finished objective can predate the current
            -- cursor. Distant future/earlier hand-ins only qualify in town.
            node.opportunity = confirmed and node.distance <= (goal.t == "turnin" and 60 or 450)
            nodes[#nodes+1] = node
            local phaseChange = saved and saved.quest == node.goal.quest and node.goal.collectThenDeliver
                and node.goal.t == "turnin"
            if saved and saved.key and not node.incidental and not node.hard and not node.unknownSource
                and (saved.key == ref.key and node.distance <= 1100 or phaseChange) then
                local walk = ns.Walking
                if walk and walk.phase == "failed" and walk.startMap == here.map and walk.target
                    and math.abs(walk.target.x-node.north) < 5 and math.abs(walk.target.y-node.west) < 5 then
                    rejected[ref.key] = here.time + 30
                elseif (rejected[ref.key] or 0) <= here.time then
                    held = node
                end
            end
        end
    end
    for _, ref in ipairs(rows) do
        local goal = ref.row
        if goal.t == "accept" and plausible(ref,state) and (ns.earlyQuestOffers or {})[goal.quest]
            and not activeJournal(goal.quest,journals).active then
            local offer = localRow(ref, guide, state, here, journals[goal.quest])
            if offer and workForPickup(goal, rows, nodes, state, here.level) then
                nodes[#nodes+1] = offer
                if saved and saved.key == ref.key then held = offer end
            end
        end
    end
    local baseHard = baseNode and baseNode.hard or base.minLevel and base.minLevel > here.level
    if held then
        local _, reason = explain(held, nodes, here.level, baseHard)
        if reason then return result(held, reason, base) end
    end
    if saved then saved.key, saved.quest = nil,nil end
    local best, bestScore, bestReason, bestBudget
    local baseValue, baseReason
    if baseNode and not baseHard and not baseNode.unknownSource then baseValue, baseReason = explain(baseNode, nodes, here.level) end
    for _, node in ipairs(nodes) do
        local ref, goal = node.ref, node.goal
        if goal ~= base and (plausible(ref,state) or node.opportunity) and not node.incidental and not node.hard and not node.unknownSource
            and (rejected[ref.key] or 0) <= here.time
            and not (saved and type(saved.deferred) == "table" and saved.deferred[ref.key]) then
            local extra = math.max(0, node.distance + distance(node,anchor) - anchor.distance)
            local budget = goal.t == "collect" and 90 or 140
            local immediate = node.distance <= nearContact
            if node.distance <= 900 and extra <= budget and (baseHard or node.distance+20 < anchor.distance or immediate) then
                local value, reason = explain(node, nodes, here.level, baseHard)
                if value then
                    -- Relative preference, not a prediction of loot or XP.
                    local score = value - extra/4 - node.distance/32
                    local incumbent = baseValue and baseValue - anchor.distance/32 or 0
                    local atBaseContact = anchor.distance <= nearContact and (base.t == "accept" or base.t == "turnin")
                    if not atBaseContact and score > math.max(0,incumbent+8) and (not best or score > bestScore) then
                        best, bestScore, bestReason, bestBudget = node, score, reason, budget
                    end
                end
            end
        end
    end
    if best then
        local height = ns.GetWaypointHeightDifference and ns:GetWaypointHeightDifference(best.point)
        local atStop = best.distance <= (height and nearContact or 8) and (not height or math.abs(height) <= 12)
            and (not read(IsIndoors) or height ~= nil)
        local key = table.concat({guide.id, state.cursor, best.ref.key, base.quest or 0, base.t or ""}, "/")
        local pass = atStop
        if not pass and ns.CircuitTerrain then
            pass = ns.CircuitTerrain:Check(key, best.point, anchor.point, bestBudget)
            if pass == false then rejected[best.ref.key] = here.time + 20 end
        end
        if pass then
            saved = bookmark(guide,state)
            saved.key, saved.quest = best.ref.key, best.goal.quest
            return result(best, bestReason, base)
        end
    end
    if baseNode and baseValue and baseValue >= 55 then return result(baseNode, baseReason, base) end
end

function Circuit:Choose(guide, step, state, base, baseIndex, baseStatus)
    if not ns.char or not ns.char.auto or not state or state.review or not base or not guide
        or guide.temporary or guide.recovery or not guide.steps or guide.steps[state.cursor] ~= step
        or (baseStatus ~= "active" and baseStatus ~= "manual" and baseStatus ~= "blocked") or not normal[base.t]
        or not ns.GetGoalWaypoint or not ns.GetPlayerWorldPosition or not ns.GetWaypointWorldPosition
        or base.navigationMode or read(IsInInstance) or read(UnitOnTaxi, "player")
        or read(UnitIsDeadOrGhost, "player") then return end
    -- Honour the existing explicit pair: getting the last shard sends the
    -- character to its recipient even if unrelated work remains nearby.
    if base.collectThenDeliver and base.t == "turnin" then return end
    local now = read(GetTime)
    local level = read(UnitLevel,"player")
    local map = read(C_Map and C_Map.GetBestMapForUnit, "player")
    if not number(level) or level < 1 or not number(map) or (base.map and map ~= base.map) then return end
    if cache and now and now >= cache.at and now-cache.at < 1.5 and cache.base == base
        and cache.guide == guide and cache.state == state and cache.step == step and cache.map == map
        and cache.level == level and cache.optional == ns.char.optional and cache.groups == ns.char.includeGroupQuests then
        return cache.stop
    end
    local continent, north, west, worldMap = ns:GetPlayerWorldPosition()
    if not number(continent) or not number(north) or not number(west) or worldMap ~= map then return end
    local here = {continent=continent, north=north, west=west, map=map, level=level, time=now or 0,
        faction=read(UnitFactionGroup, "player")}
    local stop = plan(guide, state, base, here)
    cache = {at=now or 0, base=base, guide=guide, state=state, step=step, map=map, level=level,
        optional=ns.char.optional, groups=ns.char.includeGroupQuests, stop=stop}
    return stop
end

local events = CreateFrame("Frame")
for _, event in ipairs({"QUEST_LOG_UPDATE", "QUEST_ACCEPTED", "QUEST_TURNED_IN", "QUEST_REMOVED",
    "BAG_UPDATE_DELAYED", "PLAYER_ENTERING_WORLD", "GROUP_ROSTER_UPDATE", "GOSSIP_SHOW",
    "QUEST_GREETING", "QUEST_DETAIL", "GOSSIP_CLOSED", "QUEST_FINISHED"}) do
    pcall(events.RegisterEvent, events, event)
end
events:SetScript("OnEvent", function() Circuit:Invalidate() end)
