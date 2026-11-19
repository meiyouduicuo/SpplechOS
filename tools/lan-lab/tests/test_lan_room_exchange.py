import ctypes as c
import os,socket,threading,unittest
from test_ldn_rooms import room
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
L.spple_room_exchange_client.argtypes=[c.c_ssize_t,c.c_uint64,c.c_int,c.c_void_p]
L.spple_room_exchange_server.argtypes=[c.c_ssize_t,c.c_uint64,c.c_void_p,c.POINTER(c.c_int)]
class RoomExchangeTests(unittest.TestCase):
 def test_probe_and_join_are_distinct(self):
  for mode in (1,2):
   with self.subTest(mode=mode):
    a,b=socket.socketpair();self.addCleanup(a.close);self.addCleanup(b.close)
    src=room();out=c.create_string_buffer(0x480);server_mode=c.c_int();result=[]
    t=threading.Thread(target=lambda:result.append(L.spple_room_exchange_server(a.fileno(),123,src,c.byref(server_mode))))
    t.start();self.assertEqual(L.spple_room_exchange_client(b.fileno(),123,mode,out),0);t.join(3)
    self.assertFalse(t.is_alive());self.assertEqual(result,[0]);self.assertEqual(server_mode.value,mode)
    self.assertEqual(out.raw[:0x480],src.raw[:0x480])
 def test_invalid_mode_fails_before_network_access(self):
  out=c.create_string_buffer(0x480);self.assertEqual(L.spple_room_exchange_client(-1,123,3,out),-1)
if __name__=='__main__':unittest.main()
