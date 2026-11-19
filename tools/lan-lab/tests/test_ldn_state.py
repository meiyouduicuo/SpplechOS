"""Verify state transitions against async success, failure and stale callbacks."""
import ctypes
import os
import unittest

library = ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])


class State(ctypes.Structure):
    _fields_ = [('state', ctypes.c_int), ('pending_op', ctypes.c_int),
                ('generation', ctypes.c_uint64), ('pending', ctypes.c_int)]


library.spple_ldn_init.argtypes = [ctypes.POINTER(State)]
library.spple_ldn_begin.argtypes = [ctypes.POINTER(State), ctypes.c_int, ctypes.POINTER(ctypes.c_uint64)]
library.spple_ldn_complete.argtypes = [ctypes.POINTER(State), ctypes.c_uint64, ctypes.c_int]
library.spple_ldn_finalize.argtypes = [ctypes.POINTER(State)]


class StateTests(unittest.TestCase):
    def setUp(self):
        self.s = State()
        self.assertEqual(library.spple_ldn_init(ctypes.byref(self.s)), 0)

    def begin(self, op):
        token = ctypes.c_uint64()
        self.assertEqual(library.spple_ldn_begin(ctypes.byref(self.s), op, ctypes.byref(token)), 0)
        return token.value

    def complete(self, token, ok=True):
        return library.spple_ldn_complete(ctypes.byref(self.s), token, ok)

    def test_host_creation_waits_for_real_completion(self):
        t = self.begin(0)
        self.assertEqual(self.s.state, 1)
        self.assertEqual(self.complete(t), 0)
        self.assertEqual(self.s.state, 2)
        t = self.begin(2)
        self.assertEqual(self.s.state, 2)
        self.assertEqual(self.complete(t, False), 0)
        self.assertEqual(self.s.state, 2)
        self.assertEqual(self.complete(self.begin(2)), 0)
        self.assertEqual(self.s.state, 3)
        self.assertEqual(self.complete(self.begin(4)), 0)
        self.assertEqual(self.s.state, 2)

    def test_station_and_disconnected_old_completion(self):
        self.assertEqual(self.complete(self.begin(1)), 0)
        t = self.begin(3)
        self.assertEqual(library.spple_ldn_finalize(ctypes.byref(self.s)), 0)
        self.assertEqual(self.complete(t), -1)
        self.assertEqual(self.s.state, 0)
        self.assertEqual(library.spple_ldn_init(ctypes.byref(self.s)), 0)
        self.assertEqual(self.complete(self.begin(1)), 0)
        self.assertEqual(self.complete(self.begin(3)), 0)
        self.assertEqual(self.s.state, 5)
        self.assertEqual(self.complete(self.begin(5)), 0)
        self.assertEqual(self.s.state, 4)

    def test_invalid_and_overlapping_operations_fail(self):
        token = ctypes.c_uint64()
        self.assertEqual(library.spple_ldn_begin(ctypes.byref(self.s), 2, ctypes.byref(token)), -1)
        t = self.begin(0)
        self.assertEqual(library.spple_ldn_begin(ctypes.byref(self.s), 1, ctypes.byref(token)), -1)
        self.assertEqual(self.complete(t + 1), -1)
        self.assertEqual(self.s.state, 1)


if __name__ == '__main__':
    unittest.main()
