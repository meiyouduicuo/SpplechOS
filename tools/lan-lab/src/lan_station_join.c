#include "lan_station_join.h"
#include "lan_connect.h"
#include "lan_secure_join.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <winsock2.h>
#define BADSOCK INVALID_SOCKET
#define SHUT(s) shutdown((SOCKET)(s),SD_BOTH)
#else
#include <sys/socket.h>
#define BADSOCK (-1)
#define SHUT(s) shutdown((int)(s),SHUT_RDWR)
#endif
struct spple_station_join {
 uint64_t title;spple_lan_endpoint endpoint;spple_ldn_network_info expected;spple_ldn_user_config user;
 uint8_t key[64];size_t key_size;int version,option;
 spple_room_random_fn random;spple_station_opened_fn opened;spple_station_failed_fn failed;void *context;
 pthread_t thread;pthread_mutex_t mu;_Atomic int stopped;int joined;intptr_t current;
};
static int same_room(const spple_ldn_network_info *a,const spple_ldn_network_info *b){
 return !memcmp(a->network_id.session_id,b->network_id.session_id,16) &&
 a->network_id.intent.local_communication_id==b->network_id.intent.local_communication_id &&
 a->network_id.intent.scene_id==b->network_id.intent.scene_id && !memcmp(a->server_random,b->server_random,16);
}
static void *run(void *context){
 spple_station_join *j=context;uint8_t nonce[16];intptr_t fd=(intptr_t)BADSOCK;int transferred=0,ok=0,stop=0;
 if(j->random(j->context,nonce,sizeof nonce) || spple_lan_connect(j->endpoint.host,j->endpoint.port,2000,&fd))goto done;
 pthread_mutex_lock(&j->mu);if(atomic_load(&j->stopped)){pthread_mutex_unlock(&j->mu);goto done;}
 j->current=fd;pthread_mutex_unlock(&j->mu);spple_ldn_network_info room;
 if(spple_secure_join_client(fd,j->title,j->key,j->key_size,nonce,&j->user,j->version,j->option,&room) || !same_room(&j->expected,&room))goto done;
 pthread_mutex_lock(&j->mu);j->current=(intptr_t)BADSOCK;stop=atomic_load(&j->stopped);pthread_mutex_unlock(&j->mu);
 if(!stop && !j->opened(j->context,fd,&room)){transferred=ok=1;}
done:
 pthread_mutex_lock(&j->mu);j->current=(intptr_t)BADSOCK;stop=atomic_load(&j->stopped);pthread_mutex_unlock(&j->mu);
 if(fd!=(intptr_t)BADSOCK && !transferred)spple_lan_socket_close(fd);
 if(!ok && !stop)j->failed(j->context);return NULL;
}
spple_station_join *spple_station_join_start(uint64_t title,const spple_lan_endpoint *endpoint,const spple_ldn_network_info *expected,const void *key,size_t key_size,const spple_ldn_user_config *user,int version,int option,spple_room_random_fn random,spple_station_opened_fn opened,spple_station_failed_fn failed,void *ctx){
 if(!title || !endpoint || !endpoint->port || !memchr(endpoint->host,0,sizeof endpoint->host) || !*endpoint->host || !expected || spple_ldn_validate_network(expected) || !key || key_size<16 || key_size>64 || !user || !memchr(user->user_name,0,sizeof user->user_name) || version<0 || version>0x7fff || (option&~1) || !random || !opened || !failed)return NULL;
 spple_station_join *j=calloc(1,sizeof(*j));if(!j)return NULL;if(pthread_mutex_init(&j->mu,NULL)){free(j);return NULL;}
 j->title=title;j->endpoint=*endpoint;j->expected=*expected;j->user=*user;memcpy(j->key,key,key_size);j->key_size=key_size;
 j->version=version;j->option=option;j->random=random;j->opened=opened;j->failed=failed;j->context=ctx;j->current=(intptr_t)BADSOCK;atomic_init(&j->stopped,0);
 if(pthread_create(&j->thread,NULL,run,j)){pthread_mutex_destroy(&j->mu);memset(j->key,0,sizeof j->key);free(j);return NULL;}return j;
}
void spple_station_join_wait(spple_station_join *j){
 if(!j || j->joined)return;
 pthread_join(j->thread,NULL);
 j->joined=1;
}
void spple_station_join_stop(spple_station_join *j){if(!j || j->joined)return;atomic_store(&j->stopped,1);pthread_mutex_lock(&j->mu);if(j->current!=(intptr_t)BADSOCK)SHUT(j->current);pthread_mutex_unlock(&j->mu);spple_station_join_wait(j);}
void spple_station_join_destroy(spple_station_join *j){if(!j)return;spple_station_join_stop(j);volatile uint8_t *p=j->key;for(size_t i=0;i<sizeof j->key;++i)p[i]=0;pthread_mutex_destroy(&j->mu);free(j);}
