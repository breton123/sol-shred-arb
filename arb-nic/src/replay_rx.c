#include "classify.h"
#include "packet.h"
#include "rx.h"
#include "util.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define ARBRX_MAGIC        "ARBRX1"
#define ARBRX_MAGIC_LEN    8
#define DEFAULT_LOOPS      8ULL
#define DEFAULT_WARMUP     1000ULL
#define SAMPLE_MAX         4000000u

struct opts {
    const char *file;
    uint64_t loops;
    uint64_t warmup;
    int cpu;
    int do_mlock;
};

struct packet_ref {
    const uint8_t *data;
    uint16_t len;
};

struct cyc_acc {
    uint64_t *v;
    uint32_t n;
    uint32_t cap;
};

struct acc {
    uint64_t packets;
    uint64_t parsed;
    uint64_t bad;
    uint64_t dlmm;
    uint64_t pump;
    uint64_t both;
    uint64_t irrelevant;
    uint64_t sink;
    struct cyc_acc parse;
    struct cyc_acc classify;
    struct cyc_acc total;
    struct cyc_acc classify_irrel;
    struct cyc_acc total_irrel;
};

static void usage(const char *prog)
{
    fprintf(stderr,
            "usage: %s --file shreds.arbrx [--loops N] [--warmup N] [--cpu N] [--mlock]\n",
            prog);
}

static int parse_args(int argc, char **argv, struct opts *o)
{
    int i;

    o->file = NULL;
    o->loops = DEFAULT_LOOPS;
    o->warmup = DEFAULT_WARMUP;
    o->cpu = -1;
    o->do_mlock = 0;

    for (i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--file") == 0) {
            if (require_arg(i, argc, argv[i], argv[0]) != 0) {
                return -1;
            }
            o->file = argv[++i];
        } else if (strcmp(argv[i], "--loops") == 0) {
            if (require_arg(i, argc, argv[i], argv[0]) != 0) {
                return -1;
            }
            if (parse_u64(argv[++i], &o->loops) != 0 || o->loops == 0) {
                fprintf(stderr, "bad --loops\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--warmup") == 0) {
            if (require_arg(i, argc, argv[i], argv[0]) != 0) {
                return -1;
            }
            if (parse_u64(argv[++i], &o->warmup) != 0) {
                fprintf(stderr, "bad --warmup\n");
                return -1;
            }
        } else if (strcmp(argv[i], "--cpu") == 0) {
            uint64_t v;
            if (require_arg(i, argc, argv[i], argv[0]) != 0) {
                return -1;
            }
            if (parse_u64(argv[++i], &v) != 0 || v > 4096) {
                fprintf(stderr, "bad --cpu\n");
                return -1;
            }
            o->cpu = (int)v;
        } else if (strcmp(argv[i], "--mlock") == 0) {
            o->do_mlock = 1;
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            usage(argv[0]);
            return -1;
        } else {
            fprintf(stderr, "unknown arg: %s\n", argv[i]);
            usage(argv[0]);
            return -1;
        }
    }
    if (o->file == NULL) {
        usage(argv[0]);
        return -1;
    }
    return 0;
}

static int cmp_u64(const void *a, const void *b)
{
    uint64_t xa = *(const uint64_t *)a;
    uint64_t xb = *(const uint64_t *)b;
    return (xa > xb) - (xa < xb);
}

static uint64_t pct_u64(uint64_t *v, uint32_t n, double p)
{
    if (n == 0) {
        return 0;
    }
    qsort(v, n, sizeof(v[0]), cmp_u64);
    {
        uint32_t i = (uint32_t)(p * (double)(n - 1));
        return v[i];
    }
}

static int cyc_init(struct cyc_acc *a, uint32_t cap)
{
    a->v = malloc((size_t)cap * sizeof(*a->v));
    a->n = 0;
    a->cap = cap;
    return a->v == NULL ? -1 : 0;
}

static void cyc_push(struct cyc_acc *a, uint64_t c)
{
    if (a->n < a->cap) {
        a->v[a->n++] = c;
    }
}

