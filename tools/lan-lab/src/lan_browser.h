#ifndef SPPLE_LAN_BROWSER_H
#define SPPLE_LAN_BROWSER_H
#include "lan_catalog.h"
/* Callbacks run on browser worker and must not reenter/stop it. */
typedef struct spple_lan_browser spple_lan_browser;
typedef void (*spple_browser_found_fn)(void *context,const spple_ldn_network_info *room);
typedef void (*spple_browser_removed_fn)(void *context,const uint8_t session[16]);
spple_lan_browser *spple_lan_browser_start(uint64_t title,spple_browser_found_fn found,spple_browser_removed_fn removed,void *context);
int spple_lan_browser_lookup(spple_lan_browser *browser,const uint8_t session[16],spple_lan_endpoint *out);
/* The caller owns the browser lifetime while waiting for this exact session. */
int spple_lan_browser_wait(spple_lan_browser *browser,const uint8_t session[16],spple_lan_endpoint *out);
/* External thread only; joins the worker. No callback runs after return. */
void spple_lan_browser_stop(spple_lan_browser *browser);
void spple_lan_browser_destroy(spple_lan_browser *browser);
#endif
