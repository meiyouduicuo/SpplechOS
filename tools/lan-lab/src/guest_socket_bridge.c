#include "guest_socket_bridge.h"
#include "guest_socket_api.h"
#include "guest_sockaddr.h"
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
static _Atomic(spple_guest_udp *) active;
static _Atomic(void (*)(int)) wait_hook;
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed=PTHREAD_COND_INITIALIZER;
static uint64_t generations[SPPLE_GUEST_UDP_LIMIT];
static uint64_t session_generation;
static int nonblocking[SPPLE_GUEST_UDP_LIMIT], broadcast_enabled[SPPLE_GUEST_UDP_LIMIT], reuse_enabled[SPPLE_GUEST_UDP_LIMIT], stopped;
static int owns(int fd) { spple_guest_udp *g=atomic_load(&active); return g && spple_guest_udp_ready(g,fd)>=0; }
int spple_guest_socket_bridge_ready(int fd) { spple_guest_udp *g=atomic_load(&active); return g ? spple_guest_udp_ready(g,fd) : -1; }
int spple_guest_socket_bridge_ingest(const void *packet,size_t size) {
 pthread_mutex_lock(&lock); spple_guest_udp *g=atomic_load(&active);
 int r=g && !stopped ? spple_guest_udp_ingest(g,packet,size) : -1;
 if (!r) pthread_cond_broadcast(&changed);
 pthread_mutex_unlock(&lock); return r;
}
void spple_guest_socket_bridge_stop(void) {
 pthread_mutex_lock(&lock); stopped=1; ++session_generation; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&lock);
}
int spple_guest_socket_bridge_resume(const uint8_t local[4],const uint8_t peer[4]) {
 pthread_mutex_lock(&lock);spple_guest_udp *g=atomic_load(&active);
 int rc=!stopped || !g ? -1 : spple_guest_udp_reconfigure(g,local,peer);
 if(!rc){++session_generation;stopped=0;pthread_cond_broadcast(&changed);}
 pthread_mutex_unlock(&lock);return rc;
}
static int open_socket(int family,int type,int protocol,int *error) {
 pthread_mutex_lock(&lock);
 int r=stopped ? -1 : spple_guest_socket_open(atomic_load(&active),family,type,protocol,error);
 if (stopped && error) *error=100;
 if (r>=0 && r<SPPLE_GUEST_UDP_LIMIT) { ++generations[r]; nonblocking[r]=!!(type & 0x20000000); broadcast_enabled[r]=reuse_enabled[r]=0; }
 pthread_mutex_unlock(&lock); return r;
}
static int bind_socket(int fd,const void *address,unsigned size,int *error) {
 pthread_mutex_lock(&lock); int r=spple_guest_socket_bind(atomic_load(&active),fd,address,size,error); pthread_mutex_unlock(&lock); return r;
}
static long send_socket(int fd,const void *data,unsigned long size,int flags,const void *address,unsigned addrsize,int *error) {
 pthread_mutex_lock(&lock);
 uint8_t ip[4],local[4];uint16_t port,local_port;
 if(fd>=0 && fd<SPPLE_GUEST_UDP_LIMIT && !broadcast_enabled[fd] &&
    !spple_guest_sockaddr_decode(address,addrsize,ip,&port) &&
    !spple_guest_udp_local(atomic_load(&active),fd,local,&local_port)) {
  static const uint8_t all[4]={255,255,255,255};
  if(!memcmp(ip,all,4) || (!memcmp(ip,local,3) && ip[3]==255)) {
   if(error)*error=13;pthread_mutex_unlock(&lock);return -1;
  }
 }
 long r=stopped ? -1 : spple_guest_socket_sendto(atomic_load(&active),fd,data,size,flags,address,addrsize,error);
 if (stopped && error) *error=100;
 if (r>=0) pthread_cond_broadcast(&changed);
 pthread_mutex_unlock(&lock); return r;
}
static long recv_socket(int fd,void *data,unsigned long size,int flags,void *address,unsigned *addrsize,int *error) {
 if (fd<0 || fd>=SPPLE_GUEST_UDP_LIMIT) {if(error)*error=9;return -1;}
 if (flags!=0 && flags!=0x80) {if(error)*error=95;return -1;}
 pthread_mutex_lock(&lock); uint64_t gen=generations[fd],session=session_generation; long r;
 for (;;) {
  if (stopped) {if(error)*error=100;r=-1;break;}
  if (session!=session_generation) {if(error)*error=100;r=-1;break;}
  if (gen!=generations[fd]) {if(error)*error=9;r=-1;break;}
  int local_error=0;
  r=spple_guest_socket_recvfrom(atomic_load(&active),fd,data,size,0x80,address,addrsize,&local_error);
  if (r>=0) break;
  if (local_error!=11 || flags==0x80 || nonblocking[fd]) {if(error)*error=local_error;break;}
  void (*hook)(int)=atomic_load(&wait_hook);
  if (hook) hook(1);
  pthread_cond_wait(&changed,&lock);
  if (hook) hook(0);
 }
 pthread_mutex_unlock(&lock); return r;
}
static int close_socket(int fd,int *error) {
 pthread_mutex_lock(&lock); int r=spple_guest_socket_close(atomic_load(&active),fd,error);
 if (!r && fd>=0 && fd<SPPLE_GUEST_UDP_LIMIT) {++generations[fd];nonblocking[fd]=0;broadcast_enabled[fd]=reuse_enabled[fd]=0;pthread_cond_broadcast(&changed);}
 pthread_mutex_unlock(&lock); return r;
}
static int socket_name(int fd,void *address,unsigned *size,int *error) {
 if(!address || !size){if(error)*error=14;return -1;}
 pthread_mutex_lock(&lock);uint8_t ip[4];uint16_t port;
 int rc=spple_guest_udp_local(atomic_load(&active),fd,ip,&port);
 if(!rc){if(!port)memset(ip,0,sizeof ip);rc=spple_guest_sockaddr_encode(address,size,ip,port);}
 pthread_mutex_unlock(&lock);if(rc && error)*error=9;return rc;
}
static int set_option(int fd,int level,int option,const void *value,unsigned size,int *error) {
 if(!value || size<sizeof(int)){if(error)*error=22;return -1;}
 pthread_mutex_lock(&lock);
 if(!owns(fd)){pthread_mutex_unlock(&lock);if(error)*error=9;return -1;}
 if(level!=0xffff || (option!=0x20 && option!=0x4)){pthread_mutex_unlock(&lock);if(error)*error=92;return -1;}
 int v;memcpy(&v,value,sizeof v);
 if(option==0x20)broadcast_enabled[fd]=!!v;
 else {if(spple_guest_udp_reuseaddr(atomic_load(&active),fd,v)){pthread_mutex_unlock(&lock);if(error)*error=9;return -1;}reuse_enabled[fd]=!!v;}
 pthread_mutex_unlock(&lock);return 0;
}
static int get_option(int fd,int level,int option,void *value,unsigned *size,int *error) {
 if(!value || !size || *size<sizeof(int)){if(error)*error=22;return -1;}
 pthread_mutex_lock(&lock);
 if(!owns(fd)){pthread_mutex_unlock(&lock);if(error)*error=9;return -1;}
 if(level!=0xffff || (option!=0x20 && option!=0x4)){pthread_mutex_unlock(&lock);if(error)*error=92;return -1;}
 int v=option==0x20?broadcast_enabled[fd]:reuse_enabled[fd];memcpy(value,&v,sizeof v);*size=sizeof v;pthread_mutex_unlock(&lock);return 0;
}
static int socket_fcntl(int fd,int command,uint64_t value,int *error) {
 pthread_mutex_lock(&lock);
 if(!owns(fd)){pthread_mutex_unlock(&lock);if(error)*error=9;return -1;}
 int r;
 if(command==3)r=2|(nonblocking[fd]?4:0);
 else if(command==4 && !(value & ~(uint64_t)6)){nonblocking[fd]=!!(value&4);pthread_cond_broadcast(&changed);r=0;}
 else {if(error)*error=22;r=-1;}
 pthread_mutex_unlock(&lock);return r;
}
const dm_lan_socket_backend *spple_guest_socket_bridge_init(spple_guest_udp *g) {
 static const dm_lan_socket_backend backend={owns,open_socket,bind_socket,send_socket,recv_socket,close_socket,socket_name,set_option,get_option,socket_fcntl};
 spple_guest_udp *empty=NULL;
 if (!g || !atomic_compare_exchange_strong(&active,&empty,g)) return NULL;
 return &backend;
}
int spple_guest_socket_bridge_set_wait_hook(void (*hook)(int)) {
 if (!hook || atomic_load(&active)) return -1;
 void (*empty)(int)=NULL;
 return atomic_compare_exchange_strong(&wait_hook,&empty,hook) ? 0 : -1;
}
