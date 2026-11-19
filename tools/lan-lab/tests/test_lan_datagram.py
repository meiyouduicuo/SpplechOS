import ctypes
import os
import unittest

lib = ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])


class Datagram(ctypes.Structure):
    _fields_ = [('source_ipv4', ctypes.c_uint8 * 4), ('destination_ipv4', ctypes.c_uint8 * 4),
                ('source_port', ctypes.c_uint16), ('destination_port', ctypes.c_uint16),
                ('mode', ctypes.c_uint8), ('payload', ctypes.POINTER(ctypes.c_uint8)),
                ('payload_size', ctypes.c_uint16)]


lib.spple_datagram_encode.argtypes = [ctypes.POINTER(Datagram), ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.POINTER(ctypes.c_size_t)]
lib.spple_datagram_decode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Datagram)]


class DatagramTests(unittest.TestCase):
    def test_binary_datagram_round_trip(self):
        payload = (ctypes.c_uint8 * 4)(0, 255, 1, 2)
        data = Datagram((ctypes.c_uint8 * 4)(10, 1, 2, 3), (ctypes.c_uint8 * 4)(10, 1, 2, 255),
                        1234, 5678, 1, payload, 4)
        buf = ctypes.create_string_buffer(64); size = ctypes.c_size_t()
        self.assertEqual(lib.spple_datagram_encode(ctypes.byref(data), buf, len(buf), ctypes.byref(size)), 0)
        result = Datagram()
        self.assertEqual(lib.spple_datagram_decode(buf, size.value, ctypes.byref(result)), 0)
        self.assertEqual((bytes(result.source_ipv4), bytes(result.destination_ipv4)),
                         (b'\x0a\x01\x02\x03', b'\x0a\x01\x02\xff'))
        self.assertEqual((result.source_port, result.destination_port, result.mode), (1234, 5678, 1))
        self.assertEqual(ctypes.string_at(result.payload, result.payload_size), bytes(payload))

    def test_rejects_malformed_frames(self):
        base = bytearray(16); base[10:12] = b'\x00\x01'
        for index, value in ((12, 2), (13, 1), (15, 1)):
            data = bytearray(base); data[index] = value
            out = Datagram()
            self.assertEqual(lib.spple_datagram_decode(bytes(data), len(data), ctypes.byref(out)), -1)
        base[10:12] = b'\0\0'
        self.assertEqual(lib.spple_datagram_decode(bytes(base), len(base), ctypes.byref(Datagram())), -1)


if __name__ == '__main__':
    unittest.main()
