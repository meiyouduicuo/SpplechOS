#ifndef SPPLE_GUEST_SOCKET_BRIDGE_H
#define SPPLE_GUEST_SOCKET_BRIDGE_H
#include "guest_udp.h"
#include "hle_lan_backend.h"
/* One backend per game framework. The caller keeps g and its transport alive
 * until all guest threads and poll callbacks have stopped. Do not activate for
 * production until full socket semantics and authenticated room setup exist. */
const dm_lan_socket_backend *spple_guest_socket_bridge_init(spple_guest_udp *g);
/* Set before init; host provides its guest scheduler's blocking-boundary hook. */
int spple_guest_socket_bridge_set_wait_hook(void (*hook)(int entering));
int spple_guest_socket_bridge_ready(int fd);
/* The transport must deliver through this method, not access g concurrently. */
int spple_guest_socket_bridge_ingest(const void *packet, size_t size);
/* Wake blocked receivers during transport loss. */
void spple_guest_socket_bridge_stop(void);
/* Resume with a new virtual session; old queued packets are discarded. */
int spple_guest_socket_bridge_resume(const uint8_t local_ip[4],const uint8_t peer_ip[4]);
#endif
