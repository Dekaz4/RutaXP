local _, ns = ...

-- Recommendation overlay for Blizzard's class trainer window (ClassTrainerFrame).
-- Every learnable spell gets a coloured tag; a strip under the window says what
-- to buy first with the gold the player actually has.
local TR = {}
ns.TrainerAdvice = TR

local RANK = { must = 3, good = 2, save = 1 }
local ACCENTS = {
    ["á"] = "a", ["é"] = "e", ["í"] = "i", ["ó"] = "o", ["ú"] = "u", ["ü"] = "u", ["ñ"] = "n",
    ["Á"] = "a", ["É"] = "e", ["Í"] = "i", ["Ó"] = "o", ["Ú"] = "u", ["Ü"] = "u", ["Ñ"] = "n",
}
local STOP = { de = true, del = true, la = true, el = true, los = true, las = true, ["of"] = true, the = true }
local CATEGORIES = { available = true, unavailable = true, used = true }
local decoratedRows = setmetatable({}, { __mode = "k" })

local function safe(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, a, b, c, d = pcall(fn, ...)
    if ok then return a, b, c, d end
end

-- Lower-cases, strips colours, ranks "(Rango 1)", accents and filler words so
-- "Bendición del poderío (Rango 1)" and "Bendición de poderío" compare equal.
local function normalize(text)
    text = tostring(text or "")
    text = text:gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", "")
    text = text:gsub("%b()", " ")
    for accented, plain in pairs(ACCENTS) do text = text:gsub(accented, plain) end
    text = text:lower():gsub("[^%w%s]", " ")
    local words = {}
    for word in text:gmatch("%S+") do
        if not STOP[word] then words[#words + 1] = word end
    end
    return table.concat(words, " ")
end
TR.Normalize = normalize

local function splitSpells(text)
    text = tostring(text or "")
    local aliases = {}
    for alias in text:gmatch("%((.-)%)") do
        alias = normalize(alias):gsub("%s*rango%s+%d+", ""):gsub("%s*rank%s+%d+", "")
        if #alias >= 4 and alias ~= "mision" and alias ~= "talento" then aliases[#aliases + 1] = alias end
    end
    text = text:gsub("%b()", " ")
    text = text:gsub(" y ", ","):gsub("%+", ","):gsub("/", ","):gsub("%->", ",")
    local list = {}
    for piece in text:gmatch("[^,]+") do
        local token = normalize(piece)
        if #token >= 4 then list[#list + 1] = token end
    end
    for _, alias in ipairs(aliases) do list[#list + 1] = alias end
    return list
end

function TR.BuildIndex(classToken, build)
    local data = ns.Talents and ns.Talents.Registry and ns.Talents.Registry[classToken]
    local index = {}
    local function add(token, rank)
        local current = index[token]
        if not current or rank > current.rank then index[token] = { rank = rank } end
    end
    for _, spell in ipairs(data and data.trainerSpells or {}) do
        -- The class-wide list spans several roles. Only the chosen build's
        -- key abilities get the strongest recommendation.
        for _, token in ipairs(splitSpells(spell.name)) do add(token, math.min(2, RANK[spell.prio] or 1)) end
    end
    if build and build.data and build.data.class == classToken then
        for _, token in ipairs(splitSpells(build.skills)) do add(token, 3) end
    end
    return index
end

local function lookup(index, name)
    local n = normalize(name)
    if n == "" then return nil end
    if index[n] then return index[n] end
    if #n < 5 then return nil end
    local padded, best = " " .. n .. " ", nil
    for token, info in pairs(index) do
        if #token >= 5 then
            local other = " " .. token .. " "
            if padded:find(other, 1, true) or other:find(padded, 1, true) then
                if not best or info.rank > best.rank then best = info end
            end
        end
    end
    return best
end

function TR.Describe(info, service, level)
    if service and service.category == "used" then return nil end
    if service and service.category == "unavailable" then
        return "|cff9fb0c7Más adelante|r", 0.55, 0.62, 0.72
    end
    local rank = info and info.rank
    if rank == 3 then return "|cff7edd9c★ COMPRAR|r", 0.49, 0.87, 0.61 end
    if rank == 2 then return "|cff8ec5ffRecomendada|r", 0.56, 0.77, 1.0 end
    if rank == 1 then return "|cff9fb0c7Ahorra oro|r", 0.55, 0.62, 0.72 end
    return "|cff9fb0c7Opcional|r", 0.40, 0.45, 0.52
end

local function readServices()
    local services, byIndex, byName = {}, {}, {}
    local count = tonumber(safe(GetNumTrainerServices)) or 0
    for i = 1, count do
        -- Forever: name, serviceType, texture, requiredLevel, rank/subtext.
        local ok, name, category, _, requiredLevel, subText = pcall(GetTrainerServiceInfo, i)
        if ok and type(name) == "string" and name ~= "" and CATEGORIES[category] then
            local entry = {
                index = i, name = name, category = category, requiredLevel = requiredLevel, subText = subText,
                cost = tonumber(safe(GetTrainerServiceCost, i)) or 0,
            }
            services[#services + 1] = entry
            byIndex[i] = entry
            local key = normalize(name)
            -- A text-only fallback is safe only for an unambiguous name.
            byName[key] = byName[key] == nil and entry or false
        end
    end
    return services, byIndex, byName
end

local function eachRow(frame, callback)
    local box = frame.ScrollBox
    if box and box.ForEachFrame then
        box:ForEachFrame(callback)
        return
    end
    local scroll = frame.scrollFrame
    if scroll and scroll.buttons then
        for _, button in ipairs(scroll.buttons) do
            if button:IsShown() then callback(button) end
        end
    end
end

local function rowService(row, byIndex, byName)
    local element = safe(row.GetElementData, row)
    element = element and (element.data or element)
    local service = element and byIndex[element.skillIndex]
    if service then return service end
    local function fromRegions(owner)
        if not owner.GetRegions then return nil end
        for _, region in ipairs({ owner:GetRegions() }) do
            if region.GetObjectType and region:GetObjectType() == "FontString" then
                local service = byName[normalize(region:GetText())]
                if service then return service end
            end
        end
    end
    local found = fromRegions(row)
    if found then
        local id = safe(row.GetID, row)
        -- Legacy rows may have a service ID; never reinterpret display indexes
        -- when the text identifies another service.
        if not id or not byIndex[id] or byIndex[id] == found then return found end
        return nil
    end
    if row.GetChildren then
        for _, child in ipairs({ row:GetChildren() }) do
            found = fromRegions(child)
            if found then return found end
        end
    end
end

local function ensureBadge(row)
    decoratedRows[row] = true
    if row.RutaXPBadge then return row.RutaXPBadge, row.RutaXPStripe end
    local badge = row:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    badge:SetPoint("BOTTOMRIGHT", row, "BOTTOMRIGHT", -8, 7)
    badge:SetJustifyH("RIGHT")
    local stripe = row:CreateTexture(nil, "OVERLAY")
    stripe:SetPoint("TOPLEFT", row, "TOPLEFT", 1, -1)
    stripe:SetPoint("BOTTOMLEFT", row, "BOTTOMLEFT", 1, 1)
    stripe:SetWidth(3)
    row.RutaXPBadge, row.RutaXPStripe = badge, stripe
    return badge, stripe
end

local function clearRow(row)
    if row.RutaXPBadge then row.RutaXPBadge:SetText(""); row.RutaXPBadge:Hide() end
    if row.RutaXPStripe then row.RutaXPStripe:Hide() end
end

function TR.Clear()
    for row in pairs(decoratedRows) do clearRow(row) end
    if TR.banner then TR.banner:Hide() end
end

local function ensureBanner(frame)
    if TR.banner then return TR.banner end
    local banner = CreateFrame("Frame", nil, UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    banner:SetPoint("TOPLEFT", frame, "BOTTOMLEFT", 0, -2)
    banner:SetPoint("TOPRIGHT", frame, "BOTTOMRIGHT", 0, -2)
    banner:SetHeight(48)
    if frame.GetFrameStrata then banner:SetFrameStrata(frame:GetFrameStrata()) end
    banner:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
    banner:SetBackdropColor(0.04, 0.06, 0.10, 0.96)
    banner:SetBackdropBorderColor(0.82, 0.66, 0.25, 0.9)
    banner.text = banner:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    banner.text:SetPoint("TOPLEFT", 8, -6)
    banner.text:SetPoint("TOPRIGHT", -8, -6)
    banner.text:SetJustifyH("LEFT")
    banner.text:SetJustifyV("TOP")
    banner.text:SetWordWrap(true)
    TR.banner = banner
    return banner
end

local function money(copper)
    copper = math.floor(tonumber(copper) or 0)
    local gold, silver, rest = math.floor(copper / 10000), math.floor(copper / 100) % 100, copper % 100
    local parts = {}
    if gold > 0 then parts[#parts + 1] = gold .. "o" end
    if silver > 0 then parts[#parts + 1] = silver .. "p" end
    if rest > 0 or #parts == 0 then parts[#parts + 1] = rest .. "c" end
    return table.concat(parts, " ")
end

local function currentContext()
    local now = type(GetTime) == "function" and GetTime() or 0
    local _, classToken = safe(UnitClass, "player")
    local choice = ns.Talents and ns.Talents.GetChoice and ns.Talents.GetChoice(classToken)
    local cache = TR.cache
    if cache and cache.classToken == classToken and cache.choice == choice and now - cache.time < 2 then return cache end
    local build
    if ns.Talents and ns.Talents.Evaluate then
        local evaluated = safe(ns.Talents.Evaluate, classToken)
        if evaluated and evaluated.data and evaluated.data.class == classToken then build = evaluated.build end
    end
    TR.cache = {
        time = now, classToken = classToken, choice = choice, build = build,
        index = TR.BuildIndex(classToken, build),
        level = tonumber(safe(UnitLevel, "player")) or 1,
    }
    return TR.cache
end

function TR.Refresh(frame)
    frame = frame or _G.ClassTrainerFrame
    if not frame or not frame:IsShown() then
        TR.Clear()
        return
    end
    -- Pet costs are training points, not copper. Unknown trainer types also
    -- receive no spending advice; the rest of the addon remains available.
    -- Forever calls class/weapon/riding trainers "General" (there is no
    -- TrainerType.Class). Confirm class services below before decorating.
    local generalType = Enum and Enum.TrainerType and Enum.TrainerType.General
    if generalType == nil or safe(C_Trainer and C_Trainer.GetTrainerType) ~= generalType or safe(IsTradeskillTrainer) then
        TR.Clear()
        return
    end
    local context = currentContext()
    if not (context.classToken and ns.Talents and ns.Talents.Registry[context.classToken]) then TR.Clear(); return end

    local services, byIndex, byName = readServices()
    local hasClassService = false
    for _, service in ipairs(services) do
        if lookup(context.index, service.name) then hasClassService = true; break end
    end
    if not hasClassService then TR.Clear(); return end
    local funds = tonumber(safe(GetMoney)) or 0

    eachRow(frame, function(row)
        local service = rowService(row, byIndex, byName)
        local badge, stripe = ensureBadge(row)
        if not service then
            clearRow(row)
            return
        end
        local text, r, g, b = TR.Describe(lookup(context.index, service.name), service, context.level)
        if text then
            badge:SetText(text)
            badge:Show()
            stripe:SetColorTexture(r, g, b, 0.95)
            stripe:Show()
        else
            clearRow(row)
        end
    end)

    -- Summary: what to buy now with the gold available, best first.
    local wanted = {}
    for _, service in ipairs(services) do
        if service.category == "available" then
            local info = lookup(context.index, service.name)
            local rank = info and info.rank or 0
            if rank >= 2 then wanted[#wanted + 1] = { service = service, rank = rank } end
        end
    end
    table.sort(wanted, function(a, b)
        if a.rank ~= b.rank then return a.rank > b.rank end
        return a.service.index < b.service.index
    end)
    local buy, missing, left = {}, {}, funds
    for _, item in ipairs(wanted) do
        if item.service.cost <= left then
            left = left - item.service.cost
            buy[#buy + 1] = item.service.name .. (item.service.subText and item.service.subText ~= "" and " (" .. item.service.subText .. ")" or "")
        else
            missing[#missing + 1] = item.service.name
        end
    end

    local banner = ensureBanner(frame)
    local lines = { "|cffffd966RutaXP|r · tienes |cffffffff" .. money(funds) .. "|r" }
    if #buy > 0 then
        lines[#lines + 1] = "|cff7edd9cCompra ahora:|r " .. table.concat(buy, ", ")
    elseif #wanted == 0 then
        lines[#lines + 1] = "|cff9fb0c7Nada urgente: lo disponible es opcional.|r"
    end
    if #missing > 0 then
        lines[#lines + 1] = "|cffffb468Te falta oro para:|r " .. table.concat(missing, ", ")
    end
    banner.text:SetText(table.concat(lines, "\n"))
    banner:SetHeight(math.max(34, (banner.text:GetStringHeight() or 14) + 14))
    banner:Show()
end

local driver = CreateFrame("Frame")
local elapsedTotal = 0
driver:SetScript("OnUpdate", function(_, elapsed)
    elapsedTotal = elapsedTotal + elapsed
    if elapsedTotal < 0.25 then return end
    elapsedTotal = 0
    local frame = _G.ClassTrainerFrame
    if frame and frame:IsShown() then
        pcall(TR.Refresh, frame)
    else
        TR.Clear()
    end
end)
