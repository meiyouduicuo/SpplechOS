import ctypes as c
import os,socket,threading,unittest
from test_ldn_rooms import room
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
Accept=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_int,c.c_int,c.c_void_p)
L.spple_secure_join_server.argtypes=[c.c_ssize_t,c.c_uint64,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p,Accept,c.c_void_p]
L.spple_secure_join_client.argtypes=[c.c_ssize_t,c.c_uint64,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p,c.c_int,c.c_int,c.c_void_p]
class SecureJoinTests(unittest.TestCase):
 def run_join(self,wrong=False,deny=False):
  a,b=socket.socketpair();self.addCleanup(a.close);self.addCleanup(b.close)
  base=room();user=c.create_string_buffer(bytes(48));user[0:6]=b'Player'
  host_nonce=c.create_string_buffer(bytes(range(1,17)));client_nonce=c.create_string_buffer(bytes(range(17,33)))
  host_key=c.create_string_buffer(bytes(range(16)));client_key=c.create_string_buffer(bytes(range(1,17)) if wrong else bytes(range(16)))
  calls=[]
  def callback(_,user_ptr,version,option,out):
   calls.append((c.string_at(user_ptr,6),version,option))
   if deny:return -1
   c.memmove(out,base,0x480);return 0
  accept=Accept(callback);results=[]
  def server():
   results.append(L.spple_secure_join_server(a.fileno(),123,host_key,16,host_nonce,base,accept,None))
   a.shutdown(socket.SHUT_WR)
  t=threading.Thread(target=server);t.start();out=c.create_string_buffer(b'x'*0x480,0x480)
  rc=L.spple_secure_join_client(b.fileno(),123,client_key,16,client_nonce,user,7,0,out);t.join(5)
  self.assertFalse(t.is_alive());return rc,results,calls,out.raw,base.raw[:0x480]
 def test_matching_key_authenticates_and_preserves_room(self):
  rc,result,calls,out,expected=self.run_join();self.assertEqual((rc,result),(0,[0]));self.assertEqual(calls,[(b'Player',7,0)]);self.assertEqual(out,expected)
 def test_wrong_key_never_reaches_accept(self):
  rc,result,calls,out,_=self.run_join(wrong=True);self.assertEqual((rc,result),(-1,[-1]));self.assertEqual(calls,[]);self.assertEqual(out,b'x'*0x480)
 def test_host_policy_can_reject(self):
  rc,result,calls,out,_=self.run_join(deny=True);self.assertEqual((rc,result),(-1,[-1]));self.assertEqual(len(calls),1);self.assertEqual(out,b'x'*0x480)
if __name__=='__main__':unittest.main()
