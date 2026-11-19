#ifndef SPPLE_LAN_ROOM_EXCHANGE_H
#define SPPLE_LAN_ROOM_EXCHANGE_H
#include "ldn_abi.h"
#include <stdint.h>
enum { SPPLE_ROOM_PROBE=1, SPPLE_ROOM_JOIN=2 };
/* Caller provides exclusive handshaken stream and socket timeouts. Probe must
 * close its stream after return; join retains it for data only when accepted.
 * Prototype: identity checks are not peer authentication. */
int spple_room_exchange_client(intptr_t socket,uint64_t title,int mode,spple_ldn_network_info *out);
int spple_room_exchange_server(intptr_t socket,uint64_t title,const spple_ldn_network_info *room,int *mode_out);
#endif
