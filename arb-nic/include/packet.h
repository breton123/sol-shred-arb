#ifndef ARB_NIC_PACKET_H
#define ARB_NIC_PACKET_H

#include <stdint.h>
#include <time.h>

/*
 * Synthetic benchmark datagram. Later this is replaced by Solana shreds.
 *
 * UDP payload layout:
 *   [struct test_packet][padding to --size]
 *
 * --size is the full UDP payload, not header + extra.
 * Default 1200 approximates a Solana shred-sized packet.
 *
 * Multi-byte fields are stored in network byte order on the wire.
 */

#define TEST_PACKET_DEFAULT_SIZE 1200u
#define TEST_PACKET_DEFAULT_PORT 9000u
#define TEST_PACKET_MAX_SIZE     65507u /* IPv4 UDP payload limit */

struct test_packet {
    uint64_t sequence;
    uint64_t send_ns;
};

_Static_assert(sizeof(struct test_packet) == 16, "test_packet must stay 16 bytes");

#define TEST_PACKET_MIN_SIZE ((uint32_t)sizeof(struct test_packet))

/* ---- wire endian helpers ------------------------------------------------ */

static inline uint64_t host_to_net_u64(uint64_t x)
{
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return __builtin_bswap64(x);
#else
    return x;
#endif
}

static inline uint64_t net_to_host_u64(uint64_t x)
{
    return host_to_net_u64(x);
}

/* ---- timing -------------------------------------------------------------
 *
 * now_ns(): CLOCK_MONOTONIC_RAW for the on-wire send_ns stamp and e2e latency.
 * That interval is sender userspace -> receiver userspace. NOT NIC latency.
 *
 * rdtscp(): serialized TSC for intra-process stage timing (syscall vs handle).
 * Calibrate against now_ns() at startup; do not treat TSC as a wall clock
 * across machines or as a substitute for hardware RX timestamps.
 *
 * Later additions (not in this file yet):
 *   kernel RX timestamp
 *   hardware RX timestamp
 */

static inline uint64_t now_ns(void)
{
    struct timespec ts;

    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

#if defined(__x86_64__) || defined(__i386__)
#include <x86intrin.h>
#endif

static inline uint64_t rdtscp(void)
{
#if defined(__x86_64__) || defined(__i386__)
    unsigned int aux;
    return (uint64_t)__rdtscp(&aux);
#else
    return now_ns();
#endif
}

struct tsc_clock {
    double hz;
};

static inline int tsc_calibrate(struct tsc_clock *c)
{
    struct timespec ts = { .tv_sec = 0, .tv_nsec = 50000000L };
    uint64_t t0, t1, ns0, ns1;

    t0 = rdtscp();
    ns0 = now_ns();
    clock_nanosleep(CLOCK_MONOTONIC, 0, &ts, NULL);
    t1 = rdtscp();
    ns1 = now_ns();
    if (t1 <= t0 || ns1 <= ns0) {
        return -1;
    }
    c->hz = (double)(t1 - t0) * 1e9 / (double)(ns1 - ns0);
    return 0;
}

static inline uint64_t tsc_to_ns(const struct tsc_clock *c, uint64_t cyc)
{
    if (c->hz <= 0.0) {
        return 0;
    }
    return (uint64_t)((double)cyc * 1e9 / c->hz);
}

#endif /* ARB_NIC_PACKET_H */
