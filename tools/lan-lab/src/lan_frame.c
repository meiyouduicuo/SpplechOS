#include "lan_frame.h"

#include <limits.h>
#include <string.h>

#ifdef _WIN32
#include <winsock2.h>
typedef SOCKET lan_socket;
static int interrupted(void) { return WSAGetLastError() == WSAEINTR; }
#define LAN_SEND(s, p, n) send((s), (const char *)(p), (int)(n), 0)
#define LAN_RECV(s, p, n) recv((s), (char *)(p), (int)(n), 0)
#else
#include <arpa/inet.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/select.h>
typedef int lan_socket;
static int interrupted(void) { return errno == EINTR; }
#ifdef MSG_NOSIGNAL
#define LAN_SEND(s, p, n) send((s), (p), (n), MSG_NOSIGNAL)
#else
/* Apple platforms: configure SO_NOSIGPIPE on the socket before use. */
#define LAN_SEND(s, p, n) send((s), (p), (n), 0)
#endif
#define LAN_RECV(s, p, n) recv((s), (p), (n), 0)
#endif

static int transfer_cancel(lan_socket socket, void *data, size_t size, int writing, spple_lan_cancel_fn cancelled, void *context) {
    unsigned char *bytes = (unsigned char *)data;
    while (size) {
        if (cancelled) {
            if (cancelled(context)) return SPPLE_LAN_IO_ERROR;
#ifndef _WIN32
            if (socket < 0 || socket >= FD_SETSIZE) return SPPLE_LAN_IO_ERROR;
#endif
            fd_set set; FD_ZERO(&set); FD_SET(socket,&set);
            struct timeval timeout = {0,250000};
#ifdef _WIN32
            int ready=select(0,writing?NULL:&set,writing?&set:NULL,NULL,&timeout);
#else
            int ready=select(socket+1,writing?NULL:&set,writing?&set:NULL,NULL,&timeout);
#endif
            if (!ready) continue;
            if (ready<0) { if(interrupted())continue; return SPPLE_LAN_IO_ERROR; }
        }
        size_t count = cancelled && size > 4096 ? 4096 : (size > INT_MAX ? INT_MAX : size);
        int n = writing ? (int)LAN_SEND(socket, bytes, count) : (int)LAN_RECV(socket, bytes, count);
        if (n < 0 && interrupted()) continue;
        if (n <= 0) return SPPLE_LAN_IO_ERROR;
        bytes += (size_t)n;
        size -= (size_t)n;
    }
    return SPPLE_LAN_OK;
}
int spple_lan_send_frame(intptr_t handle, const void *data, size_t size) {
    return spple_lan_send_frame_cancel(handle,data,size,NULL,NULL);
}
int spple_lan_send_frame_cancel(intptr_t handle, const void *data, size_t size,spple_lan_cancel_fn cancelled,void *context) {
    if (size > SPPLE_LAN_MAX_FRAME) return SPPLE_LAN_TOO_LARGE;
    if (size && !data) return SPPLE_LAN_INVALID;
    uint32_t length = htonl((uint32_t)size);
    if (transfer_cancel((lan_socket)handle, &length, sizeof length, 1,cancelled,context)) return SPPLE_LAN_IO_ERROR;
    return transfer_cancel((lan_socket)handle, (void *)data, size, 1,cancelled,context);
}

int spple_lan_receive_frame(intptr_t handle, void *data, size_t capacity, size_t *size_out) {
    return spple_lan_receive_frame_cancel(handle,data,capacity,size_out,NULL,NULL);
}
int spple_lan_receive_frame_cancel(intptr_t handle, void *data, size_t capacity, size_t *size_out, spple_lan_cancel_fn cancelled, void *context) {
    if (!size_out || (capacity && !data)) return SPPLE_LAN_INVALID;
    *size_out = 0;
    uint32_t length;
    if (transfer_cancel((lan_socket)handle, &length, sizeof length, 0,cancelled,context)) return SPPLE_LAN_IO_ERROR;
    size_t size = ntohl(length);
    if (size > SPPLE_LAN_MAX_FRAME || size > capacity) return SPPLE_LAN_TOO_LARGE;
    int result = transfer_cancel((lan_socket)handle, data, size, 0,cancelled,context);
    if (!result) *size_out = size;
    return result;
}
