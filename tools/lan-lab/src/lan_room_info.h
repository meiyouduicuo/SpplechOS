#ifndef SPPLE_LAN_ROOM_INFO_H
#define SPPLE_LAN_ROOM_INFO_H
#include "ldn_abi.h"
#include <stdint.h>
/* The room record is the little-endian Horizon ABI, versioned by SPLC v1.
 * This experimental operation requires a previously established session;
 * it does not authenticate the sender and must not be exposed on untrusted Wi-Fi. */
int spple_room_info_send(intptr_t socket, uint64_t title, const uint8_t session[16], const spple_ldn_network_info *info);
int spple_room_info_receive(intptr_t socket, uint64_t title, const uint8_t session[16], spple_ldn_network_info *out);
#endif
