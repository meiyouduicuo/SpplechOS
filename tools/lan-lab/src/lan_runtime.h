#ifndef SPPLE_LAN_RUNTIME_H
#define SPPLE_LAN_RUNTIME_H
#include "hle_lan_backend.h"
#include <stddef.h>
#include <stdint.h>
/* Experimental one-per-game controller. Platform functions and backend tables
 * must remain valid until all game threads and runtime workers have stopped.
 * No data path is encrypted; use only for explicitly selected local sessions. */
typedef struct {
 void *context;
 int (*reserve)(void *context);
 int (*release)(void *context,int fd);
 void (*notify)(void *context);
 void (*guest_wait)(int entering);
 void (*attach_event)(void *event);
 void (*signal_event)(void);
 int (*random)(void *context,void *output,size_t size);
} spple_runtime_platform;
typedef struct {
 const dm_lan_backend *ldn;
 const dm_lan_socket_backend *sockets;
 int (*ready)(int fd);
} spple_runtime_backends;
/* Must run once before guest threads start; no implicit registration. */
int spple_lan_runtime_init(uint64_t title,int64_t default_communication_id,const spple_runtime_platform *platform,spple_runtime_backends *out);
/* External thread only, after guest teardown has started. */
void spple_lan_runtime_stop(void);
#endif
