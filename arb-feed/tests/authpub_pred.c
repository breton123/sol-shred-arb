#include "authpub.h"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

static void
put_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
    p[2] = (uint8_t)(v >> 16);
    p[3] = (uint8_t)(v >> 24);
}

static void
put_u64(uint8_t *p, uint64_t v)
{
    put_u32(p, (uint32_t)v);
    put_u32(p + 4, (uint32_t)(v >> 32));
}

static int
seed(const char *path, const uint64_t *slots, const uint32_t *flags,
     const uint8_t *tags, uint32_t n)
{
    size_t len = AUTH_HDR + AUTH_POOL;
    int fd = open(path, O_RDWR | O_CREAT | O_TRUNC, 0600);
    uint8_t *map;
    uint8_t *pool;
    uint32_t i;

    if (fd < 0 || ftruncate(fd, (off_t)len) != 0) {
        if (fd >= 0) close(fd);
        return -1;
    }
    map = mmap(NULL, len, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (map == MAP_FAILED) return -1;
    memset(map, 0, len);
    put_u32(map, AUTH_MAGIC);
    put_u32(map + 4, ((uint32_t)AUTH_RING << 16) | AUTH_VER);
    put_u32(map + 12, 1u);
    put_u32(map + 16, AUTH_BLOB);
    pool = map + AUTH_HDR;
    put_u64(pool, 2u);
    put_u32(pool + 8, n);
    for (i = 0; i < n; i++) {
        uint8_t *e = pool + AUTH_POOL_HDR + (size_t)i * AUTH_ENT;
        put_u64(e, (uint64_t)i + 1u);
        put_u64(e + 8, slots[i]);
        put_u32(e + 16, AUTH_TXN_INDEX_UNKNOWN);
        put_u32(e + 20, flags[i] | AUTH_HAS_ACCOUNT_WRITE_VERSION);
        put_u64(e + 24, (uint64_t)i + 1u);
        memset(e + 32, tags[i], 64);
        e[97] = 1;
        put_u64(e + 100, (uint64_t)i + 5000u);
    }
    if (msync(map, len, MS_SYNC) != 0) {
        munmap(map, len);
        return -1;
    }
    munmap(map, len);
    return 0;
}

static int
check(const char *path, const uint64_t *slots, const uint32_t *flags,
      const uint8_t *tags, uint32_t n, uint64_t trig_slot,
      const uint8_t *sig, int want, uint64_t want_slot, uint8_t want_tag,
      uint64_t want_write_version)
{
    authpub_meta_t meta;
    uint8_t blob[AUTH_BLOB];
    uint16_t blob_len = 0;
    int rc;

    authpub_close();
    if (seed(path, slots, flags, tags, n) != 0 || authpub_open(path) != 0) {
        return -1;
    }
    rc = authpub_pred(0, trig_slot, sig, &meta, blob, &blob_len);
    authpub_close();
    if (want < 0) return rc < 0 ? 0 : -1;
    return rc == 0 && meta.slot == want_slot && meta.sig[0] == want_tag
        && meta.txn_index == AUTH_TXN_INDEX_UNKNOWN
        && (meta.flags & AUTH_HAS_TXN_INDEX) == 0u
        && meta.max_account_write_version == want_write_version ? 0 : -1;
}

int
main(void)
{
    char path[] = "/tmp/authpub-pred-XXXXXX";
    int fd = mkstemp(path);
    uint8_t target[64];
    const uint32_t c = AUTH_COHERENT;
    int failed = 0;

    if (fd < 0) return 1;
    close(fd);
    memset(target, 'N', sizeof(target));

    {
        const uint64_t slots[] = {10, 20, 21};
        const uint32_t flags[] = {c, c | AUTH_GAPPED, c};
        const uint8_t tags[] = {'A', 'G', 'N'};
        failed |= check(path, slots, flags, tags, 3, 21, target, -1, 0, 0, 0);
    }
    {
        const uint64_t slots[] = {40, 41};
        const uint32_t flags[] = {c, c};
        const uint8_t tags[] = {'A', 'B'};
        failed |= check(path, slots, flags, tags, 2, 41, NULL, -1, 0, 0, 0);
    }
    {
        const uint64_t slots[] = {50, 51};
        const uint32_t flags[] = {c, c};
        const uint8_t tags[] = {'A', 'B'};
        failed |= check(path, slots, flags, tags, 2, 52, NULL, 0, 51, 'B', 5001);
    }
    {
        const uint64_t slots[] = {50, 51, 52};
        const uint32_t flags[] = {c, c, c};
        const uint8_t tags[] = {'A', 'B', 'N'};
        failed |= check(path, slots, flags, tags, 3, 52, target, 0, 51, 'B', 5001);
    }
    unlink(path);
    if (failed) {
        fputs("authpub predecessor regression failed\n", stderr);
        return 1;
    }
    puts("authpub predecessor regression passed");
    return 0;
}
