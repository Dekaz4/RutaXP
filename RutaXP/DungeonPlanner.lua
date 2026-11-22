local _, ns = ...
local planner = {}
ns.DungeonPlanner = planner
local data, qs = ns.DungeonQuestData, ns.RestedQuestState
local model, modelGuide, lastInstance, queued

local function saved()
    local char = ns.char
    if not char then return end
    if not char.dungeonTrips then char.dungeonTrips = {finished={}, deferred={}, runs={}} end
    return char.dungeonTrips
end

local function context()
    local _, race, raceID = UnitRace("player")
    local _, class, classID = UnitClass("player")
    local faction = UnitFactionGroup("player")
    return {level=UnitLevel("player"), faction=faction, map=C_Map.GetBestMapForUnit("player"),
        race=race, raceID=raceID, class=class, classID=classID, status={}}
end

local function status(ctx, id)
    if not ctx.status[id] then
        ctx.status[id] = qs.Delivered(id) and "done" or
            (qs.Active(id) and (qs.Ready(id) and "ready" or "active")) or "offered"
    end
    return ctx.status[id]
end

local function bitSet(mask, bitID)
    return not mask or mask == 0 or not bitID or bitID < 1 or math.floor(mask/2^(bitID-1)) % 2 == 1
end

local function eligible(ctx, q)
    if not q or q.unavailable or q.holiday or (q.faction and q.faction ~= ctx.faction)
        or (q.classToken and q.classToken ~= ctx.class) or (q.minLevel or 0) > ctx.level
        or not bitSet(q.classes, ctx.classID) then return false end
    local skill = q.skill or (q.profession == "BLACKSMITHING" and 164) or (q.profession == "MINING" and 186)
    if skill and (not ns.GetProfessionRank or (ns:GetProfessionRank(skill) or 0) <= 0) then return false end
    for _, race in ipairs(q.unavailableRaces or {}) do
        if race == ctx.race then return false end
    end
    for _, req in ipairs(q.reputation or {}) do
        local rep = C_Reputation and C_Reputation.GetFactionDataByID and C_Reputation.GetFactionDataByID(req.faction)
        local standing = rep and rep.reaction
        if not standing and GetFactionInfoByID then standing = select(3,GetFactionInfoByID(req.faction)) end
        if not standing or standing < req.standing then return false end
    end
    if ctx.race and ctx.race:lower():find("skyborne", 1, true) then
        if not bitSet(q.raceHigh, ctx.faction == "Alliance" and 1 or 2) then return false end
    elseif not bitSet(q.races, ctx.raceID) then return false end
    for _, other in ipairs(q.excl or {}) do
        if status(ctx, math.abs(other)) ~= "offered" then return false end
    end
    return true
end

local function dungeonName(key, dungeon)
    local journal = ns.GetEmbeddedModule and ns.GetEmbeddedModule("ForeverDungeonJournal")
    if journal and journal.LocalizeDungeonName then
        local name = journal.LocalizeDungeonName(key)
        if name and name ~= "" and name ~= key then return name end
    end
    return dungeon.name or key
end

local function instance()
    if not IsInInstance or not IsInInstance() then return end
    local journal = ns.GetEmbeddedModule("ForeverDungeonJournal")
    if journal and journal.CurrentDungeon then
        local key = journal.CurrentDungeon()
        if data.dungeons[key] then return key end
    end
    if not GetInstanceInfo then return end
    local name, _, _, _, _, _, _, instanceID = GetInstanceInfo()
    local map = C_Map.GetBestMapForUnit("player")
    local possible, ambiguous
    for key, d in pairs(data.dungeons) do
        if name == key or name == d.name or (d.instanceMapID and d.instanceMapID == map) or name == dungeonName(key,d) then return key end
        if instanceID and d.instanceID == instanceID then
            if possible then ambiguous = true end
            possible = key
        end
    end
    if not ambiguous then return possible end
end

local function title(id)
    return (C_QuestLog.GetTitleForQuestID and C_QuestLog.GetTitleForQuestID(id))
        or (data.quests[id] and data.quests[id].title) or ("Misión " .. id)
end

