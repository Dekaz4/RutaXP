local addonName, ns = ...
-- Updating happens through the same external setup used to install RutaXP.
local Updates = { fallbackVersion="0.7.5", url="https://github.com/Dekaz4/RutaXP/releases/latest",
    updaterURL="https://github.com/Dekaz4/RutaXP/releases/latest/download/Instalador_RutaXP.exe" }
ns.Updates = Updates
local function read(fn,...)
    if type(fn)~="function" then return nil end
    local ok,value=pcall(fn,...)
    if ok and not (issecretvalue and issecretvalue(value)) then return value end
end
function Updates:GetLocalVersion()
    local version=read(C_AddOns and C_AddOns.GetAddOnMetadata,addonName,"Version")
        or read(GetAddOnMetadata,addonName,"Version")
    return type(version)=="string" and #version<=48 and version:match("^[%w%.%+%-]+$") and version or self.fallbackVersion
end
function Updates:GetStatus()
    return {localVersion=self:GetLocalVersion(),url=self.url,updaterURL=self.updaterURL}
end
function Updates:Show()
    local text="RutaXP "..self:GetLocalVersion().."\n\nCierra WoW, ejecuta Instalador_RutaXP.exe y elige Instalar o Actualizar. "
        .."Después vuelve a abrir WoW. Usa el mismo setup en los dos ordenadores.\n\nCopia este enlace para descargarlo:"
    if StaticPopupDialogs and type(StaticPopup_Show)=="function" then
        StaticPopupDialogs.RUTAXP_UPDATE={text=text,button1="Cerrar",hasEditBox=true,editBoxWidth=370,maxLetters=512,
            timeout=0,whileDead=true,hideOnEscape=true,preferredIndex=3,
            OnShow=function(frame)
                local box=frame.editBox or frame.EditBox
                if box then read(box.SetText,box,self.updaterURL);read(box.SetFocus,box);read(box.HighlightText,box) end
            end}
        StaticPopup_Show("RUTAXP_UPDATE")
        return true
    end
    if ns.Print then ns:Print(text.." "..self.updaterURL) end
    return false
end
function Updates:Initialize()
    if self.initialized then return end
    self.initialized=true
    if ns.Print then ns:Print("RutaXP "..self:GetLocalVersion().." · /rutaxp actualizar muestra el enlace al setup.") end
end
