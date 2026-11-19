#ifndef SPPLE_LAN_PROTOCOL_H
#define SPPLE_LAN_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>

/* Experimental SpplechOS-to-SpplechOS control protocol, not Switch LDN wire
 * format. It does not authenticate peers or implement the guest socket API. */
enum { SPPLE_PROTOCOL_VERSION = 1, SPPLE_PROTOCOL_HEADER = 36, SPPLE_PROTOCOL_MAX_BODY = 65536 };
enum spple_message_kind {
    SPPLE_MSG_HELLO = 1, SPPLE_MSG_WELCOME = 2, SPPLE_MSG_ADVERTISE = 3,
    SPPLE_MSG_JOIN = 4, SPPLE_MSG_LEAVE = 5, SPPLE_MSG_DATAGRAM = 6
};
typedef struct {
    uint8_t kind;
    uint64_t title_id;
    uint8_t session_id[16];
    const uint8_t *body; /* points into the input buffer after decode */
    uint32_t body_size;
} spple_message;

int spple_protocol_encode(const spple_message *message, void *out, size_t capacity, size_t *size_out);
int spple_protocol_decode(const void *data, size_t size, spple_message *out);

#endif
