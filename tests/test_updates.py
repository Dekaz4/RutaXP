"""A local setup link leaves networking, duo behavior and progress untouched."""

import unittest

from test_addon import AddonHost, ADDON
from test_duo_journey import primitive_copy


class UpdateTests(unittest.TestCase):
    def host(self, version=None):
        h=AddonHost()
        h.initialize()
        toc=(ADDON / "RutaXP.toc").read_text(encoding="utf-8-sig")
        h.state.addonVersion=version or next(line.split(":",1)[1].strip() for line in toc.splitlines() if line.startswith("## Version:"))
        h.lua.execute('''
            C_AddOns={GetAddOnMetadata=function() return TEST.addonVersion end}
            StaticPopupDialogs={}
            function StaticPopup_Show(key) TEST.popupCount=(TEST.popupCount or 0)+1;TEST.popupKey=key end
            C_ChatInfo={SendAddonMessage=function() TEST.networkCalls=(TEST.networkCalls or 0)+1;error("No network") end}
            C_HTTP={Request=function() TEST.networkCalls=(TEST.networkCalls or 0)+1;error("No HTTP") end}
        ''')
        h.load((ADDON / "Updates.lua").read_text(encoding="utf-8-sig"),"RutaXP",h.ns)
        return h

    def test_local_version_comes_from_toc_metadata_with_a_safe_missing_api_fallback(self):
        h=self.host()
        self.assertEqual(h.ns.Updates.GetStatus(h.ns.Updates).localVersion,h.state.addonVersion)
        h.state.addonVersion="0.7.1"
        self.assertEqual(h.ns.Updates.GetLocalVersion(h.ns.Updates),"0.7.1")
        h.lua.execute("C_AddOns=nil;GetAddOnMetadata=nil")
        self.assertEqual(h.ns.Updates.GetLocalVersion(h.ns.Updates),h.ns.Updates.fallbackVersion)

    def test_update_command_opens_the_single_setup_link_and_clear_external_install_steps(self):
        h=self.host()
        h.call("Command","actualizar")
        self.assertEqual(h.state.popupCount,1)
        dialog=h.globals.StaticPopupDialogs.RUTAXP_UPDATE
        self.assertIn("Cierra WoW",dialog.text)
        self.assertIn("Instalador_RutaXP.exe",dialog.text)
        self.assertIn("vuelve a abrir WoW",dialog.text)
        self.assertIn("mismo setup",dialog.text)
        self.assertTrue(dialog.hasEditBox)
        frame=h.table({"editBox":h.table({})})
        frame.editBox.SetText=h.lua.eval("function(self,value) self.text=value end")
        dialog.OnShow(frame)
        self.assertEqual(frame.editBox.text,"https://github.com/Dekaz4/RutaXP/releases/latest/download/Instalador_RutaXP.exe")

    def test_startup_is_idempotent_without_automatic_popups_network_or_saved_variable_changes(self):
        h=self.host()
        h.ns.char.progress=h.table({"keep":{"cursor":28,"review":True,"confirmed":{"manual":True},"skipped":{"mine":True}}})
        before=primitive_copy(h.ns.char)
        u=h.ns.Updates
        u.Initialize(u);u.Initialize(u)
        self.assertEqual(sum("enlace al setup" in message for message in h.state.messages.values()),1)
        self.assertIsNone(h.state.popupCount)
        u.GetStatus(u);u.Show(u)
        self.assertIsNone(h.state.networkCalls)
        self.assertEqual(primitive_copy(h.ns.char),before)
        self.assertIsNone(u.Tick)
        self.assertIsNone(u.ObserveVersion)


if __name__=="__main__":
    unittest.main()
