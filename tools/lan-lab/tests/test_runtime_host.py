import os,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[3];LAB=ROOT/'tools/lan-lab/src'
class RuntimeHostTests(unittest.TestCase):
 def test_host_lifecycle_and_station_rollback(self):
  code=r"""
#include <stdlib.h>
#include <string.h>
#include "lan_runtime_host.h"
#include "ldn_room_builder.h"
static spple_server_snapshot_fn snap;static spple_join_accept_fn acceptfn;static spple_server_joined_fn joinfn;static spple_server_rollback_fn rollbackfn;static void *owner;
spple_lan_host *spple_lan_host_start(uint64_t t,const char *n,const void *k,size_t z,spple_server_snapshot_fn s,spple_room_random_fn r,spple_join_accept_fn a,spple_server_joined_fn j,spple_server_rollback_fn b,spple_host_status_fn status,void *c){
 (void)t;(void)n;(void)k;(void)z;(void)r;snap=s;acceptfn=a;joinfn=j;rollbackfn=b;owner=c;status(c,1);return (spple_lan_host *)malloc(1);
}
void spple_lan_host_stop(spple_lan_host *h){(void)h;}
void spple_lan_host_destroy(spple_lan_host *h){free(h);}
static int changes,open_fail,statuses;
static int randomfn(void *c,void *out,size_t n){(void)c;memset(out,0x55,n);return 0;}
static void statusfn(void *c,int on){(void)c;statuses+=on;}
static int openedfn(void *c,intptr_t fd){(void)c;(void)fd;return open_fail;}
static void changedfn(void *c,const spple_ldn_network_info *n){(void)c;if(n->node_count==1 || n->node_count==2)changes++;}
int main(void){
 spple_ldn_network_config cfg={0};cfg.intent.local_communication_id=123;cfg.node_count_max=4;
 spple_ldn_user_config user={0};uint8_t entropy[32],ip[4]={10,77,0,1},key[16]={1};memset(entropy,1,sizeof entropy);
 spple_ldn_network_info r,out;if(spple_ldn_build_room(&cfg,&user,123,entropy,ip,&r))return 1;
 spple_runtime_host *h=spple_runtime_host_start(123,"room",key,sizeof key,&r,randomfn,statusfn,openedfn,changedfn,0);
 if(!h || statuses!=1 || snap(owner,&out))return 2;
 if(acceptfn(owner,&user,1,0,&out) || out.node_count!=2 || !acceptfn(owner,&user,1,0,&out))return 3;
 open_fail=1;if(!joinfn(owner,123))return 4;rollbackfn(owner);
 if(acceptfn(owner,&user,1,0,&out))return 5;open_fail=0;if(joinfn(owner,123) || changes!=1)return 6;
 if(spple_runtime_host_station_lost(h) || changes!=2)return 7;
 r.network_id.session_id[0]++;if(!spple_runtime_host_update(h,&r))return 8;
 spple_runtime_host_stop(h);if(!spple_runtime_host_snapshot(h,&out))return 9;
 spple_runtime_host_destroy(h);return 0;
}
"""
  with tempfile.TemporaryDirectory() as d:
   source=pathlib.Path(d)/'host.c';exe=pathlib.Path(d)/'host.exe';source.write_text(code,encoding='utf-8')
   clang=os.environ.get('SPPLE_TEST_CLANG',r'C:\msys64\mingw64\bin\clang.exe')
   subprocess.run([clang,'-std=c11','-I',str(LAB),str(source),str(LAB/'lan_runtime_host.c'),str(LAB/'ldn_room_builder.c'),str(LAB/'ldn_abi.c'),'-o',str(exe),'-pthread','-static'],check=True)
   subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
