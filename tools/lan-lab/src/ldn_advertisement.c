#include "ldn_advertisement.h"
#include "lan_protocol.h"

#include <string.h>

static int all_zero(const uint8_t *data, size_t size) {
    uint8_t any = 0;
    for (size_t i = 0; i < size; ++i) any |= data[i];
    return any == 0;
}

int spple_ldn_advertisement_encode(uint64_t title_id, const spple_ldn_network_info *network,
                                   void *output, size_t capacity, size_t *size_out) {
    if (!network || spple_ldn_validate_network(network) || all_zero(network->network_id.session_id, 16)) return -1;
    /* Never send guest padding, unconnected node bytes or string tails. */
    spple_ldn_network_info clean = {0};
    clean.network_id.intent.local_communication_id = network->network_id.intent.local_communication_id;
    clean.network_id.intent.scene_id = network->network_id.intent.scene_id;
    memcpy(clean.network_id.session_id, network->network_id.session_id, 16);
    clean.common.bssid = network->common.bssid;
    clean.common.ssid.length = network->common.ssid.length;
    memcpy(clean.common.ssid.text, network->common.ssid.text, network->common.ssid.length);
    clean.common.channel = network->common.channel;
    clean.common.link_level = network->common.link_level;
    clean.common.network_type = network->common.network_type;
    memcpy(clean.server_random, network->server_random, sizeof clean.server_random);
    clean.security_mode = network->security_mode; clean.accept_policy = network->accept_policy;
    clean.version = network->version; clean.node_count_max = network->node_count_max; clean.node_count = network->node_count;
    for (unsigned i = 0; i < 8; ++i) if (network->nodes[i].connected) {
        const spple_ldn_node_info *src = &network->nodes[i];
        spple_ldn_node_info *dst = &clean.nodes[i];
        const char *end = memchr(src->user_name, '\0', sizeof src->user_name);
        if (!end) return -1;
        memcpy(dst->ipv4, src->ipv4, sizeof dst->ipv4); dst->mac = src->mac;
        dst->node_id = src->node_id; dst->connected = 1;
        memcpy(dst->user_name, src->user_name, (size_t)(end - src->user_name));
        dst->platform = src->platform; dst->local_version = src->local_version;
    }
    clean.advertise_size = network->advertise_size;
    memcpy(clean.advertise_data, network->advertise_data, network->advertise_size);
    spple_message msg = { .kind = SPPLE_MSG_ADVERTISE, .title_id = title_id,
                          .body = (const uint8_t *)&clean, .body_size = sizeof clean };
    memcpy(msg.session_id, clean.network_id.session_id, 16);
    return spple_protocol_encode(&msg, output, capacity, size_out);
}

int spple_ldn_advertisement_decode(uint64_t title_id, const void *data, size_t size,
                                   const spple_ldn_scan_filter *filter, spple_ldn_network_info *out) {
    if (!title_id || !out || !filter) return -1;
    spple_message msg;
    if (spple_protocol_decode(data, size, &msg) || msg.kind != SPPLE_MSG_ADVERTISE ||
        msg.title_id != title_id || msg.body_size != sizeof(*out) || all_zero(msg.session_id, 16)) return -1;
    spple_ldn_network_info record;
    memcpy(&record, msg.body, sizeof(record));
    if (memcmp(msg.session_id, record.network_id.session_id, 16) || spple_ldn_validate_network(&record)) return -1;
    int match = spple_ldn_scan_matches(&record, filter);
    if (match == 1) memcpy(out, &record, sizeof(*out));
    return match;
}
