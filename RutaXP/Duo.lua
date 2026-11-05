local _, ns = ...
-- Only opt-in PARTY addon messages. A peer's state never completes our quests.
-- Current Forever API references (feature-detected; unreadable means unknown):
-- github.com/Gethe/wow-ui-source/blob/forever/Interface/AddOns/Blizzard_APIDocumentationGenerated/QuestLogDocumentation.lua#L1512
-- github.com/Gethe/wow-ui-source/blob/forever/Interface/AddOns/Blizzard_APIDocumentationGenerated/ContainerDocumentation.lua#L279
-- github.com/Gethe/wow-ui-source/blob/forever/Interface/AddOns/Blizzard_APIDocumentationGenerated/UnitDocumentation.lua#L2649
-- github.com/Gethe/wow-ui-source/blob/forever/Interface/AddOns/Blizzard_UIPanels_Game/Camelot/PaperDollFrame.lua#L1598
local Duo = { prefix = "RXPDUO3", elapsed = 0, sendElapsed = 0, sequence = 0, remoteQuests = {}, requested = {}, outboundRequests = {} }
ns.Duo = Duo
local PROTOCOL, QUEST_TTL, REQUEST_LIMIT, CACHE_LIMIT = "2", 35, 24, 48
local function readable(value)
    if issecretvalue and issecretvalue(value) then return nil end
    return value
