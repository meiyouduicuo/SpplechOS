import ctypes as c
import os,threading,time,unittest
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
L.spple_send_queue_new.argtypes=[c.c_size_t,c.c_size_t]; L.spple_send_queue_new.restype=c.c_void_p
L.spple_send_queue_put.argtypes=[c.c_void_p,c.c_void_p,c.c_size_t]
L.spple_send_queue_take.argtypes=[c.c_void_p,c.POINTER(c.c_void_p),c.POINTER(c.c_size_t)]
L.spple_send_queue_free_packet.argtypes=[c.c_void_p]
L.spple_send_queue_stop.argtypes=[c.c_void_p]; L.spple_send_queue_destroy.argtypes=[c.c_void_p]
class QueueTests(unittest.TestCase):
 def setUp(self):
  self.q=L.spple_send_queue_new(2,5); self.addCleanup(L.spple_send_queue_destroy,self.q)
 def test_fifo_capacity_and_binary_data(self):
  a=c.create_string_buffer(b'abc'); b=c.create_string_buffer(b'12')
  self.assertEqual(L.spple_send_queue_put(self.q,a,3),0); self.assertEqual(L.spple_send_queue_put(self.q,b,2),0)
  self.assertEqual(L.spple_send_queue_put(self.q,b,1),-1)
  ptr=c.c_void_p(); size=c.c_size_t()
  for expected in (b'abc',b'12'):
   self.assertEqual(L.spple_send_queue_take(self.q,c.byref(ptr),c.byref(size)),0)
   self.assertEqual(c.string_at(ptr,size.value),expected); L.spple_send_queue_free_packet(ptr)
 def test_stop_wakes_a_blocked_consumer(self):
  result=[]; started=threading.Event()
  def wait():
   ptr=c.c_void_p(); size=c.c_size_t(); started.set()
   result.append(L.spple_send_queue_take(self.q,c.byref(ptr),c.byref(size)))
  t=threading.Thread(target=wait); t.start(); self.assertTrue(started.wait(2))
  L.spple_send_queue_stop(self.q); t.join(2)
  self.assertFalse(t.is_alive()); self.assertEqual(result,[-1])
  self.assertEqual(L.spple_send_queue_put(self.q,None,0),-1)
 def test_oversize_is_rejected_without_consuming_capacity(self):
  payload=c.create_string_buffer(b'abcdef')
  self.assertEqual(L.spple_send_queue_put(self.q,payload,6),-1)
  self.assertEqual(L.spple_send_queue_put(self.q,payload,5),0)
if __name__=='__main__': unittest.main()
