#ifndef ARB_FEED_FLOWRA_N_H
#define ARB_FEED_FLOWRA_N_H

#include <stdint.h>

/*
 * Race adapter — common N event for Flowra and OrbitFlare.
 *
 * First userspace observation wins:
 *   lead_ns = T_ORBITFLARE_FIRST_ACTIONABLE - T_FLOWRA_RX
 * Negative lead_ns means Flowra was first (pre-sequencing if shreds come later).
 *
 * Dedup by 64-byte signature. FIRST timestamp is the economic one.
 * This struct is the handoff to a later hot_decide. Do not call hot_decide here.
 *
 * SOURCE_FLOWRA     pending gRPC (this tree)
 * SOURCE_ORBITFLARE shred / first actionable (existing pipeline, later)
 */

#define FEED_SRC_FLOWRA      1u
#define FEED_SRC_ORBITFLARE  2u

#define FEED_N_PROTO_DLMM  1u
#define FEED_N_PROTO_PUMP  2u

#define FEED_N_TX_MAX  4096u /* TX_RECV_MAX — v1 ingress; do not use for send */

typedef struct {
    uint64_t t_rx_mono_ns; /* T_FLOWRA_RX or T_ORBITFLARE_FIRST_ACTIONABLE */
    uint64_t t_rx_tsc;
    uint64_t wall_utc_ns;
    uint8_t  source;
    uint8_t  have_n;       /* 1 = hot_decode_trigger variant recovered */
    uint8_t  protocol;     /* 1 DLMM 2 Pump */
    uint8_t  direction;
    uint8_t  sig[64];
    uint8_t  pool[32];
    uint64_t amount_in;
    uint64_t min_out;
    uint16_t tx_len;
    uint8_t  tx[FEED_N_TX_MAX];
} feed_n_t;

typedef struct {
    uint8_t  sig[64];
    uint8_t  first_source;
    uint8_t  have_second;
    uint8_t  second_source;
    uint64_t first_mono_ns;
    uint64_t second_mono_ns;
    int64_t  lead_ns; /* second - first; OF - Flowra when both present */
} feed_race_t;

#endif /* ARB_FEED_FLOWRA_N_H */
