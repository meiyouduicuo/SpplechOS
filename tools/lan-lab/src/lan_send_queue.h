#ifndef SPPLE_LAN_SEND_QUEUE_H
#define SPPLE_LAN_SEND_QUEUE_H
#include <stddef.h>
/* Bounded queue between game threads and the blocking network writer.
 * stop discards pending packets and wakes the consumer. Join every producer
 * and consumer before destroy. Ownership of a taken buffer passes to caller. */
typedef struct spple_send_queue spple_send_queue;
spple_send_queue *spple_send_queue_new(size_t max_packets,size_t max_bytes);
int spple_send_queue_put(spple_send_queue *q,const void *packet,size_t size);
/* Blocks until available or stopped; return 0 for packet, -1 for stop. */
int spple_send_queue_take(spple_send_queue *q,void **packet,size_t *size);
void spple_send_queue_free_packet(void *packet);
void spple_send_queue_stop(spple_send_queue *q);
void spple_send_queue_destroy(spple_send_queue *q);
#endif
