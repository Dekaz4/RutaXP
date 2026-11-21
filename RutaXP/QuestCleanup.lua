local _, ns = ...

local popupName = "RUTAXP_CONFIRM_QUEST_CLEANUP"
local preview, activeBatch

-- A quest abandoned and accepted again with the same ID was never reviewed in its new state.
if ns.events and ns.events.HookScript then
    ns.events:HookScript("OnEvent", function(_, event, id)
        local batch = activeBatch or preview
        if batch and event == "QUEST_REMOVED" then
            for _, row in ipairs(batch.rows) do
                if row.id == id then row.wasRemoved = true break end
            end
        end
    end)
end

local function supported()
    local log = C_QuestLog
    return log and type(log.GetSelectedQuest) == "function" and type(log.SetSelectedQuest) == "function"
        and type(log.SetAbandonQuest) == "function" and type(log.GetAbandonQuest) == "function"
        and type(log.GetAbandonQuestItems) == "function" and type(log.CanAbandonQuest) == "function"
        and type(log.IsOnQuest) == "function" and type(log.AbandonQuest) == "function"
        and C_Timer and type(C_Timer.After) == "function"
end

local function busy()
    if InCombatLockdown and InCombatLockdown() then return "Sal de combate para limpiar el diario." end
    if StaticPopup_Visible and (StaticPopup_Visible("ABANDON_QUEST") or StaticPopup_Visible("ABANDON_QUEST_WITH_ITEMS")) then
        return "Cierra la confirmación de abandono que tienes abierta en el diario."
    end
end

local function readPlan()
    local ok, plan, problem = pcall(ns.GetQuestCleanupPlan, ns)
    if ok and plan and plan.guideID and plan.step and type(plan.candidates) == "table"
        and type(plan.kept) == "table" and type(plan.review) == "table" then return plan end
    return nil, (ok and problem) or "No se ha podido comprobar la ruta y el diario."
end

