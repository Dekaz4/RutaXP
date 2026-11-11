local _, ns = ...

-- Itineraries guide movement only. They never accept/complete/deliver a quest,
-- write quest confirmations, or move the character. Unknown floors and rides
-- require the player's explicit confirmation rather than guessed arrival.

-- Catalog facts adapted from Polestar / SendaFH, GPL-3.0-only; exact snapshot
-- and every source location are retained in Source/waypoints.json below.
local Catalog = { ["schema"] = 1, ["source"] = "Polestar / SendaFH", ["license"] = "GPL-3.0-only (con avisos de terceros existentes)", ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["description"] = "Entradas y extremos de pasos documentados; no es un navegador por carreteras. No se inventan altitudes ni rutas interiores.", ["routes"] = { { ["id"] = "den", ["title"] = "Entrada de El Cubil", ["kind"] = "cave", ["match"] = { ["map"] = 1411, ["quests"] = { 788, 97279, 3090 }, ["actions"] = { "accept", "turnin" } }, ["activationRadius"] = 1800, ["points"] = { { ["map"] = 1411, ["x"] = 42.4, ["y"] = 68.6, ["f"] = "e", ["label"] = "Entrada de El Cubil", ["radius"] = 12, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "guides/forever/horde/orc-troll/01-durotar.guide", ["line"] = 115, ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/guides/forever/horde/orc-troll/01-durotar.guide#L115", ["verification"] = "Coordenadas explícitas y explicación de la entrada en la guía fuente; altitud no disponible. Confirmación manual al llegar." } }, { ["id"] = "burning-blade", ["title"] = "Entrada del Aquelarre del Filo Ardiente", ["kind"] = "cave", ["match"] = { ["map"] = 1411, ["quests"] = { 6394, 794 }, ["actions"] = { "collect", "complete" } }, ["activationRadius"] = 1800, ["points"] = { { ["map"] = 1411, ["x"] = 45, ["y"] = 56, ["f"] = "e", ["label"] = "Entrada del Aquelarre del Filo Ardiente", ["radius"] = 12, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "guides/forever/horde/orc-troll/01-durotar.guide", ["line"] = 192, ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/guides/forever/horde/orc-troll/01-durotar.guide#L192", ["verification"] = "Coordenadas explícitas y explicación de la entrada en la guía fuente; altitud no disponible. Confirmación manual al llegar." } }, { ["id"] = "skull-rock", ["title"] = "Entrada de Roca del Cráneo", ["kind"] = "cave", ["match"] = { ["map"] = 1411, ["quests"] = { 827 }, ["actions"] = { "collect", "complete" } }, ["activationRadius"] = 1800, ["points"] = { { ["map"] = 1411, ["x"] = 55, ["y"] = 10, ["f"] = "e", ["label"] = "Entrada de Roca del Cráneo", ["radius"] = 12, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "guides/forever/horde/orc-troll/01-durotar.guide", ["line"] = 464, ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/guides/forever/horde/orc-troll/01-durotar.guide#L464", ["verification"] = "Coordenadas explícitas y explicación de la entrada en la guía fuente; altitud no disponible. Confirmación manual al llegar." } }, { ["id"] = "fargodeep", ["title"] = "Entrada de la Mina Abisal", ["kind"] = "cave", ["match"] = { ["map"] = 1429, ["quests"] = { 62, 47, 60, 87, 91775 }, ["actions"] = { "complete", "collect" } }, ["activationRadius"] = 1800, ["points"] = { { ["map"] = 1429, ["x"] = 39.5, ["y"] = 82.4, ["f"] = "e", ["label"] = "Entrada de la Mina Abisal", ["radius"] = 12, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "guides/forever/alliance/human/01-elwynn-forest.guide", ["line"] = 325, ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/guides/forever/alliance/human/01-elwynn-forest.guide#L325", ["verification"] = "Coordenadas explícitas y explicación de la entrada en la guía fuente; altitud no disponible. Confirmación manual al llegar." } }, { ["id"] = "jasperlode", ["title"] = "Entrada de la Cantera de Jaspe", ["kind"] = "cave", ["match"] = { ["map"] = 1429, ["quests"] = { 76, 91723, 91732 }, ["actions"] = { "complete", "kill", "collect" } }, ["activationRadius"] = 1800, ["points"] = { { ["map"] = 1429, ["x"] = 61.6, ["y"] = 54.1, ["f"] = "e", ["label"] = "Entrada de la Cantera de Jaspe", ["radius"] = 12, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "guides/forever/alliance/human/01-elwynn-forest.guide", ["line"] = 407, ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/guides/forever/alliance/human/01-elwynn-forest.guide#L407", ["verification"] = "Coordenadas explícitas y explicación de la entrada en la guía fuente; altitud no disponible. Confirmación manual al llegar." } }, { ["id"] = "coldridge", ["title"] = "Entrada de la cueva de los trols", ["kind"] = "cave", ["match"] = { ["map"] = 1426, ["quests"] = { 218 }, ["npcs"] = { 808 }, ["actions"] = { "collect", "complete", "kill", "objective" } }, ["activationRadius"] = 1800, ["points"] = { { ["map"] = 1426, ["x"] = 26.93, ["y"] = 80.03, ["label"] = "Entrada de la cueva de los trols", ["radius"] = 12, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "guides/forever/alliance/dwarf-gnome/01-dun-morogh.guide", ["line"] = 222, ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/guides/forever/alliance/dwarf-gnome/01-dun-morogh.guide#L222", ["objective"] = { ["questID"] = 218, ["itemID"] = 2004, ["npcID"] = 808, ["questSourceLine"] = 226, ["npcReferenceLine"] = 215, ["npcNameFile"] = "addon/SendaFH_Names_esES/Names.lua", ["npcNameLine"] = 4712, ["npcNameUrl"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/addon/SendaFH_Names_esES/Names.lua#L4712", ["actionAliases"] = "Recoger el diario, completar su objetivo o derrotar a Grik'nir llevan a la misma cueva; aceptar y entregar permanecen fuera." }, ["verification"] = "Coordenadas explícitas y explicación de la entrada en la guía fuente; altitud no disponible. Confirmación manual al llegar." } }, { ["id"] = "blackfathom", ["title"] = "Entrada de las ruinas de Cavernas de Brazanegra", ["kind"] = "cave", ["match"] = { ["map"] = 1440, ["quests"] = { 6563 }, ["actions"] = { "collect" } }, ["activationRadius"] = 1800, ["points"] = { { ["map"] = 1440, ["x"] = 14.5, ["y"] = 14.2, ["f"] = "e", ["label"] = "Entrada de las ruinas de Cavernas de Brazanegra", ["radius"] = 12, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "guides/forever/horde/07-ashenvale.guide", ["line"] = 130, ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/guides/forever/horde/07-ashenvale.guide#L130", ["verification"] = "Coordenadas explícitas y explicación de la entrada en la guía fuente; altitud no disponible. Confirmación manual al llegar." } }, { ["id"] = "durotar-barrens", ["title"] = "Paso entre Durotar y Los Baldíos", ["kind"] = "crossing", ["match"] = { ["fromMap"] = 1411, ["toMap"] = 1413 }, ["activationRadius"] = 3000, ["points"] = { { ["map"] = 1411, ["x"] = 37.2, ["y"] = 43, ["f"] = "e", ["label"] = "Acceso al paso del río Furia", ["radius"] = 18, ["mode"] = "confirm" }, { ["map"] = 1413, ["x"] = 60.8, ["y"] = 19.8, ["f"] = "e", ["label"] = "Salida del paso del río Furia", ["radius"] = 18, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "tools/lib/travel/crossings.json", ["key"] = "carbonite-durotar--the-barrens", ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/tools/lib/travel/crossings.json", ["upstream"] = "Carbonite-Classic 4d062800ae0c77c3f52ecf436b175bf06dcced4a; Carbonite/Data/classic/ZoneConnections.lua; GPL-3.0", ["verification"] = "Dos extremos exactos del paso del catálogo fuente. No incluye geometría del puente ni altitudes; requiere confirmar cada extremo." } }, { ["id"] = "barrens-durotar", ["title"] = "Paso entre Durotar y Los Baldíos", ["kind"] = "crossing", ["match"] = { ["fromMap"] = 1413, ["toMap"] = 1411 }, ["activationRadius"] = 3000, ["points"] = { { ["map"] = 1413, ["x"] = 60.8, ["y"] = 19.8, ["f"] = "e", ["label"] = "Acceso al paso del río Furia", ["radius"] = 18, ["mode"] = "confirm" }, { ["map"] = 1411, ["x"] = 37.2, ["y"] = 43, ["f"] = "e", ["label"] = "Salida del paso del río Furia", ["radius"] = 18, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "tools/lib/travel/crossings.json", ["key"] = "carbonite-durotar--the-barrens", ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/tools/lib/travel/crossings.json", ["upstream"] = "Carbonite-Classic 4d062800ae0c77c3f52ecf436b175bf06dcced4a; Carbonite/Data/classic/ZoneConnections.lua; GPL-3.0", ["verification"] = "Dos extremos exactos del paso del catálogo fuente. No incluye geometría del puente ni altitudes; requiere confirmar cada extremo." } }, { ["id"] = "boat-bootybay-ratchet-out", ["title"] = "Barco entre Bahía del Botín y Trinquete", ["kind"] = "transport", ["match"] = { ["fromMap"] = 1434, ["toMap"] = 1413 }, ["activationRadius"] = 6000, ["points"] = { { ["map"] = 1434, ["x"] = 26.35, ["y"] = 73.56, ["f"] = "e", ["label"] = "Embarque: Bahía del Botín", ["radius"] = 20, ["mode"] = "transport" }, { ["map"] = 1413, ["x"] = 63.35, ["y"] = 38.45, ["f"] = "e", ["label"] = "Desembarque: Trinquete", ["radius"] = 20, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "addon/SendaFH/Nav/TravelData.lua", ["line"] = 353, ["key"] = "boat-bootybay-ratchet", ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/addon/SendaFH/Nav/TravelData.lua#L353", ["upstream"] = "TravelData: puntos del cliente Forever 1.60.1.70425 y SendaFH; avisos de terceros en la fuente y en Licenses/SendaFH-THIRD_PARTY.md.", ["verification"] = "Extremos exactos del transporte publicado en la fuente. No hay altitud comprobada: el embarque y el desembarque requieren confirmación manual; llegar al muelle no prueba un viaje." } }, { ["id"] = "boat-bootybay-ratchet-return", ["title"] = "Barco entre Bahía del Botín y Trinquete", ["kind"] = "transport", ["match"] = { ["fromMap"] = 1413, ["toMap"] = 1434 }, ["activationRadius"] = 6000, ["points"] = { { ["map"] = 1413, ["x"] = 63.35, ["y"] = 38.45, ["f"] = "e", ["label"] = "Embarque: Trinquete", ["radius"] = 20, ["mode"] = "transport" }, { ["map"] = 1434, ["x"] = 26.35, ["y"] = 73.56, ["f"] = "e", ["label"] = "Desembarque: Bahía del Botín", ["radius"] = 20, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "addon/SendaFH/Nav/TravelData.lua", ["line"] = 353, ["key"] = "boat-bootybay-ratchet", ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/addon/SendaFH/Nav/TravelData.lua#L353", ["upstream"] = "TravelData: puntos del cliente Forever 1.60.1.70425 y SendaFH; avisos de terceros en la fuente y en Licenses/SendaFH-THIRD_PARTY.md.", ["verification"] = "Extremos exactos del transporte publicado en la fuente. No hay altitud comprobada: el embarque y el desembarque requieren confirmación manual; llegar al muelle no prueba un viaje." } }, { ["id"] = "zeppelin-orgrimmar-undercity-out", ["title"] = "Zepelín entre Orgrimmar y Entrañas", ["kind"] = "transport", ["match"] = { ["fromMap"] = 1411, ["toMap"] = 1420, ["factions"] = { "Horde" } }, ["activationRadius"] = 6000, ["points"] = { { ["map"] = 1411, ["x"] = 50.82, ["y"] = 13.54, ["f"] = "e", ["label"] = "Embarque: Orgrimmar", ["radius"] = 20, ["mode"] = "transport" }, { ["map"] = 1420, ["x"] = 60.74, ["y"] = 58.87, ["f"] = "e", ["label"] = "Desembarque: Entrañas", ["radius"] = 20, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "addon/SendaFH/Nav/TravelData.lua", ["line"] = 362, ["key"] = "zeppelin-orgrimmar-undercity", ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/addon/SendaFH/Nav/TravelData.lua#L362", ["upstream"] = "TravelData: puntos del cliente Forever 1.60.1.70425 y SendaFH; avisos de terceros en la fuente y en Licenses/SendaFH-THIRD_PARTY.md.", ["verification"] = "Extremos exactos del transporte publicado en la fuente. No hay altitud comprobada: el embarque y el desembarque requieren confirmación manual; llegar al muelle no prueba un viaje." } }, { ["id"] = "zeppelin-orgrimmar-undercity-return", ["title"] = "Zepelín entre Orgrimmar y Entrañas", ["kind"] = "transport", ["match"] = { ["fromMap"] = 1420, ["toMap"] = 1411, ["factions"] = { "Horde" } }, ["activationRadius"] = 6000, ["points"] = { { ["map"] = 1420, ["x"] = 60.74, ["y"] = 58.87, ["f"] = "e", ["label"] = "Embarque: Entrañas", ["radius"] = 20, ["mode"] = "transport" }, { ["map"] = 1411, ["x"] = 50.82, ["y"] = 13.54, ["f"] = "e", ["label"] = "Desembarque: Orgrimmar", ["radius"] = 20, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "addon/SendaFH/Nav/TravelData.lua", ["line"] = 362, ["key"] = "zeppelin-orgrimmar-undercity", ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/addon/SendaFH/Nav/TravelData.lua#L362", ["upstream"] = "TravelData: puntos del cliente Forever 1.60.1.70425 y SendaFH; avisos de terceros en la fuente y en Licenses/SendaFH-THIRD_PARTY.md.", ["verification"] = "Extremos exactos del transporte publicado en la fuente. No hay altitud comprobada: el embarque y el desembarque requieren confirmación manual; llegar al muelle no prueba un viaje." } }, { ["id"] = "portal-ruttheran", ["title"] = "Portal entre Darnassus y Rut'theran", ["kind"] = "portal", ["match"] = { ["fromMap"] = 1457, ["toMap"] = 1438, ["factions"] = { "Alliance" } }, ["activationRadius"] = 1800, ["points"] = { { ["map"] = 1457, ["x"] = 29.13, ["y"] = 41.21, ["f"] = "e", ["label"] = "Entrada del portal en Darnassus", ["radius"] = 12, ["mode"] = "confirm" }, { ["map"] = 1438, ["x"] = 55.93, ["y"] = 89.74, ["f"] = "e", ["label"] = "Salida del portal en Aldea Rut'theran", ["radius"] = 12, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "addon/SendaFH/Nav/TravelData.lua", ["line"] = 369, ["key"] = "portal-ruttheran", ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/addon/SendaFH/Nav/TravelData.lua#L369", ["upstream"] = "TravelData: puntos del cliente Forever 1.60.1.70425 y SendaFH; avisos de terceros en la fuente y en Licenses/SendaFH-THIRD_PARTY.md.", ["verification"] = "Extremos exactos del portal publicados en la fuente. Cada extremo se confirma manualmente; entrar en el radio no prueba haber atravesado el portal." } }, { ["id"] = "portal-darnassus", ["title"] = "Portal entre Darnassus y Rut'theran", ["kind"] = "portal", ["match"] = { ["fromMap"] = 1438, ["toMap"] = 1457, ["factions"] = { "Alliance" } }, ["activationRadius"] = 1800, ["points"] = { { ["map"] = 1438, ["x"] = 55.87, ["y"] = 89.34, ["f"] = "e", ["label"] = "Entrada del portal en Aldea Rut'theran", ["radius"] = 12, ["mode"] = "confirm" }, { ["map"] = 1457, ["x"] = 30.75, ["y"] = 41.39, ["f"] = "e", ["label"] = "Salida del portal en Darnassus", ["radius"] = 12, ["mode"] = "confirm" } }, ["provenance"] = { ["commit"] = "5d207e28e82e2c529143b21ace74fe88692f0067", ["file"] = "addon/SendaFH/Nav/TravelData.lua", ["line"] = 370, ["key"] = "portal-darnassus", ["url"] = "https://github.com/julen92/SendaFH/blob/5d207e28e82e2c529143b21ace74fe88692f0067/addon/SendaFH/Nav/TravelData.lua#L370", ["upstream"] = "TravelData: puntos del cliente Forever 1.60.1.70425 y SendaFH; avisos de terceros en la fuente y en Licenses/SendaFH-THIRD_PARTY.md.", ["verification"] = "Extremos exactos del portal publicados en la fuente. Cada extremo se confirma manualmente; entrar en el radio no prueba haber atravesado el portal." } } } }

local W = { catalog = Catalog, routes = Catalog.routes,
    limits = { entries = 256, ownRoutes = 32, pointsPerRoute = 64, ownPoints = 512 } }
ns.Waypoints = W

local function readable(v)
    if issecretvalue and issecretvalue(v) then return nil end
    return v
end

local function call(api, ...)
    if type(api) ~= "function" then return nil end
    local ok, a, b, c, d = pcall(api, ...)
    if ok then return readable(a), readable(b), readable(c), readable(d) end
end

local function finite(v)
    return type(v) == "number" and readable(v) ~= nil and v == v and math.abs(v) < math.huge
end

local function contains(values, wanted)
    if not values then return true end
    for _, value in ipairs(values) do if value == wanted then return true end end
    return false
end

local function count(values)
    local total = 0
    for _ in pairs(values or {}) do total = total + 1 end
    return total
end

local function entryRoom(state, key)
    if state.entries[key] or count(state.entries) < W.limits.entries then return true end
    state.limitReason = "Historial de puntos lleno; el objetivo continúa sin itinerario nuevo"
    return false, state.limitReason
end

local function db()
    if not ns.char then return nil end
    local value = ns.char.waypoints
    if type(value) ~= "table" then value = {}; ns.char.waypoints = value end
    if value.enabled == nil then value.enabled = true end
    if type(value.entries) ~= "table" then value.entries = {} end
    if type(value.ownRoutes) ~= "table" then value.ownRoutes = {} end
    value.schema = 1
    return value
end

function W:_Context(step, goal)
    if not ns.char or not ns.GetCurrent then return nil end
    local guide, current, progress = ns:GetCurrent()
    if not guide or not current or not progress then return nil end
    local active, index
    if ns.GetActiveGoal then active, index = ns:GetActiveGoal(current, progress)
    else active, index = current, 1 end
    if not active then return nil end
    if step and step ~= current and step ~= active then return nil end
    if goal and goal ~= active then return nil end
    local action = active.t or active.action or "manual"
    local id = active.quest or active.questID or active.item or active.npc or ""
    return { guide = guide, step = current, goal = active, progress = progress, index = index or 1,
        key = guide.id .. ":" .. tostring(progress.cursor) .. ":" .. tostring(index or 1)
            .. ":" .. action .. ":" .. tostring(id) }
end

-- An override may belong to a companion or a recovery target. Its immutable
-- goal identity is enough; never consult or write the player's quest cursor.
function W:_TargetContext(input)
    if type(input) ~= "table" then return nil end
    local base = input.base
    local goal = input.goal or (base and base.goal)
    if not goal and base then goal = { t = "goto", map = base.mapID, waypoint = base } end
    if type(goal) ~= "table" then return nil end
    local source = type(input.source) == "string" and input.source or (base and base.source) or "external"
    local guide = input.guide or (input.guideID and ns.guides and ns.guides[input.guideID])
    local guideID = guide and guide.id or input.guideID or "external"
    local cursor = finite(input.stepIndex) and math.max(1, math.floor(input.stepIndex)) or 1
    local index = finite(input.goalIndex) and math.max(1, math.floor(input.goalIndex)) or 1
    local step = input.step or (guide and guide.steps and guide.steps[cursor]) or { goals = { goal } }
    guide = guide or { id = guideID, steps = {} }
    local identity = type(input.key) == "string" and input.key or table.concat({ source, guideID, cursor, index,
        tostring(goal.t or goal.action or "goto"), tostring(goal.quest or goal.questID or goal.npc or goal.item or ""),
        tostring(base and base.mapID or goal.map), tostring(base and base.x or goal.x), tostring(base and base.y or goal.y) }, ":")
    return { guide = guide, step = step, goal = goal, progress = { cursor = cursor, review = input.review == true },
        index = index, key = "external:" .. identity:sub(1, 240), external = true, source = source, base = base }
end

local function isAccess(route)
    return route.accessID ~= nil or route.kind == "cave" or route.kind == "building" or route.kind == "approach"
end
local function entryKey(context, route)
    return isAccess(route) and ("access:" .. tostring(route.accessID or route.id)) or (context.key .. ":" .. route.id)
end

function W:_ControlContext()
    if self.navigationOwner == ns.char and self.navigationContext and self.navigationContext.external then
        return self.navigationContext
    end
    return self:_Context()
end

local function contextBase(context)
    if not context then return nil end
    if context.external then return context.base end
    return ns.GetBaseStepWaypoint and ns:GetBaseStepWaypoint(context.step)
end

local function routeMatches(route, context, base, checkOrigin)
    local match, goal = route.match or {}, context.goal
    local action, map = goal.t or goal.action, goal.map or (base and base.mapID)
    if match.guide and match.guide ~= context.guide.id then return false end
    if match.routeStep and match.routeStep ~= context.progress.cursor then return false end
    if match.map and match.map ~= map then return false end
    if match.toMap and match.toMap ~= map then return false end
    if match.quests or match.npcs then
        local questMatch = match.quests and contains(match.quests, goal.quest or goal.questID)
        local npcMatch = match.npcs and contains(match.npcs, goal.npc)
        if not questMatch and not npcMatch then return false end
    end
    if not contains(match.actions, action) then return false end
    if match.item and match.item ~= goal.item then return false end
    if not contains(match.factions, call(UnitFactionGroup, "player")) then return false end
    if checkOrigin and match.fromMap and call(C_Map and C_Map.GetBestMapForUnit, "player") ~= match.fromMap then return false end
    return true
end

local function routeById(id, state, context)
    local own = state.ownRoutes[context.key]
    if own and own.id == id then return own end
    for _, route in ipairs(W.routes) do if route.id == id then return route end end
end

function W:_Candidate(context, base, state)
    local active = state.active
    if active and active.key == context.key then
        local route = routeById(active.route, state, context)
        local entry = route and state.entries[entryKey(context, route)]
        if route and entry and entry.started and not entry.done and not entry.bypassed
            and routeMatches(route, context, base, false) then return route end
    end
    local own = state.ownRoutes[context.key]
    if own and #own.points > 0 then return own end
    -- A verified crossing/ride/portal comes before a destination's local cave.
    for _, route in ipairs(self.routes) do
        if route.kind ~= "cave" and routeMatches(route, context, base, true) then return route end
    end
    for _, route in ipairs(self.routes) do
        if route.kind == "cave" and routeMatches(route, context, base, true) then return route end
    end
end

local sourcePoint
function W:_Entry(state, context, route)
    local key = entryKey(context, route)
    local entry = state.entries[key]
    if type(entry) ~= "table" then
        local legacyKey = context.key .. ":" .. route.id
        local legacy = state.entries[legacyKey]
        if isAccess(route) and type(legacy) ~= "table" then
            local suffix = ":" .. route.id
            for oldKey, previous in pairs(state.entries) do
                if type(oldKey) == "string" and type(previous) == "table" and previous.done and oldKey:sub(-#suffix) == suffix then
                    legacy, legacyKey = previous, oldKey; break
                end
            end
        end
        if isAccess(route) and type(legacy) == "table" then state.entries[legacyKey] = nil
        elseif not entryRoom(state, key) then return nil end
        entry = { index = 1, sourceCommit = route.provenance and route.provenance.commit }
        if type(legacy) == "table" then for field, value in pairs(legacy) do entry[field] = value end end
        if legacy then entry.targetKey = entry.targetKey or legacyKey:sub(1, -#route.id - 2) end
        state.entries[key] = entry
    end
    -- Old versions permanently bypassed a distant or temporarily unavailable
    -- entrance. Retry those decisions; only an authored passed gate persists.
    if entry.bypassed and not entry.passEvidence then entry.bypassed, entry.reason, entry.started = nil, nil, nil end
    if isAccess(route) and (entry.done or entry.passEvidence) and entry.targetKey ~= context.key then
        local mouth = sourcePoint(route.points[1])
        local distance = mouth and ns:GetWaypointVector(mouth)
        if finite(distance) and distance > (route.exitRadius or 600) and call(IsIndoors) == false then
            entry.index, entry.done, entry.started, entry.bypassed, entry.passEvidence = 1, nil, nil, nil, nil
            entry.force, entry.reason, entry.waiting = nil, nil, nil
        end
    end
    state.limitReason = nil
    entry.index = math.max(1, math.min(math.floor(tonumber(entry.index) or 1), #route.points + 1))
    if entry.index > #route.points then entry.done = true end
    return entry
end

sourcePoint = function(raw)
    if not ns.ResolveWaypointPoint then return nil end
    local point = ns:ResolveWaypointPoint(raw)
    if point then
        point.radius = finite(raw.radius) and raw.radius > 0 and raw.radius or 12
        if finite(raw.z) then point.z = raw.z end
    end
    return point
end

function W:_ShouldStart(context, route, base)
    if context.progress.review then return false, "Revisión manual" end
    local first = sourcePoint(route.points[1])
    if not first then return false, "Entrada sin posición disponible en este cliente" end
    if isAccess(route) and ns.GetWaypointWorldPosition then
        local c1, n1, w1 = ns:GetWaypointWorldPosition(first)
        local function sameEntry(goal)
            if type(goal) ~= "table" then return false end
            if (goal.t or goal.action) ~= "goto" then return false end
            if ns.MatchesConditions and not ns:MatchesConditions(goal.only) then return false end
            local previous = ns:GetGoalWaypoint(goal)
            local c2, n2, w2
            if previous then c2, n2, w2 = ns:GetWaypointWorldPosition(previous) end
            return c1 and c1 == c2 and n2 and math.sqrt((n1 - n2)^2 + (w1 - w2)^2) <= 15
        end
        -- Respect the original route's own gate (or an explicit user skip).
        -- Do not send the next goal back through an entrance just traversed.
        for i = 1, context.index - 1 do
            if sameEntry((context.step.goals or {})[i]) then return false, "La ruta ya pasó por esta entrada", true end
        end
        local prior = context.guide.steps and context.guide.steps[context.progress.cursor - 1]
        for _, goal in ipairs(prior and prior.goals or {}) do
            if sameEntry(goal) then return false, "La ruta ya pasó por esta entrada", true end
        end
    end
    local distance = ns:GetWaypointVector(first)
    -- Indoors elsewhere (an inn across the zone) is not proof of being in this
    -- cave. Keep a close, observed interior exemption, never distance alone.
    if isAccess(route) and base and call(IsIndoors) == true then
        local direct = ns:GetWaypointVector(base)
        if finite(direct) and finite(distance) and direct <= 100 and direct + 15 < distance then
            return false, "Ya estás en un interior junto al objetivo; acceso omitido", true
        end
    end
    -- A verified entrance remains useful from far away. Missing vectors are
    -- retried by normal navigation instead of becoming a permanent bypass.
    return true
end

function W:_Arrived(raw, point)
    local distance, reason = ns:GetWaypointVector(point)
    if not finite(distance) then return false, reason or "Posición no disponible" end
    if distance > point.radius then return false end
    if raw.mode == "transport" then return false, "Confirma cuando hayas subido al transporte; estar en el muelle no prueba un viaje", "Confirma al embarcar" end
    if raw.mode == "interact" then return false, "Interactúa con el NPC indicado o confirma este punto", "Habla con el personaje" end
    if raw.mode == "confirm" then return false, "Estás cerca; confirma el punto (sin altitud verificada)", "Confirma el punto" end
    if point.z == nil then return false, "Altitud no disponible; confirma el punto", "Confirma el punto" end
    local delta = ns:GetWaypointHeightDifference(point)
    if not finite(delta) then return false, "No se puede comprobar la altura; confirma el punto", "Confirma el punto" end
    if math.abs(delta) > (raw.heightTolerance or 8) then
        local message = delta > 0 and "El punto está más arriba" or "El punto está más abajo"
        return false, message, message
    end
    return true
end

function W:_Advance(entry, route, how)
    entry.index = entry.index + 1
    entry.waiting = nil
    entry.lastAdvance = how
    if entry.index > #route.points then entry.done = true end
end

function W:Resolve(step, goal, base)
    return self:_Resolve(self:_Context(step, goal), base)
end

function W:ResolveTarget(input)
    return self:_Resolve(self:_TargetContext(input), input and input.base)
end

function W:_Resolve(context, base)
    local state = db()
    if not state or not context then return base end
    context.base = base
    self.navigationContext, self.navigationOwner = context, ns.char
    if state.active and state.active.key ~= context.key then state.active = nil end
    local route = self:_Candidate(context, base, state)
    if not route then return base end
    local entry = self:_Entry(state, context, route)
    if not entry then return base end
    if call(UnitIsDeadOrGhost, "player") == true then return base end
    if not state.enabled or state.paused or context.progress.review then return base end
    if entry.done or entry.bypassed then return base end
    if not entry.started then
        local allowed, reason, passed = self:_ShouldStart(context, route, base)
        if not entry.force and not allowed then
            entry.waiting, entry.reason = reason, reason
            if passed then entry.bypassed, entry.passEvidence, entry.targetKey = true, true, context.key; return base end
            return nil
        end
        entry.started, entry.targetKey, entry.reason = true, context.key, nil
    end
    state.active = { key = context.key, route = route.id, entryKey = entryKey(context, route), external = context.external }
    local raw = route.points[entry.index]
    local point = raw and sourcePoint(raw)
    if not point then entry.waiting = "Punto sin coordenadas disponibles"; return nil end
    local arrived, reason, hint = self:_Arrived(raw, point)
    entry.waiting = reason
    if arrived then
        self:_Advance(entry, route, "arrival")
        if entry.done then return base end
        raw = route.points[entry.index]
        point = sourcePoint(raw)
        if not point then return nil end
    end
    point.intermediate, point.routeID, point.routeTitle = true, route.id, route.title
    point.routeLabel = raw.label or route.title
    point.label = point.routeLabel
    point.pointIndex, point.pointCount = entry.index, #route.points
    point.goal, point.source = context.goal, "itinerary"
    point.targetSource = context.source or (base and base.source)
    point.guideID, point.stepIndex, point.goalIndex = context.guide.id, context.progress.cursor, context.index
    point.waiting, point.waitingHint = entry.waiting, hint
    return point
end

function W:GetStatus()
    local state, context = db(), self:_ControlContext()
    if not state or not context then return { available = false, enabled = false, routing = false } end
    local base = contextBase(context)
    local route = self:_Candidate(context, base, state)
    if not route then return { available = false, enabled = state.enabled, paused = state.paused, routing = false } end
    local entry = state.entries[entryKey(context, route)] or {}
    local index = tonumber(entry.index) or 1
    return {
        available = true, enabled = state.enabled, paused = state.paused == true,
        routing = state.enabled and not state.paused and entry.started == true and not entry.done and not entry.bypassed,
        finished = entry.done == true, bypassed = entry.bypassed == true,
        routeID = route.id, title = route.title, goalKey = context.key,
        index = index, total = #route.points, label = route.points[index] and route.points[index].label,
        waiting = entry.waiting, reason = entry.reason or state.limitReason, provenance = route.provenance,
        external = context.external == true, targetSource = context.source or (base and base.source),
    }
end

function W:IsRouting()
    -- Safe inside the quest engine: do not call GetActiveGoal/GetGoalStatus
    -- from this predicate, since a travel goal may itself ask IsRouting.
    local state = db()
    if not state or not state.enabled or state.paused or not state.active or state.active.external then return false end
    local guide, _, progress = ns:GetCurrent()
    local prefix = guide and progress and (guide.id .. ":" .. tostring(progress.cursor) .. ":")
    if not prefix or state.active.key:sub(1, #prefix) ~= prefix then return false end
    local entry = state.entries[state.active.entryKey or (state.active.key .. ":" .. state.active.route)]
    return entry ~= nil and entry.started == true and not entry.done and not entry.bypassed
end

local function refresh()
    if ns.UpdateNavigation then ns:UpdateNavigation() end
    if ns.RefreshUI then ns:RefreshUI() end
end

function W:Toggle(enabled)
    local state = db()
    if not state then return false, "Todavía no hay un personaje cargado" end
    state.enabled = enabled == nil and not state.enabled or enabled == true
    if state.enabled then
        local context = self:_ControlContext()
        local base = contextBase(context)
        local route = context and self:_Candidate(context, base, state)
        if route then
            local entry = self:_Entry(state, context, route)
            if entry and not entry.done then entry.force, entry.bypassed = true, nil end
        end
        state.paused = false
    end
    refresh()
    return true, state.enabled and "Puntos intermedios activados" or "Puntos intermedios desactivados; progreso conservado"
end

function W:Pause(paused)
    local state = db()
    if not state then return false end
    state.paused = paused == nil and not state.paused or paused == true
    refresh()
    return true, state.paused and "Itinerario en pausa" or "Itinerario reanudado"
end

function W:Skip()
    local state, context = db(), self:_ControlContext()
    if not state or not context then return false, "No hay un objetivo activo" end
    local route = self:_Candidate(context, contextBase(context), state)
    if not route then return false, "Este objetivo no tiene itinerario" end
    local entry = self:_Entry(state, context, route)
    if not entry then return false, state.limitReason end
    if entry.done then return false, "Los puntos ya están terminados" end
    entry.started, entry.force, entry.bypassed, entry.targetKey = true, true, nil, context.key
    state.active = { key = context.key, route = route.id, entryKey = entryKey(context, route), external = context.external }
    self:_Advance(entry, route, "manual")
    refresh()
    return true, entry.done and "Puntos terminados; continúa con el objetivo de la guía" or "Punto confirmado; sigue el siguiente"
end

function W:Reset()
    local state, context = db(), self:_ControlContext()
    if not state or not context then return false, "No hay un objetivo activo" end
    local route = self:_Candidate(context, contextBase(context), state)
    if not route then return false, "Este objetivo no tiene itinerario" end
    local room, reason = entryRoom(state, entryKey(context, route))
    if not room then return false, reason end
    state.entries[entryKey(context, route)] = { index = 1, force = true, started = true, targetKey = context.key }
    state.active, state.enabled, state.paused = { key = context.key, route = route.id, entryKey = entryKey(context, route), external = context.external }, true, false
    refresh()
    return true, "Itinerario reiniciado para este objetivo"
end

function W:Capture(label, options)
    local state, context = db(), self:_ControlContext()
    if not state or not context then return false, "Elige primero una guía con un objetivo activo" end
    local here = ns.PlayerPoint and ns:PlayerPoint()
    local point = here and ns.ResolveWaypointPoint and ns:ResolveWaypointPoint(here)
    if not point then return false, "El juego no ofrece tu posición actual" end
    if type(options) ~= "table" then options = { kind = options } end
    local continent = ns.GetWaypointWorldPosition and ns:GetWaypointWorldPosition(point)
    local _, _, z, instance = call(UnitPosition, "player")
    local height = finite(z) and z ~= 0 and instance == continent and z or nil
    local route = state.ownRoutes[context.key]
    if not route and count(state.ownRoutes) >= self.limits.ownRoutes then
        return false, "Límite de itinerarios propios alcanzado; tus posiciones guardadas se conservan"
    end
    if route and #route.points >= self.limits.pointsPerRoute then
        return false, "Este itinerario ya tiene el máximo de puntos; tus posiciones guardadas se conservan"
    end
    local ownPoints = 0
    for _, own in pairs(state.ownRoutes) do ownPoints = ownPoints + #(own.points or {}) end
    if ownPoints >= self.limits.ownPoints then return false, "Límite total de posiciones guardadas alcanzado" end
    local routeID = route and route.id or ("observed:" .. context.key)
    local room, reason = entryRoom(state, context.key .. ":" .. routeID)
    if not room then return false, reason end
    if not route then
        route = { id = routeID, title = "Mi itinerario", kind = "observed", points = {},
            provenance = { source = "Posiciones observadas del jugador", build = select(2, call(GetBuildInfo)) } }
        state.ownRoutes[context.key] = route
    end
    local kind = options.kind == "transport" and "transport" or (height and "walk" or "confirm")
    route.points[#route.points + 1] = {
        map = point.mapID, x = point.x * 100, y = point.y * 100, z = height,
        label = type(label) == "string" and label ~= "" and label:sub(1, 160) or ("Punto observado " .. (#route.points + 1)),
        radius = finite(options.radius) and options.radius > 0 and options.radius or 8, mode = kind,
    }
    state.entries[context.key .. ":" .. route.id] = { index = 1, force = true, started = true }
    state.active, state.enabled, state.paused = { key = context.key, route = route.id, entryKey = entryKey(context, route), external = context.external }, true, true
    refresh()
    return true, "Punto real guardado; itinerario en pausa mientras añades posiciones"
end

function W:Observe(event)
    local state, context = db(), self:_ControlContext()
    if not state or not context or not state.enabled or state.paused or context.progress.review then return end
    local route = self:_Candidate(context, contextBase(context), state)
    local entry = route and state.entries[entryKey(context, route)]
    local raw = entry and not entry.done and not entry.bypassed and route.points[entry.index]
    if not raw or raw.mode ~= "interact" or raw.event ~= event or not raw.npc then return end
    local guid = call(UnitGUID, "npc")
    local npc = type(guid) == "string" and tonumber(guid:match("%-(%d+)%-[^%-]+$"))
    local point = sourcePoint(raw)
    local distance = point and ns:GetWaypointVector(point)
    if npc == raw.npc and finite(distance) and distance <= point.radius then
        self:_Advance(entry, route, "interaction")
    end
end

local events = CreateFrame("Frame")
for _, event in ipairs({ "GOSSIP_SHOW", "QUEST_GREETING", "MERCHANT_SHOW", "TAXIMAP_OPENED" }) do
    pcall(events.RegisterEvent, events, event)
end
events:SetScript("OnEvent", function(_, event)
    if ns.initialized then W:Observe(event) end
end)


