#ifndef SPPLE_LAN_CONNECTION_H
#define SPPLE_LAN_CONNECTION_H
#include <stddef.h>
#include <stdint.h>
#include "ldn_abi.h"
typedef struct spple_lan_connection spple_lan_connection;
typedef void (*spple_connection_failed_fn)(void *context);
typedef int (*spple_connection_room_fn)(void *context,const spple_ldn_network_info *room);
/* One connection may use the game socket bridge at a time. Bridge must be
 * stopped first. On success takes ownership of the socket. Failure callbacks
 * are deferred until ready() and never run after stop() returns. */
spple_lan_connection *spple_lan_connection_start(intptr_t socket,uint64_t title,const uint8_t session[16],
 const uint8_t local_ip[4],const uint8_t peer_ip[4],spple_connection_failed_fn failed,void *context);
spple_lan_connection *spple_lan_connection_start_ex(intptr_t socket,uint64_t title,const uint8_t session[16],
 const uint8_t local_ip[4],const uint8_t peer_ip[4],spple_connection_room_fn room,spple_connection_failed_fn failed,void *context);
void spple_lan_connection_ready(spple_lan_connection *connection);
int spple_lan_connection_send(void *connection,const void *packet,size_t size);
int spple_lan_connection_send_room(spple_lan_connection *connection,const spple_ldn_network_info *room);
/* External thread only. Stop the bridge before removing the connection from
 * the vudp send callback; join workers before freeing callback context. */
void spple_lan_connection_stop(spple_lan_connection *connection);
void spple_lan_connection_destroy(spple_lan_connection *connection);
#endif
