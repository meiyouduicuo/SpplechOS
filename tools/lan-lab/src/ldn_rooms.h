#ifndef SPPLE_LDN_ROOMS_H
#define SPPLE_LDN_ROOMS_H
#include "ldn_abi.h"
#include "ldn_state.h"
#include <stddef.h>
#include <stdint.h>

/* Serialized, bounded guest-facing room catalogue. Transport owns discovery,
 * authentication and async operations. Never treats discovery as a connection. */
#define SPPLE_LDN_ROOMS_MAX 16
typedef struct spple_ldn_rooms spple_ldn_rooms;
typedef void (*spple_ldn_changed_fn)(void *context, uint64_t revision);
spple_ldn_rooms *spple_ldn_rooms_new(void);
void spple_ldn_rooms_free(spple_ldn_rooms *r);
int spple_ldn_rooms_init(spple_ldn_rooms *r);
int spple_ldn_rooms_fini(spple_ldn_rooms *r);
int spple_ldn_rooms_state(const spple_ldn_rooms *r);
int spple_ldn_rooms_begin(spple_ldn_rooms *r, int op, uint64_t *token);
/* info is required on successful CREATE/JOIN and must already be verified by
 * the transport; identity must match the one explicitly selected for JOIN. */
int spple_ldn_rooms_complete(spple_ldn_rooms *r, uint64_t token, int success,
                             const spple_ldn_network_info *info);
int spple_ldn_rooms_put(spple_ldn_rooms *r, const spple_ldn_network_info *info);
int spple_ldn_rooms_remove(spple_ldn_rooms *r, const uint8_t session_id[16]);
int spple_ldn_rooms_scan(const spple_ldn_rooms *r, const spple_ldn_scan_filter *filter,
                         spple_ldn_network_info *out, size_t cap, size_t *count);
int spple_ldn_rooms_select(spple_ldn_rooms *r, const uint8_t session_id[16]);
int spple_ldn_rooms_info(const spple_ldn_rooms *r, spple_ldn_network_info *out);
/* Reports a transport failure and invalidates any in-flight completion. */
int spple_ldn_rooms_transport_lost(spple_ldn_rooms *r);
/* Updates an active network after a peer joins or leaves. */
int spple_ldn_rooms_update_active(spple_ldn_rooms *r, const spple_ldn_network_info *info);
/* One-shot generation counter for the engine event; advances on state,
 * active-network, and discovered-room changes. */
uint64_t spple_ldn_rooms_revision(const spple_ldn_rooms *r);
/* Called synchronously after a state or active-network change. The caller must
 * serialize access and the callback must not re-enter or free this instance. */
int spple_ldn_rooms_set_listener(spple_ldn_rooms *r, spple_ldn_changed_fn listener, void *context);
#endif
