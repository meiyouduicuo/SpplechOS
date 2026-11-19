#ifndef SPPLE_LAN_CATALOG_H
#define SPPLE_LAN_CATALOG_H
#include "ldn_abi.h"
#include <stdint.h>
/* Thread-safe map from a Bonjour discovery generation to a verified probe.
 * No network or authentication is performed by this map. */
typedef struct spple_lan_catalog spple_lan_catalog;
typedef struct {char host[256];uint16_t port;uint32_t interface_index;uint64_t generation;} spple_lan_endpoint;
spple_lan_catalog *spple_lan_catalog_new(void);
void spple_lan_catalog_free(spple_lan_catalog *c);
int spple_lan_catalog_begin(spple_lan_catalog *c,uint64_t generation,uint32_t interface_index,const char *host,uint16_t port);
/* Completes only the still-live matching generation. Duplicate session IDs on
 * different active entries are rejected; callers must not guess the endpoint. */
int spple_lan_catalog_complete(spple_lan_catalog *c,uint64_t generation,const spple_ldn_network_info *room);
/* Returns 1 if an accepted room was removed, 0 if pending, -1 if absent. */
int spple_lan_catalog_remove(spple_lan_catalog *c,uint64_t generation,uint8_t session_out[16]);
int spple_lan_catalog_lookup(spple_lan_catalog *c,const uint8_t session[16],spple_lan_endpoint *out);
int spple_lan_catalog_pending(spple_lan_catalog *c,uint64_t generation);
#endif
