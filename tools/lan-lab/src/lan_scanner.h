#ifndef SPPLE_LAN_SCANNER_H
#define SPPLE_LAN_SCANNER_H
#include <stdint.h>
/* Single owner thread calls tick. Callbacks must copy their string arguments,
 * never reenter scanner and must dispatch probing to a separate worker. */
typedef struct spple_lan_scanner spple_lan_scanner;
/* host is a numeric IPv4 address obtained asynchronously on the interface. */
typedef void (*spple_scanner_found_fn)(void *context,const char *name,uint32_t index,uint64_t generation,const char *host,uint16_t port);
typedef void (*spple_scanner_removed_fn)(void *context,const char *name,uint32_t index,uint64_t generation);
spple_lan_scanner *spple_lan_scanner_new(uint64_t now_ms,spple_scanner_found_fn found,spple_scanner_removed_fn removed,void *context);
/* 0 = scanning/retrying; -1 = timed out. fd outputs -1 when absent. */
int spple_lan_scanner_tick(spple_lan_scanner *s,uint64_t now_ms,int browse_readable,int resolve_readable);
void spple_lan_scanner_fds(const spple_lan_scanner *s,int *browse_fd,int *resolve_fd);
void spple_lan_scanner_free(spple_lan_scanner *s);
#endif
