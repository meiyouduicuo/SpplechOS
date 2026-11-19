#include "lan_advertiser.h"
#include "lan_discovery.h"
#include "lan_retry.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
static void log_status(const char *what,int code){const char *v=getenv("DM_LDN_TRACE");if(v && !strcmp(v,"1"))fprintf(stderr,"[Spple LAN] advertisement %s: %d\n",what,code);}
struct spple_lan_advertiser {char name[64];uint16_t port;spple_discovery *op;spple_lan_retry retry;int error,published,failed;};
static void registered(void *context,int error) {spple_lan_advertiser *a=context;log_status("callback",error);if(error)a->error=error;else a->published=1;}
spple_lan_advertiser *spple_lan_advertiser_new(const char *name,uint16_t port,uint64_t now) {
 if(!name || !*name || strlen(name)>=64 || !port)return NULL;
 spple_lan_advertiser *a=calloc(1,sizeof(*a));if(!a)return NULL;
 strcpy(a->name,name);a->port=port;spple_lan_retry_init(&a->retry,now,120000);return a;
}
int spple_lan_advertiser_tick(spple_lan_advertiser *a,uint64_t now,int readable) {
 if(!a || a->failed)return -1;
 if(!a->published && spple_lan_retry_ready(&a->retry,now)<0){a->failed=1;if(a->op){spple_discovery_stop(a->op);a->op=NULL;}return -1;}
 if(!a->op) {
  int ready=spple_lan_retry_ready(&a->retry,now);if(ready<0){a->failed=1;return -1;}if(!ready)return 0;
  a->error=0;a->published=0;
  int rc=spple_discovery_advertise_observed(&a->op,a->name,a->port,registered,a);
  log_status("start",rc);if(rc)a->error=rc;
 }
 if(a->op && readable && !a->error){int rc=spple_discovery_process(a->op);log_status("start",rc);if(rc){log_status("process",rc);a->error=rc;}}
 if(a->error){
  if(a->published)spple_lan_retry_init(&a->retry,now,120000);
  if(a->op){spple_discovery_stop(a->op);a->op=NULL;}a->published=0;
  if(spple_lan_retry_failure(&a->retry,now)){a->failed=1;return -1;}return 0;
 }
 return a->published?1:0;
}
int spple_lan_advertiser_fd(const spple_lan_advertiser *a){return a && a->op?spple_discovery_fd(a->op):-1;}
void spple_lan_advertiser_free(spple_lan_advertiser *a){if(!a)return;if(a->op)spple_discovery_stop(a->op);free(a);}
