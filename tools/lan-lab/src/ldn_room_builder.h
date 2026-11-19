#ifndef SPPLE_LDN_ROOM_BUILDER_H
#define SPPLE_LDN_ROOM_BUILDER_H
#include "ldn_abi.h"
/* Experimental room record builder, not a security handshake. entropy must be
 * 32 cryptographically random bytes from the platform; default_communication_id
 * is used only when the game requests -1. Never transmit a security password. */
int spple_ldn_build_room(const spple_ldn_network_config *config,const spple_ldn_user_config *user,
                          int64_t default_communication_id,const uint8_t entropy[32],
                          const uint8_t owner_ip[4],spple_ldn_network_info *out);
/* Update only after the transport has accepted the station. Two-peer
 * experiment: the station is slot 1 and the caller supplies its address. */
int spple_ldn_room_add_station(const spple_ldn_network_info *room,const spple_ldn_user_config *user,
                                int local_version,const uint8_t station_ip[4],const uint8_t mac_random[6],
                                spple_ldn_network_info *out);
int spple_ldn_room_remove_station(const spple_ldn_network_info *room,spple_ldn_network_info *out);
#endif
