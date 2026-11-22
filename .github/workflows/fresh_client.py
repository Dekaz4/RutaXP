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
from zipfile import ZipFile
import winreg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import suite_journey

EXPECTED = "1.2.10"
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


def verify_lfg(addons):
    from lupa.lua51 import LuaRuntime
    published = json.loads((Path(__file__).parent/"official_lfg_hashes.json").read_text(encoding="utf8"))
    for path, expected in published.items():
        actual = addons/path
        assert actual.is_file() and hashlib.sha256(actual.read_bytes()).hexdigest() == expected, path
    es = addons/"LFGForeverLanguageSpanish"
    toc = (es/"LFGForeverLanguageSpanish.toc").read_text(encoding="utf-8-sig")
    assert "## Dependencies: LFGForever" in toc and "## X-LFGForever-LanguagePack: 1" in toc
    lua = LuaRuntime()
    lua.execute("""
        state = {}
        pack = {}
        C_AddOns = {
            GetNumAddOns = function() return 2 end,
            GetAddOnInfo = function(i) return i==1 and "LFGForever" or "LFGForeverLanguageSpanish" end,
            GetAddOnMetadata = function(n,k) if n=="LFGForeverLanguageSpanish" and k=="X-LFGForever-LanguagePack" then return "1" end end,
            LoadAddOn = function(n) assert(n=="LFGForeverLanguageSpanish"); (assert(loadstring(spanish)))(n,pack); return true end,
            GetAddOnLocalTable = function(n) assert(n=="LFGForeverLanguageSpanish"); return pack end,
        }
    """)
    lua.globals().spanish=(es/"Spanish.lua").read_text(encoding="utf-8-sig")
    lua.globals().core=(addons/"LFGForever/core/locale.lua").read_text(encoding="utf-8-sig")
    lua.execute('(assert(loadstring(core)))("LFGForever", state)')
    assert lua.globals().state.L.TAB_GROUP_BROWSER == "Buscador de grupo"
    print(f"Verified {len(published)} installed LFG files against the author's original runtime and loaded its real Spanish UI.", flush=True)




def verify_native(addon, progress, cache, work, locked):
    import build_personal_suite as composer
    import official_sources
    toc = (addon/"RutaXP.toc").read_text(encoding="utf-8-sig").splitlines()
    assert "## Version: " + EXPECTED in toc
    assert "## X-RutaXP-Journey-UI: " + VERSIONS["Journey"] in toc
    assert progress.read_bytes() == PROGRESS
    verify_lfg(addon.parent)
    expected_journal_tree = "383e2c9b055133810f7ca8b30d54181339b02c70210c08b6a5b05fa387a42cdd"
    upstream = {
        "OpenMap": "ef561c3026a14024dab9ac02afc4fd02a0ea7f8e6d298d6a68fc23c19d57b53b",
        "Journey":"ac03e7a1e02ba8c029d42e5c8da206f5c12d5db01ee02aaecc056293ac68281d",
    }
    for name in VERSIONS:
        source=official_sources.SOURCES[name]
        archive=cache/source.filename
        if locked and name=="ForeverDungeonJournal":
            # Keep an independent copy for comparing the installed, transformed files.
            assert archive.read_bytes()==b"existing file in use", "Replaced the protected entry"
            archive=work/source.filename
            address="https://edge.forgecdn.net/files/9730/326/DungeonJournal2.1.2.zip"
            with urlopen(Request(address,headers={"User-Agent":"RutaXP-release-QA"}),timeout=60) as response, archive.open("xb") as out:
                shutil.copyfileobj(response,out)
        assert archive.is_file(), f"{archive.name} missing in fresh download cache"
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        with ZipFile(archive) as z:
            files = sorted((m for m in z.infolist() if m.filename.startswith(name+"/") and not m.is_dir()), key=lambda e:e.filename)
            if name=="ForeverDungeonJournal":
                manifest=hashlib.sha256()
                for m in files:
                    manifest.update((hashlib.sha256(z.read(m)).hexdigest()+"  "+m.filename[len(name)+1:]+"\n").encode("utf8"))
                assert manifest.hexdigest()==expected_journal_tree, (digest,manifest.hexdigest())
            else:
                assert digest==upstream[name], (name,digest)
            for m in files:
                if "/../" in m.filename or "\\" in m.filename or ":" in m.filename:
                    raise ValueError(m.filename)
                z.extract(m,work/"upstream")
        folder=work/"upstream"/name
        if name=="Journey":
            expected=suite_journey.contents(folder)
        else:
            assert "## X-"+name+"-Version: "+VERSIONS[name] in toc
            expected=composer.Module(name,folder).contents()
        count=0
        for rel, data in expected:
            assert (addon/rel).read_bytes()==data, rel
            count+=1
        assert count>10, name
        print(f"{name} download SHA256 {digest}; checked {count} installed files against the original distribution.",flush=True)

def main(old,locked=False):
    assert os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("RUNNER_ENVIRONMENT")=="github-hosted"
    with tempfile.TemporaryDirectory(prefix="rutaxp-fresh-",dir=os.environ["RUNNER_TEMP"]) as temp:
        work=Path(temp)
        client=work/"World of Warcraft/_forever_"
        addons=client/"Interface/AddOns"
        addons.mkdir(parents=True)
        assert list(addons.iterdir())==[]
        character=client/"WTF/Account/SyntheticQA/Realm/Test/SavedVariables/RutaXP.lua"
        character.parent.mkdir(parents=True)
        character.write_bytes(PROGRESS)
        profile=(work/"local-app-data") if old=="build" else Path(os.environ["LOCALAPPDATA"])
        profile.mkdir(exist_ok=True)
        env=dict(os.environ, LOCALAPPDATA=str(profile))
        settings=profile/"RutaXP"
        assert not settings.exists(), "Expected a clean Windows profile"
        settings.mkdir()
        if locked:
            blocker=settings/"Suite/Descargas/DungeonJournal2.1.2.zip"
            blocker.parent.mkdir(parents=True)
            blocker.write_bytes(b"existing file in use")
            blocker.chmod(0o444)
        (settings/"client.txt").write_text(str(addons),encoding="utf8")
        if old=="build":
            command=[str(ROOT/"dist/Instalar_Suite_RutaXP.exe"),"--client",str(client)]
            expect=b"RutaXP"
        else:
            with urlopen(Request("https://api.github.com/repos/"+REPO+"/releases/latest",headers={"User-Agent":"RutaXP-release-QA"}),timeout=30) as res:
                assert json.load(res)["tag_name"]=="v"+EXPECTED
            command=[str(original(old,work))]
            expect=("Suite RutaXP "+EXPECTED).encode()
        try:
            result=subprocess.run(command,input=b"1\n" if old!="build" else b"",cwd=work,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=175)
        except subprocess.TimeoutExpired as exc:
            print((exc.output or b"").decode("utf8","replace"),flush=True)
            raise
        output=result.stdout.decode("utf8","replace")
        print(output,flush=True)
        assert all(mark not in output for mark in ("Esperando el ZIP","Abriendo la descarga oficial","https://www.curseforge.com/wow/addons/")), "Installer asked for browser interaction"
        if locked:
            assert "sin guardar el ZIP" in output, output
        assert result.returncode==0 and expect in result.stdout, result.returncode
        if old!="build":
            assert (settings/"latest.txt").read_text(encoding="utf-8-sig").strip()==EXPECTED
        verify_native(addons/"RutaXP",character,settings/"Suite/Descargas",work,locked)

if __name__=="__main__":
    main(sys.argv[1], "--locked" in sys.argv[2:])
