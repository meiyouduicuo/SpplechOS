#ifndef SPPLE_LAN_FRAME_H
#define SPPLE_LAN_FRAME_H

#include <stddef.h>
#include <stdint.h>

/* Prototype control stream only. A single reader and writer own each socket.
 * On any error the caller must close the stream; a partial frame cannot be retried.
 * This transport does not implement LDN, device discovery, or guest sockets. */
#define SPPLE_LAN_MAX_FRAME (1024u * 1024u)

enum spple_lan_result {
    SPPLE_LAN_OK = 0,
    SPPLE_LAN_IO_ERROR = -1,
    SPPLE_LAN_TOO_LARGE = -2,
    SPPLE_LAN_INVALID = -3,
};

int spple_lan_send_frame(intptr_t socket_handle, const void *data, size_t size);
int spple_lan_receive_frame(intptr_t socket_handle, void *data, size_t capacity, size_t *size_out);
typedef int (*spple_lan_cancel_fn)(void *context);
int spple_lan_send_frame_cancel(intptr_t socket_handle, const void *data, size_t size,
                                spple_lan_cancel_fn cancelled, void *context);
int spple_lan_receive_frame_cancel(intptr_t socket_handle, void *data, size_t capacity, size_t *size_out,
                                   spple_lan_cancel_fn cancelled, void *context);

#endif
