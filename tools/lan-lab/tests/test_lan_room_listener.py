import ctypes as c
import os,socket,threading,unittest
from test_ldn_rooms import room
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
Random=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_size_t)
Accept=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_int,c.c_int,c.c_void_p)
L.spple_room_listener_handle.argtypes=[c.c_ssize_t,c.c_uint64,c.c_void_p,c.c_void_p,c.c_size_t,Random,Accept,c.c_void_p]
L.spple_room_exchange_client.argtypes=[c.c_ssize_t,c.c_uint64,c.c_int,c.c_void_p]
L.spple_secure_join_client.argtypes=[c.c_ssize_t,c.c_uint64,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p,c.c_int,c.c_int,c.c_void_p]
class ListenerTests(unittest.TestCase):
 def test_probe_and_authenticated_join_share_same_listener(self):
  for join in (False,True):
   with self.subTest(join=join):
    a,b=socket.socketpair();self.addCleanup(a.close);self.addCleanup(b.close);base=room();key=c.create_string_buffer(bytes(range(16)))
    calls=[]
    def rand(_,out,n):c.memmove(out,bytes(range(1,n+1)),n);return 0
    def accept(_,user,version,option,out):calls.append(version);c.memmove(out,base,0x480);return 0
    random=Random(rand);acceptor=Accept(accept);result=[]
    t=threading.Thread(target=lambda:result.append(L.spple_room_listener_handle(a.fileno(),123,base,key,16,random,acceptor,None)))
    t.start();out=c.create_string_buffer(0x480)
    if join:
     nonce=c.create_string_buffer(bytes(range(17,33)));user=c.create_string_buffer(bytes(48))
     rc=L.spple_secure_join_client(b.fileno(),123,key,16,nonce,user,7,0,out)
    else:rc=L.spple_room_exchange_client(b.fileno(),123,1,out)
    t.join(3);self.assertFalse(t.is_alive());self.assertEqual(rc,0)
    self.assertEqual(result,[2 if join else 1]);self.assertEqual(calls,[7] if join else [])
if __name__=='__main__':unittest.main()
