from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime


SOURCE = Path(__file__).resolve().parents[1] / "RutaXP" / "WorldMapTracking.lua"

# Stable enum values from the Forever client's MinimapConstantsDocumentation.
FILTERS = (
    ("auctioneer", "Auctioneer", 1), ("banker", "Banker", 2),
    ("battlemaster", "Battlemaster", 4), ("flight", "TaxiNode", 8),
    ("innkeeper", "Innkeeper", 32), ("mailbox", "Mailbox", 64),
    ("profTrainer", "TrainerProfession", 128), ("repair", "Repair", 512),
    ("lowLevelQuests", "TrivialQuests", 1024), ("stable", "Stablemaster", 2048),
    ("classTrainer", "TrainerClass", 8388608),
)


class NativeMapTrackingTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.g = self.lua.globals()
        self.lua.execute("""
            rows, events, scans, changes = {}, {}, 0, 0
            Enum = {MinimapTrackingFilter={}}
            function CreateFrame()
                return {
                    RegisterEvent=function(self, event) events[event]=true end,
                    SetScript=function(self, script, fn)
                        assert(script=="OnEvent")
                        Fire=function(event, arg) if events[event] then fn(self, event, arg) end end
                    end,
                }
            end
            C_Minimap = {
                GetNumTrackingTypes=function() scans=scans+1; return #rows end,
                GetTrackingFilter=function(index) return {filterID=rows[index].filterID} end,
                GetTrackingInfo=function(index) return rows[index] end,
                SetTracking=function() error("the map must not overwrite minimap settings") end,
            }
        """)
        for _, field, ident in FILTERS:
            self.g.Enum.MinimapTrackingFilter[field] = ident
        self.lua.execute(SOURCE.read_text(encoding="utf-8-sig"), "RutaXP", self.lua.table())
        self.tracking = self.g.RutaXPWorldMapTracking
        self.lua.execute("RutaXPWorldMapTracking.OnChanged=function() changes=changes+1 end")

    def populate(self):
        for index, (_, _, ident) in enumerate(reversed(FILTERS), 1):
            self.g.rows[index] = self.lua.table_from({
                "filterID": ident, "active": index % 2 == 0,
                "name": f"Etiqueta del cliente {index}", "texture": 12000 + index,
            })
        self.g.rows[len(FILTERS) + 1] = self.lua.table_from({"active": True, "name": "Rastrear bestias"})

    def test_all_eleven_categories_use_native_ids_and_return_the_localized_name_and_icon(self):
        self.populate()
        entries = self.tracking.Read()
        self.assertEqual(set(entries.keys()), {key for key, _, _ in FILTERS})
        for index, (key, _, _) in enumerate(reversed(FILTERS), 1):
            with self.subTest(key=key):
                self.assertIs(self.tracking.Get(key), index % 2 == 0)
                info = self.tracking.Info(key)
                self.assertEqual((info.index, info.name, info.texture),
                                 (index, f"Etiqueta del cliente {index}", 12000 + index))
        self.assertEqual(self.g.scans, 1)

    def test_map_refreshes_when_native_state_changes_and_disappearing_rows_become_unknown(self):
        self.populate()
        self.g.Fire("PLAYER_ENTERING_WORLD")
        self.assertEqual(self.g.changes, 1)
        self.g.rows[1].active = True
        self.g.Fire("CVAR_UPDATE", "minimapTrackedInfov4")
        self.assertTrue(self.tracking.Get("classTrainer"))
        self.assertEqual(self.g.changes, 2)
        for event in ("SPELLS_CHANGED", "MINIMAP_UPDATE_TRACKING"):
            self.g.Fire(event)
        self.assertEqual(self.g.changes, 2)
        self.g.rows[1].filterID = None
        self.g.Fire("MINIMAP_UPDATE_TRACKING")
        self.assertIsNone(self.tracking.Get("classTrainer"))
        self.assertEqual(self.g.changes, 3)

    def test_empty_startup_is_cached_until_the_client_provides_its_settings(self):
        for _ in range(200):
            self.g.Fire("CVAR_UPDATE", "cameraDistanceMaxZoomFactor")
            self.assertIsNone(self.tracking.Get("lowLevelQuests"))
        self.assertEqual(self.g.scans, 1)
        self.populate()
        self.g.Fire("SPELLS_CHANGED")
        self.assertIs(self.tracking.Get("lowLevelQuests"), False)
        self.assertEqual(self.g.scans, 2)
        self.g.C_Minimap = None
        self.assertFalse(list(self.tracking.Read().keys()))
        self.assertIsNone(self.tracking.Info("lowLevelQuests"))

    def test_explicit_map_checkbox_writes_only_its_current_native_index(self):
        self.populate()
        self.lua.execute("""
            writes={}
            C_Minimap.SetTracking=function(index, on)
                writes[#writes+1]={index, on}
                rows[index].active=on
                Fire("MINIMAP_UPDATE_TRACKING")
            end
        """)
        self.tracking.Read()
        self.assertEqual(len(self.g.writes), 0)
        # Known spells can change and move the town filters while a menu is open.
        self.lua.execute("rows[1], rows[2] = rows[2], rows[1]")
        for index, enabled in enumerate((True, False), 1):
            self.assertTrue(self.tracking.Set("classTrainer", enabled))
            self.assertIs(self.tracking.Get("classTrainer"), enabled)
            self.assertEqual(len(self.g.writes), index)
            self.assertEqual((self.g.writes[index][1], self.g.writes[index][2]), (2, enabled))
            self.assertEqual(self.g.changes, index)
        self.assertTrue(self.tracking.Set("classTrainer", False))
        self.assertFalse(self.tracking.Set("unlisted", True))
        self.assertFalse(self.tracking.Set("banker", None))
        self.assertEqual(len(self.g.writes), 2)
        self.g.C_Minimap.SetTracking = None
        self.assertFalse(self.tracking.Set("classTrainer", True))
