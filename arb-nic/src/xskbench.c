#include "packet.h"
#include "util.h"
#include "xsk_ring.h"

#include <errno.h>
#include <inttypes.h>
#include <linux/if_ether.h>
#include <linux/if_link.h>
#include <linux/ip.h>
#include <linux/udp.h>
#include <net/if.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <unistd.h>

#include <bpf/bpf.h>
#include <bpf/libbpf.h>

#define DEFAULT_COUNT     1000000ULL
#define DEFAULT_FIRST_MS  30000
#define DEFAULT_IDLE_MS   1000
#define DEFAULT_DEV       "veth-rx"

struct opts {
    uint64_t count;
    const char *dev;
    const char *obj_path;
    int queue;
    int cpu;
    int first_ms;
    int idle_ms;
    int quiet;
    int do_mlock;
    int zerocopy;
    int remote;
    int port;
    uint32_t ring;
    uint32_t frames;
    uint32_t frame_sz;
};

struct xsk_sock {
    int fd;
    int ifindex;
    void *umem;
    size_t umem_len;
    uint32_t frame_sz;
    uint32_t nframes;
    struct xsk_ring rx;
    struct xsk_ring fq;
    struct xsk_ring tx;
    struct xsk_ring cr;
};

struct acc {
    uint64_t received;
    uint64_t unique;
    uint64_t duplicates;
    uint64_t out_of_order;
    uint64_t short_pkts;
    uint64_t expected_next;
    uint64_t empty_polls;
    uint64_t count;
    uint64_t *seen;
    uint64_t *lat;
    uint64_t lat_n;
    uint64_t *handle_cyc;
    uint64_t handle_n;
    uint64_t *recycle_cyc;
    uint64_t recycle_n;
    uint32_t *batch;
    uint64_t batch_n;
    uint64_t payload_bytes;
    int skip_e2e;
};

static void usage(FILE *out)
{
    fprintf(out,
            "xskbench — AF_XDP RX. Separate from rxbench.\n"
            "\n"
            "  NIC → XDP parse → configured dport → XDP_REDIRECT → XSKMAP → UMEM\n"
            "\n"
            "Usage: xskbench [options]\n"
            "\n"
            "  --dev IFACE     bind this interface (default %s)\n"
            "  --queue N       RX queue / XSKMAP key (default 0)\n"
            "  --port N        UDP dest port to redirect (default 9000)\n"
            "  --count N       expected packets (default %llu)\n"
            "  --cpu N         pin this process to CPU N\n"
            "  --obj PATH      xdp.bpf.o (default: next to this binary)\n"
            "  --ring N        RX/FILL ring entries, power of two (default %u)\n"
            "  --frames N      UMEM frames (default %u)\n"
            "  --frame-size N  UMEM chunk bytes (default %u)\n"
            "  --first-ms N    wait for first packet (default %d)\n"
            "  --idle-ms N     stop after idle once started (default %d)\n"
            "  --quiet         no progress on stderr\n"
            "  --mlock         mlockall after setup\n"
            "  --copy          XDP_COPY (default)\n"
            "  --zerocopy      force XDP_ZEROCOPY; fail if bind cannot\n"
            "  --remote        skip sender→receiver clocks (two machines)\n"
            "  --help\n"
            "\n"
            "Other UDP/TCP is XDP_PASS. Do not redirect generic traffic.\n",
            DEFAULT_DEV,
            (unsigned long long)DEFAULT_COUNT,
            XSK_DEFAULT_RING,
            XSK_DEFAULT_FRAMES,
            XSK_DEFAULT_FRAME_SZ,
            DEFAULT_FIRST_MS,
            DEFAULT_IDLE_MS);
}

static void default_obj_path(char *buf, size_t n, const char *argv0)
{
    char tmp[4096];
    const char *slash;

    snprintf(tmp, sizeof(tmp), "%s", argv0);
    slash = strrchr(tmp, '/');
    if (slash != NULL) {
        snprintf(buf, n, "%.*s/xdp.bpf.o", (int)(slash - tmp), tmp);
    } else {
        snprintf(buf, n, "./xdp.bpf.o");
    }
}

