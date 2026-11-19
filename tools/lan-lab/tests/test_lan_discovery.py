"""Exercise discovery callbacks and ownership against a fake DNS-SD backend."""
import ctypes
import os
import socket
import unittest

lib = ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
Browse = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint32,
                          ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p)
Resolve = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint16)
Registered = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int)
lib.spple_discovery_advertise.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p, ctypes.c_uint16]
lib.spple_discovery_advertise_observed.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p, ctypes.c_uint16,
                                                   Registered, ctypes.c_void_p]
lib.spple_discovery_browse.argtypes = [ctypes.POINTER(ctypes.c_void_p), Browse, ctypes.c_void_p]
lib.spple_discovery_resolve.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint32, ctypes.c_char_p,
                                        ctypes.c_char_p, ctypes.c_char_p, Resolve, ctypes.c_void_p]
lib.spple_discovery_fd.argtypes = [ctypes.c_void_p]
lib.spple_discovery_process.argtypes = [ctypes.c_void_p]
lib.spple_discovery_stop.argtypes = [ctypes.c_void_p]
lib.fake_emit_resolve.argtypes = [ctypes.c_uint16]


class DiscoveryTests(unittest.TestCase):
    def tearDown(self):
        self.assertEqual(lib.fake_active(), 0)

    def test_advertise_uses_network_order_and_releases(self):
        op = ctypes.c_void_p()
        self.assertEqual(lib.spple_discovery_advertise(ctypes.byref(op), b'room', 42500), 0)
        self.assertEqual(lib.fake_port(), socket.htons(42500))
        self.assertEqual(lib.spple_discovery_fd(op), 42)
        self.assertEqual(lib.spple_discovery_process(op), 0)
        lib.spple_discovery_stop(op)

    def test_registration_reports_permission_error_then_success(self):
        events = []
        callback = Registered(lambda ctx, error: events.append(error))
        op = ctypes.c_void_p()
        self.assertEqual(lib.spple_discovery_advertise_observed(ctypes.byref(op), b'room', 42500, callback, None), 0)
        lib.fake_emit_register(-65570)
        lib.spple_discovery_stop(op)
        op = ctypes.c_void_p()
        self.assertEqual(lib.spple_discovery_advertise_observed(ctypes.byref(op), b'room', 42500, callback, None), 0)
        lib.fake_emit_register(0)
        lib.spple_discovery_stop(op)
        self.assertEqual(events, [-65570, 0])

    def test_browse_and_resolve_callbacks(self):
        events = []
        callback = Browse(lambda ctx, err, added, idx, name, typ, domain:
                          events.append((err, added, idx, name, typ, domain)))
        op = ctypes.c_void_p()
        self.assertEqual(lib.spple_discovery_browse(ctypes.byref(op), callback, None), 0)
        lib.fake_emit_browse(1)
        lib.fake_emit_browse(0)
        self.assertEqual([event[1] for event in events], [1, 0])
        lib.spple_discovery_stop(op)
        resolved = []
        cb = Resolve(lambda ctx, err, idx, host, port: resolved.append((err, idx, host, port)))
        op = ctypes.c_void_p()
        self.assertEqual(lib.spple_discovery_resolve(ctypes.byref(op), 7, b'room',
                         b'_spplechos-ldn._tcp.', b'local.', cb, None), 0)
        lib.fake_emit_resolve(socket.htons(42500))
        self.assertEqual(resolved, [(0, 7, b'host.local.', 42500)])
        lib.spple_discovery_stop(op)

    def test_rejects_unrelated_service_type(self):
        op = ctypes.c_void_p()
        cb = Resolve(lambda *args: None)
        self.assertEqual(lib.spple_discovery_resolve(ctypes.byref(op), 0, b'x', b'_other._tcp',
                                                    b'local.', cb, None), -1)
        self.assertFalse(op.value)


if __name__ == '__main__':
    unittest.main()