local function finish(batch, message)
    activeBatch = nil
    if message then ns:Print(message) end
    ns:Print(("El diario confirma %d de %d abandonos."):format(batch.removed, #batch.rows))
end

local function abandonOne(row)
    local log, id = C_QuestLog, row.id
    if log.IsOnQuest(id) ~= true or log.CanAbandonQuest(id) ~= true then return false end
    local selected, previousTarget = log.GetSelectedQuest(), log.GetAbandonQuest()
    if type(selected) ~= "number" or type(previousTarget) ~= "number" then return false end

    -- The native abandon dialog also binds a quest ID and restores the user's selection.
    local ok, ready = pcall(function()
        log.SetSelectedQuest(id)
        if log.GetSelectedQuest() ~= id then return false end
        log.SetAbandonQuest()
        if log.GetAbandonQuest() ~= id then return false end
        local items = log.GetAbandonQuestItems()
        return items == nil or (type(items) == "table" and next(items) == nil)
    end)
    if not ready or not ok then
        -- Discard our staged request as well when preserving a quest with items.
        pcall(function()
            log.SetSelectedQuest(previousTarget)
            log.SetAbandonQuest()
        end)
    end
    log.SetSelectedQuest(selected)
    if not ok then error(ready) end
    if not ready or row.wasRemoved or log.GetAbandonQuest() ~= id then return false end
    log.AbandonQuest()
    return true
end

local function nextQuest(batch)
    while activeBatch == batch and batch.index <= #batch.rows do
        local row = batch.rows[batch.index]
        batch.index = batch.index + 1
        local reason = busy()
        if reason then return finish(batch, reason) end
        local plan, problem = readPlan()
        if not plan or plan.guideID ~= batch.guideID or plan.step ~= batch.step then
            return finish(batch, problem or "La ruta ha cambiado. Revisa de nuevo el diario.")
        end
        local eligible = false
        for _, candidate in ipairs(plan.candidates) do
            if candidate.id == row.id and candidate.title == row.title then eligible = true break end
        end
        if eligible and not row.wasRemoved then
            local ok, sent = pcall(abandonOne, row)
            if not ok then return finish(batch, "El cliente no ha permitido completar la limpieza del diario.") end
            if sent then
                -- Wait for server acknowledgement before touching the next quest. Never retry an abandon.
                local checks = 0
                local function poll()
                    if activeBatch ~= batch then return end
                    local readOK, present = pcall(C_QuestLog.IsOnQuest, row.id)
                    if readOK and present == false then
                        batch.removed = batch.removed + 1
                        return nextQuest(batch)
                    end
                    checks = checks + 1
                    if checks >= 25 then
                        return finish(batch, "El diario aún no ha confirmado el abandono de «" .. row.title .. "». Limpieza detenida.")
                    end
                    C_Timer.After(0.2, poll)
                end
                C_Timer.After(0.2, poll)
                return
            end
        end
        ns:Print("Se conserva «" .. row.title .. "» tras comprobar de nuevo el diario.")
    end
    if activeBatch == batch then finish(batch) end
end

local function confirm(_, batch)
    if not batch or preview ~= batch or activeBatch then return end
    preview, activeBatch = nil, batch
    nextQuest(batch)
end

local function printRows(heading, rows)
    if #rows == 0 then return end
    ns:Print(heading)
    for _, row in ipairs(rows) do ns:Print("«" .. row.title .. "» · " .. row.reason) end
end

function ns:ShowQuestCleanup(readOnly)
    if not readOnly then
        if activeBatch then return self:Print("Ya hay una limpieza del diario en curso.") end
        if not supported() or not StaticPopupDialogs or type(StaticPopup_Show) ~= "function" or type(StaticPopup_Visible) ~= "function" then
            return self:Print("Este cliente no permite comprobar y abandonar las misiones de forma segura.")
        end
        if preview and StaticPopup_Visible(popupName) then
            return self:Print("Revisa la lista antes de confirmar o cancelar la limpieza.")
        end
        local reason = busy()
        if reason then return self:Print(reason) end
    end
    local plan, problem = readPlan()
    if not plan then return self:Print(problem or "No se ha podido comprobar el diario.") end
    local kept, review = plan.kept, plan.review
    self:Print(("Diario revisado. %d para abandonar y %d para conservar (%d de revisión manual).")
        :format(#plan.candidates, #kept + #review, #review))
    if readOnly then
        printRows("Misiones que se conservan", kept)
        printRows("Misiones que se conservan pendientes de revisión manual", review)
    else
        self:Print("Consulta el motivo de cada misión con /rutaxp limpiar ver.")
    end
    printRows("Misiones propuestas para abandonar", plan.candidates)
    if readOnly or #plan.candidates == 0 then return end

    local batch = { guideID = plan.guideID, step = plan.step, rows = {}, removed = 0, index = 1 }
    local names = {}
    for _, candidate in ipairs(plan.candidates) do
        batch.rows[#batch.rows + 1] = {id = candidate.id, title = candidate.title}
        names[#names + 1] = candidate.title
    end
    local list = #names <= 6 and table.concat(names, "\n") or "Tienes la lista completa en el chat."
    if not StaticPopupDialogs[popupName] then
        StaticPopupDialogs[popupName] = {
            text = "¿Abandonar %s?\n\n%s\n\nPerderás su progreso. Si alguna ha cambiado o retiraría objetos, la conservarás.",
            button1 = "Abandonar", button2 = "Cancelar", timeout = 0, hideOnEscape = true,
            preferredIndex = 3, OnAccept = confirm,
            OnCancel = function(_, data) if preview == data then preview = nil end end,
        }
    end
    preview = batch
    local countText = #names == 1 and "esta misión" or ("estas %d misiones"):format(#names)
    if not StaticPopup_Show(popupName, countText, list, batch) then
        preview = nil
        self:Print("No se ha podido mostrar la confirmación de abandono.")
    end
end
