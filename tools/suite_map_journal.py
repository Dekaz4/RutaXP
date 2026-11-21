"""Adapt native map and journal entry points when composing a local RutaXP installation."""


# Both modules keep their native Lua names, globals and saved variables.
# Only WoW's addon APIs and filesystem refer to the installed TOC owner.
_OPENMAP_FILES = {
    "core.lua": (
        ('(ADDON, "Version")', '("RutaXP", "X-OpenMap-Version")'),
        (r'"Interface\\AddOns\\" .. ADDON .. "\\Media\\"',
         r'"Interface\\AddOns\\RutaXP\\Modules\\OpenMap\\Media\\"'),
    ),
    "init.lua": (('event == "ADDON_LOADED" and name == ADDON',
                  'event == "ADDON_LOADED" and name == "RutaXP"'),),
    "map/worldmap.lua": (
        ('GetAddOnMemoryUsage(ns.name)', 'GetAddOnMemoryUsage("RutaXP")'),
        ('name = ns.L["Flight masters"], order = 32, get = get, set = set,',
         '''name = ns.L["Flight masters"], order = 32,
            get = function(info)
                local tracked = RutaXPWorldMapTracking.Get("flight")
                if tracked ~= nil then return tracked end
                return get(info)
            end,
            set = function(info, value)
                if RutaXPWorldMapTracking.Get("flight") ~= nil then
                    RutaXPWorldMapTracking.Set("flight", value)
                else set(info, value) end
            end,'''),
    ),
    "map/townsfolk.lua": (
        ("function mod:RefreshTownsfolk()\n\tif not S.IsBuilt() then return end",
         "function mod:RefreshTownsfolk()\n\tif not S.IsBuilt() then return end\n\tRutaXPWorldMapTracking.Refresh(ns)"),
        ("local on = self.db.townsfolk[k.key]",
         "local on = self.db.townsfolk[k.key] and RutaXPWorldMapTracking.Get(k.key) == nil"),
    ),
    "map/flights.lua": (
        ("local function RefreshLook()\n\tReadFound()", '''local function RefreshLook()
    local filter = RutaXPWorldMapTracking.Info("flight")
    local texture = filter and filter.texture
    local look = texture and {texture=texture} or NODE_LOOK
    ReadFound()'''),
        ("pin:SetShown(known or not mod.db.foundOnly)",
         '''if pin.trackingTexture ~= texture then
            S.Look(pin.Icon, look)
            S.Look(pin.Highlight, look)
            if pin.shadow then
                S.Look(pin.shadow, look)
                pin.shadow:SetVertexColor(0, 0, 0)
            end
            pin.trackingTexture = texture
        end
        pin:SetShown(RutaXPWorldMapTracking.Get("flight") or known or not mod.db.foundOnly)'''),
    ),
    "map/stitch.lua": (
        ("return places.hidden and places.world[key] or false",
         'return places.hidden and (places.world[key] or key:sub(1, 15) == "rutaxp_service_") or false'),
        ("local shown = set.on and not S.WorldPinsHidden(key)",
         '''local enabled = set.on
        if key == "flight" then
            local tracked = RutaXPWorldMapTracking.Get("flight")
            if tracked ~= nil then enabled, from = tracked, 0 end
        end
        local shown = enabled and not S.WorldPinsHidden(key)'''),
    ),
    "map/quests.lua": (
        ("function mod:RefreshQuests()\n", "function mod:RefreshQuests()\n"
         "\tRutaXPWorldMapTracking.RefreshQuestOffers(ns, self, map, Maps, EnterOffer)\n"),
        ("not q.isHidden and not q.inProgress",
         'not q.isHidden and not (RutaXPWorldMapTracking.Get("lowLevelQuests") ~= nil '
         'and RutaXPWorldMapTracking.IsLowOffer(q)) and not q.inProgress'),
        ('"CVAR_UPDATE", "QUESTLINE_UPDATE"', '"CVAR_UPDATE", "QUESTLINE_UPDATE", "QUEST_TURNED_IN", '
         '"QUEST_ACCEPTED", "QUEST_REMOVED", "PLAYER_LEVEL_UP"'),
        ('events:SetScript("OnEvent", function(_, event, cvar)\n',
         'events:SetScript("OnEvent", function(_, event, cvar)\n'
         '\t\tRutaXPWorldMapTracking.QuestOfferEvent(event, cvar)\n'),
    ),
    "map/panel.lua": (
        ("local function optRow(label, key, icon) local get, set = opt(key)",
         '''local function trackedRow(key, id, fallbackLabel, fallbackIcon)
        local info = RutaXPWorldMapTracking.Info(key)
        if info then
            return row(info.name or fallbackLabel, id, info.texture and {texture=info.texture} or fallbackIcon,
                function() return RutaXPWorldMapTracking.Get(key) end,
                function(value) RutaXPWorldMapTracking.Set(key, value) end)
        end
    end
    local function optRow(label, key, icon)
        if key == "flight" then
            local tracked = trackedRow(key, key, label, icon)
            if tracked then return tracked end
        end
        local get, set = opt(key)'''),
        ('rows[#rows + 1] = { folkDB and L["Townsfolk"] or L["Townsfolk (needs Questie)"] }',
         '''local tracked = {}
        for _, key in ipairs({"auctioneer", "banker", "battlemaster", "innkeeper", "mailbox",
                "classTrainer", "profTrainer", "repair", "stable", "lowLevelQuests"}) do
            local filter = trackedRow(key, "townsfolk." .. key, key)
            if filter then tracked[#tracked + 1] = filter end
        end
        if #tracked > 0 then
            rows[#rows + 1] = { _G.MINIMAP_TRACKING_NAME or L["Townsfolk"] }
            for _, filter in ipairs(tracked) do rows[#rows + 1] = filter end
        end
        if folkDB or #tracked == 0 then
            rows[#rows + 1] = { folkDB and L["Townsfolk"] or L["Townsfolk (needs Questie)"] }
        end'''),
        ('if not k.rare and k.key ~= "spirit" then',
         'if not k.rare and k.key ~= "spirit" and RutaXPWorldMapTracking.Get(k.key) == nil then'),
    ),
    "map/launcher.lua": (('tocname = ns.name,', 'tocname = "RutaXP",'),),
    # OpenMap fills missing settings only. An explicit existing "map" or
    # "journal" choice still wins over this default for the integrated suite.
    "map/dungeons.lua": (('d.entranceClick = "map"', 'd.entranceClick = "journal"'),),
}

