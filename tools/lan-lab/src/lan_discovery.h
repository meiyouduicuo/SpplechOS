#ifndef SPPLE_LAN_DISCOVERY_H
#define SPPLE_LAN_DISCOVERY_H

#include <stdint.h>

/* Experimental Bonjour discovery. Each operation is owned by one caller thread.
 * Callback strings remain valid only for the duration of the callback. Poll the
 * returned fd for readability before calling process. Stop before freeing ctx. */
#define SPPLE_LAN_SERVICE_TYPE "_spplechos-ldn._tcp"
typedef struct spple_discovery spple_discovery;
typedef void (*spple_browse_callback)(void *context, int error, int added, uint32_t interface_index,
                                      const char *name, const char *type, const char *domain);
typedef void (*spple_resolve_callback)(void *context, int error, uint32_t interface_index,
                                       const char *host, uint16_t port);
typedef void (*spple_register_callback)(void *context, int error);
typedef void (*spple_address_callback)(void *context,int error,uint32_t interface_index,const uint8_t ipv4[4]);

int spple_discovery_advertise(spple_discovery **out, const char *name, uint16_t port);
int spple_discovery_advertise_observed(spple_discovery **out, const char *name, uint16_t port,
                                       spple_register_callback callback, void *context);
int spple_discovery_browse(spple_discovery **out, spple_browse_callback callback, void *context);
int spple_discovery_resolve(spple_discovery **out, uint32_t interface_index, const char *name,
                            const char *type, const char *domain, spple_resolve_callback callback, void *context);
int spple_discovery_address(spple_discovery **out,uint32_t interface_index,const char *host,spple_address_callback callback,void *context);
int spple_discovery_fd(const spple_discovery *operation);
int spple_discovery_process(spple_discovery *operation);
void spple_discovery_stop(spple_discovery *operation);

#endif
