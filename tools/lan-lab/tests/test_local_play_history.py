"""Exercise the actual friends HLE used during MHR local-player setup."""
import os, pathlib, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[3]
class LocalHistoryTests(unittest.TestCase):
 def test_local_key_initialization_and_scope(self):
  source=(ROOT/'engine/dm/host/hle_friends.c').read_text(encoding='utf-8')
  start=source.find('// SpplechOS local play-history identity')
  if start<0:start=source.index('HLE_FORCE("_ZN2nn7friends29GetPlayHistoryRegistrationKey')
  body=source[start:source.index('// Notification queue',start)]
  code=r"""
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <pthread.h>
#include <stdio.h>
typedef uint32_t Result;
#define RES_OK 0
#define RES_FAIL 0x2a2
#define LOG(...) ((void)0)
#define HLE_FORCE(symbol,description,ret,name,...) ret name(__VA_ARGS__)
static int active, draws;
static uint32_t dm_lan_ip_config(uint32_t *a,uint32_t *m){(void)a;(void)m;return active?RES_OK:RES_FAIL;}
static int dm_account_is_local_user(const void *uid){return uid && *(const uint64_t *)uid==123;}
static void test_random(void *out,size_t n){++draws;memset(out,0x5a,n);}
#define arc4random_buf test_random
"""+body+r"""
int main(void){
 uint64_t uid[2]={123,1},bad[2]={999,1};
 unsigned char a[66],b[64];memset(a,0xcc,sizeof a);
 active=1;
 if(h_fr_GetPHKey(a+1,uid,1)!=RES_OK){fprintf(stderr,"local player setup rejected\n");return 1;}
 if(a[0]!=0xcc || a[65]!=0xcc || !memcmp(a+1,(unsigned char[64]){0},64))return 2;
 if(h_fr_GetPHKey(b,uid,1)!=RES_OK || memcmp(a+1,b,64) || draws!=1)return 3;
 if(h_fr_GetPHKey(b,uid,0)==RES_OK || h_fr_GetPHKey(b,bad,1)==RES_OK || h_fr_GetPHKey(0,uid,1)==RES_OK)return 4;
 active=0;memset(b,0xdd,64);
 if(h_fr_GetPHKey(b,uid,1)==RES_OK || b[0]!=0xdd)return 5;
 return 0;
}
"""
  with tempfile.TemporaryDirectory() as tmp:
   src=pathlib.Path(tmp)/'test.c';exe=pathlib.Path(tmp)/'test.exe';src.write_text(code,encoding='utf-8')
   subprocess.run([os.environ.get('SPPLE_TEST_CLANG',r'C:\msys64\mingw64\bin\clang.exe'),'-std=c11',str(src),'-pthread','-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