_JOURNAL_FILES = {
    "core/journal.lua": (('("ForeverDungeonJournal", "Version")',
                          '("RutaXP", "X-ForeverDungeonJournal-Version")'),),
    "systems/versioncheck.lua": (('(ADDON_NAME, "Version")',
                                  '("RutaXP", "X-ForeverDungeonJournal-Version")'),),
    "systems/charactersnapshot.lua": (("metadata('ForeverDungeonJournal','Version')",
                                       "metadata('RutaXP','X-ForeverDungeonJournal-Version')"),),
    "systems/optionspanel.lua": (('pcall(getter, "ForeverDungeonJournal", "Version")',
                                  'pcall(getter, "RutaXP", "X-ForeverDungeonJournal-Version")'),),
    "systems/settingspanel.lua": (('pcall(getter, "ForeverDungeonJournal", "Version")',
                                   'pcall(getter, "RutaXP", "X-ForeverDungeonJournal-Version")'),),
    # WoW attributes a blocked group-finder action to the loaded suite.
    "systems/lfgbutton.lua": (('elseif addon == "ForeverDungeonJournal" then',
                               'elseif addon == "RutaXP" then'),),
}


def transform_lua(module, relpath, text):
    files = {"OpenMap": _OPENMAP_FILES, "ForeverDungeonJournal": _JOURNAL_FILES}.get(module, {})
    for original, embedded in files.get(str(relpath).replace("\\", "/").lower(), ()):
        text = text.replace(original, embedded)
    return text
