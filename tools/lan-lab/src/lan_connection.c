#include "lan_connection.h"
#include "lan_io.h"
#include "lan_connect.h"
#include "guest_socket_bridge.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
struct spple_lan_connection {pthread_mutex_t mu;pthread_cond_t cond;spple_lan_io *io;intptr_t socket;int ready,closing,joined;spple_connection_room_fn room;spple_connection_failed_fn failed;void *context;};
static int ingest(void *ctx,const void *data,size_t size){(void)ctx;return spple_guest_socket_bridge_ingest(data,size);}
static void failure(void *ctx){
 spple_lan_connection *c=ctx;pthread_mutex_lock(&c->mu);
 while(!c->ready && !c->closing)pthread_cond_wait(&c->cond,&c->mu);
 int notify=!c->closing;pthread_mutex_unlock(&c->mu);
 if(notify){spple_guest_socket_bridge_stop();c->failed(c->context);}
}
static int room_update(void *ctx,const spple_ldn_network_info *room){
 spple_lan_connection *c=ctx;pthread_mutex_lock(&c->mu);
 while(!c->ready && !c->closing)pthread_cond_wait(&c->cond,&c->mu);
 int ok=!c->closing && c->room;pthread_mutex_unlock(&c->mu);
 return ok?c->room(c->context,room):-1;
}
spple_lan_connection *spple_lan_connection_start(intptr_t socket,uint64_t title,const uint8_t session[16],const uint8_t local[4],const uint8_t peer[4],spple_connection_failed_fn failed,void *context){
 return spple_lan_connection_start_ex(socket,title,session,local,peer,NULL,failed,context);
}
spple_lan_connection *spple_lan_connection_start_ex(intptr_t socket,uint64_t title,const uint8_t session[16],const uint8_t local[4],const uint8_t peer[4],spple_connection_room_fn room,spple_connection_failed_fn failed,void *context){
 if(!failed)return NULL;spple_lan_connection *c=calloc(1,sizeof(*c));if(!c)return NULL;
 if(pthread_mutex_init(&c->mu,NULL)){free(c);return NULL;}
 if(pthread_cond_init(&c->cond,NULL)){pthread_mutex_destroy(&c->mu);free(c);return NULL;}
 c->room=room;c->failed=failed;c->context=context;c->socket=socket;
 if(spple_guest_socket_bridge_resume(local,peer))goto fail;
 c->io=spple_lan_io_start_ex(socket,title,session,ingest,room?room_update:NULL,failure,c);
 if(!c->io){spple_guest_socket_bridge_stop();goto fail;}
 return c;
fail:pthread_cond_destroy(&c->cond);pthread_mutex_destroy(&c->mu);free(c);return NULL;
}
void spple_lan_connection_ready(spple_lan_connection *c){if(!c)return;pthread_mutex_lock(&c->mu);c->ready=1;pthread_cond_broadcast(&c->cond);pthread_mutex_unlock(&c->mu);}
int spple_lan_connection_send(void *context,const void *data,size_t size){spple_lan_connection *c=context;return c?spple_lan_io_send(c->io,data,size):-1;}
int spple_lan_connection_send_room(spple_lan_connection *c,const spple_ldn_network_info *room){return c?spple_lan_io_send_room(c->io,room):-1;}
void spple_lan_connection_stop(spple_lan_connection *c){
 if(!c || c->joined)return;pthread_mutex_lock(&c->mu);c->closing=1;pthread_cond_broadcast(&c->cond);pthread_mutex_unlock(&c->mu);
 spple_guest_socket_bridge_stop();spple_lan_io_stop(c->io);c->joined=1;
}
void spple_lan_connection_destroy(spple_lan_connection *c){
 if(!c)return;spple_lan_connection_stop(c);spple_lan_io_destroy(c->io);spple_lan_socket_close(c->socket);
 pthread_cond_destroy(&c->cond);pthread_mutex_destroy(&c->mu);free(c);
}
