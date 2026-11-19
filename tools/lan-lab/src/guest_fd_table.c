#include "guest_fd_table.h"
#include <stdlib.h>
#include <string.h>

typedef struct { int kind, closing; unsigned refs; uint64_t generation; void *object; } entry;
struct spple_fd_table {
    entry entries[SPPLE_GUEST_FD_LIMIT];
    uint64_t generation;
    spple_fd_destroy_callback destroy;
    void *context;
};

static void dispose(spple_fd_table *t, entry *e) {
    if (t->destroy) t->destroy(t->context, e->kind, e->object);
    memset(e, 0, sizeof(*e));
}

spple_fd_table *spple_fd_table_create(spple_fd_destroy_callback destroy, void *context) {
    spple_fd_table *t = calloc(1, sizeof(*t));
    if (t) { t->destroy = destroy; t->context = context; }
    return t;
}

int spple_fd_table_destroy(spple_fd_table *t) {
    if (!t) return -1;
    for (int i = 0; i < SPPLE_GUEST_FD_LIMIT; ++i) if (t->entries[i].refs) return -1;
    for (int i = 0; i < SPPLE_GUEST_FD_LIMIT; ++i) if (t->entries[i].kind) dispose(t, &t->entries[i]);
    free(t);
    return 0;
}

int spple_fd_alloc(spple_fd_table *t, int kind, void *object) {
    if (!t || kind <= 0 || !object || t->generation == UINT64_MAX) return -1;
    for (int i = 0; i < SPPLE_GUEST_FD_LIMIT; ++i) {
        entry *e = &t->entries[i];
        if (!e->kind) {
            e->kind = kind; e->object = object; e->generation = ++t->generation;
            return i;
        }
    }
    return -1;
}

int spple_fd_acquire(spple_fd_table *t, int fd, int expected_kind, spple_fd_borrow *out) {
    if (!t || !out || fd < 0 || fd >= SPPLE_GUEST_FD_LIMIT || expected_kind < 0) return -1;
    entry *e = &t->entries[fd];
    if (!e->kind || e->closing || (expected_kind && expected_kind != e->kind) || e->refs == UINT32_MAX) return -1;
    ++e->refs;
    out->fd = fd; out->generation = e->generation; out->object = e->object;
    return 0;
}

int spple_fd_release(spple_fd_table *t, spple_fd_borrow *b) {
    if (!t || !b || b->fd < 0 || b->fd >= SPPLE_GUEST_FD_LIMIT) return -1;
    entry *e = &t->entries[b->fd];
    if (!e->kind || !e->refs || e->generation != b->generation || e->object != b->object) return -1;
    --e->refs;
    if (!e->refs && e->closing) dispose(t, e);
    memset(b, 0, sizeof(*b));
    return 0;
}

int spple_fd_close(spple_fd_table *t, int fd) {
    if (!t || fd < 0 || fd >= SPPLE_GUEST_FD_LIMIT) return -1;
    entry *e = &t->entries[fd];
    if (!e->kind || e->closing) return -1;
    e->closing = 1;
    if (!e->refs) dispose(t, e);
    return 0;
}
