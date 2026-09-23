#include "packet.h"
#include "util.h"

#include <arpa/inet.h>
#include <errno.h>
#include <inttypes.h>
#include <netinet/in.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#ifndef SO_BUSY_POLL
#define SO_BUSY_POLL 46
#endif

#define DEFAULT_COUNT    1000000ULL
#define DEFAULT_BIND     "0.0.0.0"
#define DEFAULT_FIRST_MS 30000
#define DEFAULT_IDLE_MS  1000
#define DEFAULT_BATCH    32
#define MAX_BATCH        256
#define DEFAULT_BUSY_US  50

enum rx_mode {
    MODE_POLL = 0,
    MODE_BUSY,
    MODE_PERF
};

struct opts {
    uint64_t count;
    uint16_t port;
    const char *bind_ip;
    int first_ms;
    int idle_ms;
    int cpu;
    int batch;
    int busy_us;
    int busy_poll;
    int quiet;
    int do_mlock;
    uint64_t warmup;
    enum rx_mode mode;
};

struct rx_acc {
    uint64_t received;
    uint64_t unique;
    uint64_t duplicates;
    uint64_t out_of_order;
    uint64_t short_pkts;
    uint64_t expected_next;
    uint64_t count;
    uint64_t warmup;
    uint64_t *seen;
    uint64_t *lat;
    uint64_t lat_n;
    uint64_t *handle_cyc;
    uint64_t handle_n;
    uint64_t payload_bytes;
};

static const char *mode_name(enum rx_mode m)
{
    switch (m) {
    case MODE_BUSY:
        return "busy";
    case MODE_PERF:
        return "perf";
    case MODE_POLL:
    default:
        return "poll";
    }
}

static void usage(FILE *out)
{
    fprintf(out,
            "rxbench — receive synthetic UDP packets and print stats\n"
            "\n"
            "Usage: rxbench [options]\n"
            "\n"
            "  --count N       expected packets / storage slots (default %llu)\n"
            "  --port  N       bind UDP port (default %u)\n"
            "  --bind  IP      bind IPv4 address (default %s)\n"
            "  --first-ms N    wait this long for the first packet (default %d)\n"
            "  --idle-ms  N    stop after this idle time once traffic starts (default %d)\n"
            "  --cpu N         pin this process to CPU N\n"
            "  --batch N       recvmmsg burst size (default %d, max %d)\n"
            "  --busy-poll     spin + SO_BUSY_POLL instead of poll(2)\n"
            "  --busy-us N     SO_BUSY_POLL microseconds (default %d)\n"
            "  --mode NAME     poll | busy | perf (default poll)\n"
            "  --warmup N      skip first N packets in latency/stage samples\n"
            "  --quiet         no progress on stderr\n"
            "  --mlock         mlockall current+future pages\n"
            "  --help          this message\n"
            "\n"
            "Modes:\n"
            "  poll   poll(2) then recvmmsg (v0-compatible wait)\n"
            "  busy   userspace spin + SO_BUSY_POLL + recvmmsg\n"
            "  perf   busy + --quiet + --mlock  (hot path has no I/O)\n"
            "\n"
            "e2e latency is still CLOCK_MONOTONIC_RAW (userspace→userspace).\n"
            "RDTSCP stages time recvmmsg vs per-packet handle. Not NIC latency.\n"
            "\n"
            "Example:\n"
            "  ./build/rxbench --mode busy --cpu 3 --batch 32 --count 1000000\n",
            (unsigned long long)DEFAULT_COUNT,
            TEST_PACKET_DEFAULT_PORT,
            DEFAULT_BIND,
            DEFAULT_FIRST_MS,
            DEFAULT_IDLE_MS,
            DEFAULT_BATCH,
            MAX_BATCH,
            DEFAULT_BUSY_US);
}

