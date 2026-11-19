#ifndef SPPLE_LAN_HANDSHAKE_H
#define SPPLE_LAN_HANDSHAKE_H

#include <stdint.h>

/* Blocking experimental room handshake. Callers must configure socket timeouts
 * and close the socket after failure. This does not authenticate the peer and
 * must not yet be exposed to user gameplay or an untrusted network. */
int spple_room_client_handshake(intptr_t socket, uint64_t title_id, uint8_t session_out[16]);
int spple_room_server_handshake(intptr_t socket, uint64_t title_id, const uint8_t session_id[16]);

#endif