static int parse_args(int argc, char **argv, struct opts *o, char *obj_buf, size_t obj_buf_n)
{
    memset(o, 0, sizeof(*o));
    o->count = DEFAULT_COUNT;
    o->dev = DEFAULT_DEV;
    o->queue = 0;
    o->cpu = -1;
    o->first_ms = DEFAULT_FIRST_MS;
    o->idle_ms = DEFAULT_IDLE_MS;
    o->ring = XSK_DEFAULT_RING;
    o->frames = XSK_DEFAULT_FRAMES;
    o->frame_sz = XSK_DEFAULT_FRAME_SZ;
    o->port = 9000;
    o->zerocopy = 0;
    o->remote = 0;
    default_obj_path(obj_buf, obj_buf_n, argv[0]);
    o->obj_path = obj_buf;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            usage(stdout);
            exit(0);
        }
        if (strcmp(argv[i], "--zerocopy") == 0) {
            o->zerocopy = 1;
        } else if (strcmp(argv[i], "--copy") == 0) {
            o->zerocopy = 0;
        } else if (strcmp(argv[i], "--remote") == 0) {
            o->remote = 1;
        } else if (strcmp(argv[i], "--dev") == 0) {
            if (require_arg(i, argc, argv[i], "xskbench") != 0) {
                return -1;
            }
            o->dev = argv[++i];
        } else if (strcmp(argv[i], "--obj") == 0) {
            if (require_arg(i, argc, argv[i], "xskbench") != 0) {
                return -1;
            }
            o->obj_path = argv[++i];
        } else if (strcmp(argv[i], "--queue") == 0) {
            if (require_arg(i, argc, argv[i], "xskbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 0, 63, &o->queue) != 0) {
                fprintf(stderr, "xskbench: --queue must be 0..63\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--count") == 0) {
            if (require_arg(i, argc, argv[i], "xskbench") != 0) {
                return -1;
            }
            if (parse_u64(argv[++i], &o->count) != 0 || o->count < 1) {
                fprintf(stderr, "xskbench: --count must be >= 1\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--port") == 0) {
            uint16_t p;
            if (require_arg(i, argc, argv[i], "xskbench") != 0) {
                return -1;
            }
            if (parse_u16(argv[++i], &p) != 0) {
                fprintf(stderr, "xskbench: --port must be 1..65535\n");
                return -1;
            }
            o->port = (int)p;
        } else if (strcmp(argv[i], "--cpu") == 0) {
            if (require_arg(i, argc, argv[i], "xskbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 0, CPU_SETSIZE - 1, &o->cpu) != 0) {
                fprintf(stderr, "xskbench: --cpu out of range\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--ring") == 0) {
            int v;
            if (require_arg(i, argc, argv[i], "xskbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 8, 65536, &v) != 0 || (v & (v - 1)) != 0) {
                fprintf(stderr, "xskbench: --ring must be a power of two\n");
                return -1;
            }
            o->ring = (uint32_t)v;
        } else if (strcmp(argv[i], "--frames") == 0) {
            int v;
            if (require_arg(i, argc, argv[i], "xskbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 64, 1 << 20, &v) != 0) {
                fprintf(stderr, "xskbench: --frames out of range\n");
                return -1;
            }
            o->frames = (uint32_t)v;
        } else if (strcmp(argv[i], "--frame-size") == 0) {
            int v;
            if (require_arg(i, argc, argv[i], "xskbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 2048, 8192, &v) != 0 || (v & (v - 1)) != 0) {
                fprintf(stderr, "xskbench: --frame-size must be 2048 or 4096/8192\n");
                return -1;
            }
            o->frame_sz = (uint32_t)v;
        } else if (strcmp(argv[i], "--first-ms") == 0) {
            if (require_arg(i, argc, argv[i], "xskbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 1, 86400000, &o->first_ms) != 0) {
                return -1;
            }
        } else if (strcmp(argv[i], "--idle-ms") == 0) {
            if (require_arg(i, argc, argv[i], "xskbench") != 0) {
                return -1;
            }
            if (parse_int_ge(argv[++i], 1, 86400000, &o->idle_ms) != 0) {
                return -1;
            }
        } else if (strcmp(argv[i], "--quiet") == 0) {
            o->quiet = 1;
        } else if (strcmp(argv[i], "--mlock") == 0) {
            o->do_mlock = 1;
        } else {
            fprintf(stderr, "xskbench: unknown argument: %s\n", argv[i]);
            usage(stderr);
            return -1;
        }
    }
    if (o->frames < o->ring * 2) {
        fprintf(stderr, "xskbench: --frames must be >= 2 * --ring\n");
        return -1;
    }
    return 0;
}

static int fill_stock(struct xsk_sock *s, uint32_t n)
{
    uint32_t idx;

    if (xsk_prod_reserve(&s->fq, n, &idx) != n) {
        return -1;
    }
    for (uint32_t i = 0; i < n; i++) {
        xsk_fill_addr(&s->fq, idx + i, (uint64_t)i * s->frame_sz);
    }
    xsk_prod_submit(&s->fq);
    return 0;
}

static void fill_recycle(struct xsk_sock *s, uint64_t addr)
{
    uint32_t idx;

    if (xsk_prod_reserve(&s->fq, 1, &idx) != 1) {
        return;
    }
    xsk_fill_addr(&s->fq, idx, addr);
    xsk_prod_submit(&s->fq);
}

static void fill_kick(const struct xsk_sock *s)
{
    if (s->fq.flags != NULL && (*s->fq.flags & XDP_RING_NEED_WAKEUP) != 0) {
        (void)sendto(s->fd, NULL, 0, MSG_DONTWAIT, NULL, 0);
    }
}

static int xsk_open(struct xsk_sock *s, const struct opts *o)
{
    struct xdp_umem_reg reg;
    struct xdp_mmap_offsets off;
    socklen_t off_len = sizeof(off);
    struct sockaddr_xdp sxdp;
    uint32_t ring = o->ring;

    memset(s, 0, sizeof(*s));
    s->ifindex = (int)if_nametoindex(o->dev);
    if (s->ifindex == 0) {
        fprintf(stderr, "xskbench: no such device: %s\n", o->dev);
        return -1;
    }
    s->frame_sz = o->frame_sz;
    s->nframes = o->frames;
    s->umem_len = (size_t)o->frames * (size_t)o->frame_sz;
    s->umem = mmap(NULL, s->umem_len, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_POPULATE, -1, 0);
    if (s->umem == MAP_FAILED) {
        perror("xskbench: umem mmap");
        return -1;
    }

    s->fd = socket(AF_XDP, SOCK_RAW, 0);
    if (s->fd < 0) {
        perror("xskbench: socket(AF_XDP)");
        return -1;
    }

    memset(&reg, 0, sizeof(reg));
    reg.addr = (uintptr_t)s->umem;
    reg.len = s->umem_len;
    reg.chunk_size = o->frame_sz;
    reg.headroom = 0;
    if (setsockopt(s->fd, SOL_XDP, XDP_UMEM_REG, &reg, sizeof(reg)) != 0) {
        perror("xskbench: XDP_UMEM_REG");
        return -1;
    }
    if (setsockopt(s->fd, SOL_XDP, XDP_UMEM_FILL_RING, &ring, sizeof(ring)) != 0 ||
        setsockopt(s->fd, SOL_XDP, XDP_UMEM_COMPLETION_RING, &ring, sizeof(ring)) != 0 ||
        setsockopt(s->fd, SOL_XDP, XDP_RX_RING, &ring, sizeof(ring)) != 0 ||
        setsockopt(s->fd, SOL_XDP, XDP_TX_RING, &ring, sizeof(ring)) != 0) {
        perror("xskbench: XDP_*_RING");
        return -1;
    }
    if (getsockopt(s->fd, SOL_XDP, XDP_MMAP_OFFSETS, &off, &off_len) != 0) {
        perror("xskbench: XDP_MMAP_OFFSETS");
        return -1;
    }
    if (xsk_ring_map(&s->rx, s->fd, XDP_PGOFF_RX_RING, &off.rx, ring, sizeof(struct xdp_desc)) != 0 ||
        xsk_ring_map(&s->tx, s->fd, XDP_PGOFF_TX_RING, &off.tx, ring, sizeof(struct xdp_desc)) != 0 ||
        xsk_ring_map(&s->fq, s->fd, (off_t)XDP_UMEM_PGOFF_FILL_RING, &off.fr, ring, sizeof(uint64_t)) != 0 ||
        xsk_ring_map(&s->cr, s->fd, (off_t)XDP_UMEM_PGOFF_COMPLETION_RING, &off.cr, ring, sizeof(uint64_t)) != 0) {
        perror("xskbench: ring mmap");
        return -1;
    }
    s->fq.cached_cons = s->fq.size;

    memset(&sxdp, 0, sizeof(sxdp));
    sxdp.sxdp_family = AF_XDP;
    sxdp.sxdp_ifindex = (uint32_t)s->ifindex;
    sxdp.sxdp_queue_id = (uint32_t)o->queue;
    sxdp.sxdp_flags = XDP_USE_NEED_WAKEUP | (o->zerocopy ? XDP_ZEROCOPY : XDP_COPY);
    if (bind(s->fd, (struct sockaddr *)&sxdp, sizeof(sxdp)) != 0) {
        if (o->zerocopy) {
            fprintf(stderr, "xskbench: XDP_ZEROCOPY bind failed: %s (not falling back to COPY)\n",
                    strerror(errno));
        } else {
            perror("xskbench: bind AF_XDP");
        }
        return -1;
    }
    if (fill_stock(s, ring) != 0) {
        fprintf(stderr, "xskbench: initial fill failed\n");
        return -1;
    }
    return 0;
}

static void xsk_close(struct xsk_sock *s)
{
    xsk_ring_unmap(&s->rx);
    xsk_ring_unmap(&s->tx);
    xsk_ring_unmap(&s->fq);
    xsk_ring_unmap(&s->cr);
    if (s->fd >= 0) {
        close(s->fd);
        s->fd = -1;
    }
    if (s->umem != NULL && s->umem != MAP_FAILED) {
        munmap(s->umem, s->umem_len);
        s->umem = NULL;
    }
}

static unsigned int master_ifindex(const char *dev)
{
    char path[64 + IF_NAMESIZE];
    char tgt[256];
    const char *base;
    ssize_t n;

    snprintf(path, sizeof(path), "/sys/class/net/%s/master", dev);
    n = readlink(path, tgt, sizeof(tgt) - 1);
    if (n <= 0) {
        return 0;
    }
    tgt[n] = '\0';
    base = strrchr(tgt, '/');
    base = (base != NULL) ? base + 1 : tgt;
    return if_nametoindex(base);
}

static int attach_xdp(const struct opts *o, int xsk_fd, struct bpf_object **out_obj, int *out_native)
{
    struct bpf_object *obj;
    struct bpf_program *prog, *p;
    struct bpf_map *map;
    int prog_fd, map_fd, key, err;

    obj = bpf_object__open_file(o->obj_path, NULL);
    if (obj == NULL) {
        fprintf(stderr, "xskbench: open %s: %s\n", o->obj_path, strerror(errno));
        return -1;
    }
    bpf_object__for_each_program(p, obj) {
        bpf_program__set_type(p, BPF_PROG_TYPE_XDP);
    }
    if (bpf_object__load(obj) != 0) {
        fprintf(stderr, "xskbench: load %s failed\n", o->obj_path);
        bpf_object__close(obj);
        return -1;
    }
    prog = bpf_object__find_program_by_name(obj, "xdp_parse_pass");
    map = bpf_object__find_map_by_name(obj, "xsks_map");
    if (prog == NULL || map == NULL) {
        fprintf(stderr, "xskbench: missing xdp_parse_pass or xsks_map\n");
        bpf_object__close(obj);
        return -1;
    }
    {
        struct bpf_map *cfg = bpf_object__find_map_by_name(obj, "xdp_cfg");
        __u32 ck = 0;
        __u32 port = (uint32_t)o->port;

        if (cfg == NULL || bpf_map_update_elem(bpf_map__fd(cfg), &ck, &port, BPF_ANY) != 0) {
            fprintf(stderr, "xskbench: failed to set xdp_cfg dest port %u\n", port);
            bpf_object__close(obj);
            return -1;
        }
        ck = 1;
        port = master_ifindex(o->dev);
        if (bpf_map_update_elem(bpf_map__fd(cfg), &ck, &port, BPF_ANY) != 0) {
            fprintf(stderr, "xskbench: failed to set xdp_cfg bond ifindex\n");
            bpf_object__close(obj);
            return -1;
        }
        if (port != 0) {
            fprintf(stderr, "xskbench: non-match → bpf_redirect ifindex %u (bond)\n", port);
        }
    }
    map_fd = bpf_map__fd(map);
    key = o->queue;
    if (bpf_map_update_elem(map_fd, &key, &xsk_fd, BPF_ANY) != 0) {
        perror("xskbench: XSKMAP update");
        bpf_object__close(obj);
        return -1;
    }
    prog_fd = bpf_program__fd(prog);
    (void)bpf_xdp_detach(if_nametoindex(o->dev), 0, NULL);
    err = bpf_xdp_attach(if_nametoindex(o->dev), prog_fd, XDP_FLAGS_DRV_MODE, NULL);
    if (err != 0 && o->zerocopy) {
        fprintf(stderr, "xskbench: native XDP attach failed (required for ZEROCOPY)\n");
        bpf_object__close(obj);
        return -1;
    }
    if (err == 0) {
        *out_native = 1;
    } else {
        err = bpf_xdp_attach(if_nametoindex(o->dev), prog_fd, XDP_FLAGS_SKB_MODE, NULL);
        *out_native = 0;
    }
    if (err != 0) {
        fprintf(stderr, "xskbench: XDP attach failed\n");
        bpf_object__close(obj);
        return -1;
    }
    fprintf(stderr, "xskbench: attached %s\n", *out_native ? "native" : "skb");
    *out_obj = obj;
    return 0;
}

static void print_xdp_stats(struct bpf_object *obj)
{
    struct bpf_map *m;
    int fd;
    __u32 k;
    __u64 seen = 0, match = 0;

    if (obj == NULL) {
        return;
    }
    m = bpf_object__find_map_by_name(obj, "xdp_stats");
    if (m == NULL) {
        return;
    }
    fd = bpf_map__fd(m);
    k = 0;
    (void)bpf_map_lookup_elem(fd, &k, &seen);
    k = 1;
    (void)bpf_map_lookup_elem(fd, &k, &match);
    printf("xdp_seen:      %" PRIu64 "\n", (uint64_t)seen);
    printf("xdp_dport:     %" PRIu64 "\n", (uint64_t)match);
}

static const struct test_packet *payload_hdr(const uint8_t *pkt, uint32_t len)
{
    const struct ethhdr *eth;
    const struct iphdr *ip;
    const struct udphdr *udp;
    uint32_t ihl, off;

    if (len < sizeof(*eth) + sizeof(*ip) + sizeof(*udp) + sizeof(struct test_packet)) {
        return NULL;
    }
    eth = (const struct ethhdr *)(const void *)pkt;
    if (eth->h_proto != __builtin_bswap16(ETH_P_IP)) {
        return NULL;
    }
    ip = (const struct iphdr *)(const void *)(pkt + sizeof(*eth));
    ihl = (uint32_t)ip->ihl * 4;
    off = sizeof(*eth) + ihl + sizeof(*udp);
    if (ihl < sizeof(*ip) || len < off + sizeof(struct test_packet)) {
        return NULL;
    }
    udp = (const struct udphdr *)(const void *)(pkt + sizeof(*eth) + ihl);
    (void)udp;
    return (const struct test_packet *)(const void *)(pkt + off);
}

static void handle_one(struct acc *a, const uint8_t *pkt, uint32_t len, uint64_t rx_ns)
{
    const struct test_packet *hdr;
    uint64_t seq, send_ns;

    a->received++;
    a->payload_bytes += len;
    hdr = payload_hdr(pkt, len);
    if (hdr == NULL) {
        a->short_pkts++;
        return;
    }
    seq = net_to_host_u64(hdr->sequence);
    send_ns = net_to_host_u64(hdr->send_ns);
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
    if (!a->skip_e2e && a->lat_n < a->count && rx_ns >= send_ns) {
        a->lat[a->lat_n++] = rx_ns - send_ns;
    }
}

static int cmp_u64(const void *a, const void *b)
{
    uint64_t x = *(const uint64_t *)a;
    uint64_t y = *(const uint64_t *)b;

    return (x > y) - (x < y);
}

static int cmp_u32(const void *a, const void *b)
{
    uint32_t x = *(const uint32_t *)a;
    uint32_t y = *(const uint32_t *)b;

    return (x > y) - (x < y);
}

static uint64_t pct_u64(const uint64_t *s, size_t n, double p)
{
    if (n == 0) {
        return 0;
    }
    return s[(size_t)(p * (double)(n - 1))];
}

static uint32_t pct_u32(const uint32_t *s, size_t n, double p)
{
    if (n == 0) {
        return 0;
    }
    return s[(size_t)(p * (double)(n - 1))];
}

static void print_lat(const char *name, uint64_t ns)
{
    printf("  %-8s %10" PRIu64 " ns  (%.3f us)\n", name, ns, (double)ns / 1000.0);
}

int main(int argc, char **argv)
{
    struct opts o;
    char obj_buf[4096];
    struct xsk_sock xsk;
    struct bpf_object *bpf = NULL;
    struct tsc_clock tsc;
    struct acc acc;
    uint64_t first_rx = 0, last_rx = 0, spin0;
    int started = 0;
    int ifindex;
    int xdp_native = 0;

    memset(&acc, 0, sizeof(acc));
    memset(&xsk, 0, sizeof(xsk));
    xsk.fd = -1;

    if (parse_args(argc, argv, &o, obj_buf, sizeof(obj_buf)) != 0) {
        return 2;
    }
    if (pin_cpu(o.cpu) != 0 || tsc_calibrate(&tsc) != 0) {
        return 1;
    }

    acc.count = o.count;
    acc.skip_e2e = o.remote;
    acc.seen = calloc((size_t)((o.count + 63ULL) / 64ULL), sizeof(uint64_t));
    acc.lat = calloc((size_t)o.count, sizeof(uint64_t));
    acc.handle_cyc = calloc((size_t)o.count, sizeof(uint64_t));
    acc.recycle_cyc = calloc((size_t)o.count, sizeof(uint64_t));
    acc.batch = calloc((size_t)o.count, sizeof(uint32_t));
    if (acc.seen == NULL || acc.lat == NULL || acc.handle_cyc == NULL ||
        acc.recycle_cyc == NULL || acc.batch == NULL) {
        fprintf(stderr, "xskbench: preallocate failed\n");
        return 1;
    }
    if (o.do_mlock && lock_memory() != 0) {
        return 1;
    }
    if (xsk_open(&xsk, &o) != 0) {
        return 1;
    }
    if (attach_xdp(&o, xsk.fd, &bpf, &xdp_native) != 0) {
        xsk_close(&xsk);
        return 1;
    }

    fprintf(stderr, "xskbench: ready  dev=%s queue=%d port=%d count=%" PRIu64 " %s umem=%zu\n",
            o.dev, o.queue, o.port, o.count, o.zerocopy ? "ZEROCOPY" : "COPY", xsk.umem_len);

    spin0 = now_ns();
    while (acc.received < o.count) {
        uint32_t idx = 0;
        uint32_t n;
        uint64_t rx_ns;

        n = xsk_cons_peek(&xsk.rx, 64, &idx);
        if (n == 0) {
            uint64_t now = now_ns();
            uint64_t limit = (uint64_t)(started ? o.idle_ms : o.first_ms) * 1000000ULL;

            acc.empty_polls++;
            fill_kick(&xsk);
            {
                struct pollfd pfd = { .fd = xsk.fd, .events = POLLIN };

                (void)poll(&pfd, 1, 0);
            }
            if (!started && (now - spin0) >= limit) {
                if (!o.quiet) {
                    fprintf(stderr, "xskbench: timed out waiting for the first packet\n");
                }
                break;
            }
            if (started && (now - last_rx) >= limit) {
                break;
            }
            continue;
        }

        rx_ns = now_ns();
        if (!started) {
            started = 1;
            first_rx = rx_ns;
        }
        last_rx = rx_ns;
        if (acc.batch_n < o.count) {
            acc.batch[acc.batch_n++] = n;
        }

        for (uint32_t i = 0; i < n; i++) {
            const struct xdp_desc *d = xsk_rx_desc(&xsk.rx, idx + i);
            const uint8_t *pkt;
            uint64_t h0, h1, r0, r1;

            pkt = (const uint8_t *)xsk.umem + d->addr;
            h0 = rdtscp();
            handle_one(&acc, pkt, d->len, rx_ns);
            h1 = rdtscp();
            r0 = rdtscp();
            fill_recycle(&xsk, d->addr);
            r1 = rdtscp();
            if (acc.handle_n < o.count) {
                acc.handle_cyc[acc.handle_n++] = h1 - h0;
            }
            if (acc.recycle_n < o.count) {
                acc.recycle_cyc[acc.recycle_n++] = r1 - r0;
            }
            if (acc.received >= o.count) {
                break;
            }
        }
        xsk_cons_release(&xsk.rx, n);
        fill_kick(&xsk);
    }

    {
        uint64_t missing = (acc.unique < o.count) ? (o.count - acc.unique) : 0;
        double elapsed = 0, pps = 0, gbps = 0;

        if (started && last_rx > first_rx) {
            elapsed = (double)(last_rx - first_rx) / 1e9;
            pps = (double)acc.received / elapsed;
            gbps = ((double)acc.payload_bytes * 8.0) / elapsed / 1e9;
        }
        if (acc.lat_n > 0) {
            qsort(acc.lat, (size_t)acc.lat_n, sizeof(uint64_t), cmp_u64);
        }
        if (acc.handle_n > 0) {
            qsort(acc.handle_cyc, (size_t)acc.handle_n, sizeof(uint64_t), cmp_u64);
        }
        if (acc.recycle_n > 0) {
            qsort(acc.recycle_cyc, (size_t)acc.recycle_n, sizeof(uint64_t), cmp_u64);
        }
        if (acc.batch_n > 0) {
            qsort(acc.batch, (size_t)acc.batch_n, sizeof(uint32_t), cmp_u32);
        }

        printf("AF_XDP BENCH\n\n");
        printf("dev:           %s\n", o.dev);
        printf("queue:         %d\n", o.queue);
        printf("mode:          %s\n", o.zerocopy ? "XDP_ZEROCOPY" : "XDP_COPY");
        printf("xdp_attach:    %s\n", xdp_native ? "native" : "skb");
        printf("xdp:           parse + dport %d + XDP_REDIRECT + XSKMAP\n", o.port);
        print_xdp_stats(bpf);
        printf("cpu:           %d\n", o.cpu);
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
        printf("empty_polls:   %" PRIu64 "\n", acc.empty_polls);
        printf("\n");
        printf("throughput:\n");
        printf("  packets/sec  %.2f\n", pps);
        printf("  Gbps         %.4f   (L2 bytes on the RX ring / receive window)\n", gbps);
        printf("\n");
        if (o.remote) {
            printf("sender→userspace  SKIPPED (two machines; clocks are not a µs clock)\n");
        } else {
            printf("sender→userspace  CLOCK_MONOTONIC_RAW; NOT physical NIC latency\n");
        }
        if (o.remote || acc.lat_n == 0) {
            if (!o.remote) {
                printf("  (no samples)\n");
            }
        } else {
            print_lat("p50", pct_u64(acc.lat, (size_t)acc.lat_n, 0.50));
            print_lat("p99", pct_u64(acc.lat, (size_t)acc.lat_n, 0.99));
            print_lat("p99.9", pct_u64(acc.lat, (size_t)acc.lat_n, 0.999));
            print_lat("min", acc.lat[0]);
            print_lat("max", acc.lat[acc.lat_n - 1]);
        }
        printf("\n");
        printf("RX batch size\n");
        if (acc.batch_n == 0) {
            printf("  (no samples)\n");
        } else {
            printf("  p50      %u\n", pct_u32(acc.batch, (size_t)acc.batch_n, 0.50));
            printf("  p99      %u\n", pct_u32(acc.batch, (size_t)acc.batch_n, 0.99));
        }
        printf("\n");
        printf("handle cycles   (after pointer, before recycle)\n");
        if (acc.handle_n == 0) {
            printf("  (no samples)\n");
        } else {
            printf("  p50      %" PRIu64 " cyc  (%" PRIu64 " ns)\n",
                   pct_u64(acc.handle_cyc, (size_t)acc.handle_n, 0.50),
                   tsc_to_ns(&tsc, pct_u64(acc.handle_cyc, (size_t)acc.handle_n, 0.50)));
            printf("  p99      %" PRIu64 " cyc  (%" PRIu64 " ns)\n",
                   pct_u64(acc.handle_cyc, (size_t)acc.handle_n, 0.99),
                   tsc_to_ns(&tsc, pct_u64(acc.handle_cyc, (size_t)acc.handle_n, 0.99)));
        }
        printf("\n");
        printf("recycle cycles  (fill-ring produce)\n");
        if (acc.recycle_n == 0) {
            printf("  (no samples)\n");
        } else {
            printf("  p50      %" PRIu64 " cyc  (%" PRIu64 " ns)\n",
                   pct_u64(acc.recycle_cyc, (size_t)acc.recycle_n, 0.50),
                   tsc_to_ns(&tsc, pct_u64(acc.recycle_cyc, (size_t)acc.recycle_n, 0.50)));
            printf("  p99      %" PRIu64 " cyc  (%" PRIu64 " ns)\n",
                   pct_u64(acc.recycle_cyc, (size_t)acc.recycle_n, 0.99),
                   tsc_to_ns(&tsc, pct_u64(acc.recycle_cyc, (size_t)acc.recycle_n, 0.99)));
        }
    }

    ifindex = (int)if_nametoindex(o.dev);
    if (ifindex != 0) {
        (void)bpf_xdp_detach(ifindex, XDP_FLAGS_DRV_MODE, NULL);
        (void)bpf_xdp_detach(ifindex, XDP_FLAGS_SKB_MODE, NULL);
        (void)bpf_xdp_detach(ifindex, 0, NULL);
    }
    if (bpf != NULL) {
        bpf_object__close(bpf);
    }
    xsk_close(&xsk);
    free(acc.seen);
    free(acc.lat);
    free(acc.handle_cyc);
    free(acc.recycle_cyc);
    free(acc.batch);
    return 0;
}
