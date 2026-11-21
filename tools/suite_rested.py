"""Prepare the official RestedXP files for the installed Forever build."""

import hashlib
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen
from zipfile import ZipFile


VERSION = "v4.11.36-17-gcbe05e3"
COMMIT = "cbe05e351e083108d08b35908347952fb0eaf06e"
ARCHIVE_HASH = "6fc7236044bee4b65e5f7f77b3a84c4fe1fccb6119cfd23a435ddd74f22ccfa1"
SAVED_VARIABLE_RENAMES = {"RXPDB": "RutaXPRestedDB", "RXPString": "RutaXPRestedString"}
_SAVED_VARIABLE = re.compile(r"\b(?:RXPDB|RXPString)\b")
_RUNTIME_DIRS = {"DB", "Guides", "lang", "libs", "locale", "Textures", "UI"}


def _official_archive(cache):
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"RXPGuides-{COMMIT}.zip"
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == ARCHIVE_HASH:
        return path
    url = f"https://codeload.github.com/RestedXP/RXPGuides/zip/{COMMIT}"
    req = Request(url, headers={"User-Agent": "RutaXP-addon-builder"})
    with tempfile.NamedTemporaryFile(dir=cache, suffix=".part", delete=False) as stream:
        temp = Path(stream.name)
    try:
        with urlopen(req, timeout=45) as response, temp.open("wb") as output:
            shutil.copyfileobj(response, output)
        if hashlib.sha256(temp.read_bytes()).hexdigest() != ARCHIVE_HASH:
            raise ValueError("La copia de RestedXP no coincide con la versión oficial verificada.")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return path


def prepare_official_source(installed: Path | None, cache: Path, staging: Path | None = None) -> Path:
    """Read only the local version. Materialize stock content in an empty directory."""
    if installed is not None:
        toc = (Path(installed) / "RXPGuides.toc").read_text(encoding="utf-8-sig")
        if not re.search(r"^## Version:\s*" + re.escape(VERSION) + r"\s*$", toc, re.MULTILINE):
            raise ValueError(f"El constructor requiere la versión oficial verificada de RestedXP {VERSION}.")
    cache = Path(cache)
    archive = _official_archive(cache)
    if staging is None:
        staging = Path(tempfile.mkdtemp(prefix="rested-oficial-", dir=cache))
    else:
        staging = Path(staging)
        staging.mkdir(parents=True, exist_ok=True)
        if any(staging.iterdir()):
            raise ValueError("La carpeta temporal de RestedXP debe estar vacía.")
    with ZipFile(archive) as package:
        for entry in package.infolist():
            if entry.is_dir():
                continue
            archive_parts = PurePosixPath(entry.filename).parts
            if archive_parts[0] != f"RXPGuides-{COMMIT}" or ".." in archive_parts:
                raise ValueError("Ruta no válida en los archivos oficiales de RestedXP.")
            relative = PurePosixPath(*archive_parts[1:])
            if relative.parts[0] not in _RUNTIME_DIRS and not (
                len(relative.parts) == 1
                and (relative.suffix.lower() in {".toc", ".lua", ".xml"} or relative.name == "LICENSE")
            ):
                continue
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative.name == "RXPGuides.toc":
                # The official packager fills this tag when making the release.
                path.write_bytes(package.read(entry).replace(b"@project-version@", VERSION.encode()))
            else:
                with package.open(entry) as src, path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    return staging


# The loader passes "RXPGuides" to every module chunk. AceLocale, AceAddon,
# guide registration and third-party integrations use that name as a stable key.
# Only asset lookup, TOC metadata and the client load event use the suite path.
_ASSET_PREFIX = re.compile(
    r"""(Interface)(/|\\\\)(AddOns)\2(["'])\s*\.\.\s*addonName\b""", re.IGNORECASE
)


def transform_lua(module, relpath, text):
    if module != "RXPGuides":
        return text
    path = str(relpath).replace("\\", "/").lower()
    # The embedded guides, imports and their localized versions remain upstream
    # data. They do not use the physical addon folder to display textures.
    if path.startswith(("guides/", "lang/", "db/", "locale/", "libs/")):
        return text

    def asset(match):
        separator = match[2]
        path = separator.join((match[1], match[3], "RutaXP", "Modules", "RXPGuides"))
        return path + match[4]

    text = _ASSET_PREFIX.sub(asset, text)
    # The native import payload/cache belongs to the original addon. Keep
    # this installation's database and any future explicit imports separate.
    text = _SAVED_VARIABLE.sub(lambda hit: SAVED_VARIABLE_RENAMES[hit.group()], text)
    if path == "rxpguides.lua":
        action = "function addon:QuestAutomation(event, arg1, arg2, arg3)"
        text = text.replace(action, action + "\n    if addon.rutaXPManualQuesting and addon.rutaXPManualQuesting() then return end")
        for field in ("Version", "Title"):
            text = text.replace(
                f'GetAddOnMetadata(addonName, "{field}")',
                f'GetAddOnMetadata("RutaXP", "X-RXPGuides-{field}")',
            )
        # The Journey tracker has its own visibility setting. Its active guide
        # still needs the engine when RestedXP's original window was hidden.
        text = text.replace("if profile.standbyMode and not profile.showEnabled then",
                            "if profile.standbyMode and not profile.showEnabled and not addon.rutaXPJourney then")
        # Journey's zone detection and library own first login for this build.
        # Keep the original configurator available for explicit settings changes.
        text = text.replace("addon.ui.v2.configurator:Open(true)",
                            'if not C_AddOns.GetAddOnMetadata("RutaXP", "X-RutaXP-Journey-UI") then '
                            'addon.ui.v2.configurator:Open(true) end')
    elif path == "communications.lua":
        action = "function addon.comms.grouping:ShareQuest(questId)"
        text = text.replace(action, action + "\n    if addon.rutaXPManualQuesting and addon.rutaXPManualQuesting() then return end")
    elif path == "map.lua":
        # Forever's arrow keeps its *last* element after hiding. Expose the
        # chosen waypoint independently of whether its original frame is shown.
        text = text.replace("local function updateArrowData()",
                            "local function updateArrowData()\n    addon.rutaXPWaypoint = nil")
        text = text.replace("af.dist, af.orientation, af.element = 0, 0, element",
                            "addon.rutaXPWaypoint = element\n            af.dist, af.orientation, af.element = 0, 0, element")
        text = text.replace("if #addon.activeWaypoints == 0 and not forceArrowUpdate then",
                            "if #addon.activeWaypoints == 0 and not forceArrowUpdate then\n        addon.rutaXPWaypoint = nil")
    elif path == "questlog.lua":
        text = text.replace('arg1 == addonName then', 'arg1 == "RutaXP" then')
    elif path == "settingspanel.lua":
        # Other minimap managers look up the physical addon's metadata here;
        # the actual LibDataBroker and LibDBIcon identifiers must stay RXPGuides.
        text = text.replace('tocname = addonName,', 'tocname = "RutaXP",')
        text = text.replace("enableTalentGuides = true,", "enableTalentGuides = false,")
    return text
