#include "packet.h"
#include "util.h"

#include <arpa/inet.h>
#include <errno.h>
#include <inttypes.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#define DEFAULT_COUNT 1000000ULL
#define DEFAULT_DST   "10.10.0.1"
#define DEFAULT_RATE  0ULL
#define DEFAULT_BATCH 1
#define MAX_BATCH     256

static void usage(FILE *out)
{
    fprintf(out,
            "txgen — send synthetic UDP benchmark packets\n"
            "\n"
            "Usage: txgen [options]\n"
            "\n"
            "  --count N     packets to send (default %llu)\n"
            "  --size  N     UDP payload bytes (default %u, min %u, max %u)\n"
            "  --dst   IP    destination IPv4 (default %s)\n"
            "  --port  N     destination UDP port (default %u)\n"
            "  --sport N     bind this UDP source port (default: ephemeral)\n"
            "  --rate  N     packets/sec; 0 = unlimited (default %llu)\n"
            "  --unlimited   same as --rate 0\n"
            "  --cpu N       pin this process to CPU N\n"
            "  --batch N     sendmmsg burst size (default %d, max %d)\n"
            "  --quiet       no summary on stderr\n"
            "  --help        this message\n"
            "\n"
            "Example (from the tx netns after setup_veth.sh):\n"
            "  sudo ip netns exec txns ./build/txgen \\\n"
            "      --count 1000000 --size 1200 --dst 10.10.0.1 --port 9000 --cpu 2 --batch 32\n",
            (unsigned long long)DEFAULT_COUNT,
            TEST_PACKET_DEFAULT_SIZE,
            TEST_PACKET_MIN_SIZE,
            TEST_PACKET_MAX_SIZE,
            DEFAULT_DST,
            TEST_PACKET_DEFAULT_PORT,
            (unsigned long long)DEFAULT_RATE,
            DEFAULT_BATCH,
            MAX_BATCH);
}

