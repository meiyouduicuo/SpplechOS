#include "lan_send_queue.h"
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
typedef struct item { struct item *next; size_t size; unsigned char data[]; } item;
struct spple_send_queue { pthread_mutex_t mutex; pthread_cond_t cond; item *head,*tail; size_t count,bytes,max_packets,max_bytes; int stopped; };
spple_send_queue *spple_send_queue_new(size_t max_packets,size_t max_bytes) {
 if (!max_packets || !max_bytes) return NULL;
 spple_send_queue *q=calloc(1,sizeof(*q)); if(!q)return NULL;
 if (pthread_mutex_init(&q->mutex,NULL)) {free(q);return NULL;}
 if (pthread_cond_init(&q->cond,NULL)) {pthread_mutex_destroy(&q->mutex);free(q);return NULL;}
 q->max_packets=max_packets; q->max_bytes=max_bytes; return q;
}
int spple_send_queue_put(spple_send_queue *q,const void *packet,size_t size) {
 if(!q || (size && !packet) || size>SIZE_MAX-sizeof(item)) return -1;
 pthread_mutex_lock(&q->mutex);
 if(q->stopped || q->count>=q->max_packets || size>q->max_bytes-q->bytes) {pthread_mutex_unlock(&q->mutex);return -1;}
 item *n=malloc(sizeof(*n)+size); if(!n){pthread_mutex_unlock(&q->mutex);return -1;}
 n->next=NULL;n->size=size;if(size)memcpy(n->data,packet,size);
 if(q->tail)q->tail->next=n;else q->head=n;q->tail=n;q->count++;q->bytes+=size;
 pthread_cond_signal(&q->cond);pthread_mutex_unlock(&q->mutex);return 0;
}
int spple_send_queue_take(spple_send_queue *q,void **packet,size_t *size) {
 if(!q || !packet || !size)return -1; *packet=NULL;*size=0;
 pthread_mutex_lock(&q->mutex);while(!q->stopped && !q->head)pthread_cond_wait(&q->cond,&q->mutex);
 if(q->stopped){pthread_mutex_unlock(&q->mutex);return -1;}
 item *n=q->head;q->head=n->next;if(!q->head)q->tail=NULL;q->count--;q->bytes-=n->size;
 pthread_mutex_unlock(&q->mutex);
 /* Return payload with malloc ownership; allocate 1 byte for empty datagrams. */
 void *data=malloc(n->size?n->size:1);if(!data){free(n);return -1;}
 if(n->size)memcpy(data,n->data,n->size);*packet=data;*size=n->size;free(n);return 0;
}
void spple_send_queue_stop(spple_send_queue *q) {
 if(!q)return;pthread_mutex_lock(&q->mutex);q->stopped=1;item *n=q->head;
 while(n){item *next=n->next;free(n);n=next;}q->head=q->tail=NULL;q->count=q->bytes=0;
 pthread_cond_broadcast(&q->cond);pthread_mutex_unlock(&q->mutex);
}
void spple_send_queue_free_packet(void *packet) { free(packet); }
void spple_send_queue_destroy(spple_send_queue *q) {
 if(!q)return;spple_send_queue_stop(q);pthread_cond_destroy(&q->cond);pthread_mutex_destroy(&q->mutex);free(q);
}