static int parse_args(int argc, char **argv, struct opts *o)
{
    o->count = DEFAULT_COUNT;
    o->port = TEST_PACKET_DEFAULT_PORT;
    o->bind_ip = DEFAULT_BIND;
    o->first_ms = DEFAULT_FIRST_MS;
    o->idle_ms = DEFAULT_IDLE_MS;
    o->cpu = -1;
    o->batch = DEFAULT_BATCH;
    o->busy_us = DEFAULT_BUSY_US;
    o->busy_poll = 0;
    o->quiet = 0;
    o->do_mlock = 0;
    o->warmup = 0;
    o->mode = MODE_POLL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            usage(stdout);
            exit(0);
        }
        if (strcmp(argv[i], "--count") == 0) {
            if (require_arg(i, argc, argv[i], "rxbench") != 0) {
                return -1;
            }
            if (parse_u64(argv[++i], &o->count) != 0 || o->count < 1) {
                fprintf(stderr, "rxbench: --count must be an integer >= 1\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--port") == 0) {
            if (require_arg(i, argc, argv[i], "rxbench") != 0) {
                return -1;
            }
            if (parse_u16(argv[++i], &o->port) != 0) {
                fprintf(stderr, "rxbench: --port must be 1..65535\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--bind") == 0) {
            if (require_arg(i, argc, argv[i], "rxbench") != 0) {
                return -1;
            }
            o->bind_ip = argv[++i];
        } else if (strcmp(argv[i], "--first-ms") == 0) {
            if (require_arg(i, argc, argv[i], "rxbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 1, 86400000, &o->first_ms) != 0) {
                fprintf(stderr, "rxbench: --first-ms must be 1..86400000\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--idle-ms") == 0) {
            if (require_arg(i, argc, argv[i], "rxbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 1, 86400000, &o->idle_ms) != 0) {
                fprintf(stderr, "rxbench: --idle-ms must be 1..86400000\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--cpu") == 0) {
            if (require_arg(i, argc, argv[i], "rxbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 0, CPU_SETSIZE - 1, &o->cpu) != 0) {
                fprintf(stderr, "rxbench: --cpu must be 0..%d\n", CPU_SETSIZE - 1);
                return -1;
            }
        } else if (strcmp(argv[i], "--batch") == 0) {
            if (require_arg(i, argc, argv[i], "rxbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 1, MAX_BATCH, &o->batch) != 0) {
                fprintf(stderr, "rxbench: --batch must be 1..%d\n", MAX_BATCH);
                return -1;
            }
        } else if (strcmp(argv[i], "--busy-poll") == 0) {
            o->busy_poll = 1;
        } else if (strcmp(argv[i], "--busy-us") == 0) {
            if (require_arg(i, argc, argv[i], "rxbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 1, 1000000, &o->busy_us) != 0) {
                fprintf(stderr, "rxbench: --busy-us must be 1..1000000\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--mode") == 0) {
            if (require_arg(i, argc, argv[i], "rxbench") != 0) {
                return -1;
            }
            i++;
            if (strcmp(argv[i], "poll") == 0) {
                o->mode = MODE_POLL;
            } else if (strcmp(argv[i], "busy") == 0) {
                o->mode = MODE_BUSY;
            } else if (strcmp(argv[i], "perf") == 0) {
                o->mode = MODE_PERF;
            } else {
                fprintf(stderr, "rxbench: --mode must be poll, busy, or perf\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--warmup") == 0) {
            if (require_arg(i, argc, argv[i], "rxbench") != 0) {
                return -1;
            }
            if (parse_u64(argv[++i], &o->warmup) != 0) {
                fprintf(stderr, "rxbench: --warmup must be an integer\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--quiet") == 0) {
            o->quiet = 1;
        } else if (strcmp(argv[i], "--mlock") == 0) {
            o->do_mlock = 1;
        } else {
            fprintf(stderr, "rxbench: unknown argument: %s\n", argv[i]);
            usage(stderr);
            return -1;
        }
    }

    if (o->mode == MODE_BUSY) {
        o->busy_poll = 1;
    } else if (o->mode == MODE_PERF) {
        o->busy_poll = 1;
        o->quiet = 1;
        o->do_mlock = 1;
    } else if (o->busy_poll) {
        o->mode = MODE_BUSY;
    }
    return 0;
}

static int cmp_u64(const void *a, const void *b)
{
    uint64_t x = *(const uint64_t *)a;
    uint64_t y = *(const uint64_t *)b;

    return (x > y) - (x < y);
}

static uint64_t percentile(const uint64_t *sorted, size_t n, double p)
{
    if (n == 0) {
        return 0;
    }
    return sorted[(size_t)(p * (double)(n - 1))];
}

static void print_lat(const char *name, uint64_t ns)
{
    printf("  %-12s %10" PRIu64 " ns  (%.3f us)\n", name, ns, (double)ns / 1000.0);
}

static void print_stage(const char *name, uint64_t *a, size_t n, const struct tsc_clock *tsc)
{
    uint64_t min_c, max_c;
    double mean_c = 0.0;

    printf("  %s  samples=%zu\n", name, n);
    if (n == 0) {
        return;
    }
    qsort(a, n, sizeof(uint64_t), cmp_u64);
    min_c = a[0];
    max_c = a[n - 1];
    for (size_t i = 0; i < n; i++) {
        mean_c += (double)a[i];
    }
    mean_c /= (double)n;
    printf("    min    %10" PRIu64 " cyc  (%" PRIu64 " ns)\n", min_c, tsc_to_ns(tsc, min_c));
    printf("    p50    %10" PRIu64 " cyc  (%" PRIu64 " ns)\n",
           percentile(a, n, 0.50),
           tsc_to_ns(tsc, percentile(a, n, 0.50)));
    printf("    p90    %10" PRIu64 " cyc  (%" PRIu64 " ns)\n",
           percentile(a, n, 0.90),
           tsc_to_ns(tsc, percentile(a, n, 0.90)));
    printf("    p99    %10" PRIu64 " cyc  (%" PRIu64 " ns)\n",
           percentile(a, n, 0.99),
           tsc_to_ns(tsc, percentile(a, n, 0.99)));
    printf("    max    %10" PRIu64 " cyc  (%" PRIu64 " ns)\n", max_c, tsc_to_ns(tsc, max_c));
    printf("    mean   %10.1f cyc  (%" PRIu64 " ns)\n", mean_c, tsc_to_ns(tsc, (uint64_t)mean_c));
}

static void handle_one(struct rx_acc *a, const uint8_t *buf, ssize_t n, uint64_t rx_ns)
{
    const struct test_packet *pkt;
    uint64_t seq;
    uint64_t send_ns;
    int sample;

    a->received++;
    a->payload_bytes += (uint64_t)n;
    sample = (a->received > a->warmup);

    if ((size_t)n < sizeof(struct test_packet)) {
        a->short_pkts++;
        return;
    }

    pkt = (const struct test_packet *)(const void *)buf;
    seq = net_to_host_u64(pkt->sequence);
    send_ns = net_to_host_u64(pkt->send_ns);

    if (seq < a->count) {
        size_t word = (size_t)(seq / 64ULL);
        uint64_t bit = 1ULL << (seq % 64ULL);

        if (a->seen[word] & bit) {
            a->duplicates++;
        } else {
            a->seen[word] |= bit;
            a->unique++;
            if (seq == a->expected_next) {
                a->expected_next++;
            } else if (seq > a->expected_next) {
                a->out_of_order++;
                a->expected_next = seq + 1;
            } else {
                a->out_of_order++;
            }
        }
    } else {
        a->out_of_order++;
    }

    if (sample && a->lat_n < a->count && rx_ns >= send_ns) {
        a->lat[a->lat_n++] = rx_ns - send_ns;
    }
}

static int enable_busy_poll(int fd, int busy_us, int batch)
{
    if (setsockopt(fd, SOL_SOCKET, SO_BUSY_POLL, &busy_us, sizeof(busy_us)) != 0) {
        fprintf(stderr, "rxbench: SO_BUSY_POLL: %s (userspace spin still enabled)\n", strerror(errno));
    }
#ifdef SO_PREFER_BUSY_POLL
    {
        int one = 1;
        (void)setsockopt(fd, SOL_SOCKET, SO_PREFER_BUSY_POLL, &one, sizeof(one));
    }
#endif
#ifdef SO_BUSY_POLL_BUDGET
    (void)setsockopt(fd, SOL_SOCKET, SO_BUSY_POLL_BUDGET, &batch, sizeof(batch));
#else
    (void)batch;
#endif
    return 0;
}

int main(int argc, char **argv)
{
    struct opts o;
    struct sockaddr_in addr;
    struct tsc_clock tsc;
    struct rx_acc acc;
    int fd = -1;
    int yes = 1;
    int rcvbuf = 32 * 1024 * 1024;
    struct mmsghdr *msgs = NULL;
    struct iovec *iov = NULL;
    uint8_t *bufs = NULL;
    uint64_t *syscall_cyc = NULL;
    uint64_t syscall_n = 0;
    uint64_t first_rx_ns = 0;
    uint64_t last_rx_ns = 0;
    uint64_t spin_start_ns;
    int started = 0;

    memset(&acc, 0, sizeof(acc));

    if (parse_args(argc, argv, &o) != 0) {
        return 2;
    }
    if (o.warmup >= o.count) {
        fprintf(stderr, "rxbench: --warmup must be < --count\n");
        return 2;
    }
    if (pin_cpu(o.cpu) != 0) {
        return 1;
    }
    if (tsc_calibrate(&tsc) != 0) {
        fprintf(stderr, "rxbench: TSC calibration failed\n");
        return 1;
    }

    acc.count = o.count;
    acc.warmup = o.warmup;
    acc.seen = calloc((size_t)((o.count + 63ULL) / 64ULL), sizeof(uint64_t));
    acc.lat = calloc((size_t)o.count, sizeof(uint64_t));
    acc.handle_cyc = calloc((size_t)o.count, sizeof(uint64_t));
    syscall_cyc = calloc((size_t)o.count, sizeof(uint64_t));
    msgs = calloc((size_t)o.batch, sizeof(*msgs));
    iov = calloc((size_t)o.batch, sizeof(*iov));
    bufs = calloc((size_t)o.batch, TEST_PACKET_MAX_SIZE);
    if (acc.seen == NULL || acc.lat == NULL || acc.handle_cyc == NULL ||
        syscall_cyc == NULL || msgs == NULL || iov == NULL || bufs == NULL) {
        fprintf(stderr, "rxbench: failed to preallocate for %" PRIu64 " packets\n", o.count);
        return 1;
    }
    for (int i = 0; i < o.batch; i++) {
        iov[i].iov_base = bufs + ((size_t)i * TEST_PACKET_MAX_SIZE);
        iov[i].iov_len = TEST_PACKET_MAX_SIZE;
        msgs[i].msg_hdr.msg_iov = &iov[i];
        msgs[i].msg_hdr.msg_iovlen = 1;
    }
    if (o.do_mlock && lock_memory() != 0) {
        return 1;
    }

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(o.port);
    if (inet_pton(AF_INET, o.bind_ip, &addr.sin_addr) != 1) {
        fprintf(stderr, "rxbench: invalid IPv4 address: %s\n", o.bind_ip);
        return 2;
    }

    fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) {
        perror("rxbench: socket");
        return 1;
    }
    (void)setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
    (void)setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &rcvbuf, sizeof(rcvbuf));
    if (o.busy_poll && enable_busy_poll(fd, o.busy_us, o.batch) != 0) {
        close(fd);
        return 1;
    }
    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        perror("rxbench: bind");
        close(fd);
        return 1;
    }

    if (!o.quiet) {
        fprintf(stderr,
                "rxbench: %s  %s:%u  count=%" PRIu64 "  batch=%d  cpu=%d  tsc_hz=%.3e\n",
                mode_name(o.mode),
                o.bind_ip,
                (unsigned)o.port,
                o.count,
                o.batch,
                o.cpu,
                tsc.hz);
    }

    spin_start_ns = now_ns();
    while (acc.received < o.count) {
        int n;
        uint64_t t0, t1, rx_ns;

        if (!o.busy_poll) {
            struct pollfd pfd = { .fd = fd, .events = POLLIN, .revents = 0 };
            int pr = poll(&pfd, 1, started ? o.idle_ms : o.first_ms);

            if (pr < 0) {
                if (errno == EINTR) {
                    continue;
                }
                perror("rxbench: poll");
                break;
            }
            if (pr == 0) {
                if (!started && !o.quiet) {
                    fprintf(stderr, "rxbench: timed out waiting for the first packet\n");
                }
                break;
            }
        }

        t0 = rdtscp();
        n = recvmmsg(fd, msgs, o.batch, MSG_DONTWAIT, NULL);
        t1 = rdtscp();
        rx_ns = now_ns();

        if (n < 0) {
            uint64_t now, limit_ns;

            if (errno == EINTR) {
                continue;
            }
            if (errno != EAGAIN && errno != EWOULDBLOCK) {
                perror("rxbench: recvmmsg");
                break;
            }
            if (!o.busy_poll) {
                continue;
            }
            now = now_ns();
            limit_ns = (uint64_t)(started ? o.idle_ms : o.first_ms) * 1000000ULL;
            if (!started && (now - spin_start_ns) >= limit_ns) {
                if (!o.quiet) {
                    fprintf(stderr, "rxbench: timed out waiting for the first packet\n");
                }
                break;
            }
            if (started && (now - last_rx_ns) >= limit_ns) {
                break;
            }
            continue;
        }

        if (!started) {
            started = 1;
            first_rx_ns = rx_ns;
        }
        last_rx_ns = rx_ns;

        if (acc.received >= o.warmup && syscall_n < o.count) {
            syscall_cyc[syscall_n++] = t1 - t0;
        }

        for (int i = 0; i < n && acc.received < o.count; i++) {
            uint64_t h0, h1;
            ssize_t len = msgs[i].msg_len;

            h0 = rdtscp();
            handle_one(&acc, iov[i].iov_base, len, rx_ns);
            h1 = rdtscp();
            if (acc.received > o.warmup && acc.handle_n < o.count) {
                acc.handle_cyc[acc.handle_n++] = h1 - h0;
            }
        }
    }

    {
        uint64_t missing = (acc.unique < o.count) ? (o.count - acc.unique) : 0;
        double elapsed_s = 0.0;
        double pps = 0.0;
        double gbps = 0.0;
        uint64_t min_ns = 0;
        uint64_t max_ns = 0;
        double mean_ns = 0.0;

        if (started && last_rx_ns > first_rx_ns) {
            elapsed_s = (double)(last_rx_ns - first_rx_ns) / 1e9;
            pps = (double)acc.received / elapsed_s;
            gbps = ((double)acc.payload_bytes * 8.0) / elapsed_s / 1e9;
        }

        if (acc.lat_n > 0) {
            qsort(acc.lat, (size_t)acc.lat_n, sizeof(uint64_t), cmp_u64);
            min_ns = acc.lat[0];
            max_ns = acc.lat[acc.lat_n - 1];
            for (uint64_t i = 0; i < acc.lat_n; i++) {
                mean_ns += (double)acc.lat[i];
            }
            mean_ns /= (double)acc.lat_n;
        }

        printf("RX BENCH\n\n");
        printf("mode:          %s\n", mode_name(o.mode));
        printf("cpu:           %d\n", o.cpu);
        printf("batch:         %d\n", o.batch);
        printf("busy_poll_us:  %d\n", o.busy_poll ? o.busy_us : 0);
        printf("warmup:        %" PRIu64 "\n", o.warmup);
        printf("tsc_hz:        %.6e\n", tsc.hz);
        printf("\n");
        printf("received:      %" PRIu64 "\n", acc.received);
        printf("expected:      %" PRIu64 "\n", o.count);
        printf("missing:       %" PRIu64 "\n", missing);
        printf("duplicates:    %" PRIu64 "\n", acc.duplicates);
        printf("out_of_order:  %" PRIu64 "\n", acc.out_of_order);
        if (acc.short_pkts != 0) {
            printf("short:         %" PRIu64 "\n", acc.short_pkts);
        }
        printf("\n");
        printf("throughput:\n");
        printf("  packets/sec  %.2f\n", pps);
        printf("  Gbps         %.4f   (UDP payload bits / receive window)\n", gbps);
        printf("\n");
        printf("latency:       sender userspace -> receiver userspace\n");
        printf("               CLOCK_MONOTONIC_RAW; NOT physical NIC latency\n");
        if (acc.lat_n == 0) {
            printf("  (no samples)\n");
        } else {
            print_lat("min", min_ns);
            print_lat("p50", percentile(acc.lat, (size_t)acc.lat_n, 0.50));
            print_lat("p90", percentile(acc.lat, (size_t)acc.lat_n, 0.90));
            print_lat("p99", percentile(acc.lat, (size_t)acc.lat_n, 0.99));
            print_lat("p99.9", percentile(acc.lat, (size_t)acc.lat_n, 0.999));
            print_lat("max", max_ns);
            printf("  %-12s %10.1f ns  (%.3f us)\n", "mean", mean_ns, mean_ns / 1000.0);
            printf("  samples      %" PRIu64 "\n", acc.lat_n);
        }
        printf("\n");
        printf("rdtscp stages: intra-process; NOT physical NIC latency\n");
        print_stage("recvmmsg (per syscall)", syscall_cyc, (size_t)syscall_n, &tsc);
        print_stage("handle (per packet after recv)", acc.handle_cyc, (size_t)acc.handle_n, &tsc);
    }

    close(fd);
    free(acc.seen);
    free(acc.lat);
    free(acc.handle_cyc);
    free(syscall_cyc);
    free(msgs);
    free(iov);
    free(bufs);
    return 0;
}