static int load_file(const char *path, uint8_t **out_buf, size_t *out_len)
{
    FILE *f = fopen(path, "rb");
    uint8_t *buf;
    size_t n;
    long sz;

    if (f == NULL) {
        perror(path);
        return -1;
    }
    if (fseek(f, 0, SEEK_END) != 0) {
        perror("fseek");
        fclose(f);
        return -1;
    }
    sz = ftell(f);
    if (sz < ARBRX_MAGIC_LEN) {
        fprintf(stderr, "%s: too short\n", path);
        fclose(f);
        return -1;
    }
    if (fseek(f, 0, SEEK_SET) != 0) {
        perror("fseek");
        fclose(f);
        return -1;
    }
    buf = malloc((size_t)sz);
    if (buf == NULL) {
        fprintf(stderr, "oom\n");
        fclose(f);
        return -1;
    }
    n = fread(buf, 1, (size_t)sz, f);
    fclose(f);
    if (n != (size_t)sz) {
        fprintf(stderr, "%s: short read\n", path);
        free(buf);
        return -1;
    }
    if (memcmp(buf, ARBRX_MAGIC, 6) != 0) {
        fprintf(stderr, "%s: not ARBRX1\n", path);
        free(buf);
        return -1;
    }
    *out_buf = buf;
    *out_len = n;
    return 0;
}

static int index_packets(const uint8_t *buf, size_t len,
                         struct packet_ref **out_pkts, uint32_t *out_n)
{
    size_t off = ARBRX_MAGIC_LEN;
    uint32_t cap = 1024;
    uint32_t n = 0;
    struct packet_ref *pkts = malloc((size_t)cap * sizeof(*pkts));

    if (pkts == NULL) {
        fprintf(stderr, "oom\n");
        return -1;
    }
    while (off + 2 <= len) {
        uint16_t plen = shred_load_u16_le(buf + off);
        off += 2;
        if (plen == 0 || off + plen > len) {
            fprintf(stderr, "truncated record at %zu (len=%u)\n", off, plen);
            free(pkts);
            return -1;
        }
        if (n == cap) {
            uint32_t ncap = cap * 2u;
            struct packet_ref *np = realloc(pkts, (size_t)ncap * sizeof(*pkts));
            if (np == NULL) {
                fprintf(stderr, "oom\n");
                free(pkts);
                return -1;
            }
            pkts = np;
            cap = ncap;
        }
        pkts[n].data = buf + off;
        pkts[n].len = plen;
        n++;
        off += plen;
    }
    if (n == 0) {
        fprintf(stderr, "no packets\n");
        free(pkts);
        return -1;
    }
    *out_pkts = pkts;
    *out_n = n;
    return 0;
}

static void replay(const struct packet_ref *pkts, uint32_t npkts,
                   uint64_t loops, uint64_t warmup, struct acc *acc)
{
    uint64_t i, done = 0;
    uint32_t p;

    for (i = 0; i < loops; i++) {
        for (p = 0; p < npkts; p++) {
            rx_packet_t pkt;
            shred_view_t view;
            uint64_t t0, t1, t2;
            uint32_t hit;
            uint16_t plen;
            int ok;

            pkt.data = pkts[p].data;
            pkt.len = pkts[p].len;
            pkt.queue = 0;

            t0 = rdtscp();
            ok = hot_rx(&pkt, &view);
            t1 = rdtscp();

            acc->packets++;
            if (ok != 0) {
                acc->bad++;
                done++;
                continue;
            }
            acc->parsed++;

            plen = (uint16_t)(pkt.len - (uint16_t)(view.payload - pkt.data));
            hit = classify_relevance(view.payload, plen);
            t2 = rdtscp();

            if (hit & REL_DLMM) {
                acc->dlmm++;
            }
            if (hit & REL_PUMP) {
                acc->pump++;
            }
            if (hit == REL_BOTH) {
                acc->both++;
            }
            if (hit == REL_NONE) {
                acc->irrelevant++;
            }
            acc->sink += view.slot + (uint64_t)hit + (uintptr_t)view.payload;

            if (done >= warmup && t1 >= t0 && t2 >= t1) {
                cyc_push(&acc->parse, t1 - t0);
                cyc_push(&acc->classify, t2 - t1);
                cyc_push(&acc->total, t2 - t0);
                if (hit == REL_NONE) {
                    cyc_push(&acc->classify_irrel, t2 - t1);
                    cyc_push(&acc->total_irrel, t2 - t0);
                }
            }
            done++;
        }
    }
}

