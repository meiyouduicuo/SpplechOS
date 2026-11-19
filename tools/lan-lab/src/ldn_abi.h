#ifndef SPPLE_LDN_ABI_H
#define SPPLE_LDN_ABI_H

#include <stddef.h>
#include <stdint.h>

/* Layout derived from the public libnx LDN header, whose license is reproduced
 * in LICENSE-libnx.txt. This is an unintegrated ABI experiment: validate it
 * against the SDK and the selected game before using it in a game hook. */
typedef struct { uint8_t bytes[6]; } spple_ldn_mac;
typedef struct { uint8_t length; char text[33]; } spple_ldn_ssid;
enum { SPPLE_LDN_NETWORK_TYPE_LOCAL_WIRELESS = 2 };
enum { SPPLE_LDN_SCAN_LOCAL_COMMUNICATION_ID = 1 << 0 };
typedef struct {
    int64_t local_communication_id;
    uint8_t reserved[2];
    uint16_t scene_id;
    uint8_t padding[4];
} spple_ldn_intent_id;
typedef struct { spple_ldn_intent_id intent; uint8_t session_id[16]; } spple_ldn_network_id;
typedef struct {
    spple_ldn_intent_id intent;
    int16_t channel;
    int8_t node_count_max;
    uint8_t reserved0;
    int16_t local_version;
    uint8_t reserved1[10];
} spple_ldn_network_config;
typedef struct { char user_name[33]; uint8_t reserved[15]; } spple_ldn_user_config;
typedef struct { uint8_t server_random[16]; uint8_t session_id[16]; } spple_ldn_security_parameter;
typedef struct {
    spple_ldn_mac bssid;
    spple_ldn_ssid ssid;
    int16_t channel;
    int8_t link_level;
    uint8_t network_type;
    uint8_t reserved[4];
} spple_ldn_common_info;
typedef struct {
    uint8_t ipv4[4];
    spple_ldn_mac mac;
    int8_t node_id;
    uint8_t connected;
    char user_name[33];
    uint8_t platform;
    int16_t local_version;
    uint8_t reserved[16];
} spple_ldn_node_info;
typedef struct {
    spple_ldn_network_id network_id;
    spple_ldn_common_info common;
    uint8_t server_random[16];
    uint16_t security_mode;
    uint8_t accept_policy;
    uint8_t version;
    uint8_t reserved0[2];
    int8_t node_count_max;
    uint8_t node_count;
    spple_ldn_node_info nodes[8];
    uint8_t reserved1[2];
    uint16_t advertise_size;
    uint8_t advertise_data[0x180];
    uint8_t reserved2[0x8c];
    uint64_t reserved3;
} spple_ldn_network_info;
typedef struct {
    spple_ldn_network_id network_id;
    uint32_t network_type;
    spple_ldn_mac bssid;
    spple_ldn_ssid ssid;
    uint8_t reserved[16];
    uint32_t flags;
} spple_ldn_scan_filter;

_Static_assert(sizeof(spple_ldn_intent_id) == 0x10, "LDN intent ABI");
_Static_assert(sizeof(spple_ldn_network_config) == 0x20, "LDN network-config ABI");
_Static_assert(sizeof(spple_ldn_user_config) == 0x30, "LDN user-config ABI");
_Static_assert(sizeof(spple_ldn_security_parameter) == 0x20, "LDN security-parameter ABI");
_Static_assert(sizeof(spple_ldn_common_info) == 0x30, "LDN common-info ABI");
_Static_assert(sizeof(spple_ldn_node_info) == 0x40, "LDN node ABI");
_Static_assert(offsetof(spple_ldn_network_info, nodes) == 0x68, "LDN node offset");
_Static_assert(offsetof(spple_ldn_network_info, advertise_data) == 0x26c, "LDN advertise offset");
_Static_assert(sizeof(spple_ldn_network_info) == 0x480, "LDN network-info ABI");
_Static_assert(sizeof(spple_ldn_scan_filter) == 0x60, "LDN scan-filter ABI");

int spple_ldn_validate_network(const spple_ldn_network_info *network);
/* Return 1 for a match, 0 for no match, -1 for an invalid input. */
int spple_ldn_scan_matches(const spple_ldn_network_info *network, const spple_ldn_scan_filter *filter);

#endif
