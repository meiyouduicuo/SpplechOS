#include "lan_secure_join.h"
#include "lan_auth.h"
#include "lan_frame.h"
#include "lan_handshake.h"
#include "lan_protocol.h"
#include "lan_room_info.h"
#include "ldn_advertisement.h"
#include <string.h>
enum { CLIENT_BODY=16+sizeof(spple_ldn_user_config)+2+1, TRANSCRIPT_SIZE=1+8+16+16+CLIENT_BODY };
static int nonzero(const uint8_t *p,size_t n){unsigned v=0;for(size_t i=0;i<n;++i)v|=p[i];return !!v;}
static int send_msg(intptr_t fd,uint64_t title,const uint8_t session[16],int kind,const void *body,unsigned size) {
 uint8_t buf[SPPLE_PROTOCOL_HEADER+CLIENT_BODY];size_t n;spple_message m={.kind=(uint8_t)kind,.title_id=title,.body=body,.body_size=size};
 memcpy(m.session_id,session,16);return spple_protocol_encode(&m,buf,sizeof buf,&n) || spple_lan_send_frame(fd,buf,n) ? -1:0;
}
static int recv_msg(intptr_t fd,uint64_t title,const uint8_t session[16],int kind,void *body,unsigned size) {
 uint8_t buf[SPPLE_PROTOCOL_HEADER+CLIENT_BODY];size_t n;spple_message m;
 if(spple_lan_receive_frame(fd,buf,sizeof buf,&n) || spple_protocol_decode(buf,n,&m) || m.title_id!=title || m.kind!=kind ||
    memcmp(m.session_id,session,16) || m.body_size!=size)return -1;
 if(size)memcpy(body,m.body,size);return 0;
}
static int proof(const void *key,size_t key_size,uint8_t role,uint64_t title,const uint8_t session[16],const uint8_t host_nonce[16],const uint8_t client[CLIENT_BODY],const spple_ldn_network_info *room,uint8_t out[32]) {
 uint8_t t[TRANSCRIPT_SIZE+sizeof(spple_ldn_network_info)];t[0]=role;for(int i=0;i<8;++i)t[1+i]=(uint8_t)(title>>(56-i*8));
 memcpy(t+9,session,16);memcpy(t+25,host_nonce,16);memcpy(t+41,client,CLIENT_BODY);
 if(room)memcpy(t+TRANSCRIPT_SIZE,room,sizeof(*room));
 return spple_lan_hmac(key,key_size,t,TRANSCRIPT_SIZE+(room?sizeof(*room):0),out);
}
int spple_secure_join_client(intptr_t fd,uint64_t title,const void *key,size_t key_size,const uint8_t nonce[16],const spple_ldn_user_config *user,int version,int option,spple_ldn_network_info *out) {
 if(!title || !key || key_size<16 || key_size>64 || !nonce || !nonzero(nonce,16) || !user || !memchr(user->user_name,0,sizeof user->user_name) || version<0 || version>0x7fff || (option&~1) || !out)return -1;
 uint8_t session[16],body[CLIENT_BODY],host[16],tag[32],expected[32],server_tag[32];spple_ldn_network_info info;
 memcpy(body,nonce,16);memcpy(body+16,user,sizeof *user);body[64]=(uint8_t)(version>>8);body[65]=(uint8_t)version;body[66]=(uint8_t)option;
 if(spple_room_client_handshake(fd,title,session) || send_msg(fd,title,session,SPPLE_MSG_JOIN,body,sizeof body) ||
    recv_msg(fd,title,session,SPPLE_MSG_ADVERTISE,host,sizeof host) || !nonzero(host,sizeof host) ||
    proof(key,key_size,'C',title,session,host,body,NULL,tag) || send_msg(fd,title,session,SPPLE_MSG_JOIN,tag,sizeof tag) ||
    recv_msg(fd,title,session,SPPLE_MSG_WELCOME,server_tag,sizeof server_tag) ||
    spple_room_info_receive(fd,title,session,&info) || proof(key,key_size,'S',title,session,host,body,&info,expected) ||
    !spple_lan_tag_equal(expected,server_tag))return -1;
 *out=info;return 0;
}
int spple_secure_join_server_after_request(intptr_t fd,uint64_t title,const void *key,size_t key_size,const uint8_t nonce[16],const spple_ldn_network_info *room,const void *request,size_t request_size,spple_join_accept_fn accept,void *context) {
 if(!title || !key || key_size<16 || key_size>64 || !nonce || !nonzero(nonce,16) || !room || spple_ldn_validate_network(room) || !accept || !request || request_size!=CLIENT_BODY)return -1;
 const uint8_t *session=room->network_id.session_id;uint8_t body[CLIENT_BODY],tag[32],expected[32],server_tag[32];spple_ldn_network_info accepted;spple_ldn_user_config user;
 memcpy(body,request,sizeof body);
 if(!nonzero(body,16) ||
    send_msg(fd,title,session,SPPLE_MSG_ADVERTISE,nonce,16) || recv_msg(fd,title,session,SPPLE_MSG_JOIN,tag,sizeof tag) ||
    proof(key,key_size,'C',title,session,nonce,body,NULL,expected) || !spple_lan_tag_equal(expected,tag))return -1;
 memcpy(&user,body+16,sizeof user);int version=((int)body[64]<<8)|body[65],option=body[66];
 if(!memchr(user.user_name,0,sizeof user.user_name) || version>0x7fff || (option&~1) ||
    accept(context,&user,version,option,&accepted) || spple_ldn_validate_network(&accepted) ||
    memcmp(accepted.network_id.session_id,session,16) || accepted.network_id.intent.local_communication_id!=room->network_id.intent.local_communication_id ||
    accepted.network_id.intent.scene_id!=room->network_id.intent.scene_id)return -1;
 uint8_t canonical[SPPLE_PROTOCOL_HEADER+sizeof accepted];size_t canonical_size;
 if(spple_ldn_advertisement_encode(title,&accepted,canonical,sizeof canonical,&canonical_size) || canonical_size!=sizeof canonical)return -1;
 memcpy(&accepted,canonical+SPPLE_PROTOCOL_HEADER,sizeof accepted);
 if(proof(key,key_size,'S',title,session,nonce,body,&accepted,server_tag) || send_msg(fd,title,session,SPPLE_MSG_WELCOME,server_tag,sizeof server_tag) ||
    spple_room_info_send(fd,title,session,&accepted))return -1;
 return 0;
}
int spple_secure_join_server(intptr_t fd,uint64_t title,const void *key,size_t key_size,const uint8_t nonce[16],const spple_ldn_network_info *room,spple_join_accept_fn accept,void *context) {
 if(!room || spple_ldn_validate_network(room))return -1;
 uint8_t body[CLIENT_BODY];const uint8_t *session=room->network_id.session_id;
 if(spple_room_server_handshake(fd,title,session) || recv_msg(fd,title,session,SPPLE_MSG_JOIN,body,sizeof body))return -1;
 return spple_secure_join_server_after_request(fd,title,key,key_size,nonce,room,body,sizeof body,accept,context);
}
