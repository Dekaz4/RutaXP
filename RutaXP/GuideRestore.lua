local _, ns = ...

-- The first-party engine reads the same activeGuide, progress and duo tables
-- that the suite retained while displaying RestedXP. Only the visibility
-- preference changed owners during that time.
local restoreFeatures = ns.RestoreFeatures
local placeFromJournal
function ns:RestoreFeatures()
    local char = self.char
    if not char.originalGuideDisplayRestored then
        if type(char.journeyDisplay) == "table" then
            char.tracker = char.journeyDisplay.hidden ~= true
        end
        char.originalGuideDisplayRestored = true
    end
    if restoreFeatures then restoreFeatures(self) end
    placeFromJournal = not self.guides[char.activeGuide]
end

local placeInGuide = ns.PlaceInGuide
function ns:PlaceInGuide(guide, state)
    if placeFromJournal and ns.WorldQuestFocus then
        placeFromJournal = false
        local cursor = ns.WorldQuestFocus.StartingStep(guide)
        if cursor and state.cursor == 1 then state.cursor = cursor end
    end
    return placeInGuide(self, guide, state)
end

function ns.OpenGuideLibrary()
    if ns.window then
        ns.window:Show()
        ns:RefreshUI()
    end
end

function ns.ToggleGuidePanel()
    if not ns.char then return end
    local journey = ns.GuideJourney
    if journey and journey:Available() then
        if journey:IsShown() then journey:Hide() else journey:Show() end
    else
        ns.char.tracker = not ns.char.tracker
        ns:RefreshUI()
    end
end

function ns.ActivateZoneGuide()
    if ns.char then ns:DetectZoneGuide(false) end
end
