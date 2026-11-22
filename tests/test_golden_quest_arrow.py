"""The gold mission pointer uses its actual pixels and faces the same way in both HUDs."""
import hashlib
import math
from pathlib import Path
import struct
import unittest

from lupa.lua51 import LuaRuntime
try:
    from PIL import Image
except ImportError:
    Image = None

import test_guide_journey as journey
import test_quest_engine as engine_fixtures
from tools import suite_journey


ROOT = Path(__file__).resolve().parents[1]
ART = r"Interface\AddOns\RutaXP\Media\Nav\quest-direction.tga"


def load_style_picker(load, ns):
    for name in ("Talents.lua", "ArrowStyles.lua"):
        load((ROOT / "RutaXP" / name).read_text(encoding="utf-8-sig"), "RutaXP", ns)


class ArrowPickerTests(unittest.TestCase):
    def setUp(self):
        fixture = engine_fixtures.NavigationAndFullTocTests()
        fixture.setUp()
        self.h = fixture.host
        load_style_picker(self.h.load, self.h.ns)
        self.h.guide("arrow-test", steps=[{"title": "Camino", "goals": [
            {"t": "accept", "quest": 12, "map": 1436, "x": 56.33, "y": 47.52, "f": "e"}
        ]}])
        self.h.state.mapID, self.h.state.x, self.h.state.y = 1436, .50, .50
        self.h.initialize()
        self.h.call("SelectGuide", "arrow-test")
        self.styles = self.h.ns.ArrowStyles
        self.frame = self.h.ns.navigationFrame

    def test_click_opens_picker_and_drag_leaves_it_closed(self):
        frame, styles = self.frame, self.styles
        for button, drag in (("RightButton", False), ("LeftButton", True), ("LeftButton", False)):
            frame.scripts.OnMouseDown(frame, button)
            if drag:
                frame.scripts.OnDragStart(frame)
                frame.scripts.OnDragStop(frame)
            frame.scripts.OnMouseUp(frame, button)
            if button == "LeftButton" and not drag:
                self.assertTrue(styles.panel.shown)
            else:
                self.assertIsNone(styles.panel)
        # No extra drag listener or toggle when the HUD registers again.
        styles.Attach(styles, frame)
        frame.scripts.OnMouseDown(frame, "LeftButton")
        frame.scripts.OnMouseUp(frame, "LeftButton")
        self.assertFalse(styles.panel.shown)

    def test_all_seven_previews_apply_to_the_living_hud_and_persist_per_character(self):
        h, frame, styles = self.h, self.frame, self.styles
        styles.Toggle(styles)
        panel = styles.panel
        self.assertEqual(len(panel.styles), 7)
        paths = set()
        for index, button in panel.styles.items():
            h.globals.Click(button)
            art = styles.GetTexture(styles)
            paths.add(art)
            self.assertEqual(frame.body.texture, art)
            self.assertEqual(button.icon.texture, art)
            asset = ROOT / "RutaXP" / "Media" / "Nav" / art.rsplit("\\", 1)[1]
            self.assertTrue(asset.is_file(), asset)
            self.assertEqual([i for i, b in panel.styles.items() if b.check.shown], [index])
        self.assertEqual(len(paths), 7)

        for button, scale in ((panel.larger, 2.0), (panel.smaller, 0.6)):
            for _ in range(20):
                h.globals.Click(button)
            self.assertEqual(styles.GetScale(styles), scale)
            self.assertEqual(frame.arrow.scale, scale)
        previous_height = frame.height
        h.globals.Click(panel.larger)
        self.assertGreater(frame.height, previous_height)
        panel.showText.SetChecked(panel.showText, False)
        h.globals.Click(panel.showText)
        h.call("UpdateNavigation")
        self.assertFalse(frame.distance.shown)
        self.assertFalse(frame.hint.shown)
        self.assertTrue(frame.arrow.shown)

        old = h.ns.char
        h.ns.char = h.table({})
        self.assertEqual(styles.GetTexture(styles), ART)
        self.assertEqual(styles.GetScale(styles), 1)
        self.assertTrue(styles.ShowsText(styles))
        h.ns.char = old
        # Fresh module, same persisted SavedVariables (e.g. after /reload).
        h.load((ROOT / "RutaXP/ArrowStyles.lua").read_text(encoding="utf-8-sig"), "RutaXP", h.ns)
        restored = h.ns.ArrowStyles
        self.assertEqual(restored.GetTexture(restored), frame.body.texture)
        self.assertAlmostEqual(restored.GetScale(restored), 0.7)
        self.assertFalse(restored.ShowsText(restored))


