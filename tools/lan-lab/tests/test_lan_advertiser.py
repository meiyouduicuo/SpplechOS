import ctypes as c
import os,unittest
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
L.spple_lan_advertiser_new.argtypes=[c.c_char_p,c.c_uint16,c.c_uint64];L.spple_lan_advertiser_new.restype=c.c_void_p
L.spple_lan_advertiser_tick.argtypes=[c.c_void_p,c.c_uint64,c.c_int]
L.spple_lan_advertiser_fd.argtypes=[c.c_void_p]
L.spple_lan_advertiser_free.argtypes=[c.c_void_p]
L.fake_emit_register.argtypes=[c.c_int]
class AdvertiserTests(unittest.TestCase):
 def test_permission_failure_retries_without_restart(self):
  a=L.spple_lan_advertiser_new(b'room',1234,0);self.assertTrue(a);self.addCleanup(L.spple_lan_advertiser_free,a)
  self.assertEqual(L.spple_lan_advertiser_tick(a,0,0),0);self.assertEqual(L.spple_lan_advertiser_fd(a),42)
  L.fake_emit_register(-65555);self.assertEqual(L.spple_lan_advertiser_tick(a,1,0),0)
  self.assertEqual(L.spple_lan_advertiser_fd(a),-1);self.assertEqual(L.spple_lan_advertiser_tick(a,1000,0),0)
  self.assertEqual(L.spple_lan_advertiser_tick(a,1001,0),0);L.fake_emit_register(0)
  self.assertEqual(L.spple_lan_advertiser_tick(a,1002,0),1);self.assertEqual(L.spple_lan_advertiser_tick(a,200000,0),1)
  L.fake_emit_register(-65555);self.assertEqual(L.spple_lan_advertiser_tick(a,200001,0),0)
  self.assertEqual(L.spple_lan_advertiser_tick(a,201001,0),0);L.fake_emit_register(0)
  self.assertEqual(L.spple_lan_advertiser_tick(a,201002,0),1)
 def test_missing_response_times_out_and_releases(self):
  a=L.spple_lan_advertiser_new(b'room',1234,0);self.addCleanup(L.spple_lan_advertiser_free,a)
  self.assertEqual(L.spple_lan_advertiser_tick(a,0,0),0);self.assertEqual(L.spple_lan_advertiser_tick(a,120000,0),-1)
  self.assertEqual(L.spple_lan_advertiser_fd(a),-1)
if __name__=='__main__':unittest.main()
