local addonName, ns = ...

-- SavedVariables are available on ADDON_LOADED, before the journal decides
-- whether to offer its first-login chooser on PLAYER_ENTERING_WORLD.
local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:SetScript("OnEvent", function(frame, _, name)
    if name ~= addonName then return end
    frame:UnregisterEvent("ADDON_LOADED")
    local journal = ns.GetEmbeddedModule("ForeverDungeonJournal")
    if not journal or not journal.SetJournalMode then return end
    local settings = ForeverDungeonJournalCharacterDB
    if settings and settings.rutaXPGamerModeApplied then return end
    journal.SetJournalMode("gamer")
    -- The journal creates its per-character table on first use.
    ForeverDungeonJournalCharacterDB.rutaXPGamerModeApplied = true
end)
