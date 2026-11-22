"""Exercise the same refresh calls used by the OpenMap world canvas."""
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]


class WorldMapPinTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime()
        self.lua.execute("""
            shown, active, sets, timers = true, {}, {}, {}
            local function noop() end
            function UnitFactionGroup() return "Alliance" end
            function UnitClass() return "Pícara", "ROGUE" end
            function UnitPosition() error("World pins must not require player position") end
            WorldMapFrame = {IsShown = function() return shown end}
            C_Timer = {After = function(_, fn) table.insert(timers, fn) end}
            function flush()
                while #timers > 0 do table.remove(timers, 1)() end
            end
            RutaXPWorldMapTracking = {Info = function(key)
                return {active = active[key], name = key, texture = "game-" .. key}
            end}
            local stitch = {}
            function stitch.IsBuilt() return true end
            function stitch.FromYards(cont, north, west)
                assert(cont == 1)
                return west / 1000, north / 1000
            end
            function stitch.Rect(mapID)
                assert(mapID == 1455)
                return 0.1, 0.3, 0.5, 0.7
            end
            function stitch.PinSet(key, zoom)
                assert(not sets[key] and zoom == 1)
                sets[key] = {pins = {}, on = true}
                return sets[key]
            end
            function stitch.AddPin(set, x, y, look, row)
                local pin = {x = x, y = y, texture = look.texture, row = row, SetScript = noop}
                table.insert(set.pins, pin)
                return pin
            end
            function stitch.SetPinSetOn(set, enabled) set.on = enabled end
            local mod = {Refresh = function() RutaXPWorldMapTracking.Refresh(openMap) end}
            openMap = {MapStitch = stitch, GetModule = function() return mod end}
            ns = {
                worldMapServiceEra = {[1412] = {1, 80, 50, 40, 10}},
                worldMapServiceData = {
                    [1412] = {
                        {"banker", "AH", 25, 25, "Banco", false, "", true, 1},
                        {"banker", "AH", 25, 25, "Banco", false, "", true, 1},
                        {"banker", "H", 25, 25, "Enemigo", false, "", true, 2},
                    },
                    [1455] = {
                        {"classTrainer", "A", 50, 50, "Maestro de pícaros", "ROGUE"},
                        {"classTrainer", "A", 20, 20, "Maestro de magos", "MAGE"},
                    },
                },
            }
        """)
        self.lua.execute((ROOT / "RutaXP/WorldMapServices.lua").read_text(encoding="utf-8"), "RutaXP", self.lua.globals().ns)

    def test_distant_icons_use_native_texture_faction_class_and_coordinate_system(self):
        self.lua.execute("""
            active.banker, active.classTrainer = true, true
            RutaXPWorldMapTracking.Refresh(openMap)
            flush()
            local bank, trainer = sets.rutaxp_service_banker.pins, sets.rutaxp_service_classTrainer.pins
            assert(#bank == 1 and bank[1].row[5] == "Banco" and bank[1].texture == "game-banker")
            assert(math.abs(bank[1].x - .04) < .00001 and math.abs(bank[1].y - .07) < .00001)
            assert(#trainer == 1 and trainer[1].row[6] == "ROGUE")
            assert(math.abs(trainer[1].x - .2) < .00001 and math.abs(trainer[1].y - .6) < .00001)
            active.banker = false
            RutaXPWorldMapTracking.OnChanged()
            assert(sets.rutaxp_service_banker.on == false and sets.rutaxp_service_classTrainer.on)
            active.banker = true
            RutaXPWorldMapTracking.OnChanged()
            assert(sets.rutaxp_service_banker.on and #bank == 1)
        """)

    def test_large_sets_pause_when_closed_and_resume_without_duplicate_pins(self):
        self.lua.execute("""
            for i = 1, 180 do
                table.insert(ns.worldMapServiceData[1455], {"repair", "A", i / 2, 30, "Herrero " .. i})
            end
            active.repair = true
            RutaXPWorldMapTracking.Refresh(openMap)
            local set = sets.rutaxp_service_repair
            local before = #set.pins
            assert(before > 0 and before < 180)
            shown = false
            flush()
            assert(#set.pins == before)
            shown, active.repair = true, false
            RutaXPWorldMapTracking.Refresh(openMap)
            assert(not set.on)
            active.repair = true
            RutaXPWorldMapTracking.OnChanged()
            flush()
            assert(set.on and #set.pins == 180)
        """)

    def test_city_and_parent_round_the_same_spawn_differently(self):
        self.lua.execute("""
            ns.worldMapServiceEra[1456] = {1, 75, 48, 46, 12}
            ns.worldMapServiceData[1456] = {
                {"banker", "AH", 28, 25, "Banco", false, "", true, 1},
                {"banker", "AH", 28, 25, "Segundo banquero", false, "", true, 3},
                {"banker", "AH", 90, 90, "Banco", false, "", true, 1},
            }
            active.banker = true
            RutaXPWorldMapTracking.Refresh(openMap)
            flush()
            assert(#sets.rutaxp_service_banker.pins == 3)
        """)

    def test_zone_can_place_a_service_before_continent_projection_is_available(self):
        self.lua.execute("""
            local s=openMap.MapStitch
            s.FromYards=function() return nil end
            s.Rect=function() return .1, .3, .5, .7 end
            function CreateVector2D(x,y) return {x=x,y=y} end
            C_Map={GetMapPosFromWorldPos=function(c,p,id)
                assert(c==1 and p.x==70 and p.y==40 and id==1412)
                return id, {GetXY=function() return .4,.6 end}
            end}
            active.banker=true
            RutaXPWorldMapTracking.Refresh(openMap)
            flush()
            local pins=sets.rutaxp_service_banker.pins
            assert(#pins==1 and math.abs(pins[1].x-.18)<.00001 and math.abs(pins[1].y-.62)<.00001)
        """)
