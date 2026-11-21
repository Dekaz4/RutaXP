import unittest

from lupa.lua51 import LuaRuntime

from tools.suite_lua import bind_namespace


class ModuleNamespaceTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''
            modules = {OpenMap={}, ForeverDungeonJournal={}, RXPGuides={}}
            function RutaXPModuleContext(name) return name, modules[name] end
        ''')

    def test_comments_and_guide_content_remain_byte_exact(self):
        text = r"""--[=[ local G = ... ]=] local _, addon = ...
local guide = [==[--[=[if function end until ...]=]
Guide: local _, addon = ...
'literal ...' ]==]
local label = 'a string with \' function() end ...'
--[[ stray closing tokens end, end, then ]]
return addon, guide, label
"""
        patched = bind_namespace("RXPGuides", "Guide.lua", text)
        self.assertEqual(patched, text.replace("]=] local _, addon = ...", ']=] local _, addon = RutaXPModuleContext("RXPGuides")'))
        ns, guide, label = self.lua.execute(patched, "RutaXP", self.lua.table())
        self.assertIn("Guide: local _, addon = ...", guide)
        self.assertTrue(self.lua.eval("rawequal")(ns, self.lua.globals().modules.RXPGuides))

    def test_nested_functions_get_only_their_own_args(self):
        text = '''
            local result
            if ... then
                do
                    local function call(callback, ...)
                        for _, n in ipairs({...}) do
                            if n then result = callback(...) end
                        end
                    end
                    repeat
                        call(function(...) return select('#', ...) end, 1, 2, 3)
                    until result
                end
            end
            local id, private = ...
            return id, private, result
        '''
        patched = bind_namespace("OpenMap", "Libs/Embedded.lua", text)
        self.assertEqual(patched.count("RutaXPModuleContext"), 2)
        name, private, count = self.lua.execute(patched, "RutaXP", self.lua.table())
        self.assertEqual((name, count), ("OpenMap", 3))
        self.assertTrue(self.lua.eval("rawequal")(private, self.lua.globals().modules.OpenMap))

    def test_chunk_at_the_lua_51_local_limit(self):
        text = "local " + ",".join(f"a{i}" for i in range(200)) + "\nreturn ..."
        patched = bind_namespace("OpenMap", "Map/Stitch.lua", text)
        name, _ = self.lua.execute(patched, "RutaXP", self.lua.table())
        self.assertEqual(name, "OpenMap")

    def test_native_globals_libs_and_unreferenced_guide_text_unchanged(self):
        for text in (
            "return _G.ForeverDungeonJournal_NS",
            'return function(...) return ("..."):find(...), ... end',
            "-- line ... c\r\nreturn [===[ function(...); end ]===]",
            "return \"escaped slash \\\\\" -- ...",
        ):
            self.assertEqual(bind_namespace("ForeverDungeonJournal", "Libs/Lib.lua", text), text)
        self.assertEqual(bind_namespace("OpenMap", "Core.lua", "return select(2, ...)"),
                         'return select(2, RutaXPModuleContext("OpenMap"))')
