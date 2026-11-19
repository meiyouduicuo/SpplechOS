#include "ldn_service.h"
#include "ldn_rooms.h"
#include "ldn_room_builder.h"
#include <pthread.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <time.h>
#ifdef _WIN32
#include <pthread_time.h>
#endif
#define OK 0u
#define FAIL 0x2a2u
static pthread_mutex_t mu=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t scan_changed=PTHREAD_COND_INITIALIZER;
static uint64_t scan_station_epoch;
static int scan_state;
static spple_ldn_service_ops ops;
static spple_ldn_rooms *rooms;
static int64_t default_id;
static int configured;
static spple_ldn_network_config pending_config,active_config;
static int has_pending_config,has_active_config;
static uint8_t advertise_data[0x180];
static uint16_t advertise_size;
static int accept_policy;
static int disconnect_reason;
static void trace(const char *format,...) {
 const char *enabled=getenv("DM_LDN_TRACE");if(!enabled || strcmp(enabled,"1"))return;
 va_list args;va_start(args,format);fputs("[Spple LAN] ",stderr);vfprintf(stderr,format,args);fputc('\n',stderr);va_end(args);
}
static void signal_change(void *context,uint64_t revision) {
 (void)context;
 (void)revision;
 int current=spple_ldn_rooms_state(rooms);
 if(current!=scan_state){
  scan_state=current;
  ++scan_station_epoch;
 }
 pthread_cond_broadcast(&scan_changed);
 ops.signal();
}
static uint32_t init(void) {
 pthread_mutex_lock(&mu);int rc=rooms?spple_ldn_rooms_init(rooms):-1;if(!rc){advertise_size=0;accept_policy=disconnect_reason=0;memset(advertise_data,0,sizeof advertise_data);}pthread_mutex_unlock(&mu);return rc?FAIL:OK;
}
static void fini(void) {
 pthread_mutex_lock(&mu);if(rooms)(void)spple_ldn_rooms_fini(rooms);has_pending_config=has_active_config=0;pthread_mutex_unlock(&mu);ops.stop_transport();
}
static int state(void) {pthread_mutex_lock(&mu);int s=rooms?spple_ldn_rooms_state(rooms):0;pthread_mutex_unlock(&mu);return s;}
static void attach(void *ev) {ops.attach(ev);}
static uint32_t transition(int operation) {
 pthread_mutex_lock(&mu);uint64_t token;int rc=rooms?spple_ldn_rooms_begin(rooms,operation,&token):-1;
 if(!rc)rc=spple_ldn_rooms_complete(rooms,token,1,NULL);
 if(!rc && operation==SPPLE_LDN_DISCONNECT)disconnect_reason=1;
 if(!rc && operation==SPPLE_LDN_DESTROY)disconnect_reason=3;
 pthread_mutex_unlock(&mu);return rc?FAIL:OK;
}
static uint32_t open_sta(void){
 uint32_t r=transition(SPPLE_LDN_OPEN_STATION);
 if(!r && ops.start_scan && ops.start_scan()){(void)transition(SPPLE_LDN_CLOSE_STATION);return FAIL;}
 return r;
}
static uint32_t open_ap(void){return transition(SPPLE_LDN_OPEN_AP);}
static uint32_t close_sta(void){uint32_t r=transition(SPPLE_LDN_CLOSE_STATION);if(!r)ops.stop_transport();return r;}
static uint32_t close_ap(void){uint32_t r=transition(SPPLE_LDN_CLOSE_AP);if(!r)ops.stop_transport();return r;}
static uint32_t disconnect(void){uint32_t r=transition(SPPLE_LDN_DISCONNECT);if(!r){if(ops.disconnect)ops.disconnect();else ops.stop_transport();}return r;}
static uint32_t destroy(void){uint32_t r=transition(SPPLE_LDN_DESTROY);if(!r)ops.stop_transport();return r;}
static int scan_clock(struct timespec *now) {
#ifdef _WIN32
 return clock_gettime(CLOCK_REALTIME,now)==0;
#else
 return timespec_get(now,TIME_UTC)==TIME_UTC;
#endif
}
static uint32_t scan(void *out,int *n,int max,const void *filter,int channel,int private_scan) {
 (void)channel;
 if(!out || !n || !filter || max<1)return FAIL;
 *n=0;
 spple_ldn_scan_filter resolved_filter=*(const spple_ldn_scan_filter *)filter;
 if((resolved_filter.flags & SPPLE_LDN_SCAN_LOCAL_COMMUNICATION_ID) &&
    resolved_filter.network_id.intent.local_communication_id==-1){
  resolved_filter.network_id.intent.local_communication_id=default_id;
 }
 size_t count=0;
 size_t cap=(size_t)(max>24?24:max);
 int waited=0;
 pthread_mutex_lock(&mu);
 int rc=rooms?spple_ldn_rooms_scan(rooms,&resolved_filter,out,cap,&count):-1;
 struct timespec deadline;
 if(!rc && !count && ops.start_scan && scan_state==SPPLE_LDN_STATION &&
    scan_clock(&deadline)){
  /* The game can call Scan once, immediately after opening the station.
   * Let Bonjour resolve the service and the browser finish its room probe. */
  deadline.tv_sec+=2;
  deadline.tv_nsec+=500000000L;
  if(deadline.tv_nsec>=1000000000L){
   ++deadline.tv_sec;
   deadline.tv_nsec-=1000000000L;
  }
  uint64_t epoch=scan_station_epoch;
  waited=1;
  while(!rc && !count){
   int wait_result=pthread_cond_timedwait(&scan_changed,&mu,&deadline);
   if(scan_station_epoch!=epoch){
    rc=-1;
    break;
   }
   rc=spple_ldn_rooms_scan(rooms,&resolved_filter,out,cap,&count);
   if(wait_result)break;
  }
 }
 pthread_mutex_unlock(&mu);
 trace("Scan%s: result=%d, matched=%u, waited=%d, filter=0x%x",
       private_scan?"Private":"",rc,(unsigned)count,waited,
       (unsigned)resolved_filter.flags);
 if(rc)return FAIL;
 *n=(int)count;
 return OK;
}
static uint32_t create_impl(const void *config,const void *security,const void *user,const spple_ldn_security_parameter *param) {
 if(!config || !security || !user)return FAIL;
 uint8_t entropy[32];
 if(param){memcpy(entropy,param->session_id,16);memcpy(entropy+16,param->server_random,16);}
 else if(ops.random(entropy,sizeof entropy))return FAIL;
 static const uint8_t ip[4]={10,77,0,1};spple_ldn_network_info info;
 if(spple_ldn_build_room(config,user,default_id,entropy,ip,&info))return FAIL;
 pthread_mutex_lock(&mu);uint64_t token;int rc=rooms?spple_ldn_rooms_begin(rooms,SPPLE_LDN_CREATE,&token):-1;
 if(!rc){pending_config=*(const spple_ldn_network_config *)config;pending_config.intent=info.network_id.intent;has_pending_config=1;info.advertise_size=advertise_size;memcpy(info.advertise_data,advertise_data,advertise_size);info.accept_policy=(uint8_t)accept_policy;}
 pthread_mutex_unlock(&mu);
 if(rc)return FAIL;
 if(ops.start_create(token,&info,security)) {pthread_mutex_lock(&mu);if(!spple_ldn_rooms_complete(rooms,token,0,NULL))has_pending_config=0;pthread_mutex_unlock(&mu);return FAIL;}
 return OK;
}
static uint32_t create(const void *config,const void *security,const void *user) {return create_impl(config,security,user,NULL);}
static uint32_t create_private(const void *config,const void *security,const void *param,const void *user,int count,const void *addresses) {
 (void)addresses;if(!param || count!=0)return FAIL;return create_impl(config,security,user,param);
}
static uint32_t connect_room(const void *network,const void *security,const void *user,int version,int option) {
 if(!network || !security || !user || version<0 || version>0x7fff || (option & ~1))return FAIL;
 const spple_ldn_network_info *info=network;if(spple_ldn_validate_network(info))return FAIL;
 pthread_mutex_lock(&mu);uint64_t token;int rc=rooms?spple_ldn_rooms_select(rooms,info->network_id.session_id):-1;
 if(!rc)rc=spple_ldn_rooms_begin(rooms,SPPLE_LDN_JOIN,&token);
 if(!rc){memset(&pending_config,0,sizeof pending_config);pending_config.intent=info->network_id.intent;pending_config.channel=info->common.channel;pending_config.node_count_max=info->node_count_max;pending_config.local_version=(int16_t)version;has_pending_config=1;}
 pthread_mutex_unlock(&mu);if(rc)return FAIL;
 if(ops.start_join(token,info,security,user,version,option)) {pthread_mutex_lock(&mu);if(!spple_ldn_rooms_complete(rooms,token,0,NULL))has_pending_config=0;pthread_mutex_unlock(&mu);return FAIL;}
 return OK;
}
static uint32_t connect_private(const void *cfg,const void *security,const void *param,const void *user,int version,int option) {
 if(!cfg || !security || !param || !user)return FAIL;
 const spple_ldn_network_config *config=cfg;const spple_ldn_security_parameter *parameter=param;
 spple_ldn_scan_filter filter;memset(&filter,0,sizeof filter);filter.flags=1|2|32;
 filter.network_id.intent=config->intent;if(filter.network_id.intent.local_communication_id==-1)filter.network_id.intent.local_communication_id=default_id;
 memcpy(filter.network_id.session_id,parameter->session_id,16);
 spple_ldn_network_info info;size_t count=0;
 pthread_mutex_lock(&mu);int rc=rooms?spple_ldn_rooms_scan(rooms,&filter,&info,1,&count):-1;pthread_mutex_unlock(&mu);
 if(rc || count!=1 || memcmp(info.server_random,parameter->server_random,16))return FAIL;
 return connect_room(&info,security,user,version,option);
}
static uint32_t network_info(void *out) {pthread_mutex_lock(&mu);int r=rooms?spple_ldn_rooms_info(rooms,out):-1;pthread_mutex_unlock(&mu);return r?FAIL:OK;}
static uint32_t ipv4(uint32_t *address,uint32_t *mask) {
 if(!address || !mask)return FAIL;pthread_mutex_lock(&mu);int s=rooms?spple_ldn_rooms_state(rooms):0;
 if(s!=SPPLE_LDN_AP_CREATED && s!=SPPLE_LDN_STATION_CONNECTED){pthread_mutex_unlock(&mu);return FAIL;}
 const uint8_t ip[4]={10,77,0,(uint8_t)(s==SPPLE_LDN_AP_CREATED?1:2)}, netmask[4]={255,255,255,0};
 *address=((uint32_t)ip[0]<<24)|((uint32_t)ip[1]<<16)|((uint32_t)ip[2]<<8)|ip[3];
 *mask=((uint32_t)netmask[0]<<24)|((uint32_t)netmask[1]<<16)|((uint32_t)netmask[2]<<8)|netmask[3];pthread_mutex_unlock(&mu);return OK;
}
static uint32_t advertise(const void *data,uint64_t size) {
 if(size>sizeof advertise_data || (size && !data))return FAIL;
 pthread_mutex_lock(&mu);int s=rooms?spple_ldn_rooms_state(rooms):0;
 if((s!=SPPLE_LDN_AP && s!=SPPLE_LDN_AP_CREATED) || has_pending_config){pthread_mutex_unlock(&mu);return FAIL;}
 if(s==SPPLE_LDN_AP_CREATED){
  spple_ldn_network_info info;
  if(!ops.update_room || spple_ldn_rooms_info(rooms,&info)){pthread_mutex_unlock(&mu);return FAIL;}
  memset(info.advertise_data,0,sizeof info.advertise_data);if(size)memcpy(info.advertise_data,data,(size_t)size);info.advertise_size=(uint16_t)size;
  if(ops.update_room(&info) || spple_ldn_rooms_update_active(rooms,&info)){pthread_mutex_unlock(&mu);return FAIL;}
 }
 memset(advertise_data,0,sizeof advertise_data);if(size)memcpy(advertise_data,data,(size_t)size);advertise_size=(uint16_t)size;
 pthread_mutex_unlock(&mu);return OK;
}
static uint32_t network_config(void *out) {
 if(!out)return FAIL;pthread_mutex_lock(&mu);
 int s=rooms?spple_ldn_rooms_state(rooms):0;
 if(!has_active_config || (s!=SPPLE_LDN_AP_CREATED && s!=SPPLE_LDN_STATION_CONNECTED)){pthread_mutex_unlock(&mu);return FAIL;}
 memcpy(out,&active_config,sizeof active_config);pthread_mutex_unlock(&mu);return OK;
}
static uint32_t security_parameter(void *out) {
 if(!out)return FAIL;spple_ldn_network_info info;pthread_mutex_lock(&mu);
 int r=rooms?spple_ldn_rooms_info(rooms,&info):-1;pthread_mutex_unlock(&mu);if(r)return FAIL;
 spple_ldn_security_parameter p;memcpy(p.server_random,info.server_random,16);memcpy(p.session_id,info.network_id.session_id,16);memcpy(out,&p,sizeof p);return OK;
}
static uint32_t reject_station(uint32_t address) {
 pthread_mutex_lock(&mu);int active=rooms && spple_ldn_rooms_state(rooms)==SPPLE_LDN_AP_CREATED && !has_pending_config;
 int (*reject)(uint32_t)=ops.reject;pthread_mutex_unlock(&mu);
 return active && reject && !reject(address) ? OK : FAIL;
}
const dm_lan_backend *spple_ldn_service_setup(const spple_ldn_service_ops *in,int64_t id) {
 static const dm_lan_backend table={init,fini,state,attach,open_sta,close_sta,open_ap,close_ap,disconnect,destroy,scan,create,connect_room,network_info,ipv4,advertise,create_private,connect_private,network_config,security_parameter,spple_ldn_service_policy,spple_ldn_service_disconnect_reason,reject_station};
 if(!in || !in->random || !in->start_create || !in->start_join || !in->stop_transport || !in->attach || !in->signal || id<=0)return NULL;
 pthread_mutex_lock(&mu);if(configured){pthread_mutex_unlock(&mu);return NULL;}
 rooms=spple_ldn_rooms_new();if(!rooms){pthread_mutex_unlock(&mu);return NULL;}
 ops=*in;default_id=id;configured=1;(void)spple_ldn_rooms_set_listener(rooms,signal_change,NULL);pthread_mutex_unlock(&mu);return &table;
}
int spple_ldn_service_complete(uint64_t token,int success,const spple_ldn_network_info *info) {
 pthread_mutex_lock(&mu);int r=rooms?spple_ldn_rooms_complete(rooms,token,success,info):-1;
 if(!r && has_pending_config){if(success){active_config=pending_config;has_active_config=1;disconnect_reason=0;}has_pending_config=0;}
 pthread_mutex_unlock(&mu);return r;
}
int spple_ldn_service_discover(const spple_ldn_network_info *info) {
 pthread_mutex_lock(&mu);int r=rooms?spple_ldn_rooms_put(rooms,info):-1;pthread_mutex_unlock(&mu);
 trace("room discovery catalog update: %s",r?"rejected":"accepted");return r;
}
int spple_ldn_service_forget(const uint8_t id[16]) {
 pthread_mutex_lock(&mu);int r=rooms?spple_ldn_rooms_remove(rooms,id):-1;pthread_mutex_unlock(&mu);
 trace("room removed from catalog: %s",r?"not present":"removed");return r;
}
int spple_ldn_service_lost(void) {
 pthread_mutex_lock(&mu);int r=rooms?spple_ldn_rooms_transport_lost(rooms):-1;if(!r)disconnect_reason=6;pthread_mutex_unlock(&mu);return r;
}
int spple_ldn_service_disconnect_reason(void){pthread_mutex_lock(&mu);int r=disconnect_reason;pthread_mutex_unlock(&mu);return r;}
int spple_ldn_service_update(const spple_ldn_network_info *info) {
 pthread_mutex_lock(&mu);int r=rooms?spple_ldn_rooms_update_active(rooms,info):-1;pthread_mutex_unlock(&mu);return r;
}
uint32_t spple_ldn_service_policy(int policy) {
 /* Address-based allow/deny lists need their own implementation. */
 if(policy<0 || policy>1)return FAIL;
 pthread_mutex_lock(&mu);int s=rooms?spple_ldn_rooms_state(rooms):0;
 if((s!=SPPLE_LDN_AP && s!=SPPLE_LDN_AP_CREATED) || has_pending_config){pthread_mutex_unlock(&mu);return FAIL;}
 if(s==SPPLE_LDN_AP_CREATED){
  spple_ldn_network_info info;if(!ops.update_room || spple_ldn_rooms_info(rooms,&info)){pthread_mutex_unlock(&mu);return FAIL;}
  info.accept_policy=(uint8_t)policy;
  if(ops.update_room(&info) || spple_ldn_rooms_update_active(rooms,&info)){pthread_mutex_unlock(&mu);return FAIL;}
 }
 accept_policy=policy;pthread_mutex_unlock(&mu);return OK;
}
