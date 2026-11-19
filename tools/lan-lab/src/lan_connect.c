#include "lan_connect.h"
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET sock_t;
#define BADSOCK INVALID_SOCKET
#define CLOSE(s) closesocket(s)
#else
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <netdb.h>
typedef int sock_t;
#define BADSOCK (-1)
#define CLOSE(s) close(s)
#endif
void spple_lan_socket_close(intptr_t socket_handle) {if((sock_t)socket_handle!=BADSOCK)CLOSE((sock_t)socket_handle);}
int spple_lan_connect(const char *host,uint16_t port,unsigned timeout_ms,intptr_t *out){
 if(!host || !*host || !port || !timeout_ms || timeout_ms>30000 || !out)return -1;*out=(intptr_t)BADSOCK;
 char service[8];snprintf(service,sizeof service,"%u",port);struct addrinfo hints,*list=NULL;
 memset(&hints,0,sizeof hints);hints.ai_family=AF_INET;hints.ai_socktype=SOCK_STREAM;hints.ai_protocol=IPPROTO_TCP;hints.ai_flags=AI_NUMERICHOST;
 if(getaddrinfo(host,service,&hints,&list))return -1;int result=-1;
 for(struct addrinfo *a=list;a;a=a->ai_next){
  sock_t s=socket(a->ai_family,a->ai_socktype,a->ai_protocol);if(s==BADSOCK)continue;
#ifdef _WIN32
  u_long mode=1;if(ioctlsocket(s,FIONBIO,&mode)){CLOSE(s);continue;}
#else
  int original=fcntl(s,F_GETFL,0);if(original<0 || fcntl(s,F_SETFL,original|O_NONBLOCK) || s>=FD_SETSIZE){CLOSE(s);continue;}
#endif
  int rc=connect(s,a->ai_addr,(int)a->ai_addrlen);
  if(rc){
#ifdef _WIN32
   int err=WSAGetLastError();if(err!=WSAEWOULDBLOCK && err!=WSAEINPROGRESS){CLOSE(s);continue;}
#else
   if(errno!=EINPROGRESS){CLOSE(s);continue;}
#endif
   fd_set writefds,exceptfds;FD_ZERO(&writefds);FD_ZERO(&exceptfds);FD_SET(s,&writefds);FD_SET(s,&exceptfds);
   struct timeval wait={(long)(timeout_ms/1000),(long)((timeout_ms%1000)*1000)};
#ifdef _WIN32
   rc=select(0,NULL,&writefds,&exceptfds,&wait);
#else
   rc=select(s+1,NULL,&writefds,&exceptfds,&wait);
#endif
   int error=0;
#ifdef _WIN32
   int n=sizeof error;
#else
   socklen_t n=sizeof error;
#endif
   if(rc<=0 || !FD_ISSET(s,&writefds) || getsockopt(s,SOL_SOCKET,SO_ERROR,(void *)&error,&n) || error){CLOSE(s);continue;}
  }
#ifdef _WIN32
  mode=0;DWORD timeout=timeout_ms;
  if(ioctlsocket(s,FIONBIO,&mode) || setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,(const char *)&timeout,sizeof timeout) || setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,(const char *)&timeout,sizeof timeout)){CLOSE(s);continue;}
#else
  struct timeval timeout={(long)(timeout_ms/1000),(long)((timeout_ms%1000)*1000)};
  if(fcntl(s,F_SETFL,original) || setsockopt(s,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof timeout) || setsockopt(s,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof timeout)){CLOSE(s);continue;}
#ifdef SO_NOSIGPIPE
  int one=1;if(setsockopt(s,SOL_SOCKET,SO_NOSIGPIPE,&one,sizeof one)){CLOSE(s);continue;}
#endif
#endif
  *out=(intptr_t)s;result=0;break;
 }
 freeaddrinfo(list);return result;
}
