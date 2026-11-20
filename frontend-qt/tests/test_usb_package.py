import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from nspb_qt.win.game_package import write_package
from nspb_qt.win.hot_install import HotInstallError
from nspb_qt.win.usb_package import package_identity, send_package


class FakeAFC:
    def __init__(self, *, corrupt=False, failed=False, complete=True):
        self.files = {'/Documents/games/old/save/main.dat': b'keep save'}
        self.events = []
        self.corrupt, self.failed, self.complete = corrupt, failed, complete

    async def get_device_info(self):
        return {'FSFreeBytes': 1024**3}

    async def makedirs(self, path):
        self.events.append(('mkdir', path))

    async def fopen(self, path, mode):
        self.files[path] = b''
        return path

    async def fwrite(self, handle, data):
        self.files[handle] += data

    async def fclose(self, handle):
        pass

    async def stat(self, path):
        return {'st_size': len(self.files[path])}

    async def get_file_hash(self, path):
        self.events.append(('hash', path))
        return b'corrupt' if self.corrupt else hashlib.sha1(self.files[path]).digest()

    async def rename(self, source, target):
        self.events.append(('rename', target))
        self.files[target] = self.files.pop(source)
        if target.endswith('.request.json') and (self.complete or self.failed):
            request = json.loads(self.files[target])
            receipt = dict(schema=1, id=request['id'], state='failed' if self.failed else 'complete',
                           progress=1, titleID='0100000000000001', message='import rejected')
            self.files[target.replace('.request.json', '.status.json')] = json.dumps(receipt).encode()

    async def set_file_contents(self, path, data):
        self.files[path] = data

    async def exists(self, path):
        return path in self.files

    async def get_file_contents(self, path):
        return self.files[path]

    async def rm(self, path):
        del self.files[path]


class USBPackageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        data = root / 'romfs.img'
        data.write_bytes(b'synthetic game data')
        self.path = root / 'game.sppgame'
        write_package(self.path, title_id='0100000000000001', bundle_id='org.spplechos.shell.TEAM',
                      team_id='TEAM', files=[('data/romfs.img', data, data.stat().st_size)])
        self.manifest = package_identity(self.path)

    async def test_success_waits_for_phone_receipt_and_preserves_existing_saves(self):
        afc = FakeAFC()
        progress = []
        result = await send_package(afc, self.path, self.manifest, lambda *args: progress.append(args))
        self.assertEqual(result, '0100000000000001')
        self.assertEqual(progress[-1], ('usb.complete', 100))
        request = next(i for i, event in enumerate(afc.events) if event[0] == 'rename' and event[1].endswith('.request.json'))
        verified = next(i for i, event in enumerate(afc.events) if event[0] == 'hash')
        self.assertLess(verified, request)
        self.assertEqual(afc.files['/Documents/games/old/save/main.dat'], b'keep save')

    async def test_hash_failure_does_not_publish_import_request(self):
        afc = FakeAFC(corrupt=True)
        with self.assertRaisesRegex(HotInstallError, 'usb.verifyFailed'):
            await send_package(afc, self.path, self.manifest, lambda *_: None)
        self.assertFalse(any(p.endswith('.request.json') for p in afc.files))

    async def test_phone_rejection_is_not_reported_as_success(self):
        afc = FakeAFC(failed=True)
        with self.assertRaisesRegex(HotInstallError, 'import rejected'):
            await send_package(afc, self.path, self.manifest, lambda *_: None)
        self.assertEqual(afc.files['/Documents/games/old/save/main.dat'], b'keep save')

    async def test_transfer_without_receipt_is_not_import_success(self):
        afc = FakeAFC(complete=False)
        with self.assertRaisesRegex(HotInstallError, 'usb.waitTimeout'):
            await send_package(afc, self.path, self.manifest, lambda *_: None, timeout=0)

    def test_truncated_source_is_rejected_before_transfer(self):
        self.path.write_bytes(self.path.read_bytes()[:-1])
        with self.assertRaisesRegex(HotInstallError, 'usb.invalidPackage'):
            package_identity(self.path)
