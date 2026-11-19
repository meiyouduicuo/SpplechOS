"""First-use permission prompts must not require relaunching the application."""
import ctypes
import os
import unittest

lib = ctypes.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])


class Retry(ctypes.Structure):
    _fields_ = [('deadline_ms', ctypes.c_uint64), ('next_ms', ctypes.c_uint64), ('failures', ctypes.c_uint)]


lib.spple_lan_retry_init.argtypes = [ctypes.POINTER(Retry), ctypes.c_uint64, ctypes.c_uint64]
lib.spple_lan_retry_failure.argtypes = [ctypes.POINTER(Retry), ctypes.c_uint64]
lib.spple_lan_retry_ready.argtypes = [ctypes.POINTER(Retry), ctypes.c_uint64]


class RetryTests(unittest.TestCase):
    def test_denied_before_permission_answer_retries_without_restart(self):
        state = Retry()
        lib.spple_lan_retry_init(ctypes.byref(state), 100, 120000)
        self.assertEqual(lib.spple_lan_retry_ready(ctypes.byref(state), 100), 1)
        self.assertEqual(lib.spple_lan_retry_failure(ctypes.byref(state), 100), 0)
        self.assertEqual(lib.spple_lan_retry_ready(ctypes.byref(state), 1099), 0)
        self.assertEqual(lib.spple_lan_retry_ready(ctypes.byref(state), 1100), 1)
        # The user grants access while the app stays open: the next operation can start.
        self.assertEqual(lib.spple_lan_retry_failure(ctypes.byref(state), 1100), 0)
        self.assertEqual(lib.spple_lan_retry_ready(ctypes.byref(state), 3100), 1)
        self.assertEqual(lib.spple_lan_retry_ready(ctypes.byref(state), 120100), -1)

    def test_backoff_is_bounded_and_does_not_overflow(self):
        state = Retry()
        lib.spple_lan_retry_init(ctypes.byref(state), 0, 100000)
        now = 0
        for expected in (1000, 2000, 4000, 8000, 8000):
            self.assertEqual(lib.spple_lan_retry_failure(ctypes.byref(state), now), 0)
            self.assertEqual(state.next_ms - now, expected)
            now = state.next_ms
        lib.spple_lan_retry_init(ctypes.byref(state), (1 << 64) - 50, 500)
        self.assertEqual(state.deadline_ms, (1 << 64) - 1)


if __name__ == '__main__':
    unittest.main()
