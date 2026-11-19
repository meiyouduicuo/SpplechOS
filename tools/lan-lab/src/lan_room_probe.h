#ifndef SPPLE_LAN_ROOM_PROBE_H
#define SPPLE_LAN_ROOM_PROBE_H
#include "ldn_abi.h"
#include <stdint.h>
/* Probe an already-connected stream to fetch one room. This is discovery, not
 * joining; caller closes the stream afterward. Single peer per connection,
 * caller configures timeouts and SO_NOSIGPIPE. Unauthenticated experiment. */
int spple_lan_room_probe_server(intptr_t socket,uint64_t title,const spple_ldn_network_info *room);
int spple_lan_room_probe_client(intptr_t socket,uint64_t title,spple_ldn_network_info *out);
#endif
