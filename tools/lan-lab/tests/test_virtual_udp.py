"""Two virtual peers exchange guest datagrams without LAN multicast."""
import ctypes
import os
import unittest

lib = ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
IP = ctypes.c_uint8 * 4
Send = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t)
lib.spple_vudp_create.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint8), Send, ctypes.c_void_p]
lib.spple_vudp_create.restype = ctypes.c_void_p
lib.spple_vudp_destroy.argtypes = [ctypes.c_void_p]
lib.spple_vudp_socket.argtypes = [ctypes.c_void_p]
lib.spple_vudp_ready.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.spple_vudp_close.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.spple_vudp_local.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint16)]
lib.spple_vudp_bind.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint16]
lib.spple_vudp_reuseaddr.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
lib.spple_vudp_send.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint16,
                                ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t]
lib.spple_vudp_ingest.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
lib.spple_vudp_receive.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint16)]


class VirtualUdpTests(unittest.TestCase):
    def setUp(self):
        self.ip_a, self.ip_b = IP(10, 77, 0, 1), IP(10, 77, 0, 2)
        self.a = self.b = None
        self.send_a = Send(lambda _, data, size: lib.spple_vudp_ingest(self.b, data, size))
        self.send_b = Send(lambda _, data, size: lib.spple_vudp_ingest(self.a, data, size))
        self.a = lib.spple_vudp_create(self.ip_a, self.ip_b, self.send_a, None)
        self.b = lib.spple_vudp_create(self.ip_b, self.ip_a, self.send_b, None)
        self.assertTrue(self.a and self.b)
        self.addCleanup(lib.spple_vudp_destroy, self.a)
        self.addCleanup(lib.spple_vudp_destroy, self.b)
        self.fa, self.fb = lib.spple_vudp_socket(self.a), lib.spple_vudp_socket(self.b)
        self.assertEqual(lib.spple_vudp_bind(self.a, self.fa, 4444), 0)
        self.assertEqual(lib.spple_vudp_bind(self.b, self.fb, 4444), 0)

    def read(self, endpoint, fd, capacity=100):
        buf = ctypes.create_string_buffer(capacity); source = IP(); port = ctypes.c_uint16()
        n = lib.spple_vudp_receive(endpoint, fd, buf, capacity, source, ctypes.byref(port))
        return n, buf.raw[:max(n, 0)], bytes(source), port.value

    def test_unicast_and_source(self):
        msg = ctypes.create_string_buffer(b'quest')
        self.assertEqual(lib.spple_vudp_send(self.a, self.fa, self.ip_b, 4444, 0, msg, 5), 0)
        self.assertEqual(self.read(self.b, self.fb), (5, b'quest', bytes(self.ip_a), 4444))
        self.assertEqual(self.read(self.a, self.fa)[0], -2)

    def test_readiness_changes_with_receive_and_close(self):
        self.assertEqual(lib.spple_vudp_ready(self.b, self.fb), 4)
        msg=ctypes.create_string_buffer(b'quest')
        self.assertEqual(lib.spple_vudp_send(self.a,self.fa,self.ip_b,4444,0,msg,5),0)
        self.assertEqual(lib.spple_vudp_ready(self.b,self.fb),5)
        self.assertEqual(self.read(self.b,self.fb)[0],5)
        self.assertEqual(lib.spple_vudp_ready(self.b,self.fb),4)
        self.assertEqual(lib.spple_vudp_close(self.b,self.fb),0)
        self.assertEqual(lib.spple_vudp_ready(self.b,self.fb),-1)

    def test_unbound_sender_automatically_gets_ephemeral_port(self):
        fd=lib.spple_vudp_socket(self.a); ip=IP(); port=ctypes.c_uint16()
        msg=ctypes.create_string_buffer(b'x')
        self.assertEqual(lib.spple_vudp_send(self.a,fd,self.ip_b,4444,0,msg,1),0)
        self.assertEqual(lib.spple_vudp_local(self.a,fd,ip,ctypes.byref(port)),0)
        self.assertEqual(bytes(ip),bytes(self.ip_a)); self.assertGreaterEqual(port.value,49152)
        self.assertEqual(self.read(self.b,self.fb),(1,b'x',bytes(self.ip_a),port.value))

    def test_broadcast_reaches_both_peers(self):
        msg = ctypes.create_string_buffer(b'room')
        self.assertEqual(lib.spple_vudp_send(self.a, self.fa, IP(10, 77, 0, 255), 4444, 1, msg, 4), 0)
        self.assertEqual(self.read(self.b, self.fb)[1], b'room')
        self.assertEqual(self.read(self.a, self.fa)[1], b'room')

    def test_reuseaddr_broadcast_delivers_to_each_bound_socket(self):
        second=lib.spple_vudp_socket(self.b)
        self.assertEqual(lib.spple_vudp_reuseaddr(self.b,self.fb,1),0)
        self.assertEqual(lib.spple_vudp_reuseaddr(self.b,second,1),0)
        self.assertEqual(lib.spple_vudp_bind(self.b,second,4444),0)
        msg=ctypes.create_string_buffer(b'room')
        self.assertEqual(lib.spple_vudp_send(self.a,self.fa,IP(10,77,0,255),4444,1,msg,4),0)
        self.assertEqual(self.read(self.b,self.fb)[1],b'room')
        self.assertEqual(self.read(self.b,second)[1],b'room')

    def test_rejects_unrelated_destination_and_duplicate_bind(self):
        self.assertEqual(lib.spple_vudp_send(self.a, self.fa, IP(8, 8, 8, 8), 53, 0, None, 0), -1)
        another = lib.spple_vudp_socket(self.a)
        self.assertEqual(lib.spple_vudp_bind(self.a, another, 4444), -1)

    def test_queue_limit_and_truncation(self):
        msg = ctypes.create_string_buffer(b'long')
        for _ in range(32):
            self.assertEqual(lib.spple_vudp_send(self.a, self.fa, self.ip_b, 4444, 0, msg, 4), 0)
        self.assertEqual(lib.spple_vudp_send(self.a, self.fa, self.ip_b, 4444, 0, msg, 4), 0)
        self.assertEqual(self.read(self.b, self.fb, 2)[1], b'lo')
        self.assertEqual(lib.spple_vudp_send(self.a, self.fa, self.ip_b, 4444, 0, msg, 4), 0)


if __name__ == '__main__':
    unittest.main()
