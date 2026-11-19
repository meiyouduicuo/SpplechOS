#ifndef SPPLE_VIRTUAL_UDP_H
#define SPPLE_VIRTUAL_UDP_H

#include <stddef.h>
#include <stdint.h>

/* Experimental, serialized two-peer virtual UDP model. Handles are private to
 * this model and are not yet guest file descriptors. The caller serializes all
 * calls and handles scheduling, timeouts, room authentication and transport. */
#define SPPLE_VUDP_SOCKETS 16
#define SPPLE_VUDP_QUEUE 32
typedef int (*spple_vudp_send_callback)(void *context, const void *packet, size_t size);
typedef struct spple_vudp spple_vudp;

spple_vudp *spple_vudp_create(const uint8_t local_ip[4], const uint8_t peer_ip[4],
                               spple_vudp_send_callback send, void *context);
void spple_vudp_destroy(spple_vudp *v);
/* Change virtual peers at a session boundary; drops queued old datagrams while
 * preserving socket handles and bound ports. Caller serializes this operation. */
int spple_vudp_reconfigure(spple_vudp *v,const uint8_t local_ip[4],const uint8_t peer_ip[4]);
int spple_vudp_socket(spple_vudp *v);
int spple_vudp_close(spple_vudp *v, int fd);
/* Guest poll bits: 1 when a datagram is queued, 4 when bound and writable;
 * -1 for a closed or invalid handle. Call under the model's serialization. */
int spple_vudp_ready(spple_vudp *v, int fd);
int spple_vudp_bind(spple_vudp *v, int fd, uint16_t port);
int spple_vudp_reuseaddr(spple_vudp *v,int fd,int enabled);
int spple_vudp_local(spple_vudp *v,int fd,uint8_t ip[4],uint16_t *port);
int spple_vudp_send(spple_vudp *v, int fd, const uint8_t destination[4], uint16_t port,
                    int broadcast, const void *data, size_t size);
int spple_vudp_ingest(spple_vudp *v, const void *packet, size_t size);
/* Returns bytes copied, -2 if no datagram is queued, -1 for invalid input. */
int spple_vudp_receive(spple_vudp *v, int fd, void *data, size_t capacity,
                       uint8_t source_ip[4], uint16_t *source_port);

#endif
