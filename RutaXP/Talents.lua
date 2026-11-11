local ADDON, ns = ...
ns.Talents = ns.Talents or {}
local T = ns.Talents

T.FIRST_LEVEL = 10
T.Registry = T.Registry or {}
T.ClassOrder = { "WARRIOR", "PALADIN", "HUNTER", "ROGUE", "PRIEST", "SHAMAN", "MAGE", "WARLOCK", "DRUID" }

local function safe(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, a, b, c = pcall(fn, ...)
    if ok then return a, b, c end
end

local function normalizeRace(raceToken)
    local r = tostring(raceToken or "")
    if r == "Scourge" or r == "Undead" then return "Undead" end
    if r == "HighElf" or r == "Skyborne" or r == "VoidElf" or r == "BloodElf" then return "Skyborne" end
    if r == "NightElf" or r == "Night Elf" then return "NightElf" end
    return r
end

function T.Register(data)
    if type(data) ~= "table" or not data.class then return end
    for id, n in pairs(data.nodes or {}) do
        if type(n[1]) == "number" then
            data.nodes[id] = {
                id = id,
                entry = n[1],
                max = n[2],
                spell = n[3],
                spec = n[4],
                row = n[5],
                col = n[6],
                name = n[7],
                nameEs = n[8] or n[7],
            }
        end
    end
    for _, b in ipairs(data.builds or {}) do
        local picks = {}
        for i, p in ipairs(b.picks or {}) do
            if type(p[1]) == "number" then
                picks[i] = { order = i, level = T.FIRST_LEVEL + i - 1, node = p[1], rank = p[2] }
            else
                picks[i] = p
            end
        end
        b.picks = picks
        b.data = data
        b.specName = b.specName or (data.specs and data.specs[b.spec]) or "Especialización"
    end
    T.Registry[data.class] = data
end

function T.DetectPlayer()
    local localizedClass, classToken = safe(UnitClass, "player")
    local localizedRace, raceToken = safe(UnitRace, "player")
    local faction = safe(UnitFactionGroup, "player")
    local level = tonumber(safe(UnitLevel, "player")) or 1
    classToken = (classToken and classToken:upper()) or "WARRIOR"
    local normRace = normalizeRace(raceToken)
    local raceGuide = T.RaceGuides and T.RaceGuides[normRace]
    local classData = T.Registry[classToken]
    return {
        classToken = classToken,
        className = (classData and classData.nameEs) or localizedClass or classToken,
        raceToken = normRace,
        raceName = (raceGuide and raceGuide.name) or localizedRace or normRace,
        raceGuide = raceGuide,
        faction = faction or (raceGuide and raceGuide.faction) or "Alliance",
        level = level,
    }
end

function T.Data(classToken)
    if not classToken then
        local p = T.DetectPlayer()
        classToken = p.classToken
    end
    return T.Registry[classToken]
end

local function clientEntryName(config, entryID, fallbackSpell)
    if config and entryID and C_Traits then
        local e = safe(C_Traits.GetEntryInfo, config, entryID)
        local d = e and e.definitionID and safe(C_Traits.GetDefinitionInfo, e.definitionID)
        if d then
            if d.overrideName and d.overrideName ~= "" then return d.spellID or fallbackSpell, d.overrideName end
            fallbackSpell = d.spellID or fallbackSpell
        end
    end
    if fallbackSpell then
        if C_Spell and C_Spell.GetSpellName then
            local sName = safe(C_Spell.GetSpellName, fallbackSpell)
            if sName and sName ~= "" then return fallbackSpell, sName end
        end
        if GetSpellInfo then
            local sName = safe(GetSpellInfo, fallbackSpell)
            if sName and sName ~= "" then return fallbackSpell, sName end
        end
    end
    return fallbackSpell, nil
end

local function clientGrantedPoints(config, treeID)
    if not (config and treeID and C_Traits and C_Traits.GetTreeCurrencyInfo) then return nil end
    local list = safe(C_Traits.GetTreeCurrencyInfo, config, treeID, false)
    if type(list) ~= "table" or not list[1] then return nil end
    local total
    for _, c in ipairs(list) do
        if type(c) ~= "table" or type(c.quantity) ~= "number" or type(c.spent) ~= "number" then return nil end
        total = (total or 0) + c.quantity + c.spent
    end
    return total
end

function T.ReadLive(data)
    if not data then return nil, "noclass" end
    local config = C_ClassTalents and safe(C_ClassTalents.GetActiveConfigID)
    if type(config) ~= "number" or config <= 0 then return nil, "noconfig" end
    local tree = data.tree
    if C_Traits and C_Traits.GetConfigInfo then
        local info = safe(C_Traits.GetConfigInfo, config)
        local trees = info and info.treeIDs
        if type(trees) ~= "table" or #trees == 0 then return nil, "notree" end
        if #trees == 1 then
            tree = trees[1]
        else
            tree = nil
            for _, id in ipairs(trees) do
                if id == data.tree then tree = id; break end
            end
            if not tree then return nil, "notree" end
        end
    end
    local ids = C_Traits and safe(C_Traits.GetTreeNodes, tree)
    if type(ids) ~= "table" or #ids == 0 then return nil, "notree" end
    local nodes, incomplete = {}, false
    for _, id in ipairs(ids) do
        local info = safe(C_Traits.GetNodeInfo, config, id)
        if info and info.ID == id and type(info.activeRank) == "number" and type(info.maxRanks) == "number" then
            local entry = (info.activeEntry and info.activeEntry.entryID) or (info.entryIDs and info.entryIDs[1])
            local spell, name = clientEntryName(config, entry, nil)
            nodes[id] = {
                active = info.activeRank,
                current = info.currentRank or info.activeRank,
                max = info.maxRanks,
                entry = entry,
                spell = spell,
                name = name,
            }
        elseif not (info and info.ID == 0 and info.activeRank == 0 and info.currentRank == 0) then
            incomplete = true
        end
    end
    return {
        config = config,
        nodes = nodes,
        incomplete = incomplete,
        granted = clientGrantedPoints(config, tree),
    }
end

local function sameTalent(node, live)
    if node.spell and live.spell then return node.spell == live.spell end
    if live.name then return live.name == node.nameEs or live.name == node.name end
    if live.entry then return live.entry == node.entry end
    return live.max == node.max
end

function T.Validate(data, live)
    local v = { map = {}, back = {}, names = {}, max = {}, missing = {}, ok = false }
    if not live or not live.nodes or not next(live.nodes) then return v end
    v.ok = not live.incomplete
    local bySpell, byName = {}, {}
    local function index(t, k, id)
        t[k] = t[k] == nil and id or false
    end
    for id, n in pairs(live.nodes) do
        if n.spell then index(bySpell, n.spell, id) end
        if n.name then index(byName, n.name, id) end
    end
    local candidates, owners = {}, {}
    for id, n in pairs(data.nodes) do
        local l = live.nodes[id]
        local hit
        if l and sameTalent(n, l) then
            hit = id
        else
            hit = n.spell and bySpell[n.spell]
            if not hit then
                local named = byName[n.nameEs] or byName[n.name]
                if named and not (live.nodes[named].spell and n.spell) then hit = named end
            end
        end
        if hit then
            candidates[id] = hit
            index(owners, hit, id)
        end
    end
    for id, n in pairs(data.nodes) do
        local hit = candidates[id]
        if hit and owners[hit] == id and live.nodes[hit].max > 0 then
            v.map[id], v.back[hit] = hit, id
            v.names[id], v.max[id] = live.nodes[hit].name, live.nodes[hit].max
        else
            v.missing[#v.missing + 1] = n.nameEs or n.name or tostring(id)
        end
    end
    for id, n in pairs(live.nodes) do
        if not v.back[id] and ((n.active or 0) > 0 or (n.current or 0) > 0) then v.ok = false end
    end
    return v
end

function T.NodeName(data, nodeID, valid)
    local n = data and data.nodes and data.nodes[nodeID]
    if not n then return tostring(nodeID) end
    if valid and valid.names and valid.names[nodeID] and valid.names[nodeID] ~= "" then
        return valid.names[nodeID]
    end
    local _, clientName = clientEntryName(nil, nil, n.spell)
    return n.nameEs or clientName or n.name or tostring(nodeID)
end

function T.State(build, ranks, level, granted)
    ranks = ranks or {}
    local s = {
        done = 0,
        total = #(build and build.picks or {}),
        offPlan = {},
        nodeNext = {},
        spent = 0,
        level = level or 1,
    }
    if not build or not build.picks then return s end
    local planned = {}
    for _, p in ipairs(build.picks) do
        planned[p.node] = math.max(planned[p.node] or 0, p.rank)
    end
    local off = false
    for id, r in pairs(ranks) do
        s.spent = s.spent + r
        if r > (planned[id] or 0) then
            s.offPlan[id] = r - (planned[id] or 0)
            off = true
        end
    end
    for _, p in ipairs(build.picks) do
        if (ranks[p.node] or 0) >= p.rank then
            s.done = s.done + 1
        else
            s.next = s.next or p
            s.nodeNext[p.node] = s.nodeNext[p.node] or p
        end
    end
    if type(granted) ~= "number" or granted < s.spent then
        s.status = "pointsunknown"
        return s
    end
    s.points, s.unspent = granted, granted - s.spent
    if s.points == 0 then
        s.status = "early"
    elseif off then
        s.status = "offplan"
    elseif not s.next then
        s.status = "complete"
    elseif s.unspent > 0 then
        s.status = "behind"
    else
        s.status = "onplan"
    end
    return s
end

local function charTalents()
    if not ns.char then return {} end
    if type(ns.char.talents) ~= "table" then
        ns.char.talents = { builds = {} }
    end
    if type(ns.char.talents.builds) ~= "table" then
        ns.char.talents.builds = {}
    end
    return ns.char.talents
end

function T.GetChoice(classToken)
    local p = T.DetectPlayer()
    local cls = classToken or p.classToken
    return charTalents().builds[cls] or "auto"
end

function T.SetChoice(key, classToken)
    local p = T.DetectPlayer()
    local cls = classToken or T.selectedClass or p.classToken
    charTalents().builds[cls] = (key and key ~= "auto") and key or nil
    T.Refresh()
end

-- Automatically pick the best matching build for the player's spent points, or the recommended build if no points spent
function T.BestBuild(data, ranks)
    if not data or not data.builds or #data.builds == 0 then return nil, "none" end
    local choice = T.GetChoice(data.class)
    if choice and choice ~= "auto" then
        for _, b in ipairs(data.builds) do
            if b.key == choice then return b, "chosen" end
        end
    end
    local totalSpent = 0
    for _, r in pairs(ranks or {}) do totalSpent = totalSpent + r end
    if totalSpent > 0 then
        local bestBuild, bestScore = nil, -math.huge
        for _, b in ipairs(data.builds) do
            local matched = 0
            local maxByNode = {}
            for _, p in ipairs(b.picks) do
                if p.order <= totalSpent + 5 then
                    maxByNode[p.node] = math.max(maxByNode[p.node] or 0, p.rank)
                end
            end
            for nodeID, r in pairs(ranks) do
                local cap = maxByNode[nodeID] or 0
                matched = matched + math.min(r, cap) * 3 - math.max(0, r - cap) * 2
            end
            if b.recommended then matched = matched + 0.5 end
            if matched > bestScore then
                bestScore = matched
                bestBuild = b
            end
        end
        if bestBuild then return bestBuild, "auto_points" end
    end
    for _, b in ipairs(data.builds) do
        if b.recommended then return b, "auto_recommended" end
    end
    return data.builds[1], "default"
end

local function ranksOf(valid, live, field)
    local out = {}
    if not (valid and live and live.nodes) then return out end
    for liveID, n in pairs(live.nodes) do
        local id = valid.back[liveID]
        if id and (n[field] or 0) > 0 then
            out[id] = n[field]
        end
    end
    return out
end

function T.Evaluate(classToken)
    local player = T.DetectPlayer()
    local cls = classToken or T.selectedClass or player.classToken
    local data = T.Data(cls)
    if not data then return nil end
    local isPlayerClass = (cls == player.classToken)
    local talentsUnlocked = isPlayerClass and player.level >= T.FIRST_LEVEL
    local live, liveReason
    if talentsUnlocked then live, liveReason = T.ReadLive(data) end
    local valid = T.Validate(data, live)
    local activeRanks = ranksOf(valid, live, "active")
    local stagedRanks = ranksOf(valid, live, "current")
    local build, source = T.BestBuild(data, stagedRanks)
    local unsupported
    if valid.ok and build then
        for _, pick in ipairs(build.picks) do
            -- An increased cap can also invalidate a later full-rank prerequisite.
            if valid.max[pick.node] ~= data.nodes[pick.node].max then
                valid.ok = false
                unsupported = T.NodeName(data, pick.node, valid)
                break
            end
        end
    end
    local compatible = isPlayerClass and valid.ok
    local level = isPlayerClass and player.level or 1
    local granted = 0
    if live then granted = live.granted end
    local state = T.State(build, activeRanks, level, granted)
    local staged = T.State(build, stagedRanks, level, granted)
    local unavailableReason
    if talentsUnlocked and not compatible then
        unavailableReason = unsupported and ("El plan incluye un rango que no se ha podido verificar para " .. unsupported .. ".")
            or live and "El cliente solo permite verificar parte del plan."
            or (liveReason == "notree" and "El cliente no ofrece un árbol compatible con esta guía."
            or "El cliente no permite leer tus talentos ahora. Puedes consultar la guía como referencia.")
        for _, s in ipairs({ state, staged }) do
            s.status, s.points, s.unspent, s.next = "unavailable", nil, nil, nil
            s.nodeNext = {}
            s.spent = nil
        end
        if live and not live.incomplete and next(live.nodes) then
            state.spent, staged.spent = 0, 0
            for _, node in pairs(live.nodes) do
                state.spent = state.spent + node.active
                staged.spent = staged.spent + node.current
            end
        end
    end
    return {
        player = player,
        isPlayerClass = isPlayerClass,
        data = data,
        build = build,
        source = source,
        live = live,
        valid = valid,
        compatible = compatible,
        unavailableReason = unavailableReason,
        activeRanks = activeRanks,
        stagedRanks = stagedRanks,
        state = state,
        staged = staged,
    }
end

---------------------------------------------------------------------------
-- Overlay on Blizzard's Talent Frame (PlayerSpellsFrame.TalentsFrame)
---------------------------------------------------------------------------

local marks = {}
local hookedButtons = setmetatable({}, { __mode = "k" })

local function getBlizzardTalentFrame()
    if PlayerSpellsFrame and PlayerSpellsFrame.TalentsFrame then
        return PlayerSpellsFrame.TalentsFrame, PlayerSpellsFrame
    end
    if PlayerTalentFrame then
        return PlayerTalentFrame, PlayerTalentFrame
    end
    return nil, nil
end

local function createEdge(parent, a, b, horizontal)
    local t = parent:CreateTexture(nil, "OVERLAY")
    t:SetColorTexture(1, 0.82, 0.18, 0.95)
    t:SetPoint(a, parent, a, 0, 0)
    t:SetPoint(b, parent, b, 0, 0)
    if horizontal then t:SetHeight(2) else t:SetWidth(2) end
    return t
end

local function getOrCreateMark(button)
    local m = marks[button]
    if m then return m end
    m = CreateFrame("Frame", nil, button)
    m:SetPoint("TOPLEFT", button, "TOPLEFT", -3, 3)
    m:SetPoint("BOTTOMRIGHT", button, "BOTTOMRIGHT", 3, -3)
    m:SetFrameLevel((button:GetFrameLevel() or 1) + 6)

    m.Ring = CreateFrame("Frame", nil, m)
    m.Ring:SetPoint("TOPLEFT", m, "TOPLEFT", -4, 4)
    m.Ring:SetPoint("BOTTOMRIGHT", m, "BOTTOMRIGHT", 4, -4)
    m.Ring.edges = {
        createEdge(m.Ring, "TOPLEFT", "TOPRIGHT", true),
        createEdge(m.Ring, "BOTTOMLEFT", "BOTTOMRIGHT", true),
        createEdge(m.Ring, "TOPLEFT", "BOTTOMLEFT", false),
        createEdge(m.Ring, "TOPRIGHT", "BOTTOMRIGHT", false),
    }

    m.NextTag = CreateFrame("Frame", nil, m.Ring)
    m.NextTag:SetSize(56, 13)
    m.NextTag:SetPoint("BOTTOM", m.Ring, "TOP", 0, 1)
    local tagBg = m.NextTag:CreateTexture(nil, "BACKGROUND")
    tagBg:SetAllPoints()
    tagBg:SetColorTexture(0.12, 0.09, 0.02, 0.92)
    m.NextTag.Text = m.NextTag:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    m.NextTag.Text:SetPoint("CENTER", 0, 0)
    m.NextTag.Text:SetText("|cffffd966SIGUIENTE|r")

    m.Badge = CreateFrame("Frame", nil, m)
    m.Badge:SetSize(22, 14)
    m.Badge:SetPoint("TOPRIGHT", m, "TOPRIGHT", 3, 3)
    local bBg = m.Badge:CreateTexture(nil, "BACKGROUND")
    bBg:SetAllPoints()
    bBg:SetColorTexture(0.05, 0.08, 0.14, 0.92)
    m.Badge.Text = m.Badge:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    m.Badge.Text:SetPoint("CENTER", 0, 0)

    marks[button] = m
    return m
end

local function hideAllMarks()
    for _, m in pairs(marks) do m:Hide() end
end

local function rankLimit(c, nodeID)
    return c.valid.max[nodeID] or c.data.nodes[nodeID].max
end

local function onTalentButtonEnter(button)
    if not GameTooltip or not GameTooltip:IsShown() then return end
    local c = T.current
    if not (c and c.isPlayerClass and c.compatible and c.staged and c.valid.ok) then return end
    local liveID = button.GetNodeID and safe(button.GetNodeID, button)
    local id = liveID and c.valid.back[liveID]
    if not id then return end
    local pick = c.staged.nodeNext[id]
    local off = c.staged.offPlan[id]
    local isNext = c.staged.status ~= "offplan" and c.staged.status ~= "pointsunknown" and c.staged.next and c.staged.next.node == id
    local node = c.data.nodes[id]
    if off then
        GameTooltip:AddLine("RutaXP (" .. c.build.title .. "): punto fuera de esta guía", 1, 0.45, 0.35, true)
    elseif pick and node then
        local line = string.format("RutaXP: Paso #%d (Niv. %d) · Rango %d/%d", pick.order, pick.level, pick.rank, rankLimit(c, id))
        if isNext then
            GameTooltip:AddLine(line .. " [SIGUIENTE A SUBIR]", 1, 0.85, 0.35, true)
        else
            GameTooltip:AddLine(line, 0.55, 0.82, 1, true)
        end
    else
        GameTooltip:AddLine("RutaXP: Talento completado en esta guía", 0.49, 0.87, 0.61, true)
    end
    GameTooltip:Show()
end

function T.DrawOverlay()
    local tf = getBlizzardTalentFrame()
    if not tf or not tf:IsShown() or not tf.EnumerateAllTalentButtons then
        return hideAllMarks()
    end
    if InCombatLockdown and InCombatLockdown() then
        return hideAllMarks()
    end
    local c = T.current
    if not (c and c.isPlayerClass and c.compatible and c.staged and c.valid.ok) then
        return hideAllMarks()
    end
    if tf.IsInspecting and safe(tf.IsInspecting, tf) then
        return hideAllMarks()
    end
    local seen = {}
    for button in tf:EnumerateAllTalentButtons() do
        local liveID = button.GetNodeID and safe(button.GetNodeID, button)
        local id = liveID and c.valid.back[liveID]
        if not hookedButtons[button] and button.HookScript then
            button:HookScript("OnEnter", onTalentButtonEnter)
            hookedButtons[button] = true
        end
        if id then
            local pick = c.staged.nodeNext[id]
            local isNext = c.staged.status ~= "offplan" and c.staged.status ~= "pointsunknown" and c.staged.next and c.staged.next.node == id
            if pick then
                local m = getOrCreateMark(button)
                seen[m] = true
                m.Ring:SetShown(isNext == true)
                m.NextTag:SetShown(isNext == true)
                m.Badge:Show()
                if isNext then
                    m.Badge.Text:SetText("|cffffd966#" .. pick.order .. "|r")
                else
                    m.Badge.Text:SetText("|cff9bc7ff#" .. pick.order .. "|r")
                end
                m:Show()
            end
        end
    end
    for _, m in pairs(marks) do
        if not seen[m] then m:Hide() end
    end
end

---------------------------------------------------------------------------
-- Interactive Talent & Character Build Panel (opens on 'N' or button)
---------------------------------------------------------------------------

local function createCard(parent, bgR, bgG, bgB, bgA, borderR, borderG, borderB, borderA)
    local f = CreateFrame("Frame", nil, parent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    if f.SetBackdrop then
        f:SetBackdrop({
            bgFile = "Interface\\Buttons\\WHITE8X8",
            edgeFile = "Interface\\Buttons\\WHITE8X8",
            edgeSize = 1,
        })
        f:SetBackdropColor(bgR or 0.06, bgG or 0.08, bgB or 0.12, bgA or 0.94)
        f:SetBackdropBorderColor(borderR or 0.22, borderG or 0.30, borderB or 0.42, borderA or 0.85)
    end
    return f
end

local function createPillButton(parent, width, height, text, onClick)
    local btn = CreateFrame("Button", nil, parent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    btn:SetSize(width, height)
    if btn.SetBackdrop then
        btn:SetBackdrop({
            bgFile = "Interface\\Buttons\\WHITE8X8",
            edgeFile = "Interface\\Buttons\\WHITE8X8",
            edgeSize = 1,
        })
    end
    btn.label = btn:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    btn.label:SetPoint("LEFT", 6, 0)
    btn.label:SetPoint("RIGHT", -6, 0)
    btn.label:SetJustifyH("CENTER")
    btn.label:SetWordWrap(false)
    btn.label:SetText(text or "")

    function btn:SetActiveStyle(active, accentGold)
        self.isActive = active
        if not self.SetBackdropColor then return end
        if active then
            if accentGold then
                self:SetBackdropColor(0.28, 0.21, 0.06, 0.96)
                self:SetBackdropBorderColor(0.95, 0.76, 0.25, 0.95)
            else
                self:SetBackdropColor(0.12, 0.24, 0.38, 0.96)
                self:SetBackdropBorderColor(0.40, 0.72, 1.00, 0.95)
            end
        else
            self:SetBackdropColor(0.08, 0.11, 0.16, 0.92)
            self:SetBackdropBorderColor(0.20, 0.27, 0.36, 0.80)
        end
    end

    btn:SetActiveStyle(false, false)
    btn:SetScript("OnClick", onClick)
    return btn
end

function T.PositionPanel()
    local panel = T.panel
    if not panel then return end
    local _, hostFrame = getBlizzardTalentFrame()
    if hostFrame and hostFrame:IsShown() and not panel.userDragged then
        panel:ClearAllPoints()
        local rightEdge = hostFrame:GetRight() or 0
        local screenW = UIParent and UIParent.GetWidth and UIParent:GetWidth() or 1920
        if rightEdge > 0 and (rightEdge + panel:GetWidth() + 16) <= screenW then
            panel:SetPoint("TOPLEFT", hostFrame, "TOPRIGHT", 8, 0)
        else
            panel:SetPoint("TOPRIGHT", UIParent, "TOPRIGHT", -24, -80)
        end
    end
end

function T.CreatePanel()
    if T.panel then return T.panel end

    local panel = createCard(UIParent, 0.04, 0.06, 0.10, 0.97, 0.82, 0.66, 0.25, 0.92)
    panel:SetSize(440, 610)
    panel:SetPoint("CENTER", UIParent, "CENTER", 260, 20)
    panel:SetFrameStrata("HIGH")
    panel:SetToplevel(true)
    panel:SetMovable(true)
    panel:EnableMouse(true)
    panel:RegisterForDrag("LeftButton")
    panel:SetScript("OnDragStart", function(f)
        f.userDragged = true
        f:StartMoving()
    end)
    panel:SetScript("OnDragStop", function(f)
        f:StopMovingOrSizing()
    end)
    panel:Hide()
    T.panel = panel

    -- Top Header Bar
    local header = createCard(panel, 0.08, 0.11, 0.18, 0.98, 0.28, 0.38, 0.54, 0.70)
    header:SetPoint("TOPLEFT", 1, -1)
    header:SetPoint("TOPRIGHT", -1, -1)
    header:SetHeight(48)

    local title = header:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
    title:SetPoint("TOPLEFT", 12, -8)
    title:SetText("|cffffd966RutaXP|r · Guías de Talentos y Personaje")

    panel.detectedText = header:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    panel.detectedText:SetPoint("TOPLEFT", title, "BOTTOMLEFT", 0, -3)
    panel.detectedText:SetJustifyH("LEFT")

    local closeBtn = CreateFrame("Button", nil, header, "UIPanelCloseButton")
    closeBtn:SetPoint("TOPRIGHT", -2, -2)
    closeBtn:SetScript("OnClick", function()
        panel.closedByUser = true
        panel:Hide()
    end)

    -- Class selector button (defaults to player's detected class, click to cycle or reset to player class)
    panel.classBtn = createPillButton(header, 128, 22, "Mi Clase", function(_, button)
        if button == "RightButton" or not T.selectedClass then
            local p = T.DetectPlayer()
            if T.selectedClass and T.selectedClass ~= p.classToken then
                T.selectedClass = nil
                T.Refresh()
                return
            end
        end
        local currentCls = T.selectedClass or T.DetectPlayer().classToken
        local nextIdx = 1
        for i, cls in ipairs(T.ClassOrder) do
            if cls == currentCls then
                nextIdx = (i % #T.ClassOrder) + 1
                break
            end
        end
        local picked = T.ClassOrder[nextIdx]
        if picked == T.DetectPlayer().classToken then
            T.selectedClass = nil
        else
            T.selectedClass = picked
        end
        T.Refresh()
    end)
    panel.classBtn:RegisterForClicks("LeftButtonUp", "RightButtonUp")
    panel.classBtn:SetPoint("BOTTOMRIGHT", header, "BOTTOMRIGHT", -34, 6)

    -- Section: Build Options (4 buttons in a 2x2 grid + Auto button)
    local selectorLabel = panel:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    selectorLabel:SetPoint("TOPLEFT", 12, -56)
    selectorLabel:SetText("|cff8ec5ffELIGE TU GUÍA DE TALENTOS (4 OPCIONES PARA TU CLASE):|r")

    panel.autoBtn = createPillButton(panel, 96, 18, "Auto (Detectar)", function()
        T.SetChoice("auto")
    end)
    panel.autoBtn:SetPoint("TOPRIGHT", -12, -54)

    panel.buildBtns = {}
    for i = 1, 4 do
        local col = (i - 1) % 2
        local row = math.floor((i - 1) / 2)
        local btn = createCard(panel, 0.07, 0.10, 0.15, 0.94, 0.20, 0.28, 0.38, 0.85)
        btn:SetSize(204, 42)
        btn:SetPoint("TOPLEFT", 12 + col * 210, -76 - row * 46)
        btn:EnableMouse(true)

        btn.nameText = btn:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
        btn.nameText:SetPoint("TOPLEFT", 8, -6)
        btn.nameText:SetPoint("TOPRIGHT", -8, -6)
        btn.nameText:SetJustifyH("LEFT")
        btn.nameText:SetWordWrap(false)

        btn.metaText = btn:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
        btn.metaText:SetPoint("TOPLEFT", btn.nameText, "BOTTOMLEFT", 0, -3)
        btn.metaText:SetPoint("TOPRIGHT", btn.nameText, "BOTTOMRIGHT", 0, -3)
        btn.metaText:SetJustifyH("LEFT")
        btn.metaText:SetWordWrap(false)

        btn:SetScript("OnMouseUp", function(self)
            if self.buildKey then
                T.SetChoice(self.buildKey)
            end
        end)
        panel.buildBtns[i] = btn
    end

    -- Next Talent Highlight Box
    local nextCard = createCard(panel, 0.11, 0.14, 0.08, 0.96, 0.88, 0.72, 0.24, 0.95)
    nextCard:SetPoint("TOPLEFT", 12, -172)
    nextCard:SetPoint("TOPRIGHT", -12, -172)
    nextCard:SetHeight(50)
    panel.nextCard = nextCard

    nextCard.header = nextCard:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    nextCard.header:SetPoint("TOPLEFT", 10, -6)
    nextCard.header:SetPoint("TOPRIGHT", -10, -6)
    nextCard.header:SetJustifyH("LEFT")

    nextCard.main = nextCard:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    nextCard.main:SetPoint("TOPLEFT", nextCard.header, "BOTTOMLEFT", 0, -3)
    nextCard.main:SetPoint("TOPRIGHT", nextCard.header, "BOTTOMRIGHT", 0, -3)
    nextCard.main:SetJustifyH("LEFT")
    nextCard.main:SetWordWrap(false)

    -- Character Guide Card (Stats, Weapons, Skills, Race Tip)
    local infoCard = createCard(panel, 0.06, 0.09, 0.14, 0.95, 0.22, 0.34, 0.48, 0.85)
    infoCard:SetPoint("TOPLEFT", 12, -228)
    infoCard:SetPoint("TOPRIGHT", -12, -228)
    infoCard:SetHeight(138)
    panel.infoCard = infoCard

    infoCard.text = infoCard:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    infoCard.text:SetPoint("TOPLEFT", 10, -8)
    infoCard.text:SetPoint("BOTTOMRIGHT", -10, 8)
    infoCard.text:SetJustifyH("LEFT")
    infoCard.text:SetJustifyV("TOP")
    infoCard.text:SetSpacing(2)

    -- Tab selector: Talent Order (10-60) vs Trainer Spells to Buy (1-60)
    panel.activeTab = "talents"
    panel.tabTalentsBtn = createPillButton(panel, 204, 20, "Talentos (Niv. 10–60)", function()
        panel.activeTab = "talents"
        panel.lastScrolledBuild = nil
        T.RenderPanel()
    end)
    panel.tabTalentsBtn:SetPoint("TOPLEFT", 12, -368)

    panel.tabSpellsBtn = createPillButton(panel, 206, 20, "Habilidades a Comprar (1–60)", function()
        panel.activeTab = "spells"
        panel.lastScrolledBuild = nil
        T.RenderPanel()
    end)
    panel.tabSpellsBtn:SetPoint("TOPRIGHT", -12, -368)

    local listBox = createCard(panel, 0.03, 0.05, 0.08, 0.96, 0.18, 0.26, 0.36, 0.85)
    listBox:SetPoint("TOPLEFT", 12, -390)
    listBox:SetPoint("BOTTOMRIGHT", -12, 12)

    local scroll = CreateFrame("ScrollFrame", "RutaXPTalentScrollFrame", listBox, "UIPanelScrollFrameTemplate")
    scroll:SetPoint("TOPLEFT", 6, -6)
    scroll:SetPoint("BOTTOMRIGHT", -26, 6)
    if scroll.SetClipsChildren then scroll:SetClipsChildren(true) end
    panel.scroll = scroll

    local content = CreateFrame("Frame", nil, scroll)
    content:SetSize(380, 1)
    scroll:SetScrollChild(content)
    panel.content = content
    panel.rows = {}

    return panel
end

local function ensureRow(panel, index)
    local row = panel.rows[index]
    if row then return row end
    row = CreateFrame("Frame", nil, panel.content, BackdropTemplateMixin and "BackdropTemplate" or nil)
    row:SetSize(380, 22)
    row:EnableMouse(true)
    if row.SetBackdrop then
        row:SetBackdrop({
            bgFile = "Interface\\Buttons\\WHITE8X8",
            edgeFile = "Interface\\Buttons\\WHITE8X8",
            edgeSize = 1,
        })
    end
    row.lvl = row:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    row.lvl:SetPoint("LEFT", 6, 0)
    row.lvl:SetWidth(62)
    row.lvl:SetJustifyH("LEFT")

    row.name = row:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row.name:SetPoint("LEFT", 70, 0)
    row.name:SetPoint("RIGHT", -92, 0)
    row.name:SetJustifyH("LEFT")
    row.name:SetWordWrap(false)

    row.spec = row:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    row.spec:SetPoint("RIGHT", -6, 0)
    row.spec:SetWidth(82)
    row.spec:SetJustifyH("RIGHT")
    row.spec:SetWordWrap(false)

    row:SetScript("OnEnter", function(self)
        if not self.tipTitle or not GameTooltip then return end
        GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
        GameTooltip:SetText(self.tipTitle, 1, 0.85, 0.35)
        if self.tipBody and self.tipBody ~= "" then
            GameTooltip:AddLine(self.tipBody, 0.85, 0.92, 1, true)
        end
        GameTooltip:Show()
    end)
    row:SetScript("OnLeave", function()
        if GameTooltip then GameTooltip:Hide() end
    end)

    panel.rows[index] = row
    return row
end

local function renderSpentTalents(panel, c)
    local talents = {}
    for id, node in pairs(c.live.nodes) do
        local rank = node.current or node.active or 0
        if rank > 0 then
            local match = c.valid.back[id]
            local known = match and c.data.nodes[match]
            local name = node.name or (known and (known.nameEs or known.name)) or ("Talento " .. id)
            local spec = known and c.data.specs and c.data.specs[known.spec]
            talents[#talents + 1] = {id = id, name = name, rank = rank, max = node.max, spec = spec}
        end
    end
    table.sort(talents, function(a, b)
        if a.name == b.name then return a.id < b.id end
        return a.name < b.name
    end)
    for i, talent in ipairs(talents) do
        local row = ensureRow(panel, i)
        row:ClearAllPoints()
        row:SetPoint("TOPLEFT", panel.content, "TOPLEFT", 0, -(i - 1) * 23)
        local ranks = talent.max and talent.max >= talent.rank
            and string.format("%d/%d", talent.rank, talent.max) or tostring(talent.rank)
        row.tipTitle = string.format("%s (%s)", talent.name, ranks)
        row.tipBody = talent.spec
        row.lvl:SetText("|cff7edd9cActual|r")
        row.name:SetText(row.tipTitle)
        row.spec:SetText(talent.spec or "")
        if row.SetBackdropColor then
            row:SetBackdropColor(0.05, 0.11, 0.08, 0.75)
            row:SetBackdropBorderColor(0.14, 0.28, 0.20, 0.50)
        end
        row:Show()
    end
    return #talents
end

function T.RenderPanel()
    local panel = T.panel
    if not panel or not panel:IsShown() then return end
    local c = T.current or T.Evaluate()
    if not c then return end

    local p = c.player
    local data = c.data
    local build = c.build
    local s = c.staged or c.state
    local showLiveRanks = not c.compatible and c.live and next(c.live.nodes) ~= nil

    if c.isPlayerClass then
        local progress = ""
        if (c.compatible or showLiveRanks) and c.state.spent ~= nil then
            progress = string.format(" · %d pts. gastados", c.state.spent)
        elseif showLiveRanks then
            progress = " · Árbol del personaje"
        elseif s.status == "unavailable" then
            progress = " · Solo referencia"
        end
        panel.detectedText:SetText(string.format("|cff7edd9cDetectado:|r %s %s · Nivel %d%s", p.raceName, p.className, p.level, progress))
        panel.classBtn.label:SetText("Clase: " .. data.nameEs .. " »")
        panel.classBtn:SetActiveStyle(false, false)
    else
        panel.detectedText:SetText(string.format("|cffffce72Viendo clase:|r %s (Clic der. en Clase para volver a %s)", data.nameEs, p.className))
        panel.classBtn.label:SetText("Clase: " .. data.nameEs .. " »")
        panel.classBtn:SetActiveStyle(true, false)
    end

    local choice = T.GetChoice(data.class)
    panel.autoBtn:SetActiveStyle(choice == "auto", false)

    for i = 1, 4 do
        local btn = panel.buildBtns[i]
        local b = data.builds[i]
        if b then
            btn.buildKey = b.key
            local isSelected = (b == build)
            local prefix = isSelected and "|cffffd966» " or (b.recommended and "|cff7edd9c* " or "|cffd5deeb")
            btn.nameText:SetText(prefix .. b.title .. "|r")
            btn.metaText:SetText(string.format("|cff8ec5ff%s|r · |cff9fb0c7%s|r", b.role or b.specName, b.split or ""))
            if btn.SetBackdropColor then
                if isSelected then
                    btn:SetBackdropColor(0.18, 0.15, 0.05, 0.96)
                    btn:SetBackdropBorderColor(0.95, 0.78, 0.25, 0.98)
                else
                    btn:SetBackdropColor(0.07, 0.10, 0.15, 0.92)
                    btn:SetBackdropBorderColor(0.20, 0.28, 0.38, 0.80)
                end
            end
            btn:Show()
        else
            btn:Hide()
        end
    end

    local activeTab = panel.activeTab or "talents"
    if panel.tabTalentsBtn then
        panel.tabTalentsBtn.label:SetText(showLiveRanks and "Tus talentos" or "Talentos (Niv. 10–60)")
        panel.tabTalentsBtn:SetActiveStyle(activeTab == "talents", true)
    end
    if panel.tabSpellsBtn then panel.tabSpellsBtn:SetActiveStyle(activeTab == "spells", true) end

    -- Find next/current trainer spell for the player's level
    local trainerSpells = data.trainerSpells or {}
    local nextSpellEntry = nil
    for _, sp in ipairs(trainerSpells) do
        if not c.isPlayerClass or sp.level >= p.level then
            nextSpellEntry = sp
            break
        end
    end
    if not nextSpellEntry and #trainerSpells > 0 then
        nextSpellEntry = trainerSpells[#trainerSpells]
    end

    -- Next Highlight Box (shows Next Talent in Talents tab, or Next Trainer Skill in Spells tab)
    if activeTab == "spells" and nextSpellEntry then
        if c.isPlayerClass and nextSpellEntry.level <= p.level then
            panel.nextCard.header:SetText(string.format("|cffffd966HABILIDADES DISPONIBLES EN INSTRUCTOR (NIVEL %d):|r", nextSpellEntry.level))
        else
            panel.nextCard.header:SetText(string.format("|cff8ec5ffPRÓXIMAS HABILIDADES EN INSTRUCTOR (NIVEL %d):|r", nextSpellEntry.level))
        end
        panel.nextCard.main:SetText(string.format("|cffffd966» %s|r  ·  |cff7edd9c%s|r", nextSpellEntry.name, nextSpellEntry.tip or ""))
    elseif showLiveRanks then
        panel.nextCard.header:SetText("|cffffb468GUÍA POR NIVEL NO DISPONIBLE|r")
        panel.nextCard.main:SetText("La lista muestra tus rangos actuales del juego.")
    elseif s.status == "unavailable" then
        panel.nextCard.header:SetText("|cffffb468LECTURA DE TALENTOS NO DISPONIBLE|r")
        panel.nextCard.main:SetText(c.unavailableReason or "Consulta el orden de esta guía como referencia.")
    elseif s.next then
        local nextNode = data.nodes[s.next.node]
        local nextSpec = (data.specs and nextNode and data.specs[nextNode.spec]) or build.specName
        local nextName = T.NodeName(data, s.next.node, c.valid)
        if not c.isPlayerClass then
            panel.nextCard.header:SetText("|cff8ec5ffPRIMER PUNTO DE ESTA GUÍA (NIVEL 10):|r")
        elseif p.level < T.FIRST_LEVEL and s.points == 0 then
            panel.nextCard.header:SetText(string.format("|cff8ec5ffPRIMER PUNTO AL LLEGAR A NIVEL %d|r", T.FIRST_LEVEL))
        elseif s.status == "offplan" then
            panel.nextCard.header:SetText("|cffffb468TU REPARTO DIFIERE DE ESTA GUÍA · REVISA EL ORDEN ANTES DE GASTAR|r")
        elseif s.status == "pointsunknown" then
            panel.nextCard.header:SetText("|cff8ec5ffPRÓXIMO TALENTO · PUNTOS POR CONFIRMAR|r")
        elseif (s.unspent or 0) > 0 then
            panel.nextCard.header:SetText(string.format("|cffffd966TIENES %d PUNTO(S) DISPONIBLE(S) · SUBE AHORA MISMO:|r", s.unspent))
        else
            panel.nextCard.header:SetText("|cff7edd9cCUANDO TENGAS OTRO PUNTO|r")
        end
        panel.nextCard.main:SetText(string.format("|cffffd966» %s|r |cffffffff(Rango %d/%d)|r  ·  |cff8ec5ffRama %s|r", nextName, s.next.rank, rankLimit(c, s.next.node), nextSpec))
    else
        panel.nextCard.header:SetText("|cff7edd9c¡GUÍA DE TALENTOS COMPLETADA!|r")
        panel.nextCard.main:SetText("Has aprendido los 51 puntos de talento de esta guía.")
    end

    -- Character Guide Summary (Stats, Weapons, Skills, Rotation & Racial Tip)
    local infoLines = {}
    infoLines[#infoLines + 1] = "|cffffd966Estadísticas a buscar:|r |cffffffff" .. (build.stats or "-") .. "|r"
    infoLines[#infoLines + 1] = "|cff8ec5ffMejores armas:|r |cffd5deeb" .. (build.weapons or "-") .. "|r"
    infoLines[#infoLines + 1] = "|cff7edd9cHabilidades clave (" .. (build.specName or "") .. "):|r |cffd5deeb" .. (build.skills or "-") .. "|r"
    infoLines[#infoLines + 1] = "|cffffb468Cómo jugar:|r |cffd5deeb" .. (build.rotation or "-") .. "|r"
    if p.raceGuide then
        infoLines[#infoLines + 1] = "|cffc9b3ffConsejo " .. p.raceName .. ":|r |cffd5deeb" .. p.raceGuide.tip .. "|r"
    end
    panel.infoCard.text:SetText(table.concat(infoLines, "\n"))

    -- Render Scroll List: either 51 Talent Picks OR Level 1-60 Trainer Spells
    local y = 0
    local scrollTargetY = nil
    local shownRows = 0

    if activeTab == "spells" then
        for i, sp in ipairs(trainerSpells) do
            shownRows = i
            local row = ensureRow(panel, i)
            row:ClearAllPoints()
            row:SetPoint("TOPLEFT", panel.content, "TOPLEFT", 0, -y)

            local isCurrentOrNext = (sp == nextSpellEntry)
            local isPast = c.isPlayerClass and (sp.level < p.level) and not isCurrentOrNext
            local prioTag
            if sp.prio == "must" then
                prioTag = "|cff7edd9c[COMPRAR]|r"
            elseif sp.prio == "good" then
                prioTag = "|cff8ec5ff[Útil]|r"
            else
                prioTag = "|cff9fb0c7[Ahorrar oro]|r"
            end

            row.tipTitle = string.format("Nivel %d · %s", sp.level, sp.name)
            row.tipBody = sp.tip or ""

            if isCurrentOrNext then
                scrollTargetY = math.max(0, y - 44)
                if row.SetBackdropColor then
                    row:SetBackdropColor(0.22, 0.18, 0.05, 0.95)
                    row:SetBackdropBorderColor(0.95, 0.78, 0.25, 0.90)
                end
                row.lvl:SetText(string.format("|cffffd966» Niv. %d|r", sp.level))
                row.name:SetText("|cffffd966" .. sp.name .. "|r")
                row.spec:SetText(prioTag)
            elseif isPast then
                if row.SetBackdropColor then
                    row:SetBackdropColor(0.05, 0.11, 0.08, 0.75)
                    row:SetBackdropBorderColor(0.14, 0.28, 0.20, 0.50)
                end
                row.lvl:SetText(string.format("|cff7edd9cNiv. %d|r", sp.level))
                row.name:SetText("|cff9be0b5" .. sp.name .. "|r")
                row.spec:SetText(prioTag)
            else
                if row.SetBackdropColor then
                    local even = (i % 2 == 0)
                    row:SetBackdropColor(even and 0.05 or 0.04, even and 0.08 or 0.06, even and 0.12 or 0.10, 0.82)
                    row:SetBackdropBorderColor(0.12, 0.18, 0.26, 0.45)
                end
                row.lvl:SetText(string.format("|cff9fb0c7Niv. %d|r", sp.level))
                row.name:SetText("|cffd5deeb" .. sp.name .. "|r")
                row.spec:SetText(prioTag)
            end

            row:Show()
            y = y + 23
        end
    elseif showLiveRanks then
        shownRows = renderSpentTalents(panel, c)
        y, scrollTargetY = shownRows * 23, 0
    else
        for i, pick in ipairs(build.picks) do
            shownRows = i
            local row = ensureRow(panel, i)
            row:ClearAllPoints()
            row:SetPoint("TOPLEFT", panel.content, "TOPLEFT", 0, -y)

            local node = data.nodes[pick.node]
            local maxRank = rankLimit(c, pick.node)
            local specName = (data.specs and node and data.specs[node.spec]) or ""
            local tName = T.NodeName(data, pick.node, c.valid)
            local isDone = c.compatible and ((c.stagedRanks[pick.node] or 0) >= pick.rank)
            local isNext = s.status ~= "unavailable" and (s.next == pick)

            row.tipTitle = string.format("Nivel %d · %s (Rango %d/%d)", pick.level, tName, pick.rank, maxRank)
            row.tipBody = (build.notes and build.notes[pick.level]) or ("Rama: " .. specName)

            if isNext then
                scrollTargetY = math.max(0, y - 44)
                if row.SetBackdropColor then
                    row:SetBackdropColor(0.22, 0.18, 0.05, 0.95)
                    row:SetBackdropBorderColor(0.95, 0.78, 0.25, 0.90)
                end
                row.lvl:SetText(string.format("|cffffd966» Niv. %d|r", pick.level))
                row.name:SetText(string.format("|cffffd966%s|r |cffffffff(%d/%d)|r", tName, pick.rank, maxRank))
                row.spec:SetText("|cffffd966" .. specName .. "|r")
            elseif isDone then
                if row.SetBackdropColor then
                    row:SetBackdropColor(0.05, 0.11, 0.08, 0.75)
                    row:SetBackdropBorderColor(0.14, 0.28, 0.20, 0.50)
                end
                row.lvl:SetText(string.format("|cff7edd9c[Hecho] %d|r", pick.level))
                row.name:SetText(string.format("|cff7edd9c%s (%d/%d)|r", tName, pick.rank, maxRank))
                row.spec:SetText("|cff6c8c7a" .. specName .. "|r")
            else
                if row.SetBackdropColor then
                    local even = (i % 2 == 0)
                    row:SetBackdropColor(even and 0.05 or 0.04, even and 0.08 or 0.06, even and 0.12 or 0.10, 0.82)
                    row:SetBackdropBorderColor(0.12, 0.18, 0.26, 0.45)
                end
                row.lvl:SetText(string.format("|cff9fb0c7Niv. %d|r", pick.level))
                row.name:SetText(string.format("|cffd5deeb%s|r |cff8ec5ff(%d/%d)|r", tName, pick.rank, maxRank))
                row.spec:SetText("|cff8ec5ff" .. specName .. "|r")
            end

            row:Show()
            y = y + 23
        end
    end

    for i = shownRows + 1, #panel.rows do
        panel.rows[i]:Hide()
    end
    panel.content:SetHeight(math.max(1, y + 6))

    local scrollKey = build.key .. ":" .. activeTab .. (showLiveRanks and ":live" or "")
    if scrollTargetY and panel.scroll.SetVerticalScroll and panel.lastScrolledBuild ~= scrollKey then
        panel.lastScrolledBuild = scrollKey
        safe(panel.scroll.SetVerticalScroll, panel.scroll, scrollTargetY)
    end
end

function T.Refresh()
    T.current = T.Evaluate()
    T.DrawOverlay()
    if T.panel and T.panel:IsShown() then
        T.PositionPanel()
        T.RenderPanel()
    end
    return T.current
end

function T.TogglePanel(forceShow, tab)
    local panel = T.CreatePanel()
    if tab then
        panel.activeTab = tab
        panel.lastScrolledBuild = nil
    end
    if forceShow == true then
        panel.closedByUser = false
        panel:Show()
    elseif forceShow == false then
        panel:Hide()
    elseif panel:IsShown() then
        panel.closedByUser = true
        panel:Hide()
    else
        panel.closedByUser = false
        panel:Show()
    end
    if panel:IsShown() then
        T.Refresh()
    end
end

---------------------------------------------------------------------------
-- Hooks for pressing 'N' / Opening the Talent Frame / Class Trainer
---------------------------------------------------------------------------

local attachedFrames = {}

local function attachToBlizzardFrame()
    local tf, hostFrame = getBlizzardTalentFrame()
    if tf and not attachedFrames[tf] then
        attachedFrames[tf] = true
        if tf.HookScript then
            tf:HookScript("OnShow", function()
                T._justClosedByBlizzard = false
                local panel = T.CreatePanel()
                panel.standaloneOpen = false
                panel.closedByUser = false
                panel:Show()
                T.Refresh()
            end)
            tf:HookScript("OnHide", function()
                T._justClosedByBlizzard = true
                T._closedAt = type(GetTime) == "function" and GetTime() or 0
                hideAllMarks()
                if T.panel and not T.panel.standaloneOpen then
                    T.panel:Hide()
                end
            end)
        end
        if EventRegistry and EventRegistry.RegisterCallback then
            safe(EventRegistry.RegisterCallback, EventRegistry, "TalentFrameBase.ButtonsUpdated", function() T.Refresh() end, T)
            safe(EventRegistry.RegisterCallback, EventRegistry, "TalentFrameBase.ConfigUpdated", function() T.Refresh() end, T)
            safe(EventRegistry.RegisterCallback, EventRegistry, "PlayerSpellsFrame.TalentTab.Show", function()
                local panel = T.CreatePanel()
                panel.standaloneOpen = false
                panel.closedByUser = false
                panel:Show()
                T.Refresh()
            end, T)
        end
    end
    if hostFrame and hostFrame ~= tf and not attachedFrames[hostFrame] then
        attachedFrames[hostFrame] = true
        if hostFrame.HookScript then
            hostFrame:HookScript("OnHide", function()
                T._justClosedByBlizzard = true
                T._closedAt = type(GetTime) == "function" and GetTime() or 0
                hideAllMarks()
                if T.panel and not T.panel.standaloneOpen then
                    T.panel:Hide()
                end
            end)
        end
    end
end

local function onTalentKeyTriggered()
    attachToBlizzardFrame()
    local now = type(GetTime) == "function" and GetTime() or 0
    if T._justClosedByBlizzard and T._closedAt == now then
        T._justClosedByBlizzard = false
        return
    end
    T._justClosedByBlizzard = false
    local tf, host = getBlizzardTalentFrame()
    if (tf and tf:IsShown()) or (host and host:IsShown()) then
        local panel = T.CreatePanel()
        panel.standaloneOpen = false
        panel.closedByUser = false
        panel:Show()
        T.Refresh()
    else
        -- Even if character is under level 10 and Blizzard didn't open TalentFrame, toggle our Talent Guide on N!
        local panel = T.CreatePanel()
        panel.standaloneOpen = not panel:IsShown()
        T.TogglePanel()
    end
end

local hookedToggles = false
local function hookTalentKeybindFunctions()
    if hookedToggles then return end
    hookedToggles = true
    if type(hooksecurefunc) == "function" then
        if type(_G.ToggleTalentFrame) == "function" then
            hooksecurefunc("ToggleTalentFrame", onTalentKeyTriggered)
        end
        if type(_G.PlayerSpellsUtil) == "table" then
            if type(_G.PlayerSpellsUtil.ToggleClassTalentOrSpecFrame) == "function" then
                hooksecurefunc(_G.PlayerSpellsUtil, "ToggleClassTalentOrSpecFrame", onTalentKeyTriggered)
            end
            if type(_G.PlayerSpellsUtil.OpenToClassTalentsTab) == "function" then
                hooksecurefunc(_G.PlayerSpellsUtil, "OpenToClassTalentsTab", onTalentKeyTriggered)
            end
        end
    end
end

local evFrame = CreateFrame("Frame")
for _, ev in ipairs({
    "PLAYER_LOGIN",
    "ADDON_LOADED",
    "PLAYER_LEVEL_UP",
    "TRAIT_CONFIG_UPDATED",
    "TRAIT_NODE_CHANGED",
    "TRAIT_TREE_CURRENCY_INFO_UPDATED",
    "ACTIVE_TALENT_GROUP_CHANGED",
    "PLAYER_TALENT_UPDATE",
    "PLAYER_REGEN_ENABLED",
    "TRAINER_SHOW",
}) do
    pcall(evFrame.RegisterEvent, evFrame, ev)
end

evFrame:SetScript("OnEvent", function(_, event, arg1)
    if event == "PLAYER_LOGIN" then
        hookTalentKeybindFunctions()
        attachToBlizzardFrame()
        T.Refresh()
    elseif event == "ADDON_LOADED" and (arg1 == "Blizzard_PlayerSpells" or arg1 == "Blizzard_TalentUI") then
        attachToBlizzardFrame()
        T.Refresh()
    elseif event == "TRAINER_SHOW" then
        if T.panel and T.panel:IsShown() then
            T.panel.activeTab = "spells"
            T.panel.lastScrolledBuild = nil
            T.Refresh()
        end
    else
        T.Refresh()
    end
end)
