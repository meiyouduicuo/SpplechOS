#include "lan_browser.h"
#include "lan_scanner.h"
#include "lan_connect.h"
#include "lan_room_exchange.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <stdio.h>
#ifdef _WIN32
#include <pthread_time.h>
#include <winsock2.h>
#define BADSOCK INVALID_SOCKET
#define SHUT(s) shutdown((SOCKET)(s),SD_BOTH)
#define DNS_FD(s) ((SOCKET)(s))
#else
#include <sys/socket.h>
#include <sys/select.h>
#include <unistd.h>
#include <errno.h>
#define BADSOCK (-1)
#define SHUT(s) shutdown((int)(s),SHUT_RDWR)
#define DNS_FD(s) (s)
#endif
#define JOBS 16
static void trace_code(const char *what,int code) {
 const char *enabled=getenv("DM_LDN_TRACE");if(enabled && !strcmp(enabled,"1"))fprintf(stderr,"[Spple LAN] browser %s: %d\n",what,code);
}
typedef struct {uint64_t generation,next_ms;char host[256];uint16_t port;unsigned failures;} job;
struct spple_lan_browser {
 uint64_t title;spple_lan_catalog *catalog;spple_lan_scanner *scanner;
 spple_browser_found_fn found;spple_browser_removed_fn removed;void *context;
 pthread_t thread;pthread_mutex_t mu;_Atomic int stopped;int joined;intptr_t current;
 pthread_cond_t endpoint_changed;
 job jobs[JOBS];unsigned head,count;
};
static uint64_t now_ms(void){
#ifdef _WIN32
 return (uint64_t)GetTickCount64();
#else
 struct timespec ts;if(clock_gettime(CLOCK_MONOTONIC,&ts))return 0;
 return (uint64_t)ts.tv_sec*1000+(uint64_t)ts.tv_nsec/1000000;
#endif
}
static void found(void *ctx,const char *name,uint32_t index,uint64_t gen,const char *host,uint16_t port){
 (void)name;spple_lan_browser *b=ctx;
 if(b->count==JOBS || spple_lan_catalog_begin(b->catalog,gen,index,host,port))return;
 job *j=&b->jobs[(b->head+b->count)%JOBS];memset(j,0,sizeof(*j));j->generation=gen;j->port=port;strcpy(j->host,host);++b->count;
}
static void removed(void *ctx,const char *name,uint32_t index,uint64_t gen){
 (void)name;(void)index;spple_lan_browser *b=ctx;uint8_t session[16];
 int rc=spple_lan_catalog_remove(b->catalog,gen,session);if(rc==1)b->removed(b->context,session);
}
static void retry_job(spple_lan_browser *b,job *j) {
 if(atomic_load(&b->stopped) || !spple_lan_catalog_pending(b->catalog,j->generation) || b->count==JOBS)return;
 unsigned shift=j->failures<3?j->failures:3;if(j->failures<4)++j->failures;
 uint64_t now=now_ms(),delay=UINT64_C(1000)<<shift;j->next_ms=now>UINT64_MAX-delay?UINT64_MAX:now+delay;
 b->jobs[(b->head+b->count)%JOBS]=*j;++b->count;
}
static int probe_one(spple_lan_browser *b) {
 if(!b->count)return 0;
 unsigned checked=0;
 while(checked<b->count && b->jobs[b->head].next_ms>now_ms()) {
  job later=b->jobs[b->head];b->head=(b->head+1)%JOBS;
  b->jobs[(b->head+b->count-1)%JOBS]=later;++checked;
 }
 if(checked==b->count)return 0;
 job j=b->jobs[b->head];b->head=(b->head+1)%JOBS;--b->count;
 if(!spple_lan_catalog_pending(b->catalog,j.generation))return 1;
 intptr_t fd;int connect_rc=spple_lan_connect(j.host,j.port,2000,&fd);
 if(connect_rc){trace_code("room TCP probe failed",connect_rc);retry_job(b,&j);return 1;}
 pthread_mutex_lock(&b->mu);if(atomic_load(&b->stopped)){pthread_mutex_unlock(&b->mu);spple_lan_socket_close(fd);return 1;}
 b->current=fd;pthread_mutex_unlock(&b->mu);
 spple_ldn_network_info room;int rc=spple_room_exchange_client(fd,b->title,SPPLE_ROOM_PROBE,&room);
 pthread_mutex_lock(&b->mu);b->current=(intptr_t)BADSOCK;int stop=atomic_load(&b->stopped);pthread_mutex_unlock(&b->mu);
 spple_lan_socket_close(fd);
 if(!rc && !stop){
  trace_code("room probe authenticated",0);
  if(!spple_lan_catalog_complete(b->catalog,j.generation,&room)){
   b->found(b->context,&room);
   pthread_mutex_lock(&b->mu);
   pthread_cond_broadcast(&b->endpoint_changed);
   pthread_mutex_unlock(&b->mu);
  }else{
   trace_code("room catalog completion rejected",0);
   uint8_t unused[16];(void)spple_lan_catalog_remove(b->catalog,j.generation,unused);
  }
 }
 else if(!stop){trace_code("room probe handshake failed",rc);retry_job(b,&j);}
 return 1;
}
static void *run(void *ctx){
 spple_lan_browser *b=ctx;b->scanner=spple_lan_scanner_new(now_ms(),found,removed,b);if(!b->scanner)return NULL;
 while(!atomic_load(&b->stopped)) {
  if(spple_lan_scanner_tick(b->scanner,now_ms(),0,0))break;
  if(probe_one(b))continue;
  int a=-1,c=-1;spple_lan_scanner_fds(b->scanner,&a,&c);fd_set set;FD_ZERO(&set);int high=-1;
#ifndef _WIN32
  if(a>=FD_SETSIZE || c>=FD_SETSIZE)break;
#endif
  if(a>=0){FD_SET(DNS_FD(a),&set);high=a;}if(c>=0){FD_SET(DNS_FD(c),&set);if(c>high)high=c;}
  struct timeval wait={0,250000};
#ifdef _WIN32
  int n=high>=0?select(0,&set,NULL,NULL,&wait):0;
  if(high<0)Sleep(250);
#else
  int n=select(high+1,&set,NULL,NULL,&wait);
#endif
  if(n<0) {
#ifdef _WIN32
   if(WSAGetLastError()==WSAEINTR)continue;
#else
   if(errno==EINTR)continue;
#endif
   break;
  }
  if(n>0 && spple_lan_scanner_tick(b->scanner,now_ms(),a>=0 && FD_ISSET(DNS_FD(a),&set),c>=0 && FD_ISSET(DNS_FD(c),&set)))break;
 }
 spple_lan_scanner_free(b->scanner);b->scanner=NULL;return NULL;
}
spple_lan_browser *spple_lan_browser_start(uint64_t title,spple_browser_found_fn f,spple_browser_removed_fn r,void *ctx){
 if(!title || !f || !r)return NULL;spple_lan_browser *b=calloc(1,sizeof(*b));if(!b)return NULL;
 if(pthread_mutex_init(&b->mu,NULL)){free(b);return NULL;}
 if(pthread_cond_init(&b->endpoint_changed,NULL)){pthread_mutex_destroy(&b->mu);free(b);return NULL;}
 b->catalog=spple_lan_catalog_new();
 if(!b->catalog){pthread_cond_destroy(&b->endpoint_changed);pthread_mutex_destroy(&b->mu);free(b);return NULL;}
 b->title=title;b->found=f;b->removed=r;b->context=ctx;b->current=(intptr_t)BADSOCK;atomic_init(&b->stopped,0);
 if(pthread_create(&b->thread,NULL,run,b)){spple_lan_catalog_free(b->catalog);pthread_cond_destroy(&b->endpoint_changed);pthread_mutex_destroy(&b->mu);free(b);return NULL;}return b;
}
int spple_lan_browser_lookup(spple_lan_browser *b,const uint8_t session[16],spple_lan_endpoint *out){return b?spple_lan_catalog_lookup(b->catalog,session,out):-1;}
int spple_lan_browser_wait(spple_lan_browser *b,const uint8_t session[16],spple_lan_endpoint *out){
 if(!b || !session || !out)return -1;
 struct timespec deadline;
 if(clock_gettime(CLOCK_REALTIME,&deadline))return -1;
 deadline.tv_sec+=3;
 pthread_mutex_lock(&b->mu);
 int result=-1;
 while(!atomic_load(&b->stopped)){
  result=spple_lan_browser_lookup(b,session,out);
  if(!result || pthread_cond_timedwait(&b->endpoint_changed,&b->mu,&deadline)) break;
 }
 pthread_mutex_unlock(&b->mu);
 return result;
}
void spple_lan_browser_stop(spple_lan_browser *b){
 if(!b || b->joined)return;atomic_store(&b->stopped,1);pthread_mutex_lock(&b->mu);if(b->current!=(intptr_t)BADSOCK)SHUT(b->current);pthread_cond_broadcast(&b->endpoint_changed);pthread_mutex_unlock(&b->mu);
 pthread_join(b->thread,NULL);b->joined=1;
}
void spple_lan_browser_destroy(spple_lan_browser *b){if(!b)return;spple_lan_browser_stop(b);spple_lan_catalog_free(b->catalog);pthread_cond_destroy(&b->endpoint_changed);pthread_mutex_destroy(&b->mu);free(b);}
