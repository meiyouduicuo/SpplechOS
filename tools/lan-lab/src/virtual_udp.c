#include "virtual_udp.h"
#include "lan_datagram.h"

#include <stdlib.h>
#include <string.h>

typedef struct packet {
    uint8_t ip[4]; uint16_t port; uint16_t size; uint8_t data[];
} packet;
typedef struct {
    int used,reuseaddr; uint16_t port; unsigned read_index; unsigned count;
    packet *queue[SPPLE_VUDP_QUEUE];
} guest_socket;
struct spple_vudp {
    uint8_t local[4], peer[4];
    spple_vudp_send_callback send;
    void *context;
    uint16_t next_ephemeral;
    guest_socket sockets[SPPLE_VUDP_SOCKETS];
};

static int same_ip(const uint8_t *a, const uint8_t *b) { return memcmp(a, b, 4) == 0; }
static guest_socket *lookup(spple_vudp *v, int fd) {
    return v && fd >= 0 && fd < SPPLE_VUDP_SOCKETS && v->sockets[fd].used ? &v->sockets[fd] : NULL;
}
static int queue_one(guest_socket *s, const spple_datagram *d) {
    if (s->count == SPPLE_VUDP_QUEUE) return -1;
    packet *p = malloc(sizeof(*p) + d->payload_size);
    if (!p) return -1;
    memcpy(p->ip, d->source_ipv4, 4); p->port = d->source_port; p->size = d->payload_size;
    if (p->size) memcpy(p->data, d->payload, p->size);
    s->queue[(s->read_index + s->count) % SPPLE_VUDP_QUEUE] = p;
    ++s->count;
    return 0;
}
static int deliver_local(spple_vudp *v, const spple_datagram *d) {
    for (int i = 0; i < SPPLE_VUDP_SOCKETS; ++i) {
        guest_socket *s = &v->sockets[i];
        if (s->used && s->port == d->destination_port) {
            /* UDP is lossy: a full receive queue drops the datagram; it must
             * not be reported as a broken tunnel to the stream reader. */
            (void)queue_one(s, d);
            if (d->mode != SPPLE_DATAGRAM_BROADCAST) return 0;
        }
    }
    return 0; /* UDP to a closed port is not a local send failure. */
}

