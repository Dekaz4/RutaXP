local addonName, ns = ...
ns.name = addonName
ns.guides, ns.order, ns.turnedIn = {}, {}, {}

local function trim(text)
    return (tostring(text or ""):gsub("^%s+", ""):gsub("%s+$", ""))
end

local function call(api, ...)
    if type(api) ~= "function" then return nil end
    local ok, value = pcall(api, ...)
    if ok then return value end
end

function ns:Print(text)
    if DEFAULT_CHAT_FRAME then
        DEFAULT_CHAT_FRAME:AddMessage("|cffffce72RutaXP|r · " .. text)
    end
end

function ns:RegisterGuide(guide)
    if type(guide) ~= "table" or type(guide.id) ~= "string" or guide.id == ""
        or type(guide.title) ~= "string" or type(guide.steps) ~= "table" or #guide.steps == 0 then
        return false, "La guía necesita id, título y pasos."
    end
    if self.guides[guide.id] then return false, "El id de guía ya existe." end
    for _, step in ipairs(guide.steps) do
        if type(step) ~= "table" or type(step.title) ~= "string" then
            return false, "Cada paso necesita un título."
        end
    end
    self.guides[guide.id] = guide
    self.order[#self.order + 1] = guide.id
    return true
end

function ns:GetProgress(id)
    local state = self.char.progress[id]
    if type(state) ~= "table" then
        state = { cursor = 1, confirmed = {} }
        self.char.progress[id] = state
    end
    if type(state.confirmed) ~= "table" then state.confirmed = {} end
    local guide = self.guides[id]
    state.cursor = math.max(1, math.min(tonumber(state.cursor) or 1, #guide.steps + 1))
    return state
end

function ns:GetCurrent()
    local guide = self.char and self.guides[self.char.activeGuide]
    if not guide then return nil end
    local state = self:GetProgress(guide.id)
    return guide, guide.steps[state.cursor], state
end

function ns:GetQuestTitle(id)
    return call(C_QuestLog and C_QuestLog.GetTitleForQuestID, id) or ("Misión " .. tostring(id))
end

function ns:IsStepComplete(step)
    if not step then return false end
    if step.action == "level" then return (UnitLevel("player") or 0) >= (step.level or 1000) end
    local id = step.questID
    if not id then return false end
    local delivered = self.turnedIn[id]
        or call(C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted, id)
        or call(IsQuestFlaggedCompleted, id)
    if delivered then return true end
    if step.action == "accept" then
        return call(C_QuestLog and C_QuestLog.IsOnQuest, id) == true
    elseif step.action == "complete" then
        return call(C_QuestLog and C_QuestLog.IsComplete, id) == true
    elseif step.action == "objective" and step.objective then
        local objectives = call(C_QuestLog and C_QuestLog.GetQuestObjectives, id)
        return objectives and objectives[step.objective] and objectives[step.objective].finished == true
    end
    return false
end

function ns:Sync()
    local guide, step, state = self:GetCurrent()
    while guide and self.char.auto and not state.review do
        while step and self:IsStepComplete(step) do
            state.cursor = state.cursor + 1
            step = guide.steps[state.cursor]
        end
        if step or not self.GetGuideContinuation then break end
        local successor, _, coordinated = self:GetGuideContinuation()
        if not successor or coordinated then break end
        self:ApplyGuideContinuation(successor)
        guide, step, state = self:GetCurrent()
    end
    if self.UpdateGuideTravel then self:UpdateGuideTravel() end
    if self.RefreshUI then self:RefreshUI() end
end

function ns:SelectGuide(id)
    if not self.guides[id] then return end
    self.char.activeGuide = id
    self:Sync()
end

function ns:Next()
    local guide, _, state = self:GetCurrent()
    if not guide then return end
    state.cursor = math.min(state.cursor + 1, #guide.steps + 1)
    state.review = nil
    self:Sync()
end

function ns:Previous()
    local guide, _, state = self:GetCurrent()
    if not guide then return end
    state.cursor = math.max(1, state.cursor - 1)
    state.review = true -- Permite leer pasos anteriores aunque su misión ya esté hecha.
    self:Sync()
end

function ns:ResetGuide(id)
    if self.guides[id] then
        self.char.progress[id] = { cursor = 1, confirmed = {}, review = true }
        self:Sync()
    end
end

function ns:GetVisibleGuides(search, allFactions)
    local results = {}
    search = trim(search):lower()
    local faction = UnitFactionGroup("player")
    for _, id in ipairs(self.order) do
        local guide = self.guides[id]
        local haystack = (guide.title .. " " .. (guide.zoneName or "") .. " " .. (guide.kind or "") .. " " .. (guide.summary or "")):lower()
        if (allFactions or not guide.faction or guide.faction == faction)
            and (search == "" or haystack:find(search, 1, true)) then
            results[#results + 1] = guide
        end
    end
    return results
end

function ns:GetObjectives(step)
    if not step or not step.questID then return "" end
    local objectives = call(C_QuestLog and C_QuestLog.GetQuestObjectives, step.questID)
    local lines = {}
    for _, objective in ipairs(objectives or {}) do
        if objective.text then
            lines[#lines + 1] = (objective.finished and "|cff7edd9c[Hecho] " or "|cffb7c2d0• ") .. objective.text .. "|r"
        end
    end
    return table.concat(lines, "\n")
end

function ns:PlayerPoint()
    local mapID = call(C_Map and C_Map.GetBestMapForUnit, "player")
    local position = mapID and call(C_Map and C_Map.GetPlayerMapPosition, mapID, "player")
    if position then
        local x, y = position:GetXY()
        if x and y then return { mapID = mapID, x = x, y = y } end
    end
end

function ns:Navigate()
    local _, step = self:GetCurrent()
    local point
    if self.GetStepWaypoint then point = self:GetStepWaypoint(step)
    else point = step and step.waypoint end
    if not point then self:Print("Este paso no tiene coordenadas guardadas."); return false end
    self.char.arrow = true
    if self.UpdateNavigation then self:UpdateNavigation() end
    if not (C_Map and C_Map.SetUserWaypoint and UiMapPoint and UiMapPoint.CreateFromCoordinates) then
        self:Print("Este cliente no ofrece marcadores nativos de mapa."); return false
    end
    if C_Map.CanSetUserWaypointOnMap and not call(C_Map.CanSetUserWaypointOnMap, point.mapID) then
        self:Print("El juego no permite colocar un marcador en este mapa."); return false
    end
    local target = call(UiMapPoint.CreateFromCoordinates, point.mapID, point.x, point.y)
    if not target or not call(C_Map.SetUserWaypoint, target) then
        self:Print("El juego no ha podido colocar el marcador."); return false
    end
    if C_SuperTrack and C_SuperTrack.SetSuperTrackedUserWaypoint then
        call(C_SuperTrack.SetSuperTrackedUserWaypoint, true)
    end
    self:Print("Destino marcado en el mapa.")
    return true
end

function ns:Command(message)
    local command, rest = trim(message):match("^(%S*)%s*(.-)$")
    command = command:lower()
    if self.HandleFeatureCommand and self:HandleFeatureCommand(command, rest) then return
    elseif command == "" then self:ToggleWindow()
    elseif command == "siguiente" then self:Next()
    elseif command == "anterior" then self:Previous()
    elseif command == "mapa" then self:Navigate()
    elseif command == "flecha" then
        self.char.arrow = self.char.arrow == false
        if self.UpdateNavigation then self:UpdateNavigation() end
        if self.RefreshUI then self:RefreshUI() end
        self:Print(self.char.arrow and "Flecha de destino activada." or "Flecha de destino oculta.")
    elseif command == "recomendada" or command == "zona" then
        local guide = (self.DetectZoneGuide and self:DetectZoneGuide(false))
            or (self.GetRecommendedGuide and self:GetRecommendedGuide())
        if guide and not self.DetectZoneGuide then
            self:SelectGuide(guide.id)
            self:Print("Guía recomendada seleccionada: «" .. guide.title .. "».")
        elseif not guide then
            self:Print("No hay una guía recomendada disponible para tu personaje.")
        end
    elseif command == "precision" or command == "precisión" then
        local _, step = self:GetCurrent()
        local point = step and self.GetStepWaypoint and self:GetStepWaypoint(step)
        if not point then
            self:Print("Este paso no tiene destino.")
        else
            local labels = {
                learned = "posición observada al interactuar con el NPC",
                game = "marcador del propio juego",
                guide = "coordenadas de la guía (aproximadas)",
            }
            local npc = point.candidateName or (point.goal and point.goal.npcName)
            self:Print("Destino" .. (npc and (" · " .. npc) or "") .. ": " .. (labels[point.source] or "paso manual"))
        end
    elseif command == "diagnostico" or command == "diagnóstico" then
        local guide, step, state = self:GetCurrent()
        self:Print("Diagnóstico RutaXP · " .. tostring(select(4, GetBuildInfo())) .. " · proyecto " .. tostring(WOW_PROJECT_ID))
        if not guide then self:Print("No hay guía seleccionada."); return end
        self:Print("Guía " .. guide.id .. " · paso " .. state.cursor .. "/" .. #guide.steps .. (state.review and " · revisión" or ""))
        local goal, index, status, reason
        if self.GetActiveGoal then goal, index, status, reason = self:GetActiveGoal() end
        if goal then
            self:Print("Objetivo " .. tostring(goal.quest or goal.questID or goal.t or goal.action) .. " · " .. tostring(status or "manual") .. (reason and (" · " .. reason) or ""))
        end
        local point = step and self.GetStepWaypoint and self:GetStepWaypoint(step)
        self:Print(point and string.format("Mapa %d · %.2f, %.2f · fuente %s", point.mapID, point.x * 100, point.y * 100, point.source or "personal")
            or (not goal and "Tus objetivos de este paso ya están resueltos." or "El objetivo actual no tiene coordenadas."))
        if self.Duo and self.Duo.GetReport then self:Print(self.Duo:GetReport()) end
        local walk = self.Walking and self.Walking:GetStatus()
        if walk then
            self:Print(string.format("Camino: %s · cálculos %d · cancelaciones %d · pendiente %.1f s",
                walk.text or walk.phase or "sin datos", walk.requests or 0, walk.cancellations or 0, walk.pendingSeconds or 0))
            self:Print(string.format("Rutas aceptadas %d · rechazadas %d · último motivo %s",
                walk.accepted or 0, walk.rejected or 0, walk.lastReason or "sin datos"))
        end
    elseif command == "talentos" or command == "talento" or command == "n" then
        if self.Talents and self.Talents.TogglePanel then
            self.Talents.TogglePanel()
        end
    elseif command == "actualizar" then
        if self.Updates then self.Updates:Show() end
    elseif command == "version" then
        if self.Updates then self:Print("Addon RutaXP " .. self.Updates:GetStatus().localVersion) end
        local version, build, _, interface = GetBuildInfo()
        self:Print(tostring(version) .. " · build " .. tostring(build) .. " · interfaz " .. tostring(interface) .. " · proyecto " .. tostring(WOW_PROJECT_ID))
    else
        self:Print("/rutaxp · autoduo · duo · herramientas · sesion · recuperar · adaptar · puntos · camino · recalcular · talentos · zona · flecha · mapa · siguiente · anterior · diagnostico · version · actualizar")
    end
end

function ns:Initialize()
    RutaXPDB = type(RutaXPDB) == "table" and RutaXPDB or {}
    RutaXPCharDB = type(RutaXPCharDB) == "table" and RutaXPCharDB or {}
    self.db, self.char = RutaXPDB, RutaXPCharDB
    -- Saved routes belong to the player. Keep even malformed legacy values
    -- for recovery instead of deleting them when installing a newer version.
    if type(self.db.customGuides) == "table" then
        for _, guide in ipairs(self.db.customGuides) do
            local ok = self:RegisterGuide(guide)
            if not ok then
                self:Print("Una guía personal no pudo cargarse; sus datos siguen guardados para recuperarla.")
            end
        end
    end
    self.db.schemaVersion = 3
    self.char.progress = type(self.char.progress) == "table" and self.char.progress or {}
    if self.char.auto == nil then self.char.auto = true end
    if self.char.tracker == nil then self.char.tracker = true end
    if self.char.arrow == nil then self.char.arrow = true end
    if self.char.seen and not self.char.uiV3 then
        self.char.uiV3 = true
    end
    if self.RestoreFeatures then self:RestoreFeatures() end
    local active = self.guides[self.char.activeGuide]
    if not active then
        local recommended = self.GetRecommendedGuide and self:GetRecommendedGuide()
        local guides = self:GetVisibleGuides("", false)
        self.char.activeGuide = (recommended and recommended.id) or (guides[1] and guides[1].id) or self.order[1]
        if self.char.activeGuide and self.guides[self.char.activeGuide] and self.guides[self.char.activeGuide].status == "beta" then
            local state = self:GetProgress(self.char.activeGuide)
            state.placed = false
        end
    end
    self:CreateUI()
    if self.InitializeFeatures then self:InitializeFeatures() end
    if self.Updates then self.Updates:Initialize() end
    if not self.char.seen then
        self.window:Show()
        self.char.seen = true
        self.char.uiV3 = true
    end
    self:Sync()
    if self.StartFeatureSession then self:StartFeatureSession() end
    self:Print("Listo. Panel activo en pantalla · escribe /rutaxp para abrir todas las guías o /rutaxp zona para detectar tu zona.")
    if WOW_PROJECT_ID ~= (WOW_PROJECT_CAMELOT or 18) then
        self:Print("Cliente distinto de Forever detectado. Esta versión se ha preparado para Forever; comprueba /rutaxp version.")
    end
end

ns.events = CreateFrame("Frame")
ns.events:RegisterEvent("ADDON_LOADED")
ns.events:RegisterEvent("PLAYER_LOGIN")
ns.events:RegisterEvent("PLAYER_ENTERING_WORLD")
ns.events:RegisterEvent("QUEST_ACCEPTED")
ns.events:RegisterEvent("QUEST_TURNED_IN")
ns.events:RegisterEvent("QUEST_LOG_UPDATE")
ns.events:RegisterEvent("QUEST_WATCH_UPDATE")
ns.events:RegisterEvent("QUEST_REMOVED")
ns.events:RegisterEvent("QUEST_DATA_LOAD_RESULT")
ns.events:RegisterEvent("PLAYER_LEVEL_UP")
ns.events:SetScript("OnEvent", function(_, event, first, second)
    if event == "ADDON_LOADED" then
        if first == addonName then ns.loaded = true end
    elseif event == "PLAYER_LOGIN" and ns.loaded and not ns.initialized then
        ns.initialized = true
        ns:Initialize()
    elseif ns.initialized then
        if event == "QUEST_TURNED_IN" then
            ns.turnedIn[first] = true
        elseif event == "QUEST_ACCEPTED" then
            local questID = second or first
            ns.turnedIn[questID] = nil -- Una nueva aceptación inicia otra repetición.
        end
        ns:Sync()
    end
end)

SLASH_RUTAXP1 = "/rutaxp"
SLASH_RUTAXP2 = "/rutas"
SlashCmdList.RUTAXP = function(message) ns:Command(message) end
