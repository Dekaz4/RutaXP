"""Read only the Journey presentation used in the owner's personal package."""
from pathlib import Path


PREFIX = "Modules/Journey/"
SCRIPTS = (
    "lib/TomCats/FactoryTools.lua", "lib/TomCats/Arrows.lua", "Legacy.lua", "Constants.lua",
    "Tools.lua", "ui/UI.lua", "ui/Component.lua", "ui/GuideContainer.lua", "ui/Header.lua",
    "ui/HeaderTitle.lua", "ui/HeaderStep.lua", "ui/HeaderSettingsButton.lua",
    "ui/HeaderNextButton.lua", "ui/HeaderBackButton.lua", "ui/TaskGroupContainers.lua",
    "ui/TaskContainers.lua", "ui/TaskDetailContainers.lua",
)
IMAGES = (
    "JourneyLogoMed.png", "arrow-atlas.png", "arrow-spin-atlas.png", "Arrow-Mask.blp",
    "Arrow-Shadow.blp", "UI-Panel-Button-Up.blp", "UI-Panel-Button-Down.blp",
    "UI-Panel-Button-Background.blp",
    *(f"UI-SquareButton-{direction}-{state}.blp" for direction in ("Left", "Right")
      for state in ("Up", "Down", "Disabled")),
)


def entries(root):
    return [PREFIX + script for script in SCRIPTS]


def fix_arrow_vector(text):
    text = text.replace("GetWorldPosFromMapPos(mapID, { x = targetX, y = targetY })",
                        "GetWorldPosFromMapPos(mapID, CreateVector2D(targetX, targetY))")
    signature = "function ArrowMixin:SetTarget(targetX, targetY, mapID, disablePingAnimation)"
    if signature in text:
        # Forever resolves the return-value mixin in the caller's environment.
        # The host already projected this exact target in the global WoW context.
        projection = "local _, coordinate = C_Map.GetWorldPosFromMapPos(mapID, CreateVector2D(targetX, targetY))"
        if text.count(signature) != 1 or text.count(projection) != 1:
            raise ValueError("No se reconoce la función de posición de la brújula de Journey.")
        text = text.replace(signature, signature[:-1] + ", coordinate)")
        text = text.replace(projection, "-- The host supplies the verified world coordinate.")
    return text


def adapt_arrow(text):
    text = fix_arrow_vector(text)
    start = "local function SetArrowDirection(texture, rads)"
    screen = "local function CreateScreenArrow()"
    old_art = 'arrow:SetTexture(I["arrow-atlas.png"])'
    art = r'arrow:SetTexture([[Interface\AddOns\RutaXP\Media\Nav\quest-direction.tga]])'
    if start not in text and screen not in text:
        return text
    if art in text:
        return text  # The installed UI already uses the directional texture.
    if any(text.count(anchor) != 1 for anchor in (start, screen, old_art, "f:SetSize(128, 128)")):
        raise ValueError("No se reconoce el dibujo de la brújula de Journey.")
    begin, end = text.index(start), text.index(screen)
    if begin >= end:
        raise ValueError("La estructura de la brújula de Journey es incompatible.")
    # Keep Journey's HUD, distance, draggable frame and arrival animation.
    # Positive bearings turn from north towards west, as does SetRotation.
    text = text[:begin] + start + "\n    texture:SetRotation(rads)\nend\n\n" + text[end:]
    return text.replace(old_art, art).replace("f:SetSize(128, 128)", "f:SetSize(80, 80)")


def embedded_contents(read):
    """Update the already-adapted UI from an earlier RutaXP personal installation."""
    for script in SCRIPTS:
        name = PREFIX + script
        data = read(name)
        if script == "lib/TomCats/Arrows.lua":
            data = adapt_arrow(data.decode("utf-8-sig")).encode("utf8")
        yield name, data
    for asset in (*("images/" + image for image in IMAGES), "license.txt"):
        yield PREFIX + asset, read(PREFIX + asset)


def contents(root):
    root = Path(root).resolve(strict=True)

    def read(name):
        source = (root / name).resolve(strict=True)
        if not source.is_relative_to(root):
            raise ValueError(f"El archivo de Journey está fuera de la carpeta seleccionada: {name}")
        return source.read_bytes()

    for script in SCRIPTS:
        text = read(script).decode("utf-8-sig")
        # Each original component binds itself to a private Lua environment.
        # Only the presentation is loaded. RutaXP provides its guide/step model.
        loader = "select(2, ...).SetupGlobalFacade()"
        if text.count(loader) != 1:
            raise ValueError(f"Versión de la interfaz de Journey incompatible: {script}")
        if script == "Tools.lua":
            # Only the header's texture constructors live in this section.
            begin, end = "--[[ Texture Functions ]]", "--[[ Text Manipulation Functions ]]"
            if begin not in text or end not in text:
                raise ValueError("No se encontraron las funciones de texturas de Journey.")
            text = text.partition(loader)[0] + loader + "\n" + text.split(begin, 1)[1].split(end, 1)[0]
        text = text.replace(loader, "setfenv(1, RutaXPJourneyEnvironment())")
        if script == "ui/TaskDetailContainers.lua":
            text = text.replace("JGGameFontWhite", "RutaXPJourneyGameFontWhite")
        if script == "lib/TomCats/Arrows.lua":
            text = adapt_arrow(text)
            text = text.replace('math.floor(distance + 0.5) .. " yards"', 'FormatJourneyDistance(distance)')
        if script == "ui/HeaderStep.lua":
            text = text.replace('("Step: %s"):format(stepText)', 'FormatJourneyStep(stepText)')
        yield PREFIX + script, text.encode("utf8")
    for name in IMAGES:
        yield PREFIX + "images/" + name, read("images/" + name)
    yield PREFIX + "license.txt", read("license.txt")
