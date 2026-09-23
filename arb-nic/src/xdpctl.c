#include <errno.h>
#include <linux/if_link.h>
#include <net/if.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <bpf/bpf.h>
#include <bpf/libbpf.h>

#define STATS_PIN "/sys/fs/bpf/arb-nic-xdp-stats"

static void usage(FILE *out)
{
    fprintf(out,
            "xdpctl — attach / detach the arb-nic XDP programs\n"
            "\n"
            "Usage:\n"
            "  xdpctl attach --dev IFACE --prog pass|parse [--obj PATH] [--mode auto|drv|skb]\n"
            "  xdpctl detach --dev IFACE\n"
            "  xdpctl stats\n"
            "  xdpctl --help\n"
            "\n"
            "pass  — XDP_PASS.\n"
            "parse — IPv4/UDP/dport 9000, then XSKMAP redirect (XDP_PASS if no XSK).\n"
            "Zero-copy is NIC-005, not this tool.\n");
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

static const char *prog_name(const char *kind)
{
    if (strcmp(kind, "pass") == 0) {
        return "xdp_pass";
    }
    if (strcmp(kind, "parse") == 0) {
        return "xdp_parse_pass";
    }
    return NULL;
}

static int attach_with_flags(int ifindex, int prog_fd, unsigned int flags, const char *label)
{
    int err = bpf_xdp_attach(ifindex, prog_fd, flags, NULL);

    if (err == 0) {
        printf("xdpctl: attached on ifindex %d (%s)\n", ifindex, label);
        return 0;
    }
    return err;
}

static int cmd_attach(const char *dev, const char *kind, const char *obj_path, const char *mode)
{
    const char *name = prog_name(kind);
    struct bpf_object *obj;
    struct bpf_program *prog;
    int ifindex;
    int prog_fd;
    int err;

    if (name == NULL) {
        fprintf(stderr, "xdpctl: --prog must be pass or parse\n");
        return 2;
    }
    ifindex = (int)if_nametoindex(dev);
    if (ifindex == 0) {
        fprintf(stderr, "xdpctl: no such device: %s\n", dev);
        return 1;
    }

    obj = bpf_object__open_file(obj_path, NULL);
    if (obj == NULL) {
        char buf[256];

        libbpf_strerror(errno, buf, sizeof(buf));
        fprintf(stderr, "xdpctl: open %s: %s\n", obj_path, buf);
        return 1;
    }
    {
        struct bpf_program *p;

        bpf_object__for_each_program(p, obj) {
            bpf_program__set_type(p, BPF_PROG_TYPE_XDP);
        }
    }
    err = bpf_object__load(obj);
    if (err != 0) {
        fprintf(stderr, "xdpctl: load %s failed (%d)\n", obj_path, err);
        bpf_object__close(obj);
        return 1;
    }
    prog = bpf_object__find_program_by_name(obj, name);
    if (prog == NULL) {
        fprintf(stderr, "xdpctl: program %s not found in %s\n", name, obj_path);
        bpf_object__close(obj);
        return 1;
    }
    prog_fd = bpf_program__fd(prog);
    if (prog_fd < 0) {
        fprintf(stderr, "xdpctl: no fd for %s\n", name);
        bpf_object__close(obj);
        return 1;
    }

    (void)bpf_xdp_detach(ifindex, 0, NULL);

    err = -1;
    if (strcmp(mode, "drv") == 0) {
        err = attach_with_flags(ifindex, prog_fd, XDP_FLAGS_DRV_MODE, "xdpdrv");
    } else if (strcmp(mode, "skb") == 0) {
        err = attach_with_flags(ifindex, prog_fd, XDP_FLAGS_SKB_MODE, "xdpgeneric");
    } else {
        err = attach_with_flags(ifindex, prog_fd, XDP_FLAGS_DRV_MODE, "xdpdrv");
        if (err != 0) {
            err = attach_with_flags(ifindex, prog_fd, XDP_FLAGS_SKB_MODE, "xdpgeneric");
        }
    }
    if (err != 0) {
        fprintf(stderr, "xdpctl: attach %s on %s failed: %s\n", name, dev, strerror(errno));
        bpf_object__close(obj);
        return 1;
    }
    {
        struct bpf_map *map = bpf_object__find_map_by_name(obj, "xdp_stats");

        unlink(STATS_PIN);
        if (map != NULL && bpf_map__pin(map, STATS_PIN) != 0) {
            fprintf(stderr, "xdpctl: pin %s failed: %s (stats unavailable)\n",
                    STATS_PIN,
                    strerror(errno));
        }
    }
    printf("xdpctl: prog=%s obj=%s dev=%s\n", name, obj_path, dev);
    bpf_object__close(obj);
    return 0;
}

static int cmd_detach(const char *dev)
{
    int ifindex = (int)if_nametoindex(dev);

    if (ifindex == 0) {
        fprintf(stderr, "xdpctl: no such device: %s\n", dev);
        return 1;
    }
    (void)bpf_xdp_detach(ifindex, XDP_FLAGS_DRV_MODE, NULL);
    (void)bpf_xdp_detach(ifindex, XDP_FLAGS_SKB_MODE, NULL);
    (void)bpf_xdp_detach(ifindex, 0, NULL);
    unlink(STATS_PIN);
    printf("xdpctl: detached from %s\n", dev);
    return 0;
}

static int cmd_stats(void)
{
    int fd;
    __u32 k;
    __u64 seen = 0;
    __u64 udp = 0;

    fd = bpf_obj_get(STATS_PIN);
    if (fd < 0) {
        fprintf(stderr, "xdpctl: stats pin %s: %s\n", STATS_PIN, strerror(errno));
        return 1;
    }
    k = 0;
    if (bpf_map_lookup_elem(fd, &k, &seen) != 0) {
        seen = 0;
    }
    k = 1;
    if (bpf_map_lookup_elem(fd, &k, &udp) != 0) {
        udp = 0;
    }
    close(fd);
    printf("xdp_stats  seen=%llu  udp_dport_9000=%llu\n",
           (unsigned long long)seen,
           (unsigned long long)udp);
    return 0;
}

int main(int argc, char **argv)
{
    const char *cmd;
    const char *dev = NULL;
    const char *kind = NULL;
    const char *mode = "auto";
    char obj_buf[4096];
    const char *obj_path = NULL;

    if (argc < 2 || strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0) {
        usage(stdout);
        return 0;
    }

    default_obj_path(obj_buf, sizeof(obj_buf), argv[0]);
    obj_path = obj_buf;
    cmd = argv[1];

    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--dev") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "xdpctl: --dev requires a value\n");
                return 2;
            }
            dev = argv[++i];
        } else if (strcmp(argv[i], "--prog") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "xdpctl: --prog requires a value\n");
                return 2;
            }
            kind = argv[++i];
        } else if (strcmp(argv[i], "--obj") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "xdpctl: --obj requires a value\n");
                return 2;
            }
            obj_path = argv[++i];
        } else if (strcmp(argv[i], "--mode") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "xdpctl: --mode requires a value\n");
                return 2;
            }
            mode = argv[++i];
            if (strcmp(mode, "auto") != 0 && strcmp(mode, "drv") != 0 && strcmp(mode, "skb") != 0) {
                fprintf(stderr, "xdpctl: --mode must be auto, drv, or skb\n");
                return 2;
            }
        } else if (strcmp(argv[i], "--help") == 0) {
            usage(stdout);
            return 0;
        } else {
            fprintf(stderr, "xdpctl: unknown argument: %s\n", argv[i]);
            usage(stderr);
            return 2;
        }
    }

    if (strcmp(cmd, "stats") == 0) {
        return cmd_stats();
    }
    if (dev == NULL) {
        fprintf(stderr, "xdpctl: --dev is required\n");
        return 2;
    }
    if (strcmp(cmd, "attach") == 0) {
        if (kind == NULL) {
            fprintf(stderr, "xdpctl: --prog is required for attach\n");
            return 2;
        }
        return cmd_attach(dev, kind, obj_path, mode);
    }
    if (strcmp(cmd, "detach") == 0) {
        return cmd_detach(dev);
    }
    fprintf(stderr, "xdpctl: unknown command: %s\n", cmd);
    usage(stderr);
    return 2;
}
