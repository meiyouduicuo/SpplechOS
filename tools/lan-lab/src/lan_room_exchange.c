#include "lan_room_exchange.h"
#include "lan_frame.h"
#include "lan_handshake.h"
#include "lan_protocol.h"
#include "lan_room_info.h"
#include <string.h>
int spple_room_exchange_client(intptr_t socket,uint64_t title,int mode,spple_ldn_network_info *out) {
 if(!out || (mode!=SPPLE_ROOM_PROBE && mode!=SPPLE_ROOM_JOIN))return -1;
 uint8_t session[16],buffer[SPPLE_PROTOCOL_HEADER];size_t len=0;spple_ldn_network_info candidate;
 if(spple_room_client_handshake(socket,title,session))return -1;
 spple_message msg={.kind=mode==SPPLE_ROOM_PROBE?SPPLE_MSG_ADVERTISE:SPPLE_MSG_JOIN,.title_id=title};
 memcpy(msg.session_id,session,16);
 if(spple_protocol_encode(&msg,buffer,sizeof(buffer),&len) || spple_lan_send_frame(socket,buffer,len) ||
    spple_room_info_receive(socket,title,session,&candidate))return -1;
 *out=candidate;return 0;
}
int spple_room_exchange_server(intptr_t socket,uint64_t title,const spple_ldn_network_info *room,int *mode_out) {
 if(!room || !mode_out || spple_ldn_validate_network(room))return -1;
 uint8_t buffer[SPPLE_PROTOCOL_HEADER];size_t len=0;spple_message msg;
 if(spple_room_server_handshake(socket,title,room->network_id.session_id) ||
    spple_lan_receive_frame(socket,buffer,sizeof(buffer),&len) || spple_protocol_decode(buffer,len,&msg) ||
    msg.title_id!=title || memcmp(msg.session_id,room->network_id.session_id,16) || msg.body_size ||
    (msg.kind!=SPPLE_MSG_ADVERTISE && msg.kind!=SPPLE_MSG_JOIN))return -1;
 int mode=msg.kind==SPPLE_MSG_JOIN?SPPLE_ROOM_JOIN:SPPLE_ROOM_PROBE;
 if(spple_room_info_send(socket,title,room->network_id.session_id,room))return -1;
 *mode_out=mode;return 0;
}
