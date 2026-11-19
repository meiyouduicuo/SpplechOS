#include "ldn_rooms.h"
#include <stdlib.h>
#include <string.h>

struct spple_ldn_rooms {
    spple_ldn ldn;
    spple_ldn_network_info entries[SPPLE_LDN_ROOMS_MAX], active;
    unsigned used[SPPLE_LDN_ROOMS_MAX];
    uint8_t selected[16];
    int64_t selected_communication_id;
    uint16_t selected_scene_id;
    int has_selected, has_active;
    uint64_t revision;
    spple_ldn_changed_fn listener;
    void *listener_context;
};
static void changed(spple_ldn_rooms *r) {
    ++r->revision;
    if (r->listener) r->listener(r->listener_context, r->revision);
}
static int nonzero(const uint8_t *p) { unsigned x = 0; for (int i = 0; i < 16; ++i) x |= p[i]; return !!x; }
static int same(const uint8_t *a, const uint8_t *b) { return memcmp(a,b,16) == 0; }
static int find(const spple_ldn_rooms *r, const uint8_t *id) {
    for (int i=0; i<SPPLE_LDN_ROOMS_MAX; ++i) if (r->used[i] && same(r->entries[i].network_id.session_id,id)) return i;
    return -1;
}
spple_ldn_rooms *spple_ldn_rooms_new(void) { return calloc(1,sizeof(spple_ldn_rooms)); }
void spple_ldn_rooms_free(spple_ldn_rooms *r) { free(r); }
int spple_ldn_rooms_init(spple_ldn_rooms *r) {
    if (!r || spple_ldn_init(&r->ldn)) return -1;
    changed(r); return 0;
}
int spple_ldn_rooms_fini(spple_ldn_rooms *r) {
    if (!r || spple_ldn_finalize(&r->ldn)) return -1;
    memset(r->used,0,sizeof r->used); r->has_active=r->has_selected=0;
    changed(r); return 0;
}
int spple_ldn_rooms_state(const spple_ldn_rooms *r) { return r ? (int)r->ldn.state : -1; }
int spple_ldn_rooms_begin(spple_ldn_rooms *r, int op, uint64_t *token) {
    if (!r || (op == SPPLE_LDN_JOIN && !r->has_selected)) return -1;
    return spple_ldn_begin(&r->ldn,(spple_ldn_operation)op,token);
}
int spple_ldn_rooms_complete(spple_ldn_rooms *r, uint64_t token, int success, const spple_ldn_network_info *info) {
    if (!r || !r->ldn.pending || r->ldn.generation != token) return -1;
    spple_ldn_operation op=r->ldn.pending_op;
    if (success && (op == SPPLE_LDN_CREATE || op == SPPLE_LDN_JOIN)) {
        if (!info || spple_ldn_validate_network(info) || !nonzero(info->network_id.session_id)) return -1;
        if (op == SPPLE_LDN_JOIN) {
            int selected = r->has_selected ? find(r, r->selected) : -1;
            if (selected < 0 || !same(r->selected,info->network_id.session_id) ||
                r->selected_communication_id != info->network_id.intent.local_communication_id ||
                r->selected_scene_id != info->network_id.intent.scene_id) return -1;
        }
    }
    spple_ldn_state old=r->ldn.state;
    if (spple_ldn_complete(&r->ldn,token,success)) return -1;
    if (success && (op == SPPLE_LDN_CREATE || op == SPPLE_LDN_JOIN)) { r->active=*info; r->has_active=1; }
    if (success && (op == SPPLE_LDN_DESTROY || op == SPPLE_LDN_DISCONNECT || op == SPPLE_LDN_CLOSE_AP || op == SPPLE_LDN_CLOSE_STATION)) r->has_active=0;
    if (r->ldn.state != old) changed(r);
    return 0;
}
int spple_ldn_rooms_put(spple_ldn_rooms *r, const spple_ldn_network_info *info) {
    if (!r || r->ldn.state == SPPLE_LDN_NONE || !info || spple_ldn_validate_network(info) || !nonzero(info->network_id.session_id)) return -1;
    int i=find(r,info->network_id.session_id);
    if (i < 0) for (int k=0; k<SPPLE_LDN_ROOMS_MAX; ++k) if (!r->used[k]) {i=k; break;}
    if (i < 0) return -1;
    int updated=!r->used[i] || memcmp(&r->entries[i],info,sizeof(*info))!=0;
    r->entries[i]=*info; r->used[i]=1;
    /* A room becoming visible is an asynchronous LDN result change even
     * though the adapter's station state remains SPPLE_LDN_STATION. Wake the
     * guest so games which wait on the LDN event can rescan immediately. */
    if(updated) changed(r);
    return 0;
}
int spple_ldn_rooms_remove(spple_ldn_rooms *r, const uint8_t id[16]) {
    if (!r || !id) return -1;
    int i=find(r,id); if (i<0) return -1;
    r->used[i]=0;
    if (r->has_selected && same(r->selected,id)) r->has_selected=0;
    changed(r);
    return 0;
}
int spple_ldn_rooms_scan(const spple_ldn_rooms *r, const spple_ldn_scan_filter *filter, spple_ldn_network_info *out, size_t cap, size_t *count) {
    if (!r || !filter || !count || (cap && !out) || (r->ldn.state != SPPLE_LDN_STATION && r->ldn.state != SPPLE_LDN_STATION_CONNECTED && r->ldn.state != SPPLE_LDN_AP_CREATED)) return -1;
    if ((filter->flags & ~UINT32_C(0x3f)) || ((filter->flags & 16) && (filter->ssid.length > 32 || filter->ssid.text[filter->ssid.length]))) return -1;
    *count=0;
    for (int i=0; i<SPPLE_LDN_ROOMS_MAX; ++i) if (r->used[i]) {
        int match=spple_ldn_scan_matches(&r->entries[i],filter); if (match<0) return -1;
        if (match && *count<cap) out[(*count)++]=r->entries[i];
    }
    return 0;
}
int spple_ldn_rooms_select(spple_ldn_rooms *r, const uint8_t id[16]) {
    if (!r || !id || r->ldn.state != SPPLE_LDN_STATION || r->ldn.pending) return -1;
    int i = find(r,id); if (i < 0) return -1;
    memcpy(r->selected,id,16);
    r->selected_communication_id=r->entries[i].network_id.intent.local_communication_id;
    r->selected_scene_id=r->entries[i].network_id.intent.scene_id;
    r->has_selected=1; return 0;
}
int spple_ldn_rooms_info(const spple_ldn_rooms *r, spple_ldn_network_info *out) {
    if (!r || !out || !r->has_active) return -1;
    *out=r->active; return 0;
}
int spple_ldn_rooms_transport_lost(spple_ldn_rooms *r) {
    if (!r || spple_ldn_transport_lost(&r->ldn)) return -1;
    r->has_active=0;
    r->has_selected=0;
    changed(r);
    return 0;
}
int spple_ldn_rooms_update_active(spple_ldn_rooms *r, const spple_ldn_network_info *info) {
    if (!r || !r->has_active || !info || spple_ldn_validate_network(info) ||
        !same(info->network_id.session_id, r->active.network_id.session_id) ||
        info->network_id.intent.local_communication_id != r->active.network_id.intent.local_communication_id ||
        info->network_id.intent.scene_id != r->active.network_id.intent.scene_id) return -1;
    if (memcmp(&r->active, info, sizeof(*info))) { r->active=*info; changed(r); }
    return 0;
}
uint64_t spple_ldn_rooms_revision(const spple_ldn_rooms *r) { return r ? r->revision : 0; }
int spple_ldn_rooms_set_listener(spple_ldn_rooms *r, spple_ldn_changed_fn listener, void *context) {
    if (!r || (!listener && context)) return -1;
    r->listener=listener; r->listener_context=context; return 0;
}
