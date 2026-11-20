import unittest
from nspb_qt.win.device_probe import is_original_shell


class DeviceIdentityTests(unittest.TestCase):
    def test_original_and_altstore_metadata(self):
        self.assertTrue(is_original_shell('org.spplechos.shell', {}))
        self.assertTrue(is_original_shell('resigned.app', {'ALTBundleIdentifier': 'org.spplechos.shell'}))

    def test_sideloadly_suffix_must_match_installed_entitlement(self):
        metadata = {'Entitlements': {'com.apple.developer.team-identifier': 'TEAM123'}}
        self.assertTrue(is_original_shell('org.spplechos.shell.TEAM123', metadata))
        self.assertFalse(is_original_shell('org.spplechos.shell.OTHER', metadata))
        self.assertFalse(is_original_shell('org.spplechos.shell.TEAM123', {}))

    def test_independent_lan_and_airport_apps_are_not_original(self):
        metadata = {'Entitlements': {'com.apple.developer.team-identifier': 'TEAM123'}}
        for bundle_id in ('org.spplechos.acnh.airporttest.TEAM123', 'org.spplechos.shell.lantest.TEAM123'):
            self.assertFalse(is_original_shell(bundle_id, metadata))
