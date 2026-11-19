#include "guest_socket_api.h"
#include "guest_sockaddr.h"
#include "lan_datagram.h"
#include <string.h>
/* Guest nn::socket uses musl errno values, not the BSD service wire values. Only nonblocking recv is implemented. */
enum { E_BADF=9,E_FAULT=14,E_INVAL=22,E_AGAIN=11,E_OPNOTSUPP=95,E_AFNOSUPPORT=97,E_NETDOWN=100 };
static int fail(int *error,int value) {if(error)*error=value; return -1;}
int spple_guest_socket_open(spple_guest_udp *g,int family,int type,int protocol,int *error) {
 if (!g) return fail(error,E_NETDOWN);
 if (family!=SPPLE_GUEST_AF_INET) return fail(error,E_AFNOSUPPORT);
 if ((type & ~0x30000000)!=2 || (protocol!=0 && protocol!=17)) return fail(error,E_OPNOTSUPP);
 int fd=spple_guest_udp_socket(g); return fd<0?fail(error,E_NETDOWN):fd;
}
int spple_guest_socket_bind(spple_guest_udp *g,int fd,const void *addr,unsigned size,int *error) {
 if (!g || spple_guest_udp_ready(g,fd)<0) return fail(error,E_BADF);
 uint8_t ip[4]; uint16_t port;
 if (spple_guest_sockaddr_decode(addr,size,ip,&port)) return fail(error,E_INVAL);
 static const uint8_t zero[4]={0};uint8_t local[4];uint16_t current;
 if(spple_guest_udp_local(g,fd,local,&current))return fail(error,E_BADF);
 if(memcmp(ip,zero,4) && memcmp(ip,local,4))return fail(error,E_OPNOTSUPP);
 return spple_guest_udp_bind(g,fd,port)?fail(error,E_INVAL):0;
}
long spple_guest_socket_sendto(spple_guest_udp *g,int fd,const void *data,unsigned long size,int flags,const void *addr,unsigned addrsize,int *error) {
 if (!g || spple_guest_udp_ready(g,fd)<0) return fail(error,E_BADF);
 if (size && !data) return fail(error,E_FAULT);
 if (flags || size>SPPLE_DATAGRAM_MAX_PAYLOAD) return fail(error,E_OPNOTSUPP);
 uint8_t ip[4]; uint16_t port;
 if (spple_guest_sockaddr_decode(addr,addrsize,ip,&port) || !port) return fail(error,E_INVAL);
 /* The current virtual LDN subnet is /24. Never emit native LAN broadcast. */
 static const uint8_t all[4]={255,255,255,255};uint8_t local[4];uint16_t current;
 if(spple_guest_udp_local(g,fd,local,&current))return fail(error,E_BADF);
 int broadcast=!memcmp(ip,all,4) || (!memcmp(ip,local,3) && ip[3]==255);
 return spple_guest_udp_send(g,fd,ip,port,broadcast,data,size)?fail(error,E_NETDOWN):(long)size;
}
long spple_guest_socket_recvfrom(spple_guest_udp *g,int fd,void *data,unsigned long size,int flags,void *addr,unsigned *addrsize,int *error) {
 if (!g || spple_guest_udp_ready(g,fd)<0) return fail(error,E_BADF);
 if ((size && !data) || (addr && !addrsize)) return fail(error,E_FAULT);
 if (flags!=0x80) return fail(error,E_OPNOTSUPP);
 uint8_t ip[4]; uint16_t port;
 int n=spple_guest_udp_receive(g,fd,data,size,ip,&port);
 if (n==-2) return fail(error,E_AGAIN);
 if (n<0) return fail(error,E_BADF);
 if (addr && spple_guest_sockaddr_encode(addr,addrsize,ip,port)) return fail(error,E_FAULT);
 return n;
}
int spple_guest_socket_close(spple_guest_udp *g,int fd,int *error) {
 return !g || spple_guest_udp_close(g,fd)?fail(error,E_BADF):0;
}
