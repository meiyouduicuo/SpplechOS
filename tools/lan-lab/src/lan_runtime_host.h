#ifndef SPPLE_LAN_RUNTIME_HOST_H
#define SPPLE_LAN_RUNTIME_HOST_H
#include "lan_host.h"
/* Host runtime: callbacks run on worker threads and must be thread-safe.
 * opened() returns 0 only after taking socket ownership; changed() publishes
 * room changes. No callback may stop or destroy this object. */
typedef struct spple_runtime_host spple_runtime_host;
typedef void (*spple_runtime_host_status_fn)(void *context,int published);
typedef int (*spple_runtime_host_opened_fn)(void *context,intptr_t socket);
typedef void (*spple_runtime_host_changed_fn)(void *context,const spple_ldn_network_info *room);
spple_runtime_host *spple_runtime_host_start(uint64_t title,const char *name,const void *key,size_t key_size,
 const spple_ldn_network_info *room,spple_room_random_fn random,spple_runtime_host_status_fn status,
 spple_runtime_host_opened_fn opened,spple_runtime_host_changed_fn changed,void *context);
int spple_runtime_host_update(spple_runtime_host *host,const spple_ldn_network_info *room);
int spple_runtime_host_snapshot(spple_runtime_host *host,spple_ldn_network_info *room);
int spple_runtime_host_station_lost(spple_runtime_host *host);
void spple_runtime_host_stop(spple_runtime_host *host);
void spple_runtime_host_destroy(spple_runtime_host *host);
#endif
