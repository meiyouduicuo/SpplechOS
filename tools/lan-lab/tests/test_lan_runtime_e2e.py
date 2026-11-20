"""Full runtime on two processes with synthetic asynchronous Bonjour."""
import ctypes as c
from concurrent.futures import ThreadPoolExecutor
import multiprocessing as mp
import os,socket,time,unittest

def device(control,is_host,port):
 try:
  from test_ldn_service import Backend
  from test_guest_udp import Backend as SocketBackend
  L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
  Reserve=c.CFUNCTYPE(c.c_int,c.c_void_p);Release=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_int);Notify=c.CFUNCTYPE(None,c.c_void_p)
  Wait=c.CFUNCTYPE(None,c.c_int);Attach=c.CFUNCTYPE(None,c.c_void_p);Signal=c.CFUNCTYPE(None);Random=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_size_t)
  class Platform(c.Structure):_fields_=[('ctx',c.c_void_p),('reserve',Reserve),('release',Release),('notify',Notify),('wait',Wait),('attach',Attach),('signal',Signal),('random',Random)]
  class Backends(c.Structure):_fields_=[('ldn',c.POINTER(Backend)),('sockets',c.POINTER(SocketBackend)),('ready',c.c_void_p)]
  L.spple_lan_runtime_init.argtypes=[c.c_uint64,c.c_int64,c.POINTER(Platform),c.POINTER(Backends)]
  L.fake_dns_set_async.argtypes=[c.c_int];L.fake_has_operation.argtypes=[c.c_int];L.fake_emit_register.argtypes=[c.c_int];L.fake_emit_browse.argtypes=[c.c_int];L.fake_emit_resolve.argtypes=[c.c_uint16]
  def wait_for(fn,desc,timeout=12):
   end=time.monotonic()+timeout
   while time.monotonic()<end:
    if fn():return
    time.sleep(.01)
   raise RuntimeError('timeout: '+desc)
  used=set()
  def reserve(_):
   for i in range(64):
    if i not in used:used.add(i);return i
   return -1
  def release(_,fd):used.discard(fd);return 0
  def random(_,out,n):
   if not is_host:
    # Keep the station handshake pending after the endpoint is discoverable.
    time.sleep(.2)
   c.memmove(out,os.urandom(n),n)
   return 0
  platform=Platform(None,Reserve(reserve),Release(release),Notify(lambda _:None),Wait(lambda _:None),Attach(lambda _:None),Signal(lambda:None),Random(random))
  assert L.fake_dns_set_async(1)==0
  out=Backends();assert L.spple_lan_runtime_init(123,123,c.byref(platform),c.byref(out))==0
  b=out.ldn.contents;sk=out.sockets.contents;assert b.init()==0
  security=bytearray(68);security[2:4]=(16).to_bytes(2,'little');security[4:20]=bytes(range(16));secret=c.create_string_buffer(bytes(security))
  user=c.create_string_buffer(bytes(48));config=bytearray(32);config[:8]=(123).to_bytes(8,'little');config[18]=4;cfg=c.create_string_buffer(bytes(config))
  if is_host:
   assert b.open_ap()==0;assert b.create(cfg,secret,user)==0;assert b.state()==3
   # ACNH opens admission after creation while Bonjour is still registering.
   # A local room-setting update must not require publication to have finished.
   for policy in (0,1,0):
    result=b.policy(policy)
    assert result==0,('acceptance policy before Bonjour registration',policy,result)
   initial_advert=c.create_string_buffer(b'pending room')
   assert b.advertise(initial_advert,12)==0,'advertise-data update before publication failed'
   pre_err=c.c_int();pre_fd=sk.socket(2,2,0,c.byref(pre_err));assert pre_fd>=0,('host socket before join',pre_err.value)
   peer_addr=c.create_string_buffer(bytes([16,2,0x11,0x5c,10,77,0,2])+bytes(8),16)
   payload=c.create_string_buffer(b'probe')
   assert sk.sendto(pre_fd,payload,5,0,peer_addr,16,c.byref(pre_err))==5,('send before station',pre_err.value)
   assert sk.close(pre_fd,c.byref(pre_err))==0
   wait_for(lambda:L.fake_has_operation(1),'advertise registration');L.fake_emit_register(0)
   wait_for(lambda:b.state()==3,'host published');hostport=socket.ntohs(L.fake_port());control.send(('port',hostport))
   info=c.create_string_buffer(0x480)
   def joined():return b.info(info)==0 and info.raw[0x67]==2
   wait_for(joined,'host station joins');control.send(('joined',))
  else:
   def publish_room():
    wait_for(lambda:L.fake_has_operation(2),'browse');L.fake_emit_browse(1)
    wait_for(lambda:L.fake_has_operation(3),'resolve');L.fake_emit_resolve(socket.htons(port))
    wait_for(lambda:L.fake_has_operation(4),'address');L.fake_emit_address()
   assert b.open_sta()==0
   publish_room()
   info=c.create_string_buffer(0x480);count=c.c_int();flt=c.create_string_buffer(0x60)
   def found():return b.scan(info,c.byref(count),1,flt,0,0)==0 and count.value==1
   wait_for(found,'room probe')
   # Rise closes the browsing station, reopens it, then immediately connects
   # using the previous scan result before the new browser has an endpoint.
   assert b.close_sta()==0
   assert b.open_sta()==0
   assert L.fake_has_operation(3)==0
   with ThreadPoolExecutor(max_workers=1) as pool:
    joining=pool.submit(b.connect,info,secret,user,1,0)
    time.sleep(.1)
    assert not joining.done(),'join returned before the endpoint was available'
    publish_room()
    assert joining.result(timeout=5)==0
   active_config=c.create_string_buffer(32)
   assert b.config(active_config)==0,'Connect returned before network configuration was available'
   assert b.state()==5
   control.send(('joined',))
  if is_host:
   assert control.recv()=='update';advert=c.create_string_buffer(b'new lobby')
   assert b.advertise(advert,9)==0;control.send(('updated',))
  else:
   def room_updated():return b.info(info)==0 and info.raw[0x26c:0x275]==b'new lobby'
   wait_for(room_updated,'host room update');control.send(('roomupdate',))
  err=c.c_int();fd=sk.socket(2,2,0,c.byref(err));assert fd>=0
  bind=c.create_string_buffer(bytes([16,2,0x11,0x5c])+bytes(12),16);assert sk.bind(fd,bind,16,c.byref(err))==0
  control.send(('socket',));assert control.recv()=='exchange'
  message=b'HOST' if is_host else b'GUEST';buf=c.create_string_buffer(message)
  addr=c.create_string_buffer(bytes([16,2,0x11,0x5c,10,77,0,2 if is_host else 1])+bytes(8),16)
  assert sk.sendto(fd,buf,len(message),0,addr,16,c.byref(err))==len(message)
  received=c.create_string_buffer(16);peer=c.create_string_buffer(16);size=c.c_uint(16)
  n=sk.recvfrom(fd,received,16,0x80,peer,c.byref(size),c.byref(err))
  end=time.monotonic()+8
  while n<0 and err.value==11 and time.monotonic()<end:
   time.sleep(.02);size.value=16;n=sk.recvfrom(fd,received,16,0x80,peer,c.byref(size),c.byref(err))
  assert n>=0,('recv',n,err.value);control.send(('data',received.raw[:n]));assert control.recv()=='reconnect'
  if is_host:
   def peer_left():return b.info(info)==0 and info.raw[0x67]==1
   wait_for(peer_left,'station disconnect');control.send(('peerleft',))
   def peer_rejoined():return b.info(info)==0 and info.raw[0x67]==2
   wait_for(peer_rejoined,'station rejoined');control.send(('rejoined',))
  else:
   assert b.disconnect()==0;control.send(('left',));assert control.recv()=='rejoin'
   assert b.connect(info,secret,user,1,0)==0;wait_for(lambda:b.state()==5,'station reconnect');control.send(('rejoined',))
  assert control.recv()=='exchange2'
  message=b'HOST2' if is_host else b'GUEST2';buf=c.create_string_buffer(message)
  assert sk.sendto(fd,buf,len(message),0,addr,16,c.byref(err))==len(message)
  end=time.monotonic()+8;size.value=16;n=sk.recvfrom(fd,received,16,0x80,peer,c.byref(size),c.byref(err))
  while n<0 and err.value==11 and time.monotonic()<end:
   time.sleep(.02);size.value=16;n=sk.recvfrom(fd,received,16,0x80,peer,c.byref(size),c.byref(err))
  assert n>=0,('second recv',n,err.value);control.send(('data2',received.raw[:n]));assert control.recv()=='reject'
  if is_host:
   assert b.reject(0x0a4d0002)==0
   wait_for(lambda:b.info(info)==0 and info.raw[0x67]==1,'host rejected station');control.send(('rejected',))
  else:
   wait_for(lambda:b.state()==4,'station rejected by host');control.send(('rejected',))
  control.recv()
  assert sk.close(fd,c.byref(err))==0;b.fini();L.spple_lan_runtime_stop();control.send(('done',))
 except BaseException as e:
  try:control.send(('error',repr(e)))
  except Exception:pass
