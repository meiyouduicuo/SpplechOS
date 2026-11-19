import ctypes as c
import os,socket,threading,unittest
from test_ldn_rooms import room
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
Ingest=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_size_t)
Failure=c.CFUNCTYPE(None,c.c_void_p)
Room=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p)
Session=c.c_uint8*16
L.spple_lan_io_start.argtypes=[c.c_ssize_t,c.c_uint64,c.POINTER(c.c_uint8),Ingest,Failure,c.c_void_p];L.spple_lan_io_start.restype=c.c_void_p
L.spple_lan_io_send.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t]
L.spple_lan_io_start_ex.argtypes=[c.c_ssize_t,c.c_uint64,c.POINTER(c.c_uint8),Ingest,Room,Failure,c.c_void_p];L.spple_lan_io_start_ex.restype=c.c_void_p
L.spple_lan_io_send_room.argtypes=[c.c_void_p,c.c_void_p]
L.spple_lan_io_stop.argtypes=[c.c_void_p];L.spple_lan_io_destroy.argtypes=[c.c_void_p]
class IoTests(unittest.TestCase):
 def test_room_changes_are_delivered_without_stopping_datagrams(self):
  a,b=socket.socketpair();self.addCleanup(a.close);self.addCleanup(b.close)
  event=threading.Event();updates=[];ingest=Ingest(lambda *_:0);failure=Failure(lambda _:None)
  def on_room(_,info):updates.append(c.string_at(info,0x480));event.set();return 0
  callback=Room(on_room);session=Session(*([1]*16));src=room()
  ia=L.spple_lan_io_start_ex(a.fileno(),123,session,ingest,callback,failure,None)
  ib=L.spple_lan_io_start_ex(b.fileno(),123,session,ingest,callback,failure,None)
  self.assertTrue(ia and ib)
  try:
   self.assertEqual(L.spple_lan_io_send_room(ia,src),0);self.assertTrue(event.wait(5))
   self.assertEqual(updates[0][:0x480],src.raw[:0x480])
  finally:L.spple_lan_io_stop(ia);L.spple_lan_io_stop(ib);L.spple_lan_io_destroy(ia);L.spple_lan_io_destroy(ib)
 def test_two_stream_workers_exchange_both_directions(self):
  a,b=socket.socketpair(); self.addCleanup(a.close);self.addCleanup(b.close)
  received=[[],[]]; events=[threading.Event(),threading.Event()]; failures=[]
  def receive(index):
   def cb(_,packet,size): received[index].append(c.string_at(packet,size));events[index].set();return 0
   return Ingest(cb)
  ca,cb=receive(0),receive(1); fail=Failure(lambda _:failures.append(1)); session=Session(*range(1,17))
  ia=L.spple_lan_io_start(a.fileno(),123,session,ca,fail,None); ib=L.spple_lan_io_start(b.fileno(),123,session,cb,fail,None)
  self.assertTrue(ia and ib)
  try:
   pa=c.create_string_buffer(b'hello');pb=c.create_string_buffer(b'world')
   self.assertEqual(L.spple_lan_io_send(ia,pa,5),0);self.assertEqual(L.spple_lan_io_send(ib,pb,5),0)
   self.assertTrue(events[0].wait(5));self.assertTrue(events[1].wait(5))
   self.assertEqual(received,[[b'world'],[b'hello']])
  finally:
   L.spple_lan_io_stop(ia);L.spple_lan_io_stop(ib);L.spple_lan_io_destroy(ia);L.spple_lan_io_destroy(ib)
 def test_disconnect_notifies_and_disables_send(self):
  a,b=socket.socketpair();self.addCleanup(a.close);self.addCleanup(b.close)
  event=threading.Event(); calls=[]; cb=Ingest(lambda *_:0)
  def failure(_):calls.append(1);event.set()
  fail=Failure(failure);session=Session(*range(1,17)); io=L.spple_lan_io_start(a.fileno(),123,session,cb,fail,None)
  self.assertTrue(io)
  try:
   b.shutdown(socket.SHUT_RDWR);self.assertTrue(event.wait(5));msg=c.create_string_buffer(b'x')
   self.assertEqual(L.spple_lan_io_send(io,msg,1),-1)
  finally:L.spple_lan_io_stop(io);L.spple_lan_io_destroy(io)
  self.assertEqual(calls,[1])
if __name__=='__main__': unittest.main()
