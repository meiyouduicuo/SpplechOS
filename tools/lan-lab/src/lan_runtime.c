#include "lan_runtime.h"
#include "ldn_service.h"
#include "lan_runtime_host.h"
#include "lan_browser.h"
#include "lan_station_join.h"
#include "lan_connection.h"
#include "guest_socket_bridge.h"
#include "virtual_udp.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
typedef struct {uint64_t epoch,token;int role;int announced,failed,join_ready;spple_ldn_network_info room;} session;
static struct {
 pthread_mutex_t mu,operations;pthread_cond_t started;uint64_t title,epoch;int initialized,stopping,final,role;
 spple_runtime_platform platform;spple_vudp *udp;spple_guest_udp *guest;
 spple_runtime_host *host;spple_lan_browser *browser;spple_station_join *join;
 session *host_session,*join_session;
 _Atomic(spple_lan_connection *) connection;
} g={.mu=PTHREAD_MUTEX_INITIALIZER,.operations=PTHREAD_MUTEX_INITIALIZER,.started=PTHREAD_COND_INITIALIZER};
static void trace(const char *message){const char *enabled=getenv("DM_LDN_TRACE");if(enabled && !strcmp(enabled,"1"))fprintf(stderr,"[Spple LAN] %s\n",message);}
static int active(session *s) {return s && !g.stopping && !g.final && s->epoch==g.epoch;}
static int reserve_fd(void *ctx){(void)ctx;return g.platform.reserve(g.platform.context);}
static int release_fd(void *ctx,int fd){(void)ctx;return g.platform.release(g.platform.context,fd);}
static void notify_fd(void *ctx){(void)ctx;g.platform.notify(g.platform.context);}
static int random_bytes(void *out,size_t n){return g.platform.random(g.platform.context,out,n);}
static int random_ctx(void *ctx,void *out,size_t n){(void)ctx;return random_bytes(out,n);}
static void attach_event(void *event){g.platform.attach_event(event);}
static void signal_event(void){g.platform.signal_event();}
static int send_packet(void *ctx,const void *data,size_t size){
 (void)ctx;spple_lan_connection *c=atomic_load(&g.connection);
 /* UDP sends may succeed before a station is present; there is no recipient. */
 if(!c){pthread_mutex_lock(&g.mu);int hosting=!g.stopping && !g.final && g.role==1 && g.host;pthread_mutex_unlock(&g.mu);return hosting?0:-1;}
 return spple_lan_connection_send(c,data,size);
}
static int read_key(const void *security,uint8_t key[64],size_t *size) {
 if(!security || !key || !size)return -1;const uint8_t *p=security;unsigned n=(unsigned)p[2]|((unsigned)p[3]<<8);
 if(n<16 || n>64){char msg[96];snprintf(msg,sizeof msg,"invalid LDN passphrase length: %u",n);trace(msg);return -1;}memcpy(key,p+4,n);*size=n;return 0;
}
static void erase(void *p,size_t n){volatile uint8_t *v=p;while(n--)*v++=0;}
static void connection_failed(void *ctx){
 trace("connection lost");
 session *s=ctx;pthread_mutex_lock(&g.mu);int ok=active(s);int role=s?s->role:0;spple_runtime_host *host=g.host;pthread_mutex_unlock(&g.mu);
 if(!ok)return;
 if(role==1 && host)(void)spple_runtime_host_station_lost(host);else if(role==2)(void)spple_ldn_service_lost();
}
static int connection_room(void *ctx,const spple_ldn_network_info *room){
 session *s=ctx;pthread_mutex_lock(&g.mu);int ok=active(s) && s->role==2;pthread_mutex_unlock(&g.mu);
 return ok?spple_ldn_service_update(room):-1;
}
/* bridge_stop serializes against every in-flight socket send before the
 * pointer is removed, so no sender can use a destroyed connection. */
