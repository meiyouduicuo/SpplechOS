#include "ldn_state.h"

/* Return -1 for invalid state or a stale completion; 0 for accepted calls.
 * Transport completion is explicit: a room is never reported created merely
 * because the caller requested it. A finalized instance rejects old callbacks. */
int spple_ldn_init(spple_ldn *l) {
    if (!l || l->state != SPPLE_LDN_NONE || l->pending) return -1;
    l->state = SPPLE_LDN_INITIALIZED;
    ++l->generation;
    return 0;
}

int spple_ldn_begin(spple_ldn *l, spple_ldn_operation op, uint64_t *token) {
    if (!l || !token || l->pending) return -1;
    int valid = 0;
    switch (op) {
    case SPPLE_LDN_OPEN_AP: case SPPLE_LDN_OPEN_STATION: valid = l->state == SPPLE_LDN_INITIALIZED; break;
    case SPPLE_LDN_CREATE: valid = l->state == SPPLE_LDN_AP; break;
    case SPPLE_LDN_JOIN: valid = l->state == SPPLE_LDN_STATION; break;
    case SPPLE_LDN_DESTROY: valid = l->state == SPPLE_LDN_AP_CREATED; break;
    case SPPLE_LDN_DISCONNECT: valid = l->state == SPPLE_LDN_STATION_CONNECTED; break;
    case SPPLE_LDN_CLOSE_AP: valid = l->state == SPPLE_LDN_AP || l->state == SPPLE_LDN_AP_CREATED; break;
    case SPPLE_LDN_CLOSE_STATION: valid = l->state == SPPLE_LDN_STATION || l->state == SPPLE_LDN_STATION_CONNECTED; break;
    default: break;
    }
    if (!valid) return -1;
    l->pending = 1;
    l->pending_op = op;
    *token = ++l->generation;
    return 0;
}

int spple_ldn_complete(spple_ldn *l, uint64_t token, int success) {
    if (!l || !l->pending || token != l->generation) return -1;
    spple_ldn_operation op = l->pending_op;
    l->pending = 0;
    if (!success) return 0;
    switch (op) {
    case SPPLE_LDN_OPEN_AP: case SPPLE_LDN_DESTROY: l->state = SPPLE_LDN_AP; break;
    case SPPLE_LDN_CREATE: l->state = SPPLE_LDN_AP_CREATED; break;
    case SPPLE_LDN_OPEN_STATION: case SPPLE_LDN_DISCONNECT: l->state = SPPLE_LDN_STATION; break;
    case SPPLE_LDN_JOIN: l->state = SPPLE_LDN_STATION_CONNECTED; break;
    case SPPLE_LDN_CLOSE_AP: case SPPLE_LDN_CLOSE_STATION: l->state = SPPLE_LDN_INITIALIZED; break;
    default: return -1;
    }
    return 0;
}

int spple_ldn_finalize(spple_ldn *l) {
    if (!l || l->state == SPPLE_LDN_NONE) return -1;
    l->pending = 0;
    l->state = SPPLE_LDN_NONE;
    ++l->generation;
    return 0;
}

int spple_ldn_transport_lost(spple_ldn *l) {
    if (!l || (l->state != SPPLE_LDN_AP_CREATED && l->state != SPPLE_LDN_STATION_CONNECTED)) return -1;
    l->state = l->state == SPPLE_LDN_AP_CREATED ? SPPLE_LDN_AP : SPPLE_LDN_STATION;
    l->pending = 0;
    ++l->generation;
    return 0;
}
