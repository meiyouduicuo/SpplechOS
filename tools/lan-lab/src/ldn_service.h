#ifndef SPPLE_LDN_SERVICE_H
#define SPPLE_LDN_SERVICE_H
#include "ldn_abi.h"
#include "hle_lan_backend.h"
#include <stddef.h>
#include <stdint.h>
/* Prototype seam. start_create / start_join must copy all pointed-to data
 * before return, initiate real discovery/connection and later call complete.
 * Security config is secret: do not log it. signal must not reenter service. */
typedef struct {
 int (*random)(void *out,size_t size);
 int (*start_create)(uint64_t token,const spple_ldn_network_info *room,const void *security);
 int (*start_join)(uint64_t token,const spple_ldn_network_info *room,const void *security,const void *user,int version,int option);
 void (*stop_transport)(void);
 void (*attach)(void *event);
 void (*signal)(void);
 /* Optional, synchronous. Must copy and must not reenter this service. */
 int (*update_room)(const spple_ldn_network_info *room);
 /* Optional: start asynchronous discovery after station opens. */
 int (*start_scan)(void);
 /* Optional: leave a joined network without stopping station discovery. */
 void (*disconnect)(void);
 /* Optional: disconnect one connected station by guest IPv4 address. */
 int (*reject)(uint32_t address);
} spple_ldn_service_ops;
/* One instance per game framework, valid until all threads stop. */
const dm_lan_backend *spple_ldn_service_setup(const spple_ldn_service_ops *ops,int64_t default_id);
int spple_ldn_service_complete(uint64_t token,int success,const spple_ldn_network_info *room);
int spple_ldn_service_discover(const spple_ldn_network_info *room);
int spple_ldn_service_forget(const uint8_t session[16]);
int spple_ldn_service_lost(void);
int spple_ldn_service_update(const spple_ldn_network_info *room);
uint32_t spple_ldn_service_policy(int policy);
int spple_ldn_service_disconnect_reason(void);
#endif
