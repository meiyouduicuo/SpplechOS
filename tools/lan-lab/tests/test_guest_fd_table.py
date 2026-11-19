"""Sockets and event descriptors cannot collide or reuse a borrowed slot."""
import ctypes
import os
import unittest

lib = ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
Destroy = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)


class Borrow(ctypes.Structure):
    _fields_ = [('fd', ctypes.c_int), ('generation', ctypes.c_uint64), ('object', ctypes.c_void_p)]


lib.spple_fd_table_create.argtypes = [Destroy, ctypes.c_void_p]
lib.spple_fd_table_create.restype = ctypes.c_void_p
lib.spple_fd_table_destroy.argtypes = [ctypes.c_void_p]
lib.spple_fd_alloc.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
lib.spple_fd_acquire.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(Borrow)]
lib.spple_fd_release.argtypes = [ctypes.c_void_p, ctypes.POINTER(Borrow)]
lib.spple_fd_close.argtypes = [ctypes.c_void_p, ctypes.c_int]


class GuestFdTests(unittest.TestCase):
    def setUp(self):
        self.destroyed = []
        self.callback = Destroy(lambda ctx, kind, obj: self.destroyed.append((kind, obj)))
        self.table = lib.spple_fd_table_create(self.callback, None)
        self.assertTrue(self.table)

    def tearDown(self):
        self.assertEqual(lib.spple_fd_table_destroy(self.table), 0)

    def test_closing_borrowed_socket_delays_reuse_and_destruction(self):
        socket_fd = lib.spple_fd_alloc(self.table, 1, 0x1111)
        event_fd = lib.spple_fd_alloc(self.table, 2, 0x2222)
        self.assertEqual((socket_fd, event_fd), (0, 1))
        borrow = Borrow()
        self.assertEqual(lib.spple_fd_acquire(self.table, socket_fd, 1, ctypes.byref(borrow)), 0)
        stale = Borrow.from_buffer_copy(borrow)
        self.assertEqual(lib.spple_fd_close(self.table, socket_fd), 0)
        self.assertEqual(lib.spple_fd_acquire(self.table, socket_fd, 1, ctypes.byref(Borrow())), -1)
        self.assertEqual(lib.spple_fd_table_destroy(self.table), -1)
        self.assertEqual(lib.spple_fd_alloc(self.table, 1, 0x3333), 2)
        self.assertEqual(lib.spple_fd_release(self.table, ctypes.byref(borrow)), 0)
        self.assertEqual(self.destroyed, [(1, 0x1111)])
        self.assertEqual(lib.spple_fd_alloc(self.table, 1, 0x4444), 0)
        self.assertEqual(lib.spple_fd_release(self.table, ctypes.byref(stale)), -1)
        self.assertEqual(lib.spple_fd_close(self.table, event_fd), 0)
        self.assertIn((2, 0x2222), self.destroyed)

    def test_invalid_kind_and_exhaustion(self):
        self.assertEqual(lib.spple_fd_alloc(self.table, 0, 1), -1)
        for i in range(1024):
            self.assertEqual(lib.spple_fd_alloc(self.table, 1, i + 1), i)
        self.assertEqual(lib.spple_fd_alloc(self.table, 1, 9999), -1)
        borrow = Borrow()
        self.assertEqual(lib.spple_fd_acquire(self.table, 5, 2, ctypes.byref(borrow)), -1)


if __name__ == '__main__':
    unittest.main()
