import ctypes as c
import os,struct,unittest
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
Random=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_size_t)
Create=c.CFUNCTYPE(c.c_int,c.c_uint64,c.c_void_p,c.c_void_p)
Join=c.CFUNCTYPE(c.c_int,c.c_uint64,c.c_void_p,c.c_void_p,c.c_void_p,c.c_int,c.c_int)
Void=c.CFUNCTYPE(None);Attach=c.CFUNCTYPE(None,c.c_void_p)
Update=c.CFUNCTYPE(c.c_int,c.c_void_p)
Start=c.CFUNCTYPE(c.c_int)
Reject=c.CFUNCTYPE(c.c_int,c.c_uint32)
class Ops(c.Structure):_fields_=[('random',Random),('create',Create),('join',Join),('stop',Void),('attach',Attach),('signal',Void),('update',Update),('scan',Start),('disconnect',Void),('reject',Reject)]
Result0=c.CFUNCTYPE(c.c_uint32);State=c.CFUNCTYPE(c.c_int)
Scan=c.CFUNCTYPE(c.c_uint32,c.c_void_p,c.POINTER(c.c_int),c.c_int,c.c_void_p,c.c_int,c.c_int)
CreateCall=c.CFUNCTYPE(c.c_uint32,c.c_void_p,c.c_void_p,c.c_void_p)
JoinCall=c.CFUNCTYPE(c.c_uint32,c.c_void_p,c.c_void_p,c.c_void_p,c.c_int,c.c_int)
Info=c.CFUNCTYPE(c.c_uint32,c.c_void_p); Ip=c.CFUNCTYPE(c.c_uint32,c.c_void_p,c.c_void_p)
Adv=c.CFUNCTYPE(c.c_uint32,c.c_void_p,c.c_uint64)
CreatePrivate=c.CFUNCTYPE(c.c_uint32,c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p,c.c_int,c.c_void_p)
ConnectPrivate=c.CFUNCTYPE(c.c_uint32,c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p,c.c_int,c.c_int)
class Backend(c.Structure):
 _fields_=[('init',Result0),('fini',Void),('state',State),('attach',Attach),('open_sta',Result0),('close_sta',Result0),('open_ap',Result0),('close_ap',Result0),('disconnect',Result0),('destroy',Result0),('scan',Scan),('create',CreateCall),('connect',JoinCall),('info',Info),('ipv4',Ip),('advertise',Adv),('create_private',CreatePrivate),('connect_private',ConnectPrivate),('config',Info),('security',Info),('policy',c.CFUNCTYPE(c.c_uint32,c.c_int)),('reason',State),('reject',c.CFUNCTYPE(c.c_uint32,c.c_uint32))]
