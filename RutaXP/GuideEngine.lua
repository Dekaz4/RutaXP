local _, ns = ...
local engine = {}
ns.GuideEngine = engine

local function runtime()
    return ns.GetEmbeddedModule("RXPGuides")
end

local function official(guide)
    return guide and guide.key and guide.group and guide.name and not
        (guide.imported or guide.internal or guide.disabled or guide.chapter or guide.empty)
end

function engine.Ready()
    local r = runtime()
    return r and r.addonLoaded and r.guides and r.settings.profile and
        (not r.embeddedGuides or #r.embeddedGuides == 0) and true or false
end

function engine.Catalog()
    local result, seen, r = {}, {}, runtime()
    if not engine.Ready() then return result end
    for _, guide in pairs(r.guides) do
        if official(guide) and not seen[guide.key] and r.IsGuideActive(guide) and
            r.IsGuideSelectable(guide, nil, true) then
            result[#result + 1], seen[guide.key] = guide, true
        end
    end
    table.sort(result, function(a, b) return a.key < b.key end)
    return result
end

function engine.Current()
    local r = runtime()
    local g = r and r.currentGuide
    if official(g) then return g, r.GetGuideProgress(g) end
end

function engine.MapID(value)
    local r = runtime()
    return tonumber(value) or (value and r and r.GetMapId and r.GetMapId(value))
end

local function entry(r, g)
    if not engine.Ready() or not official(g) then return end
    local registered = r.GetGuideTable(g.group, g.name)
    if official(registered) and registered.key == g.key and r.IsGuideActive(registered) and
        r.IsGuideSelectable(registered, nil, true) then return registered end
end

function engine.Preview(guide)
    local r = runtime()
    local g = entry(r, guide)
    if not g then return end
    local current = engine.Current()
    if current and current.key == g.key then return current end
    -- The lazy parser also sets these working fields while reading a header.
    -- Looking at another zone must not rename the guide currently being used.
    local group, name = r.currentGuideGroup, r.currentGuideName
    g = g.steps and g or r:FetchGuide(g)
    -- Some official chapters contain #include references to other zones.
    -- Project the same steps the player would actually get upon selection.
    if official(g) and g.steps then g = r.ProcessGuideTable(g) end
    r.currentGuideGroup, r.currentGuideName = group, name
    if official(g) then return g end
end

function engine.SetStep(n)
    local guide = engine.Current()
    if not guide or type(n) ~= "number" or n % 1 ~= 0 or n < 1 or n > #guide.steps then return false end
    runtime().SetStep(n)
    return true
end

function engine.Advance(delta)
    local guide, n = engine.Current()
    if not guide or (delta ~= 1 and delta ~= -1) or n + delta < 1 then return false end
    -- One past the end invokes RestedXP's own next-chapter conditions.
    runtime().SetStep(n + delta)
    return true
end

function engine.Select(guide, n)
    local r = runtime()
    local g = entry(r, guide)
    if not g then return false end
    if not r.currentGuide or r.currentGuide.key ~= g.key then r:LoadGuide(g) end
    local active = engine.Current()
    if not active or active.key ~= g.key then return false end
    if n then return engine.SetStep(n) end
    return true
end

function engine.Clear()
    local r = runtime()
    if not engine.Ready() then return false end
    if r.currentGuide and not r.currentGuide.empty then r:LoadGuide(r.emptyGuide) end
    return not engine.Current()
end

local savedGroup, savedName, savedStep
function engine.SavedSelection()
    return savedGroup, savedName, savedStep
end

function engine.ActiveSteps()
    local r = runtime()
    return engine.Current() and r.RXPFrame.activeSteps or {}
end

local function renderedText(r, e)
    -- The engine resolves quest/NPC names and live objective counts on the
    -- bound row. Prefer what it rendered (also preserves the quest hyperlink).
    local fs = e.frame and e.frame.element == e and e.frame.text
    local text = fs and fs.GetText and fs:GetText()
    if type(text) == "string" and text:find("%S") then return text end
    text = e.text
    if type(text) ~= "string" or not text:find("%S") then text = e.tooltipText or e.rawtext end
    if type(text) ~= "string" or not text:find("%S") then return end
    if r.locale and r.locale.Get then text = r.locale.Get(text) end
    return r.ReplaceNpcIds(text, e)
end

function engine.Tasks()
    local out, r = {}, runtime()
    for _, step in ipairs(engine.ActiveSteps()) do
        if step.active and not step.hidewindow and not step.hidetip then
            local before = #out
            for _, e in ipairs(step.elements or {}) do
                local text = renderedText(r, e)
                if text then
                    out[#out + 1] = {text=text, element=e, step=step.index,
                        checked=not not (e.completed or e.skip), manual=not (e.textOnly or e.optional or e.completed)}
                end
            end
            if #out == before and step.text and step.text ~= "" then
                out[#out+1] = {text=step.text, step=step.index, checked=not not step.completed, manual=false}
            end
        end
    end
    return out
end

function engine.ToggleTask(task)
    local e, r = task and task.element, runtime()
    if not e or not task.manual or e.optional or e.textOnly or e.completed then return false end
    for _, step in ipairs(engine.ActiveSteps()) do
        if step.index == task.step and step.active then
            for _, live in ipairs(step.elements or {}) do
                if live == e then
                    -- Delegate to the same handler as a manual checkbox click
                    -- in the stock guide, including OnComplete and map refresh.
                    local row = {element=e}
                    r.ActiveStepElementPostClick({GetParent=function() return row end,
                        GetChecked=function() return not e.skip end})
                    return true
                end
            end
        end
    end
    return false
end

function engine.Waypoint()
    local r = runtime()
    local e = r and r.rutaXPWaypoint
    if not e or e.hidden or not engine.Current() or (e.step and not e.step.active) then return end
    local id, x, y = engine.MapID(e.zone or e.mapID), tonumber(e.x), tonumber(e.y)
    if x and y and id then
        x, y = x / 100, y / 100
    elseif e.wx and e.wy and e.instance and C_Map then
        id = C_Map.GetBestMapForUnit("player")
        local hbd = LibStub("HereBeDragons-2.0", true)
        if not id or not hbd then return end
        x, y = hbd:GetZoneCoordinatesFromWorldInstance(e.wx, e.wy, e.instance, id)
    else
        return
    end
    if x and y and x >= 0 and x <= 1 and y >= 0 and y <= 1 then
        return id, x, y, e.title or (e.step and (e.step.arrowtext or e.step.title))
    end
end

local useJourney, clip, parked, originalClick = false, nil, {}, nil
local function park(frame)
    if not frame or frame:GetParent() == clip then return end
    parked[frame] = frame:GetParent()
    frame:SetParent(clip)
end

local function toggle() ns.ToggleGuidePanel() end
local function library() ns.OpenGuideLibrary() end
local function click(_, button)
    if button == "RightButton" then library() else toggle() end
end
local originalToggle, originalLibrary
local function present()
    local r = runtime()
    if not r or not r.addonLoaded or InCombatLockdown() then return end
    local ldb = LibStub("LibDataBroker-1.1", true)
    local broker = ldb and ldb:GetDataObjectByName("RXPGuides")
    if useJourney then
        if not clip then
            -- Keep the native frames visible to the scheduler. Clipping their
            -- entire subtree outside the screen also removes their hit areas.
            clip = CreateFrame("Frame", nil, UIParent)
            clip:SetSize(1, 1)
            clip:SetPoint("BOTTOMLEFT", UIParent, "TOPRIGHT", 4096, 4096)
            clip:SetAlpha(0)
            clip:SetClipsChildren(true)
        end
        r.rutaXPJourney = true
        park(r.RXPFrame)
        park(r.arrowFrame)
        local state = r.v2 and r.v2.state
        if state then
            park(state.guideWindow and state.guideWindow.frame)
            local player = state.player and state.player[r.player.name]
            park(player and player.activeStepFrame and player.activeStepFrame.frame)
        end
        -- Standby/automation gates use this transient flag and the legacy
        -- parent. Keep both active, regardless of the old window preference.
        r.RXPFrame:Show()
        r.isHidden = false
        if r.currentGuide and r.currentGuide.imported then r:LoadGuide(r.emptyGuide) end
        if broker and broker.OnClick ~= click then originalClick, broker.OnClick = broker.OnClick, click end
        if r.settings.ToggleActive ~= toggle then originalToggle, r.settings.ToggleActive = r.settings.ToggleActive, toggle end
        if r.v2 and r.v2.ShowGuideSelectionMenu ~= library then
            originalLibrary, r.v2.ShowGuideSelectionMenu = r.v2.ShowGuideSelectionMenu, library
        end
    elseif r.rutaXPJourney then
        r.rutaXPJourney = nil
        for frame, parent in pairs(parked) do
            if frame:GetParent() == clip then frame:SetParent(parent) end
            parked[frame] = nil
        end
        if broker and broker.OnClick == click then broker.OnClick = originalClick end
        if r.settings.ToggleActive == toggle then r.settings.ToggleActive = originalToggle end
        if r.v2 and r.v2.ShowGuideSelectionMenu == library then r.v2.ShowGuideSelectionMenu = originalLibrary end
        r.isHidden = not r.settings.profile.showEnabled or r.settings.profile.hideGuideWindow
        r.RXPFrame:SetShown(not r.isHidden)
    end
end

function engine.PresentWithJourney(on)
    useJourney = not not on
    present()
end

local listeners, pending, attached = {}, false, false
function engine.Subscribe(fn)
    listeners[fn] = true
end

local function notify()
    if pending then return end
    pending = true
    C_Timer.After(0, function()
        pending = false
        if useJourney then present() end
        for fn in pairs(listeners) do fn() end
    end)
end

local function attach()
    local r = runtime()
    if attached or not (r and r.SetStep and r.UpdateMap and r.RegisterMessage) then return end
    attached = true
    for _, message in ipairs({"RXP_GUIDE_LOADED", "RXPGuidesV2_UpdateActiveSteps",
        "RXPGuidesV2_GuideStepsChanged", "RXPGuidesV2_QuestDataLoaded", "RXPGuidesV2_GuideWindowRefresh"}) do
        r:RegisterMessage(message, notify)
    end
    hooksecurefunc(r, "SetStep", notify)
    hooksecurefunc(r, "LoadEmbeddedGuides", notify)
    local lastTarget
    local function targetChanged()
        if r.rutaXPWaypoint ~= lastTarget then lastTarget = r.rutaXPWaypoint; notify() end
    end
    hooksecurefunc(r, "UpdateMap", targetChanged)
    hooksecurefunc(r, "UpdateGotoSteps", targetChanged)
end

local events = CreateFrame("Frame")
for _, e in ipairs({"ADDON_LOADED", "PLAYER_LOGIN", "PLAYER_ENTERING_WORLD", "PLAYER_REGEN_ENABLED",
    "QUEST_LOG_UPDATE", "ZONE_CHANGED_NEW_AREA", "PLAYER_LEVEL_UP"}) do events:RegisterEvent(e) end
events:SetScript("OnEvent", function(_, event, name)
    if event == "ADDON_LOADED" then
        if name ~= "RutaXP" then return end
        local c = runtime() and RXPCData
        if c and c.currentGuideName and c.currentGuideName ~= "" and c.currentGuideGroup ~= "" then
            savedGroup, savedName, savedStep = c.currentGuideGroup, c.currentGuideName, tonumber(c.currentStep)
        end
    end
    attach()
    if event == "PLAYER_REGEN_ENABLED" then present() end
    notify()
end)
