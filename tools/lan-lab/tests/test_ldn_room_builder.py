import ctypes as c
import os,struct,unittest
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
L.spple_ldn_build_room.argtypes=[c.c_void_p,c.c_void_p,c.c_int64,c.c_void_p,c.c_void_p,c.c_void_p]
L.spple_ldn_validate_network.argtypes=[c.c_void_p]
L.spple_ldn_room_add_station.argtypes=[c.c_void_p,c.c_void_p,c.c_int,c.c_void_p,c.c_void_p,c.c_void_p]
L.spple_ldn_room_remove_station.argtypes=[c.c_void_p,c.c_void_p]
class BuilderTests(unittest.TestCase):
 def inputs(self):
  config=bytearray(32);struct.pack_into('<q',config,0,-1);struct.pack_into('<H',config,10,3)
  config[18]=4;struct.pack_into('<h',config,20,1)
  user=bytearray(48);user[:6]=b'Player';entropy=bytes(range(1,33));ip=bytes([10,77,0,1])
  return config,user,entropy,ip
 def build(self,config,user,entropy,ip,out):
  return L.spple_ldn_build_room(c.create_string_buffer(bytes(config)),c.create_string_buffer(bytes(user)),123,c.create_string_buffer(entropy),c.create_string_buffer(ip),out)
 def test_build_preserves_intent_and_owner(self):
  cfg,u,e,ip=self.inputs();out=c.create_string_buffer(0x480)
  self.assertEqual(self.build(cfg,u,e,ip,out),0);self.assertEqual(L.spple_ldn_validate_network(out),0)
  self.assertEqual(struct.unpack_from('<q',out.raw,0)[0],123)
  self.assertEqual(struct.unpack_from('<H',out.raw,10)[0],3)
  self.assertEqual(out.raw[16:32],e[:16]);self.assertEqual(out.raw[0x68:0x6c],ip[::-1])
 def test_invalid_input_does_not_modify_output(self):
  cfg,u,e,ip=self.inputs();cfg[18]=9;out=c.create_string_buffer(b'x'*0x480,0x480)
  self.assertEqual(self.build(cfg,u,e,ip,out),-1);self.assertEqual(out.raw,b'x'*0x480)
  cfg[18]=4;self.assertEqual(self.build(cfg,u,bytes(32),ip,out),-1)
 def test_add_and_remove_station_requires_real_slot(self):
  cfg,u,e,ip=self.inputs();out=c.create_string_buffer(0x480);updated=c.create_string_buffer(0x480)
  self.assertEqual(self.build(cfg,u,e,ip,out),0)
  user=c.create_string_buffer(bytes(u));station=c.create_string_buffer(bytes([10,77,0,2]));mac=c.create_string_buffer(bytes([31,32,33,34,35,36]))
  self.assertEqual(L.spple_ldn_room_add_station(out,user,1,station,mac,updated),0)
  self.assertEqual(updated.raw[0x67],2);self.assertEqual(updated.raw[0x68+0x40:0x68+0x44],station.raw[:4][::-1])
  self.assertEqual(L.spple_ldn_room_add_station(updated,user,1,station,mac,out),-1)
  self.assertEqual(L.spple_ldn_room_remove_station(updated,out),0);self.assertEqual(out.raw[0x67],1)
if __name__=='__main__':unittest.main()
