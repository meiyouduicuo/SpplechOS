import ctypes as c
import os, threading, unittest
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
IP=c.c_uint8*4
Send=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_size_t)
Reserve=c.CFUNCTYPE(c.c_int,c.c_void_p)
Release=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_int)
Notify=c.CFUNCTYPE(None,c.c_void_p)
L.spple_vudp_create.argtypes=[c.POINTER(c.c_uint8),c.POINTER(c.c_uint8),Send,c.c_void_p]; L.spple_vudp_create.restype=c.c_void_p
L.spple_vudp_destroy.argtypes=[c.c_void_p]
L.spple_guest_udp_new.argtypes=[c.c_void_p,Reserve,Release,Notify,c.c_void_p]; L.spple_guest_udp_new.restype=c.c_void_p
for name,args in {
 'free':[c.c_void_p], 'socket':[c.c_void_p], 'close':[c.c_void_p,c.c_int],
 'bind':[c.c_void_p,c.c_int,c.c_uint16], 'ready':[c.c_void_p,c.c_int],
 'send':[c.c_void_p,c.c_int,c.POINTER(c.c_uint8),c.c_uint16,c.c_int,c.c_void_p,c.c_size_t],
 'receive':[c.c_void_p,c.c_int,c.c_void_p,c.c_size_t,c.POINTER(c.c_uint8),c.POINTER(c.c_uint16)]
}.items(): getattr(L,'spple_guest_udp_'+name).argtypes=args
for name,args in {
 'open':[c.c_void_p,c.c_int,c.c_int,c.c_int,c.POINTER(c.c_int)],
 'bind':[c.c_void_p,c.c_int,c.c_void_p,c.c_uint,c.POINTER(c.c_int)],
 'sendto':[c.c_void_p,c.c_int,c.c_void_p,c.c_ulong,c.c_int,c.c_void_p,c.c_uint,c.POINTER(c.c_int)],
 'recvfrom':[c.c_void_p,c.c_int,c.c_void_p,c.c_ulong,c.c_int,c.c_void_p,c.POINTER(c.c_uint),c.POINTER(c.c_int)]
}.items(): getattr(L,'spple_guest_socket_'+name).argtypes=args
L.spple_guest_socket_sendto.restype=L.spple_guest_socket_recvfrom.restype=c.c_long
SocketFn=c.CFUNCTYPE(c.c_int,c.c_int,c.c_int,c.c_int,c.POINTER(c.c_int))
BindFn=c.CFUNCTYPE(c.c_int,c.c_int,c.c_void_p,c.c_uint,c.POINTER(c.c_int))
SendFn=c.CFUNCTYPE(c.c_long,c.c_int,c.c_void_p,c.c_ulong,c.c_int,c.c_void_p,c.c_uint,c.POINTER(c.c_int))
RecvFn=c.CFUNCTYPE(c.c_long,c.c_int,c.c_void_p,c.c_ulong,c.c_int,c.c_void_p,c.POINTER(c.c_uint),c.POINTER(c.c_int))
class Backend(c.Structure):
 _fields_=[('owns',c.CFUNCTYPE(c.c_int,c.c_int)),('socket',SocketFn),('bind',BindFn),('sendto',SendFn),('recvfrom',RecvFn),('close',c.CFUNCTYPE(c.c_int,c.c_int,c.POINTER(c.c_int))),
 ('getsockname',c.CFUNCTYPE(c.c_int,c.c_int,c.c_void_p,c.POINTER(c.c_uint),c.POINTER(c.c_int))),
 ('setsockopt',c.CFUNCTYPE(c.c_int,c.c_int,c.c_int,c.c_int,c.c_void_p,c.c_uint,c.POINTER(c.c_int))),
 ('getsockopt',c.CFUNCTYPE(c.c_int,c.c_int,c.c_int,c.c_int,c.c_void_p,c.POINTER(c.c_uint),c.POINTER(c.c_int))),
 ('fcntl',c.CFUNCTYPE(c.c_int,c.c_int,c.c_int,c.c_uint64,c.POINTER(c.c_int)))]
