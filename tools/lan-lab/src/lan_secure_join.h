#ifndef SPPLE_LAN_SECURE_JOIN_H
#define SPPLE_LAN_SECURE_JOIN_H
#include "ldn_abi.h"
#include <stdint.h>
/* The host and client must provide a fresh unpredictable 16-byte nonce on
 * each attempt and a shared 16..64-byte key. Authentication uses HMAC-SHA256;
 * it does not encrypt payloads. accept must atomically check policy/capacity,
 * fill the accepted room and roll back if the subsequent stream is lost. */
typedef int (*spple_join_accept_fn)(void *context,const spple_ldn_user_config *user,int version,int option,spple_ldn_network_info *accepted);
int spple_secure_join_client(intptr_t socket,uint64_t title,const void *key,size_t key_size,const uint8_t nonce[16],
 const spple_ldn_user_config *user,int version,int option,spple_ldn_network_info *out);
int spple_secure_join_server(intptr_t socket,uint64_t title,const void *key,size_t key_size,const uint8_t nonce[16],
 const spple_ldn_network_info *room,spple_join_accept_fn accept,void *context);
/* Variant for a listener which already completed HELLO and validated that
 * the first frame is a JOIN for this title and session. */
int spple_secure_join_server_after_request(intptr_t socket,uint64_t title,const void *key,size_t key_size,const uint8_t nonce[16],
 const spple_ldn_network_info *room,const void *request,size_t request_size,spple_join_accept_fn accept,void *context);
#endif
