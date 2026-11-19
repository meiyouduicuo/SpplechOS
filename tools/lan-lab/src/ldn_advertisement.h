#ifndef SPPLE_LDN_ADVERTISEMENT_H
#define SPPLE_LDN_ADVERTISEMENT_H

#include "ldn_abi.h"
#include <stddef.h>
#include <stdint.h>

/* Experimental same-architecture control record. This is not Switch radio
 * wire format. Callers must authenticate the stream before trusting a record. */
int spple_ldn_advertisement_encode(uint64_t title_id, const spple_ldn_network_info *network,
                                   void *output, size_t capacity, size_t *size_out);
/* Returns 1 when matching, 0 when filtered out, -1 for malformed data. */
int spple_ldn_advertisement_decode(uint64_t title_id, const void *data, size_t size,
                                   const spple_ldn_scan_filter *filter, spple_ldn_network_info *out);

#endif
