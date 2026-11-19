#include "guest_sockaddr.h"
#include <string.h>
int spple_guest_sockaddr_decode(const void *address,size_t length,uint8_t ip[4],uint16_t *port) {
    if (!address || !ip || !port || length<SPPLE_GUEST_SOCKADDR_IN_SIZE) return -1;
    const uint8_t *p=address;
    if (p[0]!=SPPLE_GUEST_SOCKADDR_IN_SIZE || p[1]!=SPPLE_GUEST_AF_INET) return -1;
    uint16_t value=(uint16_t)(((uint16_t)p[2]<<8)|p[3]);
    memcpy(ip,p+4,4); *port=value; return 0;
}
int spple_guest_sockaddr_encode(void *address,unsigned *length,const uint8_t ip[4],uint16_t port) {
    if (!length || !ip || (!address && *length)) return -1;
    uint8_t data[SPPLE_GUEST_SOCKADDR_IN_SIZE]={SPPLE_GUEST_SOCKADDR_IN_SIZE,SPPLE_GUEST_AF_INET};
    data[2]=(uint8_t)(port>>8); data[3]=(uint8_t)port; memcpy(data+4,ip,4);
    unsigned n=*length<sizeof(data)?*length:(unsigned)sizeof(data);
    if (n) memcpy(address,data,n); *length=sizeof(data); return 0;
}
