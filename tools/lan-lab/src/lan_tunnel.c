#include "lan_tunnel.h"
#include "lan_datagram.h"
#include "lan_frame.h"
#include "lan_protocol.h"
#include "ldn_advertisement.h"

#include <stdlib.h>
#include <string.h>

int spple_lan_tunnel_init(spple_lan_tunnel *t, intptr_t socket, uint64_t title_id,
                          const uint8_t session_id[16]) {
    if (!t || !title_id || !session_id) return -1;
    unsigned any = 0;
    for (int i = 0; i < 16; ++i) any |= session_id[i];
    if (!any) return -1;
    memset(t, 0, sizeof(*t));
    t->socket = socket; t->title_id = title_id;
    memcpy(t->session_id, session_id, 16);
    return 0;
}

int spple_lan_tunnel_attach_udp(spple_lan_tunnel *t, spple_vudp *udp) {
    if (!t || !t->title_id || !udp || t->udp) return -1;
    t->udp = udp;
    return 0;
}

int spple_lan_tunnel_send(void *context, const void *packet, size_t size) {
    return spple_lan_tunnel_send_cancel(context,packet,size,NULL,NULL);
}
int spple_lan_tunnel_send_cancel(spple_lan_tunnel *t,const void *packet,size_t size,
                                  spple_lan_cancel_fn cancelled,void *cancel_context) {
    if (!t || !t->title_id || !packet || size > SPPLE_DATAGRAM_HEADER + SPPLE_DATAGRAM_MAX_PAYLOAD) return -1;
    size_t capacity = SPPLE_PROTOCOL_HEADER + size;
    uint8_t *encoded = malloc(capacity);
    if (!encoded) return -1;
    spple_message msg = { .kind = SPPLE_MSG_DATAGRAM, .title_id = t->title_id,
                          .body = packet, .body_size = (uint32_t)size };
    memcpy(msg.session_id, t->session_id, 16);
    size_t encoded_size = 0;
    int rc = spple_protocol_encode(&msg, encoded, capacity, &encoded_size);
    if (!rc) rc = spple_lan_send_frame_cancel(t->socket, encoded, encoded_size,cancelled,cancel_context);
    free(encoded);
    return rc ? -1 : 0;
}

int spple_lan_tunnel_pump_to(spple_lan_tunnel *t, spple_lan_ingest_callback ingest, void *context) {
    return spple_lan_tunnel_pump_cancel(t,ingest,context,NULL,NULL);
}
int spple_lan_tunnel_pump_cancel(spple_lan_tunnel *t, spple_lan_ingest_callback ingest, void *context,
                                  spple_lan_cancel_fn cancelled, void *cancel_context) {
    return spple_lan_tunnel_pump_events(t,ingest,NULL,context,cancelled,cancel_context);
}
int spple_lan_tunnel_pump_events(spple_lan_tunnel *t,spple_lan_ingest_callback ingest,spple_lan_room_callback room,void *context,
                                  spple_lan_cancel_fn cancelled,void *cancel_context) {
    if (!t || !t->title_id || !ingest) return -1;
    const size_t capacity = SPPLE_PROTOCOL_HEADER + SPPLE_DATAGRAM_HEADER + SPPLE_DATAGRAM_MAX_PAYLOAD;
    uint8_t *buffer = malloc(capacity);
    if (!buffer) return -1;
    size_t received = 0;
    spple_message msg;
    int rc = spple_lan_receive_frame_cancel(t->socket, buffer, capacity, &received,cancelled,cancel_context);
    if (!rc) rc = spple_protocol_decode(buffer, received, &msg);
    if (!rc && (msg.title_id != t->title_id ||
                memcmp(msg.session_id, t->session_id, 16))) rc = -1;
    if (!rc && msg.kind==SPPLE_MSG_DATAGRAM) rc = ingest(context, msg.body, msg.body_size);
    else if (!rc && msg.kind==SPPLE_MSG_ADVERTISE && room) {
        spple_ldn_scan_filter filter={0};spple_ldn_network_info info;
        if(spple_ldn_advertisement_decode(t->title_id,buffer,received,&filter,&info)!=1)rc=-1;
        else rc=room(context,&info);
    } else if(!rc)rc=-1;
    free(buffer);
    return rc ? -1 : 0;
}
static int ingest_udp(void *context, const void *packet, size_t size) { return spple_vudp_ingest(context,packet,size); }
int spple_lan_tunnel_pump(spple_lan_tunnel *t) {
    if (!t || !t->udp) return -1;
    return spple_lan_tunnel_pump_to(t,ingest_udp,t->udp);
}
