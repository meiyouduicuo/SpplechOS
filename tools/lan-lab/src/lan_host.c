#include "lan_host.h"
#include "lan_advertiser.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <time.h>
#ifdef _WIN32
#include <winsock2.h>
#define DNS_FD(s) ((SOCKET)(s))
#else
#include <sys/select.h>
#include <errno.h>
#define DNS_FD(s) (s)
#endif
struct spple_lan_host {spple_lan_server *server;spple_lan_advertiser *advertiser;pthread_t thread;_Atomic int stopped;int joined;spple_host_status_fn status;void *context;};
static uint64_t now_ms(void){
#ifdef _WIN32
 return (uint64_t)GetTickCount64();
#else
 struct timespec t;if(clock_gettime(CLOCK_MONOTONIC,&t))return 0;return (uint64_t)t.tv_sec*1000+(uint64_t)t.tv_nsec/1000000;
#endif
}
static void *run(void *ctx){
 spple_lan_host *h=ctx;int published=0;
 while(!atomic_load(&h->stopped)) {
  int status=spple_lan_advertiser_tick(h->advertiser,now_ms(),0);
  if(status<0){if(!atomic_load(&h->stopped))h->status(h->context,0);break;}
  if(status!=published){published=status;h->status(h->context,status);}
  int fd=spple_lan_advertiser_fd(h->advertiser);fd_set set;FD_ZERO(&set);
#ifndef _WIN32
  if(fd>=FD_SETSIZE){h->status(h->context,0);break;}
#endif
  if(fd>=0)FD_SET(DNS_FD(fd),&set);struct timeval wait={0,250000};
#ifdef _WIN32
  int n=fd>=0?select(0,&set,NULL,NULL,&wait):0;if(fd<0)Sleep(250);
#else
  int n=select(fd+1,&set,NULL,NULL,&wait);
#endif
  if(n<0) {
#ifdef _WIN32
   if(WSAGetLastError()==WSAEINTR)continue;
#else
   if(errno==EINTR)continue;
#endif
   if(!atomic_load(&h->stopped))h->status(h->context,0);break;
  }
  if(n>0 && fd>=0 && FD_ISSET(DNS_FD(fd),&set)) {
   status=spple_lan_advertiser_tick(h->advertiser,now_ms(),1);
   if(status<0){if(!atomic_load(&h->stopped))h->status(h->context,0);break;}
   if(status!=published){published=status;h->status(h->context,status);}
  }
 }
 return NULL;
}
spple_lan_host *spple_lan_host_start(uint64_t title,const char *name,const void *key,size_t key_size,spple_server_snapshot_fn snapshot,spple_room_random_fn random,spple_join_accept_fn accept,spple_server_joined_fn joined,spple_server_rollback_fn rollback,spple_host_status_fn status,void *context){
 if(!status)return NULL;spple_lan_host *h=calloc(1,sizeof(*h));if(!h)return NULL;
 h->server=spple_lan_server_start(title,key,key_size,snapshot,random,accept,joined,rollback,context);if(!h->server){free(h);return NULL;}
 h->advertiser=spple_lan_advertiser_new(name,spple_lan_server_port(h->server),now_ms());
 if(!h->advertiser){spple_lan_server_destroy(h->server);free(h);return NULL;}
 h->status=status;h->context=context;atomic_init(&h->stopped,0);
 if(pthread_create(&h->thread,NULL,run,h)){spple_lan_advertiser_free(h->advertiser);spple_lan_server_destroy(h->server);free(h);return NULL;}
 return h;
}
void spple_lan_host_stop(spple_lan_host *h){if(!h || h->joined)return;atomic_store(&h->stopped,1);pthread_join(h->thread,NULL);spple_lan_server_stop(h->server);h->joined=1;}
void spple_lan_host_destroy(spple_lan_host *h){if(!h)return;spple_lan_host_stop(h);spple_lan_advertiser_free(h->advertiser);spple_lan_server_destroy(h->server);free(h);}
