#ifndef SPPLE_LAN_RETRY_H
#define SPPLE_LAN_RETRY_H

#include <stdint.h>

/* Monotonic-clock backoff for Bonjour/local network operations. There is no
 * general iOS API that distinguishes first-use prompt from user denial. */
typedef struct {
    uint64_t deadline_ms;
    uint64_t next_ms;
    unsigned failures;
} spple_lan_retry;

/* Duration and time use milliseconds from the same monotonic clock. */
void spple_lan_retry_init(spple_lan_retry *retry, uint64_t now_ms, uint64_t duration_ms);
/* Returns -1 after the deadline, otherwise schedules a bounded retry. */
int spple_lan_retry_failure(spple_lan_retry *retry, uint64_t now_ms);
/* 1: retry now, 0: wait, -1: timed out or invalid input. */
int spple_lan_retry_ready(const spple_lan_retry *retry, uint64_t now_ms);

#endif
