#include "lan_room_listener.h"
#include "lan_frame.h"
#include "lan_handshake.h"
#include "lan_protocol.h"
#include "lan_room_info.h"
#include <string.h>
int spple_room_listener_handle(intptr_t fd,uint64_t title,const spple_ldn_network_info *room,const void *key,size_t key_size,spple_room_random_fn random,spple_join_accept_fn accept,void *context) {
 if(!title || !room || spple_ldn_validate_network(room) || !key || key_size<16 || key_size>64 || !random || !accept)return -1;
 const uint8_t *session=room->network_id.session_id;uint8_t buf[SPPLE_PROTOCOL_HEADER+128];size_t n=0;spple_message msg;
 if(spple_room_server_handshake(fd,title,session) || spple_lan_receive_frame(fd,buf,sizeof buf,&n) || spple_protocol_decode(buf,n,&msg) ||
    msg.title_id!=title || memcmp(msg.session_id,session,16))return -1;
 if(msg.kind==SPPLE_MSG_ADVERTISE && !msg.body_size)
  return spple_room_info_send(fd,title,session,room) ? -1 : 1;
 if(msg.kind!=SPPLE_MSG_JOIN)return -1;
 uint8_t nonce[16];if(random(context,nonce,sizeof nonce))return -1;
 return spple_secure_join_server_after_request(fd,title,key,key_size,nonce,room,msg.body,msg.body_size,accept,context)?-1:2;
}
