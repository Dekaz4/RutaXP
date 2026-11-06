local _, ns = ...
-- Planning reads observed journals. Only an explicit click changes OUR guide;
-- no cursor, quest, omission or peer setting is copied from another player.
local P = {}
ns.DuoPlanner = P
local TTL, MAX_REQUESTS = 5, 12

local function read(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, a, b = pcall(fn, ...)
    if not ok then return nil end
    if issecretvalue then
        if issecretvalue(a) then a = nil end
        if issecretvalue(b) then b = nil end
    end
    return a, b
end
local function finite(n) return type(n) == "number" and n == n and math.abs(n) < math.huge end
local function token(value)
    value = tostring(value or ""):lower():gsub("[%s_%-]", "")
    if value == "undead" then return "scourge" end
    if value:find("skyborne", 1, true) then return "skyborne" end
    return value
end
local function matches(list, value)
    if list == nil then return true end
    if type(list) ~= "table" then list = { list } end
    local positive, found = false, false
    for _, item in ipairs(list) do
        local exclude = tostring(item):sub(1, 1) == "!"
        local name = token(exclude and item:sub(2) or item)
        if exclude and name == token(value) then return false end
        if not exclude then positive = true; if name == token(value) and value then found = true end end
    end
    return not positive or found
end
local function only(conditions, who)
    if not conditions then return true end
    return matches(conditions.classes, who.class) and matches(conditions.races, who.race)
        and matches(conditions.factions, who.faction)
end
local function people()
    local ctx = ns.Duo and read(ns.Duo.GetContext, ns.Duo) or {}
    ctx = type(ctx) == "table" and ctx or {}
    local _, class = read(UnitClass, "player")
    local _, race = read(UnitRace, "player")
    local mine = { level=read(UnitLevel, "player"), class=class, race=race,
        faction=read(UnitFactionGroup, "player"), map=read(C_Map and C_Map.GetBestMapForUnit, "player") }
    local partner = { level=ctx.partnerLevel, class=ctx.partnerClass, race=ctx.partnerRace,
        faction=ctx.partnerFaction, map=ctx.partnerMapID }
    local real = ctx.enabled == true and ctx.known == true and ctx.online == true and ctx.sameParty == true
        and finite(mine.level) and finite(partner.level) and partner.level > 0
        and mine.class and mine.race and mine.faction and partner.class and partner.race
        and partner.faction == mine.faction
    return mine, partner, ctx, not not real
end
local function identityAllowed(g, who)
    return g and not g.recovery and not g.temporary and (not g.faction or g.faction == who.faction)
        and only(g.only, who) and only(g, who)
end
local function guideAllowed(g, who)
    return identityAllowed(g, who) and finite(who.level)
        and who.level >= (g.minLevel or 1)
end
local function applies(record, who)
    return only(record.step.only, who) and only(record.goal.only, who)
        and (not record.goal.class or matches(record.goal.class, who.class))
end
local function questID(goal)
    local q = goal and (goal.quest or goal.questID)
    return finite(q) and q > 0 and q == math.floor(q) and q or nil
end
local function action(goal) return goal and (goal.t or goal.action) end
local function profession(goal, step)
    if ns.GetGoalProfessionRequirement then return ns:GetGoalProfessionRequirement(goal, step) end
    return goal and (goal.requiresSkill or goal.profLine) or step and (step.requiresSkill or step.profLine)
end
local function copy(value)
    if type(value) ~= "table" then return value end
    local out = {}; for k, v in pairs(value) do if k ~= "_rxpSpot" then out[k] = copy(v) end end
    return out
end
local function title(q, fallback)
    return read(C_QuestLog and C_QuestLog.GetTitleForQuestID, q) or fallback or ("Misión " .. tostring(q))
end
local function catalog()
    local cached, order = P.catalog, ns.order or {}
    local valid = cached and cached.count == #order
    if valid then for _, id in ipairs(order) do if cached.refs[id] ~= ns.guides[id] then valid = false; break end end end
    if valid then return cached end
    local index = { count=#order, refs={}, guides={}, quests={} }
    for position, id in ipairs(order) do
        local g = ns.guides[id]; index.refs[id] = g
        if g and not g.recovery and not g.temporary then
            local route = { guide=g, order=position, entries={}, quests={} }
            index.guides[#index.guides + 1] = route
            for si, step in ipairs(g.steps or {}) do
                for gi, goal in ipairs(step.goals or { step }) do
                    local q = questID(goal)
                    if q then
                        local record = { goal=goal, step=step, guide=g, stepIndex=si, goalIndex=gi }
                        index.quests[q] = index.quests[q] or {}
                        index.quests[q][#index.quests[q] + 1] = record
                        if not route.quests[q] then
                            route.quests[q] = {}; route.entries[#route.entries + 1] = q
                        end
                        route.quests[q][#route.quests[q] + 1] = record
                    end
                end
            end
        end
    end
    P.catalog = index
    return index
end
local function observe()
    local cache, requests = {}, 0
    return function(q, owner)
        local key = owner .. ":" .. q
        if cache[key] ~= nil then return cache[key] or nil end
        local value
        if owner == "mine" then
            if ns.Duo and ns.Duo.LocalQuest then value = read(ns.Duo.LocalQuest, ns.Duo, q) end
            if type(value) ~= "table" then
                local active = read(C_QuestLog and C_QuestLog.IsOnQuest, q)
                local delivered
                if ns.IsQuestDelivered then delivered = read(ns.IsQuestDelivered, ns, q)
                elseif active ~= true then delivered = read(C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted, q) end
                local complete = read(C_QuestLog and C_QuestLog.IsComplete, q)
                if delivered == true then value = { state=3 }
                elseif active == true then value = { state=complete == true and 2 or 1 }
                elseif active == false then value = { state=0 } end
            end
        elseif ns.Duo then
            value = read(ns.Duo.GetPartnerQuest, ns.Duo, q)
            if (not value or value.basic) and requests < MAX_REQUESTS and ns.Duo.RequestQuest then
                requests = requests + 1; read(ns.Duo.RequestQuest, ns.Duo, q)
            end
        end
        if type(value) ~= "table" or value.known == false or not finite(value.state)
            or value.state ~= math.floor(value.state) or value.state < 0 or value.state > 3 then value = nil end
        cache[key] = value or false
        return value
    end
end
local function delivered(observation, q, owner)
    local item = observation(math.abs(q), owner)
    if not item or item.basic then return nil end
    return item.state == 3
end
local function activeParent(goal, owner, observation)
    if not goal.parent then return true end
    if not finite(goal.parent) or goal.parent <= 0 or goal.parent ~= math.floor(goal.parent) then return nil end
    local item = observation(goal.parent, owner)
    if not item or item.basic then return nil end
    return item.state == 1 or item.state == 2
end
-- nil is unknown, false is a known unmet requirement. OR and AND retain their
-- authored meaning; a partner's absent snapshot never becomes a missing quest.
local function prerequisites(goal, who, owner, observation)
    local missing, unknown, orMissing = {}, {}, {}
    if goal.minLevel and (not finite(who.level) or who.level < goal.minLevel) then
        return false, "Requiere nivel " .. tostring(goal.minLevel) .. ".", missing, unknown
    end
    if profession(goal) then
        if owner ~= "mine" or not ns.CheckGoalProfession then
            return nil, "La profesión del compañero debe comprobarse en su personaje.", missing, unknown
        end
        local eligible, reason = ns:CheckGoalProfession(goal)
        if eligible ~= true then return eligible, reason, missing, unknown end
    end
    if goal.profession or goal.skill or goal.reputation then
        return nil, "El requisito de profesión, habilidad o reputación debe comprobarse en su personaje.", missing, unknown
    end
    local parent = activeParent(goal, owner, observation)
    if parent == false then
        missing[#missing + 1] = goal.parent
        return false, "Acepta primero " .. title(goal.parent, (goal.preTitles or {})[goal.parent])
            .. " y mantenla en tu diario.", missing, unknown
    elseif parent == nil then
        if finite(goal.parent) then unknown[#unknown + 1] = goal.parent end
        return nil, "Sin confirmar la misión que debe mantener en el diario.", missing, unknown
    end
    for _, q in ipairs(goal.closedBy or {}) do
        local item = observation(math.abs(q), owner)
        if not item or item.basic then unknown[#unknown + 1] = math.abs(q)
        elseif item.state > 0 then return false, "Otra misión activa o entregada cierra esta rama: " .. title(math.abs(q), (goal.preTitles or {})[math.abs(q)]) .. ".", missing, unknown end
    end
    for _, q in ipairs(goal.preAll or {}) do
        local state = delivered(observation, q, owner)
        if state == false then missing[#missing + 1] = math.abs(q)
        elseif state == nil then unknown[#unknown + 1] = math.abs(q) end
    end
    local alternatives = goal.pre or {}
    if #alternatives > 0 then
        local satisfied, unresolved = false, false
        for _, q in ipairs(alternatives) do
            local state = delivered(observation, q, owner)
            if state then satisfied = true
            elseif state == nil then unresolved = true end
        end
        if not satisfied then
            for _, q in ipairs(alternatives) do
                local state = delivered(observation, q, owner)
                if state == nil then unknown[#unknown + 1] = math.abs(q)
                else orMissing[#orMissing + 1] = math.abs(q) end
            end
            if unresolved then -- Still unknown whether another alternative suffices.
                orMissing = {}
            end
        end
    end
    local function names(ids)
        local out = {}; for _, q in ipairs(ids) do out[#out + 1] = title(q, (goal.preTitles or {})[q]) end
        return table.concat(out, ", ")
    end
    local reasons = {}
    if #missing > 0 then reasons[#reasons + 1] = "Debe entregar todas estas previas: " .. names(missing) .. "." end
    if #orMissing > 0 then
        reasons[#reasons + 1] = "Debe entregar una de estas previas alternativas: " .. names(orMissing) .. "."
        for _, q in ipairs(orMissing) do missing[#missing + 1] = q end
    end
    if #unknown > 0 then reasons[#reasons + 1] = "Sin confirmar requisitos del registro: " .. names(unknown) .. "." end
    if #missing > 0 then return false, table.concat(reasons, " "), missing, unknown end
    if #unknown > 0 then return nil, table.concat(reasons, " "), missing, unknown end
    return true, "Previas registradas satisfechas.", missing, unknown
end
local function acceptRecords(q, who)
    local out = {}
    for _, record in ipairs(catalog().quests[q] or {}) do
        if action(record.goal) == "accept" and identityAllowed(record.guide, who) and applies(record, who) then out[#out + 1] = record end
    end
    return out
end
local function completeSource(record, who)
    local q, work, handin = questID(record.goal), false, false
    for _, item in ipairs(catalog().quests[q] or {}) do
        if item.guide == record.guide and item.stepIndex >= record.stepIndex and applies(item, who) then
            local kind = action(item.goal)
            if kind == "turnin" then handin = true
            elseif kind ~= "accept" and kind ~= "note" and kind ~= "goto" then work = true end
        end
    end
    return work and handin
end
local function recoveryAvailable(target, who, owner, observation)
    -- Recovery plans complete and deliver prerequisites. An active parent
    -- must stay in the journal and cannot be recovered by such a plan.
    if activeParent(target, owner, observation) ~= true then return false end
    local work, path = 0, {}
    local resolve
    resolve = function(q, depth)
        local observed = observation(q, owner)
        if not observed or observed.basic then return false end
        if observed.state == 3 then return true end
        if depth > 12 or work >= 64 or path[q] then return false end
        work, path[q] = work + 1, true
        for _, r in ipairs(acceptRecords(q, who)) do
            local goal, valid = r.goal, completeSource(r, who)
            if goal.minLevel and who.level < goal.minLevel then valid=false end
            if goal.profession or goal.skill or goal.reputation then valid=false end
            if observed.state == 0 and profession(goal) and (owner ~= "mine" or not ns.CheckGoalProfession
                or ns:CheckGoalProfession(goal) ~= true) then valid=false end
            if valid and observed.state == 0 then
                if activeParent(goal, owner, observation) ~= true then valid=false end
                for _, closed in ipairs(goal.closedBy or {}) do
                    local value = observation(math.abs(closed), owner)
                    if not value or value.basic or value.state > 0 then valid=false end
                end
                for _, pre in ipairs(goal.preAll or {}) do if not resolve(math.abs(pre),depth+1) then valid=false end end
                if goal.pre and #goal.pre > 0 then
                    local satisfied=false
                    for _, pre in ipairs(goal.pre) do if resolve(math.abs(pre),depth+1) then satisfied=true;break end end
                    if not satisfied then valid=false end
                end
            end
            if valid then path[q]=nil;return true end
        end
        path[q]=nil;return false
    end
    for _, q in ipairs(target.preAll or {}) do if not resolve(math.abs(q),1) then return false end end
    if target.pre and #target.pre > 0 then
        local possible=false
        for _, q in ipairs(target.pre) do if resolve(math.abs(q),1) then possible=true;break end end
        if not possible then return false end
    end
    return true
end
local function commonAccept(records, mine, partner)
    for _, r in ipairs(records) do
        if action(r.goal) == "accept" and applies(r, mine) and applies(r, partner) and not profession(r.goal, r.step) then return r end
    end
end
local function key(mine, partner, ctx)
    local id = ns.char and ns.char.activeGuide
    local state = ns.char and ns.char.progress and ns.char.progress[id]
    return table.concat({tostring(id), tostring(state and state.cursor), tostring(mine.level), token(mine.class), token(mine.race),
        tostring(mine.faction), tostring(mine.map), tostring(partner.level), token(partner.class), token(partner.race),
        tostring(partner.faction), tostring(partner.map), tostring(ctx.enabled), tostring(ctx.known), tostring(ctx.online),
        tostring(ctx.sameParty), tostring(ctx.partnerName), tostring(ctx.guideID), tostring(ctx.cursor)}, "|")
end
function P:Invalidate() self.routesAt, self.differencesAt, self.automaticAt = nil, nil, nil end
function P:GetCommonRoutes()
    if not ns.char then return {} end
    local mine, partner, ctx, real = people()
    local stamp, identity = read(GetTime) or 0, key(mine, partner, ctx)
    if self.routesAt and self.routesKey == identity and stamp - self.routesAt >= 0 and stamp - self.routesAt < TTL then return self.routes end
    local results, observation = {}, observe()
    if real then
        local journal
        local total = read(C_QuestLog and C_QuestLog.GetNumQuestLogEntries)
        if finite(total) then
            journal = {}
            for i=1, math.min(total, 100) do
                local info = read(C_QuestLog and C_QuestLog.GetInfo, i)
                if type(info)=="table" and questID(info) and not info.isHeader then journal[questID(info)]=true end
            end
        end
        local candidates = {}
        for _, route in ipairs(catalog().guides) do
            local g = route.guide
            if guideAllowed(g, mine) and guideAllowed(g, partner) then
                local reference = math.min(mine.level,partner.level)
                local priority = (g.id == ns.char.activeGuide and 100 or 0) + (g.id == ctx.guideID and 80 or 0)
                    + (g.zone == mine.map and 40 or 0) + (g.zone == partner.map and 40 or 0)
                    + (reference <= (g.maxLevel or 60) and 50 or 0) - math.abs(reference-(g.minLevel or 1))
                candidates[#candidates + 1] = { route=route, priority=priority }
            end
        end
        table.sort(candidates, function(a,b) return a.priority == b.priority and a.route.order < b.route.order or a.priority > b.priority end)
        for _, candidate in ipairs(candidates) do
            local route, chosen = candidate.route
            local g = route.guide
            local function describe(q, accept, bothHere, sharedJournal)
                return {guideID=g.id, title=g.title, questID=q, referenceLevel=math.min(mine.level,partner.level),
                    sharedActive=sharedJournal, sameZone=bothHere, reason="Requisitos observados compatibles para ambos en este punto común.",
                    text="Compatible con los niveles " .. mine.level .. " y " .. partner.level
                        .. ", las razas y las clases de ambos. " .. (bothHere and "Ambos estáis en la zona de la guía. " or "Ambos lleváis esta misión; estáis en mapas distintos o sin mapa confirmado. ")
                        .. (math.max(mine.level,partner.level)>(g.maxLevel or 60) and "El rango es orientativo: el personaje con más nivel puede recibir menos XP; conserva sus requisitos y cadenas. " or "")
                        .. "Punto común comprobado: " .. title(q, accept and accept.goal.title) .. ". La elección cambia solo tu guía; conserva los pasos y las cadenas individuales. No confirma misiones anteriores ni incluye un viaje calculado."}
            end
            -- A shared active quest is stronger evidence than a cursor or a
            -- reconstructed full history (which the peer may not expose).
            for _, q in ipairs(route.entries) do
                if not journal or journal[q] then
                    local a = observation(q,"mine")
                    if a and a.state>0 and a.state<3 then
                        local shared=false
                        for _, r in ipairs(route.quests[q]) do
                            if not r.goal.optional and applies(r,mine) and applies(r,partner) and not profession(r.goal,r.step) then shared=true;break end
                        end
                        if shared then
                            local b=observation(q,"partner")
                            if b and b.state>0 and b.state<3 then
                                chosen=describe(q,commonAccept(route.quests[q],mine,partner),g.zone==mine.map and g.zone==partner.map,true)
                                break
                            end
                        end
                    end
                end
            end
            for _, q in ipairs(chosen and {} or route.entries) do
                local shared, required = false, false
                for _, r in ipairs(route.quests[q]) do
                    if applies(r, mine) and applies(r, partner) and not profession(r.goal,r.step) then shared=true; if not r.goal.optional then required=true end end
                end
                if shared and required then
                    local a, b = observation(q, "mine"), observation(q, "partner")
                    if not a or not b then break end
                    if not (a.state == 3 and b.state == 3) then
                        local accept = commonAccept(route.quests[q], mine, partner)
                        local readyA = a.state > 0
                        local readyB = b.state > 0
                        if not readyA and accept then readyA = prerequisites(accept.goal, mine, "mine", observation) == true end
                        if not readyB and accept then readyB = prerequisites(accept.goal, partner, "partner", observation) == true end
                        local bothHere = finite(g.zone) and g.zone == mine.map and g.zone == partner.map
                        local sharedJournal = a.state > 0 and a.state < 3 and b.state > 0 and b.state < 3
                        if readyA and readyB and (bothHere or sharedJournal) then
                            chosen = describe(q,accept,bothHere,sharedJournal)
                        end
                        break -- Never jump over a blocked/unknown shared branch.
                    end
                end
            end
            if chosen then results[#results + 1] = chosen; if #results == 3 then break end end
        end
    end
    self.routes, self.routesAt, self.routesKey = results, stamp, identity
    return results
end
function P:ApplyCommonRoute(index)
    local entry = (self.routes or self:GetCommonRoutes())[tonumber(index) or 0]
    if not entry then return false, "No hay una ruta común confirmada en esa posición." end
    local wanted = entry.guideID
    self.routesAt = nil
    local valid
    for _, current in ipairs(self:GetCommonRoutes()) do if current.guideID == wanted then valid = true end end
    if not valid then return false, "Han cambiado los datos; comprueba otra vez los requisitos de ambos." end
    if ns.char.activeGuide == wanted then return true, wanted end
    ns.char.adaptation = type(ns.char.adaptation) == "table" and ns.char.adaptation or {}
    local saved = ns.char.adaptation
    saved.bookmarks = type(saved.bookmarks) == "table" and saved.bookmarks or {}
    local previous = ns.char.activeGuide
    local state = ns.char.progress and ns.char.progress[previous]
    saved.bookmarks[#saved.bookmarks + 1] = { guideID=previous, cursor=state and state.cursor or 1, review=state and state.review }
    while #saved.bookmarks > 10 do table.remove(saved.bookmarks, 1) end
    ns.char.activeGuide, saved.lastChoice = wanted, wanted
    self:ClearFocus(); self:Invalidate()
    if ns.Adaptation and ns.Adaptation.Invalidate then ns.Adaptation:Invalidate() end
    return true, wanted
end
local stateNames = {[0]="no la lleva",[1]="en curso",[2]="lista para entregar",[3]="entregada"}
local function currentRecords(id, cursor, output, seen, mine, partner)
    local g = ns.guides and ns.guides[id]
    local step = g and g.steps and g.steps[tonumber(cursor) or 1]
    if not step then return end
    for _, goal in ipairs(step.goals or { step }) do
        local q = questID(goal)
        if q and not seen[q] and (only(step.only, mine) and only(goal.only, mine) or only(step.only, partner) and only(goal.only, partner)) then
            seen[q] = true; output[#output + 1] = {q=q,goal=goal,step=step,guide=g}
        end
    end
end
local function pickup(entry, who, owner, observation)
    local records = acceptRecords(entry.questID, who)
    if #records == 0 then
        entry.text = entry.text .. " No hay una recogida compatible publicada para su raza/clase; consulta el diario o el instructor."
        return
    end
    local chosen, ready, reason, missing, unknown
    for _, r in ipairs(records) do
        local ok, explanation, absent, uncertain = prerequisites(r.goal, who, owner, observation)
        if not chosen or ok == true then chosen,ready,reason,missing,unknown=r,ok,explanation,absent,uncertain end
        if ok == true then break end
    end
    local goal = chosen.goal
    entry.npcName, entry.npcID = goal.npcName or goal.objName, goal.npc or goal.object
    entry.missingQuestIDs, entry.unknownQuestIDs = missing, unknown
    entry.text = entry.text .. " " .. (entry.npcName and ("Recogida publicada: " .. entry.npcName .. ". ") or "La fuente no identifica al NPC de recogida. ") .. reason
    entry.sourceGuideID, entry.sourceStep = chosen.guide.id, chosen.stepIndex
    entry.recoveryPossible = ready == false and #missing > 0 and #unknown == 0
        and recoveryAvailable(goal, who, owner, observation) or false
    if entry.recoveryPossible then entry.text = entry.text .. " Hay acciones completas publicadas para las previas pendientes; comprueba Recuperación en el paso local bloqueado." end
    if owner == "mine" and ready == true and entry.npcID and entry.npcName and completeSource(chosen, who) and ns.GetGoalWaypoint then
        local point = read(ns.GetGoalWaypoint, ns, copy(goal))
        if type(point) == "table" and finite(point.mapID) and point.mapID>0 and finite(point.x) and finite(point.y)
            and point.x >= 0 and point.x <= 1 and point.y >= 0 and point.y <= 1 then
            entry.action, entry.waypoint = "pickup", copy(point)
            entry.text = entry.text .. " Puedes señalar esta recogida localmente y después cancelar el desvío para volver a tu objetivo."
        end
    end
    if not entry.action then entry.text = entry.text .. " No se propone un desvío automático; revisa los requisitos y la fuente." end
end
function P:GetDifferences()
    if not ns.char then return {} end
    local mine, partner, ctx, real = people()
    local stamp, identity = read(GetTime) or 0, key(mine, partner, ctx)
    if self.differencesAt and self.differencesKey == identity and stamp - self.differencesAt >= 0 and stamp - self.differencesAt < TTL then return self.differences end
    local results, observation, records = {}, observe(), {}
    if real then
        local id, seen = ns.char.activeGuide, {}
        local state = ns.char.progress and ns.char.progress[id]
        currentRecords(id, state and state.cursor, records, seen, mine, partner)
        currentRecords(ctx.guideID, ctx.cursor, records, seen, mine, partner)
        for _, record in ipairs(records) do
            local q = record.q
            local a, b = observation(q,"mine"), observation(q,"partner")
            local common = applies(record,mine) and applies(record,partner) and not profession(record.goal,record.step)
                and identityAllowed(record.guide, mine) and identityAllowed(record.guide, partner)
            local entry
            if not common then
                entry={questID=q,title=title(q,record.goal.title),owner=applies(record,mine) and "mine" or "partner",kind="individual",
                    text="Esta rama es individual por requisitos de guía, raza, clase, profesión o nivel. Cada uno conserva su cadena; no se compara como una misión compartida."}
            elseif not a then
                entry={questID=q,title=title(q,record.goal.title),owner="mine",kind="unknown",
                    text="El cliente no permite confirmar tu registro actual para esta misión. No se deduce una diferencia con tu amigo ni se propone una recogida."}
            elseif not b or b.basic then
                entry={questID=q,title=title(q,record.goal.title),owner="partner",kind="unknown",
                    text=b and b.basic and "El juego confirma que tu amigo la lleva, pero faltan sus objetivos y entregas recientes. No se supone que vaya al mismo ritmo."
                        or "Sin datos recientes del registro de tu amigo para esta misión. No se interpreta como ausente, completa ni entregada."}
            elseif a.state ~= b.state then
                local owner = a.state < b.state and "mine" or "partner"
                entry={questID=q,title=title(q,record.goal.title),owner=owner,kind="quest",
                    text="Tú: " .. stateNames[a.state] .. "; amigo: " .. stateNames[b.state] .. ". Cada entrega y cada recogida sigue siendo individual."}
                if a.state == 0 then pickup(entry,mine,"mine",observation)
                elseif b.state == 0 then pickup(entry,partner,"partner",observation) end
            end
            if entry and #results < 12 then results[#results + 1] = entry end
            if common and a and b and not b.basic and a.state > 0 and b.state > 0 and a.state < 3 and b.state < 3 and ns.Duo.GetObjectiveProgress then
                local localObjectives = read(C_QuestLog and C_QuestLog.GetQuestObjectives,q) or {}
                local indices, seen = {}, {}
                local function add(i) if finite(i) and i>=1 and i<=32 and not seen[i] then seen[i]=true;indices[#indices+1]=i end end
                for i in ipairs(localObjectives) do add(i) end
                for i in pairs(b.objectives or {}) do add(i) end
                add(record.goal.oi or record.goal.objective)
                table.sort(indices)
                for _, i in ipairs(indices) do
                    local progress = read(ns.Duo.GetObjectiveProgress,ns.Duo,q,i)
                    local ma, pa = progress and progress.mine, progress and progress.partner
                    if ma and pa and ma.known and pa.known and (ma.current ~= pa.current or ma.finished ~= pa.finished or ma.total ~= pa.total) and #results < 12 then
                        local function value(v) return v.finished and "completo" or (finite(v.current) and finite(v.total) and (v.current .. "/" .. v.total) or "pendiente") end
                        results[#results + 1]={questID=q,objectiveIndex=i,title=title(q,record.goal.title) .. " · objetivo " .. i,
                            owner=(ma.finished and not pa.finished or finite(ma.current) and finite(pa.current) and ma.current>pa.current) and "partner" or "mine",kind="objective",
                            text="Tú: " .. value(ma) .. "; amigo: " .. value(pa) .. ". Datos individuales observados; no se copia botín ni se completa el objetivo de otra persona."}
                    elseif (not ma or not ma.known) and #results < 12 then
                        results[#results + 1]={questID=q,objectiveIndex=i,title=title(q,record.goal.title) .. " · objetivo " .. i,owner="mine",kind="unknown",
                            text="Falta una muestra confirmada de tu contador local para este objetivo. No se deduce una diferencia con el compañero ni se da por completado."}
                    elseif (not pa or not pa.known) and #results < 12 then
                        results[#results + 1]={questID=q,objectiveIndex=i,title=title(q,record.goal.title) .. " · objetivo " .. i,owner="partner",kind="unknown",
                            text="Falta una muestra reciente de este objetivo del compañero. La ausencia de datos no prueba que le falte ni que lo haya completado."}
                    end
                end
            end
            if #results >= 12 then break end
        end
    end
    self.differences, self.differencesAt, self.differencesKey = results, stamp, identity
    return results
end
function P:FocusDifference(index)
    local selected = (self.differences or self:GetDifferences())[tonumber(index) or 0]
    if not selected or selected.owner ~= "mine" or selected.action ~= "pickup" then return false, "Solo puede señalarse una recogida local con fuente completa y requisitos confirmados." end
    local wanted = selected.questID
    self.differencesAt = nil
    local entry
    for _, candidate in ipairs(self:GetDifferences()) do
        if candidate.questID == wanted and candidate.owner == "mine" and candidate.action == "pickup" then entry=candidate;break end
    end
    if not entry then return false, "La recogida o sus requisitos han cambiado. Actualiza las diferencias." end
    if ns.char.recovery and ns.char.recovery.active then return false, "Vuelve de la recuperación actual antes de señalar otra recogida." end
    local point = copy(entry.waypoint)
    point.title, point.label, point.source = "Recoger: " .. entry.title, "Recogida: " .. entry.npcName, "duo-difference"
    point.questID, point.temporary = wanted, true
    local id = ns.char.activeGuide
    local state = ns.char.progress and ns.char.progress[id]
    self.focus = { point=point, guideID=id, cursor=state and state.cursor or 1 }
    if ns.Duo and ns.Duo.FollowMeeting then ns.Duo:FollowMeeting(false) end
    return true, point
end
function P:GetNavigationOverride()
    local focus, char = self.focus, ns.char
    if not focus then return nil end
    local guide = char and ns.guides and ns.guides[char.activeGuide]
    local state = char and char.progress and char.progress[char.activeGuide]
    local cursor = state and state.cursor or 1
    -- A pickup belongs to one selected route position. New navigation context
    -- and real acceptance/delivery invalidate it without any engine sync.
    local stale = not guide or char.activeGuide ~= focus.guideID or cursor ~= focus.cursor
        or guide.recovery or (type(char.recovery)=="table" and char.recovery.active)
    if not stale then
        local quest = observe()(focus.point.questID,"mine")
        stale = not quest or quest.state ~= 0
    end
    if stale then self:ClearFocus();return nil end
    -- Arrival alone never accepts a quest or changes guide progress.
    return focus.point
end
function P:ClearFocus()
    local had = self.focus ~= nil
    self.focus = nil
    return had, "Desvío cancelado; continúa el objetivo de tu guía conservada."
end
function P:GetReport()
    local _, _, _, real = people()
    if not real then return "Hace falta un dúo conectado, de la misma facción, con perfiles recientes de ambos. El registro desconocido del compañero no se da por comprobado." end
    local lines = {"Plan común: las elecciones afectan solo a tu personaje y conservan el progreso de ambos."}
    local routes = self:GetCommonRoutes()
    if #routes == 0 then lines[#lines+1]="No hay una ruta común suficientemente confirmada. Espera los registros recientes y revisa nivel, previas y zona; no se inventa un traslado." end
    for i, route in ipairs(routes) do lines[#lines+1]=i .. ". " .. route.title .. ": " .. route.text end
    local differences = self:GetDifferences()
    if #differences == 0 then lines[#lines+1]="Sin diferencias comprobadas en los pasos actuales; no confirma que todo el registro coincida." end
    for _, entry in ipairs(differences) do lines[#lines+1]=entry.title .. ": " .. entry.text end
    local focused = self:GetNavigationOverride()
    if focused then lines[#lines+1]="Desvío local señalado: " .. focused.label .. ". Usa Volver al objetivo para cancelarlo; no modifica la guía del amigo." end
    return table.concat(lines,"\n\n")
end

-- Automatic party planning is pure. The transport module negotiates a plan;
-- these helpers neither select a guide nor create/overwrite saved progress.
local function cursor(value, guide)
    return finite(value) and value==math.floor(value) and value>=1 and value<=#guide.steps+1 and value or nil
end
local function canonical(name, realm)
    if type(name)~="string" or name=="" then return nil end
    if realm and realm~="" and not name:find("-",1,true) then name=name.."-"..realm end
    if not name:find("-",1,true) then
        local localRealm=read(GetNormalizedRealmName) or read(GetRealmName)
        if localRealm then name=name.."-"..localRealm end
    end
    return name:gsub("%s",""):lower()
end
local function names(ctx)
    local name, realm=read(UnitFullName or UnitName,"player")
    return canonical(ctx.ownName) or canonical(name,realm) or "yo", canonical(ctx.partnerName) or "compañero"
end
local function reference(guideID,mine,partner,ctx,ownCursor,partnerCursor)
    local myName,hisName=names(ctx)
    if ownCursor and partnerCursor then
        if ownCursor<partnerCursor then return myName,ownCursor,"mine" end
        if partnerCursor<ownCursor then return hisName,partnerCursor,"partner" end
    end
    if mine.level<partner.level then return myName,ownCursor,"mine" end
    if partner.level<mine.level then return hisName,partnerCursor,"partner" end
    if myName<hisName then return myName,ownCursor,"mine" end
    return hisName,partnerCursor,"partner"
end
local function countText(value)
    if value and finite(value.current) and finite(value.total) then return value.current.."/"..value.total end
    return value and value.finished==true and "completo" or "sin contador confirmado"
end
local function goalObservation(goal,who,owner,observation)
    local kind,q=action(goal),questID(goal)
    if kind=="level" then
        local target=goal.level or goal.n
        if finite(target) and finite(who.level) then
            return {known=true,done=who.level>=target,status=who.level>=target and "done" or "active",reason="Nivel "..who.level.."/"..target}
        end
    end
    local item=q and observation(q,owner)
    if profession(goal) and (not item or item.state==0) then
        if owner~="mine" or not ns.CheckGoalProfession then
            return {known=false,done=false,status="blocked",reason="Profesión del compañero sin confirmar.",quest=item}
        end
        local ready,why=ns:CheckGoalProfession(goal)
        if ready==false then return {known=true,done=true,status="skip",reason=why,quest=item} end
        if ready==nil then return {known=false,done=false,status="blocked",reason=why,quest=item} end
    end
    if not q then return {known=false,done=false,status="manual",reason="Acción de viaje o servicio sin confirmación individual compartida."} end
    if not item or item.basic then return {known=false,done=false,status="blocked",reason="Registro individual sin confirmar.",quest=item} end
    if item.state==3 then return {known=true,done=true,status="done",reason="Entregada en su registro.",quest=item} end
    if kind=="accept" then
        if item.state>0 then return {known=true,done=true,status="done",reason="Aceptada en su registro.",quest=item} end
        local ready,why=prerequisites(goal,who,owner,observation)
        return {known=ready~=nil,done=false,status=ready==true and "active" or "blocked",reason=ready==true and "Debe aceptar la misión." or why,quest=item}
    end
    if item.state==0 then return {known=true,done=false,status="blocked",reason="La misión no está en su registro; necesita una recogida o recuperación comprobada.",quest=item} end
    if kind=="turnin" then return {known=true,done=false,status="active",reason=item.state==2 and "Lista para entregar individualmente." or "Todavía debe completar y entregar su misión.",quest=item} end
    if item.state==2 then return {known=true,done=true,status="done",reason="El juego confirma sus objetivos completos.",quest=item} end
    local oi=goal.oi or goal.objective
    if finite(oi) and oi>=1 and oi<=32 then
        local progress=ns.Duo and read(ns.Duo.GetObjectiveProgress,ns.Duo,q,oi)
        local value=type(progress)=="table" and progress[owner] or nil
        if value and value.known then return {known=true,done=value.finished==true,status=value.finished==true and "done" or "active",reason=countText(value),quest=item,objective=value} end
        if finite(item.total) and item.total>=oi and finite(item.mask) then
            local done=math.floor(item.mask/2^(oi-1))%2==1
            return {known=true,done=done,status=done and "done" or "active",reason=done and "Objetivo completado en su registro." or "Objetivo pendiente; cantidad sin confirmar.",quest=item}
        end
        return {known=false,done=false,status="blocked",reason="Contador de este objetivo sin confirmar.",quest=item}
    end
    return {known=true,done=false,status="active",reason="Misión en curso en su registro.",quest=item}
end
local function stepItems(g,stepIndex,mine,partner,observation)
    local step=g.steps[stepIndex]
    if not step then return {},"La guía no tiene un paso pendiente en esa posición." end
    local items,first={},nil
    local hasTask=false
    for _,goal in ipairs(step.goals or {step}) do if action(goal)~="note" then hasTask=true end end
    for i,goal in ipairs(step.goals or {step}) do
        local record={goal=goal,step=step,guide=g}
        local a,b=applies(record,mine),applies(record,partner)
        local item={goal=goal,index=i,action=action(goal) or "manual",questID=questID(goal),title=goal.title or step.title,
            appliesMine=a,appliesPartner=b,individual=not(a and b) or profession(goal,step)~=nil,optional=goal.optional==true}
        item.mine=a and goalObservation(goal,mine,"mine",observation) or {known=true,done=false,status="skip",reason="Rama de otra raza o clase."}
        item.partner=b and goalObservation(goal,partner,"partner",observation) or {known=true,done=false,status="skip",reason="Rama de otra raza o clase."}
        item.known=(not a or item.mine.known) and (not b or item.partner.known)
        if item.individual or item.optional then
            item.status="skip"
            item.reason=item.individual and "Rama individual: cada personaje conserva sus requisitos de raza, clase o profesión; no se marca completada para el otro." or "Objetivo opcional; no se exige como avance común."
        elseif item.action=="note" and hasTask then
            item.status,item.known,item.reason="skip",true,"Información del autor; no representa una misión completada."
        elseif not item.known then
            item.status,item.reason="blocked","Faltan datos individuales recientes; no se supone que el objetivo esté hecho."
        elseif item.mine.done and item.partner.done then
            item.status,item.reason="done","Ambos registros confirman esta acción."
        elseif item.mine.status=="blocked" or item.partner.status=="blocked" then
            item.status,item.reason="blocked","Hay un requisito individual pendiente."
        elseif item.mine.status=="manual" or item.partner.status=="manual" then
            item.status,item.reason="manual","Esta acción requiere comprobación manual en cada personaje."
        else item.status,item.reason="active","Ayuda al personaje que aún tiene esta acción pendiente." end
        item.subtitle=item.reason.." Tú: "..item.mine.reason.." Amigo: "..item.partner.reason
        item.owner=item.mine.done and not item.partner.done and "partner" or (item.partner.done and not item.mine.done and "mine" or "both")
        if not first and item.status~="done" and item.status~="skip" then first=i;item.isCurrent=true end
        items[#items+1]=item
    end
    return items
end
function P:GetSharedGoalItems(guideID,sharedCursor)
    local mine,partner,_,real=people()
    local g=ns.guides and ns.guides[guideID]
    local position=g and cursor(sharedCursor,g)
    if not real then return {},"Faltan perfiles recientes de un dúo conectado." end
    if not g or not position or not identityAllowed(g,mine) or not identityAllowed(g,partner) then return {},"La guía o sus condiciones no son compatibles con ambos." end
    return stepItems(g,position,mine,partner,observe())
end
function P:GetSharedStepStatus(guideID,sharedCursor)
    local items,reason=self:GetSharedGoalItems(guideID,sharedCursor)
    local result={items=items,known=true,complete=true,status="done",reason=reason,individualOnly=true}
    local pending
    if #items==0 then result.known,result.complete,result.status=false,false,"unknown";return result end
    for _,item in ipairs(items) do
        if not item.individual and not item.optional and not(item.action=="note" and item.status=="skip") then
            result.individualOnly=false
            if item.status~="done" then result.complete=false;if not pending then pending=item end end
        end
    end
    if result.individualOnly then
        result.complete,result.status=false,"individual"
        result.reason="Este paso tiene ramas individuales; ayudan al compañero sin dar por terminadas tus misiones de clase."
        local mine,partner,ctx=people()
        local saved=ns.char and ns.char.activeGuide==guideID and ns.char.progress and ns.char.progress[guideID]
        local _,_,owner=reference(guideID,mine,partner,ctx,saved and saved.cursor,ctx.guideID==guideID and ctx.cursor or nil)
        for _,item in ipairs(items) do
            local applicable,value
            if owner=="partner" then applicable,value=item.appliesPartner,item.partner else applicable,value=item.appliesMine,item.mine end
            if applicable and not value.known then
                result.known,result.status,result.reason=false,"unknown","Faltan datos de la rama individual del personaje de referencia; no se supone completada."
            end
        end
    elseif pending and not pending.known then result.known,result.status,result.reason=false,"unknown",pending.subtitle
    elseif result.complete then result.reason="Ambos registros confirman los objetivos comunes de este paso."
    elseif pending then result.status,result.reason=pending.status,pending.subtitle
    else result.reason=result.reason or "Hay acciones individuales pendientes en el paso común." end
    return result
end
local function ownProjection(g,mine,observation)
    local saved=ns.char and ns.char.progress and ns.char.progress[g.id]
    local existing=type(saved)=="table" and cursor(saved.cursor,g)
    if existing then return existing,true,"saved" end
    for si,step in ipairs(g.steps) do
        local pending,unknown=false,false
        local hasTask=false
        for _,goal in ipairs(step.goals or {step}) do
            if applies({goal=goal,step=step},mine) and action(goal)~="note" then hasTask=true end
        end
        for _,goal in ipairs(step.goals or {step}) do
            if applies({goal=goal,step=step},mine) and not goal.optional and not(action(goal)=="note" and hasTask) then
                local state=goalObservation(goal,mine,"mine",observation)
                if not state.known then unknown=true end
                if not state.done then pending=true end
            end
        end
        -- Never jump to an isolated active/delivered later quest. Every
        -- previous required action must have its own local evidence.
        if unknown then return 1,false,"unknown" end
        if pending then return si,true,"local-prefix" end
    end
    return #g.steps+1,true,"local-prefix"
end
local function routeByID(id)
    for _,route in ipairs(catalog().guides) do if route.guide.id==id then return route end end
end
local function automaticGuide(id,mine,partner,ctx,observed)
    local route=routeByID(id)
    local g=route and route.guide
    if not guideAllowed(g,mine) or not guideAllowed(g,partner) then return nil,"Nivel mínimo, facción, raza o clase incompatibles con ambos." end
    local observation=observed or observe()
    local ownCursor,ownObserved,ownSource=ownProjection(g,mine,observation)
    local partnerCursor=ctx.guideID==id and cursor(ctx.cursor,g) or nil
    local ownCurrent=ns.char and ns.char.activeGuide==id and cursor(ownCursor,g) or nil
    local pointCursor
    if ownCurrent and partnerCursor then pointCursor=math.min(ownCurrent,partnerCursor)
    else pointCursor=partnerCursor or ownCurrent end
    local candidates,seen={},{}
    local function add(si) if si and not seen[si] and si<=#g.steps then seen[si]=true;candidates[#candidates+1]=si end end
    add(pointCursor)
    if not pointCursor then
        -- New-route evidence may locate a common point, but NEVER becomes
        -- the local saved cursor (ownProjection independently handles that).
        for _,q in ipairs(route.entries) do
            local a=observation(q,"mine")
            if a and a.state>0 and a.state<3 then
                local b=observation(q,"partner")
                if b and b.state>0 and b.state<3 then
                    for _,r in ipairs(route.quests[q]) do if applies(r,mine) and applies(r,partner) then add(r.stepIndex);break end end
                end
            end
        end
        if #candidates==0 and g.zone==mine.map and g.zone==partner.map then add(1) end
    end
    local lastReason="No hay un paso común confirmado; termina los inicios individuales y espera datos recientes."
    local _,_,referenceOwner=reference(id,mine,partner,ctx,ownCurrent,partnerCursor)
    for _,si in ipairs(candidates) do
        local items=stepItems(g,si,mine,partner,observation)
        local any,valid,individual,pending=false,true,false,nil
        for _,item in ipairs(items) do
            if item.individual then
                local current,applicable
                if referenceOwner=="partner" then current,applicable=item.partner,item.appliesPartner
                else current,applicable=item.mine,item.appliesMine end
                if applicable and current.known and current.status~="blocked" then individual=true
                elseif applicable and not current.known then lastReason="Falta confirmar la rama individual del personaje rezagado." end
            elseif not item.optional and not(item.action=="note" and item.status=="skip") then
                any=true
                if not pending and item.status~="done" then pending=item end
            end
        end
        if pending and (not pending.known or pending.status=="blocked" or pending.status=="manual") then valid=false;lastReason=pending.subtitle end
        if valid and (any or individual) then
            local refName,refCursor,refOwner=reference(id,mine,partner,ctx,ownCurrent,partnerCursor)
            if not refCursor then refCursor=si end
            local myName,hisName=names(ctx)
            local lowName=mine.level<partner.level and myName or (partner.level<mine.level and hisName or (myName<hisName and myName or hisName))
            local behindGuide=mine.level<partner.level and (ns.char and ns.char.activeGuide) or (partner.level<mine.level and ctx.guideID or nil)
            local score=(id==(ns.char and ns.char.activeGuide) and 100 or 0)+(id==ctx.guideID and 100 or 0)
                +(id==behindGuide and 100 or 0)+(g.zone==mine.map and 40 or 0)+(g.zone==partner.map and 40 or 0)
                -math.abs(math.min(mine.level,partner.level)-(g.minLevel or 1))
            return {guideID=id,verified=true,referenceName=refName or lowName,referenceOwner=refOwner,
                referenceCursor=refCursor or si,sharedCursor=refCursor or si,ownCursor=ownCursor,partnerCursor=partnerCursor,
                ownCursorObserved=ownObserved,ownCursorSource=ownSource,referenceLevel=math.min(mine.level,partner.level),
                individualOnly=not any,rank=score,reason="Referencia observada del personaje rezagado; conserva el progreso propio y sus cadenas individuales."}
        end
    end
    return nil,lastReason
end
function P:ValidateAutomaticGuide(guideID)
    local mine,partner,ctx,real=people()
    if not real then return false,"Faltan perfiles recientes de ambos jugadores en el mismo grupo." end
    local plan,reason=automaticGuide(guideID,mine,partner,ctx)
    if not plan then return false,reason end
    return true,plan.reason,plan
end
function P:GetAutomaticPlan()
    local mine,partner,ctx,real=people()
    if not real then return nil,"Faltan perfiles recientes de ambos jugadores en el mismo grupo." end
    local stamp,identity=read(GetTime) or 0,key(mine,partner,ctx)
    if self.automaticAt and self.automaticKey==identity and stamp-self.automaticAt>=0 and stamp-self.automaticAt<TTL then return self.automaticPlan,self.automaticReason end
    local plans,lastReason,observation={},"No hay una guía común comprobada para los dos inicios, niveles y registros.",observe()
    for _,route in ipairs(catalog().guides) do
        if guideAllowed(route.guide,mine) and guideAllowed(route.guide,partner) then
            local plan,reason=automaticGuide(route.guide.id,mine,partner,ctx,observation)
            if plan then plans[#plans+1]=plan elseif reason then lastReason=reason end
        end
    end
    table.sort(plans,function(a,b) return a.rank==b.rank and a.guideID<b.guideID or a.rank>b.rank end)
    self.automaticPlan,self.automaticReason,self.automaticAt,self.automaticKey=plans[1],plans[1] and plans[1].reason or lastReason,stamp,identity
    return self.automaticPlan,self.automaticReason
end
local function authoredPoint(goal,who)
    local selected=goal
    if goal.candidates and #goal.candidates>0 then
        selected=nil
        local code=who.faction=="Alliance" and "A" or "H"
        for _,candidate in ipairs(goal.candidates) do
            if (not candidate.faction or candidate.faction=="AH" or candidate.faction==code or candidate.faction==who.faction)
                and only(candidate,who) then selected=candidate;if candidate.map==who.map then break end end
        end
        if not selected then return nil end
    end
    local raw=copy(selected)
    raw.quest,raw.questID,raw.candidates,raw.only=nil,nil,nil,nil
    raw.classes,raw.races=nil,nil
    raw.t=action(goal)
    local point=ns.ResolveWaypointPoint and read(ns.ResolveWaypointPoint,ns,raw)
    -- With the quest removed the existing resolver can use a learned NPC or
    -- authored point, never our completed quest's live turn-in waypoint.
    if not point and ns.GetGoalWaypoint then point=read(ns.GetGoalWaypoint,ns,raw) end
    if type(point)~="table" or not finite(point.mapID) or point.mapID<=0 or not finite(point.x) or not finite(point.y)
        or point.x<0 or point.x>1 or point.y<0 or point.y>1 then return nil end
    return copy(point),selected.npcName or selected.objName or goal.npcName or goal.objName
end
function P:GetSharedWaypoint(guideID,sharedCursor)
    local mine,partner,ctx,real=people()
    if not real then return nil,"Falta un compañero conectado con perfil reciente." end
    local g=ns.guides and ns.guides[guideID]
    if not g or not cursor(sharedCursor,g) then return nil,"Paso común no disponible." end
    local items,reason=self:GetSharedGoalItems(guideID,sharedCursor)
    local own=ns.char and ns.char.activeGuide==guideID and ns.char.progress and ns.char.progress[guideID]
    local ownCursor=type(own)=="table" and cursor(own.cursor,g) or nil
    local partnerCursor=ctx.guideID==guideID and cursor(ctx.cursor,g) or nil
    local refName,_,refOwner=reference(guideID,mine,partner,ctx,ownCursor,partnerCursor)
    local selected,who
    for _,item in ipairs(items) do
        if not item.individual and not item.optional and item.status~="skip" and item.status~="done" then
            local service=not item.questID and item.action=="train"
            if not service and (not item.known or item.status=="blocked" or item.status=="manual") then return nil,item.subtitle end
            selected=item
            if item.owner=="partner" then who=partner;refName=select(2,names(ctx))
            elseif item.owner=="mine" then who=mine;refName=names(ctx)
            else who=refOwner=="partner" and partner or mine end
            break
        end
    end
    if not selected then
        -- Class errands do not become shared prerequisites. A helper may
        -- still see the authored NPC applicable to the reference character.
        for _,item in ipairs(items) do
            local candidate=refOwner=="partner" and item.partner or item.mine
            local appliesToReference
            if refOwner=="partner" then appliesToReference=item.appliesPartner else appliesToReference=item.appliesMine end
            local service=not item.questID and item.action=="train"
            if item.individual and appliesToReference and candidate and not candidate.done and (service or candidate.known and candidate.status~="blocked") then
                selected,who=item,refOwner=="partner" and partner or mine;break
            end
        end
    end
    if not selected then return nil,reason or "No hay un objetivo pendiente confirmado para señalar." end
    local point,npc=authoredPoint(selected.goal,who)
    if not point then return nil,"La fuente no ofrece una posición compatible confirmada para ese personaje." end
    point.source,point.guideID,point.sharedCursor,point.goalIndex="duo-follow",guideID,sharedCursor,selected.index
    point.questID,point.referenceName,point.goalTitle=selected.questID,refName,selected.title
    point.goal=selected.goal
    point.label="Ayudar a "..refName..": "..selected.title..(npc and (" · "..npc) or "")
    point.title,point.individual=point.label,selected.individual
    point.requiresConfirmation=not selected.known or selected.action=="train"
    return point
end
