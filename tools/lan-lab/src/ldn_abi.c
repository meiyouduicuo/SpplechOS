#include "ldn_abi.h"
#include <string.h>

/* Validate bounds before copying data received over the network into a guest.
 * Do not infer successful LDN connection from a structurally valid record. */
int spple_ldn_validate_network(const spple_ldn_network_info *network) {
    if (!network || network->node_count_max < 1 || network->node_count_max > 8 ||
        network->node_count > (uint8_t)network->node_count_max || network->advertise_size > 0x180 ||
        network->common.ssid.length > 32) return -1;
    if (network->common.ssid.text[network->common.ssid.length] != '\0') return -1;
    unsigned connected = 0;
    for (unsigned i = 0; i < 8; ++i) {
        if (network->nodes[i].connected > 1) return -1;
        connected += network->nodes[i].connected;
    }
    return connected == network->node_count ? 0 : -1;
}

int spple_ldn_scan_matches(const spple_ldn_network_info *n, const spple_ldn_scan_filter *f) {
    if (!f || spple_ldn_validate_network(n) || (f->flags & ~UINT32_C(0x3f))) return -1;
    if ((f->flags & 1) && f->network_id.intent.local_communication_id != n->network_id.intent.local_communication_id) return 0;
    if ((f->flags & 2) && memcmp(f->network_id.session_id, n->network_id.session_id, 16)) return 0;
    if ((f->flags & 4) && f->network_type != n->common.network_type) return 0;
    if ((f->flags & 8) && memcmp(f->bssid.bytes, n->common.bssid.bytes, 6)) return 0;
    if (f->flags & 16) {
        if (f->ssid.length > 32 || f->ssid.text[f->ssid.length] != '\0') return -1;
        if (f->ssid.length != n->common.ssid.length || memcmp(f->ssid.text, n->common.ssid.text, f->ssid.length)) return 0;
    }
    if ((f->flags & 32) && f->network_id.intent.scene_id != n->network_id.intent.scene_id) return 0;
    return 1;
}
