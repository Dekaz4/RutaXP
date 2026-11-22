-- OpenMap draws its own map. Read the same selections and textures used by
-- Blizzard’s minimap menu, including when the player is in a different zone.
local tracking = {}
RutaXPWorldMapTracking = tracking

local filters = {
    auctioneer = "Auctioneer",
    banker = "Banker",
    battlemaster = "Battlemaster",
    innkeeper = "Innkeeper",
    mailbox = "Mailbox",
    classTrainer = "TrainerClass",
    profTrainer = "TrainerProfession",
    repair = "Repair",
    stable = "Stablemaster",
    flight = "TaxiNode",
    lowLevelQuests = "TrivialQuests",
}

local snapshot, writingAll, filterButton, menuRefreshPending

function tracking.Read()
    local entries = {}
    local enum = Enum and Enum.MinimapTrackingFilter
    if enum and C_Minimap and C_Minimap.GetNumTrackingTypes
        and C_Minimap.GetTrackingFilter and C_Minimap.GetTrackingInfo then
        local byID = {}
        for key, field in pairs(filters) do
            if enum[field] then byID[enum[field]] = key end
        end
        for index = 1, C_Minimap.GetNumTrackingTypes() do
            local filter = C_Minimap.GetTrackingFilter(index)
            local key = filter and byID[filter.filterID]
            if key then
                local info = C_Minimap.GetTrackingInfo(index)
                if info and type(info.active) == "boolean" then
                    entries[key] = {active = info.active, name = info.name, texture = info.texture, index = index}
                end
            end
        end
    end
    snapshot = entries
    return entries
end

function tracking.Info(key)
    return (snapshot or tracking.Read())[key]
end

-- False means the player unchecked the filter. Nil means it is unavailable.
function tracking.Get(key)
    local entry = tracking.Info(key)
    if entry then return entry.active end
end

local function refresh()
    if writingAll then return end
    local previous = snapshot or {}
    local current = tracking.Read()
    for key in pairs(filters) do
        local old, new = previous[key], current[key]
        if (not old) ~= (not new) or (old and new and
            (old.active ~= new.active or old.name ~= new.name or old.texture ~= new.texture)) then
            if tracking.OnChanged then tracking.OnChanged() end
            if filterButton and filterButton:IsMenuOpen() and not menuRefreshPending then
                menuRefreshPending = true
                C_Timer.After(0, function()
                    menuRefreshPending = false
                    if filterButton:IsMenuOpen() then filterButton:GenerateMenu() end
                end)
            end
            return
        end
    end
end

local function clearFilters()
    refresh()
    -- SetTracking can synchronously fire MINIMAP_UPDATE_TRACKING. Apply the
    -- visible service/quest choices as one edit without touching tracking spells.
    writingAll = true
    local ok, err = pcall(function()
        for _, info in pairs(snapshot) do
            if info.active then C_Minimap.SetTracking(info.index, false) end
        end
    end)
    writingAll = false
    refresh()
    if not ok then error(err, 0) end
    return MenuResponse.Refresh
end

local function toggle(key)
    local active = tracking.Get(key)
    if active ~= nil then tracking.Set(key, not active) end
    return MenuResponse.Refresh
end

local function filterMenu(_, root)
    refresh()
    local choices = {}
    for key, info in pairs(snapshot) do choices[#choices+1] = {key=key, info=info} end
    table.sort(choices, function(a, b) return a.info.index < b.info.index end)
    if #choices == 0 then
        root:CreateTitle("El seguimiento aún no está disponible")
        return
    end
    root:CreateButton(UNCHECK_ALL or "Desmarcar todo", clearFilters)
    for _, choice in ipairs(choices) do
        local info = choice.info
        local row = root:CreateCheckbox(info.name, tracking.Get, toggle, choice.key)
        if info.texture then
            row:AddInitializer(function(button)
                local icon = button:AttachTexture()
                icon:SetSize(18,18)
                icon:SetPoint("RIGHT")
                icon:SetTexture(info.texture)
                button.fontString:SetPoint("RIGHT", icon, "LEFT", -4, 0)
                return button.fontString:GetUnboundedStringWidth()+62, 20
            end)
        end
    end
end

function tracking.AttachFilterButton(map)
    if filterButton or not (map.ScrollContainer and MenuUtil and AnchorUtil) then return end
    local view = map.ScrollContainer
    filterButton = CreateFrame("DropdownButton", "RutaXPWorldMapFiltersButton", map, "UIPanelButtonTemplate")
    filterButton:SetSize(76, 22)
    filterButton:SetPoint("TOPRIGHT", view, "TOPRIGHT", -10, -6)
    filterButton:SetFrameLevel(math.min(view:GetFrameLevel()+9300, 9950))
    filterButton:SetText("Filtros")
    filterButton:SetMenuAnchor(AnchorUtil.CreateAnchor("TOPRIGHT", filterButton, "BOTTOMRIGHT", 0, -2))
    filterButton:SetupMenu(filterMenu)
    filterButton:HookScript("OnHide", function(self) self:CloseMenu() end)
end

-- Called only when the player changes a filter in OpenMap. Spell and service
-- tracking entries share the same list, whose indices can change on SPELLS_CHANGED.
function tracking.Set(key, enabled)
    if type(enabled) ~= "boolean" or not (C_Minimap and C_Minimap.SetTracking) then return false end
    refresh()
    local entry = snapshot[key]
    if not entry then return false end
    if entry.active ~= enabled then
        C_Minimap.SetTracking(entry.index, enabled)
        refresh()
    end
    return true
end

local events = CreateFrame("Frame")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:RegisterEvent("SPELLS_CHANGED")
events:RegisterEvent("MINIMAP_UPDATE_TRACKING")
events:RegisterEvent("CVAR_UPDATE")
events:SetScript("OnEvent", function(_, event, cvar)
    if event ~= "CVAR_UPDATE" or cvar == "minimapTrackedInfov4" then refresh() end
end)
