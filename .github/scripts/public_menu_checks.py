"""Exercise unmodified Windows installers in a disposable GitHub-hosted profile."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import suite_journey

EXPECTED = "1.2.8"
REPO = "Dekaz4/RutaXP"
VERSIONS = {"OpenMap": "v0.8.11", "ForeverDungeonJournal": "2.1.2", "Journey": "4.00.13"}
PROGRESS = b'RutaXPCharDB = { ["activeGuide"] = "qa", ["progress"] = { ["qa"] = { ["step"] = 17 } } }\n'


def original(version, directory):
    base = f"https://github.com/{REPO}/releases/download/v{version}"
    exe = directory / "Instalador_RutaXP.exe"
    req = Request(base + "/SHA256SUMS.txt", headers={"User-Agent": "RutaXP-release-QA"})
    with urlopen(req, timeout=40) as remote:
        sums = dict(row.strip().split("  ")[::-1] for row in remote.read().decode("utf-8-sig").splitlines() if row.strip())
    with urlopen(base + "/" + exe.name, timeout=90) as source, exe.open("xb") as dest:
        shutil.copyfileobj(source, dest)
    assert hashlib.sha256(exe.read_bytes()).hexdigest() == sums[exe.name]
    return exe


def previous(addon, character):
    addon.mkdir(parents=True)
    character.parent.mkdir(parents=True)
    character.write_bytes(PROGRESS)
    files = {"Bindings.xml": b'<Bindings />', "Leveling.lua": b"-- previous fixture"}
    toc = ["## Interface: 16001", "## Version: 1.0.2", "## X-RutaXP-Embedded: OpenMap, ForeverDungeonJournal",
           "## X-RutaXP-Journey-UI: " + VERSIONS["Journey"], "Leveling.lua"]
    for module in ("OpenMap", "ForeverDungeonJournal"):
        name = "Modules/" + module + "/Fixture.lua"
        toc.extend((f"## X-{module}-Title: {module}", f"## X-{module}-Version: {VERSIONS[module]}", name))
        files[name] = b"-- synthetic addon"
    for name in suite_journey.entries(None):
        toc.append(name)
        files[name] = ("setfenv(1, RutaXPJourneyEnvironment())\nregistered[" + json.dumps(name) + "] = true\n").encode()
    for image in suite_journey.IMAGES:
        files[suite_journey.PREFIX + "images/" + image] = b"synthetic artwork"
    files[suite_journey.PREFIX + "license.txt"] = b"Test fixture."
    files["RutaXP.toc"] = ("\n".join(toc) + "\n").encode()
    for name, data in files.items():
        obj = addon / name
        obj.parent.mkdir(parents=True, exist_ok=True)
        obj.write_bytes(data)
    (addon / "manifest.sha256").write_text("\n".join(f"{hashlib.sha256(data).hexdigest()}  {name}" for name,data in files.items()) + "\n", encoding="utf-8")


def verify(addon, character):
    from lupa.lua51 import LuaRuntime
    toc = (addon / "RutaXP.toc").read_text(encoding="utf-8-sig").splitlines()
    assert "## Version: " + EXPECTED in toc
    assert "## X-RutaXP-Journey-UI: " + VERSIONS["Journey"] in toc
    assert "DungeonPreparationUI.lua" in toc and (addon / "DungeonPreparationUI.lua").is_file()
    for module in ("OpenMap", "ForeverDungeonJournal"):
        assert f"## X-{module}-Version: {VERSIONS[module]}" in toc
    assert PROGRESS.rstrip() in character.read_bytes()
    assert all(f.exists() for f in (addon/"Leveling.lua",addon/"Media/Nav/quest-direction.tga"))
    runtime = LuaRuntime()
    runtime.execute("registered={}; function RutaXPJourneyEnvironment() return _G end")
    entries = [line.replace("\\","/") for line in toc if line.startswith("Modules/Journey/")]
    assert entries == suite_journey.entries(None)
    for line in entries:
        runtime.execute((addon / line).read_text(encoding="utf-8-sig"))
    assert runtime.globals().registered["Modules/Journey/ui/UI.lua"]
    assert runtime.globals().registered["Modules/Journey/lib/TomCats/Arrows.lua"]
    sys.path.insert(0,str(ROOT/"tests"))
    import test_dungeon_preparation_ui as icon
    icon.ADDON = addon
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(icon))
    assert result.wasSuccessful() and result.testsRun >= 1
    print("Verified installed minimap button, Journey UI and compass registration, pinned modules and saved progress.", flush=True)


def main(old):
    assert os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
    api = "https://api.github.com/repos/" + REPO + "/releases/latest"
    with urlopen(Request(api,headers={"User-Agent":"RutaXP-release-QA"}), timeout=40) as response:
        latest = json.load(response)
    assert latest["tag_name"] == "v"+EXPECTED, latest["tag_name"]
    with tempfile.TemporaryDirectory(prefix="rutaxp-press-1-",dir=os.environ["RUNNER_TEMP"]) as temp:
        work = Path(temp)
        client = work/"World of Warcraft/_forever_"
        addons = client/"Interface/AddOns"
        addon = addons/"RutaXP"
        character = client/"WTF/Account/SyntheticQA/Realm/Test/SavedVariables/RutaXP.lua"
        previous(addon,character)
        settings = Path(os.environ["LOCALAPPDATA"])/"RutaXP"
        assert not settings.exists(), "Expected a fresh hosted profile"
        settings.mkdir()
        (settings/"client.txt").write_text(str(addons), encoding="utf-8")
        exe = original(old,work)
        result = subprocess.run([str(exe)],input=b"1\n",cwd=work,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=540)
        print(result.stdout.decode("utf8","replace"),flush=True)
        assert result.returncode == 0 and ("Suite RutaXP " + EXPECTED).encode() in result.stdout
        assert (settings/"latest.txt").read_text(encoding="utf-8-sig").strip()==EXPECTED
        verify(addon,character)


if __name__=="__main__":
    main(sys.argv[1])
