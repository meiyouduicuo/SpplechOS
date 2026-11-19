#ifndef SPPLE_LAN_TUNNEL_H
#define SPPLE_LAN_TUNNEL_H

#include "virtual_udp.h"
#include "lan_frame.h"
#include "ldn_abi.h"
#include <stdint.h>

/* Experimental two-peer control-stream tunnel. A single caller must serialize
 * writes, reads and virtual UDP access. It does not authenticate peers, manage
 * socket lifetime, perform discovery, or implement game SDK hooks. */
typedef struct {
    intptr_t socket;
    uint64_t title_id;
    uint8_t session_id[16];
    spple_vudp *udp;
} spple_lan_tunnel;

int spple_lan_tunnel_init(spple_lan_tunnel *t, intptr_t socket, uint64_t title_id,
                          const uint8_t session_id[16]);
int spple_lan_tunnel_attach_udp(spple_lan_tunnel *t, spple_vudp *udp);
/* Compatible with spple_vudp_send_callback. */
int spple_lan_tunnel_send(void *context, const void *packet, size_t size);
int spple_lan_tunnel_send_cancel(spple_lan_tunnel *t,const void *packet,size_t size,
                                 spple_lan_cancel_fn cancelled,void *cancel_context);
/* Processes one frame; returns -1 on I/O, framing, identity or delivery error. */
int spple_lan_tunnel_pump(spple_lan_tunnel *t);
typedef int (*spple_lan_ingest_callback)(void *context, const void *packet, size_t size);
/* The socket reader may block; callback is invoked only after a complete and
 * validated frame arrives, so it may acquire the guest-UDP bridge lock. */
int spple_lan_tunnel_pump_to(spple_lan_tunnel *t, spple_lan_ingest_callback ingest, void *context);
int spple_lan_tunnel_pump_cancel(spple_lan_tunnel *t, spple_lan_ingest_callback ingest, void *context,
                                  spple_lan_cancel_fn cancelled, void *cancel_context);
typedef int (*spple_lan_room_callback)(void *context,const spple_ldn_network_info *room);
int spple_lan_tunnel_pump_events(spple_lan_tunnel *t,spple_lan_ingest_callback ingest,spple_lan_room_callback room,void *context,
                                  spple_lan_cancel_fn cancelled,void *cancel_context);

#endif
