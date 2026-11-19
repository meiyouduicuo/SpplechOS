"""Validate bounds of guest LDN records before accepting remote data."""
import ctypes
import os
import struct
import unittest

lib = ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
lib.spple_ldn_validate_network.argtypes = [ctypes.c_void_p]
lib.spple_ldn_scan_matches.argtypes = [ctypes.c_void_p, ctypes.c_void_p]


class LdnAbiTests(unittest.TestCase):
    def make_valid(self):
        buf = bytearray(0x480)
        buf[0x26] = 4
        buf[0x27:0x2c] = b'room\0'
        buf[0x66] = 4
        buf[0x67] = 1
        buf[0x68 + 11] = 1
        return buf

    def validate(self, buf):
        record = ctypes.create_string_buffer(bytes(buf))
        return lib.spple_ldn_validate_network(record)

    def test_valid_guest_record(self):
        self.assertEqual(self.validate(self.make_valid()), 0)

    def test_rejects_out_of_bounds_and_inconsistent_nodes(self):
        for offset, value in ((0x26, 33), (0x66, 9), (0x67, 5), (0x68 + 11, 2)):
            record = self.make_valid(); record[offset] = value
            self.assertEqual(self.validate(record), -1)
        record = self.make_valid(); struct.pack_into('<H', record, 0x26a, 0x181)
        self.assertEqual(self.validate(record), -1)

    def test_scan_filters_game_session_and_scene(self):
        network = self.make_valid()
        struct.pack_into('<q', network, 0, 0x0100559011740000)
        struct.pack_into('<H', network, 10, 3)
        network[16:32] = bytes(range(16))
        filt = bytearray(0x60)
        struct.pack_into('<q', filt, 0, 0x0100559011740000)
        struct.pack_into('<H', filt, 10, 3)
        filt[16:32] = bytes(range(16))
        struct.pack_into('<I', filt, 0x5c, 1 | 2 | 32)
        n = ctypes.create_string_buffer(bytes(network)); f = ctypes.create_string_buffer(bytes(filt))
        self.assertEqual(lib.spple_ldn_scan_matches(n, f), 1)
        filt[16] = 255
        f = ctypes.create_string_buffer(bytes(filt))
        self.assertEqual(lib.spple_ldn_scan_matches(n, f), 0)
        struct.pack_into('<I', filt, 0x5c, 1 << 12)
        f = ctypes.create_string_buffer(bytes(filt))
        self.assertEqual(lib.spple_ldn_scan_matches(n, f), -1)
        record = self.make_valid(); record[0x2b] = 1
        self.assertEqual(self.validate(record), -1)


if __name__ == '__main__':
    unittest.main()
