#ifndef SPPLE_LAN_SERVER_H
#define SPPLE_LAN_SERVER_H
#include "lan_room_listener.h"
#include <stdint.h>
typedef struct spple_lan_server spple_lan_server;
/* snapshot and callbacks run on the server worker. The listener owns accepted
 * sockets until joined() receives one. Callbacks must not stop the server. */
typedef int (*spple_server_snapshot_fn)(void *context,spple_ldn_network_info *room);
/* Return 0 to take ownership of the socket; failure leaves it with server. */
typedef int (*spple_server_joined_fn)(void *context,intptr_t socket);
typedef void (*spple_server_rollback_fn)(void *context);
spple_lan_server *spple_lan_server_start(uint64_t title,const void *key,size_t key_size,
 spple_server_snapshot_fn snapshot,spple_room_random_fn random,spple_join_accept_fn accept,
 spple_server_joined_fn joined,spple_server_rollback_fn rollback,void *context);
uint16_t spple_lan_server_port(const spple_lan_server *server);
/* External thread only. Stops listening and pending handshake, joins worker. */
void spple_lan_server_stop(spple_lan_server *server);
void spple_lan_server_destroy(spple_lan_server *server);
#endif