static void print_cyc_row(const char *name, struct cyc_acc *a, const struct tsc_clock *tsc)
{
    uint64_t p50, p99, p999;

    if (a->n == 0) {
        printf("  %-18s  %8s %8s %8s   (0 samples)\n", name, "-", "-", "-");
        return;
    }
    p50 = pct_u64(a->v, a->n, 0.50);
    p99 = pct_u64(a->v, a->n, 0.99);
    p999 = pct_u64(a->v, a->n, 0.999);
    printf("  %-18s  %8" PRIu64 " %8" PRIu64 " %8" PRIu64 "   (%" PRIu64 " / %" PRIu64 " / %" PRIu64 " ns)\n",
           name, p50, p99, p999,
           tsc_to_ns(tsc, p50), tsc_to_ns(tsc, p99), tsc_to_ns(tsc, p999));
}

static void print_report(const struct acc *acc, const struct tsc_clock *tsc,
                         uint32_t npkts, uint64_t loops)
{
    printf("REPLAY\n");
    printf("\n");
    printf("packets       %" PRIu64 "\n", acc->packets);
    printf("parsed        %" PRIu64 "\n", acc->parsed);
    printf("bad           %" PRIu64 "\n", acc->bad);
    printf("\n");
    printf("relevant\n");
    printf("  DLMM        %" PRIu64 "\n", acc->dlmm);
    printf("  Pump        %" PRIu64 "\n", acc->pump);
    printf("  both        %" PRIu64 "\n", acc->both);
    printf("irrelevant    %" PRIu64 "\n", acc->irrelevant);
    printf("\n");
    printf("cycles:                  p50      p99     p999\n");
    print_cyc_row("shred parse", (struct cyc_acc *)&acc->parse, tsc);
    print_cyc_row("classification", (struct cyc_acc *)&acc->classify, tsc);
    print_cyc_row("total", (struct cyc_acc *)&acc->total, tsc);
    print_cyc_row("classify irrel", (struct cyc_acc *)&acc->classify_irrel, tsc);
    print_cyc_row("total irrel", (struct cyc_acc *)&acc->total_irrel, tsc);
    printf("\n");
    printf("recorded %u  loops %" PRIu64 "  sink %" PRIu64 "\n",
           npkts, loops, acc->sink);
}

static void acc_free(struct acc *acc)
{
    free(acc->parse.v);
    free(acc->classify.v);
    free(acc->total.v);
    free(acc->classify_irrel.v);
    free(acc->total_irrel.v);
}

int main(int argc, char **argv)
{
    struct opts o;
    struct tsc_clock tsc;
    struct acc acc;
    uint8_t *buf = NULL;
    size_t buflen = 0;
    struct packet_ref *pkts = NULL;
    uint32_t npkts = 0;

    if (parse_args(argc, argv, &o) != 0) {
        return 1;
    }
    if (pin_cpu(o.cpu) != 0) {
        return 1;
    }
    if (o.do_mlock && lock_memory() != 0) {
        return 1;
    }
    if (tsc_calibrate(&tsc) != 0) {
        fprintf(stderr, "tsc calibrate failed\n");
        return 1;
    }
    if (load_file(o.file, &buf, &buflen) != 0) {
        return 1;
    }
    if (index_packets(buf, buflen, &pkts, &npkts) != 0) {
        free(buf);
        return 1;
    }

    memset(&acc, 0, sizeof(acc));
    if (cyc_init(&acc.parse, SAMPLE_MAX) != 0
        || cyc_init(&acc.classify, SAMPLE_MAX) != 0
        || cyc_init(&acc.total, SAMPLE_MAX) != 0
        || cyc_init(&acc.classify_irrel, SAMPLE_MAX) != 0
        || cyc_init(&acc.total_irrel, SAMPLE_MAX) != 0) {
        fprintf(stderr, "oom\n");
        acc_free(&acc);
        free(pkts);
        free(buf);
        return 1;
    }

    replay(pkts, npkts, o.loops, o.warmup, &acc);
    print_report(&acc, &tsc, npkts, o.loops);

    acc_free(&acc);
    free(pkts);
    free(buf);
    return acc.bad != 0 ? 2 : 0;
}
