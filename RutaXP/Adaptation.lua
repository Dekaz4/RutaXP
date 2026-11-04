local _, ns = ...

-- Explain choices, never alter quest requirements or switch a route by itself.
local Adaptation = {}
ns.Adaptation = Adaptation

local function safe(fn, ...)
    if type(fn) ~= "function" then return nil end
    local ok, a, b = pcall(fn, ...)
    if ok then return a, b end
end
local function number(v)
    if issecretvalue and issecretvalue(v) then return nil end
    if type(v) == "number" and v == v and math.abs(v) < math.huge then return v end
end
local function token(value)
    local normalized = tostring(value or ""):lower():gsub("[%s_%-]", "")
    return normalized == "scourge" and "undead" or normalized
end
local function matches(list, value)
    if type(list) ~= "table" then return list == nil or token(list) == token(value) end
    local positive, hit = false, false
    for _, item in ipairs(list) do
        local excluded = tostring(item):sub(1, 1) == "!"
        local key = token(excluded and item:sub(2) or item)
        if excluded and key == token(value) then return false end
        if not excluded then positive = true; if key == token(value) then hit = true end end
    end
    return not positive or hit
end
local function player()
    local _, race = safe(UnitRace, "player")
    local _, class = safe(UnitClass, "player")
    return { level=number(safe(UnitLevel, "player")) or 1, race=race, class=class,
        faction=safe(UnitFactionGroup, "player"), map=safe(C_Map and C_Map.GetBestMapForUnit, "player") }
end
local function only(conditions, who)
    conditions = type(conditions) == "table" and conditions or {}
    return matches(conditions.races, who.race) and matches(conditions.classes, who.class) and matches(conditions.factions, who.faction)
end
local function duoContext()
    local data = ns.Duo and safe(ns.Duo.GetContext, ns.Duo)
    return type(data) == "table" and data or {}
end
local function duoReal(duo)
    -- A manually entered partner level is not proof of a live two-player group.
    return duo.enabled == true and duo.known == true and duo.online == true and duo.sameParty == true
end
local function guideAllowed(guide, who, level)
    return (not guide.faction or guide.faction == who.faction)
        and matches(guide.classes, who.class) and matches(guide.races, who.race)
        and level >= (guide.minLevel or 1) and level <= (guide.maxLevel or 60) + 2
end

local function questStats(guide, who, cache)
    local seen, active, total, done = {}, 0, 0, 0
    for _, step in ipairs(guide.steps or {}) do
        if only(step.only, who) then
            for _, goal in ipairs(step.goals or {}) do
                local id = goal.quest or goal.questID
                if id and not seen[id] and not goal.optional and only(goal.only, who) then
                    seen[id], total = true, total + 1
                    if not cache[id] then
                        cache[id] = {
                            active=safe(C_QuestLog and C_QuestLog.IsOnQuest, id) == true,
                            done=(ns.turnedIn and ns.turnedIn[id]) == true or safe(C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted, id) == true or safe(IsQuestFlaggedCompleted, id) == true,
                        }
                    end
                    if cache[id].done then done = done + 1 elseif cache[id].active then active = active + 1 end
                end
            end
        end
    end
    return active, total, done
end

function Adaptation:Invalidate() self.cachedAt = nil end

