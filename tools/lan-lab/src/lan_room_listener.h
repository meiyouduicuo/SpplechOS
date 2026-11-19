#ifndef SPPLE_LAN_ROOM_LISTENER_H
#define SPPLE_LAN_ROOM_LISTENER_H
#include "lan_secure_join.h"
#include <stddef.h>
/* Handles one accepted TCP connection. Return 1 for probe (caller closes), 2
 * for authenticated join (caller hands stream to game transport), -1 for
 * failure (caller closes). random must generate fresh cryptographic bytes. */
typedef int (*spple_room_random_fn)(void *context,void *out,size_t size);
int spple_room_listener_handle(intptr_t socket,uint64_t title,const spple_ldn_network_info *room,
 const void *key,size_t key_size,spple_room_random_fn random,spple_join_accept_fn accept,void *context);
#endif
