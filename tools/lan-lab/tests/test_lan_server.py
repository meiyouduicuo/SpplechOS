import ctypes as c
import os,socket,threading,time,unittest
from test_ldn_rooms import room
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
Snapshot=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p)
Random=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_size_t)
Accept=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_int,c.c_int,c.c_void_p)
Joined=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_ssize_t);Rollback=c.CFUNCTYPE(None,c.c_void_p)
L.spple_lan_server_start.argtypes=[c.c_uint64,c.c_void_p,c.c_size_t,Snapshot,Random,Accept,Joined,Rollback,c.c_void_p];L.spple_lan_server_start.restype=c.c_void_p
L.spple_lan_server_port.argtypes=[c.c_void_p];L.spple_lan_server_port.restype=c.c_uint16
L.spple_lan_server_stop.argtypes=[c.c_void_p];L.spple_lan_server_destroy.argtypes=[c.c_void_p]
L.spple_room_exchange_client.argtypes=[c.c_ssize_t,c.c_uint64,c.c_int,c.c_void_p]
L.spple_secure_join_client.argtypes=[c.c_ssize_t,c.c_uint64,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p,c.c_int,c.c_int,c.c_void_p]
class Endpoint(c.Structure):_fields_=[('host',c.c_char*256),('port',c.c_uint16),('index',c.c_uint32),('generation',c.c_uint64)]
Opened=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_ssize_t,c.c_void_p);Failed=c.CFUNCTYPE(None,c.c_void_p)
L.spple_station_join_start.argtypes=[c.c_uint64,c.POINTER(Endpoint),c.c_void_p,c.c_void_p,c.c_size_t,c.c_void_p,c.c_int,c.c_int,Random,Opened,Failed,c.c_void_p]
L.spple_station_join_start.restype=c.c_void_p
L.spple_station_join_destroy.argtypes=[c.c_void_p]
class ServerTests(unittest.TestCase):
 def setUp(self):
  self.base=room();self.key=c.create_string_buffer(bytes(range(16)));self.joins=[];self.rollbacks=[];self.event=threading.Event()
  def snapshot(_,out):c.memmove(out,self.base,0x480);return 0
  def rand(_,out,n):c.memmove(out,bytes(range(1,n+1)),n);return 0
  def accept(_,user,version,option,out):c.memmove(out,self.base,0x480);return 0
  def joined(_,fd):self.joins.append(fd);socket.socket(fileno=fd).close();self.event.set();return 0
  self.callbacks=(Snapshot(snapshot),Random(rand),Accept(accept),Joined(joined),Rollback(lambda _:self.rollbacks.append(1)))
  self.server=L.spple_lan_server_start(123,self.key,16,*self.callbacks,None);self.assertTrue(self.server)
  self.addCleanup(L.spple_lan_server_destroy,self.server)
  self.port=L.spple_lan_server_port(self.server);self.assertGreater(self.port,0)
 def test_server_probes_and_authenticates_a_real_tcp_connection(self):
  with socket.create_connection(('127.0.0.1',self.port),timeout=3) as s:
   s.settimeout(None);out=c.create_string_buffer(0x480)
   self.assertEqual(L.spple_room_exchange_client(s.fileno(),123,1,out),0)
  self.assertEqual(self.joins,[])
  with socket.create_connection(('127.0.0.1',self.port),timeout=3) as s:
   s.settimeout(None);out=c.create_string_buffer(0x480);nonce=c.create_string_buffer(bytes(range(17,33)));user=c.create_string_buffer(bytes(48))
   self.assertEqual(L.spple_secure_join_client(s.fileno(),123,self.key,16,nonce,user,1,0,out),0)
  self.assertTrue(self.event.wait(3));self.assertEqual(len(self.joins),1);self.assertEqual(self.rollbacks,[])
 def test_stop_during_incomplete_handshake(self):
  with socket.create_connection(('127.0.0.1',self.port),timeout=3):
   started=time.monotonic();L.spple_lan_server_stop(self.server);self.assertLess(time.monotonic()-started,4)
 def test_failed_handoff_rolls_back_accepted_station(self):
  failed=threading.Event();rollbacks=[]
  def reject_handoff(_,fd):return -1
  def rollback(_):rollbacks.append(1);failed.set()
  bad_join=Joined(reject_handoff);undo=Rollback(rollback)
  second=L.spple_lan_server_start(123,self.key,16,*self.callbacks[:3],bad_join,undo,None);self.assertTrue(second)
  try:
   port=L.spple_lan_server_port(second)
   with socket.create_connection(('127.0.0.1',port),timeout=3) as s:
    s.settimeout(None);out=c.create_string_buffer(0x480);nonce=c.create_string_buffer(bytes(range(17,33)));user=c.create_string_buffer(bytes(48))
    self.assertEqual(L.spple_secure_join_client(s.fileno(),123,self.key,16,nonce,user,1,0,out),0)
   self.assertTrue(failed.wait(3));self.assertEqual(rollbacks,[1])
  finally:L.spple_lan_server_destroy(second)
 def test_station_worker_joins_the_selected_room(self):
  event=threading.Event();result=[]
  def opened(_,fd,info):result.append(('ok',c.string_at(info,0x480)));socket.socket(fileno=fd).close();event.set();return 0
  def failed(_):result.append(('failed',None));event.set()
  success=Opened(opened);fail=Failed(failed);endpoint=Endpoint(b'127.0.0.1',self.port,7,1);user=c.create_string_buffer(bytes(48))
  join=L.spple_station_join_start(123,c.byref(endpoint),self.base,self.key,16,user,1,0,self.callbacks[1],success,fail,None)
  self.assertTrue(join)
  try:self.assertTrue(event.wait(5));self.assertEqual(result[0][0],'ok')
  finally:L.spple_station_join_destroy(join)
if __name__=='__main__':unittest.main()