end
local function safe(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, a, b, c, d = pcall(fn, ...)
    if ok then
        if issecretvalue then
            if issecretvalue(a) then a = nil end
            if issecretvalue(b) then b = nil end
            if issecretvalue(c) then c = nil end
        end
        return a, b, c, readable(d)
    end
end
local function now() return safe(GetTime) or 0 end
local function integer(value, low, high)
    value = readable(value)
    local n = tonumber(value)
    if n and n == math.floor(n) and n >= low and n <= high then return n end
end
local function fresh(seen, ttl) return type(seen) == "number" and now() >= seen and now() - seen <= (ttl or QUEST_TTL) end
local function unknown(value) return value == nil and "?" or tostring(value) end
local function boolean(value) if value == "1" then return true elseif value == "0" then return false end end
local function encodeBoolean(value) return value == true and "1" or value == false and "0" or "?" end
local function suppliesFields(fields, first)
    local ranges, data = { {0, 10000}, {0, 10000}, {0, 100}, {0, 100}, {1, 100} }, {}
    for index, range in ipairs(ranges) do
        local raw = fields[first + index - 1]
        data[index] = integer(raw, range[1], range[2])
        if raw ~= "?" and not data[index] then return nil end
    end
    if (data[1] == nil) ~= (data[2] == nil) or (data[1] and data[1] > data[2]) then return nil end
    local result = { known = true, seen = now(), freeSlots = data[1], totalSlots = data[2],
        bagsKnown = data[1] ~= nil, durabilityPercent = data[3], manaPercent = data[4], level = data[5] }
    if data[4] then result.manaLow = data[4] <= 25 end
    return result
end
local function token(s) return type(s) == "string" and s:match("^[%w_/%-%.:]+$") and #s <= 100 end
local function conditionToken(value)
    local normalized = tostring(value or ""):lower():gsub("[%s_%-]", "")
    if normalized == "undead" then return "scourge" end
    if normalized:find("skyborne", 1, true) then return "skyborne" end
    return normalized
end
local function matches(values, actual)
    if not values or #values == 0 then return true end
    if not actual or actual == "" then return false end
    local included, found = false, false
    for _, value in ipairs(values) do
        value = tostring(value)
        if value:sub(1, 1) == "!" then
            if conditionToken(value:sub(2)) == conditionToken(actual) then return false end
        else
            included = true
            if conditionToken(value) == conditionToken(actual) then found = true end
        end
    end
    return not included or found
end
local function appliesToPartner(only, context)
    return not only or (matches(only.classes, context.partnerClass) and matches(only.races, context.partnerRace)
        and matches(only.factions, context.partnerFaction))
end
local function canonical(name)
    name = readable(name)
    if type(name) ~= "string" then return nil end
    name = name:gsub("%s", ""):lower()
    if not name:find("-", 1, true) then
        local realm = safe(GetNormalizedRealmName) or safe(GetRealmName) or ""
        name = name .. "-" .. realm:gsub("%s", ""):lower()
    end
    return name
end
local function identityText(value)
    value = readable(value)
    return type(value) == "string" and value ~= "" and value ~= UNKNOWNOBJECT and #value <= 240 and value or nil
end
local function identityRead(fn, unit)
    if type(fn) ~= "function" then return nil, nil, false end
    local ok, name, server = pcall(fn, unit)
    if not ok then return nil, nil, false end
    if issecretvalue and (issecretvalue(name) or issecretvalue(server)) then return nil, nil, true end
    return name, server, false
end
local function fullNameParts(unit)
    local name, realm, hidden = identityRead(UnitFullName, unit)
    if hidden or (UNKNOWNOBJECT and name == UNKNOWNOBJECT) or name == "" then return nil, nil, hidden end
    if identityText(name) then return name, identityText(realm), false end
    name, _, hidden = identityRead(NameUtil and NameUtil.GetUnmodifiedUnitFullName, unit)
    if hidden then return nil, nil, true end
    if identityText(name) then return name, nil, false end
    name, realm, hidden = identityRead(UnitName, unit)
    return identityText(name), identityText(realm), hidden
end
local function unitName(unit)
    local name, realm, hidden = fullNameParts(unit)
    if not name or hidden then return nil end
    return canonical(realm and realm ~= "" and (name .. "-" .. realm) or name)
end
local function aliasKey(value)
    value = identityText(value)
    -- Authentication preserves the first/surname boundary. The historical
    -- canonical key above is for saved records, never a partial-name match.
    return value and value:lower():gsub("%s+", " "):gsub("^ ", ""):gsub(" $", "")
end
local function regionalName(unit)
    local full, _, hidden = identityRead(NameUtil and NameUtil.GetUnmodifiedUnitFullName, unit)
    if hidden then return nil, true end
    local camelot = WOW_PROJECT_ID and WOW_PROJECT_ID == (WOW_PROJECT_CAMELOT or 18)
    local regional = safe(RegionalUniqueNamesEnabled) == true or camelot
    local separator = Constants and Constants.CharacterNameSeparatorConsts
        and Constants.CharacterNameSeparatorConsts.CHARACTERNAME_SURNAME_SEPARATOR or " "
    if regional and identityText(full) and type(separator) == "string" and separator ~= "" and full:find(separator, 1, true) then return full, false end
    return nil, false
end
local function unitFingerprint(unit)
    local name, realm, hidden = fullNameParts(unit)
    if hidden or not name then return nil end
    local regional, restricted = regionalName(unit)
    if restricted then return nil end
    local server = realm or identityText(safe(GetNormalizedRealmName)) or identityText(safe(GetRealmName)) or ""
    return aliasKey(regional or name) .. "\031" .. server:gsub("[%s%-]", ""):lower()
end
local function senderIsUnit(sender, unit)
    local key = aliasKey(sender)
    if not key then return false end
    local name, realm, hidden = fullNameParts(unit)
    if not name or hidden then return false end
    local aliases = {}
    local localRealm = identityText(safe(GetNormalizedRealmName)) or identityText(safe(GetRealmName))
    local function add(value) local candidate = aliasKey(value); if candidate then aliases[candidate] = true end end
    local function forms(value, regional)
        if not identityText(value) then return end
        local server = realm or localRealm
        if regional or not realm or not localRealm or realm:gsub("[%s%-]", ""):lower() == localRealm:gsub("[%s%-]", ""):lower() then add(value) end
        if server then add(value .. "-" .. server); add(value .. "-" .. server:gsub("[%s%-]", "")) end
    end
    local regional, restricted = regionalName(unit)
    if restricted then return false end
    if regional then
        -- Camelot's official helper supplies the complete regional identity.
        -- Accept its chat-link spelling as another complete alias, not the
        -- ambiguous first name or a whitespace-stripped concatenation.
        forms(regional, true)
        forms(safe(C_NameUtil and C_NameUtil.ReplaceSurnameSeparatorWithLinkSeparator, regional), true)
    else forms(name) end
    return aliases[key] == true
end
local function transport(self)
    if not self.transport then self.transport = { attempts=0, accepted=0, failed=0, receivedHeaders=0, unmatchedHeaders=0 } end
    return self.transport
end
local function increment(value) return math.min(99999, (value or 0) + 1) end
local function resultName(result, names, reasons)
    for field, reason in pairs(reasons) do if names and names[field] == result then return reason end end
end
function Duo:RegisterPrefix()
    if self.registered then return true end
    if self.lastRegisterAt and now() - self.lastRegisterAt < 1 then return false end
    if not (C_ChatInfo and type(C_ChatInfo.RegisterAddonMessagePrefix) == "function") then
        self.registrationError = "El cliente no ofrece registro de mensajes de addons."; return false
    end
    self.lastRegisterAt = now()
    local ok, result = pcall(C_ChatInfo.RegisterAddonMessagePrefix, self.prefix)
    local names = Enum and Enum.RegisterAddonMessagePrefixResult
    local success, duplicate = names and names.Success or 0, names and names.DuplicatePrefix or 1
    local hidden = issecretvalue and issecretvalue(result)
    local accepted = ok and not hidden
        and (result == nil or result == true or result == success or result == duplicate)
    local checked = safe(C_ChatInfo.IsAddonMessagePrefixRegistered, self.prefix)
    self.registered = ok and (checked == true or checked ~= false and accepted) or false
    if self.registered then self.registrationError = nil; return true end
    self.registrationError = not ok and "Error al registrar el canal de RutaXP."
        or hidden and "El juego no permite confirmar el registro de RutaXP."
        or resultName(result, names or {InvalidPrefix=2,MaxPrefixes=3}, {
            InvalidPrefix="El juego rechazó el prefijo de RutaXP.", MaxPrefixes="El juego no admite más prefijos de addons." })
        or "El canal de RutaXP no se ha registrado todavía."
    return false
end
function Duo:GetTransportStatus()
    local info, time = transport(self), now()
    local function age(seen) return type(seen) == "number" and math.max(0, time-seen) or nil end
    return { registered=self.registered == true, attempts=info.attempts, accepted=info.accepted, failed=info.failed,
        lastError=info.lastError or self.registrationError, lastResult=info.lastResult,
        lastAttemptAge=age(info.lastAttempt), lastSuccessAge=age(info.lastSuccess),
        receivedHeaders=info.receivedHeaders, unmatchedHeaders=info.unmatchedHeaders,
        lastHeaderAge=age(info.lastHeader), lastUnmatchedHeaderAge=age(info.lastUnmatchedHeader) }
end
local function profile(unit)
    local _, class = safe(UnitClass, unit)
    local _, race = safe(UnitRace, unit)
    return safe(UnitLevel, unit), class, race
end
function Duo:AppliesToPartner(conditions)
    return appliesToPartner(conditions, self:GetContext())
end
function Duo:Settings()
    if not ns.char then return nil end
    if type(ns.char.duo) ~= "table" then ns.char.duo = { enabled = false, wait = false } end
    return ns.char.duo
end
function Duo:ClearPeer()
    self.lastTravelSignal, self.lastTravelSent = nil, nil
    self.transport = nil
    self.peer, self.remoteQuests, self.requested, self.outboundRequests = nil, {}, {}, {}
    self.remoteSupplies, self.remoteCheckpoint, self.partnerMeeting = nil, nil, nil
    self.lastSentMeeting, self.lastSentSupplies, self.lastSentCheckpoint, self.lastSentRequest = nil, nil, nil, nil
    self.lastHeader, self.lastSentHeader, self.rotation = nil, nil, 0
    self.lastSentQuest, self.objectiveRotation = nil, {}
    self.autoQueue, self.lastSentAuto = nil, nil
end
function Duo:RefreshRoster()
    local members = safe(GetNumGroupMembers) or 0
    local identity = members == 2 and not safe(IsInRaid) and unitFingerprint("party1") or nil
    local name = identity and unitName("party1") or nil
    local faction = safe(UnitFactionGroup, "party1")
    if faction and faction ~= "Neutral" and faction ~= safe(UnitFactionGroup, "player") then name, identity = nil, nil end
    if name ~= self.partnerName or identity ~= self.partnerIdentity then
        self:ClearPeer(); self.partnerName, self.partnerIdentity = name, identity
    end
    self.groupSize = members
    self.online = name ~= nil and safe(UnitIsConnected, "party1") ~= false
    if not self.online and self.peer then self:ClearPeer() end
end
function Duo:CanCommunicate()
    if not self.registered then self:RegisterPrefix() end
    if not (C_ChatInfo and C_ChatInfo.SendAddonMessage and self.registered) then return false, "Este cliente no ofrece comunicación entre addons." end
    if safe(C_ChatInfo.AreOutgoingAddonChatMessagesRestricted) == true or safe(C_ChatInfo.InChatMessagingLockdown) == true then
        return false, "El cliente restringe los mensajes de addons; solo se muestra la información que permite el juego."
    end
    return true
end
function Duo:SetEnabled(enabled)
    local settings = self:Settings()
    if not settings then return end
    settings.enabled = not not enabled
    self.ready = false
    self:ClearPeer()
    self:RefreshRoster()
    self:Changed()
end
function Duo:SetWait(value)
    local settings = self:Settings()
    if settings then settings.wait = not not value; self:Changed() end
end
function Duo:SetReady(value) self.ready = not not value; self.lastSentHeader = nil; self:Changed() end
function Duo:Changed()
    if ns.Adaptation and ns.Adaptation.Invalidate then ns.Adaptation:Invalidate() end
    if ns.initialized and ns.Sync and not self.changing then
        self.changing = true; ns:Sync(); self.changing = nil
    end
end
function Duo:NavigationChanged()
    if ns.Adaptation and ns.Adaptation.Invalidate then ns.Adaptation:Invalidate() end
    if ns.DuoPlanner and ns.DuoPlanner.Invalidate then ns.DuoPlanner:Invalidate() end
    if ns.UpdateNavigation then ns:UpdateNavigation() end
    if ns.initialized and ns.RefreshUI then ns:RefreshUI() end
end
function Duo:GetContext()
    local settings = self:Settings() or {}
    self:RefreshRoster()
    local recent = self.peer and fresh(self.peer.seen, 15)
    local headerRecent = self.peer and fresh(self.peer.headerSeen or self.lastHeader, 15)
    local level, class, race = profile("party1")
    local mapID = integer(safe(C_Map and C_Map.GetBestMapForUnit, "player"), 1, 100000)
    local inRange, checked = safe(UnitInRange, "party1")
    local dead = self.partnerName and safe(UnitIsDeadOrGhost, "party1")
    if headerRecent and self.peer.dead == true then dead = true end
    local context = { enabled = settings.enabled == true, known = recent and true or false,
        online = self.online, sameParty = self.partnerName ~= nil, groupSize = self.groupSize,
        partnerName = self.partnerName, partnerMapID = headerRecent and self.peer.mapID or nil, mapID = mapID,
        partnerLevel = (recent and self.peer.level) or (self.partnerName and level),
        partnerClass = (recent and self.peer.class) or (self.partnerName and class),
        partnerRace = (recent and self.peer.race) or (self.partnerName and race),
        partnerFaction = self.partnerName and safe(UnitFactionGroup, "party1"),
        ready = self.ready == true, partnerReady = recent and self.peer.ready == true,
        guideID = recent and self.peer.guideID, cursor = recent and self.peer.cursor,
        partnerAutoCompatible = headerRecent and self.peer.autoCapability == "1" or false,
        partnerAutoPair = headerRecent and self.peer.autoPair == true or false,
        partnerAutoEpoch = headerRecent and self.peer.autoEpoch or nil,
        partnerReview = headerRecent and self.peer.review == true or false,
        partnerAtWestfall = headerRecent and fresh(self.peer.travelSeen, 18) and self.peer.travelReady == true or false,
        ownName = unitName("player"), partnerNonce = recent and self.peer.nonce or nil,
        wait = settings.wait == true, dead = dead == true,
        separated = self.partnerName and checked == true and inRange == false or nil }
    context.differentZone = headerRecent and mapID and context.partnerMapID and mapID ~= context.partnerMapID or false
    return context
end
function Duo:PruneQuestCaches()
    local time = now()
    for id, seen in pairs(self.requested) do
        if type(seen) ~= "number" or time - seen > QUEST_TTL or time < seen then self.requested[id] = nil end
    end
    for id, quest in pairs(self.remoteQuests) do
        if time - quest.seen > QUEST_TTL or time < quest.seen then self.remoteQuests[id] = nil end
        for index, objective in pairs(quest.objectives or {}) do
            if not fresh(objective.seen) then quest.objectives[index] = nil end
        end
    end
    for id, seen in pairs(self.outboundRequests) do if not fresh(seen) then self.outboundRequests[id] = nil end end
end
local function makeRoom(cache, limit, timestamp)
    local count, oldestID, oldest = 0, nil, math.huge
    for id, entry in pairs(cache) do
        count = count + 1
        local seen = timestamp and entry[timestamp] or entry
        if seen < oldest or (seen == oldest and (not oldestID or id < oldestID)) then oldestID, oldest = id, seen end
    end
    if count >= limit and oldestID then cache[oldestID] = nil end
end
function Duo:GetLocalQuestIDs()
    local ids, set = {}, {}
    local function add(q)
        q = integer(q, 1, 10000000)
        if q and not set[q] and #ids < 24 then set[q] = true; ids[#ids + 1] = q end
    end
    local guide = ns.char and ns.guides[ns.char.activeGuide]
    local state = guide and ns.char.progress[guide.id]
    local step = guide and guide.steps[state and state.cursor or 1]
    if step and (not step.only or not ns.MatchesConditions or ns:MatchesConditions(step.only)) then
        add(step.questID)
        for _, goal in ipairs(step.goals or {}) do
            if not goal.only or not ns.MatchesConditions or ns:MatchesConditions(goal.only) then add(goal.quest or goal.questID) end
        end
    end
    return ids, set
end
function Duo:GetQuestIDs()
    self:PruneQuestCaches()
    local localIDs, localSet = self:GetLocalQuestIDs()
    local ids, set = {}, {}
    local function add(id)
        if id and not set[id] and #ids < REQUEST_LIMIT then set[id] = true; ids[#ids + 1] = id end
    end
    local guide = ns.char and ns.guides[ns.char.activeGuide]
    local state = guide and ns.char.progress[guide.id]
    local step = guide and guide.steps[state and state.cursor or 1]
    local active = step and ns.GetActiveGoal and ns:GetActiveGoal(step, state)
    local activeID = active and (active.quest or active.questID)
    if localSet[activeID] then add(activeID) end
    -- A fresh header identifies the peer's actual current visit. Answer those
    -- quests before exploratory planner requests: numeric sorting of a full
    -- request cache otherwise starves later IDs such as Talin's quest 234.
    local ctx = self:GetContext()
    local peerGuide = ctx.known and self.peer and fresh(self.peer.headerSeen or self.lastHeader, 15)
        and ns.guides[ctx.guideID]
    local peerStep = peerGuide and peerGuide.steps[integer(ctx.cursor, 1, #peerGuide.steps)]
    if peerStep and appliesToPartner(peerGuide, ctx) and appliesToPartner(peerGuide.only, ctx)
        and appliesToPartner(peerStep.only, ctx) then
        add(integer(peerStep.questID, 1, 10000000))
        for _, goal in ipairs(peerStep.goals or {}) do
            if appliesToPartner(goal.only, ctx) then add(integer(goal.quest or goal.questID, 1, 10000000)) end
        end
    end
    for _, id in ipairs(localIDs) do add(id) end
    local extra = {}
    for id in pairs(self.requested) do extra[#extra + 1] = id end
    table.sort(extra)
    for _, id in ipairs(extra) do add(id) end
    return ids
end
function Duo:LocalQuest(id)
    local delivered = ns.IsQuestDelivered and ns:IsQuestDelivered(id) == true
    local flag = safe(C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted, id)
    if flag == nil then flag = safe(IsQuestFlaggedCompleted, id) end
    if flag == true then delivered = true end
    local activeValue = safe(C_QuestLog and C_QuestLog.IsOnQuest, id)
    local active = activeValue == true
    local known = delivered == true or active or (activeValue == false and flag == false)
    local complete = safe(C_QuestLog and C_QuestLog.IsComplete, id) == true
        or safe(C_QuestLog and C_QuestLog.ReadyForTurnIn, id) == true
    local done, total, mask, objectives = 0, 0, 0, {}
    for index, objective in ipairs(safe(C_QuestLog and C_QuestLog.GetQuestObjectives, id) or {}) do
        total = total + 1
        local finished = readable(objective.finished)
        if type(finished) ~= "boolean" then finished = nil end
        if finished == true then
            done = done + 1
            if index <= 32 then mask = mask + 2 ^ (index - 1) end
        end
        if index <= 32 then
            local current = integer(objective.numFulfilled, 0, 10000000)
            local required = integer(objective.numRequired, 0, 10000000)
            if not current or not required or current > required then current, required = nil, nil end
            objectives[index] = { current = current, total = required, index = index,
                finished = finished,
                known = current ~= nil and required ~= nil, seen = now() }
        end
    end
    return { known = known, state = known and (delivered and 3 or (complete and active and 2 or (active and 1 or 0))) or nil,
        done = done, total = total, mask = mask,
        objectives = objectives, seen = now() }
end
function Duo:GetLocalQuest(id) return self:LocalQuest(id) end

function Duo:RequestQuest(id)
    id = integer(id, 1, 10000000)
    local context = self:GetContext()
    if not id or not (context.enabled and context.sameParty and context.online) then return false end
    self:PruneQuestCaches()
    if not self.outboundRequests[id] then makeRoom(self.outboundRequests, REQUEST_LIMIT) end
    self.outboundRequests[id] = now()
    return true
end

function Duo:GetObjectiveProgress(id, objectiveIndex)
    objectiveIndex = integer(objectiveIndex, 1, 32)
    local function progress(q, remote)
        local item = objectiveIndex and q and q.objectives and q.objectives[objectiveIndex]
        local finished = item and item.finished
        if remote and q and not q.basic and q.known ~= false and objectiveIndex and objectiveIndex <= (q.total or 0) then
            finished = math.floor((q.mask or 0) / 2 ^ (objectiveIndex - 1)) % 2 == 1
        end
        if not item or (remote and not fresh(item.seen)) then return { known = false, index = objectiveIndex, finished = finished } end
        return { known = item.known == true, current = item.current, total = item.total, finished = finished,
            index = objectiveIndex, seen = item.seen }
    end
    local mine = progress(self:LocalQuest(id), false)
    local partner = progress(self:GetPartnerQuest(id), true)
    local function text(item) return item.known and (item.current .. "/" .. item.total) or "Sin datos" end
    return { mine = mine, partner = partner, index = objectiveIndex,
        text = "Tú: " .. text(mine) .. " · amigo: " .. text(partner) }
end
function Duo:GetPartnerQuest(id)
    local ctx = self:GetContext()
    if not (ctx.enabled and ctx.sameParty and ctx.online) then return nil end
    self:PruneQuestCaches()
    local q = self.remoteQuests[id]
    if ctx.known and q and q.known ~= false then return q end
    local active = safe(C_QuestLog and C_QuestLog.IsUnitOnQuest, "party1", id)
    if active == true then return { state = 1, basic = true } end
    -- The game may hide absent quests. Unknown is never reported as completed.
end
function Duo:GetStepWaitStatus(step)
    local noWait = { waiting = false }
    if not step then return noWait end
    if ns.DuoAuto and ns.DuoAuto.IsIndependentPhase and ns.DuoAuto:IsIndependentPhase(step) then return noWait end
    local ctx = self:GetContext()
    if not (ctx.enabled and ctx.wait and ctx.sameParty) then return noWait end
    local guide = ns.char and ns.guides[ns.char.activeGuide]
    if (guide and guide.recovery) or not appliesToPartner(guide, ctx) or not appliesToPartner(step.only, ctx) then return noWait end
    local requirements, order = {}, {}
    local state = guide and ns.char.progress[guide.id]
    for index, goal in ipairs(step.goals or { step }) do
        local id, action = goal.quest or goal.questID, goal.t or goal.action
        local applicable = not goal.only or not ns.MatchesConditions or ns:MatchesConditions(goal.only)
        -- Class/race errands are individual branches; never wait on another
        -- class to finish our class quest.
        local individual = not appliesToPartner(goal.only, ctx)
        local skipped = ns.GetGoalStatus and ns:GetGoalStatus(goal, step, state, index) == "skip"
        if id and applicable and not individual and not skipped and not goal.optional and action ~= "note" then
            local needed = action == "accept" and 1 or 2
            local requirement = requirements[id] or { state = 1, objectives = {} }
            if not requirements[id] then order[#order + 1] = id end
            local objective = integer(goal.oi or goal.objective, 1, 32)
            if needed == 2 and action ~= "turnin" and objective then requirement.objectives[objective] = true
            else requirement.state = math.max(requirement.state, needed) end
            if action == "turnin" or requirement.action ~= "turnin" and needed >= (requirement.needed or 0) then
                requirement.action = action == "accept" and "accept" or action == "turnin" and "turnin" or "complete"
                requirement.needed = needed
            end
            requirements[id] = requirement
        end
    end
    if not next(requirements) then return noWait end
    if not ctx.online or not ctx.known then
        return { waiting = true, kind = "sync", unknown = true,
            reason = "Sin sincronización: espera o desactiva «Esperar al amigo»." }
    end
    for _, id in ipairs(order) do
        local requirement = requirements[id]
        local q = self:GetPartnerQuest(id)
        local unknownState = not q or q.basic or type(q.state) ~= "number"
        local pending = unknownState or q.state < requirement.state
        if not pending and q.state < 2 then
            for objective in pairs(requirement.objectives) do
                if math.floor((q.mask or 0) / 2 ^ (objective - 1)) % 2 ~= 1 then pending = true; break end
            end
        end
        if pending then
            self:RequestQuest(id)
            return { waiting = true, kind = "quest", action = requirement.action, questID = id,
                state = q and q.state, unknown = unknownState == true,
                reason = "Esperando a tu amigo · " .. ns:GetQuestTitle(id)
                    .. (unknownState and " · Sin datos recientes de esta misión" or "") }
        end
    end
    return noWait
end
function Duo:ShouldWaitForStep(step)
    local status = self:GetStepWaitStatus(step)
    if status.waiting then return true, status.reason end
    return false
end
function Duo:Resynchronize()
    local ctx = self:GetContext()
    if not (ctx.enabled and ctx.sameParty) then return false, "Activa Dúo y forma un grupo de dos para sincronizar." end
    local allowed, reason = self:CanCommunicate()
    if not allowed then return false, reason end
    self.remoteQuests, self.requested, self.outboundRequests = {}, {}, {}
    self.objectiveRotation, self.rotation = {}, 0
    self.lastSentHeader, self.lastSentQuest, self.lastSentRequest, self.lastSentCheckpoint = nil, nil, nil, nil
    -- Reannounce on the normal one-message-per-second tick. Keep the current
    -- profile/nonce/agreement and all character settings and progress intact.
    self:NavigationChanged()
    return true, "Sincronización solicitada; esperando datos nuevos del compañero."
end
-- Sources: Gethe/wow-ui-source, branch forever, generated Container/Unit/QuestLog
-- documentation. General bag space excludes profession/ammunition-only bags.
function Duo:GetLocalSupplies()
    local result = { known = true, seen = now(), level = integer(safe(UnitLevel, "player"), 1, 100) }
    local free, total, valid = 0, 0, true
    local slotsAPI = C_Container and C_Container.GetContainerNumSlots or GetContainerNumSlots
    local freeAPI = C_Container and C_Container.GetContainerNumFreeSlots or GetContainerNumFreeSlots
    if type(slotsAPI) ~= "function" or type(freeAPI) ~= "function" then valid = false end
    for bag = 0, integer(NUM_BAG_SLOTS, 0, 10) or 4 do
        local slots = integer(safe(slotsAPI, bag), 0, 1000)
        if not slots then valid = false
        elseif slots > 0 then
            local available, family = safe(freeAPI, bag)
            available, family = integer(available, 0, slots), integer(family, 0, 10000000)
            if not available or not family then valid = false
            elseif family == 0 then free, total = free + available, total + slots end
        end
    end
    if valid then result.freeSlots, result.totalSlots, result.bagsKnown = free, total, true end
    local currentDurability, maximumDurability = 0, 0
    if type(GetInventoryItemDurability) == "function" then
        for slot = 1, 19 do
            local value, maximum = safe(GetInventoryItemDurability, slot)
            value, maximum = integer(value, 0, 10000000), integer(maximum, 1, 10000000)
            if value and maximum and value <= maximum then
                currentDurability, maximumDurability = currentDurability + value, maximumDurability + maximum
            end
        end
    end
    if maximumDurability > 0 then result.durabilityPercent = math.floor(100 * currentDurability / maximumDurability + .5) end
    local manaType = Enum and Enum.PowerType and Enum.PowerType.Mana or 0
    local mana, maximumMana = safe(UnitPower, "player", manaType), safe(UnitPowerMax, "player", manaType)
    mana, maximumMana = integer(mana, 0, 1000000000), integer(maximumMana, 1, 1000000000)
    if mana and maximumMana and mana <= maximumMana then
        result.manaPercent = math.floor(mana * 100 / maximumMana + .5)
        result.manaLow = result.manaPercent <= 25
    end
    return result
end

function Duo:GetPartnerSupplies()
    local context = self:GetContext()
    if not (context.enabled and context.known and context.online and context.sameParty)
        or not self.remoteSupplies or not fresh(self.remoteSupplies.seen) then return { known = false } end
    local copy = {}; for key, value in pairs(self.remoteSupplies) do copy[key] = value end
    return copy
end

function Duo:RegisterCheckpointProvider(provider)
    if provider ~= nil and type(provider) ~= "function" then return false end
    self.checkpointProvider, self.lastSentCheckpoint = provider, nil
    return true
end

function Duo:GetPartnerCheckpoint()
    local context = self:GetContext()
    local checkpoint = self.remoteCheckpoint
    if not (context.enabled and context.known and context.online and context.sameParty)
        or not checkpoint or not fresh(checkpoint.seen) then return { known = false } end
    self:PruneQuestCaches()
    local copy = { known = true, quests = {} }
    for key, value in pairs(checkpoint) do copy[key] = value end
    for id, quest in pairs(self.remoteQuests) do
        local item = { objectives = {} }
        for key, value in pairs(quest) do if type(value) ~= "table" then item[key] = value end end
        for index, objective in pairs(quest.objectives or {}) do
            if fresh(objective.seen) then
                local values = {}; for key, value in pairs(objective) do values[key] = value end
                item.objectives[index] = values
            end
        end
        copy.quests[id] = item
    end
    return copy
end

local function meetingValid(point)
    return type(point) == "table" and type(point.owner) == "string" and integer(point.revision, 1, 1000000000)
        and (point.clear == true or (integer(point.mapID, 1, 100000) and type(point.x) == "number"
        and type(point.y) == "number" and point.x >= 0 and point.x <= 1 and point.y >= 0 and point.y <= 1))
end
local function newerMeeting(a, b)
    if not a then return b end
    if not b then return a end
    if a.revision ~= b.revision then return a.revision > b.revision and a or b end
    return a.owner > b.owner and a or b
end
function Duo:_Meeting()
    local settings, context = self:Settings(), self:GetContext()
    local mine = settings and settings.meeting
    if not meetingValid(mine) or mine.owner ~= unitName("player") then mine = nil end
    local partner = context.enabled and context.known and context.online and self.partnerMeeting
    if not partner or not fresh(partner.seen, 60) or partner.owner ~= context.partnerName then partner = nil end
    local selected = newerMeeting(mine, partner)
    local floor = settings and settings.meetingFloor
    if selected and floor and newerMeeting(selected, floor) == floor
        and (selected.revision ~= floor.revision or selected.owner ~= floor.owner) then return nil end
    return selected
end

function Duo:SetMeetingPoint()
    local settings = self:Settings()
    if not settings then return false, "No hay personaje cargado" end
    if not unitName("player") then return false, "Nombre del personaje no disponible" end
    local point = ns.PlayerPoint and ns:PlayerPoint()
    if not point or not integer(point.mapID, 1, 100000) or type(point.x) ~= "number" or type(point.y) ~= "number"
        or point.x < 0 or point.x > 1 or point.y < 0 or point.y > 1 then return false, "Posición no disponible" end
    local prior = self:_Meeting()
    local _, _, height, instance = safe(UnitPosition, "player")
    local continent = ns.GetWaypointWorldPosition and ns:GetWaypointWorldPosition(point)
    if not continent or continent ~= instance or type(height) ~= "number" or height == 0 or height ~= height or math.abs(height) > 100000 then height = nil end
    settings.meeting = { owner = unitName("player"), revision = math.max(prior and prior.revision or 0, settings.meetingClock or 0) + 1,
        mapID = point.mapID, x = point.x, y = point.y, z = height }
    settings.meetingClock = settings.meeting.revision
    settings.meetingFloor = { owner = settings.meeting.owner, revision = settings.meeting.revision }
    self.lastSentMeeting = nil
    self:NavigationChanged()
    return true, "Punto de reunión guardado y preparado para compartir"
end
function Duo:FollowMeeting(value)
    local settings = self:Settings()
    if not settings then return false end
    settings.followMeeting = value == true
    self:NavigationChanged()
    return true, settings.followMeeting and "Siguiendo el punto de reunión" or "Reunión en pausa; continúa la guía"
end
function Duo:ClearMeeting()
    local settings = self:Settings()
    if not settings then return false end
    local previous = self:_Meeting()
    settings.meeting = { owner = unitName("player"), revision = math.max(previous and previous.revision or 0, settings.meetingClock or 0) + 1, clear = true }
    settings.meetingClock = settings.meeting.revision
    settings.meetingFloor = { owner = settings.meeting.owner, revision = settings.meeting.revision }
    settings.followMeeting, self.lastSentMeeting = false, nil
    self:NavigationChanged()
    return true, "Punto de reunión retirado"
end
function Duo:GetMeetingStatus()
    local settings = self:Settings() or {}
    local point = self:_Meeting()
    local context = self:GetContext()
    local available = point ~= nil and point.clear ~= true
    local normalized = available and { mapID = point.mapID, x = point.x, y = point.y, z = point.z } or nil
    local distance = normalized and ns.GetWaypointVector and ns:GetWaypointVector(normalized)
    local label = available and ("Reunión acordada por " .. point.owner) or "Sin punto de reunión reciente"
    local text = label
    if type(distance) == "number" then text = text .. " · " .. math.floor(distance + .5) .. " yardas" end
    if available then text = text .. (settings.followMeeting and " · Flecha activada" or " · Pulsa Seguir para orientar la flecha") end
    return { available = available, following = settings.followMeeting == true, shared = context.enabled and context.known,
        owner = point and point.owner, mapID = available and point.mapID, x = available and point.x, y = available and point.y,
        z = available and point.z, revision = point and point.revision, known = available,
        point = normalized, distance = distance, label = label, text = text, report = text,
        reason = not available and "Sin punto de reunión reciente" or nil }
end
function Duo:GetMeetingWaypoint()
    local settings = self:Settings() or {}
    if not settings.enabled or not settings.followMeeting then return nil end
    local point = self:_Meeting()
    if not point or point.clear then return nil end
    return { mapID = point.mapID, x = point.x, y = point.y, z = point.z, radius = 12,
        meeting = true, source = "duo-meeting", label = "Punto de reunión", routeLabel = "Punto de reunión", owner = point.owner }
end
function Duo:GetAlerts()
    local context, alerts = self:GetContext(), {}
    if not (context.enabled and context.sameParty) then return alerts end
    if context.dead then alerts[#alerts + 1] = { kind = "death", text = "Tu amigo ha muerto o está como fantasma." } end
    if context.differentZone then alerts[#alerts + 1] = { kind = "zone", text = "Estáis en mapas distintos; comprobad la zona de reunión." }
    elseif context.separated then alerts[#alerts + 1] = { kind = "separation", text = "Tu amigo está fuera del alcance de grupo." } end
    return alerts
end

local function parseQuest(fields, allowUnknown)
    if #fields ~= 10 and #fields ~= 11 then return nil end
    local id, status = integer(fields[5], 1, 10000000), integer(fields[6], 0, 3)
    local unknownStatus = allowUnknown and fields[6] == "?"
    local done, total = integer(fields[7], 0, 100), integer(fields[8], 0, 100)
    local mask, request = integer(fields[9], 0, 4294967295), integer(fields[10], 0, 1)
    if not id or (not status and not unknownStatus) or not done or not total or not mask or not request
        or done > total or mask >= 2 ^ math.min(total, 32) then return nil end
    if unknownStatus and (done ~= 0 or total ~= 0 or mask ~= 0) then return nil end
    local bits, remaining = 0, mask
    while remaining > 0 do bits = bits + remaining % 2; remaining = math.floor(remaining / 2) end
    if bits > done or done - bits > math.max(0, total - 32) then return nil end
    local objectives = {}
    if fields[11] and fields[11] ~= "" then
        local count = 0
        for entry in (fields[11] .. ";"):gmatch("(.-);") do
            count = count + 1
            local index, current, required, finished = entry:match("^(%d+):([^:]+):([^:]+):([01?])$")
            index = integer(index, 1, math.min(total, 32))
            if not index or objectives[index] or count > 32 then return nil end
            local currentValue, requiredValue = integer(current, 0, 10000000), integer(required, 0, 10000000)
            if (current ~= "?" or required ~= "?") and (not currentValue or not requiredValue or currentValue > requiredValue) then return nil end
            local flag = boolean(finished)
            local completed = math.floor(mask / 2 ^ (index - 1)) % 2 == 1
            if flag ~= nil and flag ~= completed then return nil end
            objectives[index] = { known = currentValue ~= nil and requiredValue ~= nil, current = currentValue,
                total = requiredValue, finished = flag, index = index, seen = now() }
        end
    end
    return { id = id, known = not unknownStatus, state = status, done = done, total = total, mask = mask,
        request = request, objectives = objectives }
end

local function storeQuest(self, snapshot)
    local id = snapshot.id
    if snapshot.request == 1 then
        if not self.requested[id] then makeRoom(self.requested, REQUEST_LIMIT) end
        self.requested[id] = now()
    end
    if not self.remoteQuests[id] then makeRoom(self.remoteQuests, CACHE_LIMIT, "seen") end
    if not snapshot.known then self.remoteQuests[id] = { known = false, seen = now(), objectives = {} }; return end
    local previous = self.remoteQuests[id]
    for index, item in pairs(previous and previous.objectives or {}) do
        if not snapshot.objectives[index] and index <= snapshot.total and fresh(item.seen) then
            local completed = math.floor(snapshot.mask / 2 ^ (index - 1)) % 2 == 1
            -- A newer completion bit invalidates an older partial counter.
            if item.finished == completed then snapshot.objectives[index] = item end
        end
    end
    self.remoteQuests[id] = { known = true, state = snapshot.state, done = snapshot.done, total = snapshot.total,
        mask = snapshot.mask, seen = now(), objectives = snapshot.objectives }
end

function Duo:Receive(prefix, message, channel, sender)
    if issecretvalue and (issecretvalue(prefix) or issecretvalue(channel) or issecretvalue(message) or issecretvalue(sender)) then return false end
    local settings = self:Settings()
    if prefix ~= self.prefix or channel ~= "PARTY" or not settings or not settings.enabled
        or type(message) ~= "string" or #message > 255 then return false end
    self:RefreshRoster()
    if not self.partnerName or not self.online then return false end
    if not senderIsUnit(sender, "party1") then
        if message:sub(1, 4) == PROTOCOL .. "|H|" and not senderIsUnit(sender, "player") then
            local info = transport(self)
            info.unmatchedHeaders, info.lastUnmatchedHeader = increment(info.unmatchedHeaders), now()
        end
        return false
    end
    local fields = {}; for field in (message .. "|"):gmatch("(.-)|") do fields[#fields + 1] = field end
    if fields[1] ~= PROTOCOL then return false end
    local seq = integer(fields[4], 1, 1000000000)
    if not token(fields[3]) or not seq then return false end
    local kind = fields[2]
    if kind == "H" and (#fields == 11 or #fields == 13 or #fields == 18 or #fields == 21) then
        local level, cursor = integer(fields[5], 1, 100), integer(fields[9], 1, 100000)
        if not level or not cursor or not token(fields[6]) or not token(fields[7]) or not token(fields[8])
            or (fields[10] ~= "0" and fields[10] ~= "1") or fields[11] ~= safe(UnitFactionGroup, "player") then return false end
        local mapID = fields[12] and integer(fields[12], 1, 100000)
        if #fields >= 13 and ((fields[12] ~= "?" and not mapID)
            or (fields[13] ~= "?" and fields[13] ~= "0" and fields[13] ~= "1")) then return false end
        local supplies = #fields >= 18 and suppliesFields(fields, 14)
        if #fields >= 18 and not supplies then return false end
        local autoEpoch = fields[19] and integer(fields[19]:match("^1:(%d+)$"), 1, 1000000000)
        if #fields == 21 and ((fields[19] ~= "1" and not autoEpoch) or (fields[20] ~= "0" and fields[20] ~= "1")
            or (fields[21] ~= "0" and fields[21] ~= "1")) then return false end
        if self.peer and self.peer.nonce == fields[3] and seq <= self.peer.sequence then return false end
        if not self.peer or self.peer.nonce ~= fields[3] then
            self.remoteQuests, self.requested, self.remoteSupplies, self.remoteCheckpoint, self.partnerMeeting = {}, {}, nil, nil, nil
        end
        local previous = self.peer
        self.peer = { nonce = fields[3], sequence = seq, level = level, class = fields[6], race = fields[7],
            guideID = fields[8], cursor = cursor, ready = fields[10] == "1", seen = now(), headerSeen = now(), mapID = mapID, dead = boolean(fields[13]),
            autoCapability = fields[19] and "1" or nil, autoEpoch = autoEpoch,
            autoPair = boolean(fields[20]), review = boolean(fields[21]) }
        if previous and previous.nonce == fields[3] and previous.guideID == fields[8] then
            self.peer.travelReady, self.peer.travelSeen = previous.travelReady, previous.travelSeen
        end
        self.lastHeader = now()
        if supplies then self.remoteSupplies = supplies end
    elseif kind == "Q" and (#fields == 10 or #fields == 11) and self.peer and self.peer.nonce == fields[3] then
        if seq <= self.peer.sequence then return false end
        local snapshot = parseQuest(fields, false)
        if not snapshot then return false end
        self:PruneQuestCaches()
        storeQuest(self, snapshot)
        self.peer.sequence, self.peer.seen = seq, now()
    elseif self.peer and self.peer.nonce == fields[3] and seq > self.peer.sequence then
        if (kind == "A" or kind == "P" or kind == "N" or kind == "K") and #fields == 9 and self.peer.autoCapability == "1" and ns.DuoAuto and ns.DuoAuto.OnProtocol then
            local reference = integer(fields[7], 0, 1)
            local cursor, phase = integer(fields[8], 1, 100001), integer(fields[9], 0, (kind == "A" or kind == "N") and 1 or 2)
            if not token(fields[5]) or #fields[5] > 40 or not token(fields[6]) or not reference or not cursor or not phase then return false end
            if not safe(ns.DuoAuto.OnProtocol, ns.DuoAuto, kind, { transaction=fields[5], guideID=fields[6],
                reference=reference, cursor=cursor, phase=phase, nonce=fields[3], sender=self.partnerName }) then return false end
        elseif kind == "T" and #fields == 6 then
            if fields[5] ~= self.peer.guideID or (fields[6] ~= "0" and fields[6] ~= "1") then return false end
            self.peer.travelReady, self.peer.travelSeen = fields[6] == "1", now()
        elseif kind == "B" and #fields == 5 then
            local snapshots, ids = {}, {}
            for raw in (fields[5] .. "/"):gmatch("(.-)/") do
                if #snapshots >= 3 then return false end
                local values = { PROTOCOL, "Q", fields[3], fields[4] }
                for value in (raw .. ","):gmatch("(.-),") do values[#values + 1] = value end
                local snapshot = parseQuest(values, true)
                if not snapshot or ids[snapshot.id] then return false end
                snapshots[#snapshots + 1], ids[snapshot.id] = snapshot, true
            end
            if #snapshots == 0 then return false end
            -- Validate the entire bounded batch before applying any state.
            self:PruneQuestCaches()
            for _, snapshot in ipairs(snapshots) do storeQuest(self, snapshot) end
        elseif kind == "U" and #fields == 6 then
            local id, request = integer(fields[5], 1, 10000000), integer(fields[6], 0, 1)
            if not id or not request then return false end
            self:PruneQuestCaches()
            if request == 1 then
                if not self.requested[id] then makeRoom(self.requested, REQUEST_LIMIT) end
                self.requested[id] = now()
            end
            if not self.remoteQuests[id] then makeRoom(self.remoteQuests, CACHE_LIMIT, "seen") end
            self.remoteQuests[id] = { known = false, seen = now(), objectives = {} }
        elseif kind == "S" and #fields == 9 then
            local supplies = suppliesFields(fields, 5)
            if not supplies then return false end
            self.remoteSupplies = supplies
        elseif kind == "C" and #fields == 11 then
            local cursor, mapID, level = integer(fields[6], 1, 100000), integer(fields[10], 1, 100000), integer(fields[11], 1, 100)
            if not token(fields[5]) or not cursor or not token(fields[7]) or #fields[7] > 64
                or not token(fields[8]) or #fields[8] > 24 or (fields[9] ~= "?" and fields[9] ~= "0" and fields[9] ~= "1")
                or (fields[10] ~= "?" and not mapID) or (fields[11] ~= "?" and not level) then return false end
            self.remoteCheckpoint = { known = true, seen = now(), guideID = fields[5], cursor = cursor,
                checkpointID = fields[7], stopKind = fields[8], stopReady = boolean(fields[9]), mapID = mapID, level = level }
        elseif kind == "M" and #fields == 10 then
            local revision, mapID = integer(fields[5], 1, 1000000000), integer(fields[6], 0, 100000)
            local x, y, z = integer(fields[7], 0, 1000000), integer(fields[8], 0, 1000000), integer(fields[9], -1000000, 1000000)
            local clear = boolean(fields[10])
            if not revision or not mapID or not x or not y or clear == nil or (fields[9] ~= "?" and not z)
                or (not clear and mapID == 0) then return false end
            local prior = self.partnerMeeting
            if prior and revision < prior.revision then return false end
            self.partnerMeeting = { owner = self.partnerName, revision = revision, clear = clear,
                mapID = mapID, x = x / 1000000, y = y / 1000000, z = z and z / 10 or nil, seen = now() }
            settings.meetingClock = math.max(settings.meetingClock or 0, revision)
            settings.meetingFloor = newerMeeting(settings.meetingFloor, { owner = self.partnerName, revision = revision })
        elseif kind == "R" and #fields == 5 then
            local ids, seen = {}, {}
            for raw in (fields[5] .. ","):gmatch("(.-),") do
                local id = integer(raw, 1, 10000000)
                if not id or seen[id] or #ids >= 12 then return false end
                ids[#ids + 1], seen[id] = id, true
            end
            if #ids == 0 then return false end
            self:PruneQuestCaches()
            for _, id in ipairs(ids) do
                if not self.requested[id] then makeRoom(self.requested, REQUEST_LIMIT) end
                self.requested[id] = now()
            end
        else return false end
        self.peer.sequence, self.peer.seen = seq, now()
    else return false end
    if kind == "H" then
        local info = transport(self)
        info.receivedHeaders, info.lastHeader = increment(info.receivedHeaders), now()
    end
    if kind == "H" or kind == "Q" or kind == "U" or kind == "B" or kind == "T" then self:Changed() else self:NavigationChanged() end
    return true
end
function Duo:QueueAutoMessage(kind, packet)
    if kind ~= "A" and kind ~= "P" and kind ~= "N" and kind ~= "K" then return false end
    if type(packet) ~= "table" or not token(packet.transaction) or #packet.transaction > 40 or not token(packet.guideID)
        or not integer(packet.reference, 0, 1) or not integer(packet.cursor, 1, 100001)
        or not integer(packet.phase, 0, (kind == "A" or kind == "N") and 1 or 2) then return false end
    local values = table.concat({ packet.transaction, packet.guideID, packet.reference, packet.cursor, packet.phase }, "|")
    if #(PROTOCOL .. "|" .. kind .. "|" .. tostring(self.nonce) .. "|1000000000|" .. values) > 255 then return false end
    self.autoQueue = { kind = kind, values = values }
    return true
end
function Duo:ClearAutoMessages() self.autoQueue = nil end
function Duo:Send(kind, values)
    if self.lastSendAt and now() - self.lastSendAt < 1 then return false end
    local settings = self:Settings()
    if not settings or not settings.enabled or not self:CanCommunicate() then return false end
    self.sequence = self.sequence + 1
    local message = PROTOCOL .. "|" .. kind .. "|" .. self.nonce .. "|" .. self.sequence .. "|" .. values
    self.lastSendAt = now()
    local info = transport(self)
    info.attempts, info.lastAttempt = increment(info.attempts), now()
    local ok, result
    if #message > 255 then ok, result = false, "length"
    else ok, result = pcall(C_ChatInfo.SendAddonMessage, self.prefix, message, "PARTY") end
    local hidden = issecretvalue and issecretvalue(result)
    local names = Enum and Enum.SendAddonMessageResult
    local success = names and names.Success or 0
    local accepted = ok and not hidden and (result == nil or result == true or result == success)
    if not ok then info.lastResult = result == "length" and "length" or "error"
    elseif hidden then info.lastResult = "protected"
    elseif type(result) == "number" or type(result) == "boolean" or result == nil then info.lastResult = result
    else info.lastResult = "unexpected" end
    if not accepted then
        info.failed = increment(info.failed)
        info.lastError = not ok and (result == "length" and "El mensaje supera el tamaño permitido." or "Error del juego al enviar el mensaje de RutaXP.")
            or hidden and "El juego no permite confirmar el resultado del envío."
            or resultName(result, names or {InvalidPrefix=1,InvalidMessage=2,AddonMessageThrottle=3,InvalidChatType=4,
                NotInGroup=5,TargetRequired=6,InvalidChannel=7,ChannelThrottle=8,GeneralError=9,NotInGuild=10,
                AddOnMessageLockdown=11,TargetOffline=12}, {
                InvalidPrefix="El juego rechazó el prefijo de RutaXP.", InvalidMessage="El juego rechazó el mensaje de RutaXP.",
                AddonMessageThrottle="El juego ha limitado temporalmente los mensajes de addons.",
                InvalidChatType="El juego rechazó el canal de grupo.", NotInGroup="El juego todavía no confirma el grupo.",
                TargetRequired="El juego requiere un destinatario para este envío.", InvalidChannel="El juego rechazó el canal de grupo.",
                ChannelThrottle="El juego ha limitado temporalmente el canal de grupo.", GeneralError="El juego no pudo enviar el mensaje.",
                NotInGuild="El juego rechazó el tipo de canal solicitado.", AddOnMessageLockdown="El juego bloquea temporalmente los mensajes de addons.",
                TargetOffline="El juego indica que el destinatario no está conectado." })
            or "El juego no aceptó el mensaje de RutaXP."
        return false
    end
    info.accepted, info.lastSuccess, info.lastError = increment(info.accepted), now(), nil
    return true
end
function Duo:QuestPayload(id, q, request, maximum, preferredIndex)
    if q.known == false then return id .. "|?|0|0|0|" .. (request and "1" or "0") .. "|" end
    local payload = table.concat({ id, q.state, q.done, q.total, q.mask, request and 1 or 0 }, "|")
    local budget = 255 - #(PROTOCOL .. "|Q|" .. self.nonce .. "|" .. tostring(self.sequence + 1) .. "|" .. payload .. "|")
    if maximum then budget = math.min(budget, maximum - #payload - 1) end
    local pieces, used, count = {}, 0, math.min(q.total, 32)
    self.objectiveRotation = self.objectiveRotation or {}
    local start = self.objectiveRotation[id] or 1
    local order, included = {}, {}
    preferredIndex = integer(preferredIndex, 1, count)
    if preferredIndex then order[#order + 1], included[preferredIndex] = preferredIndex, true end
    for offset = 0, count - 1 do
        local index = (start + offset - 1) % count + 1
        if not included[index] then order[#order + 1], included[index] = index, true end
    end
    for _, index in ipairs(order) do
        local objective = q.objectives[index]
        local piece = index .. ":" .. unknown(objective.current) .. ":" .. unknown(objective.total) .. ":" .. encodeBoolean(objective.finished)
        local size = #piece + (#pieces > 0 and 1 or 0)
        if used + size > budget then self.objectiveRotation[id] = index; break end
        pieces[#pieces + 1], used = piece, used + size
        if index ~= preferredIndex then self.objectiveRotation[id] = index % count + 1 end
    end
    return payload .. "|" .. table.concat(pieces, ";")
end
function Duo:Tick(elapsed)
    if not self:Settings() then return end
    self.elapsed, self.sendElapsed = self.elapsed + elapsed, self.sendElapsed + elapsed
    if self.elapsed < 1 then return end
    self.elapsed = 0
    local ctx = self:GetContext()
    local guide = ns.char and ns.guides[ns.char.activeGuide]
    local state = guide and ns.char.progress[guide.id]
    local routeKey = (guide and guide.id or "") .. ":" .. tostring(state and state.cursor or 1)
    if self.lastRouteKey and self.lastRouteKey ~= routeKey then self.ready, self.lastSentHeader = false, nil end
    self.lastRouteKey = routeKey
    local statusKey = table.concat({ tostring(ctx.enabled), tostring(ctx.sameParty), tostring(ctx.online), tostring(ctx.known), tostring(ctx.partnerReady), tostring(ctx.dead), tostring(ctx.separated), tostring(ctx.partnerMapID), routeKey }, "|")
    if self.statusKey ~= statusKey then
        self.statusKey = statusKey
        if ns.RefreshUI then ns:RefreshUI() end
    end
    if not (ctx.enabled and ctx.sameParty and ctx.online and self:CanCommunicate()) then return end
    if self.sendElapsed < 1 then return end
    self.sendElapsed = 0
    if not self.lastSentHeader or now() - self.lastSentHeader >= 5 then
        local level, class, race = profile("player")
        local id = guide and guide.id or "none"
        if not (token(id) and token(class) and token(race)) then return end
        local supplies = self:GetLocalSupplies()
        local header = table.concat({ level or 1, class, race, id, state and state.cursor or 1, self.ready and 1 or 0,
            safe(UnitFactionGroup, "player") or "Neutral", unknown(ctx.mapID), encodeBoolean(safe(UnitIsDeadOrGhost, "player")),
            unknown(supplies.freeSlots), unknown(supplies.totalSlots), unknown(supplies.durabilityPercent), unknown(supplies.manaPercent), unknown(supplies.level) }, "|")
        if ns.DuoAuto then header = header .. "|1:" .. tostring(self:Settings().autoEpoch or 1)
            .. "|" .. (self:Settings().autoPair ~= false and "1" or "0") .. "|" .. (state and state.review and "1" or "0") end
        if self:Send("H", header) then self.lastSentHeader = now() end
    else
        local ids = self:GetQuestIDs()
        local _, localIDs = self:GetLocalQuestIDs()
        -- A quest frame always follows an auxiliary frame. Supplies ride in the
        -- header, counters in Q: neither creates extra per-objective traffic.
        local auxiliary = #ids == 0 or (self.lastSentQuest ~= nil and now() - self.lastSentQuest < 2)
        local meeting = self:Settings().meeting
        local signal = ns.GetWestfallTravelSignal and ns:GetWestfallTravelSignal()
        local travel = signal and (guide.id .. "|" .. signal)
        if self.autoQueue and (not self.lastSentAuto or now() - self.lastSentAuto >= 3) then
            if self:Send(self.autoQueue.kind, self.autoQueue.values) then self.lastSentAuto = now(); self.autoQueue = nil end
        elseif travel and (travel ~= self.lastTravelSignal or not self.lastTravelSent or now() - self.lastTravelSent >= 8) then
            if self:Send("T", travel) then self.lastTravelSignal, self.lastTravelSent = travel, now() end
        elseif auxiliary and meetingValid(meeting) and (not self.lastSentMeeting or now() - self.lastSentMeeting >= 20) then
            local clear = meeting.clear == true
            if self:Send("M", table.concat({ meeting.revision, clear and 0 or meeting.mapID,
                clear and 0 or math.floor(meeting.x * 1000000 + .5), clear and 0 or math.floor(meeting.y * 1000000 + .5),
                unknown(meeting.z and math.floor(meeting.z * 10 + .5)), clear and 1 or 0 }, "|")) then self.lastSentMeeting = now() end
        elseif auxiliary and next(self.outboundRequests) and (not self.lastSentRequest or now() - self.lastSentRequest >= 10) then
            self:PruneQuestCaches()
            local requested = {}; for questID in pairs(self.outboundRequests) do requested[#requested + 1] = questID end
            table.sort(requested)
            local chunk = {}; local start = self.requestRotation or 1
            for offset = 0, math.min(12, #requested) - 1 do chunk[#chunk + 1] = requested[(start + offset - 1) % #requested + 1] end
            self.requestRotation = #requested > 0 and ((start + #chunk - 1) % #requested + 1) or 1
            if #chunk > 0 and self:Send("R", table.concat(chunk, ",")) then self.lastSentRequest = now() end
        elseif auxiliary and self.checkpointProvider and (not self.lastSentCheckpoint or now() - self.lastSentCheckpoint >= 10) then
            local checkpoint = safe(self.checkpointProvider)
            if type(checkpoint) == "table" then
                local checkpointID, guideID = checkpoint.checkpointID or "none", checkpoint.guideID or (guide and guide.id or "none")
                local cursor = integer(checkpoint.cursor, 1, 100000) or (state and state.cursor or 1)
                local stopKind = checkpoint.stopKind or "none"
                if token(checkpointID) and #checkpointID <= 64 and token(guideID) and token(stopKind) and #stopKind <= 24
                    and self:Send("C", table.concat({ guideID, cursor, checkpointID, stopKind, encodeBoolean(checkpoint.stopReady),
                        unknown(ctx.mapID), unknown(integer(safe(UnitLevel, "player"), 1, 100)) }, "|")) then self.lastSentCheckpoint = now() end
            end
        elseif #ids > 0 then
            local step = guide and guide.steps[state and state.cursor or 1]
            local activeGoal = step and ns.GetActiveGoal and ns:GetActiveGoal(step, state)
            local activeID = activeGoal and (activeGoal.quest or activeGoal.questID)
            local activeIndex = activeGoal and (activeGoal.oi or activeGoal.objective)
            local batch, selected = {}, {}
            local tracked = {}; for _, id in ipairs(ids) do tracked[id] = true end
            for id in pairs(self.objectiveRotation or {}) do if not tracked[id] then self.objectiveRotation[id] = nil end end
            if activeID and tracked[activeID] then batch[1], selected[activeID] = activeID, true end
            while #batch < math.min(3, #ids) do
                self.rotation = (self.rotation or 0) % #ids + 1
                local id = ids[self.rotation]
                if not selected[id] then batch[#batch + 1], selected[id] = id, true end
            end
            local sent
            if #batch == 1 then
                local id = batch[1]; local q = self:LocalQuest(id)
                if q.known then sent = self:Send("Q", self:QuestPayload(id, q, localIDs[id], nil, activeIndex))
                else sent = self:Send("U", id .. "|" .. (localIDs[id] and "1" or "0")) end
            else
                local size = 255 - #(PROTOCOL .. "|B|" .. self.nonce .. "|" .. tostring(self.sequence + 1) .. "|") - (#batch - 1)
                local perQuest, pieces = math.floor(size / #batch), {}
                for _, id in ipairs(batch) do
                    pieces[#pieces + 1] = self:QuestPayload(id, self:LocalQuest(id), localIDs[id], perQuest,
                        id == activeID and activeIndex or nil):gsub("|", ",")
                end
                sent = self:Send("B", table.concat(pieces, "/"))
            end
            if sent then self.lastSentQuest = now() end
        elseif not self.lastSentQuest then
            -- No quest is active; auxiliary state may still be useful.
            self.lastSentQuest = now()
        end
    end
end
function Duo:GetReport()
    local ctx = self:GetContext()
    if not ctx.enabled then return "Modo dúo desactivado. Ambos podéis activarlo con /rutaxp duo. Funciona con dos jugadores de la misma facción, de cualquier raza y clase." end
    if not ctx.sameParty then return "Invita a tu amigo a un grupo de dos, de la misma facción. En grupos mayores se suspende la sincronización para evitar confundir compañeros." end
    local lines = { "Compañero: " .. (self.partnerName or "—"), ctx.online and "Conectado" or "Desconectado" }
    local allowed, reason = self:CanCommunicate()
    if not allowed then lines[#lines + 1] = ns.GetDuoConnectionText and ns:GetDuoConnectionText(ctx) or reason
    elseif not ctx.known then lines[#lines + 1] = ns.GetDuoConnectionText and ns:GetDuoConnectionText(ctx) or "Esperando RutaXP del compañero. Ambos debéis instalar esta versión y activar Dúo."
    else
        local guide = ns.guides[ctx.guideID]
        lines[#lines + 1] = "Su ruta: " .. (guide and guide.title or "Guía no instalada") .. " · paso " .. ctx.cursor
        lines[#lines + 1] = "Preparados: tú " .. (ctx.ready and "sí" or "no") .. " · amigo " .. (ctx.partnerReady and "sí" or "no")
        local problem = self:GetTransportStatus().lastError
        if problem then lines[#lines + 1] = problem end
    end
    if ctx.dead then lines[#lines + 1] = "Tu amigo ha muerto o está como fantasma. Reuniros antes de continuar." end
    local inRange, checked = safe(UnitInRange, "party1")
    if checked and not inRange then lines[#lines + 1] = "Está lejos del alcance de grupo. Comprobad distancia, zona y capa." end
    local names = { [0] = "No la lleva", [1] = "En curso", [2] = "Lista para entregar", [3] = "Entregada" }
    lines[#lines + 1] = ""
    for _, id in ipairs(self:GetQuestIDs()) do
        local mine, friend = self:LocalQuest(id), self:GetPartnerQuest(id)
        local theirs = friend and (friend.basic and "La lleva; objetivos sin confirmar" or names[friend.state]) or "Sin datos recientes"
        if friend and not friend.basic and friend.total > 0 then theirs = theirs .. " (" .. friend.done .. "/" .. friend.total .. " objetivos)" end
        lines[#lines + 1] = ns:GetQuestTitle(id) .. " · tú: " .. (names[mine.state] or "Sin datos") .. " · amigo: " .. theirs
        local function countText(objective)
            if objective and objective.known and fresh(objective.seen) then return objective.current .. "/" .. objective.total end
            return "Sin datos"
        end
        for index = 1, math.min(32, math.max(mine.total or 0, friend and friend.total or 0)) do
            local localObjective, remoteObjective = mine.objectives[index], friend and friend.objectives and friend.objectives[index]
            if (localObjective and localObjective.known) or (remoteObjective and remoteObjective.known) then
                lines[#lines + 1] = "  Objetivo " .. index .. " · tú: " .. countText(localObjective) .. " · amigo: " .. countText(remoteObjective)
            end
        end
    end
    for _, alert in ipairs(self:GetAlerts()) do lines[#lines + 1] = alert.text end
    local meeting = self:GetMeetingStatus()
    if meeting.available then lines[#lines + 1] = meeting.text end
    local guide = ns.char and ns.guides[ns.char.activeGuide]
    local state = guide and ns.char.progress[guide.id]
    local step = guide and guide.steps[state and state.cursor or 1]
    local wait, reasonWait
    if step then wait, reasonWait = self:ShouldWaitForStep(step) end
    lines[#lines + 1] = ""
    lines[#lines + 1] = ctx.wait and "Esperar al amigo: activado. Puedes desactivarlo para continuar por tu cuenta." or "Cada uno avanza con sus propias misiones. Activa «Esperar» si queréis acabar juntos cada paso."
    if wait and reasonWait then lines[#lines + 1] = reasonWait end
    lines[#lines + 1] = "Comprobad que AMBOS aceptáis, recogéis objetos y entregáis. El botín y las misiones de clase pueden ser individuales. Compartid las misiones desde el registro del juego cuando lo permita."
    lines[#lines + 1] = "Razas distintas: terminad vuestro inicio y acordad una zona común. Las misiones élite no se vuelven seguras automáticamente por ser dos."
    return table.concat(lines, "\n\n")
end
function Duo:AdoptPartnerGuide()
    local ctx = self:GetContext(); local guide = ctx.known and ns.guides[ctx.guideID]
    if not guide or (guide.faction and guide.faction ~= safe(UnitFactionGroup, "player")) or guide.recovery or guide.temporary
        or (ns.MatchesConditions and not ns:MatchesConditions({ classes = guide.classes, races = guide.races })) then
        return false, "No hay una guía compatible del compañero."
    end
    ns.char.activeGuide = guide.id -- Never copy their cursor, omissions or completions.
    self:Changed()
    return true
end
function Duo:Initialize()
    if self.frame then return end
    self:Settings()
    self.nonce = tostring(math.floor((safe(GetTime) or 1) * 1000)) .. "_" .. tostring(math.random(10000, 99999))
    self:RegisterPrefix()
    self:RefreshRoster()
    self.frame = CreateFrame("Frame")
    for _, event in ipairs({ "CHAT_MSG_ADDON", "GROUP_ROSTER_UPDATE", "UNIT_CONNECTION", "PLAYER_ENTERING_WORLD" }) do self.frame:RegisterEvent(event) end
    self.frame:SetScript("OnEvent", function(_, event, ...)
        if event == "CHAT_MSG_ADDON" then self:Receive(...)
        else if not self.registered then self:RegisterPrefix() end; self:RefreshRoster(); self:Changed() end
    end)
end
