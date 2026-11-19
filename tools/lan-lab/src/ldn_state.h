#ifndef SPPLE_LDN_STATE_H
#define SPPLE_LDN_STATE_H

#include <stdint.h>

/* Isolated prototype. State numbers follow libnx LdnState; no networking or
 * game hooks are enabled by this module. Calls must be serialized by caller. */
typedef enum {
    SPPLE_LDN_NONE = 0, SPPLE_LDN_INITIALIZED = 1, SPPLE_LDN_AP = 2,
    SPPLE_LDN_AP_CREATED = 3, SPPLE_LDN_STATION = 4,
    SPPLE_LDN_STATION_CONNECTED = 5, SPPLE_LDN_ERROR = 6
} spple_ldn_state;

typedef enum {
    SPPLE_LDN_OPEN_AP, SPPLE_LDN_OPEN_STATION, SPPLE_LDN_CREATE,
    SPPLE_LDN_JOIN, SPPLE_LDN_DESTROY, SPPLE_LDN_DISCONNECT,
    SPPLE_LDN_CLOSE_AP, SPPLE_LDN_CLOSE_STATION
} spple_ldn_operation;

typedef struct {
    spple_ldn_state state;
    spple_ldn_operation pending_op;
    uint64_t generation;
    int pending;
} spple_ldn;

int spple_ldn_init(spple_ldn *ldn);
int spple_ldn_begin(spple_ldn *ldn, spple_ldn_operation operation, uint64_t *token);
int spple_ldn_complete(spple_ldn *ldn, uint64_t token, int success);
int spple_ldn_finalize(spple_ldn *ldn);
/* Transport loss is asynchronous; invalidate outstanding completions. */
int spple_ldn_transport_lost(spple_ldn *ldn);

#endif
