import ctypes as c
import os,unittest
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
IP=c.c_uint8*4
L.spple_guest_sockaddr_decode.argtypes=[c.c_void_p,c.c_size_t,c.POINTER(c.c_uint8),c.POINTER(c.c_uint16)]
L.spple_guest_sockaddr_encode.argtypes=[c.c_void_p,c.POINTER(c.c_uint),c.POINTER(c.c_uint8),c.c_uint16]
class SockaddrTests(unittest.TestCase):
 def test_roundtrip_network_order(self):
  ip=IP(10,77,0,2); data=c.create_string_buffer(16); n=c.c_uint(16)
  self.assertEqual(L.spple_guest_sockaddr_encode(data,c.byref(n),ip,4444),0)
  self.assertEqual(data.raw[:8],bytes([16,2,0x11,0x5c,10,77,0,2]))
  out=IP(); port=c.c_uint16()
  self.assertEqual(L.spple_guest_sockaddr_decode(data,16,out,c.byref(port)),0)
  self.assertEqual(bytes(out),bytes(ip)); self.assertEqual(port.value,4444)
 def test_truncated_output_reports_full_size_without_overrun(self):
  data=c.create_string_buffer(b'xxxxxxxx',8); n=c.c_uint(4)
  self.assertEqual(L.spple_guest_sockaddr_encode(data,c.byref(n),IP(1,2,3,4),10),0)
  self.assertEqual(n.value,16); self.assertEqual(data.raw[4:],b'xxxx')
 def test_rejects_short_or_wrong_family_without_writing_outputs(self):
  data=c.create_string_buffer(bytes([16,3])+bytes(14),16); ip=IP(9,9,9,9); port=c.c_uint16(99)
  for length in (15,16): self.assertEqual(L.spple_guest_sockaddr_decode(data,length,ip,c.byref(port)),-1)
  self.assertEqual(bytes(ip),bytes([9]*4)); self.assertEqual(port.value,99)
if __name__=='__main__': unittest.main()
