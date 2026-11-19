import ctypes as c
import os, socket, unittest
from test_ldn_rooms import room
L=c.CDLL(os.environ["SPPLE_LAN_TEST_LIBRARY"])
Session=c.c_uint8*16
L.spple_room_info_send.argtypes=[c.c_ssize_t,c.c_uint64,c.POINTER(c.c_uint8),c.c_void_p]
L.spple_room_info_receive.argtypes=[c.c_ssize_t,c.c_uint64,c.POINTER(c.c_uint8),c.c_void_p]
class RoomInfoTests(unittest.TestCase):
    def setUp(self):
        self.a,self.b=socket.socketpair(); self.addCleanup(self.a.close); self.addCleanup(self.b.close)
        self.session=Session(*([1]*16)); self.title=0x0100559011740000
    def test_record_passes_over_real_socket(self):
        src=room(); out=c.create_string_buffer(0x480)
        self.assertEqual(L.spple_room_info_send(self.a.fileno(),self.title,self.session,src),0)
        self.assertEqual(L.spple_room_info_receive(self.b.fileno(),self.title,self.session,out),0)
        self.assertEqual(src.raw[:0x480],out.raw[:0x480])
    def test_wrong_title_is_not_delivered(self):
        src=room(); out=c.create_string_buffer(b"x"*0x480,0x480)
        self.assertEqual(L.spple_room_info_send(self.a.fileno(),self.title,self.session,src),0)
        self.assertEqual(L.spple_room_info_receive(self.b.fileno(),self.title+1,self.session,out),-1)
        self.assertEqual(out.raw,b"x"*0x480)
    def test_reserved_guest_bytes_are_not_transmitted(self):
        src=room(); src[8]=b'\x7f'; src[0x68+12+10]=b'\x7f'
        out=c.create_string_buffer(0x480)
        self.assertEqual(L.spple_room_info_send(self.a.fileno(),self.title,self.session,src),0)
        self.assertEqual(L.spple_room_info_receive(self.b.fileno(),self.title,self.session,out),0)
        self.assertEqual(out.raw[8],0);self.assertEqual(out.raw[0x68+12+10],0)
    def test_invalid_or_other_session_is_not_sent(self):
        self.assertEqual(L.spple_room_info_send(self.a.fileno(),self.title,self.session,room(2)),-1)
        bad=room(); bad[0x66]=b"\x09"
        self.assertEqual(L.spple_room_info_send(self.a.fileno(),self.title,self.session,bad),-1)
if __name__ == "__main__": unittest.main()
