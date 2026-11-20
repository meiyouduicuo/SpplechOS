import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('verify_framework_hle', Path(__file__).resolve().parents[1] / 'verify_framework_hle.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ForcedHleRegistryTests(unittest.TestCase):
    def image(self, duplicate=False, chained=False):
        data = bytearray(1024)
        struct.pack_into('<8I', data, 0, 0xfeedfacf, 0x100000c, 0, 6, 2 if chained else 1, 168 if chained else 152, 0, 0)
        struct.pack_into('<II16sQQQQIIII', data, 32, 0x19, 152, b'__DATA', 0, 1024, 0, 1024, 3, 3, 1, 0)
        struct.pack_into('<16s16sQQIIIIIIII', data, 104, b'swforce', b'__DATA', 256, 48, 256, 3, 0, 0, 0, 0, 0, 0)
        data[512:516] = b'a\0b\0'
        flag = (2 << 51) if chained else 0
        struct.pack_into('<3Q', data, 256, 512 | flag, 0, 0)
        struct.pack_into('<3Q', data, 280, (512 if duplicate else 514) | flag, 0, 0)
        if chained:
            struct.pack_into('<4I', data, 184, 0x80000034, 16, 768, 128)
            struct.pack_into('<7I', data, 768, 0, 28, 0, 0, 0, 0, 0)
            struct.pack_into('<2I', data, 796, 1, 8)
            struct.pack_into('<IHHQIH', data, 804, 24, 16384, 6, 0, 0, 1)
        return data

    def check(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'framework'
            path.write_bytes(data)
            return module.verify_forced_hle(path)

    def test_distinct_registrations(self):
        self.assertEqual(self.check(self.image()), 2)

    def test_rejects_duplicate_names(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate forced-HLE registrations: a'):
            self.check(self.image(duplicate=True))

    def test_decodes_chained_rebases_before_checking_duplicates(self):
        self.assertEqual(self.check(self.image(chained=True)), 2)
        with self.assertRaisesRegex(ValueError, 'Duplicate forced-HLE registrations: a'):
            self.check(self.image(duplicate=True, chained=True))
