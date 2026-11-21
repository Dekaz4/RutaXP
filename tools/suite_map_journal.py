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
    "map/worldmap.lua": (('GetAddOnMemoryUsage(ns.name)', 'GetAddOnMemoryUsage("RutaXP")'),),
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
