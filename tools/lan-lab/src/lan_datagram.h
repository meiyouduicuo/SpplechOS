#ifndef SPPLE_LAN_DATAGRAM_H
#define SPPLE_LAN_DATAGRAM_H

#include "lan_protocol.h"

/* Experimental UDP-over-control-channel packet. Addresses are raw IPv4 network
 * order bytes. This alone is not a Switch socket implementation. */
enum { SPPLE_DATAGRAM_HEADER = 16, SPPLE_DATAGRAM_MAX_PAYLOAD = 65507 };
enum { SPPLE_DATAGRAM_UNICAST = 0, SPPLE_DATAGRAM_BROADCAST = 1 };
typedef struct {
    uint8_t source_ipv4[4];
    uint8_t destination_ipv4[4];
    uint16_t source_port;
    uint16_t destination_port;
    uint8_t mode;
    const uint8_t *payload;
    uint16_t payload_size;
} spple_datagram;

int spple_datagram_encode(const spple_datagram *datagram, void *out, size_t capacity, size_t *size_out);
int spple_datagram_decode(const void *data, size_t size, spple_datagram *out);

#endif
