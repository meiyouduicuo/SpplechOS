#ifndef SPPLE_LAN_AUTH_H
#define SPPLE_LAN_AUTH_H
#include <stddef.h>
#include <stdint.h>
/* Platform HMAC-SHA256. Secret material is never logged. */
int spple_lan_hmac(const void *key,size_t key_size,const void *data,size_t data_size,uint8_t out[32]);
int spple_lan_tag_equal(const uint8_t a[32],const uint8_t b[32]);
#endif
