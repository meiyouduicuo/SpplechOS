#include "lan_handshake.h"
#include "lan_frame.h"
#include "lan_protocol.h"

#include <string.h>

static int all_zero(const uint8_t *data, size_t size) {
    uint8_t any = 0;
    for (size_t i = 0; i < size; ++i) any |= data[i];
    return any == 0;
}

static int send_message(intptr_t socket, const spple_message *message) {
    uint8_t packet[SPPLE_PROTOCOL_HEADER];
    size_t size;
    if (message->body_size || spple_protocol_encode(message, packet, sizeof packet, &size)) return -1;
    return spple_lan_send_frame(socket, packet, size) == SPPLE_LAN_OK ? 0 : -1;
}

static int receive_message(intptr_t socket, uint8_t *packet, size_t capacity, spple_message *message) {
    size_t size;
    if (spple_lan_receive_frame(socket, packet, capacity, &size) != SPPLE_LAN_OK) return -1;
    return spple_protocol_decode(packet, size, message);
}

int spple_room_client_handshake(intptr_t socket, uint64_t title_id, uint8_t session_out[16]) {
    if (!title_id || !session_out) return -1;
    memset(session_out, 0, 16);
    spple_message hello = { .kind = SPPLE_MSG_HELLO, .title_id = title_id };
    if (send_message(socket, &hello)) return -1;
    uint8_t packet[SPPLE_PROTOCOL_HEADER];
    spple_message reply;
    if (receive_message(socket, packet, sizeof packet, &reply) || reply.kind != SPPLE_MSG_WELCOME ||
        reply.title_id != title_id || reply.body_size || all_zero(reply.session_id, 16)) return -1;
    memcpy(session_out, reply.session_id, 16);
    return 0;
}

int spple_room_server_handshake(intptr_t socket, uint64_t title_id, const uint8_t session_id[16]) {
    if (!title_id || !session_id || all_zero(session_id, 16)) return -1;
    uint8_t packet[SPPLE_PROTOCOL_HEADER];
    spple_message hello;
    if (receive_message(socket, packet, sizeof packet, &hello) || hello.kind != SPPLE_MSG_HELLO ||
        hello.title_id != title_id || hello.body_size || !all_zero(hello.session_id, 16)) return -1;
    spple_message reply = { .kind = SPPLE_MSG_WELCOME, .title_id = title_id };
    memcpy(reply.session_id, session_id, 16);
    return send_message(socket, &reply);
}