int main(int argc, char **argv)
{
    uint64_t count = DEFAULT_COUNT;
    uint64_t size = TEST_PACKET_DEFAULT_SIZE;
    uint64_t rate = DEFAULT_RATE;
    uint16_t port = TEST_PACKET_DEFAULT_PORT;
    uint16_t sport = 0;
    const char *dst = DEFAULT_DST;
    int cpu = -1;
    int batch = DEFAULT_BATCH;
    int quiet = 0;
    struct sockaddr_in addr;
    int fd = -1;
    int sndbuf = 16 * 1024 * 1024;
    uint8_t *bufs = NULL;
    struct mmsghdr *msgs = NULL;
    struct iovec *iov = NULL;
    uint64_t seq;
    uint64_t interval_ns = 0;
    uint64_t t0;
    uint64_t t1;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            usage(stdout);
            return 0;
        }
        if (strcmp(argv[i], "--count") == 0) {
            if (require_arg(i, argc, argv[i], "txgen") != 0) {
                return 2;
            }
            if (parse_u64(argv[++i], &count) != 0 || count < 1) {
                fprintf(stderr, "txgen: --count must be an integer >= 1\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--size") == 0) {
            if (require_arg(i, argc, argv[i], "txgen") != 0) {
                return 2;
            }
            if (parse_u64(argv[++i], &size) != 0 ||
                size < TEST_PACKET_MIN_SIZE || size > TEST_PACKET_MAX_SIZE) {
                fprintf(stderr,
                        "txgen: --size must be %u..%u\n",
                        TEST_PACKET_MIN_SIZE,
                        TEST_PACKET_MAX_SIZE);
                return 2;
            }
        } else if (strcmp(argv[i], "--dst") == 0) {
            if (require_arg(i, argc, argv[i], "txgen") != 0) {
                return 2;
            }
            dst = argv[++i];
        } else if (strcmp(argv[i], "--port") == 0) {
            if (require_arg(i, argc, argv[i], "txgen") != 0) {
                return 2;
            }
            if (parse_u16(argv[++i], &port) != 0) {
                fprintf(stderr, "txgen: --port must be 1..65535\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--sport") == 0) {
            if (require_arg(i, argc, argv[i], "txgen") != 0) {
                return 2;
            }
            if (parse_u16(argv[++i], &sport) != 0) {
                fprintf(stderr, "txgen: --sport must be 1..65535\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--rate") == 0) {
            if (require_arg(i, argc, argv[i], "txgen") != 0) {
                return 2;
            }
            if (parse_u64(argv[++i], &rate) != 0) {
                fprintf(stderr, "txgen: --rate must be an integer (0 = unlimited)\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--unlimited") == 0) {
            rate = 0;
        } else if (strcmp(argv[i], "--cpu") == 0) {
            if (require_arg(i, argc, argv[i], "txgen") != 0) {
                return 2;
            }
            if (parse_int_ge(argv[++i], 0, CPU_SETSIZE - 1, &cpu) != 0) {
                fprintf(stderr, "txgen: --cpu must be 0..%d\n", CPU_SETSIZE - 1);
                return 2;
            }
        } else if (strcmp(argv[i], "--batch") == 0) {
            if (require_arg(i, argc, argv[i], "txgen") != 0) {
                return 2;
            }
            if (parse_int_ge(argv[++i], 1, MAX_BATCH, &batch) != 0) {
                fprintf(stderr, "txgen: --batch must be 1..%d\n", MAX_BATCH);
                return 2;
            }
        } else if (strcmp(argv[i], "--quiet") == 0) {
            quiet = 1;
        } else {
            fprintf(stderr, "txgen: unknown argument: %s\n", argv[i]);
            usage(stderr);
            return 2;
        }
    }

    if (pin_cpu(cpu) != 0) {
        return 1;
    }

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    if (inet_pton(AF_INET, dst, &addr.sin_addr) != 1) {
        fprintf(stderr, "txgen: invalid IPv4 address: %s\n", dst);
        return 2;
    }

    fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) {
        perror("txgen: socket");
        return 1;
    }
    (void)setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &sndbuf, sizeof(sndbuf));
    if (sport != 0) {
        struct sockaddr_in local;

        memset(&local, 0, sizeof(local));
        local.sin_family = AF_INET;
        local.sin_port = htons(sport);
        if (bind(fd, (struct sockaddr *)&local, sizeof(local)) != 0) {
            perror("txgen: bind --sport");
            close(fd);
            return 1;
        }
    }
    /* Unconnected sendto. connect() + ICMP port-unreachable → ECONNREFUSED
     * on the next sendmmsg, which is normal until XDP/UDP is actually up. */

    bufs = calloc((size_t)batch, (size_t)size);
    msgs = calloc((size_t)batch, sizeof(*msgs));
    iov = calloc((size_t)batch, sizeof(*iov));
    if (bufs == NULL || msgs == NULL || iov == NULL) {
        fprintf(stderr, "txgen: out of memory\n");
        close(fd);
        return 1;
    }
    for (int i = 0; i < batch; i++) {
        iov[i].iov_base = bufs + ((size_t)i * (size_t)size);
        iov[i].iov_len = (size_t)size;
        msgs[i].msg_hdr.msg_iov = &iov[i];
        msgs[i].msg_hdr.msg_iovlen = 1;
        msgs[i].msg_hdr.msg_name = &addr;
        msgs[i].msg_hdr.msg_namelen = sizeof(addr);
    }

    if (rate > 0) {
        interval_ns = 1000000000ULL / rate;
        if (interval_ns == 0) {
            interval_ns = 1;
        }
    }

    t0 = now_ns();
    seq = 0;
    while (seq < count) {
        int n = (int)((count - seq) < (uint64_t)batch ? (count - seq) : (uint64_t)batch);
        int sent;

        if (interval_ns != 0) {
            uint64_t target = t0 + seq * interval_ns;
            uint64_t now = now_ns();

            if (now < target) {
                struct timespec ts;
                uint64_t sleep_ns = target - now;

                ts.tv_sec = (time_t)(sleep_ns / 1000000000ULL);
                ts.tv_nsec = (long)(sleep_ns % 1000000000ULL);
                clock_nanosleep(CLOCK_MONOTONIC, 0, &ts, NULL);
            }
        }

        for (int i = 0; i < n; i++) {
            struct test_packet *pkt = (struct test_packet *)(void *)iov[i].iov_base;

            pkt->sequence = host_to_net_u64(seq + (uint64_t)i);
            pkt->send_ns = host_to_net_u64(now_ns());
        }

        sent = sendmmsg(fd, msgs, (unsigned int)n, 0);
        if (sent < 0) {
            if (errno == ECONNREFUSED || errno == EAGAIN || errno == EWOULDBLOCK) {
                continue;
            }
            perror("txgen: sendmmsg");
            free(bufs);
            free(msgs);
            free(iov);
            close(fd);
            return 1;
        }
        if (sent == 0) {
            fprintf(stderr, "txgen: sendmmsg sent 0\n");
            break;
        }
        seq += (uint64_t)sent;
    }
    t1 = now_ns();

    if (!quiet) {
        fprintf(stderr,
                "txgen: sent %" PRIu64 " packets  size=%" PRIu64
                "  batch=%d  cpu=%d  elapsed_ns=%" PRIu64 "\n",
                seq,
                size,
                batch,
                cpu,
                t1 - t0);
    }

    free(bufs);
    free(msgs);
    free(iov);
    close(fd);
    return 0;
}
