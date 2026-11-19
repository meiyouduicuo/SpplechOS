#include "lan_room_probe.h"
#include "lan_handshake.h"
#include "lan_room_info.h"
int spple_lan_room_probe_server(intptr_t socket,uint64_t title,const spple_ldn_network_info *room) {
 if(!room || spple_ldn_validate_network(room))return -1;
 if(spple_room_server_handshake(socket,title,room->network_id.session_id))return -1;
 return spple_room_info_send(socket,title,room->network_id.session_id,room);
}
int spple_lan_room_probe_client(intptr_t socket,uint64_t title,spple_ldn_network_info *out) {
 if(!out)return -1;uint8_t session[16];spple_ldn_network_info candidate;
 if(spple_room_client_handshake(socket,title,session) || spple_room_info_receive(socket,title,session,&candidate))return -1;
 *out=candidate;return 0;
}
