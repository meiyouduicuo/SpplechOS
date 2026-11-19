"""Route virtual UDP packets over actual connected TCP sockets."""
import ctypes
import os
import socket
import unittest

lib = ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
IP = ctypes.c_uint8 * 4
Session = ctypes.c_uint8 * 16
Send = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t)


class Tunnel(ctypes.Structure):
    _fields_ = [('socket', ctypes.c_ssize_t), ('title_id', ctypes.c_uint64),
                ('session_id', Session), ('udp', ctypes.c_void_p)]


lib.spple_lan_tunnel_init.argtypes = [ctypes.POINTER(Tunnel), ctypes.c_ssize_t, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint8)]
lib.spple_lan_tunnel_attach_udp.argtypes = [ctypes.POINTER(Tunnel), ctypes.c_void_p]
lib.spple_lan_tunnel_pump.argtypes = [ctypes.POINTER(Tunnel)]
lib.spple_vudp_create.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint8), Send, ctypes.c_void_p]
lib.spple_vudp_create.restype = ctypes.c_void_p
lib.spple_vudp_destroy.argtypes = [ctypes.c_void_p]
lib.spple_vudp_socket.argtypes = [ctypes.c_void_p]
lib.spple_vudp_bind.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint16]
lib.spple_vudp_send.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint16,
                                ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t]
lib.spple_vudp_receive.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint16)]


class TunnelTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = socket.socketpair()
        self.addCleanup(self.a.close); self.addCleanup(self.b.close)
        self.ip_a, self.ip_b = IP(10, 77, 0, 1), IP(10, 77, 0, 2)
        self.session = Session(*range(1, 17))
        self.ta, self.tb = Tunnel(), Tunnel()
        title = 0x0100559011740000
        self.assertEqual(lib.spple_lan_tunnel_init(ctypes.byref(self.ta), self.a.fileno(), title, self.session), 0)
        self.assertEqual(lib.spple_lan_tunnel_init(ctypes.byref(self.tb), self.b.fileno(), title, self.session), 0)
        self.callback = Send(('spple_lan_tunnel_send', lib))
        self.ua = lib.spple_vudp_create(self.ip_a, self.ip_b, self.callback, ctypes.byref(self.ta))
        self.ub = lib.spple_vudp_create(self.ip_b, self.ip_a, self.callback, ctypes.byref(self.tb))
        self.assertTrue(self.ua and self.ub)
        self.addCleanup(lib.spple_vudp_destroy, self.ua); self.addCleanup(lib.spple_vudp_destroy, self.ub)
        self.assertEqual(lib.spple_lan_tunnel_attach_udp(ctypes.byref(self.ta), self.ua), 0)
        self.assertEqual(lib.spple_lan_tunnel_attach_udp(ctypes.byref(self.tb), self.ub), 0)
        self.fa = lib.spple_vudp_socket(self.ua); self.fb = lib.spple_vudp_socket(self.ub)
        self.assertEqual(lib.spple_vudp_bind(self.ua, self.fa, 4444), 0)
        self.assertEqual(lib.spple_vudp_bind(self.ub, self.fb, 4444), 0)

    def test_game_datagram_traverses_real_stream(self):
        data = ctypes.create_string_buffer(b'quest')
        self.assertEqual(lib.spple_vudp_send(self.ua, self.fa, self.ip_b, 4444, 0, data, 5), 0)
        self.assertEqual(lib.spple_lan_tunnel_pump(ctypes.byref(self.tb)), 0)
        out = ctypes.create_string_buffer(16); ip = IP(); port = ctypes.c_uint16()
        n = lib.spple_vudp_receive(self.ub, self.fb, out, len(out), ip, ctypes.byref(port))
        self.assertEqual((n, out.raw[:n], bytes(ip), port.value), (5, b'quest', bytes(self.ip_a), 4444))

    def test_wrong_session_cannot_deliver(self):
        self.tb.session_id[0] ^= 1
        data = ctypes.create_string_buffer(b'x')
        self.assertEqual(lib.spple_vudp_send(self.ua, self.fa, self.ip_b, 4444, 0, data, 1), 0)
        self.assertEqual(lib.spple_lan_tunnel_pump(ctypes.byref(self.tb)), -1)
        out = ctypes.create_string_buffer(16); ip = IP(); port = ctypes.c_uint16()
        self.assertEqual(lib.spple_vudp_receive(self.ub, self.fb, out, len(out), ip, ctypes.byref(port)), -2)


if __name__ == '__main__':
    unittest.main()
