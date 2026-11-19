#ifndef SPPLE_GUEST_FD_TABLE_H
#define SPPLE_GUEST_FD_TABLE_H

#include <stdint.h>

/* Prototype guest descriptor space. All operations, including destructor
 * callbacks, require caller-provided synchronization. This is not yet wired to
 * nxnative's existing eventfd or socket hooks. */
#define SPPLE_GUEST_FD_LIMIT 1024
typedef struct spple_fd_table spple_fd_table;
typedef void (*spple_fd_destroy_callback)(void *context, int kind, void *object);
typedef struct { int fd; uint64_t generation; void *object; } spple_fd_borrow;

spple_fd_table *spple_fd_table_create(spple_fd_destroy_callback destroy, void *context);
/* Fails while any borrower is outstanding; no entry is changed on failure. */
int spple_fd_table_destroy(spple_fd_table *table);
int spple_fd_alloc(spple_fd_table *table, int kind, void *object);
int spple_fd_acquire(spple_fd_table *table, int fd, int expected_kind, spple_fd_borrow *out);
/* A successful release invalidates the borrow; callers must not copy borrows. */
int spple_fd_release(spple_fd_table *table, spple_fd_borrow *borrow);
int spple_fd_close(spple_fd_table *table, int fd);

#endif
