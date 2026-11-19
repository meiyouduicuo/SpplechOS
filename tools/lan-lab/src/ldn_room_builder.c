#include "ldn_room_builder.h"
#include <string.h>
int spple_ldn_build_room(const spple_ldn_network_config *config,const spple_ldn_user_config *user,
 int64_t default_id,const uint8_t entropy[32],const uint8_t ip[4],spple_ldn_network_info *out) {
 if(!config || !user || !entropy || !ip || !out || config->node_count_max<1 || config->node_count_max>8 || config->local_version<0)return -1;
 int64_t id=config->intent.local_communication_id==-1?default_id:config->intent.local_communication_id;
 unsigned session_any=0,random_any=0,ip_any=0;
 for(int i=0;i<16;++i){session_any|=entropy[i];random_any|=entropy[i+16];}
 for(int i=0;i<4;++i)ip_any|=ip[i];
 if(id<=0 || !session_any || !random_any || !ip_any || !memchr(user->user_name,0,sizeof(user->user_name)))return -1;
 spple_ldn_network_info n;memset(&n,0,sizeof(n));
 n.network_id.intent.local_communication_id=id;n.network_id.intent.scene_id=config->intent.scene_id;
 memcpy(n.network_id.session_id,entropy,16);memcpy(n.server_random,entropy+16,16);
 static const char hex[]="0123456789abcdef";n.common.ssid.length=32;
 for(int i=0;i<16;++i){n.common.ssid.text[i*2]=hex[entropy[i]>>4];n.common.ssid.text[i*2+1]=hex[entropy[i]&15];}
 memcpy(n.common.bssid.bytes,entropy+16,6);n.common.bssid.bytes[0]=(n.common.bssid.bytes[0]&0xfe)|2;
 n.common.channel=config->channel;n.common.link_level=3;
 n.common.network_type=SPPLE_LDN_NETWORK_TYPE_LOCAL_WIRELESS;
 n.security_mode=1;n.version=1;
 n.node_count_max=config->node_count_max;n.node_count=1;
 for(int i=0;i<4;++i)n.nodes[0].ipv4[i]=ip[3-i];memcpy(n.nodes[0].mac.bytes,n.common.bssid.bytes,6);
 n.nodes[0].node_id=0;n.nodes[0].connected=1;n.nodes[0].local_version=config->local_version;
 memcpy(n.nodes[0].user_name,user->user_name,sizeof(n.nodes[0].user_name));
 if(spple_ldn_validate_network(&n))return -1;*out=n;return 0;
}
int spple_ldn_room_add_station(const spple_ldn_network_info *room,const spple_ldn_user_config *user,
 int version,const uint8_t ip[4],const uint8_t random[6],spple_ldn_network_info *out) {
 if(!room || !user || !ip || !random || !out || spple_ldn_validate_network(room) ||
    room->node_count!=1 || room->node_count_max<2 || !room->nodes[0].connected || room->nodes[1].connected ||
    version<0 || version>0x7fff || !memchr(user->user_name,0,sizeof(user->user_name)))return -1;
 unsigned any=0,mac_any=0;for(int i=0;i<4;++i)any|=ip[i];for(int i=0;i<6;++i)mac_any|=random[i];
 if(!any || !mac_any || (ip[0]==room->nodes[0].ipv4[3] && ip[1]==room->nodes[0].ipv4[2] && ip[2]==room->nodes[0].ipv4[1] && ip[3]==room->nodes[0].ipv4[0]))return -1;
 spple_ldn_network_info n=*room;memset(&n.nodes[1],0,sizeof n.nodes[1]);
 for(int i=0;i<4;++i)n.nodes[1].ipv4[i]=ip[3-i];memcpy(n.nodes[1].mac.bytes,random,6);n.nodes[1].mac.bytes[0]=(n.nodes[1].mac.bytes[0]&0xfe)|2;
 if(!memcmp(n.nodes[1].mac.bytes,n.nodes[0].mac.bytes,6))return -1;
 n.nodes[1].node_id=1;n.nodes[1].connected=1;n.nodes[1].local_version=(int16_t)version;
 memcpy(n.nodes[1].user_name,user->user_name,sizeof n.nodes[1].user_name);n.node_count=2;
 if(spple_ldn_validate_network(&n))return -1;*out=n;return 0;
}
int spple_ldn_room_remove_station(const spple_ldn_network_info *room,spple_ldn_network_info *out) {
 if(!room || !out || spple_ldn_validate_network(room) || room->node_count!=2 || !room->nodes[0].connected || !room->nodes[1].connected)return -1;
 spple_ldn_network_info n=*room;memset(&n.nodes[1],0,sizeof n.nodes[1]);n.node_count=1;*out=n;return 0;
}
