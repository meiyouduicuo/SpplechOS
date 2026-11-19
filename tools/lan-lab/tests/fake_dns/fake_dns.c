#ifdef _WIN32
#include <winsock2.h>
typedef SOCKET fake_socket;
#define FAKE_BAD INVALID_SOCKET
#define FAKE_CLOSE closesocket
#else
#include <arpa/inet.h>
#include <unistd.h>
typedef int fake_socket;
#define FAKE_BAD (-1)
#define FAKE_CLOSE close
#endif
#include "dns_sd.h"
#include <pthread.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
struct fake_dns { int kind; DNSServiceBrowseReply browse; DNSServiceResolveReply resolve; DNSServiceRegisterReply registered; DNSServiceGetAddrInfoReply address; void *context;fake_socket recv_fd,send_fd;int pending,value; };
static DNSServiceRef current,last_browse,last_resolve,last_register,last_address;
static int active,async_mode;static uint16_t registered_port;static pthread_mutex_t mu=PTHREAD_MUTEX_INITIALIZER;
int fake_dns_set_async(int enabled){pthread_mutex_lock(&mu);if(active){pthread_mutex_unlock(&mu);return -1;}async_mode=!!enabled;pthread_mutex_unlock(&mu);return 0;}
static DNSServiceRef make_op(int kind,void *ctx){
 DNSServiceRef s=calloc(1,sizeof(*s));if(!s)return NULL;s->kind=kind;s->context=ctx;s->recv_fd=s->send_fd=FAKE_BAD;
 pthread_mutex_lock(&mu);int use_async=async_mode;pthread_mutex_unlock(&mu);
 if(use_async){
  s->recv_fd=socket(AF_INET,SOCK_DGRAM,0);s->send_fd=socket(AF_INET,SOCK_DGRAM,0);
  if(s->recv_fd==FAKE_BAD || s->send_fd==FAKE_BAD)goto fail;
  struct sockaddr_in a;memset(&a,0,sizeof a);a.sin_family=AF_INET;a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
#ifdef _WIN32
  int n=sizeof a;
#else
  socklen_t n=sizeof a;
#endif
  if(bind(s->recv_fd,(struct sockaddr *)&a,sizeof a) || getsockname(s->recv_fd,(struct sockaddr *)&a,&n) || connect(s->send_fd,(struct sockaddr *)&a,sizeof a))goto fail;
  if((uintptr_t)s->recv_fd>INT_MAX)goto fail;
 }
 pthread_mutex_lock(&mu);current=s;active++;
 if(kind==1)last_register=s;else if(kind==2)last_browse=s;else if(kind==3)last_resolve=s;else if(kind==4)last_address=s;
 pthread_mutex_unlock(&mu);return s;
fail:if(s->recv_fd!=FAKE_BAD)FAKE_CLOSE(s->recv_fd);if(s->send_fd!=FAKE_BAD)FAKE_CLOSE(s->send_fd);free(s);return NULL;
}
DNSServiceErrorType DNSServiceRegister(DNSServiceRef *out,DNSServiceFlags f,uint32_t i,const char *name,const char *type,const char *domain,const char *host,uint16_t port,uint16_t len,const void *txt,DNSServiceRegisterReply cb,void *ctx){
 (void)f;(void)i;(void)name;(void)domain;(void)host;(void)len;(void)txt;if(strcmp(type,"_spplechos-ldn._tcp"))return -99;
 DNSServiceRef s=make_op(1,ctx);if(!s)return -1;s->registered=cb;pthread_mutex_lock(&mu);registered_port=port;pthread_mutex_unlock(&mu);*out=s;return 0;
}
DNSServiceErrorType DNSServiceBrowse(DNSServiceRef *out,DNSServiceFlags f,uint32_t i,const char *type,const char *domain,DNSServiceBrowseReply cb,void *ctx){
 (void)f;(void)i;(void)domain;if(strcmp(type,"_spplechos-ldn._tcp"))return -99;
 DNSServiceRef s=make_op(2,ctx);if(!s)return -1;s->browse=cb;*out=s;return 0;
}
DNSServiceErrorType DNSServiceResolve(DNSServiceRef *out,DNSServiceFlags f,uint32_t i,const char *name,const char *type,const char *domain,DNSServiceResolveReply cb,void *ctx){
 (void)f;(void)i;(void)name;(void)type;(void)domain;DNSServiceRef s=make_op(3,ctx);if(!s)return -1;s->resolve=cb;*out=s;return 0;
}
DNSServiceErrorType DNSServiceGetAddrInfo(DNSServiceRef *out,DNSServiceFlags f,uint32_t i,DNSServiceProtocol p,const char *host,DNSServiceGetAddrInfoReply cb,void *ctx){
 (void)f;(void)i;(void)p;(void)host;DNSServiceRef s=make_op(4,ctx);if(!s)return -1;s->address=cb;*out=s;return 0;
}
int DNSServiceRefSockFD(DNSServiceRef s){return s?(s->recv_fd!=FAKE_BAD?(int)s->recv_fd:42):-1;}
static void dispatch(DNSServiceRef s,int value){
 if(s->kind==1 && s->registered)s->registered(s,0,value,"room","_spplechos-ldn._tcp.","local.",s->context);
 else if(s->kind==2 && s->browse)s->browse(s,value?kDNSServiceFlagsAdd:0,7,0,"room","_spplechos-ldn._tcp.","local.",s->context);
 else if(s->kind==3 && s->resolve)s->resolve(s,0,7,0,"room","host.local.",(uint16_t)value,0,NULL,s->context);
 else if(s->kind==4 && s->address){struct sockaddr_in a;memset(&a,0,sizeof a);a.sin_family=AF_INET;const unsigned char ip[4]={127,0,0,1};memcpy(&a.sin_addr,ip,4);s->address(s,kDNSServiceFlagsAdd,7,0,"host.local.",(const struct sockaddr *)&a,30,s->context);}
}
DNSServiceErrorType DNSServiceProcessResult(DNSServiceRef s){
 if(!s)return -1;if(s->recv_fd==FAKE_BAD)return 0;char byte;
 if(recv(s->recv_fd,&byte,1,0)!=1)return -1;pthread_mutex_lock(&mu);int value=s->value;s->pending=0;pthread_mutex_unlock(&mu);dispatch(s,value);return 0;
}
void DNSServiceRefDeallocate(DNSServiceRef s){
 if(!s)return;pthread_mutex_lock(&mu);if(current==s)current=NULL;if(last_browse==s)last_browse=NULL;if(last_resolve==s)last_resolve=NULL;if(last_register==s)last_register=NULL;if(last_address==s)last_address=NULL;active--;pthread_mutex_unlock(&mu);
 if(s->recv_fd!=FAKE_BAD)FAKE_CLOSE(s->recv_fd);if(s->send_fd!=FAKE_BAD)FAKE_CLOSE(s->send_fd);free(s);
}
static void emit(int kind,int value){
 pthread_mutex_lock(&mu);DNSServiceRef s=kind==1?last_register:kind==2?last_browse:kind==3?last_resolve:last_address;
 if(!s){pthread_mutex_unlock(&mu);return;}
 if(s->send_fd!=FAKE_BAD){if(!s->pending){s->pending=1;s->value=value;char byte=1;(void)send(s->send_fd,&byte,1,0);}pthread_mutex_unlock(&mu);return;}
 pthread_mutex_unlock(&mu);dispatch(s,value);
}
void fake_emit_browse(int added){emit(2,added);}
void fake_emit_register(int error){emit(1,error);}
void fake_emit_resolve(uint16_t port){emit(3,port);}
void fake_emit_address(void){emit(4,0);}
int fake_active(void){pthread_mutex_lock(&mu);int n=active;pthread_mutex_unlock(&mu);return n;}
unsigned fake_port(void){pthread_mutex_lock(&mu);unsigned p=registered_port;pthread_mutex_unlock(&mu);return p;}
int fake_has_operation(int kind){pthread_mutex_lock(&mu);int found=(kind==1?last_register:kind==2?last_browse:kind==3?last_resolve:last_address)!=NULL;pthread_mutex_unlock(&mu);return found;}
