#ifndef SPPLE_LAN_IO_H
#define SPPLE_LAN_IO_H
#include "lan_tunnel.h"
#include <stddef.h>
#include <stdint.h>
typedef struct spple_lan_io spple_lan_io;
typedef void (*spple_lan_io_failure_fn)(void *context);
/* Takes exclusive read/write use of an already handshaken stream, but not its
 * close ownership. Caller configures socket timeouts / SO_NOSIGPIPE. Failure
 * callback runs on a worker and must not call stop or free the object. */
spple_lan_io *spple_lan_io_start(intptr_t socket,uint64_t title,const uint8_t session[16],
 spple_lan_ingest_callback ingest,spple_lan_io_failure_fn failure,void *context);
spple_lan_io *spple_lan_io_start_ex(intptr_t socket,uint64_t title,const uint8_t session[16],
 spple_lan_ingest_callback ingest,spple_lan_room_callback room,spple_lan_io_failure_fn failure,void *context);
/* Nonblocking bounded enqueue, usable as vudp's send callback. */
int spple_lan_io_send(void *context,const void *packet,size_t size);
int spple_lan_io_send_room(spple_lan_io *io,const spple_ldn_network_info *room);
/* External thread only: shuts down (but does not close) socket and joins both
 * workers. After stop, the instance may be destroyed. Not safe concurrently. */
void spple_lan_io_stop(spple_lan_io *io);
void spple_lan_io_destroy(spple_lan_io *io);
#endif
