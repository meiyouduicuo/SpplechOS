"""Two isolated game backends exchange guest UDP over a real TCP stream."""
import ctypes as c
import multiprocessing as mp
import os,socket,threading,unittest

def peer(control, host, port):
 try:
  L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
  IP=c.c_uint8*4; Session=c.c_uint8*16
  Ingest=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_size_t)
  Failure=c.CFUNCTYPE(None,c.c_void_p)
  Accept=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_int,c.c_int,c.c_void_p)
  Send=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_size_t)
  Reserve=c.CFUNCTYPE(c.c_int,c.c_void_p);Release=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_int);Notify=c.CFUNCTYPE(None,c.c_void_p)
  L.spple_lan_io_start.argtypes=[c.c_ssize_t,c.c_uint64,c.POINTER(c.c_uint8),Ingest,Failure,c.c_void_p];L.spple_lan_io_start.restype=c.c_void_p
  L.spple_lan_io_send.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t];L.spple_lan_io_destroy.argtypes=[c.c_void_p]
  L.spple_secure_join_server.argtypes=[c.c_ssize_t,c.c_uint64,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p,Accept,c.c_void_p]
  L.spple_secure_join_client.argtypes=[c.c_ssize_t,c.c_uint64,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p,c.c_int,c.c_int,c.c_void_p]
  L.spple_ldn_room_add_station.argtypes=[c.c_void_p,c.c_void_p,c.c_int,c.c_void_p,c.c_void_p,c.c_void_p]
  L.spple_guest_socket_bridge_ingest.argtypes=[c.c_void_p,c.c_size_t]
  L.spple_vudp_create.argtypes=[c.POINTER(c.c_uint8),c.POINTER(c.c_uint8),Send,c.c_void_p];L.spple_vudp_create.restype=c.c_void_p
  L.spple_vudp_destroy.argtypes=[c.c_void_p]
  L.spple_guest_udp_new.argtypes=[c.c_void_p,Reserve,Release,Notify,c.c_void_p];L.spple_guest_udp_new.restype=c.c_void_p
  L.spple_guest_udp_free.argtypes=[c.c_void_p]
  Sock=c.CFUNCTYPE(c.c_int,c.c_int,c.c_int,c.c_int,c.POINTER(c.c_int))
  Bind=c.CFUNCTYPE(c.c_int,c.c_int,c.c_void_p,c.c_uint,c.POINTER(c.c_int))
  SendTo=c.CFUNCTYPE(c.c_long,c.c_int,c.c_void_p,c.c_ulong,c.c_int,c.c_void_p,c.c_uint,c.POINTER(c.c_int))
  RecvFrom=c.CFUNCTYPE(c.c_long,c.c_int,c.c_void_p,c.c_ulong,c.c_int,c.c_void_p,c.POINTER(c.c_uint),c.POINTER(c.c_int))
  class Backend(c.Structure):
   _fields_=[('owns',c.CFUNCTYPE(c.c_int,c.c_int)),('socket',Sock),('bind',Bind),('sendto',SendTo),('recvfrom',RecvFrom),('close',c.CFUNCTYPE(c.c_int,c.c_int,c.POINTER(c.c_int)))]
  L.spple_guest_socket_bridge_init.argtypes=[c.c_void_p];L.spple_guest_socket_bridge_init.restype=c.POINTER(Backend)
  L.spple_guest_socket_open.argtypes=[c.c_void_p,c.c_int,c.c_int,c.c_int,c.POINTER(c.c_int)]
  L.spple_guest_socket_bind.argtypes=[c.c_void_p,c.c_int,c.c_void_p,c.c_uint,c.POINTER(c.c_int)]
  L.spple_guest_socket_sendto.argtypes=[c.c_void_p,c.c_int,c.c_void_p,c.c_ulong,c.c_int,c.c_void_p,c.c_uint,c.POINTER(c.c_int)]
  L.spple_guest_socket_recvfrom.argtypes=[c.c_void_p,c.c_int,c.c_void_p,c.c_ulong,c.c_int,c.c_void_p,c.POINTER(c.c_uint),c.POINTER(c.c_int)]
  used=set(); received=threading.Event(); io_ref=[None]
  def reserve(_):
   for n in range(64):
    if n not in used: used.add(n);return n
   return -1
  def release(_,fd):
   if fd not in used:return -1
   used.remove(fd);return 0
  res=Reserve(reserve);rel=Release(release);notify=Notify(lambda _:received.set())
  send=Send(lambda _,p,n:L.spple_lan_io_send(io_ref[0],p,n))
  ingest=Ingest(lambda _,p,n:L.spple_guest_socket_bridge_ingest(p,n));failure=Failure(lambda _:None)
  sock=socket.create_connection(('127.0.0.1',port),timeout=5);sock.settimeout(None)
  from test_ldn_rooms import room
  session=Session(*([1]*16));base=room();key=c.create_string_buffer(bytes(range(16)))
  host_nonce=c.create_string_buffer(bytes(range(1,17)));client_nonce=c.create_string_buffer(bytes(range(17,33)))
  def accept(_,user,version,option,out):
   ip=c.create_string_buffer(bytes([10,77,0,2]));mac=c.create_string_buffer(bytes([10,11,12,13,14,15]))
   return L.spple_ldn_room_add_station(base,user,version,ip,mac,out)
  acceptor=Accept(accept)
  if host: assert L.spple_secure_join_server(sock.fileno(),123,key,16,host_nonce,base,acceptor,None)==0
  else:
   user=c.create_string_buffer(bytes(48));accepted=c.create_string_buffer(0x480)
   assert L.spple_secure_join_client(sock.fileno(),123,key,16,client_nonce,user,1,0,accepted)==0
   assert accepted.raw[0x67]==2
  io=L.spple_lan_io_start(sock.fileno(),123,session,ingest,failure,None);io_ref[0]=io
  local=IP(10,77,0,1 if host else 2);remote=IP(10,77,0,2 if host else 1)
  udp=L.spple_vudp_create(local,remote,send,None); g=L.spple_guest_udp_new(udp,res,rel,notify,None)
  assert io and udp and g
  bridge=L.spple_guest_socket_bridge_init(g);assert bridge
  err=c.c_int();fd=bridge.contents.socket(2,2,0,c.byref(err));assert fd>=0
  bind=c.create_string_buffer(bytes([16,2,0x11,0x5c])+bytes(12),16)
  assert bridge.contents.bind(fd,bind,16,c.byref(err))==0
  control.send('ready'); assert control.recv()=='go'
  msg=c.create_string_buffer(b'host' if host else b'guest')
  dst=c.create_string_buffer(bytes([16,2,0x11,0x5c,10,77,0,2 if host else 1])+bytes(8),16)
  assert bridge.contents.sendto(fd,msg,4 if host else 5,0,dst,16,c.byref(err))>=0
  import time
  deadline=time.monotonic()+5; out=c.create_string_buffer(16);addr=c.create_string_buffer(16)
  while time.monotonic()<deadline:
   size=c.c_uint(16)
   n=bridge.contents.recvfrom(fd,out,16,0x80,addr,c.byref(size),c.byref(err))
   if n>=0:break
   assert err.value==11; received.wait(.05);received.clear()
  else: raise RuntimeError('timed out receiving guest packet')
  control.send((out.raw[:n],addr.raw[4:8]));control.recv()
  L.spple_lan_io_destroy(io); L.spple_guest_udp_free(g);L.spple_vudp_destroy(udp);sock.close()
 except BaseException as e:
  control.send(('error',repr(e)))