spple_vudp *spple_vudp_create(const uint8_t local[4], const uint8_t peer[4],
                               spple_vudp_send_callback send, void *context) {
    static const uint8_t zero[4] = {0};
    if (!local || !peer || !send || same_ip(local, peer) || same_ip(local, zero) || same_ip(peer, zero)) return NULL;
    spple_vudp *v = calloc(1, sizeof(*v));
    if (v) { memcpy(v->local, local, 4); memcpy(v->peer, peer, 4); v->send = send; v->context = context; v->next_ephemeral=49152; }
    return v;
}
void spple_vudp_destroy(spple_vudp *v) {
    if (!v) return;
    for (int i = 0; i < SPPLE_VUDP_SOCKETS; ++i) if (v->sockets[i].used) spple_vudp_close(v, i);
    free(v);
}
int spple_vudp_reconfigure(spple_vudp *v,const uint8_t local[4],const uint8_t peer[4]) {
    static const uint8_t zero[4]={0};
    if(!v || !local || !peer || same_ip(local,peer) || same_ip(local,zero) || same_ip(peer,zero))return -1;
    for(int i=0;i<SPPLE_VUDP_SOCKETS;++i) {
        guest_socket *s=&v->sockets[i];
        for(unsigned j=0;j<s->count;++j)free(s->queue[(s->read_index+j)%SPPLE_VUDP_QUEUE]);
        memset(s->queue,0,sizeof s->queue);s->read_index=s->count=0;
    }
    memcpy(v->local,local,4);memcpy(v->peer,peer,4);return 0;
}
int spple_vudp_socket(spple_vudp *v) {
    if (!v) return -1;
    for (int i = 0; i < SPPLE_VUDP_SOCKETS; ++i) if (!v->sockets[i].used) { v->sockets[i].used = 1; return i; }
    return -1;
}
int spple_vudp_close(spple_vudp *v, int fd) {
    guest_socket *s = lookup(v, fd);
    if (!s) return -1;
    for (unsigned i = 0; i < s->count; ++i) free(s->queue[(s->read_index + i) % SPPLE_VUDP_QUEUE]);
    memset(s, 0, sizeof(*s));
    return 0;
}
int spple_vudp_ready(spple_vudp *v, int fd) {
    guest_socket *s = lookup(v, fd);
    if (!s) return -1;
    return (s->count ? 1 : 0) | (s->port ? 4 : 0);
}
int spple_vudp_bind(spple_vudp *v, int fd, uint16_t port) {
    guest_socket *s = lookup(v, fd);
    if (!s || s->port) return -1;
    if (!port) {
        for (unsigned tries=0;tries<16384;tries++) {
            uint16_t candidate=v->next_ephemeral;
            v->next_ephemeral = candidate==65535 ? 49152 : (uint16_t)(candidate+1);
            int used=0; for (int i=0;i<SPPLE_VUDP_SOCKETS;i++) if(v->sockets[i].used && v->sockets[i].port==candidate) {used=1;break;}
            if(!used){port=candidate;break;}
        }
        if(!port)return -1;
    }
    for (int i = 0; i < SPPLE_VUDP_SOCKETS; ++i) if (v->sockets[i].used && v->sockets[i].port == port && (!s->reuseaddr || !v->sockets[i].reuseaddr)) return -1;
    s->port = port;
    return 0;
}
int spple_vudp_reuseaddr(spple_vudp *v,int fd,int enabled) {
    guest_socket *s=lookup(v,fd);if(!s)return -1;s->reuseaddr=!!enabled;return 0;
}
int spple_vudp_local(spple_vudp *v,int fd,uint8_t ip[4],uint16_t *port) {
    guest_socket *s=lookup(v,fd);if(!s || !ip || !port)return -1;
    memcpy(ip,v->local,4);*port=s->port;return 0;
}
int spple_vudp_send(spple_vudp *v, int fd, const uint8_t dest[4], uint16_t port,
                    int broadcast, const void *data, size_t size) {
    guest_socket *s = lookup(v, fd);
    if (!s || !dest || !port || (broadcast != 0 && broadcast != 1) ||
        size > SPPLE_DATAGRAM_MAX_PAYLOAD || (size && !data)) return -1;
    if (!broadcast && !same_ip(dest, v->local) && !same_ip(dest, v->peer)) return -1;
    if (!s->port && spple_vudp_bind(v,fd,0)) return -1;
    spple_datagram d = { .source_port = s->port, .destination_port = port,
                        .mode = broadcast ? SPPLE_DATAGRAM_BROADCAST : SPPLE_DATAGRAM_UNICAST,
                        .payload = data, .payload_size = (uint16_t)size };
    memcpy(d.source_ipv4, v->local, 4); memcpy(d.destination_ipv4, dest, 4);
    if (broadcast || same_ip(dest, v->peer)) {
        uint8_t *encoded = malloc(SPPLE_DATAGRAM_HEADER + size);
        size_t encoded_size;
        if (!encoded) return -1;
        int ret = spple_datagram_encode(&d, encoded, SPPLE_DATAGRAM_HEADER + size, &encoded_size);
        if (!ret) ret = v->send(v->context, encoded, encoded_size);
        free(encoded);
        if (ret) return -1;
    }
    if (broadcast || same_ip(dest, v->local)) return deliver_local(v, &d);
    return 0;
}
int spple_vudp_ingest(spple_vudp *v, const void *packet_bytes, size_t size) {
    spple_datagram d;
    if (!v || spple_datagram_decode(packet_bytes, size, &d) || !same_ip(d.source_ipv4, v->peer) ||
        !d.source_port || (d.mode == SPPLE_DATAGRAM_UNICAST && !same_ip(d.destination_ipv4, v->local))) return -1;
    return deliver_local(v, &d);
}
int spple_vudp_receive(spple_vudp *v, int fd, void *data, size_t capacity,
                       uint8_t source_ip[4], uint16_t *source_port) {
    guest_socket *s = lookup(v, fd);
    if (!s || (capacity && !data) || !source_ip || !source_port) return -1;
    if (!s->count) return -2;
    packet *p = s->queue[s->read_index];
    size_t size = p->size < capacity ? p->size : capacity;
    if (size) memcpy(data, p->data, size);
    memcpy(source_ip, p->ip, 4); *source_port = p->port;
    free(p); s->queue[s->read_index] = NULL;
    s->read_index = (s->read_index + 1) % SPPLE_VUDP_QUEUE; --s->count;
    return (int)size;
}
