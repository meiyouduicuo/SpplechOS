"""Renewed profiles may coexist. Use synthetic public metadata, never credentials."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nspb_qt.win.hot_install import HostIdentity, HotInstallError
from nspb_qt.win.signing_profiles import select_signing_profile, profile_error_text


class SigningProfileTests(unittest.TestCase):
    now = datetime(2026, 11, 21, tzinfo=timezone.utc)
    host = HostIdentity('org.spplechos.shell.TESTTEAM01', 'TESTTEAM01', 'b-test', None)
    cert = b'public certificate fixture, not a private key'

    def profile(self, days=7, uuid='latest', **changes):
        data = dict(Entitlements={'application-identifier': self.host.team_id + '.' + self.host.bundle_id,
                                  'com.apple.developer.team-identifier': self.host.team_id},
                    TeamIdentifier=[self.host.team_id], DeveloperCertificates=[self.cert],
                    ProvisionedDevices=['fixture-device'], CreationDate=self.now - timedelta(days=1),
                    ExpirationDate=self.now + timedelta(days=days), UUID=uuid)
        data.update(changes)
        return SimpleNamespace(plist=data, buf=b'synthetic profile')

    def choose(self, profiles):
        return select_signing_profile(profiles, self.host, self.cert, device_udid='fixture-device', now=self.now)

    def test_renewal_selects_latest_usable_profile_in_any_order(self):
        old, latest = self.profile(2, 'old'), self.profile(7, 'latest')
        for profiles in [[old, latest], [latest, old], [latest, latest]]:
            self.assertIs(self.choose(profiles), latest)

    def test_expired_profile_is_never_used(self):
        with self.assertRaisesRegex(HotInstallError, 'sign.profile.expired'):
            self.choose([self.profile(-1)])

    def test_wrong_certificate_is_explained_separately(self):
        with self.assertRaisesRegex(HotInstallError, 'sign.profile.certificate'):
            self.choose([self.profile(DeveloperCertificates=[b'different public cert'])])

    def test_wrong_app_is_never_selected(self):
        with self.assertRaises(HotInstallError):
            self.choose([self.profile(Entitlements={'application-identifier': 'TESTTEAM01.other.app'})])

    def test_other_device_and_other_team_are_never_used(self):
        for change in [dict(ProvisionedDevices=['other-device']), dict(TeamIdentifier=['OTHERTEAM0'])]:
            with self.subTest(change=change), self.assertRaises(HotInstallError):
                self.choose([self.profile(**change)])

    def test_missing_expiry_does_not_make_a_profile_usable(self):
        with self.assertRaises(HotInstallError):
            self.choose([self.profile(ExpirationDate=None)])

    def test_naive_plist_dates_and_deterministic_ties(self):
        a = self.profile(7, 'a', ExpirationDate=(self.now + timedelta(days=7)).replace(tzinfo=None))
        z = self.profile(7, 'z', ExpirationDate=(self.now + timedelta(days=7)).replace(tzinfo=None))
        self.assertIs(self.choose([a, z]), z)
        self.assertIs(self.choose([z, a]), z)

    def test_profile_errors_are_readable_in_the_selected_language(self):
        from nspb_qt.i18n import Lang
        from nspb_qt.l10n import t
        self.assertIn('证书', profile_error_text('sign.profile.certificate', lambda key: t(key, Lang('zh'))))
        self.assertIn('expired', profile_error_text('sign.profile.expired', lambda key: t(key, Lang('en'))))
        self.assertEqual(profile_error_text('other failure', lambda key: t(key, Lang('en'))), 'other failure')


if __name__ == '__main__':
    unittest.main()
