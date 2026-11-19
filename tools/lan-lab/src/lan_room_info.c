#include "lan_room_info.h"
#include "lan_protocol.h"
#include "lan_frame.h"
#include "ldn_advertisement.h"
#include <string.h>

static int identity_ok(const spple_ldn_network_info *info, const uint8_t *session) {
    unsigned any=0; for (int i=0;i<16;++i) any |= session[i];
    return any && !spple_ldn_validate_network(info) && !memcmp(info->network_id.session_id,session,16);
}
int spple_room_info_send(intptr_t socket, uint64_t title, const uint8_t session[16], const spple_ldn_network_info *info) {
    if (!title || !session || !info || !identity_ok(info,session)) return -1;
    uint8_t buffer[SPPLE_PROTOCOL_HEADER + sizeof(*info)]; size_t size=0;
    if (spple_ldn_advertisement_encode(title,info,buffer,sizeof(buffer),&size)) return -1;
    return spple_lan_send_frame(socket,buffer,size) == SPPLE_LAN_OK ? 0 : -1;
}
int spple_room_info_receive(intptr_t socket, uint64_t title, const uint8_t session[16], spple_ldn_network_info *out) {
    if (!title || !session || !out) return -1;
    uint8_t buffer[SPPLE_PROTOCOL_HEADER + sizeof(*out)]; size_t size=0; spple_message msg;
    if (spple_lan_receive_frame(socket,buffer,sizeof(buffer),&size) != SPPLE_LAN_OK ||
        spple_protocol_decode(buffer,size,&msg) || msg.kind != SPPLE_MSG_ADVERTISE || msg.title_id != title ||
        memcmp(msg.session_id,session,16) || msg.body_size != sizeof(*out)) return -1;
    spple_ldn_network_info candidate; memcpy(&candidate,msg.body,sizeof candidate);
    if (!identity_ok(&candidate,session)) return -1;
    *out=candidate; return 0;
}
