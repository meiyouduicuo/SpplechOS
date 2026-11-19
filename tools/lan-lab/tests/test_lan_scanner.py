import ctypes as c
import os,socket,unittest
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
Found=c.CFUNCTYPE(None,c.c_void_p,c.c_char_p,c.c_uint32,c.c_uint64,c.c_char_p,c.c_uint16)
Removed=c.CFUNCTYPE(None,c.c_void_p,c.c_char_p,c.c_uint32,c.c_uint64)
L.spple_lan_scanner_new.argtypes=[c.c_uint64,Found,Removed,c.c_void_p];L.spple_lan_scanner_new.restype=c.c_void_p
L.spple_lan_scanner_tick.argtypes=[c.c_void_p,c.c_uint64,c.c_int,c.c_int]
L.spple_lan_scanner_fds.argtypes=[c.c_void_p,c.POINTER(c.c_int),c.POINTER(c.c_int)]
L.spple_lan_scanner_free.argtypes=[c.c_void_p]
L.fake_emit_browse.argtypes=[c.c_int];L.fake_emit_resolve.argtypes=[c.c_uint16]
class ScannerTests(unittest.TestCase):
 def setUp(self):
  self.found=[];self.removed=[]
  self.fc=Found(lambda _,name,index,gen,host,port:self.found.append((name,index,gen,host,port)))
  self.rc=Removed(lambda _,name,index,gen:self.removed.append((name,index,gen)))
  self.s=L.spple_lan_scanner_new(0,self.fc,self.rc,None);self.assertTrue(self.s);self.addCleanup(L.spple_lan_scanner_free,self.s)
 def tick(self,now):self.assertEqual(L.spple_lan_scanner_tick(self.s,now,0,0),0)
 def test_discovery_resolve_remove_and_generation(self):
  self.tick(0);L.fake_emit_browse(1);self.tick(1);L.fake_emit_resolve(socket.htons(1234));self.tick(2);L.fake_emit_address();self.tick(3)
  self.assertEqual(self.found,[(b'room',7,1,b'127.0.0.1',1234)])
  L.fake_emit_browse(0);self.assertEqual(self.removed,[(b'room',7,1)])
  L.fake_emit_browse(1);self.tick(4);L.fake_emit_resolve(socket.htons(1234));self.tick(5);L.fake_emit_address();self.tick(6)
  self.assertEqual(self.found[-1][2],2)
 def test_stalled_resolver_retries_and_removed_room_is_not_returned(self):
  self.tick(0);L.fake_emit_browse(1);self.tick(1)
  self.tick(5001);a,b=c.c_int(),c.c_int();L.spple_lan_scanner_fds(self.s,c.byref(a),c.byref(b));self.assertEqual(b.value,-1)
  self.tick(6001);L.spple_lan_scanner_fds(self.s,c.byref(a),c.byref(b));self.assertEqual(b.value,42)
  L.fake_emit_browse(0);L.fake_emit_resolve(socket.htons(1234));self.tick(6002)
  self.assertEqual(self.found,[]);self.assertEqual(self.removed,[(b'room',7,1)])
if __name__=='__main__':unittest.main()
