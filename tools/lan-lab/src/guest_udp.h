#ifndef SPPLE_GUEST_UDP_H
#define SPPLE_GUEST_UDP_H
#include "virtual_udp.h"
#include <stdint.h>
/* Caller serializes every method except ready(); notify is called after changes,
 * outside any engine fd lock. The UDP model must outlive this adapter. Stop
 * all readiness callbacks before freeing the adapter. */
#define SPPLE_GUEST_UDP_LIMIT 64
typedef struct spple_guest_udp spple_guest_udp;
typedef int (*spple_guest_reserve_fn)(void *context);
typedef int (*spple_guest_release_fn)(void *context, int fd);
typedef void (*spple_guest_notify_fn)(void *context);
spple_guest_udp *spple_guest_udp_new(spple_vudp *udp, spple_guest_reserve_fn reserve,
                                     spple_guest_release_fn release, spple_guest_notify_fn notify, void *context);
void spple_guest_udp_free(spple_guest_udp *g);
int spple_guest_udp_reconfigure(spple_guest_udp *g,const uint8_t local_ip[4],const uint8_t peer_ip[4]);
int spple_guest_udp_socket(spple_guest_udp *g);
int spple_guest_udp_close(spple_guest_udp *g, int fd);
int spple_guest_udp_bind(spple_guest_udp *g, int fd, uint16_t port);
int spple_guest_udp_reuseaddr(spple_guest_udp *g,int fd,int enabled);
int spple_guest_udp_local(spple_guest_udp *g,int fd,uint8_t ip[4],uint16_t *port);
int spple_guest_udp_send(spple_guest_udp *g, int fd, const uint8_t ip[4], uint16_t port,
                         int broadcast, const void *data, size_t size);
int spple_guest_udp_receive(spple_guest_udp *g, int fd, void *data, size_t capacity, uint8_t ip[4], uint16_t *port);
int spple_guest_udp_ingest(spple_guest_udp *g, const void *packet, size_t size);
/* Lock-free and safe inside the engine descriptor lock. -1 means invalid. */
int spple_guest_udp_ready(const spple_guest_udp *g, int fd);
#endif
