#include "lan_runtime_host.h"
#include "ldn_room_builder.h"
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
struct spple_runtime_host {
 pthread_mutex_t mu;spple_lan_host *host;spple_ldn_network_info room,pending;
 int online,closing,pending_join;
 spple_room_random_fn random;spple_runtime_host_status_fn status;
 spple_runtime_host_opened_fn opened;spple_runtime_host_changed_fn changed;void *context;
};
static int snapshot(void *ctx,spple_ldn_network_info *out){
 spple_runtime_host *h=ctx;pthread_mutex_lock(&h->mu);int ok=h->online && !h->closing;
 if(ok)*out=h->room;pthread_mutex_unlock(&h->mu);return ok?0:-1;
}
static int random_bytes(void *ctx,void *out,size_t size){spple_runtime_host *h=ctx;return h->random(h->context,out,size);}
static int accept(void *ctx,const spple_ldn_user_config *user,int version,int option,spple_ldn_network_info *out){
 spple_runtime_host *h=ctx;uint8_t mac[6];static const uint8_t ip[4]={10,77,0,2};(void)option;
 if(h->random(h->context,mac,sizeof mac))return -1;
 pthread_mutex_lock(&h->mu);int rc=h->online && !h->closing && !h->pending_join && h->room.accept_policy==0 ? spple_ldn_room_add_station(&h->room,user,version,ip,mac,&h->pending):-1;
 if(!rc){h->pending_join=1;*out=h->pending;}pthread_mutex_unlock(&h->mu);return rc;
}
static int opened(void *ctx,intptr_t socket){
 spple_runtime_host *h=ctx;pthread_mutex_lock(&h->mu);int ok=h->pending_join && h->online && !h->closing;
 pthread_mutex_unlock(&h->mu);if(!ok || h->opened(h->context,socket))return -1;
 pthread_mutex_lock(&h->mu);h->room=h->pending;h->pending_join=0;spple_ldn_network_info room=h->room;
 pthread_mutex_unlock(&h->mu);h->changed(h->context,&room);return 0;
}
static void rollback(void *ctx){spple_runtime_host *h=ctx;pthread_mutex_lock(&h->mu);h->pending_join=0;pthread_mutex_unlock(&h->mu);}
static void status(void *ctx,int online){
 spple_runtime_host *h=ctx;pthread_mutex_lock(&h->mu);if(!online)h->online=0;int notify=!h->closing;pthread_mutex_unlock(&h->mu);
 if(notify)h->status(h->context,online);
 if(online){pthread_mutex_lock(&h->mu);h->online=!h->closing;pthread_mutex_unlock(&h->mu);}
}
spple_runtime_host *spple_runtime_host_start(uint64_t title,const char *name,const void *key,size_t key_size,const spple_ldn_network_info *room,spple_room_random_fn random,spple_runtime_host_status_fn status_fn,spple_runtime_host_opened_fn opened_fn,spple_runtime_host_changed_fn changed_fn,void *context){
 if(!room || spple_ldn_validate_network(room) || !random || !status_fn || !opened_fn || !changed_fn)return NULL;
 spple_runtime_host *h=calloc(1,sizeof(*h));if(!h)return NULL;if(pthread_mutex_init(&h->mu,NULL)){free(h);return NULL;}
 h->room=*room;h->random=random;h->status=status_fn;h->opened=opened_fn;h->changed=changed_fn;h->context=context;
 h->host=spple_lan_host_start(title,name,key,key_size,snapshot,random_bytes,accept,opened,rollback,status,h);
 if(!h->host){pthread_mutex_destroy(&h->mu);free(h);return NULL;}return h;
}
int spple_runtime_host_update(spple_runtime_host *h,const spple_ldn_network_info *room){
 if(!h || !room || spple_ldn_validate_network(room))return -1;pthread_mutex_lock(&h->mu);
 int ok=!h->closing && !h->pending_join && !memcmp(h->room.network_id.session_id,room->network_id.session_id,16) &&
 h->room.network_id.intent.local_communication_id==room->network_id.intent.local_communication_id && h->room.network_id.intent.scene_id==room->network_id.intent.scene_id;
 if(ok)h->room=*room;pthread_mutex_unlock(&h->mu);return ok?0:-1;
}
int spple_runtime_host_snapshot(spple_runtime_host *h,spple_ldn_network_info *room){return h && room?snapshot(h,room):-1;}
int spple_runtime_host_station_lost(spple_runtime_host *h){
 if(!h)return -1;pthread_mutex_lock(&h->mu);spple_ldn_network_info new_room;
 int rc=h->closing?-1:spple_ldn_room_remove_station(&h->room,&new_room);
 if(!rc)h->room=new_room;pthread_mutex_unlock(&h->mu);if(!rc)h->changed(h->context,&new_room);return rc;
}
void spple_runtime_host_stop(spple_runtime_host *h){if(!h)return;pthread_mutex_lock(&h->mu);h->closing=1;h->online=0;pthread_mutex_unlock(&h->mu);spple_lan_host_stop(h->host);}
void spple_runtime_host_destroy(spple_runtime_host *h){if(!h)return;spple_runtime_host_stop(h);spple_lan_host_destroy(h->host);pthread_mutex_destroy(&h->mu);free(h);}
