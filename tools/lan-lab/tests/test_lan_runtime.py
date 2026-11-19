import ctypes as c
import multiprocessing as mp
import os,socket,time,unittest

def exercise(queue):
 try:
  from test_ldn_service import Backend
  L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
  Reserve=c.CFUNCTYPE(c.c_int,c.c_void_p);Release=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_int);Notify=c.CFUNCTYPE(None,c.c_void_p)
  Wait=c.CFUNCTYPE(None,c.c_int);Attach=c.CFUNCTYPE(None,c.c_void_p);Signal=c.CFUNCTYPE(None);Random=c.CFUNCTYPE(c.c_int,c.c_void_p,c.c_void_p,c.c_size_t)
  class Platform(c.Structure):_fields_=[('ctx',c.c_void_p),('reserve',Reserve),('release',Release),('notify',Notify),('wait',Wait),('attach',Attach),('signal',Signal),('random',Random)]
  class Backends(c.Structure):_fields_=[('ldn',c.POINTER(Backend)),('sockets',c.c_void_p),('ready',c.c_void_p)]
  L.spple_lan_runtime_init.argtypes=[c.c_uint64,c.c_int64,c.POINTER(Platform),c.POINTER(Backends)];L.spple_lan_runtime_stop.argtypes=[]
  used=set();signals=[]
  def reserve(_):
   for i in range(64):
    if i not in used:used.add(i);return i
   return -1
  def release(_,fd):used.discard(fd);return 0
  def random(_,out,n):c.memmove(out,bytes((i%255)+1 for i in range(n)),n);return 0
  platform=Platform(None,Reserve(reserve),Release(release),Notify(lambda _:None),Wait(lambda _:None),Attach(lambda _:None),Signal(lambda:signals.append(1)),Random(random))
  out=Backends();assert L.spple_lan_runtime_init(123,123,c.byref(platform),c.byref(out))==0
  b=out.ldn.contents;assert b.init()==0;assert b.open_ap()==0
  cfg=bytearray(32);cfg[18]=4;cfg[0:8]=(123).to_bytes(8,'little')
  security=bytearray(68);security[2:4]=(16).to_bytes(2,'little');security[4:20]=bytes(range(16))
  user=c.create_string_buffer(bytes(48));assert b.create(c.create_string_buffer(bytes(cfg)),c.create_string_buffer(bytes(security)),user)==0
  # Fake DNS has no real descriptor: first publication fails. Recreating must
  # tear down the failed host and start a fresh attempt without restarting.
  limit=time.monotonic()+5;retried=False
  while time.monotonic()<limit:
   if b.create(c.create_string_buffer(bytes(cfg)),c.create_string_buffer(bytes(security)),user)==0:retried=True;break
   time.sleep(.02)
  assert retried,'host could not retry after discovery failure'
  b.fini();L.spple_lan_runtime_stop();queue.put(('ok',len(signals)))
 except BaseException as e:queue.put(('error',repr(e)))
class RuntimeTests(unittest.TestCase):
 def test_host_startup_failure_tears_down_without_hanging(self):
  ctx=mp.get_context('spawn');q=ctx.Queue();p=ctx.Process(target=exercise,args=(q,));p.start();p.join(12)
  if p.is_alive():p.terminate();p.join();self.fail('runtime teardown hung')
  self.assertEqual(p.exitcode,0);result=q.get(timeout=2);self.assertEqual(result[0],'ok',result)
if __name__=='__main__':unittest.main()
