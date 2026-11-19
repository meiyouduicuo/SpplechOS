"""Exercise the actual C stream transport using connected local sockets."""
import ctypes
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import unittest

library = ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
library.spple_lan_send_frame.argtypes = (ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_size_t)
library.spple_lan_send_frame.restype = ctypes.c_int
library.spple_lan_receive_frame.argtypes = (ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_size_t,
                                            ctypes.POINTER(ctypes.c_size_t))
library.spple_lan_receive_frame.restype = ctypes.c_int


class LanFrameTests(unittest.TestCase):
    def setUp(self):
        self.writer, self.reader = socket.socketpair()
        self.addCleanup(self.writer.close)
        self.addCleanup(self.reader.close)

    def read_frame(self, capacity=1024):
        output = ctypes.create_string_buffer(capacity)
        size = ctypes.c_size_t(999)
        result = library.spple_lan_receive_frame(self.reader.fileno(), output, capacity, ctypes.byref(size))
        return result, output.raw[:size.value], size.value

    def test_actual_round_trip_and_boundaries(self):
        payload = b'first frame' * 10
        buf = ctypes.create_string_buffer(payload)
        self.assertEqual(library.spple_lan_send_frame(self.writer.fileno(), buf, len(payload)), 0)
        self.assertEqual(library.spple_lan_send_frame(self.writer.fileno(), None, 0), 0)
        self.assertEqual(self.read_frame(), (0, payload, len(payload)))
        self.assertEqual(self.read_frame(), (0, b'', 0))

    def test_fragmented_network_writes(self):
        packet = struct.pack('!I', 7) + b'abcdefg'
        def send_fragments():
            for byte in packet:
                self.writer.sendall(bytes([byte]))
        thread = threading.Thread(target=send_fragments)
        thread.start()
        self.assertEqual(self.read_frame(), (0, b'abcdefg', 7))
        thread.join()

    def test_oversized_frame_is_rejected_without_writing(self):
        self.writer.sendall(struct.pack('!I', 1025))
        self.assertEqual(self.read_frame(1024), (-2, b'', 0))

    def test_truncated_frame_fails(self):
        self.writer.sendall(struct.pack('!I', 9) + b'abc')
        self.writer.shutdown(socket.SHUT_WR)
        self.assertEqual(self.read_frame(), (-1, b'', 0))

    def test_two_processes_exchange_frames_over_tcp(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(listener.close)
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(5)
        script = '''
import ctypes, os, socket, sys
lib=ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
lib.spple_lan_send_frame.argtypes=(ctypes.c_ssize_t,ctypes.c_void_p,ctypes.c_size_t)
s=socket.create_connection(('127.0.0.1',int(sys.argv[1])),timeout=5); s.setblocking(True)
message=ctypes.create_string_buffer(b'child')
assert lib.spple_lan_send_frame(s.fileno(),message,5)==0
s.close()
'''
        child = subprocess.Popen([sys.executable, '-c', script, str(listener.getsockname()[1])])
        try:
            peer, _ = listener.accept()
            with peer:
                output = ctypes.create_string_buffer(16)
                size = ctypes.c_size_t()
                result = library.spple_lan_receive_frame(peer.fileno(), output, len(output), ctypes.byref(size))
                self.assertEqual((result, output.raw[:size.value]), (0, b'child'))
            self.assertEqual(child.wait(timeout=5), 0)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()


if __name__ == '__main__':
    unittest.main()
