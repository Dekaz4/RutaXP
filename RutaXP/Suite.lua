local _, ns = ...
local modules = {}

-- Each native chunk receives the same private table as its siblings, just as
-- it would when WoW loads that addon's individual TOC.
function RutaXPModuleContext(name)
    if not modules[name] then modules[name] = {} end
    return name, modules[name]
end

function ns.GetEmbeddedModule(name)
    return modules[name]
end

local entries = {
    {key="guias", label="Guías de RestedXP", icon="INV_Misc_Book_09", module="RXPGuides"},
    {key="mapa", label="Mapa del mundo", icon="INV_Misc_Map_01"},
    {key="mazmorras", label="Diario de mazmorras", icon="INV_Misc_Book_11", module="ForeverDungeonJournal"},
    {key="talentos", label="Guía de talentos", icon="Ability_Marksmanship"},
}

local function open(entry)
    if entry.module and not modules[entry.module] then
        ns:Print("Para activar «" .. entry.label .. "», cierra WoW y ejecuta Instalar_Suite_RutaXP.exe en Interface/AddOns/RutaXP.")
        return
    end
    if entry.key == "talentos" then
        ns.Talents.TogglePanel(true)
    elseif entry.key == "mapa" then
        if not (WorldMapFrame and WorldMapFrame:IsShown()) then ToggleWorldMap() end
    elseif entry.key == "mazmorras" and ForeverDungeonJournal_Toggle then
        if not (ForeverDungeonJournalFrame and ForeverDungeonJournalFrame:IsShown()) then ForeverDungeonJournal_Toggle() end
    elseif entry.key == "guias" then
        local rxp = modules.RXPGuides
        if rxp.v2 and rxp.v2.ShowGuideSelectionMenu then rxp.v2:ShowGuideSelectionMenu()
        elseif rxp.RXPFrame and rxp.RXPFrame.DropDownMenu then rxp.RXPFrame.DropDownMenu()
        else ns:Print("RestedXP todavía está cargando su biblioteca de guías."); return end
    else
        ns:Print("El diario de mazmorras todavía está cargando."); return
    end
    if ns.suiteWindow then ns.suiteWindow:Hide() end
end

local function showMenu()
    if ns.suiteWindow then
        ns.suiteWindow:SetShown(not ns.suiteWindow:IsShown())
        return
    end
    local panel = CreateFrame("Frame", "RutaXPSuiteWindow", UIParent, "BasicFrameTemplateWithInset")
    panel:SetSize(300, 244)
    panel:SetPoint("CENTER")
    panel:SetFrameStrata("DIALOG")
    panel.TitleText:SetText("RutaXP")
    panel:EnableMouse(true)
    panel:SetMovable(true)
    panel:SetClampedToScreen(true)
    panel:RegisterForDrag("LeftButton")
    panel:SetScript("OnDragStart", panel.StartMoving)
    panel:SetScript("OnDragStop", panel.StopMovingOrSizing)
    for index, entry in ipairs(entries) do
        local button = CreateFrame("Button", nil, panel, "UIPanelButtonTemplate")
        button:SetPoint("TOPLEFT", 20, -36 - (index-1)*49)
        button:SetSize(260, 42)
        button:SetText(entry.label)
        local icon = button:CreateTexture(nil, "ARTWORK")
        icon:SetSize(26, 26)
        icon:SetPoint("LEFT", 10, 0)
        icon:SetTexture("Interface\\Icons\\" .. entry.icon)
        button:SetScript("OnClick", function() open(entry) end)
    end
    ns.suiteWindow = panel
    if UISpecialFrames then table.insert(UISpecialFrames, "RutaXPSuiteWindow") end
    panel:Show()
end

function ns:HandleSuiteCommand(command)
    if command == "" then showMenu(); return true end
    if command == "guías" then command = "guias" end
    for _, entry in ipairs(entries) do
        if command == entry.key then open(entry); return true end
    end
end

function RutaXPSuite_OnClick() showMenu() end
