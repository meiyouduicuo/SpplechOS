"""Compile the real HLE seam with stubbed host bindings and exercise both paths."""
import os, pathlib, re, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[3]
class EngineSeamTests(unittest.TestCase):
    def test_cpp_errno_query_sees_the_receive_error_used_by_animal_crossing(self):
        """ACNH main+0xe061c calls the C++ GetLastErrno, not GetLastError."""
        clang=os.environ.get('SPPLE_TEST_CLANG',r'C:\msys64\mingw64\bin\clang.exe')
        source=(ROOT/'engine/dm/host/hle_net.c').read_text(encoding='utf-8')
        seam=source[source.index('#define SK_ENETDOWN'):source.index('#define SKF')]
        # The C++ errno entry lives in hle_offline.c. Query all host files so
        # adding it again in hle_net.c cannot pass this test and crash at load.
        all_source='\n'.join(p.read_text(encoding='utf-8') for p in sorted((ROOT/'engine/dm/host').glob('*.c')))
        for name in ('_ZN2nn6socket12GetLastErrnoEv','_ZN2nn6socket12GetLastErrorEv','nnsocketGetLastErrno'):
            self.assertEqual(len(re.findall(r'HLE_FORCE\("'+re.escape(name)+r'"',all_source)),1,name)
        hooks=re.findall(r'HLE_FORCE\("([^"]+)",\s*"[^"]*",\s*int,\s*(\w+),\s*void\)\s*\{([^{}]*)\}',all_source)
        hooks=[(name,fn,body) for name,fn,body in hooks if 'GetLastErr' in name]
        code='''#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdatomic.h>
#define LOG(...) ((void)0)
#include "hle_lan_backend.h"
'''+seam+'\n'
        code+='\n'.join(f'static int {fn}(void) {{{body}}}' for _,fn,body in hooks)
        code+='\nstruct entry {const char *name; int (*get)(void);};\nstatic struct entry queries[]={\n'
        code+=',\n'.join('{"'+name+'",'+fn+'}' for name,fn,_ in hooks)+'};\n'
        code+='''
static long receive_empty(int fd,void *p,unsigned long n,int flags,void *a,unsigned *sz,int *error) {
 (void)fd;(void)p;(void)n;(void)flags;(void)a;(void)sz;*error=11;return -1;
}
static int owned(int fd){return fd==7;}
int main(void) {
 dm_lan_socket_backend backend={0};backend.owns=owned;backend.recvfrom=receive_empty;
 atomic_store(&g_lan_sockets,&backend);
 if(dm_sk_recvfrom(7,0,0,0,0,0)!=-1)return 1;
 const char *names[]={"_ZN2nn6socket12GetLastErrnoEv","_ZN2nn6socket12GetLastErrorEv","nnsocketGetLastErrno"};
 for(unsigned n=0;n<sizeof names/sizeof names[0];++n){
  int found=0;
  for(unsigned i=0;i<sizeof queries/sizeof queries[0];++i)if(!strcmp(names[n],queries[i].name)){
   found=1;if(queries[i].get()!=11)return 2;
  }
  if(!found)return 3;
 }
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src=pathlib.Path(tmp)/'errno.c'; exe=pathlib.Path(tmp)/'errno.exe'; src.write_text(code,encoding='utf-8')
            subprocess.run([clang,'-std=c11','-I',str(ROOT/'engine/dm/host'),str(src),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
    def test_socket_dispatch_and_error_propagation(self):
        clang=os.environ.get('SPPLE_TEST_CLANG',r'C:\msys64\mingw64\bin\clang.exe')
        source=(ROOT/'engine/dm/host/hle_net.c').read_text(encoding='utf-8')
        source=source[source.index('#define SK_ENETDOWN'):source.index('#define SKF')]
        source=r'''#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdatomic.h>
