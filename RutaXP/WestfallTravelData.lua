local _, ns = ...

-- Outdoor and city coordinates use the Era rectangles in MapFrames.lua.
-- The tram is a different instance with no shared city/world coordinate frame.
-- Radii and heights are in yards. For a boundary, reaching its pin is an
-- instruction to cross; the next map or instance confirms the crossing.
--
-- Geography: SendaFH 5d207e2, guides/forever/alliance/dwarf-gnome/01-dun-morogh,
-- 02-westfall and exploration/eastern-kingdoms-1-30. The city exit and border
-- bridge use tools/lib/travel/crossings.json (Carbonite-Classic 4d06280).
-- The Tinker Town portal is AreaTrigger 2175. Interior turns and the ramp
-- are sampled on connected walking paths in the bundled Forever terrain,
-- with city-floor heights to distinguish streets from the roofs above.
ns.WestfallTravelLegs = {
    { id = "dun-ramp", map = 1426, f = "e", x = 51.02, y = 43.91, z = 396, radius = 48,
        title = "Camino de Forjaz",
        text = "Sigue los carteles de Forjaz hasta la subida de la ciudad. Desde Kharanos, toma la carretera que sale hacia el norte." },
    { id = "dun-gate", map = 1426, f = "e", x = 53.63, y = 34.73, z = 497, radius = 24, boundary = true,
        title = "Entra en Forjaz",
        text = "Sube la rampa, atraviesa la gran puerta de piedra y sigue el pasadizo hasta entrar en la ciudad." },
    { id = "forge-ring", map = 1455, f = "e", x = 49.66, y = 59.93, z = 502, radius = 28,
        title = "Hacia Ciudad Manitas",
        text = "Rodea la Gran Fundición por el lado sur y sigue los carteles de Ciudad Manitas, al este de Forjaz." },
    -- 502 is the walking floor inside trigger 2175, whose center is six yards higher.
    { id = "tinker-town", map = 1455, f = "e", x = 78.02, y = 51.37, z = 502, radius = 14, boundary = true,
        title = "Entrada del Tren Subterráneo",
        text = "En Ciudad Manitas, atraviesa el portal del Tren Subterráneo para entrar en la estación." },
    { id = "tram", instanceID = 369, boundary = true,
        title = "Tren a Ventormenta",
        text = "Espera en el andén y sube al tren. En la otra estación, baja y atraviesa el portal al Distrito de los Enanos." },
    { id = "stormwind-canals", map = 1453, f = "e", x = 65.38, y = 36.53, z = 104, radius = 30,
        title = "Sal del Distrito de los Enanos",
        text = "Desde la estación, sal a las calles del Distrito de los Enanos y sigue el camino hacia los canales." },
    { id = "trade-district", map = 1453, f = "e", x = 57.01, y = 62.56, z = 94, radius = 34,
        title = "Distrito de Mercaderes",
        text = "Cruza hacia el Distrito de Mercaderes y toma la salida hacia el Valle de los Héroes." },
    { id = "stormwind-gate", map = 1453, f = "e", x = 73.34, y = 90.73, radius = 24, boundary = true,
        title = "Puerta de Ventormenta",
        text = "Cruza el puente de las estatuas y atraviesa la puerta principal para salir al Bosque de Elwynn." },
    { id = "goldshire", map = 1429, f = "e", x = 42.11, y = 65.93, radius = 56,
        title = "Cruce de Villadorada",
        text = "Sigue la carretera hasta el cruce de Villadorada. Allí toma el camino hacia el oeste, a la izquierda en el mapa." },
    { id = "westbrook", map = 1429, f = "e", x = 24.23, y = 74.45, radius = 65,
        title = "Cuartel Arroyoeste",
        text = "Sigue al oeste por la carretera y pasa junto al cuartel. Continúa por el camino hacia el puente." },
    { id = "westfall-bridge", map = 1429, f = "e", x = 22.30, y = 78.20, radius = 30, boundary = true,
        title = "Puente a Páramos de Poniente",
        text = "Cruza el puente y continúa por la carretera hasta entrar en Páramos de Poniente." },
    { id = "saldean", map = 1436, f = "e", x = 56.25, y = 34.73, z = 38, radius = 68,
        title = "Carretera de la Finca de Saldean",
        text = "Desde la entrada de Páramos, sigue la carretera hacia el sur. Pasa junto a la Finca de Saldean rumbo a la colina." },
    { id = "sentinel", map = 1436, f = "e", x = 55.90, y = 49.80, radius = 150,
        title = "Llega a Colina del Centinela",
        text = "Sigue la carretera hasta la colina de la torre de piedra. Sube al poblado para empezar las misiones." },
}

local WESTFALL = "forever/alliance/02-westfall"
local ELWYNN = "forever/alliance/human/01-elwynn-forest"
local cartQuests = {[36] = "estofado", [151] = "avena", [64] = "reloj"}
local hintGuide, hintStep, hintTime, lastHint

-- The wagon stands beside the road into Westfall. Mention its quests only
-- while the player is passing it. The arrow keeps its original destination.
function ns:GetWestfallCartHint(guide, step, state, travel)
    if not guide or not state or state.review then return end
    if travel then
        if travel.destination ~= WESTFALL or travel.arrivalMap ~= 1436 or travel.waiting or not travel.point then return end
        if guide.id ~= WESTFALL and (guide.id ~= travel.source or state.cursor <= #guide.steps) then return end
    elseif guide.id == ELWYNN then
        local goal = step and step.goals and step.goals[1]
        if not goal or goal.t ~= "getfp" or goal.node ~= 4 then return end
    elseif guide.id ~= WESTFALL or state.cursor ~= 1 then
        return
    end
    local now = GetTime and GetTime()
    if now and hintTime and hintGuide == guide and hintStep == step and now - hintTime < 1 then return lastHint end
    hintGuide, hintStep, hintTime, lastHint = guide, step, now, nil
    local routing = self.TravelRouting
    if not routing or routing.OnTaxi() or routing.Zone() ~= 1436 then return end
    if UnitFactionGroup("player") ~= "Alliance" then return end
    local west = self.guides[WESTFALL]
    local visit = west and west.steps[3]
    local saved = self.char.progress[WESTFALL]
    if not visit or not visit.goals or (saved and (saved.review or type(saved.cursor) ~= "number" or saved.cursor > 3)) then return end
    if travel and saved and saved.cursor ~= 1 then return end
    local wagon = visit.goals[1]
    if not wagon or wagon.quest ~= 36 then return end
    local point = self:ResolveWaypointPoint(wagon)
    local distance = point and self:GetWaypointVector(point)
    if not distance or distance > 45 or not self:GetEarlyQuestSpace() then return end
    if not travel and self:ShouldWaitForEarlyQuest(step) then return end
    if travel and self.DuoAuto and self.DuoAuto:ShouldPauseAutomation() then return end

    local visitState = {cursor = 3, skipped = saved and saved.skipped, confirmed = saved and saved.confirmed}
    local names = {}
    for i, goal in ipairs(visit.goals) do
        local name = cartQuests[goal.quest]
        if name and goal.t == "accept" and self:GetGoalStatus(goal, visit, visitState, i) == "active" then
            names[#names + 1] = name
        end
    end
    if #names > 0 then lastHint = "Habla con los Cejade · " .. table.concat(names, ", ") end
    return lastHint
end
