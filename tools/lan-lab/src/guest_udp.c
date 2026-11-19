#include "guest_udp.h"
#include <stdatomic.h>
#include <stdlib.h>
struct spple_guest_udp {
    spple_vudp *udp;
    spple_guest_reserve_fn reserve;
    spple_guest_release_fn release;
    spple_guest_notify_fn notify;
    void *context;
    int local[SPPLE_GUEST_UDP_LIMIT];
    _Atomic int ready[SPPLE_GUEST_UDP_LIMIT];
};
static int valid(const spple_guest_udp *g,int fd) { return g && fd>=0 && fd<SPPLE_GUEST_UDP_LIMIT && g->local[fd]>=0; }
static void refresh(spple_guest_udp *g) {
    for (int i=0;i<SPPLE_GUEST_UDP_LIMIT;++i)
        if (g->local[i]>=0) atomic_store(&g->ready[i],spple_vudp_ready(g->udp,g->local[i]));
    g->notify(g->context);
}
spple_guest_udp *spple_guest_udp_new(spple_vudp *udp,spple_guest_reserve_fn reserve,spple_guest_release_fn release,spple_guest_notify_fn notify,void *context) {
    if (!udp || !reserve || !release || !notify) return NULL;
    spple_guest_udp *g=calloc(1,sizeof(*g)); if (!g) return NULL;
    g->udp=udp; g->reserve=reserve; g->release=release; g->notify=notify; g->context=context;
    for (int i=0;i<SPPLE_GUEST_UDP_LIMIT;++i) {g->local[i]=-1; atomic_init(&g->ready[i],-1);}
    return g;
}
void spple_guest_udp_free(spple_guest_udp *g) {
    if (!g) return;
    for (int i=0;i<SPPLE_GUEST_UDP_LIMIT;++i) if (g->local[i]>=0) (void)spple_guest_udp_close(g,i);
    free(g);
}
int spple_guest_udp_reconfigure(spple_guest_udp *g,const uint8_t local[4],const uint8_t peer[4]) {
    if(!g || spple_vudp_reconfigure(g->udp,local,peer))return -1;
    refresh(g);return 0;
}
int spple_guest_udp_socket(spple_guest_udp *g) {
    if (!g) return -1;
    int local=spple_vudp_socket(g->udp); if (local<0) return -1;
    int fd=g->reserve(g->context);
    if (fd<0 || fd>=SPPLE_GUEST_UDP_LIMIT || g->local[fd]>=0) {
        if (fd>=SPPLE_GUEST_UDP_LIMIT) (void)g->release(g->context,fd);
        (void)spple_vudp_close(g->udp,local); return -1;
    }
    g->local[fd]=local; refresh(g); return fd;
}
int spple_guest_udp_close(spple_guest_udp *g,int fd) {
    if (!valid(g,fd)) return -1;
    int local=g->local[fd]; g->local[fd]=-1; atomic_store(&g->ready[fd],-1);
    int a=spple_vudp_close(g->udp,local), b=g->release(g->context,fd);
    g->notify(g->context); return a || b ? -1 : 0;
}
int spple_guest_udp_bind(spple_guest_udp *g,int fd,uint16_t port) {
    if (!valid(g,fd)) return -1;
    int rc=spple_vudp_bind(g->udp,g->local[fd],port); refresh(g); return rc;
}
int spple_guest_udp_reuseaddr(spple_guest_udp *g,int fd,int enabled) {
    return valid(g,fd)?spple_vudp_reuseaddr(g->udp,g->local[fd],enabled):-1;
}
int spple_guest_udp_local(spple_guest_udp *g,int fd,uint8_t ip[4],uint16_t *port) {
    return valid(g,fd)?spple_vudp_local(g->udp,g->local[fd],ip,port):-1;
}
int spple_guest_udp_send(spple_guest_udp *g,int fd,const uint8_t ip[4],uint16_t port,int broadcast,const void *data,size_t size) {
    if (!valid(g,fd)) return -1;
    int rc=spple_vudp_send(g->udp,g->local[fd],ip,port,broadcast,data,size); refresh(g); return rc;
}
int spple_guest_udp_receive(spple_guest_udp *g,int fd,void *data,size_t cap,uint8_t ip[4],uint16_t *port) {
    if (!valid(g,fd)) return -1;
    int rc=spple_vudp_receive(g->udp,g->local[fd],data,cap,ip,port); refresh(g); return rc;
}
int spple_guest_udp_ingest(spple_guest_udp *g,const void *packet,size_t size) {
    if (!g) return -1;
    int rc=spple_vudp_ingest(g->udp,packet,size); refresh(g); return rc;
}
int spple_guest_udp_ready(const spple_guest_udp *g,int fd) {
    if (!g || fd<0 || fd>=SPPLE_GUEST_UDP_LIMIT) return -1;
    return atomic_load(&g->ready[fd]);
}
