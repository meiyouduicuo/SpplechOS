import ctypes as c
import os,unittest
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
L.spple_lan_hmac.argtypes=[c.c_void_p,c.c_size_t,c.c_void_p,c.c_size_t,c.c_void_p]
L.spple_lan_tag_equal.argtypes=[c.c_void_p,c.c_void_p]
class AuthTests(unittest.TestCase):
 def test_hmac_sha256_known_vector_and_constant_time_compare(self):
  key=c.create_string_buffer(bytes([0x0b])*20);data=c.create_string_buffer(b'Hi There');out=c.create_string_buffer(32)
  self.assertEqual(L.spple_lan_hmac(key,20,data,8,out),0)
  self.assertEqual(out.raw.hex(),'b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7')
  good=c.create_string_buffer(out.raw,32);bad=c.create_string_buffer(out.raw[:-1]+b'X',32)
  self.assertEqual(L.spple_lan_tag_equal(out,good),1);self.assertEqual(L.spple_lan_tag_equal(out,bad),0)
 def test_rejects_invalid_inputs(self):
  self.assertEqual(L.spple_lan_hmac(None,16,None,0,c.create_string_buffer(32)),-1)
  self.assertEqual(L.spple_lan_hmac(c.create_string_buffer(15),15,None,0,c.create_string_buffer(32)),-1)
if __name__=='__main__':unittest.main()