class ArrowAssetTests(unittest.TestCase):
    def test_quest_icon_is_a_square_truecolor_tga_with_alpha(self):
        data = (ROOT / "RutaXP/Media/Nav/quest-direction.tga").read_bytes()
        self.assertIn(data[2], (2, 10))
        self.assertEqual(struct.unpack_from("<HHB", data, 12), (128, 128, 32))
        self.assertEqual(data[17] & 15, 8)

    @unittest.skipUnless(Image, "Pillow required to sample the arrow silhouette")
    def test_visible_art_is_gold_with_a_centred_upward_tip_and_transparent_margins(self):
        with Image.open(ROOT / "RutaXP/Media/Nav/quest-direction.tga") as asset:
            image = asset.convert("RGBA")
        mask = image.getchannel("A").point(lambda alpha: 255 if alpha>=100 else 0)
        left,top,right,bottom = mask.getbbox()
        self.assertGreater(min(left, top, image.width-right, image.height-bottom), 0)
        widths=[]
        for y in range(top,bottom):
            widths.append(sum(bool(v) for v in mask.crop((left,y,right,y+1)).getdata()))
        widest = max(widths)
        head = widths.index(widest)
        self.assertLess(head, len(widths)*.45)
        self.assertLess(widths[0], widest*.20)
        self.assertGreater(widest, 1.5*widths[len(widths)//2])
        tip = mask.crop((0,top,image.width,top+1)).getbbox()
        self.assertAlmostEqual((tip[0]+tip[2])/2, image.width/2, delta=3)
        opaque = [rgb for rgb in image.getdata() if rgb[3]>=128]
        gold = sum(r>g and g>b*1.25 for r,g,b,_ in opaque)
        self.assertGreater(gold/len(opaque), .60)


@unittest.skipUnless((journey.NATIVE / "Journey.toc").is_file(), "requires the owner's native Journey HUD")
class JourneyArrowTests(unittest.TestCase):
    def test_cardinal_goals_and_changing_facing_rotate_only_the_intact_golden_art(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(journey.MOCK)
        lua.execute("""
            local proto=getmetatable(UIParent)
            function proto:SetTexture(path) self.art=path end
            function proto:SetTexCoord(...) self.uv={...} end
            function proto:SetVertexColor(...) self.tint={...} end
            function proto:SetRotation(angle) self.angle=angle end
            function proto:SetAllPoints(anchor) self.allPoints=anchor end
            function GetPlayerFacing() return facing end
            facing=0
            dn,dw=0,100
            ns.GuideEngine.Waypoint=function()
                return 1429,(500+dn)/1300,(500+dw)/1300,"Destino de misión"
            end
        """)
        ns = lua.globals().ns
        load_style_picker(lua.execute, ns)
        lua.execute((journey.ROOT / "RutaXP/GuideJourney.lua").read_text(encoding="utf8"), "RutaXP", ns)
        for filename, data in suite_journey.contents(journey.NATIVE):
            if filename.endswith(".lua"):
                lua.execute(data, "RutaXP", ns)
        lua.execute('event("PLAYER_LOGIN"); tick(); tick()')
        hud = lua.globals().RutaXPJourneyScreenArrow
        self.assertEqual(hud.arrowTexture.art, ART)
        self.assertGreater(hud.GetWidth(hud), 0)
        self.assertEqual(hud.GetWidth(hud), hud.GetHeight(hud))
        self.assertTrue(lua.eval("RutaXPJourneyScreenArrow.arrowTexture.allPoints==RutaXPJourneyScreenArrow"))
        self.assertEqual(hud.label.text, "Destino de misión")
        for yards in (25,250):
            for dn,dw,bearing in ((1,0,0),(0,-1,-math.pi/2),(-1,0,math.pi),(0,1,math.pi/2)):
                for facing in (0,math.pi/2,math.pi,3*math.pi/2):
                    with self.subTest(yards=yards,direction=(dn,dw),facing=facing):
                        lua.execute("dn,dw,facing=...; tick(); tick()",dn*yards,dw*yards,facing)
                        texture = hud.arrowTexture
                        self.assertTrue(texture.IsShown(texture))
                        self.assertTrue(hud.container.IsShown(hud.container))
                        self.assertIsNotNone(texture.angle)
                        error = (texture.angle-bearing+facing+math.pi)%(2*math.pi)-math.pi
                        self.assertAlmostEqual(error, 0, places=8)
                        self.assertIn(tuple(texture.tint.values()) if texture.tint else (), ((),(1,1,1),(1,1,1,1)))
                        self.assertIn(tuple(texture.uv.values()) if texture.uv else (), ((),(0,1,0,1),(0,0,0,1,1,0,1,1)))
                        self.assertTrue(hud.distLabel.text)

        hud.scripts.OnMouseDown(hud, "LeftButton")
        hud.scripts.OnMouseUp(hud, "LeftButton")
        picker = ns.ArrowStyles.panel
        self.assertTrue(picker.shown)
        button = picker.styles[3]
        button.scripts.OnClick(button)
        self.assertEqual(hud.arrowTexture.art, ART.replace("direction.tga", "forge.tga"))
        old_scale = hud.scale
        picker.larger.scripts.OnClick(picker.larger)
        self.assertAlmostEqual(hud.scale, old_scale * 1.1)
        for show in (False, True):
            picker.showText.SetChecked(picker.showText, show)
            picker.showText.scripts.OnClick(picker.showText)
            lua.execute("tick(); tick()")
            self.assertEqual(hud.label.IsShown(hud.label), show)
            self.assertEqual(hud.distLabel.IsShown(hud.distLabel), show)
            self.assertTrue(hud.arrowTexture.IsShown(hud.arrowTexture))

    def test_upgrade_of_already_embedded_journey_matches_a_clean_package(self):
        # Recreate the old adapted arrow from the owner's source without
        # redistributing it, then use the normal in-place packaging entry point.
        clean = dict(suite_journey.contents(journey.NATIVE))
        script = "lib/TomCats/Arrows.lua"
        key = "Modules/Journey/" + script
        old = (journey.NATIVE / script).read_bytes().decode("utf-8-sig")
        old = old.replace("select(2, ...).SetupGlobalFacade()", "setfenv(1, RutaXPJourneyEnvironment())")
        old = old.replace("function ArrowMixin:SetTarget(targetX, targetY, mapID, disablePingAnimation)",
                          "function ArrowMixin:SetTarget(targetX, targetY, mapID, disablePingAnimation, coordinate)")
        old = old.replace("local _, coordinate = C_Map.GetWorldPosFromMapPos(mapID, { x = targetX, y = targetY })",
                          "-- The host supplies the verified world coordinate.")
        old = old.replace('math.floor(distance + 0.5) .. " yards"', 'FormatJourneyDistance(distance)')
        self.assertIn('I["arrow-atlas.png"]', old)
        previous = {**clean, key: old.encode("utf8")}
        upgraded = dict(suite_journey.embedded_contents(previous.__getitem__))
        def fingerprints(files):
            return {name: hashlib.sha256(data).hexdigest() for name,data in files.items()}
        self.assertEqual(fingerprints(upgraded), fingerprints(clean))
        self.assertTrue(upgraded[key] != previous[key])
        self.assertEqual(fingerprints(dict(suite_journey.embedded_contents(upgraded.__getitem__))), fingerprints(clean))


if __name__ == "__main__":
    unittest.main()
