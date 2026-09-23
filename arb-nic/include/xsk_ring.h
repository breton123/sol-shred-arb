#ifndef ARB_NIC_XSK_RING_H
#define ARB_NIC_XSK_RING_H

#include <linux/if_xdp.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <unistd.h>

#ifndef SOL_XDP
#define SOL_XDP 283
#endif
#ifndef AF_XDP
#define AF_XDP 44
#endif

#define XSK_DEFAULT_RING    2048u
#define XSK_DEFAULT_FRAMES  4096u
#define XSK_DEFAULT_FRAME_SZ 2048u

struct xsk_ring {
    uint32_t cached_prod;
    uint32_t cached_cons;
    uint32_t mask;
    uint32_t size;
    uint32_t *producer;
    uint32_t *consumer;
    uint32_t *flags;
    void *descs;
    void *map;
    size_t map_len;
};

static inline void xsk_acquire(void)
{
    atomic_thread_fence(memory_order_acquire);
}

static inline void xsk_release(void)
{
    atomic_thread_fence(memory_order_release);
}

static inline int xsk_ring_map(struct xsk_ring *r, int fd, off_t pgoff,
                               const struct xdp_ring_offset *off, uint32_t n,
                               size_t desc_sz)
{
    size_t len = (size_t)off->desc + (size_t)n * desc_sz;
    void *m = mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_POPULATE, fd, pgoff);

    if (m == MAP_FAILED) {
        return -1;
    }
    r->map = m;
    r->map_len = len;
    r->producer = (uint32_t *)(void *)((uint8_t *)m + off->producer);
    r->consumer = (uint32_t *)(void *)((uint8_t *)m + off->consumer);
    r->flags = (uint32_t *)(void *)((uint8_t *)m + off->flags);
    r->descs = (uint8_t *)m + off->desc;
    r->size = n;
    r->mask = n - 1;
    r->cached_prod = 0;
    r->cached_cons = 0;
    return 0;
}

static inline void xsk_ring_unmap(struct xsk_ring *r)
{
    if (r->map != NULL && r->map != MAP_FAILED) {
        munmap(r->map, r->map_len);
    }
    r->map = NULL;
}

/* ---- consumer (RX / completion) ---------------------------------------- */

static inline uint32_t xsk_cons_peek(struct xsk_ring *r, uint32_t max, uint32_t *idx)
{
    uint32_t entries = r->cached_prod - r->cached_cons;

    if (entries == 0) {
        r->cached_prod = *r->producer;
        xsk_acquire();
        entries = r->cached_prod - r->cached_cons;
    }
    if (entries > max) {
        entries = max;
    }
    if (entries > 0) {
        *idx = r->cached_cons;
    }
    return entries;
}

static inline void xsk_cons_release(struct xsk_ring *r, uint32_t n)
{
    r->cached_cons += n;
    xsk_release();
    *r->consumer = r->cached_cons;
}

static inline const struct xdp_desc *xsk_rx_desc(const struct xsk_ring *r, uint32_t idx)
{
    return &((const struct xdp_desc *)r->descs)[idx & r->mask];
}

/* ---- producer (fill / TX) ---------------------------------------------- */

static inline uint32_t xsk_prod_reserve(struct xsk_ring *r, uint32_t want, uint32_t *idx)
{
    uint32_t free_entries = r->cached_cons - r->cached_prod;

    if (free_entries < want) {
        r->cached_cons = *r->consumer + r->size;
        free_entries = r->cached_cons - r->cached_prod;
    }
    if (free_entries < want) {
        return 0;
    }
    *idx = r->cached_prod;
    r->cached_prod += want;
    return want;
}

static inline void xsk_prod_submit(struct xsk_ring *r)
{
    xsk_release();
    *r->producer = r->cached_prod;
}

static inline void xsk_fill_addr(struct xsk_ring *r, uint32_t idx, uint64_t addr)
{
    ((uint64_t *)r->descs)[idx & r->mask] = addr;
}

#endif /* ARB_NIC_XSK_RING_H */
