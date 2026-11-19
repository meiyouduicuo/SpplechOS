import ctypes as c
import os, struct, unittest
L = c.CDLL(os.environ["SPPLE_LAN_TEST_LIBRARY"])
L.spple_ldn_rooms_new.restype = c.c_void_p
for name, args in {
    "free": [c.c_void_p], "init": [c.c_void_p], "fini": [c.c_void_p],
    "state": [c.c_void_p], "begin": [c.c_void_p,c.c_int,c.POINTER(c.c_uint64)],
    "complete": [c.c_void_p,c.c_uint64,c.c_int,c.c_void_p],
    "put": [c.c_void_p,c.c_void_p], "remove": [c.c_void_p,c.c_void_p],
    "select": [c.c_void_p,c.c_void_p], "info": [c.c_void_p,c.c_void_p],
    "scan": [c.c_void_p,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)],
    "revision": [c.c_void_p],
    "transport_lost": [c.c_void_p], "update_active": [c.c_void_p,c.c_void_p],
}.items(): getattr(L,"spple_ldn_rooms_"+name).argtypes=args
L.spple_ldn_rooms_revision.restype=c.c_uint64
CALLBACK=c.CFUNCTYPE(None,c.c_void_p,c.c_uint64)
L.spple_ldn_rooms_set_listener.argtypes=[c.c_void_p,CALLBACK,c.c_void_p]

def room(ident=1, game=123):
    b=bytearray(0x480); struct.pack_into("<Q",b,0,game); b[16:32]=bytes([ident])*16
    b[0x26]=4; b[0x27:0x2c]=b"room\0"; b[0x66]=4; b[0x67]=1; b[0x68+11]=1
    return c.create_string_buffer(bytes(b))

class Rooms(unittest.TestCase):
    def setUp(self):
        self.r=L.spple_ldn_rooms_new(); self.assertTrue(self.r); self.assertEqual(L.spple_ldn_rooms_init(self.r),0)
    def tearDown(self): L.spple_ldn_rooms_free(self.r)
    def begin(self,op):
        token=c.c_uint64(); self.assertEqual(L.spple_ldn_rooms_begin(self.r,op,c.byref(token)),0); return token.value
    def done(self,token,success=1,info=None): return L.spple_ldn_rooms_complete(self.r,token,success,info)
    def test_discovery_is_not_connection_and_wrong_identity_is_rejected(self):
        self.assertEqual(self.done(self.begin(1)),0)
        net=room(); self.assertEqual(L.spple_ldn_rooms_put(self.r,net),0)
        out=c.create_string_buffer(0x480); self.assertEqual(L.spple_ldn_rooms_info(self.r,out),-1)
        filt=c.create_string_buffer(0x60); count=c.c_size_t()
        self.assertEqual(L.spple_ldn_rooms_scan(self.r,filt,out,1,c.byref(count)),0); self.assertEqual(count.value,1)
        self.assertEqual(L.spple_ldn_rooms_select(self.r,c.c_char_p(bytes([1])*16)),0)
        token=self.begin(3)
        self.assertEqual(L.spple_ldn_rooms_put(self.r,room(1,124)),0)
        self.assertEqual(self.done(token,1,room(1,124)),-1)
        self.assertEqual(L.spple_ldn_rooms_state(self.r),4)
        self.assertEqual(self.done(token,1,net),0); self.assertEqual(L.spple_ldn_rooms_state(self.r),5)
        self.assertEqual(L.spple_ldn_rooms_info(self.r,out),0)
        self.assertEqual(self.done(self.begin(5)),0); self.assertEqual(L.spple_ldn_rooms_info(self.r,out),-1)
    def test_cancel_rejects_stale_and_room_removal(self):
        self.assertEqual(self.done(self.begin(1)),0); net=room()
        self.assertEqual(L.spple_ldn_rooms_put(self.r,net),0)
        ident=c.c_char_p(bytes([1])*16)
        self.assertEqual(L.spple_ldn_rooms_select(self.r,ident),0)
        t=self.begin(3); self.assertEqual(L.spple_ldn_rooms_fini(self.r),0)
        self.assertEqual(self.done(t,1,net),-1)
        self.assertEqual(L.spple_ldn_rooms_init(self.r),0); self.assertEqual(self.done(self.begin(1)),0)
        self.assertEqual(L.spple_ldn_rooms_select(self.r,ident),-1)
    def test_invalid_and_capacity(self):
        self.assertEqual(self.done(self.begin(1)),0)
        for i in range(1,17): self.assertEqual(L.spple_ldn_rooms_put(self.r,room(i)),0)
        self.assertEqual(L.spple_ldn_rooms_put(self.r,room(17)),-1)
        bad=room(2); bad[0x66]=b"\x09"; self.assertEqual(L.spple_ldn_rooms_put(self.r,bad),-1)
        ident=c.c_char_p(bytes([3])*16); self.assertEqual(L.spple_ldn_rooms_remove(self.r,ident),0)
        self.assertEqual(L.spple_ldn_rooms_put(self.r,room(17)),0)
    def test_revision_changes_only_when_state_changes(self):
        revision=L.spple_ldn_rooms_revision(self.r); t=self.begin(0)
        self.assertEqual(self.done(t,0),0); self.assertEqual(L.spple_ldn_rooms_revision(self.r),revision)
        self.assertEqual(self.done(self.begin(0)),0); self.assertEqual(L.spple_ldn_rooms_revision(self.r),revision+1)

    def test_peer_update_and_transport_loss_invalidate_pending(self):
        self.assertEqual(self.done(self.begin(1)),0)
        net=room(); ident=c.c_char_p(bytes([1])*16)
        self.assertEqual(L.spple_ldn_rooms_put(self.r,net),0)
        self.assertEqual(L.spple_ldn_rooms_select(self.r,ident),0)
        self.assertEqual(self.done(self.begin(3),1,net),0)
        rev=L.spple_ldn_rooms_revision(self.r)
        self.assertEqual(L.spple_ldn_rooms_update_active(self.r,room(1,124)),-1)
        self.assertEqual(L.spple_ldn_rooms_update_active(self.r,net),0)
        self.assertEqual(L.spple_ldn_rooms_revision(self.r),rev)
        net[0x67]=b'\x02'; net[0x68+0x40+11]=b'\x01'
        self.assertEqual(L.spple_ldn_rooms_update_active(self.r,net),0)
        self.assertEqual(L.spple_ldn_rooms_revision(self.r),rev+1)
        pending=self.begin(5)
        self.assertEqual(L.spple_ldn_rooms_transport_lost(self.r),0)
        self.assertEqual(L.spple_ldn_rooms_state(self.r),4)
        self.assertEqual(self.done(pending),-1)
        self.assertEqual(L.spple_ldn_rooms_info(self.r,c.create_string_buffer(0x480)),-1)

    def test_state_change_notifies_once_and_failures_do_not_signal(self):
        notifications=[]
        cb=CALLBACK(lambda ctx, revision: notifications.append(revision))
        self.assertEqual(L.spple_ldn_rooms_set_listener(self.r,cb,None),0)
        rev=L.spple_ldn_rooms_revision(self.r)
        self.assertEqual(self.done(self.begin(0),0),0)
        self.assertEqual(notifications,[])
        self.assertEqual(self.done(self.begin(0),1),0)
        self.assertEqual(notifications,[rev+1])
        self.assertEqual(L.spple_ldn_rooms_fini(self.r),0)
        self.assertEqual(notifications,[rev+1,rev+2])

if __name__ == "__main__": unittest.main()
