#ifndef ARB_NIC_BPF_HELPERS_H
#define ARB_NIC_BPF_HELPERS_H

#define SEC(NAME) __attribute__((section(NAME), used))

#ifndef __always_inline
#define __always_inline inline __attribute__((always_inline))
#endif

#ifndef BPF_FUNC_map_lookup_elem
#define BPF_FUNC_map_lookup_elem 1
#endif

static void *(*bpf_map_lookup_elem)(void *map, const void *key) =
    (void *)BPF_FUNC_map_lookup_elem;

#ifndef BPF_FUNC_redirect
#define BPF_FUNC_redirect 23
#endif

static long (*bpf_redirect)(__u32 ifindex, __u64 flags) =
    (void *)BPF_FUNC_redirect;

#ifndef BPF_FUNC_redirect_map
#define BPF_FUNC_redirect_map 51
#endif

static long (*bpf_redirect_map)(void *map, __u64 key, __u64 flags) =
    (void *)BPF_FUNC_redirect_map;

/* BTF map annotations (libbpf v1+). Do not use SEC("maps") / bpf_map_def. */
#define __uint(name, val) int (*name)[val]
#define __type(name, val) typeof(val) *name

#endif