function Adaptation:GetSuggestions()
    if not ns.char then return {} end
    local who, duo = player(), duoContext()
    local real = duoReal(duo)
    local level = who.level
    if real and number(duo.partnerLevel) and duo.partnerLevel > 0 then level = math.min(level, duo.partnerLevel) end
    local current = ns.guides and ns.guides[ns.char.activeGuide]
    local state = current and ns.char.progress and ns.char.progress[current.id]
    local now = number(safe(GetTime)) or 0
    local key = table.concat({ tostring(who.level), token(who.race), token(who.class), tostring(who.faction), tostring(who.map),
        current and current.id or "", tostring(state and state.cursor or 1), tostring(duo.enabled), tostring(real),
        tostring(duo.partnerLevel), token(duo.partnerRace), token(duo.partnerClass), tostring(duo.partnerFaction) }, "|")
    if self.cachedAt and self.cacheKey == key and now - self.cachedAt >= 0 and now - self.cachedAt < 5 then return self.suggestions end
    local results = {}
    local function append(title, text, guideID, reason)
        if #results < 5 then results[#results + 1] = { title=title, text=text, guideID=guideID, reason=reason or text } end
    end
    if duo.enabled and not real then
        append("Compañero sin confirmar", "Faltan datos de un compañero conectado en el mismo grupo. Las recomendaciones de nivel siguen siendo individuales; no se da por hecho que podáis hacer contenido de grupo.", nil, "No hay un dúo real confirmado.")
    elseif real then
        if duo.partnerFaction and duo.partnerFaction ~= who.faction then
            append("Comprobad la facción", "El compañero indica otra facción. No se presuponen misiones ni puntos de encuentro compartidos.", nil, "Las facciones registradas son distintas.")
        end
        if level < who.level then
            append("El menor nivel marca el ritmo", "Planificad para el nivel " .. level .. ". No se eliminan los requisitos individuales ni las misiones de clase del personaje con más nivel.", nil, "El compañero conectado tiene menos nivel.")
        end
        if duo.partnerRace and token(duo.partnerRace) ~= token(who.race) and math.min(who.level, number(duo.partnerLevel) or who.level) <= 15 then
            append("Inicios distintos: acordad un encuentro", "Podéis tener misiones iniciales y de clase distintas. Terminad los requisitos de cada raza y elegid después un centro al que ambos tengáis acceso; no se inventa un viaje o una cadena común.", nil, "Las razas iniciales son distintas.")
        end
    end

    local step = current and current.steps and current.steps[state and state.cursor or 1]
    local hasClass, hasGroup = false, nil
    if step and only(step.only, who) then
        for _, goal in ipairs(step.goals or {}) do
            if only(goal.only, who) then
                if goal.only and goal.only.classes then hasClass = true end
                if goal.class and token(goal.class) == token(who.class) then hasClass = true end
                if goal.group then hasGroup = goal.group end
            end
        end
    end
    if hasClass or (current and current.category == "Class") then
        append("Conserva las misiones de tu clase", "Este paso contiene requisitos de clase aplicables a tu personaje. El compañero puede necesitar otra cadena; esta recomendación no los omite ni los marca como hechos.", nil, "Hay objetivos específicos de " .. tostring(who.class or "tu clase") .. ".")
    end
    if hasGroup then
        local advised = type(hasGroup) == "table" and tonumber(hasGroup.size) or nil
        if real then
            append("Revisad el objetivo de grupo", "Hay un dúo conectado, pero dos jugadores no garantizan superar un élite, mazmorra o requisito de grupo" .. (advised and (" de " .. advised .. " jugadores") or "") .. ". Revisad nivel, equipo y descripción; el requisito sigue intacto.", nil, "El paso está marcado como contenido de grupo.")
        else
            append("Este paso requiere revisar el grupo", "No hay un dúo conectado confirmado. Busca el grupo que pida el objetivo o déjalo pendiente; no se cambia su dificultad ni su estado.", nil, "El paso está marcado como contenido de grupo.")
        end
    end

    local best, score, bestActive, cache = nil, -math.huge, 0, {}
    for _, id in ipairs(ns.order or {}) do
        local guide = ns.guides[id]
        if guide and guideAllowed(guide, who, level) then
            local active, total, done = questStats(guide, who, cache)
            if total == 0 or done < total then
                local rating = active * 50 + (guide.zone == who.map and 100 or 0) + (guide.races and 15 or 0) - math.abs(level - (guide.minLevel or 1))
                if current and current.id == id then rating = rating + 5 end
                if rating > score then best, score, bestActive = guide, rating, active end
            end
        end
    end
    if best and (not current or best.id ~= current.id) then
        append("Ruta adecuada: " .. best.title,
            "Encaja con el nivel " .. level .. ", tu facción y tus requisitos de raza/clase" .. (bestActive > 0 and ("; incluye " .. bestActive .. " misiones de tu registro") or "") .. ". Cambiarla requiere pulsar esta sugerencia; conserva tu progreso anterior.",
            best.id, "Coinciden nivel y requisitos" .. (best.zone == who.map and ", y estás en su zona." or "."))
    elseif current and (level < (current.minLevel or 1) or level > (current.maxLevel or 60) + 2) then
        append("Revisa el rango de la ruta", "La guía seleccionada cubre aproximadamente " .. tostring(current.minLevel or 1) .. "–" .. tostring(current.maxLevel or 60) .. "; el nivel de referencia es " .. level .. ". Revisa misiones pendientes y requisitos antes de trasladarte.", nil, "El nivel está fuera del rango orientativo.")
    elseif #results == 0 then
        append("Continúa con tu registro", "La ruta actual encaja con tu nivel. Revisa objetivos y requisitos del cliente; no hay datos suficientes para proponer un cambio mejor.", nil, "Sin una alternativa claramente mejor según zona y misiones activas.")
    end
    self.suggestions, self.cachedAt, self.cacheKey = results, now, key
    return results
end

function Adaptation:ApplySuggestion(index)
    local suggestion = (self.suggestions or self:GetSuggestions())[tonumber(index) or 0]
    if not suggestion or not suggestion.guideID then return false, "Esta sugerencia es informativa." end
    local guide = ns.guides and ns.guides[suggestion.guideID]
    local who, duo = player(), duoContext()
    local level = who.level
    if duoReal(duo) and number(duo.partnerLevel) and duo.partnerLevel > 0 then level = math.min(level, duo.partnerLevel) end
    if not guide or not guideAllowed(guide, who, level) then return false, "La recomendación ya no coincide con el personaje o el dúo." end
    if not ns.char then return false, "El personaje aún no está cargado." end
    ns.char.adaptation = type(ns.char.adaptation) == "table" and ns.char.adaptation or {}
    local saved = ns.char.adaptation
    saved.bookmarks = type(saved.bookmarks) == "table" and saved.bookmarks or {}
    local previous = ns.char.activeGuide
    local state = previous and ns.char.progress and ns.char.progress[previous]
    saved.bookmarks[#saved.bookmarks + 1] = { guideID=previous, cursor=state and state.cursor or 1, review=state and state.review or nil }
    while #saved.bookmarks > 10 do table.remove(saved.bookmarks, 1) end
    -- Do not call SelectGuide/Sync/GetCurrent: those can place/clamp cursors.
    ns.char.activeGuide = guide.id
    saved.lastChoice = guide.id
    self:Invalidate()
    return true, guide.id
end

function Adaptation:ReturnToPrevious()
    local saved = ns.char and ns.char.adaptation
    local bookmarks = type(saved) == "table" and saved.bookmarks
    if type(bookmarks) ~= "table" then return false, "No hay una ruta anterior guardada." end
    while #bookmarks > 0 do
        local entry = table.remove(bookmarks)
        local id = type(entry) == "table" and entry.guideID
        if id and ns.guides and ns.guides[id] then
            ns.char.activeGuide = id
            saved.lastChoice = id
            self:Invalidate()
            return true, id
        end
    end
    return false, "La ruta anterior ya no está disponible."
end