L.spple_guest_socket_bridge_init.argtypes=[c.c_void_p]
L.spple_guest_socket_bridge_init.restype=c.POINTER(Backend)
L.spple_guest_socket_bridge_ready.argtypes=[c.c_int]
L.spple_guest_socket_bridge_resume.argtypes=[c.POINTER(c.c_uint8),c.POINTER(c.c_uint8)]
WaitHook=c.CFUNCTYPE(None,c.c_int)
L.spple_guest_socket_bridge_set_wait_hook.argtypes=[WaitHook]
class GuestUdpTests(unittest.TestCase):
 def setUp(self):
    self.used=set(); self.notifies=0
    def reserve(_):
      for i in range(64):
       if i not in self.used: self.used.add(i); return i
      return -1
    def release(_,fd):
      if fd not in self.used:return -1
      self.used.remove(fd); return 0
    def notify(_): self.notifies+=1
    self.reserve,self.release,self.notify=Reserve(reserve),Release(release),Notify(notify)
    self.send=Send(lambda *_:0); self.ip=IP(10,77,0,1)
    self.udp=L.spple_vudp_create(self.ip,IP(10,77,0,2),self.send,None)
    self.g=L.spple_guest_udp_new(self.udp,self.reserve,self.release,self.notify,None)
    self.addCleanup(L.spple_vudp_destroy,self.udp); self.addCleanup(L.spple_guest_udp_free,self.g)
 def test_descriptor_and_readiness_follow_packet_lifecycle(self):
    fd=L.spple_guest_udp_socket(self.g); self.assertEqual(fd,0)
    self.assertEqual(L.spple_guest_udp_ready(self.g,fd),0)
    self.assertEqual(L.spple_guest_udp_bind(self.g,fd,1234),0)
    self.assertEqual(L.spple_guest_udp_ready(self.g,fd),4)
    msg=c.create_string_buffer(b'abc')
    self.assertEqual(L.spple_guest_udp_send(self.g,fd,self.ip,1234,0,msg,3),0)
    self.assertEqual(L.spple_guest_udp_ready(self.g,fd),5)
    out=c.create_string_buffer(8); ip=IP(); port=c.c_uint16()
    self.assertEqual(L.spple_guest_udp_receive(self.g,fd,out,8,ip,c.byref(port)),3)
    self.assertEqual(out.raw[:3],b'abc'); self.assertEqual(L.spple_guest_udp_ready(self.g,fd),4)
    self.assertEqual(L.spple_guest_udp_close(self.g,fd),0)
    self.assertEqual(L.spple_guest_udp_ready(self.g,fd),-1)
    self.assertEqual(self.used,set()); self.assertGreaterEqual(self.notifies,5)
 def test_reserved_number_is_reused_only_after_close(self):
    a=L.spple_guest_udp_socket(self.g); b=L.spple_guest_udp_socket(self.g)
    self.assertEqual((a,b),(0,1)); self.assertEqual(L.spple_guest_udp_close(self.g,a),0)
    self.assertEqual(L.spple_guest_udp_socket(self.g),0)
 # MHR 3.9.1 main+0x5357b08 checks 11 after an empty RecvFrom.
 # Its typed socket path at 0x2076bd0 also maps 11 to retry, 35 to fatal.
 def test_guest_sockaddr_send_and_nonblocking_receive(self):
    err=c.c_int(); fd=L.spple_guest_socket_open(self.g,2,2,0,c.byref(err)); self.assertEqual(fd,0)
    addr=c.create_string_buffer(bytes([16,2,0x04,0xd2])+bytes(12),16)
    self.assertEqual(L.spple_guest_socket_bind(self.g,fd,addr,16,c.byref(err)),0)
    out=c.create_string_buffer(8); peer=c.create_string_buffer(16); length=c.c_uint(16)
    self.assertEqual(L.spple_guest_socket_recvfrom(self.g,fd,out,8,0x80,peer,c.byref(length),c.byref(err)),-1)
    self.assertEqual(err.value,11)
    dest=c.create_string_buffer(bytes([16,2,0x04,0xd2,10,77,0,1])+bytes(8),16)
    message=c.create_string_buffer(b'quest')
    self.assertEqual(L.spple_guest_socket_sendto(self.g,fd,message,5,0,dest,16,c.byref(err)),5)
    self.assertEqual(L.spple_guest_socket_recvfrom(self.g,fd,out,8,0x80,peer,c.byref(length),c.byref(err)),5)
    self.assertEqual(out.raw[:5],b'quest'); self.assertEqual(peer.raw[:8],dest.raw[:8])
 def test_unsupported_features_fail_explicitly(self):
    err=c.c_int(); self.assertEqual(L.spple_guest_socket_open(self.g,2,1,0,c.byref(err)),-1)
    self.assertEqual(err.value,95)
    fd=L.spple_guest_socket_open(self.g,2,2,0,c.byref(err)); out=c.create_string_buffer(8)
    self.assertEqual(L.spple_guest_socket_recvfrom(self.g,fd,out,8,0,None,None,c.byref(err)),-1)
    self.assertEqual(err.value,95)
 def test_engine_backend_bridge_dispatches_game_socket_calls(self):
    waited=threading.Event(); wait_events=[]
    def wait_hook(enter):
     wait_events.append(enter)
     if enter: waited.set()
    hook=WaitHook(wait_hook)
    self.assertEqual(L.spple_guest_socket_bridge_set_wait_hook(hook),0)
    b=L.spple_guest_socket_bridge_init(self.g); self.assertTrue(b)
    self.assertFalse(L.spple_guest_socket_bridge_init(self.g))
    err=c.c_int(); fd=b.contents.socket(2,2,0,c.byref(err)); self.assertEqual(fd,0)
    self.assertTrue(b.contents.owns(fd))
    bind=c.create_string_buffer(bytes([16,2,4,210])+bytes(12),16)
    self.assertEqual(b.contents.bind(fd,bind,16,c.byref(err)),0)
    name=c.create_string_buffer(16);namelen=c.c_uint(16)
    self.assertEqual(b.contents.getsockname(fd,name,c.byref(namelen),c.byref(err)),0)
    self.assertEqual(name.raw[:8],bytes([16,2,4,210,10,77,0,1]))
    self.assertEqual(b.contents.fcntl(fd,4,4,c.byref(err)),0)
    self.assertEqual(b.contents.fcntl(fd,3,0,c.byref(err)),6)
    temp=c.create_string_buffer(1)
    self.assertEqual(b.contents.recvfrom(fd,temp,1,0,None,None,c.byref(err)),-1);self.assertEqual(err.value,11)
    self.assertEqual(b.contents.fcntl(fd,4,0,c.byref(err)),0)
    broad=c.create_string_buffer(bytes([16,2,4,210,255,255,255,255])+bytes(8),16)
    msg=c.create_string_buffer(b'hi')
    self.assertEqual(b.contents.sendto(fd,msg,2,0,broad,16,c.byref(err)),-1);self.assertEqual(err.value,13)
    enabled=c.c_int(1);self.assertEqual(b.contents.setsockopt(fd,0xffff,0x20,c.byref(enabled),4,c.byref(err)),0)
    enabled.value=0;optlen=c.c_uint(4)
    self.assertEqual(b.contents.getsockopt(fd,0xffff,0x20,c.byref(enabled),c.byref(optlen),c.byref(err)),0);self.assertEqual(enabled.value,1)
    self.assertEqual(L.spple_guest_socket_bridge_ready(fd),4)
    dest=c.create_string_buffer(bytes([16,2,4,210,10,77,0,1])+bytes(8),16)
    msg=c.create_string_buffer(b'hi')
    self.assertEqual(b.contents.sendto(fd,msg,2,0,dest,16,c.byref(err)),2)
    self.assertEqual(L.spple_guest_socket_bridge_ready(fd),5)
    out=c.create_string_buffer(8); addr=c.create_string_buffer(16); size=c.c_uint(16)
    self.assertEqual(b.contents.recvfrom(fd,out,8,0x80,addr,c.byref(size),c.byref(err)),2)
    self.assertEqual(out.raw[:2],b'hi')
    ready=threading.Event(); result=[]
    def receive_blocking():
     local_error=c.c_int(); local=c.create_string_buffer(8); ready.set()
     n=b.contents.recvfrom(fd,local,8,0,None,None,c.byref(local_error))
     result.append((n,local.raw[:max(n,0)],local_error.value))
    t=threading.Thread(target=receive_blocking); t.start(); self.assertTrue(ready.wait(2))
    self.assertTrue(waited.wait(2))
    self.assertEqual(b.contents.sendto(fd,msg,2,0,dest,16,c.byref(err)),2)
    t.join(2); self.assertFalse(t.is_alive()); self.assertEqual(result[0][:2],(2,b'hi'))
    self.assertEqual(wait_events[:2],[1,0])
    ready.clear(); result.clear(); t=threading.Thread(target=receive_blocking); t.start(); self.assertTrue(ready.wait(2))
    L.spple_guest_socket_bridge_stop(); t.join(2)
    self.assertFalse(t.is_alive()); self.assertEqual(result,[(-1,b'',100)])
    self.assertEqual(L.spple_guest_socket_bridge_resume(IP(10,77,0,2),IP(10,77,0,1)),0)
    self.assertEqual(L.spple_guest_socket_bridge_ready(fd),4)
    namelen.value=16;self.assertEqual(b.contents.getsockname(fd,name,c.byref(namelen),c.byref(err)),0)
    self.assertEqual(name.raw[4:8],bytes([10,77,0,2]))
    self.assertEqual(b.contents.close(fd,c.byref(err)),0)
    self.assertEqual(L.spple_guest_socket_bridge_ready(fd),-1)
if __name__=='__main__': unittest.main()
