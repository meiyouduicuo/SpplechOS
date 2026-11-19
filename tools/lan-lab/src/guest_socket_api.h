#ifndef SPPLE_GUEST_SOCKET_API_H
#define SPPLE_GUEST_SOCKET_API_H
#include "guest_udp.h"
/* Nonblocking UDP experiment; caller serializes access. It does not implement
 * connected sockets, blocking receive, socket options, or game ABI validation. */
int spple_guest_socket_open(spple_guest_udp *g,int family,int type,int protocol,int *error);
int spple_guest_socket_bind(spple_guest_udp *g,int fd,const void *addr,unsigned size,int *error);
long spple_guest_socket_sendto(spple_guest_udp *g,int fd,const void *data,unsigned long size,int flags,const void *addr,unsigned addrsize,int *error);
long spple_guest_socket_recvfrom(spple_guest_udp *g,int fd,void *data,unsigned long size,int flags,void *addr,unsigned *addrsize,int *error);
int spple_guest_socket_close(spple_guest_udp *g,int fd,int *error);
#endif
