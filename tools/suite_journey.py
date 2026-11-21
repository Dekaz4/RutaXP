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
            text = text.replace('math.floor(distance + 0.5) .. " yards"', 'FormatJourneyDistance(distance)')
        if script == "ui/HeaderStep.lua":
            text = text.replace('("Step: %s"):format(stepText)', 'FormatJourneyStep(stepText)')
        yield PREFIX + script, text.encode("utf8")
    for name in IMAGES:
        yield PREFIX + "images/" + name, read("images/" + name)
    yield PREFIX + "license.txt", read("license.txt")
