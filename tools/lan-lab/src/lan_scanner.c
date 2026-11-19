#include "lan_scanner.h"
#include "lan_discovery.h"
#include "lan_retry.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#define LIMIT 16
static void trace_code(const char *what,int code) {
 const char *enabled=getenv("DM_LDN_TRACE");if(enabled && !strcmp(enabled,"1"))fprintf(stderr,"[Spple LAN] scanner %s: %d\n",what,code);
}
typedef struct {char name[256],type[256],domain[256];uint32_t index;uint64_t generation,next_retry;unsigned failures;int used,pending;} service;
struct spple_lan_scanner {spple_discovery *browse,*resolve;spple_lan_retry retry;service items[LIMIT];uint64_t generation,resolve_deadline;int resolving,stage,resolve_done,resolve_error,error,failed;char host[256];uint16_t port;spple_scanner_found_fn found;spple_scanner_removed_fn removed;void *context;};
static int fits(const char *s){return s && strlen(s)<256;}
static void on_browse(void *ctx,int error,int added,uint32_t index,const char *name,const char *type,const char *domain) {
 spple_lan_scanner *s=ctx;if(error){trace_code("browse callback error",error);s->error=error;return;}if(!fits(name)||!fits(type)||!fits(domain))return;
 int pos=-1;for(int i=0;i<LIMIT;++i)if(s->items[i].used && s->items[i].index==index && !strcmp(s->items[i].name,name) && !strcmp(s->items[i].domain,domain)){pos=i;break;}
 if(!added){if(pos>=0){trace_code("Bonjour service removed",(int)index);s->items[pos].used=0;s->removed(s->context,name,index,s->items[pos].generation);}return;}
 if(pos>=0)return;for(int i=0;i<LIMIT;++i)if(!s->items[i].used && i!=s->resolving){pos=i;break;}
 if(pos<0 || s->generation==UINT64_MAX){trace_code("Bonjour service list full",LIMIT);return;}service *x=&s->items[pos];memset(x,0,sizeof *x);strcpy(x->name,name);strcpy(x->type,type);strcpy(x->domain,domain);x->index=index;x->generation=++s->generation;x->used=x->pending=1;
 trace_code("Bonjour service added on interface",(int)index);
}
static void on_resolve(void *ctx,int error,uint32_t index,const char *host,uint16_t port) {
 spple_lan_scanner *s=ctx;s->resolve_done=1;int i=s->resolving;
 if(error || !fits(host) || !*host || !port){trace_code("service resolve failed",error);s->resolve_error=1;return;}
 if(i<0 || i>=LIMIT || !s->items[i].used || s->items[i].index!=index){trace_code("service resolve interface mismatch",(int)index);s->resolve_error=1;return;}
 strcpy(s->host,host);s->port=port;
 trace_code("service resolved",(int)port);
}
static void on_address(void *ctx,int error,uint32_t index,const uint8_t ip[4]) {
 spple_lan_scanner *s=ctx;s->resolve_done=1;int i=s->resolving;
 if(error || !ip){trace_code("address resolution failed",error);s->resolve_error=1;return;}
 if(i<0 || i>=LIMIT || !s->items[i].used || s->items[i].index!=index)return;
 char numeric[16];snprintf(numeric,sizeof numeric,"%u.%u.%u.%u",ip[0],ip[1],ip[2],ip[3]);
 trace_code("IPv4 address resolved",(int)index);
 s->found(s->context,s->items[i].name,index,s->items[i].generation,numeric,s->port);
}
static void clear_items(spple_lan_scanner *s) {
 for(int i=0;i<LIMIT;++i)if(s->items[i].used){s->removed(s->context,s->items[i].name,s->items[i].index,s->items[i].generation);s->items[i].used=0;}
}
static void retry_resolve(spple_lan_scanner *s,uint64_t now) {
 int i=s->resolving;if(i<0 || i>=LIMIT || !s->items[i].used)return;service *x=&s->items[i];
 unsigned shift=x->failures<3?x->failures:3;if(x->failures<4)++x->failures;
 uint64_t delay=UINT64_C(1000)<<shift;x->next_retry=now>UINT64_MAX-delay?UINT64_MAX:now+delay;x->pending=1;
}
spple_lan_scanner *spple_lan_scanner_new(uint64_t now,spple_scanner_found_fn found,spple_scanner_removed_fn removed,void *context) {
 if(!found || !removed)return NULL;spple_lan_scanner *s=calloc(1,sizeof(*s));if(!s)return NULL;
 s->found=found;s->removed=removed;s->context=context;s->resolving=-1;spple_lan_retry_init(&s->retry,now,120000);return s;
}
int spple_lan_scanner_tick(spple_lan_scanner *s,uint64_t now,int browse_ready,int resolve_ready) {
 if(!s || s->failed)return -1;
 if(!s->browse){
  int ready=spple_lan_retry_ready(&s->retry,now);if(ready<0){s->failed=1;return -1;}if(!ready)return 0;
  s->error=0;int rc=spple_discovery_browse(&s->browse,on_browse,s);if(rc)s->error=rc;
 }
 if(s->browse && browse_ready && !s->error){int rc=spple_discovery_process(s->browse);if(rc)s->error=rc;else if(!s->error)spple_lan_retry_init(&s->retry,now,120000);}
 if(s->resolve && resolve_ready && !s->error){int rc=spple_discovery_process(s->resolve);if(rc){s->resolve_done=1;s->resolve_error=1;}}
 if(s->resolve && now>=s->resolve_deadline){s->resolve_done=1;s->resolve_error=1;}
 if(s->resolve && s->resolve_done){
  int i=s->resolving,proceed=!s->resolve_error && s->stage==1 && i>=0 && i<LIMIT && s->items[i].used;
  if(s->resolve_error)retry_resolve(s,now);
  spple_discovery_stop(s->resolve);s->resolve=NULL;s->resolve_done=s->resolve_error=0;
  if(proceed){
   s->stage=2;int rc=spple_discovery_address(&s->resolve,s->items[i].index,s->host,on_address,s);
   if(rc){retry_resolve(s,now);s->resolving=-1;}else s->resolve_deadline=now>UINT64_MAX-5000?UINT64_MAX:now+5000;
  } else s->resolving=-1;
 }
 if(s->error){
  if(s->resolve){spple_discovery_stop(s->resolve);s->resolve=NULL;}s->resolving=-1;
  if(s->browse){spple_discovery_stop(s->browse);s->browse=NULL;}clear_items(s);
  if(spple_lan_retry_failure(&s->retry,now)){s->failed=1;return -1;}return 0;
 }
 if(!s->resolve)for(int i=0;i<LIMIT;++i)if(s->items[i].used && s->items[i].pending && now>=s->items[i].next_retry){
  service *x=&s->items[i];x->pending=0;s->resolving=i;s->stage=1;
  int rc=spple_discovery_resolve(&s->resolve,x->index,x->name,x->type,x->domain,on_resolve,s);
  if(rc){retry_resolve(s,now);s->resolving=-1;}else s->resolve_deadline=now>UINT64_MAX-5000?UINT64_MAX:now+5000;break;
 }
 return 0;
}
void spple_lan_scanner_fds(const spple_lan_scanner *s,int *browse_fd,int *resolve_fd){
 if(browse_fd)*browse_fd=s && s->browse?spple_discovery_fd(s->browse):-1;
 if(resolve_fd)*resolve_fd=s && s->resolve?spple_discovery_fd(s->resolve):-1;
}
void spple_lan_scanner_free(spple_lan_scanner *s){if(!s)return;if(s->resolve)spple_discovery_stop(s->resolve);if(s->browse)spple_discovery_stop(s->browse);free(s);}
