#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/in.h>
#include <linux/ip.h>
#include <linux/udp.h>

#include <bpf/bpf_endian.h>
#include <bpf/bpf_helpers.h>

#include "xdp_port.h"

/*
 * xdp_pass        — XDP_PASS only (control / “added a hop” experiment)
 * xdp_parse_pass  — Ethernet / IPv4 / UDP / configured dport, then:
 *                     XSKMAP redirect on match (fallback pass_up if no XSK)
 *                     pass_up otherwise
 *
 * Dest port comes from xdp_cfg[0] (0 means ARB_NIC_UDP_PORT).
 * xdp_cfg[1] = bond ifindex. Non-zero → bpf_redirect to the bond
 * so XDP on a LACP slave does not steal SSH / normal stack traffic.
 * Anything else, including other UDP, is pass_up. No extra parse.
 */

#define STAT_SEEN    0
#define STAT_UDP9000 1
#define XSK_QUEUES   64

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 2);
    __type(key, __u32);
    __type(value, __u64);
} xdp_stats SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_XSKMAP);
    __uint(max_entries, XSK_QUEUES);
    __type(key, __u32);
    __type(value, __u32);
} xsks_map SEC(".maps");

/* [0] dest UDP port, host order. 0 → ARB_NIC_UDP_PORT.
 * [1] bond ifindex. 0 → XDP_PASS (veth). */
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 2);
    __type(key, __u32);
    __type(value, __u32);
} xdp_cfg SEC(".maps");

static __always_inline void stats_inc(__u32 key)
{
    __u64 *v = bpf_map_lookup_elem(&xdp_stats, &key);

    if (v)
        __sync_fetch_and_add(v, 1);
}

static __always_inline int pass_up(void)
{
    __u32 k = 1;
    __u32 *ifindex = bpf_map_lookup_elem(&xdp_cfg, &k);

    if (ifindex && *ifindex != 0)
        return bpf_redirect(*ifindex, 0);
    return XDP_PASS;
}

SEC("xdp")
int xdp_pass(struct xdp_md *ctx)
{
    (void)ctx;
    return pass_up();
}

static __always_inline int parse_ipv4_udp_dport(struct xdp_md *ctx)
{
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;
    struct ethhdr *eth;
    struct iphdr *ip;
    struct udphdr *udp;
    __u32 ihl;
    __u32 qid;
    __u32 want = ARB_NIC_UDP_PORT;
    __u32 cfg_key = 0;
    __u32 *cfg;

    stats_inc(STAT_SEEN);
    cfg = bpf_map_lookup_elem(&xdp_cfg, &cfg_key);
    if (cfg && *cfg != 0)
        want = *cfg;

    eth = data;
    if ((void *)(eth + 1) > data_end)
        return pass_up();
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return pass_up();

    ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end)
        return pass_up();
    if (ip->protocol != IPPROTO_UDP)
        return pass_up();

    ihl = (__u32)ip->ihl * 4;
    if (ihl < sizeof(struct iphdr))
        return pass_up();

    udp = (void *)ip + ihl;
    if ((void *)(udp + 1) > data_end)
        return pass_up();
    if (bpf_ntohs(udp->dest) != want)
        return pass_up();

    stats_inc(STAT_UDP9000);

    qid = ctx->rx_queue_index;
    if (qid >= XSK_QUEUES)
        return pass_up();
    {
        int act = bpf_redirect_map(&xsks_map, qid, XDP_PASS);

        if (act != XDP_REDIRECT)
            return pass_up();
        return act;
    }
}

SEC("xdp")
int xdp_parse_pass(struct xdp_md *ctx)
{
    return parse_ipv4_udp_dport(ctx);
}

char LICENSE[] SEC("license") = "GPL";