class RuntimeE2ETests(unittest.TestCase):
 def test_discover_join_and_exchange_between_two_runtimes(self):
  ctx=mp.get_context('spawn');pipes=[];processes=[]
  def start(host,port):
   parent,child=ctx.Pipe();p=ctx.Process(target=device,args=(child,host,port));p.start();pipes.append(parent);processes.append(p);return parent
  def receive(p,kind,timeout=18):
   self.assertTrue(p.poll(timeout),'timeout waiting for '+kind);result=p.recv();self.assertEqual(result[0],kind,result);return result
  host=start(True,0)
  try:
   port=receive(host,'port')[1];station=start(False,port)
   receive(station,'joined');receive(host,'joined');host.send('update');receive(host,'updated');receive(station,'roomupdate')
   receive(host,'socket');receive(station,'socket')
   host.send('exchange');station.send('exchange')
   self.assertEqual(receive(host,'data')[1],b'GUEST');self.assertEqual(receive(station,'data')[1],b'HOST')
   host.send('reconnect');station.send('reconnect');receive(station,'left');receive(host,'peerleft')
   station.send('rejoin');receive(station,'rejoined');receive(host,'rejoined')
   host.send('exchange2');station.send('exchange2')
   self.assertEqual(receive(host,'data2')[1],b'GUEST2');self.assertEqual(receive(station,'data2')[1],b'HOST2')
   host.send('reject');station.send('reject');receive(host,'rejected');receive(station,'rejected')
   host.send('stop');station.send('stop');receive(host,'done');receive(station,'done')
  finally:
   for p in processes:
    p.join(5)
    if p.is_alive():p.terminate();p.join(5)
  self.assertEqual([p.exitcode for p in processes],[0,0])
if __name__=='__main__':unittest.main()
