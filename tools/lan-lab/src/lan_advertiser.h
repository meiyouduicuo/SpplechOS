#ifndef SPPLE_LAN_ADVERTISER_H
#define SPPLE_LAN_ADVERTISER_H
#include <stdint.h>
typedef struct spple_lan_advertiser spple_lan_advertiser;
/* Single-threaded state machine; caller polls fd then calls tick. now_ms must
 * be monotonic. Initially transient permission errors are retried for 120 s. */
spple_lan_advertiser *spple_lan_advertiser_new(const char *name,uint16_t port,uint64_t now_ms);
/* 1 = published, 0 = waiting/retrying, -1 = timeout or invalid state. */
int spple_lan_advertiser_tick(spple_lan_advertiser *a,uint64_t now_ms,int readable);
int spple_lan_advertiser_fd(const spple_lan_advertiser *a);
void spple_lan_advertiser_free(spple_lan_advertiser *a);
#endif
