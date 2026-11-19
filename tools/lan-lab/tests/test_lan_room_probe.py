import ctypes as c
import os,socket,threading,unittest
from test_ldn_rooms import room
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
for name in ('client','server'):
 f=getattr(L,'spple_lan_room_probe_'+name);f.argtypes=[c.c_ssize_t,c.c_uint64,c.c_void_p]
class ProbeTests(unittest.TestCase):
 def test_fetch_room_after_handshake(self):
  a,b=socket.socketpair();self.addCleanup(a.close);self.addCleanup(b.close)
  result=[];src=room();out=c.create_string_buffer(0x480)
  t=threading.Thread(target=lambda:result.append(L.spple_lan_room_probe_server(a.fileno(),123,src)))
  t.start();self.assertEqual(L.spple_lan_room_probe_client(b.fileno(),123,out),0);t.join(3)
  self.assertFalse(t.is_alive());self.assertEqual(result,[0]);self.assertEqual(out.raw[:0x480],src.raw[:0x480])
 def test_other_game_never_receives_room(self):
  a,b=socket.socketpair();self.addCleanup(a.close);self.addCleanup(b.close);result=[]
  def serve():
   result.append(L.spple_lan_room_probe_server(a.fileno(),123,room()));a.shutdown(socket.SHUT_WR)
  t=threading.Thread(target=serve);t.start();out=c.create_string_buffer(b'x'*0x480,0x480)
  self.assertEqual(L.spple_lan_room_probe_client(b.fileno(),124,out),-1);t.join(3)
  self.assertEqual(result,[-1]);self.assertEqual(out.raw,b'x'*0x480)
if __name__=='__main__':unittest.main()
