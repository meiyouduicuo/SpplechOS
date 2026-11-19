import ctypes as c
import multiprocessing as mp
import os,socket,threading,time,unittest

def exercise(queue,ready):
 try:
  L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY']);IP=c.c_uint8*4;Session=c.c_uint8*16
  Send=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_size_t);Reserve=c.CFUNCTYPE(c.c_int,c.c_void_p);Release=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_int);Notify=c.CFUNCTYPE(None,c.c_void_p);Fail=c.CFUNCTYPE(None,c.c_void_p)
  L.spple_vudp_create.argtypes=[c.POINTER(c.c_uint8),c.POINTER(c.c_uint8),Send,c.c_void_p];L.spple_vudp_create.restype=c.c_void_p;L.spple_vudp_destroy.argtypes=[c.c_void_p]
  L.spple_guest_udp_new.argtypes=[c.c_void_p,Reserve,Release,Notify,c.c_void_p];L.spple_guest_udp_new.restype=c.c_void_p;L.spple_guest_udp_free.argtypes=[c.c_void_p]
  L.spple_guest_socket_bridge_init.argtypes=[c.c_void_p];L.spple_guest_socket_bridge_init.restype=c.c_void_p
  L.spple_lan_connection_start.argtypes=[c.c_ssize_t,c.c_uint64,c.POINTER(c.c_uint8),c.POINTER(c.c_uint8),c.POINTER(c.c_uint8),Fail,c.c_void_p];L.spple_lan_connection_start.restype=c.c_void_p
  L.spple_lan_connection_ready.argtypes=[c.c_void_p];L.spple_lan_connection_destroy.argtypes=[c.c_void_p]
  send=Send(lambda *_:0);reserve=Reserve(lambda _:0);release=Release(lambda *_:0);notify=Notify(lambda _:None)
  local,peer=IP(10,77,0,1),IP(10,77,0,2);udp=L.spple_vudp_create(local,peer,send,None);g=L.spple_guest_udp_new(udp,reserve,release,notify,None)
  assert L.spple_guest_socket_bridge_init(g);L.spple_guest_socket_bridge_stop()
  a,b=socket.socketpair();failed=threading.Event();calls=[];cb=Fail(lambda _:(calls.append(1),failed.set()))
  session=Session(*range(1,17));conn=L.spple_lan_connection_start(a.fileno(),123,session,local,peer,cb,None);assert conn;a.detach()
  b.shutdown(socket.SHUT_RDWR);time.sleep(.15);assert not failed.is_set()
  if ready:L.spple_lan_connection_ready(conn);assert failed.wait(3)
  L.spple_lan_connection_destroy(conn);L.spple_guest_udp_free(g);L.spple_vudp_destroy(udp);b.close()
  queue.put(('ok',calls))
 except BaseException as e:queue.put(('error',repr(e)))
class ConnectionTests(unittest.TestCase):
 def test_failure_is_deferred_until_room_is_published(self):
  ctx=mp.get_context('spawn')
  for ready in (True,False):
   with self.subTest(ready=ready):
    q=ctx.Queue();p=ctx.Process(target=exercise,args=(q,ready));p.start();p.join(10)
    if p.is_alive():p.terminate();p.join();self.fail('connection did not stop')
    self.assertEqual(p.exitcode,0);self.assertEqual(q.get(timeout=2),('ok',[1] if ready else []))
if __name__=='__main__':unittest.main()
