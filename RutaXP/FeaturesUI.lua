local _, ns = ...
local tabs = { { "duo", "Dúo" }, { "session", "Mediciones" }, { "recovery", "Bloqueos" }, { "adaptation", "Ajustar ruta" }, { "waypoints", "Flecha" } }
local duoTabs = { { "duo", "Progreso" }, { "duo-route", "Ruta común" }, { "duo-differences", "Diferencias" },
    { "duo-meeting", "Reunión" }, { "duo-checkpoint", "Partida" }, { "duo-stops", "Paradas" } }
local function label(parent, text, x, y, width, font)
    local item = parent:CreateFontString(nil, "OVERLAY", font or "GameFontHighlight")
    item:SetPoint("TOPLEFT", x, y); item:SetWidth(width); item:SetJustifyH("LEFT"); item:SetJustifyV("TOP"); item:SetText(text)
    return item
end
local function button(parent, text, width, x, y, action)
    local b = CreateFrame("Button", nil, parent, "UIPanelButtonTemplate")
    b:SetSize(width, 26); b:SetPoint("TOPLEFT", x, y); b:SetText(text); b:SetScript("OnClick", action)
    return b
end
function ns:ShowFeatureText(title, text)
    if not self.featureExport then
        local f = CreateFrame("Frame", nil, UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
        f:SetSize(660, 460); f:SetPoint("CENTER"); f:SetFrameStrata("DIALOG")
        f:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
        f:SetBackdropColor(.035, .05, .08, 1); f:SetBackdropBorderColor(.65, .5, .26, 1)
        f.heading = label(f, "", 18, -16, 570, "GameFontNormalLarge")
        button(f, "X", 30, 612, -10, function() f:Hide() end)
        label(f, "Selecciona el texto y pulsa Ctrl+C para copiarlo.", 18, -46, 610)
        local scroll = CreateFrame("ScrollFrame", nil, f, "UIPanelScrollFrameTemplate")
        scroll:SetPoint("TOPLEFT", 18, -74); scroll:SetSize(598, 365)
        local edit = CreateFrame("EditBox", nil, scroll)
        edit:SetWidth(592); edit:SetHeight(360); edit:SetAutoFocus(false)
        if edit.SetMultiLine then edit:SetMultiLine(true) end
        if edit.SetFontObject then edit:SetFontObject("GameFontHighlightSmall") end
        edit:SetMaxLetters(50000)
        edit:SetScript("OnEscapePressed", function() f:Hide() end)
        scroll:SetScrollChild(edit); f.edit, f.scroll = edit, scroll
        f.measure = label(f, "", 0, 0, 592, "GameFontHighlightSmall"); f.measure:Hide()
        self.featureExport = f
    end
    self.featureExport.heading:SetText(title)
    self.featureExport.edit:SetText(text or "")
    self.featureExport.measure:SetText(text or "")
    self.featureExport.edit:SetHeight(math.max(360, self.featureExport.measure:GetStringHeight() + 30))
    self.featureExport.scroll:SetVerticalScroll(0)
    self.featureExport:Show()
    if self.featureExport.edit.HighlightText then self.featureExport.edit:HighlightText() end
end
function ns:CreateFeaturesUI()
    if self.featuresPanel then return end
    local f = CreateFrame("Frame", nil, UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
    f:SetSize(720, 550); f:SetPoint("CENTER"); f:SetFrameStrata("DIALOG")
    f:SetMovable(true); f:EnableMouse(true); f:RegisterForDrag("LeftButton"); f:SetClampedToScreen(true)
    f:SetScript("OnDragStart", f.StartMoving); f:SetScript("OnDragStop", f.StopMovingOrSizing)
    f:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
    f:SetBackdropColor(.035, .05, .08, .99); f:SetBackdropBorderColor(.65, .5, .26, 1)
    label(f, "RutaXP · Herramientas de ruta", 20, -16, 620, "GameFontNormalLarge")
    button(f, "X", 30, 672, -10, function() f:Hide() end)
    f.tabs, f.actions, f.duoTabs = {}, {}, {}
    for i, tab in ipairs(tabs) do
        f.tabs[i] = button(f, tab[2], 128, 20 + (i - 1) * 136, -52, function()
            self.featureTab = tab[1]; self:UpdateFeatures(); f.scroll:SetVerticalScroll(0)
        end)
    end
    for i, tab in ipairs(duoTabs) do
        f.duoTabs[i] = button(f, tab[2], 107, 20 + (i - 1) * 114, -88, function()
            self.featureTab = tab[1]; self:UpdateFeatures(); f.scroll:SetVerticalScroll(0)
        end)
    end
    f.scroll = CreateFrame("ScrollFrame", nil, f, "UIPanelScrollFrameTemplate")
    f.scroll:SetPoint("TOPLEFT", 20, -96); f.scroll:SetSize(654, 334)
    f.content = CreateFrame("Frame", nil, f.scroll); f.content:SetSize(646, 334)
    f.body = label(f.content, "", 0, 0, 638)
    f.scroll:SetScrollChild(f.content)
    for i = 1, 6 do
        local b = button(f, "", 216, 20 + ((i - 1) % 3) * 232, -452 - math.floor((i - 1) / 3) * 34, function()
            local action = self.featuresPanel.actions[i].action
            if action then action(); self:RefreshUI(); self:UpdateFeatures() end
        end)
        f.actions[i] = b
    end
    label(f, "Los ajustes se aplican a tu personaje. El progreso del amigo se muestra por separado.", 20, -526, 680, "GameFontHighlightSmall")
    f:SetScript("OnShow", function() self:UpdateFeatures() end)
    f:Hide(); self.featuresPanel = f
end
function ns:ToggleFeatures(tab)
    self:CreateFeaturesUI()
    if tab then self.featureTab = tab end
    if not tab and self.featuresPanel:IsShown() then self.featuresPanel:Hide()
    else self.featuresPanel:Show(); self:UpdateFeatures() end
end
function ns:UpdateFeatures()
    local f = self.featuresPanel
    if not f or not f:IsShown() or not self.char then return end
    local actions, text = {}, ""
    local function add(title, action) actions[#actions + 1] = { title = title, action = action } end
    local function result(ok, reason) if not ok and reason then self:Print(reason) end end
    local tab = self.featureTab or "duo"
    local isDuo = tab == "duo" or tab:sub(1, 4) == "duo-"
    for _, b in ipairs(f.duoTabs) do b:SetShown(isDuo) end
    f.scroll:ClearAllPoints(); f.scroll:SetPoint("TOPLEFT", 20, isDuo and -128 or -96)
    f.scroll:SetHeight(isDuo and 302 or 334)
    if tab == "duo" and self.Duo then
        local ctx = self.Duo:GetContext(); text = self.Duo:GetReport()
        local auto = self.DuoAuto and self.DuoAuto:GetStatus()
        if auto and (auto.phase ~= "probing" or ctx.known) then text = auto.text .. "\n\n" .. text end
        add(ctx.enabled and "Desactivar dúo" or "Activar dúo", function() self:UseManualDuoMode("Modo dúo cambiado manualmente", true); self.Duo:SetEnabled(not ctx.enabled) end)
        add(ctx.wait and "Continuar sin esperar" or "Esperar al amigo", function() self:UseManualDuoMode("Espera cambiada manualmente", true); self.Duo:SetWait(not ctx.wait) end)
        add(ctx.ready and "Marcarme no preparado" or "Estoy preparado", function() self.Duo:SetReady(not ctx.ready) end)
        add("Elegir la guía del amigo", function() self:UseManualDuoMode("Guía del compañero elegida manualmente"); result(self.Duo:AdoptPartnerGuide()) end)
        if auto then add(auto.enabled and "Automático al agruparse: sí" or "Automático al agruparse: no", function() result(self.DuoAuto:SetEnabled(not auto.enabled)) end) end
        if self.Duo.Resynchronize then add("Sincronizar de nuevo", function() result(self.Duo:Resynchronize()) end) end
    elseif tab == "duo-route" and self.DuoPlanner then
        local routes = self.DuoPlanner:GetCommonRoutes() or {}
        local lines = { "Rutas que podéis seguir juntos. Cada uno debe elegirla en su addon; se conserva el progreso individual." }
        for i, route in ipairs(routes) do
            lines[#lines + 1] = i .. ". " .. route.title .. "\n" .. (route.text or "")
            local index = i
            add("Elegir ruta común " .. i, function() self:UseManualDuoMode("Ruta común elegida manualmente"); result(self.DuoPlanner:ApplyCommonRoute(index)) end)
        end
        if #routes == 0 then lines[#lines + 1] = "No hay una ruta común verificable con los datos actuales. Activad Dúo y comprobad los requisitos y las zonas iniciales de ambos." end
        if self.Adaptation then add("Volver a ruta anterior", function() self:UseManualDuoMode("Ruta anterior elegida manualmente"); result(self.Adaptation:ReturnToPrevious()) end) end
        text = table.concat(lines, "\n\n")
    elseif tab == "duo-differences" and self.DuoPlanner then
        local differences = self.DuoPlanner:GetDifferences() or {}
        local pages = math.max(1, math.ceil(#differences / 3))
        f.differencePage = math.max(1, math.min(f.differencePage or 1, pages))
        local lines = { "Qué le falta a cada uno · página " .. f.differencePage .. "/" .. pages .. ". Un estado desconocido requiere datos recientes del compañero." }
        for i = (f.differencePage - 1) * 3 + 1, math.min(f.differencePage * 3, #differences) do
            local item = differences[i]
            lines[#lines + 1] = i .. ". " .. (item.title or self:GetQuestTitle(item.questID)) .. "\n" .. (item.text or "")
            if item.waypoint or item.action then
                local index = i
                add("Ver destino de diferencia " .. i, function() self:UseManualDuoMode("Recogida señalada manualmente"); result(self.DuoPlanner:FocusDifference(index)); if self.UpdateNavigation then self:UpdateNavigation() end end)
            end
        end
        if #differences == 0 then lines[#lines + 1] = "No se han confirmado diferencias en las misiones comparadas." end
        if pages > 1 then
            add("Página anterior", function() f.differencePage = f.differencePage > 1 and f.differencePage - 1 or pages end)
            add("Página siguiente", function() f.differencePage = f.differencePage % pages + 1 end)
        end
        add("Volver al objetivo de la guía", function() self.DuoPlanner:ClearFocus(); if self.Duo then self.Duo:FollowMeeting(false) end end)
        text = table.concat(lines, "\n\n")
    elseif tab == "duo-meeting" and self.Duo then
        local status = self.Duo:GetMeetingStatus() or {}
        text = status.text or status.report or "Compartid una posición real como punto de reunión. Recibirla no cambia la guía ni activa la flecha del compañero."
        if status.label then text = text .. "\n\n" .. status.label end
        if status.reason then text = text .. "\n\n" .. status.reason end
        if status.point then text = text .. string.format("\n\nMapa %d · %.1f, %.1f", status.point.mapID, status.point.x * 100, status.point.y * 100) end
        if status.distance then text = text .. string.format("\nDistancia al punto: %.0f m", status.distance * .9144) end
        text = text .. "\n\nLa flecha señala el punto acordado. Seguid los accesos del terreno y comprobad si estáis en la misma zona o capa."
        add("Reunirnos en mi posición", function() result(self.Duo:SetMeetingPoint()) end)
        add(status.following and "Dejar de seguir reunión" or "Seguir punto de reunión", function() result(self.Duo:FollowMeeting(not status.following)); if self.char then self.char.arrow = true end end)
        add("Quitar punto de reunión", function() result(self.Duo:ClearMeeting()) end)
        add("Volver al objetivo de la guía", function() self.Duo:FollowMeeting(false); if self.DuoPlanner then self.DuoPlanner:ClearFocus() end end)
    elseif tab == "duo-checkpoint" and self.DuoJourney then
        text = self.DuoJourney:GetCheckpointReport()
        add("Guardar partida juntos", function() result(self.DuoJourney:SaveCheckpoint()) end)
        add("Retomar mi ruta guardada", function() result(self.DuoJourney:ResumeCheckpoint()) end)
        add("Copiar resumen de partida", function() self:ShowFeatureText("Partida conjunta", self.DuoJourney:GetCheckpointReport()) end)
    elseif tab == "duo-stops" and self.DuoJourney then
        text = self.DuoJourney:GetStopReport()
        local stops = self.DuoJourney:GetStops() or {}
        local pages = math.max(1, math.ceil(#stops / 3))
        f.stopPage = math.max(1, math.min(f.stopPage or 1, pages))
        for i = (f.stopPage - 1) * 3 + 1, math.min(f.stopPage * 3, #stops) do
            local index = i
            add("Proponer parada " .. i, function() result(self.DuoJourney:BeginStop(index)) end)
        end
        if pages > 1 then add("Otras propuestas " .. f.stopPage .. "/" .. pages, function() f.stopPage = f.stopPage % pages + 1 end) end
        local status = self.DuoJourney:GetStopStatus() or {}
        if status.active and #stops > 0 then
            local choices = { "Propuestas disponibles:" }
            for i = (f.stopPage - 1) * 3 + 1, math.min(f.stopPage * 3, #stops) do
                choices[#choices + 1] = i .. ". " .. stops[i].title .. " · " .. (stops[i].text or "")
            end
            text = text .. "\n\n" .. table.concat(choices, "\n\n")
        end
        add(status.localReady and "Aún necesito la parada" or "Estoy listo para seguir", function() result(self.DuoJourney:SetStopReady(not status.localReady)) end)
        add("Terminar mi parada", function() result(self.DuoJourney:EndStop()) end)
        if pages == 1 then add("Consultar talentos", function() if self.Talents and self.Talents.TogglePanel then self.Talents.TogglePanel() end end) end
    elseif tab == "session" and self.Session then
        text = self.Session:GetReport()
        local summary = self.Session:GetSummary() or {}
        add(summary.paused and "Reanudar medición" or "Pausar medición", function() self.Session:SetPaused(not summary.paused) end)
        add("Empezar otra sesión", function() self.Session:Reset() end)
        add("Copiar informe", function() self:ShowFeatureText("Mediciones de RutaXP", self.Session:GetReport()) end)
    elseif tab == "recovery" and self.Recovery then
        local blockers = self.Recovery:GetBlockers() or {}
        local lines = { "La recuperación busca requisitos en las guías instaladas y conserva el punto donde dejaste tu ruta." }
        if #blockers == 0 then lines[#lines + 1] = "No se han detectado bloqueos en el objetivo actual." end
        for i, item in ipairs(blockers) do lines[#lines + 1] = i .. ". " .. (item.title or "Requisito pendiente") .. "\n" .. (item.reason or "") end
        local status = self.Recovery:GetStatus()
        if status and status.active then lines[#lines + 1] = "Recuperación en curso. «Volver a mi ruta» restaura tu paso anterior; no marca misiones como entregadas." end
        text = self.Recovery.GetReport and self.Recovery:GetReport() or table.concat(lines, "\n\n")
        if status and status.active then
            local missing = {}
            for _, id in ipairs(status.remainingQuestIDs or {}) do missing[#missing + 1] = "• " .. self:GetQuestTitle(id) end
            if #missing > 0 then text = text .. "\n\nPendientes de entregar:\n" .. table.concat(missing, "\n") end
            text = text .. "\n\nPuedes usar «Volver a mi ruta» sin dar estos requisitos por completados."
        end
        for i = 1, math.min(3, #blockers) do
            local index = i
            add("Recuperar requisito " .. i, function() result(self.Recovery:Start(index)) end)
        end
        add("Comprobar requisitos", function() result(self.Recovery:Resume()) end)
        add("Volver a mi ruta", function() result(self.Recovery:Cancel()) end)
    elseif tab == "adaptation" and self.Adaptation then
        local suggestions = self.Adaptation:GetSuggestions() or {}
        local lines = { "Propuestas según tu nivel, raza, clase y registro de misiones. Tú decides cuándo cambiar. La ruta del compañero no se cambia." }
        for i, item in ipairs(suggestions) do
            lines[#lines + 1] = i .. ". " .. (item.title or "Propuesta") .. "\n" .. (item.text or item.reason or "")
            if item.guideID then
                local index = i
                add("Aplicar propuesta " .. i, function() self:UseManualDuoMode("Ruta elegida manualmente"); result(self.Adaptation:ApplySuggestion(index)) end)
            end
        end
        if #suggestions == 0 then lines[#lines + 1] = "Tu ruta actual encaja con los datos disponibles." end
        if self.Adaptation.ReturnToPrevious then add("Volver a ruta anterior", function() self:UseManualDuoMode("Ruta anterior elegida manualmente"); result(self.Adaptation:ReturnToPrevious()) end) end
        text = table.concat(lines, "\n\n")
    elseif tab == "waypoints" and self.Waypoints then
        local status = self.Waypoints:GetStatus()
        text = type(status) == "string" and status or "Puntos intermedios: la flecha puede guiarte por una entrada antes del objetivo. Sigue las indicaciones del punto y confirma las entradas sin altura verificada."
        if type(status) == "table" then
            text = text .. "\n\n" .. (status.label or "Sin recorrido intermedio en este objetivo")
                .. (status.index and (" · punto " .. status.index .. "/" .. (status.total or "?")) or "")
                .. (status.paused and " · En pausa" or "")
                .. (status.reason and ("\n" .. status.reason) or "")
                .. (status.waiting and ("\n" .. tostring(status.waiting)) or "")
        end
        add("Activar / desactivar puntos", function() self.Waypoints:Toggle() end)
        add("Confirmar / omitir este punto", function() self.Waypoints:Skip() end)
        add("Reiniciar recorrido de puntos", function() self.Waypoints:Reset() end)
        add(type(status) == "table" and status.paused and "Reanudar puntos" or "Pausar puntos", function() self.Waypoints:Pause() end)
        add("Guardar mi posición", function() local ok, reason = self.Waypoints:Capture("Punto guardado"); if reason then self:Print(reason) end end)
        add("Guardar muelle / transporte", function() local ok, reason = self.Waypoints:Capture("Subir al transporte", "transport"); if reason then self:Print(reason) end end)
        local walk = self.Walking and self.Walking:GetStatus()
        if walk then text = "Camino por terreno: " .. (walk.text or "Esperando destino") .. "\n/rutaxp camino: activar o desactivar · /rutaxp recalcular: calcular de nuevo\n\n" .. text end
        text = text .. "\n\nLa ruta terrestre utiliza el terreno publicado de Forever cuando está disponible. Sin cobertura, la flecha avisa que la dirección es orientativa. Los accesos y transportes sin altura comprobada se confirman manualmente. Saltar un punto nunca completa una misión."
    end
    for i, b in ipairs(f.actions) do
        local action = actions[i]; b.action = action and action.action
        b:SetText(action and action.title or ""); b:SetShown(action ~= nil)
    end
    f.body:SetText(text)
    f.content:SetHeight(math.max(isDuo and 302 or 334, f.body:GetStringHeight() + 16))
end
function ns:UpdateDuoTracker()
    if not self.tracker or not self.Duo or not self.char then return end
    local guide, step = self:GetCurrent()
    if not guide then if self.duoTracker then self.duoTracker:Hide() end; return end
    local ctx = self.Duo:GetContext()
    if not self.duoTracker then
        self.duoTracker = button(self.tracker, "", 308, 8, -20, function()
            local stop = self.DuoJourney and self.DuoJourney:GetStopStatus()
            self:ToggleFeatures(stop and stop.active and "duo-stops" or "duo")
        end)
        self.duoTracker:SetScript("OnEnter", function(b)
            if not GameTooltip or not b.waitReason then return end
            GameTooltip:SetOwner(b, "ANCHOR_TOP")
            GameTooltip:AddLine("Estado del dúo", 1, .8, .45)
            GameTooltip:AddLine(b.waitReason, 1, 1, 1, true)
            GameTooltip:AddLine("Pulsa para ver las misiones de ambos y sincronizar de nuevo.", .7, .8, .9, true)
            GameTooltip:Show()
        end)
        self.duoTracker:SetScript("OnLeave", function() if GameTooltip then GameTooltip:Hide() end end)
    end
    self.trackerDuoVisible = ctx.enabled == true
    if not ctx.enabled then
        self.duoTracker:Hide()
        if self.LayoutTracker then self:LayoutTracker() end
        return
    end
    local text = not ctx.sameParty and "Dúo · invita a tu amigo"
        or not ctx.online and "Dúo · amigo desconectado"
        or not ctx.known and "Dúo · esperando sincronización"
        or ("Dúo · " .. (ctx.partnerReady and "amigo preparado" or "amigo en curso"))
    local waiting, waitReason, waitInfo
    if step and self.Duo.GetStepWaitStatus then
        waitInfo = self.Duo:GetStepWaitStatus(step)
        waiting, waitReason = waitInfo.waiting, waitInfo.reason
    elseif step then waiting, waitReason = self.Duo:ShouldWaitForStep(step) end
    if not waiting and step and self.DuoAuto then waiting, waitReason = self.DuoAuto:ShouldWaitForStep(step) end
    local autoView = self.DuoAuto and self.DuoAuto:GetSharedView()
    if autoView then text = autoView.following and ("Dúo auto · amigo " .. autoView.sharedCursor .. " · tú " .. autoView.ownCursor) or "Dúo auto · siguiendo la guía común" end
    if waiting then
        local verbs = {accept="falta aceptar",complete="misión en curso",turnin="falta entregar"}
        text = not ctx.known and "Dúo · sin datos del compañero"
            or waitInfo and (waitInfo.kind=="sync" or waitInfo.unknown) and "Dúo · sincronizando misiones"
            or ("Dúo · " .. (waitInfo and verbs[waitInfo.action] or "esperando al amigo"))
    end
    self.duoTracker.waitReason = waiting and waitReason or nil
    if ctx.differentZone then text = "Dúo · estáis en zonas distintas"
    elseif ctx.separated then text = "Dúo · amigo fuera de alcance" end
    if ctx.dead then text = "Dúo · amigo muerto o fantasma" end
    local stop = self.DuoJourney and self.DuoJourney:GetStopStatus()
    if stop and stop.active then text = stop.bothReady and "Dúo · ambos listos para seguir" or ("Dúo · parada: " .. (stop.title or "por acordar")) end
    self.duoTracker:SetText(text); self.duoTracker:Show()
    if self.LayoutTracker then self:LayoutTracker() end
end
function ns:GetDuoGoalSuffix(goal)
    if not goal or not self.Duo or not self.Duo.GetObjectiveProgress then return "" end
    local ctx = self.Duo:GetContext()
    if not (ctx.enabled and ctx.sameParty) then return "" end
    local id, index = goal.quest or goal.questID, goal.oi or goal.objective
    if not id or not index then return "" end
    local progress = self.Duo:GetObjectiveProgress(id, index)
    local other = progress and progress.partner
    if other and other.known and type(other.current) == "number" and type(other.total) == "number" then
        return string.format("Amigo: %d/%d", other.current, other.total)
    end
    if other and other.finished == true then return "Amigo: objetivo hecho" end
    return "Amigo: sin datos del contador"
end
