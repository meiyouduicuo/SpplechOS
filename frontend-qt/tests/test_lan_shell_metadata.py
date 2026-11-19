import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nspb_qt.win import shell_export


class LocalNetworkMetadataTests(unittest.TestCase):
    def test_export_declares_local_network_and_preserves_existing_services(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp) / 'DmShell.app'
            app.mkdir()
            with (app / 'Info.plist').open('wb') as f:
                plistlib.dump({'NSBonjourServices': ['_existing._tcp']}, f)
            with patch.object(shell_export, '_dm_chain', return_value=''), \
                    patch.object(shell_export, '_dm_commit', return_value=''), \
                    patch.object(shell_export, '_dm_fork_patches', return_value=[]):
                shell_export._update_shell_plist(app, 'org.spplechos.shell', Path(temp))
                shell_export._update_shell_plist(app, 'org.spplechos.shell', Path(temp))
            with (app / 'Info.plist').open('rb') as f:
                info = plistlib.load(f)
            self.assertTrue(info['NSLocalNetworkUsageDescription'])
            self.assertEqual(info['NSBonjourServices'], ['_existing._tcp', '_spplechos-ldn._tcp'])


if __name__ == '__main__':
    unittest.main()
