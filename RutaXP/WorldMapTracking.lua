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

local snapshot

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
    local previous = snapshot or {}
    local current = tracking.Read()
    if not tracking.OnChanged then return end
    for key in pairs(filters) do
        local old, new = previous[key], current[key]
        if (not old) ~= (not new) or (old and new and
            (old.active ~= new.active or old.name ~= new.name or old.texture ~= new.texture)) then
            tracking.OnChanged()
            return
        end
    end
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
