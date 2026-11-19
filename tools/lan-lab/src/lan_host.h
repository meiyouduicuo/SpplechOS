#ifndef SPPLE_LAN_HOST_H
#define SPPLE_LAN_HOST_H
#include "lan_server.h"
/* Status 1 = Bonjour published, 0 = lost or timed out. Callbacks must not
 * stop/destroy this object or retain borrowed data. */
typedef struct spple_lan_host spple_lan_host;
typedef void (*spple_host_status_fn)(void *context,int published);
spple_lan_host *spple_lan_host_start(uint64_t title,const char *service_name,const void *key,size_t key_size,
 spple_server_snapshot_fn snapshot,spple_room_random_fn random,spple_join_accept_fn accept,
 spple_server_joined_fn joined,spple_server_rollback_fn rollback,spple_host_status_fn status,void *context);
void spple_lan_host_stop(spple_lan_host *host);
void spple_lan_host_destroy(spple_lan_host *host);
#endif
