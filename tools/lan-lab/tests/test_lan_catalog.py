import ctypes as c
import os,unittest
from test_ldn_rooms import room
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
class Endpoint(c.Structure):_fields_=[('host',c.c_char*256),('port',c.c_uint16),('index',c.c_uint32),('generation',c.c_uint64)]
L.spple_lan_catalog_new.restype=c.c_void_p
for n,a in {'free':[c.c_void_p],'begin':[c.c_void_p,c.c_uint64,c.c_uint32,c.c_char_p,c.c_uint16], 'complete':[c.c_void_p,c.c_uint64,c.c_void_p], 'remove':[c.c_void_p,c.c_uint64,c.c_void_p], 'lookup':[c.c_void_p,c.c_void_p,c.POINTER(Endpoint)]}.items():getattr(L,'spple_lan_catalog_'+n).argtypes=a
class CatalogTests(unittest.TestCase):
 def setUp(self):self.p=L.spple_lan_catalog_new();self.addCleanup(L.spple_lan_catalog_free,self.p)
 def test_stale_probe_does_not_resurrect_removed_service(self):
  self.assertEqual(L.spple_lan_catalog_begin(self.p,1,7,b'host.local.',444),0)
  out=c.create_string_buffer(16);self.assertEqual(L.spple_lan_catalog_remove(self.p,1,out),0)
  self.assertEqual(L.spple_lan_catalog_complete(self.p,1,room()),-1)
  self.assertEqual(L.spple_lan_catalog_begin(self.p,2,7,b'new.local.',445),0)
  self.assertEqual(L.spple_lan_catalog_complete(self.p,2,room()),0)
  ep=Endpoint();sid=c.create_string_buffer(bytes([1])*16)
  self.assertEqual(L.spple_lan_catalog_lookup(self.p,sid,c.byref(ep)),0)
  self.assertEqual((ep.host,ep.port,ep.generation),(b'new.local.',445,2))
  self.assertEqual(L.spple_lan_catalog_remove(self.p,2,out),1);self.assertEqual(out.raw[:16],bytes([1])*16)
  self.assertEqual(L.spple_lan_catalog_lookup(self.p,sid,c.byref(ep)),-1)
 def test_ambiguous_session_is_rejected(self):
  for n in (1,2):self.assertEqual(L.spple_lan_catalog_begin(self.p,n,7,b'host.local.',444+n),0)
  self.assertEqual(L.spple_lan_catalog_complete(self.p,1,room()),0)
  self.assertEqual(L.spple_lan_catalog_complete(self.p,2,room()),-1)
if __name__=='__main__':unittest.main()
