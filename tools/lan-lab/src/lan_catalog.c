#include "lan_catalog.h"
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#define LIMIT 16
typedef struct {int used,complete;spple_lan_endpoint endpoint;uint8_t session[16];} entry;
struct spple_lan_catalog {pthread_mutex_t mu;entry entries[LIMIT];};
static int find_generation(spple_lan_catalog *c,uint64_t generation) {for(int i=0;i<LIMIT;++i)if(c->entries[i].used && c->entries[i].endpoint.generation==generation)return i;return -1;}
static int nonzero(const uint8_t *id){unsigned x=0;for(int i=0;i<16;++i)x|=id[i];return !!x;}
spple_lan_catalog *spple_lan_catalog_new(void){spple_lan_catalog *c=calloc(1,sizeof(*c));if(c && pthread_mutex_init(&c->mu,NULL)){free(c);return NULL;}return c;}
void spple_lan_catalog_free(spple_lan_catalog *c){if(!c)return;pthread_mutex_destroy(&c->mu);free(c);}
int spple_lan_catalog_begin(spple_lan_catalog *c,uint64_t gen,uint32_t index,const char *host,uint16_t port){
 if(!c || !gen || !index || !host || !*host || strlen(host)>=256 || !port)return -1;
 pthread_mutex_lock(&c->mu);if(find_generation(c,gen)>=0){pthread_mutex_unlock(&c->mu);return -1;}
 int n=-1;for(int i=0;i<LIMIT;++i)if(!c->entries[i].used){n=i;break;}
 if(n>=0){entry *e=&c->entries[n];memset(e,0,sizeof(*e));e->used=1;e->endpoint.generation=gen;e->endpoint.interface_index=index;e->endpoint.port=port;strcpy(e->endpoint.host,host);}
 pthread_mutex_unlock(&c->mu);return n>=0?0:-1;
}
int spple_lan_catalog_complete(spple_lan_catalog *c,uint64_t gen,const spple_ldn_network_info *room){
 if(!c || !gen || !room || spple_ldn_validate_network(room) || !nonzero(room->network_id.session_id))return -1;
 pthread_mutex_lock(&c->mu);int n=find_generation(c,gen),ok=n>=0 && !c->entries[n].complete;
 if(ok)for(int i=0;i<LIMIT;++i)if(i!=n && c->entries[i].used && c->entries[i].complete && !memcmp(c->entries[i].session,room->network_id.session_id,16)){ok=0;break;}
 if(ok){memcpy(c->entries[n].session,room->network_id.session_id,16);c->entries[n].complete=1;}
 pthread_mutex_unlock(&c->mu);return ok?0:-1;
}
int spple_lan_catalog_remove(spple_lan_catalog *c,uint64_t gen,uint8_t out[16]){
 if(!c || !gen || !out)return -1;pthread_mutex_lock(&c->mu);int n=find_generation(c,gen);
 if(n<0){pthread_mutex_unlock(&c->mu);return -1;}int rc=c->entries[n].complete;
 if(rc)memcpy(out,c->entries[n].session,16);else memset(out,0,16);memset(&c->entries[n],0,sizeof(entry));pthread_mutex_unlock(&c->mu);return rc;
}
int spple_lan_catalog_lookup(spple_lan_catalog *c,const uint8_t session[16],spple_lan_endpoint *out){
 if(!c || !session || !out || !nonzero(session))return -1;pthread_mutex_lock(&c->mu);int n=-1;
 for(int i=0;i<LIMIT;++i)if(c->entries[i].used && c->entries[i].complete && !memcmp(c->entries[i].session,session,16)){n=i;break;}
 if(n>=0)*out=c->entries[n].endpoint;pthread_mutex_unlock(&c->mu);return n>=0?0:-1;
}
int spple_lan_catalog_pending(spple_lan_catalog *c,uint64_t gen) {
 if(!c || !gen)return 0;pthread_mutex_lock(&c->mu);int n=find_generation(c,gen);int pending=n>=0 && !c->entries[n].complete;
 pthread_mutex_unlock(&c->mu);return pending;
}
