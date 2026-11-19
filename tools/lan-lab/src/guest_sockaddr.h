#ifndef SPPLE_GUEST_SOCKADDR_H
#define SPPLE_GUEST_SOCKADDR_H
#include <stddef.h>
#include <stdint.h>
/* Switch BSD sockaddr_in: length, family, network-order port, IPv4, padding.
 * No native OS struct casts: host and guest sockaddr ABIs can differ. */
#define SPPLE_GUEST_AF_INET 2
#define SPPLE_GUEST_SOCKADDR_IN_SIZE 16
int spple_guest_sockaddr_decode(const void *address, size_t length, uint8_t ip[4], uint16_t *port);
/* Length is in/out like recvfrom: copies at most input capacity and reports 16. */
int spple_guest_sockaddr_encode(void *address, unsigned *length, const uint8_t ip[4], uint16_t port);
#endif
