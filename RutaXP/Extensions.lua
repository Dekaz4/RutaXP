local _, ns = ...
-- Central integration preserves the guide engine and Antigravity's UI.
function ns:RestoreFeatures()
    if self.Recovery and self.Recovery.RestoreSaved then self.Recovery:RestoreSaved() end
end
function ns:InitializeFeatures()
    for _, name in ipairs({ "Duo", "Recovery" }) do
        if self[name] and self[name].Initialize then self[name]:Initialize() end
    end
    if self.window and self.window.SetPoint then
        self.toolsButton = CreateFrame("Button", nil, self.window, "UIPanelButtonTemplate")
        self.toolsButton:SetSize(254, 24); self.toolsButton:SetPoint("TOPLEFT", 20, -532)
        self.toolsButton:SetText("Dúo y herramientas de ruta")
        self.toolsButton:SetScript("OnClick", function() self:ToggleFeatures() end)
    end
    self.featureDriver = CreateFrame("Frame")
    local elapsed = 0
    self.featureDriver:SetScript("OnUpdate", function(_, delta)
        elapsed = elapsed + delta
        if elapsed < 1 then return end
        local tick = elapsed; elapsed = 0
        if self.Session then self.Session:Tick(tick) end
        if self.DuoAuto then self.DuoAuto:Tick(tick) end
        if self.Duo then self.Duo:Tick(tick) end
        if self.DuoJourney then self.DuoJourney:Tick(tick) end
        if self.UpdateDuoAlerts then self:UpdateDuoAlerts() end
        if self.UpdateFeatures then self:UpdateFeatures() end
    end)
end
function ns:UpdateDuoAlerts()
    if not self.Duo or not self.Duo.GetAlerts then return end
    local context = self.Duo:GetContext()
    local partner = context.partnerName or self.Duo.partnerName
    if not context.enabled or not context.sameParty or not partner then self.duoAlertState = nil; return end
    if not self.duoAlertState or self.duoAlertState.partner ~= partner then self.duoAlertState = { partner = partner, active = {}, last = {} } end
    local state, present = self.duoAlertState, {}
    local now = GetTime and GetTime() or 0
    for _, alert in ipairs(self.Duo:GetAlerts()) do
        present[alert.kind] = true
        if not state.active[alert.kind] and (not state.last[alert.kind] or now - state.last[alert.kind] >= 60) then
            self:Print(alert.text)
            state.last[alert.kind] = now
        end
    end
    state.active = present
end
function ns:StartFeatureSession()
    -- Initial guide placement uses old quest history, not observed gameplay.
    -- Take the telemetry baseline only after the first real engine sync.
    if self.DuoAuto then self.DuoAuto:Initialize() end
    if self.Session then self.Session:Initialize() end
    if self.DuoJourney then self.DuoJourney:Initialize() end
end
local complete = ns.IsStepComplete
function ns:IsStepComplete(step, ...)
    if not complete(self, step, ...) then return false end
    if step and self.DuoAuto and self.DuoAuto:ShouldWaitForStep(step) then return false end
    if step and self.Duo and self.Duo:ShouldWaitForStep(step) then return false end
    return true
end
function ns:UseManualDuoMode(reason, force)
    if not self.DuoAuto or not self.DuoAuto.UseManualMode then return end
    local ctx = self.Duo and self.Duo:GetContext()
    if force or (ctx and ctx.sameParty) then self.DuoAuto:UseManualMode(reason) end
end
-- The shared display is separate from the real engine cursor. The advanced
-- player can help at an earlier step while their saved progress stays intact.
function ns:GetDisplayedCurrent()
    local guide, step, state = self:GetCurrent()
    local view = self.DuoAuto and self.DuoAuto:GetSharedView()
    if guide and state and type(view) == "table" and view.following and view.guideID == guide.id
        and type(view.sharedCursor) == "number" and guide.steps[view.sharedCursor] then
        return guide, guide.steps[view.sharedCursor], { cursor=view.sharedCursor, review=false,
            confirmed={}, skipped={}, duoFollowing=true, ownCursor=state.cursor }, view
    end
    return guide, step, state
end
function ns:GetFollowingGoalItems(view)
    if not view or not self.DuoPlanner or not self.DuoPlanner.GetSharedGoalItems then return nil end
    return self.DuoPlanner:GetSharedGoalItems(view.guideID, view.sharedCursor)