#define LOG(...) ((void)0)
#include "hle_lan_backend.h"
''' + source + r'''
static int owns(int fd) {return fd==7;}
static int socketfn(int a,int b,int c,int *e) {(void)a;(void)b;(void)c;(void)e;return 7;}
static int bindfn(int s,const void *a,unsigned n,int *e) {(void)s;(void)a;(void)n;*e=22;return -1;}
static long sendfn(int s,const void *d,unsigned long n,int f,const void *a,unsigned al,int *e) {(void)s;(void)d;(void)f;(void)a;(void)al;(void)e;return (long)n;}
static long recvfn(int s,void *d,unsigned long n,int f,void *a,unsigned *al,int *e) {(void)s;(void)d;(void)n;(void)f;(void)a;(void)al;*e=11;return -1;}
static int closefn(int s,int *e) {(void)s;(void)e;return 0;}
int main(void) {
 if (dm_sk_socket(2,2,0)!=-1 || dm_sk_last_errno()!=100) return 1;
 dm_lan_socket_backend b={owns,socketfn,bindfn,sendfn,recvfn,closefn};
 dm_lan_socket_backend invalid=b; invalid.recvfrom=0;
 if (dm_net_register_lan_sockets(&invalid)!=-1 || dm_net_register_lan_sockets(&b) || dm_net_register_lan_sockets(&b)!=-1) return 2;
 if (dm_sk_socket(2,2,0)!=7 || dm_sk_bind(7,0,0)!=-1 || dm_sk_last_errno()!=22) return 3;
 if (dm_sk_sendto(7,0,5,0,0,0)!=5 || dm_sk_recvfrom(7,0,0,0,0,0)!=-1 || dm_sk_last_errno()!=11) return 4;
 if (dm_sk_bind(8,0,0)!=-1 || dm_sk_last_errno()!=100) return 5;
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src=pathlib.Path(tmp)/'dispatch.c'; exe=pathlib.Path(tmp)/'dispatch.exe'; src.write_text(source,encoding='utf-8')
            subprocess.run([clang,'-std=c11','-I',str(ROOT/'engine/dm/host'),str(src),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
    def test_event_and_lan_descriptors_do_not_collide(self):
        clang=os.environ.get('SPPLE_TEST_CLANG',r'C:\msys64\mingw64\bin\clang.exe')
        source=(ROOT/'engine/dm/host/hle_net.c').read_text(encoding='utf-8')
        source=source[source.index('enum { EFD_MAX'):source.index('// Select is Poll over')]
        source=r'''#include <stdint.h>
#include <pthread.h>
#include <stdatomic.h>
#include "hle_lan_backend.h"
#define LOG(...) ((void)0)
static __thread int t_skerr;
static int sk_fail(void) {return -1;}
static _Atomic(const dm_lan_socket_backend *) g_lan_sockets;
typedef struct { int32_t fd; int16_t events, revents; } sk_pollfd;
static int dm_detclock_enabled(void) {return 0;}
static void dm_guest_cond_wait_ns(pthread_cond_t *c,pthread_mutex_t *m,int64_t ns) {(void)c;(void)m;(void)ns;}
static void dm_guest_sleep_ns(int64_t ns) {(void)ns;}
static uint64_t guest_ns(void) {static uint64_t t; return ++t*1000000;}
static int sk_idle(int64_t ms) {(void)ms;return 0;}
''' + source + r'''
static int lan_state;
static int test_ready(int fd) {(void)fd;return lan_state;}
int main(void) {
    int e=efd_create(0,0), s=dm_net_reserve_fd(), other=efd_create(0,0);
    if (e!=0 || s!=1 || other!=2 || efd_used(s)) return 1;
    if (dm_net_release_fd(e)!=-1 || efd_close(s)!=-1) return 2;
    if (dm_net_register_lan_ready(test_ready) || dm_net_register_lan_ready(test_ready)!=-1) return 5;
    sk_pollfd p[2]={{e,1,0},{s,0x45,0}};
    uint64_t open=(1ull<<e)|(1ull<<s);
    uint64_t gen[EFD_MAX]={0}; gen[e]=g_efd[e].generation; gen[s]=g_efd[s].generation;
    lan_state=1; if (efd_ready(p,2,open,gen)!=1 || p[1].revents!=0x41) return 6;
    lan_state=4; if (efd_ready(p,2,open,gen)!=1 || p[1].revents!=4) return 7;
    if (efd_write(e,1) || efd_ready(p,2,open,gen)!=2 || p[0].revents!=1) return 8;
    if (dm_sk_poll(p,2,0)!=2 || p[0].revents!=1 || p[1].revents!=4) return 11;
    lan_state=-1; if (efd_ready(p,2,open,gen)!=2 || p[1].revents!=0x20) return 9;
    if (dm_net_release_fd(s)!=0 || efd_create(0,0)!=s) return 3;
    if (efd_ready(p,2,open,gen)!=2 || p[1].revents!=0x20) return 10;
    if (dm_net_release_fd(s)!=-1) return 4;
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src=pathlib.Path(tmp)/'fd.c'; exe=pathlib.Path(tmp)/'fd.exe'; src.write_text(source,encoding='utf-8')
            subprocess.run([clang,'-std=c11','-I',str(ROOT/'engine/dm/host'),str(src),'-o',str(exe),'-pthread'],check=True)
            subprocess.run([str(exe)],check=True)
    def test_offline_and_registered_backend(self):
        clang=os.environ.get('SPPLE_TEST_CLANG',r'C:\msys64\mingw64\bin\clang.exe')
        source=(ROOT/'engine/dm/host/hle_offline.c').read_text(encoding='utf-8')
        source=source.split('// ---------- bluetooth:')[0]
        source=source.split('// ---------- prepo:')[0] + source[source.index('// ---------- ldn:'):]
        source=source.replace('#include "hle.h"', r"""
#include <stdint.h>
#include <stddef.h>
typedef uint32_t Result;
#define RES_FAIL 0x2a2u
#define RES_OK 0u
#define LOG(...) ((void)0)
#define HLE_FORCE(name, desc, ret, fn, ...) ret fn(__VA_ARGS__)
static void hle_bind_system_event(void *p, int x) {(void)p;(void)x;}
static uint64_t fake_binding=7, signalled=0;
static uint64_t hle_system_event_binding(void *p) {(void)p;return fake_binding;}
static int hle_signal_system_event_binding(uint64_t b) {signalled=b;return 1;}
""")
        source+=r"""
static uint32_t ok(void) {return 123;}
static void fini(void) {}
static int state(void) {return 5;}
static void attach(void *p) {(void)p;}
static uint32_t scan(void *p,int *n,int m,const void *f,int c,int priv) {(void)p;(void)m;(void)f;(void)c;*n=priv+7;return 321;}
static uint32_t create(const void *a,const void *b,const void *c) {(void)a;(void)b;(void)c;return 111;}
static uint32_t connectfn(const void *a,const void *b,const void *c,int d,int e) {(void)a;(void)b;(void)c;(void)d;(void)e;return 222;}
static uint32_t info(void *p) {(void)p;return 333;}
static uint32_t ip(uint32_t *a,uint32_t *m) {*a=1;*m=2;return 444;}
static uint32_t advertise(const void *p,uint64_t n) {(void)p;(void)n;return 555;}
int main(void) {
    int n=99; uint32_t a=7,m=7;
    if (h_ldn_Init()!=RES_FAIL || h_ldn_State()!=0 || h_ldn_Scan(0,&n,0,0,0)!=RES_FAIL || n) return 1;
    if (h_ldn_Ip(&a,&m)!=RES_FAIL || a || m) return 2;
    dm_lan_backend b={ok,fini,state,attach,ok,ok,ok,ok,ok,ok,scan,create,connectfn,info,ip,advertise};
    dm_lan_backend invalid=b; invalid.connect=0;
    if (dm_lan_register_backend(&invalid)!=-1 || dm_lan_register_backend(&b)!=0 || dm_lan_register_backend(&b)!=-1) return 3;
    if (h_ldn_Init()!=123 || h_ldn_State()!=5 || h_ldn_OpenSta()!=123) return 4;
    if (h_ldn_ScanP(0,&n,0,0,0)!=321 || n!=8 || h_ldn_Ip(&a,&m)!=444 || a!=1 || m!=2) return 5;
    if (h_ldn_Create(0,0,0)!=111 || h_ldn_Connect(0,0,0,0,0)!=222 || h_ldn_Adv(0,0)!=555) return 6;
    dm_lan_event_attach(&n); dm_lan_event_signal(); if (signalled != 7) return 7;
    signalled=0; dm_lan_event_reset(); dm_lan_event_signal(); if (signalled) return 8;
    fake_binding=9; dm_lan_event_attach(&n); dm_lan_event_signal(); if (signalled!=9) return 9;
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            src=pathlib.Path(tmp)/'seam.c'; exe=pathlib.Path(tmp)/'seam.exe'; src.write_text(source,encoding='utf-8')
            subprocess.run([clang,'-std=c11','-I',str(ROOT/'engine/dm/host'),str(src),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
if __name__=='__main__': unittest.main()