L.spple_ldn_service_setup.argtypes=[c.POINTER(Ops),c.c_int64];L.spple_ldn_service_setup.restype=c.POINTER(Backend)
L.spple_ldn_service_complete.argtypes=[c.c_uint64,c.c_int,c.c_void_p]
L.spple_ldn_service_discover.argtypes=[c.c_void_p]
L.spple_ldn_service_lost.argtypes=[]
L.spple_ldn_service_policy.argtypes=[c.c_int];L.spple_ldn_service_policy.restype=c.c_uint32
L.spple_ldn_service_disconnect_reason.argtypes=[]
class ServiceTests(unittest.TestCase):
 def test_async_host_then_discover_and_join(self):
  created=[];joined=[];signals=[];stops=[];updates=[]
  def rand(out,n): c.memmove(out,bytes(range(1,n+1)),n);return 0
  def create(token,room,security): created.append((token,c.string_at(room,0x480)));return 0
  def join(token,room,security,user,version,option): joined.append((token,c.string_at(room,0x480)));return 0
  starts=[]
  disconnects=[];rejects=[]
  o=Ops(Random(rand),Create(create),Join(join),Void(lambda:stops.append(1)),Attach(lambda _:None),Void(lambda:signals.append(1)),Update(lambda p:updates.append(c.string_at(p,0x480)) or 0),Start(lambda:starts.append(1) or 0),Void(lambda:disconnects.append(1)),Reject(lambda addr:rejects.append(addr) or 0))
  b=L.spple_ldn_service_setup(c.byref(o),123);self.assertTrue(b);b=b.contents
  self.assertEqual(b.init(),0);self.assertEqual(b.open_ap(),0);self.assertEqual(b.state(),2)
  msg=c.create_string_buffer(b'room');self.assertEqual(b.advertise(msg,4),0)
  cfg=bytearray(32);struct.pack_into('<q',cfg,0,-1);cfg[18]=4
  config=c.create_string_buffer(bytes(cfg));user=c.create_string_buffer(bytes(48));security=c.create_string_buffer(bytes(68))
  self.assertEqual(b.create(config,security,user),0);self.assertEqual(b.state(),2)
  token,raw=created[0];self.assertEqual(raw[0x26c:0x270],b'room');room=c.create_string_buffer(raw)
  self.assertEqual(L.spple_ldn_service_complete(token,1,room),0);self.assertEqual(b.state(),3)
  self.assertEqual(b.reject(0x0a4d0002),0);self.assertEqual(rejects,[0x0a4d0002])
  address=c.c_uint32();mask=c.c_uint32();self.assertEqual(b.ipv4(c.byref(address),c.byref(mask)),0)
  self.assertEqual(address.value,0x0a4d0001);self.assertEqual(mask.value,0xffffff00)
  self.assertEqual(b.policy(2),0x2a2)
  self.assertEqual(b.policy(1),0);self.assertEqual(updates[-1][0x62],1)
  self.assertEqual(b.policy(0),0)
  msg2=c.create_string_buffer(b'new');self.assertEqual(b.advertise(msg2,3),0)
  self.assertEqual(updates[-1][0x26c:0x26f],b'new')
  active_config=c.create_string_buffer(32);param=c.create_string_buffer(32)
  self.assertEqual(b.config(active_config),0);self.assertEqual(b.security(param),0)
  self.assertEqual(param.raw[:16],raw[0x50:0x60]);self.assertEqual(param.raw[16:32],raw[16:32])
  output=c.create_string_buffer(0x480);self.assertEqual(b.info(output),0)
  self.assertEqual(b.destroy(),0)
  self.assertEqual(b.reject(0x0a4d0002),0x2a2)
  self.assertEqual(b.create_private(active_config,security,param,user,1,None),0x2a2)
  self.assertEqual(b.create_private(active_config,security,param,user,0,None),0)
  private_token,private_raw=created[-1];self.assertEqual(private_raw[16:32],param.raw[16:32])
  self.assertEqual(L.spple_ldn_service_complete(private_token,1,c.create_string_buffer(private_raw)),0)
  self.assertEqual(b.destroy(),0);self.assertEqual(b.close_ap(),0)
  self.assertEqual(b.open_sta(),0);self.assertEqual(L.spple_ldn_service_discover(room),0)
  self.assertEqual(starts,[1])
  n=c.c_int();filter=c.create_string_buffer(0x60);out=c.create_string_buffer(0x480)
  self.assertEqual(b.scan(out,c.byref(n),1,filter,0,0),0);self.assertEqual(n.value,1)
  # Monster Hunter Rise filters by local communication ID, network type and scene.
  struct.pack_into('<q',filter,0,-1)
  struct.pack_into('<I',filter,0x20,2)
  struct.pack_into('<I',filter,0x5c,0x25)
  self.assertEqual(b.scan(out,c.byref(n),1,filter,0,0),0);self.assertEqual(n.value,1)
  self.assertEqual(out.raw[0x4b],2)
  self.assertEqual(b.connect_private(active_config,security,param,user,0,0),0);self.assertEqual(b.state(),4)
  self.assertEqual(L.spple_ldn_service_complete(joined[0][0],1,room),0);self.assertEqual(b.state(),5)
  self.assertEqual(b.disconnect(),0);self.assertEqual(disconnects,[1]);self.assertEqual(b.state(),4)
  self.assertEqual(b.reason(),1)
  self.assertEqual(b.connect_private(active_config,security,param,user,0,0),0)
  self.assertEqual(L.spple_ldn_service_complete(joined[-1][0],1,room),0)
  self.assertEqual(L.spple_ldn_service_lost(),0);self.assertEqual(b.state(),4)
  self.assertEqual(b.reason(),6)
  self.assertEqual(L.spple_ldn_service_complete(joined[0][0],1,room),-1)
  self.assertGreater(len(signals),5);b.fini();self.assertGreaterEqual(len(stops),3)
if __name__=='__main__':unittest.main()
