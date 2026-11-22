local _, ns = ...
local planner = {}
ns.DungeonPlanner = planner
local data, qs = ns.DungeonQuestData, ns.RestedQuestState
local model, lastInstance, queued

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
        if name == key or name == d.name or (d.instanceMapID and d.instanceMapID == map) then return key end
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

local function planDungeon(ctx, dungeon, inside)
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
    if not run or not next(run) then return end
    for id in pairs(run) do
        local s = status(ctx,id)
        if s ~= "ready" and s ~= "done" then return end
    end
    -- Leave inside pickups visible while still in the run. On leaving, the
    -- character only needs hand-ins. This also survives logout in an instance.
    if not inside then trips.finished[key] = true end
end

local verbs = {pickup="Recoge", inside="Recoge dentro", work="Completa la previa",check="Consulta el objetivo en tu diario",
    itemDrop="Acepta si consigues el objeto",
    run="Completa dentro", turnin="Entrega", locked="Después de la previa", unknown="Inicio por confirmar"}
local function line(kind,id) return verbs[kind] .. " · " .. title(id) end

local function rebuild()
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
        if requested or (not trips.deferred[key] and ctx.level >= (d.minLevel or 1) and ctx.level <= (d.maxLevel or 60)) then
            local plan = planDungeon(ctx,d,key == here)
            if trips.finished[key] and key ~= repeatKey then
                local deliveries = {}
                for _,t in ipairs(plan.tasks) do
                    if t.kind == "turnin" and not (t.point and t.point.inside) then deliveries[#deliveries+1]=t end
                end
                plan.tasks = deliveries
            end
            local first = plan.tasks[1]
            local actionable = first and first.kind ~= "locked" and first.kind ~= "unknown" and first.kind ~= "itemDrop"
            if actionable and (requested or nearby or plan.localCount > 0 or plan.held > 0) then
                local rank = (key == here and 10000 or key == repeatKey and 8000 or key == trips.selected and 5000 or 0)
                    + plan.held*20 + math.min(10,plan.localCount)*2 + (nearby and 8 or 0)
                if not score or rank > score or (rank == score and key < chosen) then chosen,best,score = key,plan,rank end
            end
        end
    end
    if repeatData and chosen ~= repeatKey and (not here or here == repeatKey) then
        local hint = here == repeatKey and "Visita libre en curso" or "Ve a la entrada de la mazmorra"
        return {detour=true, key=repeatKey, heading=repeatData.name or repeatKey, hint=hint,
            point=here ~= repeatKey and repeatData.entrance or nil,
            rows={{text=hint},{text="Volver a la ruta de mundo abierto",action="later",dungeon=repeatKey}}}
    end
    if trips.selected and chosen ~= trips.selected and (not here or trips.finished[trips.selected]) then trips.selected = nil end
    local out = {rows={}, key=chosen, plan=best}
    local function row(text, action)
        out.rows[#out.rows+1] = {text=text, action=action, dungeon=chosen}
    end
    local task, dungeon = best and best.tasks[1], data.dungeons[chosen]
    local group = IsInGroup and IsInGroup()
    local defer = chosen and trips.deferred[chosen]
    local autoRun = task and not defer and group and GetNumGroupMembers and GetNumGroupMembers() >= 5
        and dungeon.entrance and (dungeon.entrance.map or dungeon.entrance.mapID) == ctx.map
        and best.held > 0 and task.kind == "run"
    local nearPickup = task and not defer and task.kind == "pickup" and task.distance < .0009
    out.detour = chosen and not defer and (chosen == trips.selected or chosen == repeatKey or chosen == here or autoRun or nearPickup)
    if chosen then
        local name = dungeon.name or chosen
        if out.detour then
            local inside = chosen == here
            local enter = not inside and (task.kind == "run" or task.kind == "inside" or
                (task.kind == "turnin" and task.point and task.point.inside))
            out.heading = name
            out.hint = enter and ("Ve a la entrada de " .. name) or line(task.kind,task.id)
            out.point = enter and dungeon.entrance or task.point
            if inside and task.kind ~= "inside" and task.kind ~= "run" and not (task.point and task.point.inside) then
                out.point = nil
                out.hint = "Sal de la mazmorra para continuar las entregas"
            elseif enter then row(out.hint)
            elseif task.kind == "work" or task.kind == "check" then out.questPoint = task.id end
            for _, t in ipairs(best.tasks) do
                row(line(t.kind,t.id) .. ((t.point and t.point.name) and (" · " .. t.point.name) or ""))
            end
            row("Seguir con la ruta de mundo abierto", "later")
        else
            local prefix = trips.finished[chosen] and "Entregas pendientes" or "Preparar mazmorra"
            row(prefix .. " · " .. name, "prepare")
        end
    end
    if not out.detour and not here and not (ns.DuoAuto and ns.DuoAuto:GetSharedView()) then
        local id, match = ns.WorldQuestFocus.Current()
        if id then
            out.detour, out.world, out.match = true,id,match
            out.heading = title(id)
            out.hint = qs.Ready(id) and "Entrega la misión" or "Continúa el objetivo de tu diario"
            table.insert(out.rows,1,{text=out.hint .. " · " .. out.heading})
            for _, obj in ipairs(C_QuestLog.GetQuestObjectives and C_QuestLog.GetQuestObjectives(id) or {}) do
                if obj.text and not obj.finished then table.insert(out.rows,2,{text=obj.text}) end
            end
            row("Volver al paso de RutaXP", "world")
        end
    end
    return out
end

local function current()
    if not model then model = rebuild() end
    return model
end
function planner:Rows() return current().rows end
function planner:IsDetouring() return current().detour end
function planner:Heading() local m=current(); return m.heading, m.hint end
function planner:Hint() return current().hint end
function planner:Waypoint()
    local m = current()
    if not m.detour then return end
    local p
    if m.world then p = ns.WorldQuestFocus.Point(m.world,m.match)
    elseif m.questPoint then
        local match = ns.WorldQuestFocus.Match(m.questPoint,ns:GetCurrent(),C_Map.GetBestMapForUnit("player"))
        p = ns.WorldQuestFocus.Point(m.questPoint, match)
        if not p and m.point then p = ns:ResolveWaypointPoint(m.point) end
    elseif m.point then p = ns:ResolveWaypointPoint(m.point) end
    if p then return p.mapID,p.x,p.y,m.hint end
end

function planner:Changed()
    model = nil
    if queued or not ns.initialized then return end
    local function refresh()
        queued = nil
        if ns.GuideJourney and ns.GuideJourney:Available() then ns.GuideJourney:Refresh()
        elseif ns.window then ns:RefreshUI() end
    end
    if C_Timer and C_Timer.After then queued=true; C_Timer.After(0,refresh) else refresh() end
end

function planner:Click(entry)
    local m, trips = current(), saved()
    if not trips then return end
    if entry.action == "prepare" and m.key == entry.dungeon then
        trips.selected = m.key
        trips.deferred[m.key] = nil
    elseif entry.action == "later" and m.key == entry.dungeon then
        trips.deferred[m.key] = true
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

function planner:Resume()
    local trips = saved()
    if not trips then return end
    trips.deferred = {}
    self:Changed()
    local m = current()
    if m.key then self:Click({action="prepare", dungeon=m.key})
    else ns:Print("No tienes una visita a mazmorra pendiente para esta zona y nivel.") end
end

function planner:Repeat(name)
    local trips = saved()
    if not trips then return false end
    for key, d in pairs(data.dungeons) do
        if key:lower() == name:lower() or (d.name and d.name:lower() == name:lower()) then
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
