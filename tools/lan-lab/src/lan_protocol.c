#include "lan_protocol.h"

#include <string.h>

static void write_be32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24); p[1] = (uint8_t)(v >> 16); p[2] = (uint8_t)(v >> 8); p[3] = (uint8_t)v;
}
static uint32_t read_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}
static int valid_kind(uint8_t kind) { return kind >= SPPLE_MSG_HELLO && kind <= SPPLE_MSG_DATAGRAM; }

int spple_protocol_encode(const spple_message *m, void *out, size_t capacity, size_t *size_out) {
    if (!size_out) return -1;
    *size_out = 0;
    if (!m || !out || !valid_kind(m->kind) || !m->title_id || m->body_size > SPPLE_PROTOCOL_MAX_BODY ||
        (m->body_size && !m->body) || capacity < SPPLE_PROTOCOL_HEADER + (size_t)m->body_size) return -1;
    uint8_t *p = out;
    memcpy(p, "SPLC", 4);
    p[4] = SPPLE_PROTOCOL_VERSION; p[5] = m->kind; p[6] = 0; p[7] = 0;
    for (int i = 0; i < 8; ++i) p[8 + i] = (uint8_t)(m->title_id >> (56 - i * 8));
    memcpy(p + 16, m->session_id, 16);
    write_be32(p + 32, m->body_size);
    if (m->body_size) memcpy(p + SPPLE_PROTOCOL_HEADER, m->body, m->body_size);
    *size_out = SPPLE_PROTOCOL_HEADER + (size_t)m->body_size;
    return 0;
}

int spple_protocol_decode(const void *data, size_t size, spple_message *out) {
    if (!out) return -1;
    memset(out, 0, sizeof(*out));
    if (!data || size < SPPLE_PROTOCOL_HEADER) return -1;
    const uint8_t *p = data;
    if (memcmp(p, "SPLC", 4) || p[4] != SPPLE_PROTOCOL_VERSION || !valid_kind(p[5]) || p[6] || p[7]) return -1;
    uint32_t n = read_be32(p + 32);
    if (n > SPPLE_PROTOCOL_MAX_BODY || size - SPPLE_PROTOCOL_HEADER != n) return -1;
    uint64_t title = 0;
    for (int i = 0; i < 8; ++i) title = (title << 8) | p[8 + i];
    if (!title) return -1;
    out->kind = p[5]; out->title_id = title;
    memcpy(out->session_id, p + 16, 16);
    out->body = p + SPPLE_PROTOCOL_HEADER;
    out->body_size = n;
    return 0;
}