end
function ns:GetFollowingObjectives(items)
    local lines = {}
    for _, item in ipairs(items or {}) do
        lines[#lines + 1] = "• " .. (item.title or "Objetivo") .. (item.subtitle and (" · " .. item.subtitle) or "")
    end
    return #lines > 0 and table.concat(lines, "\n") or "Esperando datos recientes del paso del compañero."
end
local function followingGuard(self)
    local view = self.DuoAuto and self.DuoAuto:GetSharedView()
    if type(view) == "table" and view.following then
        self:Print("Estás acompañando el paso " .. view.sharedCursor .. " del amigo. Tu progreso propio se conserva; desactiva el modo automático para modificarlo manualmente.")
        return true
    end
end
for _, method in ipairs({ "Next", "Previous", "SkipStep", "ToggleGoalConfirm" }) do
    local original = ns[method]
    local methodName = method
    if original then ns[method] = function(self, ...)
        if followingGuard(self) then return end
        if methodName == "Previous" then self:UseManualDuoMode("Revisión manual solicitada") end
        return original(self, ...)
    end end
end
local selectGuide = ns.SelectGuide
function ns:SelectGuide(id, ...)
    if self.char and self.guides[id] and id ~= self.char.activeGuide then self:UseManualDuoMode("Guía elegida manualmente") end
    return selectGuide(self, id, ...)
end
local questAutomation = ns.HandleQuestAutomation
if questAutomation then
    function ns:HandleQuestAutomation(...)
        if self.DuoAuto and self.DuoAuto:ShouldPauseAutomation() then return end
        return questAutomation(self, ...)
    end
end
local refresh = ns.RefreshUI
function ns:RefreshUI(...)
    if refresh then refresh(self, ...) end
    if self.UpdateDuoTracker then self:UpdateDuoTracker() end
    if self.UpdateFeatures then self:UpdateFeatures() end
end
function ns:HandleFeatureCommand(command, rest)
    if command == "herramientas" then self:ToggleFeatures()
    elseif command == "sesion" or command == "sesión" then self:ToggleFeatures("session")
    elseif command == "sincronizar" then
        if self.Duo and self.Duo.Resynchronize then
            local ok, reason = self.Duo:Resynchronize()
            if reason then self:Print(reason) end
        end
        self:ToggleFeatures("duo")
    elseif command == "duo" or command == "dúo" then
        self:UseManualDuoMode("Modo dúo cambiado manualmente", true)
        self.Duo:SetEnabled(not self.Duo:GetContext().enabled); self:ToggleFeatures("duo")
    elseif command == "autoduo" or command == "autodúo" then
        self.DuoAuto:SetEnabled(not self.DuoAuto:GetStatus().enabled); self:ToggleFeatures("duo")
    elseif command == "esperar" then self:UseManualDuoMode("Espera cambiada manualmente", true); self.Duo:SetWait(not self.Duo:GetContext().wait); self:ToggleFeatures("duo")
    elseif command == "listo" then self.Duo:SetReady(not self.Duo.ready); self:ToggleFeatures("duo")
    elseif command == "comun" or command == "común" then
        if tonumber(rest) and self.DuoPlanner then self:UseManualDuoMode("Ruta común elegida manualmente"); local ok, reason = self.DuoPlanner:ApplyCommonRoute(tonumber(rest)); if not ok and reason then self:Print(reason) end end
        self:ToggleFeatures("duo-route")
    elseif command == "diferencias" or command == "diferencia" then
        if tonumber(rest) and self.DuoPlanner then self:UseManualDuoMode("Recogida señalada manualmente"); local ok, reason = self.DuoPlanner:FocusDifference(tonumber(rest)); if not ok and reason then self:Print(reason) end end
        self:ToggleFeatures("duo-differences")
    elseif command == "reunion" or command == "reunión" then
        local ok, reason
        if rest == "marcar" then ok, reason = self.Duo:SetMeetingPoint()
        elseif rest == "seguir" then ok, reason = self.Duo:FollowMeeting(true); self.char.arrow = true
        elseif rest == "borrar" then ok, reason = self.Duo:ClearMeeting()
        elseif rest == "cancelar" then ok, reason = self.Duo:FollowMeeting(false) end
        if ok == false and reason then self:Print(reason) end
        self:ToggleFeatures("duo-meeting")
    elseif command == "partida" then
        local ok, reason
        if rest == "guardar" then ok, reason = self.DuoJourney:SaveCheckpoint()
        elseif rest == "reanudar" then ok, reason = self.DuoJourney:ResumeCheckpoint() end
        if ok == false and reason then self:Print(reason) end
        self:ToggleFeatures("duo-checkpoint")
    elseif command == "paradas" or command == "parada" then
        local ok, reason
        if rest == "fin" then ok, reason = self.DuoJourney:EndStop()
        elseif tonumber(rest) then ok, reason = self.DuoJourney:BeginStop(tonumber(rest)) end
        if ok == false and reason then self:Print(reason) end
        self:ToggleFeatures("duo-stops")
    elseif command == "recuperar" then
        if rest ~= "" then local ok, reason = self.Recovery:Start(tonumber(rest)); if not ok and reason then self:Print(reason) end end
        self:ToggleFeatures("recovery")
    elseif command == "volver" then self.Recovery:Cancel(); self:RefreshUI()
    elseif command == "adaptar" then self:ToggleFeatures("adaptation")
    elseif command == "puntos" then self:ToggleFeatures("waypoints")
    elseif command == "camino" then
        local _, reason = self.Walking:Toggle(); if reason then self:Print(reason) end
        self:ToggleFeatures("waypoints")
    elseif command == "recalcular" then
        local _, reason = self.Walking:Retry(); if reason then self:Print(reason) end
    elseif command == "punto" then
        local ok, reason = self.Waypoints:Capture(rest ~= "" and rest or "Punto guardado")
        if reason then self:Print(reason) end
        self:ToggleFeatures("waypoints")
    else return false end
    return true
end
