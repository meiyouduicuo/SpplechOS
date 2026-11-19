#ifndef SPPLE_LAN_CONNECT_H
#define SPPLE_LAN_CONNECT_H
#include <stdint.h>
/* Numeric IPv4 only: the scanner resolves Bonjour asynchronously. Connect
 * timeout is 1..30000 ms. Returns an owned TCP socket with
 * bounded send/receive timeouts and SO_NOSIGPIPE on Apple. */
int spple_lan_connect(const char *host,uint16_t port,unsigned timeout_ms,intptr_t *socket_out);
void spple_lan_socket_close(intptr_t socket);
#endif
