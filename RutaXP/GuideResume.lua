local _, ns = ...
local resume = {}
ns.GuideResume = resume

local status, message = "pending", "Leyendo la zona, las guías y el registro de misiones…"
local journalReady, subscribed, scheduled, switching, entered
local carrying
local lastMap, lastLevel
local profiles = {}
local actions = {accept=true, complete=true, turnin=true}

local function report(code, text)
    local changed = code ~= status or text ~= message
    status, message = code, text
    if changed and ns.OnGuideResumeChanged then ns.OnGuideResumeChanged() end
    return code, text
end

function resume.Status() return status, message end
function resume.HoldingJournal() return carrying == true end

local function key(guide)
    return guide and (guide.key or (guide.group and guide.name and guide.group .. "||" .. guide.name))
end

-- Accepts are useful to locate a shared quest; a legacy cursor is never
-- interpreted as a RestedXP step number or written back into the old routes.
local function oldPosition(char)
    local id, bookmark = char.activeGuide, char.recovery and char.recovery.bookmark
    if id == "_recovery" and bookmark then id = bookmark.guideID else bookmark = nil end
    local old = id and ns.legacyGuideAnchors and ns.legacyGuideAnchors[id]
    local saved = id and char.progress and char.progress[id]
    if not old or not saved then return end
    local at = tonumber(bookmark and bookmark.cursor or saved.cursor)
    local revision = tonumber(saved.routeRevision)
    if not at or not revision then return end
    while revision < old.revision do
        local change = old.migrations and old.migrations[revision]
        if not change or at > change.count or change.to <= revision then return end
        at, revision = change[at] or at, change.to
    end
    if revision == old.revision then return old[at] end
end
resume.LegacyPosition = oldPosition

local function player()
    local map = C_Map and C_Map.GetBestMapForUnit and C_Map.GetBestMapForUnit("player")
    local level = UnitLevel("player")
    if not map or not level or level < 1 then return end
    local info = C_Map.GetMapInfo(map)
    local zoneType = Enum and Enum.UIMapType and Enum.UIMapType.Zone
    -- The API may return the interior of a mine or a starting subzone.
    -- Resolve these to the zone used by the guide's waypoints.
    for _ = 1, 8 do
        if not (zoneType and info and info.mapType and info.mapType > zoneType and
                info.parentMapID and info.parentMapID > 0) then break end
        info = C_Map.GetMapInfo(info.parentMapID)
        if info then map = info.mapID end
    end
    local pos = C_Map.GetPlayerMapPosition and C_Map.GetPlayerMapPosition(map, "player")
    local x, y
    if pos then x, y = pos:GetXY() end
    return {map=map, name=info and info.name or GetZoneText(), level=level,
        x=x and x*100, y=y and y*100, quests={}}
end

local function quest(ctx, id)
    local q = ctx.quests[id]
    if not q then
        q = {done=ns:IsQuestDelivered(id), active=ns:IsQuestActive(id)}
        ctx.quests[id] = q
    end
    return q
end

local function unresolved(ctx, element)
    local q = quest(ctx, element.questId)
    if q.done or (element.skipIfMissing and not q.active) then return false end
    if element.tag == "accept" then return not q.active end
    if element.tag == "complete" and q.active then
        if q.complete == nil then q.complete = C_QuestLog.IsComplete and C_QuestLog.IsComplete(element.questId) or false end
        if q.complete then return false end
        if element.obj and C_QuestLog.GetQuestObjectives then
            q.objectives = q.objectives or C_QuestLog.GetQuestObjectives(element.questId) or {}
            local objective = q.objectives[element.obj]
            if objective and (objective.finished or element.objMax and objective.numFulfilled and
                    objective.numFulfilled >= element.objMax) then return false end
        end
    end
    return true
end

local function zoneOf(e)
    if not e then return end
    local z = e.zone or e.map
    if type(z) == "number" then return z end
    if type(z) == "string" then return tonumber(z) or ns.GuideEngine.MapID(z) end
end

