#include "lan_io.h"
#include "lan_send_queue.h"
#include "lan_datagram.h"
#include "ldn_advertisement.h"
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <winsock2.h>
#define IO_SHUT(s) shutdown((SOCKET)(s),SD_BOTH)
#else
#include <sys/socket.h>
#define IO_SHUT(s) shutdown((int)(s),SHUT_RDWR)
#endif
struct spple_lan_io {
 spple_lan_tunnel tunnel; spple_send_queue *queue; pthread_t reader,writer;
 int reader_started,writer_started,joined; _Atomic int stopped;
 spple_lan_ingest_callback ingest; spple_lan_room_callback room; spple_lan_io_failure_fn failure; void *context;
};
static void fail_io(spple_lan_io *io,int notify) {
 if(!atomic_exchange(&io->stopped,1)) {
  spple_send_queue_stop(io->queue); (void)IO_SHUT(io->tunnel.socket);
  if(notify && io->failure)io->failure(io->context);
 }
}
static int is_stopped(void *p) { return atomic_load(&((spple_lan_io *)p)->stopped); }
static void *write_loop(void *p) {
 spple_lan_io *io=p;void *packet;size_t size;
 while(!spple_send_queue_take(io->queue,&packet,&size)) {
  int rc=-1;uint8_t *bytes=packet;
  if(size && bytes[0]==1)rc=spple_lan_tunnel_send_cancel(&io->tunnel,bytes+1,size-1,is_stopped,io);
  else if(size==1+sizeof(spple_ldn_network_info) && bytes[0]==2){
   spple_ldn_network_info info;memcpy(&info,bytes+1,sizeof info);
   uint8_t frame[SPPLE_PROTOCOL_HEADER+sizeof info];size_t n;
   rc=spple_ldn_advertisement_encode(io->tunnel.title_id,&info,frame,sizeof frame,&n);
   if(!rc)rc=spple_lan_send_frame_cancel(io->tunnel.socket,frame,n,is_stopped,io);
  }
  spple_send_queue_free_packet(packet);
  if(rc){fail_io(io,1);break;}
 }
 if (!atomic_load(&io->stopped)) fail_io(io,1);
 return NULL;
}
static void *read_loop(void *p) {
 spple_lan_io *io=p;
 while(!atomic_load(&io->stopped)) if(spple_lan_tunnel_pump_events(&io->tunnel,io->ingest,io->room,io->context,is_stopped,io)) {fail_io(io,1);break;}
 return NULL;
}
spple_lan_io *spple_lan_io_start(intptr_t socket,uint64_t title,const uint8_t session[16],spple_lan_ingest_callback ingest,spple_lan_io_failure_fn failure,void *context) {
 return spple_lan_io_start_ex(socket,title,session,ingest,NULL,failure,context);
}
spple_lan_io *spple_lan_io_start_ex(intptr_t socket,uint64_t title,const uint8_t session[16],spple_lan_ingest_callback ingest,spple_lan_room_callback room,spple_lan_io_failure_fn failure,void *context) {
 if(!ingest)return NULL;spple_lan_io *io=calloc(1,sizeof(*io));if(!io)return NULL;
 if(spple_lan_tunnel_init(&io->tunnel,socket,title,session)) {free(io);return NULL;}
 io->queue=spple_send_queue_new(128,2*1024*1024);if(!io->queue){free(io);return NULL;}
 io->ingest=ingest;io->room=room;io->failure=failure;io->context=context;atomic_init(&io->stopped,0);
 if(pthread_create(&io->writer,NULL,write_loop,io))goto error;io->writer_started=1;
 if(pthread_create(&io->reader,NULL,read_loop,io))goto error;io->reader_started=1;
 return io;
error:
 fail_io(io,0);if(io->writer_started)pthread_join(io->writer,NULL);if(io->reader_started)pthread_join(io->reader,NULL);
 spple_send_queue_destroy(io->queue);free(io);return NULL;
}
int spple_lan_io_send(void *context,const void *packet,size_t size) {
 spple_lan_io *io=context;
 if(!io || atomic_load(&io->stopped) || !packet || size>SPPLE_DATAGRAM_HEADER+SPPLE_DATAGRAM_MAX_PAYLOAD)return -1;
 uint8_t *payload=malloc(size+1);if(!payload)return -1;payload[0]=1;memcpy(payload+1,packet,size);
 int rc=spple_send_queue_put(io->queue,payload,size+1);free(payload);return rc;
}
int spple_lan_io_send_room(spple_lan_io *io,const spple_ldn_network_info *room){
 if(!io || atomic_load(&io->stopped) || !room || spple_ldn_validate_network(room) || memcmp(room->network_id.session_id,io->tunnel.session_id,16))return -1;
 uint8_t payload[1+sizeof(*room)];payload[0]=2;memcpy(payload+1,room,sizeof(*room));return spple_send_queue_put(io->queue,payload,sizeof payload);
}
void spple_lan_io_stop(spple_lan_io *io) {
 if(!io || io->joined)return;fail_io(io,0);
 if(io->reader_started)pthread_join(io->reader,NULL);if(io->writer_started)pthread_join(io->writer,NULL);io->joined=1;
}
void spple_lan_io_destroy(spple_lan_io *io) {if(!io)return;spple_lan_io_stop(io);spple_send_queue_destroy(io->queue);free(io);}