class GameTransportTests(unittest.TestCase):
 def test_two_game_processes_send_guest_datagrams(self):
  # Parent acts as byte-forwarding relay, preserving each stream direction.
  ctx=mp.get_context('spawn');listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(2);listener.settimeout(10)
  self.addCleanup(listener.close);port=listener.getsockname()[1]
  pipes=[ctx.Pipe() for _ in range(2)]
  ps=[ctx.Process(target=peer,args=(pipes[i][1],i==0,port)) for i in range(2)]
  for p in ps:p.start()
  connections=[listener.accept()[0] for _ in range(2)]
  def relay(src,dst):
   try:
    while True:
     data=src.recv(65536)
     if not data:break
     dst.sendall(data)
   except OSError:pass
  ts=[threading.Thread(target=relay,args=(connections[i],connections[1-i]),daemon=True) for i in range(2)]
  for t in ts:t.start()
  try:
   for parent,_ in pipes:
    self.assertTrue(parent.poll(15));self.assertEqual(parent.recv(),'ready')
   for parent,_ in pipes:parent.send('go')
   results=[]
   for parent,_ in pipes:
    self.assertTrue(parent.poll(15));results.append(parent.recv())
   self.assertEqual(results,[(b'guest',bytes([10,77,0,2])),(b'host',bytes([10,77,0,1]))])
  finally:
   for parent,_ in pipes:
    try:parent.send('stop')
    except (OSError,EOFError):pass
   for p in ps:
    p.join(5)
    if p.is_alive():p.terminate();p.join(5)
   for connection in connections:connection.close()
  self.assertEqual([p.exitcode for p in ps],[0,0])
if __name__=='__main__':unittest.main()
