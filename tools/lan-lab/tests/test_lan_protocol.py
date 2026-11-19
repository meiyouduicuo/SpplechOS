"""Check message boundaries and protocol version before any game integration."""
import ctypes
import os
import unittest

lib = ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])


class Message(ctypes.Structure):
    _fields_ = [('kind', ctypes.c_uint8), ('title_id', ctypes.c_uint64), ('session_id', ctypes.c_uint8 * 16),
                ('body', ctypes.POINTER(ctypes.c_uint8)), ('body_size', ctypes.c_uint32)]


lib.spple_protocol_encode.argtypes = [ctypes.POINTER(Message), ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.POINTER(ctypes.c_size_t)]
lib.spple_protocol_decode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Message)]


class ProtocolTests(unittest.TestCase):
    def test_round_trip_preserves_title_session_and_binary_body(self):
        payload = (ctypes.c_uint8 * 4)(0, 1, 128, 255)
        message = Message(kind=1, title_id=0x0100559011740000, session_id=(ctypes.c_uint8 * 16)(*range(16)),
                          body=payload, body_size=4)
        out = ctypes.create_string_buffer(100)
        size = ctypes.c_size_t()
        self.assertEqual(lib.spple_protocol_encode(ctypes.byref(message), out, len(out), ctypes.byref(size)), 0)
        decoded = Message()
        self.assertEqual(lib.spple_protocol_decode(out, size.value, ctypes.byref(decoded)), 0)
        self.assertEqual(decoded.title_id, 0x0100559011740000)
        self.assertEqual(bytes(decoded.session_id), bytes(range(16)))
        self.assertEqual(ctypes.string_at(decoded.body, decoded.body_size), bytes(payload))

    def test_rejects_invalid_version_length_and_reserved_fields(self):
        msg = Message(kind=1, title_id=1)
        out = ctypes.create_string_buffer(64)
        size = ctypes.c_size_t()
        self.assertEqual(lib.spple_protocol_encode(ctypes.byref(msg), out, len(out), ctypes.byref(size)), 0)
        for index, bad in ((0, 0), (4, 2), (5, 255), (6, 1), (35, 1)):
            corrupted = bytearray(out.raw[:size.value]); corrupted[index] = bad
            data = ctypes.create_string_buffer(bytes(corrupted))
            decoded = Message()
            self.assertEqual(lib.spple_protocol_decode(data, len(corrupted), ctypes.byref(decoded)), -1)

    def test_encode_requires_nonzero_game_id_and_capacity(self):
        msg = Message(kind=1, title_id=0)
        out = ctypes.create_string_buffer(35)
        size = ctypes.c_size_t(99)
        self.assertEqual(lib.spple_protocol_encode(ctypes.byref(msg), out, len(out), ctypes.byref(size)), -1)
        self.assertEqual(size.value, 0)


if __name__ == '__main__':
    unittest.main()
