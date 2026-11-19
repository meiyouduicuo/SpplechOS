#ifndef SPPLE_LAN_STATION_JOIN_H
#define SPPLE_LAN_STATION_JOIN_H
#include "lan_catalog.h"
#include "lan_room_listener.h"
typedef struct spple_station_join spple_station_join;
/* Callbacks run on the join worker and may not stop/destroy it. opened returns
 * 0 only after taking socket ownership; failed reports failure once. */
typedef int (*spple_station_opened_fn)(void *context,intptr_t socket,const spple_ldn_network_info *room);
typedef void (*spple_station_failed_fn)(void *context);
spple_station_join *spple_station_join_start(uint64_t title,const spple_lan_endpoint *endpoint,
 const spple_ldn_network_info *expected,const void *key,size_t key_size,const spple_ldn_user_config *user,
 int version,int option,spple_room_random_fn random,spple_station_opened_fn opened,spple_station_failed_fn failed,void *context);
/* Wait for the connection attempt and its callbacks to finish. */
void spple_station_join_wait(spple_station_join *join);
void spple_station_join_stop(spple_station_join *join);
void spple_station_join_destroy(spple_station_join *join);
#endif
