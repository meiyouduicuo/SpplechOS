#include "lan_datagram.h"

#include <string.h>

int spple_datagram_encode(const spple_datagram *d, void *out, size_t capacity, size_t *size_out) {
    if (!size_out) return -1;
    *size_out = 0;
    if (!d || !out || d->mode > SPPLE_DATAGRAM_BROADCAST || !d->destination_port ||
        d->payload_size > SPPLE_DATAGRAM_MAX_PAYLOAD || (d->payload_size && !d->payload) ||
        capacity < SPPLE_DATAGRAM_HEADER + (size_t)d->payload_size) return -1;
    uint8_t *p = out;
    memcpy(p, d->source_ipv4, 4); memcpy(p + 4, d->destination_ipv4, 4);
    p[8] = (uint8_t)(d->source_port >> 8); p[9] = (uint8_t)d->source_port;
    p[10] = (uint8_t)(d->destination_port >> 8); p[11] = (uint8_t)d->destination_port;
    p[12] = d->mode; p[13] = 0;
    p[14] = (uint8_t)(d->payload_size >> 8); p[15] = (uint8_t)d->payload_size;
    if (d->payload_size) memcpy(p + SPPLE_DATAGRAM_HEADER, d->payload, d->payload_size);
    *size_out = SPPLE_DATAGRAM_HEADER + (size_t)d->payload_size;
    return 0;
}

int spple_datagram_decode(const void *data, size_t size, spple_datagram *out) {
    if (!out) return -1;
    memset(out, 0, sizeof(*out));
    if (!data || size < SPPLE_DATAGRAM_HEADER) return -1;
    const uint8_t *p = data;
    uint16_t length = (uint16_t)(((uint16_t)p[14] << 8) | p[15]);
    uint16_t port = (uint16_t)(((uint16_t)p[10] << 8) | p[11]);
    if (p[12] > SPPLE_DATAGRAM_BROADCAST || p[13] || !port || length > SPPLE_DATAGRAM_MAX_PAYLOAD ||
        size - SPPLE_DATAGRAM_HEADER != length) return -1;
    memcpy(out->source_ipv4, p, 4); memcpy(out->destination_ipv4, p + 4, 4);
    out->source_port = (uint16_t)(((uint16_t)p[8] << 8) | p[9]);
    out->destination_port = port; out->mode = p[12];
    out->payload = p + SPPLE_DATAGRAM_HEADER; out->payload_size = length;
    return 0;
}
