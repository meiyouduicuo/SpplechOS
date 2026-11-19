#include "lan_server.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <winsock2.h>
typedef SOCKET sock_t;
#define BADSOCK INVALID_SOCKET
#define CLOSE(s) closesocket(s)
#define SHUT(s) shutdown(s,SD_BOTH)
#else
#include <unistd.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <netinet/in.h>
#include <arpa/inet.h>
typedef int sock_t;
#define BADSOCK (-1)
#define CLOSE(s) close(s)
#define SHUT(s) shutdown(s,SHUT_RDWR)
#endif
struct spple_lan_server {
 sock_t listener,current;uint16_t port;uint64_t title;uint8_t key[64];size_t key_size;
 pthread_t thread;pthread_mutex_t mu;_Atomic int stopped;int joined;
 spple_server_snapshot_fn snapshot;spple_room_random_fn random;spple_join_accept_fn accept;
 spple_server_joined_fn on_join;spple_server_rollback_fn rollback;void *context;
};
typedef struct {spple_lan_server *server;int accepted;} handler_context;
static int handler_random(void *ctx,void *out,size_t size) {
 handler_context *h=ctx;return h->server->random(h->server->context,out,size);
}
static int handler_accept(void *ctx,const spple_ldn_user_config *user,int version,int option,spple_ldn_network_info *out) {
 handler_context *h=ctx;int rc=h->server->accept(h->server->context,user,version,option,out);
 if(!rc)h->accepted=1;return rc;
}
static void configure(sock_t s) {
#ifdef _WIN32
 DWORD timeout=3000;setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,(const char *)&timeout,sizeof timeout);setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,(const char *)&timeout,sizeof timeout);
#else
 struct timeval timeout={3,0};setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof timeout);setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof timeout);
#ifdef SO_NOSIGPIPE
 int one=1;setsockopt(s,SOL_SOCKET,SO_NOSIGPIPE,&one,sizeof one);
#endif
#endif
}
static void *run_server(void *p) {
 spple_lan_server *s=p;
 while(!atomic_load(&s->stopped)) {
#ifndef _WIN32
  if(s->listener<0 || s->listener>=FD_SETSIZE)break;
#endif
  fd_set set;FD_ZERO(&set);FD_SET(s->listener,&set);struct timeval wait={0,250000};
#ifdef _WIN32
  int r=select(0,&set,NULL,NULL,&wait);
#else
  int r=select(s->listener+1,&set,NULL,NULL,&wait);
#endif
  if(r<=0)continue;sock_t client=accept(s->listener,NULL,NULL);if(client==BADSOCK)continue;
  pthread_mutex_lock(&s->mu);
  if(atomic_load(&s->stopped)){pthread_mutex_unlock(&s->mu);CLOSE(client);break;}
  s->current=client;pthread_mutex_unlock(&s->mu);configure(client);
  spple_ldn_network_info room;handler_context handler={s,0};int outcome=s->snapshot(s->context,&room)?-1:
   spple_room_listener_handle((intptr_t)client,s->title,&room,s->key,s->key_size,handler_random,handler_accept,&handler);
  pthread_mutex_lock(&s->mu);s->current=BADSOCK;int stopped=atomic_load(&s->stopped);pthread_mutex_unlock(&s->mu);
  if(outcome==2 && !stopped && !s->on_join(s->context,(intptr_t)client)) { /* handed off */ }
  else {if(handler.accepted)s->rollback(s->context);CLOSE(client);}
 }
 return NULL;
}
spple_lan_server *spple_lan_server_start(uint64_t title,const void *key,size_t key_size,spple_server_snapshot_fn snapshot,spple_room_random_fn random,spple_join_accept_fn accept,spple_server_joined_fn joined,spple_server_rollback_fn rollback,void *context) {
 if(!title || !key || key_size<16 || key_size>64 || !snapshot || !random || !accept || !joined || !rollback)return NULL;
 spple_lan_server *s=calloc(1,sizeof(*s));if(!s)return NULL;s->listener=s->current=BADSOCK;
 if(pthread_mutex_init(&s->mu,NULL)){free(s);return NULL;}
 s->listener=socket(AF_INET,SOCK_STREAM,0);if(s->listener==BADSOCK)goto fail;
 struct sockaddr_in addr;memset(&addr,0,sizeof addr);addr.sin_family=AF_INET;addr.sin_addr.s_addr=htonl(INADDR_ANY);
 if(bind(s->listener,(struct sockaddr *)&addr,sizeof addr) || listen(s->listener,8))goto fail;
#ifdef _WIN32
 int len=sizeof addr;
#else
 socklen_t len=sizeof addr;
#endif
 if(getsockname(s->listener,(struct sockaddr *)&addr,&len))goto fail;
 s->port=ntohs(addr.sin_port);s->title=title;memcpy(s->key,key,key_size);s->key_size=key_size;
 s->snapshot=snapshot;s->random=random;s->accept=accept;s->on_join=joined;s->rollback=rollback;s->context=context;atomic_init(&s->stopped,0);
 if(pthread_create(&s->thread,NULL,run_server,s))goto fail;return s;
fail:
 if(s->listener!=BADSOCK)CLOSE(s->listener);pthread_mutex_destroy(&s->mu);free(s);return NULL;
}
uint16_t spple_lan_server_port(const spple_lan_server *s){return s?s->port:0;}
void spple_lan_server_stop(spple_lan_server *s){
 if(!s || s->joined)return;atomic_store(&s->stopped,1);SHUT(s->listener);
 pthread_mutex_lock(&s->mu);if(s->current!=BADSOCK)SHUT(s->current);pthread_mutex_unlock(&s->mu);
 pthread_join(s->thread,NULL);s->joined=1;CLOSE(s->listener);s->listener=BADSOCK;
}
void spple_lan_server_destroy(spple_lan_server *s){
 if(!s)return;spple_lan_server_stop(s);volatile uint8_t *p=s->key;for(size_t i=0;i<sizeof s->key;++i)p[i]=0;
 pthread_mutex_destroy(&s->mu);free(s);
}
