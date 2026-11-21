local addonName, ns = ...
ns.name = addonName

function ns:Print(text)
    if DEFAULT_CHAT_FRAME then
        DEFAULT_CHAT_FRAME:AddMessage("|cffffce72RutaXP|r · " .. text)
    end
end

function ns:IsQuestActive(id)
    return C_QuestLog and C_QuestLog.IsOnQuest and C_QuestLog.IsOnQuest(id) == true
end

function ns:IsQuestDelivered(id)
    local getFlag = C_QuestLog and C_QuestLog.IsQuestFlaggedCompleted or IsQuestFlaggedCompleted
    return getFlag and getFlag(id) == true
end

function ns:Command(message)
    local command, rest = (message or ""):match("^%s*(%S*)%s*(.-)%s*$")
    command = command:lower()
    if command == "talentos" or command == "talento" or command == "n" then
        self.Talents.TogglePanel()
    elseif self.HandleSuiteCommand and self:HandleSuiteCommand(command, rest) then
        return
    elseif command == "" then
        self.Talents.TogglePanel()
    else
        self:Print("Escribe /rutaxp para abrir el addon.")
    end
end

local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:SetScript("OnEvent", function(frame, _, name)
    if name ~= addonName then return end
    RutaXPCharDB = type(RutaXPCharDB) == "table" and RutaXPCharDB or {}
    RutaXPDB = type(RutaXPDB) == "table" and RutaXPDB or {}
    ns.char, ns.db = RutaXPCharDB, RutaXPDB
    ns.initialized = true
    frame:UnregisterEvent("ADDON_LOADED")
end)

SLASH_RUTAXP1 = "/rutaxp"
SLASH_RUTAXP2 = "/rutas"
SlashCmdList.RUTAXP = function(message) ns:Command(message) end