static void drop_connection(void){
 spple_guest_socket_bridge_stop();spple_lan_connection *old=atomic_exchange(&g.connection,NULL);
 if(old)spple_lan_connection_destroy(old);
}
static int open_connection(session *s,intptr_t fd,const spple_ldn_network_info *room){
 pthread_mutex_lock(&g.mu);int ok=active(s);pthread_mutex_unlock(&g.mu);if(!ok)return -1;
 drop_connection();const uint8_t host[4]={10,77,0,1},station[4]={10,77,0,2};
 spple_lan_connection *c=spple_lan_connection_start_ex(fd,g.title,room->network_id.session_id,s->role==1?host:station,s->role==1?station:host,connection_room,connection_failed,s);
 if(!c)return -1;
 pthread_mutex_lock(&g.mu);ok=active(s);if(ok)atomic_store(&g.connection,c);pthread_mutex_unlock(&g.mu);
 if(!ok){spple_lan_connection_destroy(c);return 0;} /* descriptor consumed */
 return 0;
}
static void host_status(void *ctx,int published){
 trace(published?"room advertised":"room advertisement failed");
 session *s=ctx;pthread_mutex_lock(&g.mu);
 while(active(s) && g.host_session==s && !g.host)pthread_cond_wait(&g.started,&g.mu);
 int ok=active(s) && g.host_session==s && g.host,announced=s->announced;
 if(ok && published && !announced)s->announced=1;
 if(ok && !published)s->failed=1;
 pthread_mutex_unlock(&g.mu);if(!ok)return;
 if(published && !announced)(void)spple_ldn_service_complete(s->token,1,&s->room);
 else if(!published && !announced)(void)spple_ldn_service_complete(s->token,0,NULL);
 else if(!published)(void)spple_ldn_service_lost();
}
static int host_opened(void *ctx,intptr_t fd){trace("station authenticated by host");session *s=ctx;return open_connection(s,fd,&s->room);}
static void host_changed(void *ctx,const spple_ldn_network_info *room){
 session *s=ctx;pthread_mutex_lock(&g.mu);int ok=active(s);pthread_mutex_unlock(&g.mu);if(!ok)return;
 if(!spple_ldn_service_update(room)){spple_lan_connection *c=atomic_load(&g.connection);if(c)spple_lan_connection_ready(c);}
}
static void browser_found(void *ctx,const spple_ldn_network_info *room){trace("compatible room discovered");(void)ctx;(void)spple_ldn_service_discover(room);}
static void browser_removed(void *ctx,const uint8_t session_id[16]){(void)ctx;(void)spple_ldn_service_forget(session_id);}
static int start_scan(void){
 trace("starting room discovery");
 pthread_mutex_lock(&g.operations);pthread_mutex_lock(&g.mu);int ok=!g.stopping && !g.final && !g.browser;
 if(ok){g.role=2;++g.epoch;}pthread_mutex_unlock(&g.mu);
 spple_lan_browser *b=ok?spple_lan_browser_start(g.title,browser_found,browser_removed,NULL):NULL;
 pthread_mutex_lock(&g.mu);if(b)g.browser=b;pthread_mutex_unlock(&g.mu);trace(b?"room discovery started":"room discovery could not start");pthread_mutex_unlock(&g.operations);return b?0:-1;
}
static int start_create(uint64_t token,const spple_ldn_network_info *room,const void *security){
 trace("starting room host");
 uint8_t key[64]={0};size_t key_size=0;if(read_key(security,key,&key_size))return -1;
 pthread_mutex_lock(&g.operations);pthread_mutex_lock(&g.mu);
 spple_runtime_host *old_host=NULL;session *old_session=NULL;
 if(g.host && g.host_session && g.host_session->failed){old_host=g.host;old_session=g.host_session;g.host=NULL;g.host_session=NULL;++g.epoch;}
 pthread_mutex_unlock(&g.mu);
 if(old_host){spple_runtime_host_stop(old_host);drop_connection();spple_runtime_host_destroy(old_host);free(old_session);}
 pthread_mutex_lock(&g.mu);int ok=!g.stopping && !g.final && !g.host;
 session *s=ok?calloc(1,sizeof(*s)):NULL;
 if(s){g.role=1;s->role=1;s->epoch=++g.epoch;s->token=token;s->room=*room;g.host_session=s;}
 pthread_mutex_unlock(&g.mu);char name[48];spple_runtime_host *host=NULL;
 if(s){snprintf(name,sizeof name,"Spple-%02x%02x%02x%02x%02x%02x",room->network_id.session_id[0],room->network_id.session_id[1],room->network_id.session_id[2],room->network_id.session_id[3],room->network_id.session_id[4],room->network_id.session_id[5]);
  host=spple_runtime_host_start(g.title,name,key,key_size,room,random_ctx,host_status,host_opened,host_changed,s);}
 erase(key,sizeof key);pthread_mutex_lock(&g.mu);if(host){g.host=host;s->announced=1;}else {g.host_session=NULL;free(s);}pthread_cond_broadcast(&g.started);pthread_mutex_unlock(&g.mu);
 /* CreateNetwork returns a created room while Bonjour publication continues. */
 if(host){const uint8_t local[4]={10,77,0,1},peer[4]={10,77,0,2};
  if(spple_guest_socket_bridge_resume(local,peer))trace("host socket bridge could not resume");
  (void)spple_ldn_service_complete(token,1,room);
 }
 trace(host?"room host started, waiting for advertisement":"room host could not start");pthread_mutex_unlock(&g.operations);return host?0:-1;
}
static int station_opened(void *ctx,intptr_t fd,const spple_ldn_network_info *room){
 trace("station authenticated");
 session *s=ctx;if(open_connection(s,fd,room))return -1;
 pthread_mutex_lock(&g.mu);int ok=active(s);pthread_mutex_unlock(&g.mu);
 if(ok && !spple_ldn_service_complete(s->token,1,room)){
  spple_lan_connection *c=atomic_load(&g.connection);
  if(c){spple_lan_connection_ready(c);s->join_ready=1;}
 }
 else drop_connection();
 return 0; /* connection took ownership even if the game cancelled */
}
static void station_failed(void *ctx){trace("station connection or authentication failed");session *s=ctx;pthread_mutex_lock(&g.mu);int ok=active(s);pthread_mutex_unlock(&g.mu);if(ok)(void)spple_ldn_service_complete(s->token,0,NULL);}
static int start_join(uint64_t token,const spple_ldn_network_info *room,const void *security,const void *user,int version,int option){
 trace("joining room");
 uint8_t key[64]={0};size_t key_size=0;if(read_key(security,key,&key_size))return -1;
 pthread_mutex_lock(&g.operations);pthread_mutex_lock(&g.mu);
 spple_station_join *old_join=g.join;session *old_session=g.join_session;g.join=NULL;g.join_session=NULL;
 pthread_mutex_unlock(&g.mu);
 if(old_join)spple_station_join_destroy(old_join);drop_connection();free(old_session);
 pthread_mutex_lock(&g.mu);
 spple_lan_browser *browser=!g.stopping && !g.final?g.browser:NULL;
 pthread_mutex_unlock(&g.mu);
 spple_lan_endpoint endpoint;
 int ok=browser && !spple_lan_browser_wait(browser,room->network_id.session_id,&endpoint);
 trace(ok?"join endpoint resolved":"join endpoint unavailable");
 pthread_mutex_lock(&g.mu);
 ok=ok && !g.final && !g.stopping;
 session *s=ok?calloc(1,sizeof(*s)):NULL;if(s){s->role=2;s->epoch=g.epoch;s->token=token;s->room=*room;g.join_session=s;}
 pthread_mutex_unlock(&g.mu);spple_station_join *join=s?spple_station_join_start(g.title,&endpoint,room,key,key_size,user,version,option,random_ctx,station_opened,station_failed,s):NULL;
 erase(key,sizeof key);
 if(join){
  /* Connect callers may read the active network configuration immediately. */
  g.platform.guest_wait(1);
  spple_station_join_wait(join);
  g.platform.guest_wait(0);
 }
 pthread_mutex_lock(&g.mu);
 ok=join && s->join_ready && active(s);
 if(ok)g.join=join;
 else g.join_session=NULL;
 pthread_mutex_unlock(&g.mu);
 if(!ok){
  spple_station_join_destroy(join);
  drop_connection();
  free(s);
 }
 trace(ok?"join ready before returning":"join did not complete");
 pthread_mutex_unlock(&g.operations);return ok?0:-1;
}
static void disconnect_transport(void){
 pthread_mutex_lock(&g.operations);pthread_mutex_lock(&g.mu);++g.epoch;
 spple_station_join *join=g.join;session *s=g.join_session;g.join=NULL;g.join_session=NULL;
 pthread_mutex_unlock(&g.mu);spple_guest_socket_bridge_stop();if(join)spple_station_join_destroy(join);drop_connection();free(s);
 pthread_mutex_unlock(&g.operations);
}
static int reject_station(uint32_t address){
 if(address!=UINT32_C(0x0a4d0002))return -1;
 pthread_mutex_lock(&g.operations);pthread_mutex_lock(&g.mu);
 spple_runtime_host *host=g.host;int ok=!g.stopping && !g.final && g.role==1 && host && atomic_load(&g.connection);
 pthread_mutex_unlock(&g.mu);
 int rc=-1;if(ok){drop_connection();rc=spple_runtime_host_station_lost(host);}
 pthread_mutex_unlock(&g.operations);return rc;
}
static int update_room(const spple_ldn_network_info *room){
 pthread_mutex_lock(&g.mu);spple_runtime_host *h=g.host;int ok=!g.stopping && !g.final && h;spple_ldn_network_info previous;
 int rc=ok?spple_runtime_host_snapshot(h,&previous):-1;
 if(!rc)rc=spple_runtime_host_update(h,room);
 spple_lan_connection *c=atomic_load(&g.connection);
 if(!rc && c && spple_lan_connection_send_room(c,room)){(void)spple_runtime_host_update(h,&previous);rc=-1;}
 pthread_mutex_unlock(&g.mu);return rc;
}
static void stop_transport(void){
 pthread_mutex_lock(&g.operations);pthread_mutex_lock(&g.mu);g.stopping=1;++g.epoch;
 spple_station_join *join=g.join;spple_runtime_host *host=g.host;spple_lan_browser *browser=g.browser;
 pthread_mutex_unlock(&g.mu);spple_guest_socket_bridge_stop();
 if(join)spple_station_join_stop(join);if(host)spple_runtime_host_stop(host);if(browser)spple_lan_browser_stop(browser);
 drop_connection();
 if(join)spple_station_join_destroy(join);if(host)spple_runtime_host_destroy(host);if(browser)spple_lan_browser_destroy(browser);
 pthread_mutex_lock(&g.mu);g.join=NULL;g.host=NULL;g.browser=NULL;free(g.join_session);free(g.host_session);g.join_session=g.host_session=NULL;g.role=0;g.stopping=0;pthread_mutex_unlock(&g.mu);
 pthread_mutex_unlock(&g.operations);
}
int spple_lan_runtime_init(uint64_t title,int64_t default_id,const spple_runtime_platform *platform,spple_runtime_backends *out){
 if(!title || default_id<=0 || !platform || !out || !platform->reserve || !platform->release || !platform->notify || !platform->guest_wait || !platform->attach_event || !platform->signal_event || !platform->random)return -1;
 pthread_mutex_lock(&g.operations);if(g.initialized){pthread_mutex_unlock(&g.operations);return -1;}g.initialized=1;g.title=title;g.platform=*platform;
 const uint8_t local[4]={10,77,0,1},peer[4]={10,77,0,2};g.udp=spple_vudp_create(local,peer,send_packet,NULL);
 if(g.udp)g.guest=spple_guest_udp_new(g.udp,reserve_fd,release_fd,notify_fd,NULL);
 const dm_lan_socket_backend *sock=NULL;const dm_lan_backend *ldn=NULL;
 if(g.guest && !spple_guest_socket_bridge_set_wait_hook(platform->guest_wait))sock=spple_guest_socket_bridge_init(g.guest);
 spple_ldn_service_ops ops={random_bytes,start_create,start_join,stop_transport,attach_event,signal_event,update_room,start_scan,disconnect_transport,reject_station};
 if(sock)ldn=spple_ldn_service_setup(&ops,default_id);
 if(!sock || !ldn){pthread_mutex_unlock(&g.operations);return -1;} /* singleton is intentionally not reused on failure */
 spple_guest_socket_bridge_stop();out->ldn=ldn;out->sockets=sock;out->ready=spple_guest_socket_bridge_ready;
 pthread_mutex_unlock(&g.operations);return 0;
}
void spple_lan_runtime_stop(void){
 pthread_mutex_lock(&g.mu);int initialized=g.initialized;g.final=1;pthread_cond_broadcast(&g.started);pthread_mutex_unlock(&g.mu);
 if(initialized)stop_transport();
}
