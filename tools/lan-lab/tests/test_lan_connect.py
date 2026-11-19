import ctypes as c
import os,socket,unittest
L=c.CDLL(os.environ['SPPLE_LAN_TEST_LIBRARY'])
L.spple_lan_connect.argtypes=[c.c_char_p,c.c_uint16,c.c_uint,c.POINTER(c.c_ssize_t)]
L.spple_lan_socket_close.argtypes=[c.c_ssize_t]
class ConnectTests(unittest.TestCase):
 def test_connects_to_local_listener(self):
  with socket.socket() as listener:
   listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(3);fd=c.c_ssize_t(-1)
   self.assertEqual(L.spple_lan_connect(b'127.0.0.1',listener.getsockname()[1],1000,c.byref(fd)),0)
   try:
    conn,_=listener.accept();conn.close()
   finally:L.spple_lan_socket_close(fd.value)
 def test_invalid_and_refused_connections_fail(self):
  fd=c.c_ssize_t(5);self.assertEqual(L.spple_lan_connect(b'127.0.0.1',5,0,c.byref(fd)),-1)
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  self.assertEqual(L.spple_lan_connect(b'127.0.0.1',port,500,c.byref(fd)),-1)
if __name__=='__main__':unittest.main()
