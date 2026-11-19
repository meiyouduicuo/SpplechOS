#include "lan_retry.h"
#include <limits.h>

static uint64_t saturating_add(uint64_t a, uint64_t b) {
    return b > UINT64_MAX - a ? UINT64_MAX : a + b;
}

void spple_lan_retry_init(spple_lan_retry *retry, uint64_t now_ms, uint64_t duration_ms) {
    if (!retry) return;
    retry->deadline_ms = saturating_add(now_ms, duration_ms);
    retry->next_ms = now_ms;
    retry->failures = 0;
}

int spple_lan_retry_failure(spple_lan_retry *retry, uint64_t now_ms) {
    if (!retry || now_ms >= retry->deadline_ms) return -1;
    unsigned shift = retry->failures < 3 ? retry->failures : 3;
    uint64_t delay = UINT64_C(1000) << shift;
    if (retry->failures < UINT_MAX) ++retry->failures;
    retry->next_ms = saturating_add(now_ms, delay);
    if (retry->next_ms > retry->deadline_ms) retry->next_ms = retry->deadline_ms;
    return 0;
}

int spple_lan_retry_ready(const spple_lan_retry *retry, uint64_t now_ms) {
    if (!retry || now_ms >= retry->deadline_ms) return -1;
    return now_ms >= retry->next_ms ? 1 : 0;
}
