"""The control handshake requires both endpoints to use the same title ID."""
import ctypes
import os
import socket
import threading
import unittest

lib = ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
Session = ctypes.c_uint8 * 16
lib.spple_room_client_handshake.argtypes = [ctypes.c_ssize_t, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint8)]
lib.spple_room_server_handshake.argtypes = [ctypes.c_ssize_t, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint8)]


class HandshakeTests(unittest.TestCase):
    def test_two_peers_agree_on_the_room(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close); self.addCleanup(b.close)
        title = 0x0100559011740000
        session = Session(*range(1, 17))
        result = []
        thread = threading.Thread(target=lambda: result.append(lib.spple_room_server_handshake(a.fileno(), title, session)))
        thread.start()
        received = Session()
        self.assertEqual(lib.spple_room_client_handshake(b.fileno(), title, received), 0)
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [0])
        self.assertEqual(bytes(received), bytes(session))

    def test_other_game_does_not_connect(self):
        a, b = socket.socketpair()
        self.addCleanup(a.close); self.addCleanup(b.close)
        result = []
        session = Session(*range(1, 17))
        def server():
            result.append(lib.spple_room_server_handshake(a.fileno(), 0x0100559011740000, session))
            a.shutdown(socket.SHUT_WR)
        thread = threading.Thread(target=server)
        thread.start()
        received = Session(*([255] * 16))
        self.assertEqual(lib.spple_room_client_handshake(b.fileno(), 0x0100A00019DE0000, received), -1)
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [-1])
        self.assertEqual(bytes(received), bytes(16))

    def test_zero_session_is_rejected_before_network_io(self):
        self.assertEqual(lib.spple_room_server_handshake(-1, 1, Session()), -1)


if __name__ == '__main__':
    unittest.main()