local function profile(guide)
    local id = key(guide)
    if profiles[id] then return profiles[id] end
    local full = ns.GuideEngine.Preview(guide)
    if not (full and full.steps and #full.steps > 0) then return end
    local result = {zones={}, quests={}}
    for _, step in ipairs(full.steps) do
        local area, point = zoneOf(step)
        for _, e in ipairs(step.elements or {}) do
            if actions[e.tag] and e.questId then result.quests[e.questId] = true end
            if e.x and e.y and zoneOf(e) then area, point = zoneOf(e), e end
        end
        if area then
            local zone = result.zones[area]
            if not zone then zone = {count=0}; result.zones[area] = zone end
            zone.count = zone.count + 1
            if point then zone[#zone+1] = {point.x, point.y} end
        end
    end
    profiles[id] = result
    return result
end

local function levelRange(guide)
    local name = (guide.displayname or ""):gsub("|c%x%x%x%x%x%x%x%x",""):gsub("|r","")
    local lo, hi = name:match("^%s*(%d+)%s*%-%s*(%d+)")
    if not lo then lo, hi = (guide.name or ""):match("^%s*(%d+)%s*%-%s*(%d+)") end
    return tonumber(lo), tonumber(hi)
end

local function bestGuide(ctx, legacy)
    local best, bestScore
    for _, g in ipairs(ns.GuideEngine.Catalog()) do
        local lo, hi = levelRange(g)
        -- The catalog also contains optional, dungeon, hardcore and endgame
        -- guides. Keep them available for explicit selection.
        if key(g) and lo and lo <= ctx.level and ctx.level <= hi and not g.lowPrio and
                not g.farm and not g.hardcore and not g.dungeon and not g.enabledungeons and
                (not g.forever or g.disabledungeons) then
            local data = profile(g)
            local localZone = data and data.zones[ctx.map]
            local active, overlap = 0, 0
            local finished = data and next(data.quests) ~= nil
            if data then
                if legacy then
                    for i = 2, #legacy do if data.quests[legacy[i]] then overlap = overlap + 1 end end
                end
                for id in pairs(data.quests) do
                    local q = quest(ctx,id)
                    if q.active then active = active + 1 end
                    if not q.done then finished = false end
                end
            end
            if not finished and (localZone or (legacy and overlap > 0 and data.zones[legacy[1]])) then
                local score = math.min(5, active)*7 + math.min(4, overlap)*4
                if localZone then
                    score = score + 38 + math.min(12, localZone.count)
                    if ctx.x and ctx.y then
                        local nearest = math.huge
                        for _, point in ipairs(localZone) do
                            nearest = math.min(nearest, (point[1]-ctx.x)^2 + (point[2]-ctx.y)^2)
                        end
                        if nearest < 64 then score = score + (8-math.sqrt(nearest)) end
                    end
                end
                if g.disabledungeons then score = score + 3 end
                if ctx.level == hi and hi ~= lo then score = score - 2 end
                if not bestScore or score > bestScore or (score == bestScore and key(g) < key(best)) then
                    best, bestScore = g, score
                end
            end
        end
    end
    return best
end

-- Resolve against the processed steps for this character. In particular, raw
-- preview indices can differ after filtering class steps and expanding includes.
local function resumeStep(guide, ctx, legacy)
    local oldIDs = {}
    if legacy then for i=2,#legacy do oldIDs[legacy[i]] = true end end
    local journalStep, oldStep, firstPending, knownBefore, crossedKnown
    local accepts, uses, labels = {}, {}, {}
    for i, step in ipairs(guide.steps) do
        if step.label then labels[step.label] = i end
        local pending, evidence = false, false
        for _, e in ipairs(step.elements or {}) do
            local id = e.questId
            if id and actions[e.tag] then
                local q = quest(ctx,id)
                evidence = evidence or q.active or q.done
                if unresolved(ctx,e) then
                    pending = true
                    if q.active and e.tag ~= "accept" then journalStep = journalStep or i end
                    if oldIDs[id] then oldStep = oldStep or i end
                    if not q.active and not e.skipIfMissing then
                        if e.tag == "accept" then accepts[id] = accepts[id] or i else uses[id] = i end
                    end
                end
            end
        end
        if not firstPending and pending then firstPending, crossedKnown = i, knownBefore end
        if evidence and not pending then knownBefore = true end
    end
    local target = journalStep or oldStep or (crossedKnown and firstPending) or 1
    -- Don't land on an objective that still needs an earlier acceptance or
    -- skip a prerequisite that the guide explicitly identifies by its label.
    local previous
    repeat
        previous = target
        for id, accepted in pairs(accepts) do
            if accepted < target and uses[id] and uses[id] >= target then target = accepted end
        end
        local required = labels[guide.steps[target].requires]
        if required and required < target then
            local hasQuest, pending = false, false
            for _, e in ipairs(guide.steps[required].elements or {}) do
                if actions[e.tag] and e.questId then hasQuest = true; pending = pending or unresolved(ctx,e) end
            end
            if not hasQuest or pending then target = required end
        end
    until previous == target
    return target
end

local function remember(mode, guide, text, awaitingZone)
    ns.char.guideLink = {mode=mode, key=key(guide), awaitingZone=awaitingZone}
    return report(mode, text or guide.displayname or guide.name)
end

local function selectGuide(g, mode, ctx, legacy, savedStep, checkpoint)
    local engine = ns.GuideEngine
    switching = true
    local ok = key(engine.Current()) == key(g) or engine.Select(g)
    local current, at = engine.Current()
    if ok and key(current) == key(g) then
        if current.steps and #current.steps > 0 then
            local step
            if checkpoint and checkpoint.step then
                step = math.max(1, math.min(checkpoint.step,#current.steps))
                if checkpoint.stepID then
                    for i, row in ipairs(current.steps) do
                        if row.stepId == checkpoint.stepID then step = i; break end
                    end
                end
            elseif not at or at <= 1 then
                if savedStep then step = math.max(1, math.min(savedStep,#current.steps))
                elseif ctx then step = resumeStep(current, ctx, legacy) end
            end
            if step and step ~= at then engine.SetStep(step) end
        end
        -- Restore a held guide on login. A successful zone lookup (ctx)
        -- finishes the wait, including when the held guide is the best match.
        local link = ns.char.guideLink
        local awaitingZone = mode == "auto" and not ctx and link and link.awaitingZone or nil
        remember(mode, current, nil, awaitingZone)
    else
        ok = false
    end
    switching = false
    return ok
end

function resume.SelectManually(guide)
    if not ns.char or not ns.GuideEngine.Ready() or not key(guide) then return false end
    if not selectGuide(guide, "manual") then return false end
    if ns.GuideCarryover then
        ns.GuideCarryover.Dismiss()
        ns.char.heldOfficialGuide, carrying = nil, nil
    end
    return true
end

local function savedGuide(catalog, ctx, char)
    local group, name, step = ns.GuideEngine.SavedSelection()
    if not (group and name) then return end
    for _, g in ipairs(catalog) do
        if g.group == group and g.name == name then
            local lo, hi = levelRange(g)
            -- A previous bootstrap could persist a level-one default without
            -- ever advancing it. An out-of-range default isn't a continuation
            -- for a character arriving with a real RutaXP chapter.
            if not char.guideLink and char.progress and char.progress[char.activeGuide] and (tonumber(step) or 1) <= 1 and
                    lo == 1 and ctx.level > hi then return end
            return g, tonumber(step)
        end
    end
end

local function byKey(catalog, match)
    if match then
        for _, g in ipairs(catalog) do if key(g) == match then return g end end
    end
end

local function holdForJournal(engine, char)
    local current, at = engine.Current()
    if not char.heldOfficialGuide then
        local catalog, link = engine.Catalog(), char.guideLink
        if #catalog == 0 then return end
        local g, n = savedGuide(catalog, {level=UnitLevel("player") or 0}, char)
        g = g or (link and byKey(catalog, link.key))
        local hold = {} -- An engine-generated default is not a character bookmark.
        if g then
            hold.key = key(g)
            hold.mode = link and link.key and link.mode or "saved"
            if current and key(current) == hold.key and at and (at > 1 or not n) then
                n = at
                local row = current.steps and current.steps[n]
                hold.stepID = row and row.stepId
            end
            hold.step = n
        end
        char.heldOfficialGuide = hold
    end
    if current and not (InCombatLockdown and InCombatLockdown()) then
        switching = true
        engine.Clear()
        switching = false
    end
end

local function sync(force)
    local engine, char = ns.GuideEngine, ns.char
    if switching or not entered or not char then
        return false, "El catálogo de guías todavía se está cargando."
    end
    local carry = ns.GuideCarryover
    if carry and not force and not (char.guideLink and char.guideLink.mode == "manual") then
        local state, detail = carry.Check()
        if state == "pending" or state == "journal" then
            carrying = true
            if engine and engine.Ready() then holdForJournal(engine, char) end
            report(state, detail)
            return false, detail
        end
    end
    if not engine or not engine.Ready() then return false, "El catálogo de guías todavía se está cargando." end
    if InCombatLockdown and InCombatLockdown() then return false, "Sal de combate para cambiar de guía." end
    local ctx = player()
    if not ctx then return false, "Esperando a que el juego indique tu zona y nivel." end
    local current = engine.Current()
    local link = char.guideLink
    if carry and not force and (carrying or char.heldOfficialGuide) then
        -- Clearing the active guide changes RXP's native currentGuide fields.
        -- The character checkpoint survives logout while finishing the journal.
        lastMap, lastLevel = nil, nil
        local hold = char.heldOfficialGuide
        if hold and hold.key and not (link and link.mode == "manual") then
            local catalog = engine.Catalog()
            if #catalog == 0 then return end
            local g = byKey(catalog, hold.key)
            if g then
                if not selectGuide(g, hold.mode, nil, nil, nil, hold) then return end
                char.heldOfficialGuide, carrying = nil, nil
                lastMap, lastLevel = ctx.map, ctx.level
                return
            end
        end
        char.heldOfficialGuide, carrying = nil, nil
    end
    if not force and lastMap and current and link and link.key and key(current) ~= link.key then
        -- The native engine owns the cursor after a chapter transition. Keep
        -- the character's choice about whether future zones should be followed.
        remember(link.mode, current, nil, link.awaitingZone)
        link = char.guideLink
    end
    if not force and lastMap == ctx.map and lastLevel == ctx.level then return end
    local catalog = engine.Catalog()
    if #catalog == 0 then return false, "El catálogo de guías todavía se está cargando." end
    if not force and not lastMap then
        -- Restore a real previous selection ahead of any temporary guide the
        -- native engine happened to load during this login.
        local saved, step = savedGuide(catalog,ctx,char)
        if saved and (not link or link.mode ~= "unavailable") then
            local mode = link and link.key and link.mode or "saved"
            if not selectGuide(saved, mode, nil, nil, step) then return end
        elseif link and link.key then
            for _, g in ipairs(catalog) do
                if key(g) == link.key then
                    if not selectGuide(g, link.mode) then return end
                    break
                end
            end
        end
        current, link = engine.Current(), char.guideLink
        if current and link and key(current) == link.key and link.mode ~= "auto" then
            lastMap, lastLevel = ctx.map, ctx.level
            return
        end
    end
    if not force and current and link and (link.mode=="manual" or link.mode=="saved") then
        lastMap, lastLevel = ctx.map, ctx.level
        return
    end
    if not journalReady and ctx.level > 1 then
        local entries = C_QuestLog and C_QuestLog.GetNumQuestLogEntries and C_QuestLog.GetNumQuestLogEntries()
        if not entries or entries == 0 then return false, "Esperando a que cargue tu registro de misiones." end
    end
    if UnitOnTaxi and UnitOnTaxi("player") then return false, "La zona se puede detectar al aterrizar." end
    if IsInInstance and IsInInstance() then return false, "La búsqueda de rutas de leveo usa la zona del mundo exterior." end
    if carry and force then
        carry.Dismiss()
        char.heldOfficialGuide, carrying = nil, nil
    end
    local legacy = not force and not link and oldPosition(char)
    if not force and link and link.mode == "auto" and not link.awaitingZone and current and current.steps then
        local data = profile(current)
        -- A chapter may intentionally take the player across several zones.
        if data and data.zones[ctx.map] then
            lastMap, lastLevel = ctx.map, ctx.level
            return
        end
    end
    local g = bestGuide(ctx, legacy)
    lastMap, lastLevel = ctx.map, ctx.level
    if g then
        if selectGuide(g,"auto",ctx,legacy) then return true end
        lastMap = nil
        return false, "Todavía no se pudo activar la guía de esta zona."
    elseif current and link and link.key and (force or link.awaitingZone) then
        local text = ("Sin guía de leveo para %s al nivel %d. Sigue activa %s hasta llegar a una zona con guía."):format(
            ctx.name,ctx.level,current.displayname or current.name)
        remember("auto", current, text, true)
    elseif not force and current and link and link.key then
        return -- A short visit to a city or a transit zone should keep the route.
    else
        if current then
            switching = true
            engine.Clear()
            switching = false
        end
        char.guideLink = {mode="unavailable"}
        report("unavailable", ("Sin guía oficial de leveo para %s al nivel %d."):format(ctx.name,ctx.level))
    end
end

function resume.UseZone()
    local matched, why = sync(true)
    return status, why or message, matched == true
end
function resume.Sync() sync(false); return status, message end

local function queue()
    if switching or scheduled then return end
    scheduled = true
    C_Timer.After(0, function()
        scheduled = false
        if not subscribed and ns.GuideEngine and ns.GuideEngine.Subscribe then
            subscribed = true
            ns.GuideEngine.Subscribe(queue)
        end
        resume.Sync()
    end)
end

local frame = CreateFrame("Frame")
for _, event in ipairs({"PLAYER_ENTERING_WORLD","QUEST_LOG_UPDATE","ZONE_CHANGED_NEW_AREA","ZONE_CHANGED_INDOORS",
        "PLAYER_LEVEL_UP","PLAYER_REGEN_ENABLED","PLAYER_CONTROL_GAINED"}) do frame:RegisterEvent(event) end
frame:SetScript("OnEvent",function(_,event)
    if event=="PLAYER_ENTERING_WORLD" then entered = true
    elseif event=="QUEST_LOG_UPDATE" then
        if journalReady and status ~= "pending" and status ~= "journal" then return end
        journalReady = true
    end
    queue()
    -- UnitLevel and the player's new map can still report their previous
    -- values during these events. Recheck once after the transition.
    if event=="PLAYER_LEVEL_UP" or event=="ZONE_CHANGED_NEW_AREA" then C_Timer.After(1, queue) end
end)