local function meets(ctx, requirement)
    if requirement < 0 then
        local value = status(ctx, -requirement)
        return value == "active" or value == "ready"
    end
    return status(ctx, requirement) == "done"
end

local function planDungeon(ctx, dungeon, inside, handinsOnly)
    local plan = {tasks={}, seen={}, members={}, held=0, done=0, applicable=0, localCount=0}
    for _, id in ipairs(dungeon.quests) do plan.members[id] = true end
    local function add(kind, id, point)
        local key = kind .. id
        if plan.seen[key] then return end
        plan.seen[key] = true
        local task = {kind=kind, id=id, point=point}
        plan.tasks[#plan.tasks+1] = task
        if point and (point.map or point.mapID) == ctx.map then plan.localCount = plan.localCount + 1 end
    end
    local visiting = {}
    local function visit(id)
        if visiting[id] then return end
        visiting[id] = true
        local q, state = data.quests[id], status(ctx,id)
        if not q or state == "done" then return end
        if state == "ready" then add("turnin", id, q.turnin); return end
        if state == "active" then
            if q.workInside then add("run", id, q.work)
            elseif plan.members[id] then add("check", id)
            else add("work", id, q.work) end
            return
        end
        if not eligible(ctx, q) then return end
        local waiting = false
        for _, parent in ipairs(q.preAll or {}) do
            if not meets(ctx, parent) then
                waiting = true
                visit(math.abs(parent))
            end
        end
        local alternatives = q.pre or {}
        if #alternatives > 0 then
            local unlocked, best, bestScore
            for _, parent in ipairs(alternatives) do
                if meets(ctx, parent) then unlocked = true; break end
                local n = math.abs(parent)
                local p = data.quests[n]
                if p and eligible(ctx, p) then
                    local rank = (status(ctx,n) ~= "offered" and 4 or 0)
                        + (p.pickup and p.pickup.map == ctx.map and 2 or 0)
                    if not bestScore or rank > bestScore then best, bestScore = n, rank end
                end
            end
            if not unlocked then
                waiting = true
                if best then visit(best) end
            end
        end
        if waiting then add("locked",id); return end
        local pick = q.pickup
        if pick and pick.inside then add("inside", id, pick)
        elseif pick and pick.item and not pick.map and not pick.mapID and
            not ((C_Item and C_Item.GetItemCount and C_Item.GetItemCount(pick.item) or 0) > 0) then
            add("itemDrop", id, pick)
        elseif pick and (pick.map or pick.mapID or pick.npc or pick.item or pick.object) then add("pickup", id, pick)
        else add("unknown", id) end
    end
    for _, id in ipairs(dungeon.quests) do
        local s = status(ctx,id)
        if s == "done" then plan.done = plan.done + 1
        elseif data.quests[id] and (s ~= "offered" or eligible(ctx,data.quests[id])) then
            plan.applicable = plan.applicable + 1
            if s == "active" or s == "ready" then plan.held = plan.held + 1 end
            visit(id)
        end
    end
    if handinsOnly then
        local deliveries = {}
        plan.localCount = 0
        for _,task in ipairs(plan.tasks) do
            if task.kind == "turnin" and task.point and not task.point.inside then
                deliveries[#deliveries+1] = task
                if (task.point.map or task.point.mapID) == ctx.map then
                    plan.localCount = plan.localCount + 1
                end
            end
        end
        plan.tasks = deliveries
    end
    local function priority(t)
        local interior = t.point and t.point.inside
        if inside then
            if t.kind == "inside" or (t.kind == "turnin" and interior) then return 0 end
            if t.kind == "run" or t.kind == "check" then return 1 end
            return 10
        end
        if t.kind == "turnin" and not interior or t.kind == "pickup" or t.kind == "work" then return 1 end
        if t.kind == "run" or t.kind == "inside" or (t.kind == "turnin" and interior) then return 3 end
        if t.kind == "check" then return 4 end
        return 8
    end
    local player = ns:PlayerPoint()
    local function distance(t)
        if not t.point or (t.point.map or t.point.mapID) ~= ctx.map then return math.huge end
        local p = ns:ResolveWaypointPoint(t.point)
        if not p or not player or player.mapID ~= p.mapID then return math.huge end
        return (p.x-player.x)^2 + (p.y-player.y)^2
    end
    for _, t in ipairs(plan.tasks) do t.priority, t.distance = priority(t), distance(t) end
    table.sort(plan.tasks, function(a,b)
        if a.priority ~= b.priority then return a.priority < b.priority end
        if a.distance ~= b.distance then return a.distance < b.distance end
        return a.id < b.id
    end)
    return plan
end

local function actionable(plan)
    local first = plan.tasks[1]
    return first and first.kind ~= "locked" and first.kind ~= "unknown" and first.kind ~= "itemDrop"
end

local function inLevelRange(ctx, dungeon)
    return ctx.level >= (dungeon.minLevel or 1) and ctx.level <= (dungeon.maxLevel or 60)
end

local function runComplete(ctx, run)
    if not run or not next(run) then return false end
    for id in pairs(run) do
        local s = status(ctx,id)
        if s ~= "ready" and s ~= "done" then return false end
    end
    return true
end

local function observeRun(trips, key, ctx, inside)
    if not key then return end
    local dungeon, run = data.dungeons[key], trips.runs[key]
    if not dungeon then return end
    for _, id in ipairs(dungeon.quests) do
        local s = status(ctx,id)
        if inside and (s == "active" or s == "ready") then
            if not run then run = {}; trips.runs[key] = run end
            run[id] = true
        end
    end
    -- Leave inside pickups visible while still in the run. On leaving, the
    -- character only needs hand-ins. This also survives logout in an instance.
    if not inside and runComplete(ctx,run) then trips.finished[key] = true end
end

local verbs = {pickup="Recoge", inside="Recoge dentro", work="Completa la previa",check="Consulta el objetivo en tu diario",
    itemDrop="Acepta si consigues el objeto",
    run="Completa dentro", turnin="Entrega", locked="Después de la previa", unknown="Inicio por confirmar"}
local questActions={pickup="accept",inside="accept",itemDrop="accept",work="complete",run="complete",turnin="turnin"}
local function line(task)
    task.questTitle = task.questTitle or title(task.id)
    return verbs[task.kind] .. " · " .. task.questTitle
end

local function rebuild(activeGuide)
    local trips = saved()
    if not trips then return {rows={}} end
    local ctx, here = context(), instance()
    observeRun(trips, here, ctx, true)
    if lastInstance and lastInstance ~= here then observeRun(trips, lastInstance, ctx, false) end
    if not here then
        for key in pairs(trips.runs) do
            if not trips.finished[key] then observeRun(trips, key, ctx, false) end
        end
    end
    lastInstance = here
    local repeatKey = trips.repeatDungeon
    local repeatData = repeatKey and data.dungeons[repeatKey]
    local chosen, best, score
    for key,d in pairs(data.dungeons) do
        local nearby = d.entrance and (d.entrance.map or d.entrance.mapID) == ctx.map
        local requested = key == trips.selected or key == here or key == repeatKey
        if requested or (not trips.deferred[key] and inLevelRange(ctx,d)) then
            local plan = planDungeon(ctx,d,key == here,trips.finished[key] and key ~= repeatKey)
            if actionable(plan) and (requested or nearby or plan.localCount > 0 or plan.held > 0) then
                local rank = (key == here and 10000 or key == repeatKey and 8000 or key == trips.selected and 5000 or 0)
                    + plan.held*20 + math.min(10,plan.localCount)*2 + (nearby and 8 or 0)
                if not score or rank > score or (rank == score and key < chosen) then chosen,best,score = key,plan,rank end
            end
        end
    end
    if repeatData and chosen ~= repeatKey and (not here or here == repeatKey) then
        local hint = here == repeatKey and "Visita libre en curso" or "Ve a la entrada de la mazmorra"
        return {detour=true, key=repeatKey, heading=dungeonName(repeatKey,repeatData), hint=hint,
            point=here ~= repeatKey and repeatData.entrance or nil,
            rows={{text=hint},{text="Volver a la ruta de mundo abierto",action="later",dungeon=repeatKey}}}
    end
    if trips.selected and chosen ~= trips.selected and (not here or trips.finished[trips.selected]) then trips.selected = nil end
    local out = {rows={}, key=chosen, plan=best}
    local function row(text, action)
        local entry={text=text, action=action, dungeon=chosen}
        out.rows[#out.rows+1] = entry
        return entry
    end
    local task, dungeon = best and best.tasks[1], data.dungeons[chosen]
    local defer = chosen and trips.deferred[chosen]
    local focusedQuest, focusedMatch
    local autoVisit
    if not activeGuide then
        if not here and not (ns.DuoAuto and ns.DuoAuto:GetSharedView()) then
            focusedQuest, focusedMatch = ns.WorldQuestFocus.Current()
        end
        if task and task.kind == "run" and best.held > 0 then
            autoVisit = IsInGroup and IsInGroup() and GetNumGroupMembers and GetNumGroupMembers() >= 5
                and dungeon.entrance and (dungeon.entrance.map or dungeon.entrance.mapID) == ctx.map
        elseif task and task.kind == "pickup" and task.distance < .0009 and not focusedQuest then
            local traveling = (ns.GetGuideTravel and ns:GetGuideTravel()) or
                (not ns.navigationActivity and ns.GetDestinationTravelView and ns:GetDestinationTravelView())
            autoVisit = not traveling
        end
    end
    out.detour = chosen and not defer and (chosen == trips.selected or chosen == repeatKey or chosen == here or autoVisit)
    if chosen then
        local name = dungeonName(chosen,dungeon)
        if out.detour then
            local inside = chosen == here
            local enter = not inside and (task.kind == "run" or task.kind == "inside" or
                (task.kind == "turnin" and task.point and task.point.inside))
            out.heading = name
            out.hint = enter and ("Ve a la entrada de " .. name) or line(task)
            out.point = enter and dungeon.entrance or task.point
            if inside and task.kind ~= "inside" and task.kind ~= "run" and not (task.point and task.point.inside) then
                out.point = nil
                if task.point then
                    if task.kind == "turnin" then out.hint = "Sal de la mazmorra para continuar las entregas"
                    elseif task.kind == "work" or task.kind == "pickup" then
                        out.hint = "Fuera de la mazmorra · " .. line(task)
                    end
                end
            elseif enter then row(out.hint)
            elseif task.kind == "work" or task.kind == "check" then out.questPoint = task.id end
            for _, t in ipairs(best.tasks) do
                local p=t.point
                local entry=row(line(t) .. ((p and p.name) and (" · " .. p.name) or ""))
                entry.questID,entry.questTitle,entry.questAction=t.id,t.questTitle,questActions[t.kind]
                entry.status=t.kind=="locked" and "blocked" or status(ctx,t.id)
                entry.isCurrent=t==task
                if p then
                    if p.npc then entry.npcName=p.name
                    elseif p.object then entry.objectName=p.name
                    elseif p.item then entry.itemName=p.name end
                end
            end
            row("Seguir con la ruta de mundo abierto", "later")
        else
            local prefix = trips.finished[chosen] and "Entregas pendientes" or "Preparar mazmorra"
            row(prefix .. " · " .. name, "prepare")
        end
    end
    if not out.detour and focusedQuest then
        out.detour, out.world, out.match = true,focusedQuest,focusedMatch
        out.heading = title(focusedQuest)
        local ready=qs.Ready(focusedQuest)
        local goal=focusedMatch and focusedMatch.goal
        local action=ready and "turnin" or (goal and (goal.t or goal.action)) or "complete"
        out.hint = ready and "Entrega la misión" or "Continúa el objetivo de tu diario"
        table.insert(out.rows,1,{text=out.hint .. " · " .. out.heading,questID=focusedQuest,questTitle=out.heading,
            questAction=action,status=ready and "ready" or "active",isCurrent=true,goal=goal})
        local objectives=not ready and C_QuestLog.GetQuestObjectives and C_QuestLog.GetQuestObjectives(focusedQuest) or {}
        local nextRow=2
        for i,obj in ipairs(objectives) do
            if obj.text and not obj.finished then
                local matching=goal and (goal.oi or goal.objectiveIndex or goal.objective)==i and goal or nil
                table.insert(out.rows,nextRow,{text=obj.text,questID=focusedQuest,questTitle=out.heading,
                    questAction=matching and (matching.t or matching.action) or "complete",goal=matching,
                    status="active",questObjectives=objectives,objectiveIndex=i})
                nextRow=nextRow+1
            end
        end
        row("Dejar de seguir esta misión", "world")
    end
    return out
end

local function current()
    local guide = ns.WorldQuestFocus.ActiveGuide()
    if not model or guide ~= modelGuide then
        model, modelGuide = rebuild(guide), guide
    end
    return model
end
function planner:Rows() return current().rows end
function planner:IsDetouring() return current().detour end
function planner:Heading() local m=current(); return m.heading, m.hint end
function planner:Hint() return current().hint end
function planner:RouteKey()
    local m = current()
    if m.detour then return m.world or (tostring(m.key)..":"..tostring(m.questPoint or m.hint)) end
end
function planner:RoutePoint()
    local m = current()
    if not m.detour then return end
    local p
    if m.world then p = ns.WorldQuestFocus.Point(m.world,m.match)
    elseif m.questPoint then
        local match = ns.WorldQuestFocus.Match(m.questPoint,ns:GetCurrent(),C_Map.GetBestMapForUnit("player"))
        p = ns.WorldQuestFocus.Point(m.questPoint, match)
        if not p and m.point then p = ns:ResolveWaypointPoint(m.point) end
    elseif m.point then p = ns:ResolveWaypointPoint(m.point) end
    if p and ns.RouteDestination then
        return ns:RouteDestination(p, self:RouteKey(), "activity")
    end
    return p
end
function planner:Waypoint()
    local p,view = self:RoutePoint()
    return p and p.mapID,p and p.x,p and p.y,view and view.shortText or current().hint,view
end
function planner:TravelView()
    local _,view = self:RoutePoint()
    return view
end

function planner:Changed()
    model = nil
    if queued or not ns.initialized then return end
    local function refresh()
        queued = nil
        if ns.GuideJourney and ns.GuideJourney:Available() then ns.GuideJourney:Refresh()
        elseif ns.window then ns:RefreshUI() end
        if ns.DungeonPreparationUI then ns.DungeonPreparationUI:RefreshIfShown() end
    end
    if C_Timer and C_Timer.After then queued=true; C_Timer.After(0,refresh) else refresh() end
end

function planner:Click(entry)
    local m, trips = current(), saved()
    if not trips then return end
    if entry.action == "prepare" and m.key == entry.dungeon then
        return self:StartPreparation(m.key)
    elseif entry.action == "later" and m.key == entry.dungeon then
        trips.deferred[m.key] = true
        trips.lastDeferred = m.key
        trips.selected = nil
        trips.repeatDungeon = nil
    elseif entry.action == "world" and m.world then ns.WorldQuestFocus.Clear(m.world)
    else return end
    self:Changed()
end

function planner:Wants(action,id)
    local m = current()
    if not m.plan or not m.detour or m.world then return false end
    for _, t in ipairs(m.plan.tasks) do
        if t.id == id and ((action == "turnin" and t.kind == "turnin") or (action == "accept" and
            (t.kind == "pickup" or t.kind == "inside"))) then return true end
    end
    return false
end

-- The picker may be opened while the character is following an unrelated guide.
-- Examine live quests without changing the selection, deferrals or visit history.
local emptyTrips = {finished={},deferred={},runs={}}

local function preparationPlan(key, dungeon, ctx, here, trips)
    local inside = here == key
    local finished = trips.finished[key] or (not inside and runComplete(ctx,trips.runs[key]))
    if not (inside or finished or trips.selected == key or trips.deferred[key] or inLevelRange(ctx,dungeon)) then return end
    local plan = planDungeon(ctx,dungeon,inside,finished)
    if actionable(plan) then return plan,not not finished end
end

function planner:PreparationOptions()
    local options = {}
    if not ns.char then return options end
    local ctx, here, trips = context(), instance(), ns.char.dungeonTrips or emptyTrips
    for key,dungeon in pairs(data.dungeons) do
        local plan,finished = preparationPlan(key,dungeon,ctx,here,trips)
        if plan then
            local deferred = not not trips.deferred[key]
            local entry = {key=key, name=dungeonName(key,dungeon), tasks={}, deferred=deferred, finished=finished}
            entry.priority = trips.selected == key and 4 or (deferred and trips.lastDeferred == key) and 3
                or here == key and 2 or deferred and 1 or 0
            local door = dungeon.entrance
            local nearby = door and (door.map or door.mapID) == ctx.map
            entry.relevance = plan.held*20 + math.min(10,plan.localCount)*2 + (nearby and 8 or 0)
            for _,task in ipairs(plan.tasks) do
                local place = task.point and task.point.name
                entry.tasks[#entry.tasks+1] = line(task) .. (place and (" · " .. place) or "")
            end
            options[#options+1] = entry
        end
    end
    table.sort(options,function(a,b)
        if a.priority ~= b.priority then return a.priority > b.priority end
        if a.relevance ~= b.relevance then return a.relevance > b.relevance end
        return a.key < b.key
    end)
    return options
end

function planner:StartPreparation(key)
    local dungeon = data.dungeons[key]
    if not ns.char or not dungeon then return false end
    if not preparationPlan(key,dungeon,context(),instance(),ns.char.dungeonTrips or emptyTrips) then return false end
    local trips = saved()
    trips.selected, trips.repeatDungeon = key,nil
    trips.deferred[key] = nil
    if trips.lastDeferred == key then trips.lastDeferred = nil end
    self:Changed()
    return true
end

function planner:Resume()
    local first = self:PreparationOptions()[1]
    if first then return self:StartPreparation(first.key) end
    ns:Print("No tienes una preparación de mazmorra pendiente.")
    return false
end

function planner:Repeat(name)
    local trips = saved()
    if not trips then return false end
    for key, d in pairs(data.dungeons) do
        if key:lower() == name:lower() or (d.name and d.name:lower() == name:lower()) or dungeonName(key,d):lower() == name:lower() then
            trips.repeatDungeon = key
            trips.deferred[key] = nil
            self:Changed()
            return true
        end
    end
    ns:Print("Usa /rutaxp repetir seguido del nombre de la mazmorra que aparece en el diario.")
    return false
end

local driver = CreateFrame("Frame")
for _, e in ipairs({"PLAYER_LOGIN","PLAYER_ENTERING_WORLD","ZONE_CHANGED_NEW_AREA","QUEST_LOG_UPDATE",
    "QUEST_ACCEPTED","QUEST_TURNED_IN","QUEST_REMOVED","QUEST_WATCH_UPDATE","PLAYER_LEVEL_UP",
    "GROUP_ROSTER_UPDATE","SUPER_TRACKING_CHANGED","GOSSIP_SHOW","QUEST_GREETING","SKILL_LINES_CHANGED"}) do pcall(driver.RegisterEvent,driver,e) end
driver:SetScript("OnEvent",function(_,event)
    if ns.char and (event == "QUEST_LOG_UPDATE" or event == "QUEST_WATCH_UPDATE") then ns.WorldQuestFocus.Observe() end
    if ns.char and event == "SUPER_TRACKING_CHANGED" then ns.WorldQuestFocus.TrackingChanged() end
    planner:Changed()
end)

-- Walking to another questgiver can change the best pickup without producing
-- a zone or quest event. Re-evaluate only after appreciable movement.
local elapsed, lastPosition = 0, nil
driver:SetScript("OnUpdate",function(_,dt)
    elapsed = elapsed + dt
    if elapsed < 3 or not ns.char then return end
    elapsed = 0
    local p = ns:PlayerPoint()
    if not p then return end
    if not lastPosition or p.mapID ~= lastPosition.mapID or
        (p.x-lastPosition.x)^2 + (p.y-lastPosition.y)^2 > .0004 then
        lastPosition = p
        planner:Changed()
    end
end)
