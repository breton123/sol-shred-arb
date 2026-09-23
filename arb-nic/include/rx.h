#ifndef ARB_NIC_RX_H
#define ARB_NIC_RX_H

#include "shred.h"

#include <stdint.h>

/*
 * Post-AF_XDP boundary. Every source (replay, UDP, AF_XDP) fills this
 * and calls hot_rx(). No callbacks, no vtable — the outer loop is
 * compile-time / source-specific.
 */
typedef struct {
    const uint8_t *data;
    uint16_t len;
    uint16_t queue;
} rx_packet_t;

/*
 * Future arb pipeline entry. Today: shred header → shred_view.
 * Returns 0 if the packet is a shred we can name, -1 otherwise.
 * view aliases pkt->data. No allocation.
 */
static inline int
hot_rx(rx_packet_t *pkt, shred_view_t *view)
{
    return shred_parse(pkt->data, pkt->len, view);
}

#endif /* ARB_NIC_RX_H */
