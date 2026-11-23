/* Process sandbox for the standard answer, loaded with LD_PRELOAD into the unmodified calcurse process.
 * Its constructor runs before calcurse's main(). It (1) loads the locale and time zone data and the unwinder
 * (libgcc_s) that thread cancellation needs, then confines all
 * file access with Landlock: read and write only below the instance directories named in PBSANDBOX_RW, read only
 * the system data named in PBSANDBOX_RO (terminal descriptions, locale and time zone data); the installation and
 * the rest of the file system are not reachable. It then (2) installs a seccomp filter under which the process
 * cannot create other processes or run programs (fork, vfork, clone without CLONE_THREAD, execve and execveat
 * fail with EPERM; clone3 reports ENOSYS so that threads are created with clone) and cannot leave its session
 * (setsid, setpgid). calcurse's own threads keep working. Its features that start an external program (editor,
 * pager, help viewer, pipe, notification command, hooks, merge tool) therefore have no effect, and it cannot
 * start its background daemon. If either layer cannot be installed the process exits: calcurse never runs
 * unconfined. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/filter.h>
#include <linux/landlock.h>
#include <linux/seccomp.h>
#include <locale.h>
#include <sched.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#ifndef LANDLOCK_ACCESS_FS_REFER
#define LANDLOCK_ACCESS_FS_REFER (1ULL << 13)
#endif
#ifndef LANDLOCK_ACCESS_FS_TRUNCATE
#define LANDLOCK_ACCESS_FS_TRUNCATE (1ULL << 14)
#endif
#ifndef AUDIT_ARCH_X86_64
#define AUDIT_ARCH_X86_64 0xC000003E
#endif
#ifndef __X32_SYSCALL_BIT
#define __X32_SYSCALL_BIT 0x40000000
#endif

static void die(const char *what) {
    dprintf(2, "pbsandbox: %s: %s\n", what, strerror(errno));
    _exit(126);
}

#define FS_FILE (LANDLOCK_ACCESS_FS_EXECUTE | LANDLOCK_ACCESS_FS_WRITE_FILE | LANDLOCK_ACCESS_FS_READ_FILE | \
                 LANDLOCK_ACCESS_FS_TRUNCATE)
#define FS_READ (LANDLOCK_ACCESS_FS_READ_FILE | LANDLOCK_ACCESS_FS_READ_DIR)
#define FS_WRITE (LANDLOCK_ACCESS_FS_WRITE_FILE | LANDLOCK_ACCESS_FS_REMOVE_DIR | LANDLOCK_ACCESS_FS_REMOVE_FILE | \
                  LANDLOCK_ACCESS_FS_MAKE_DIR | LANDLOCK_ACCESS_FS_MAKE_REG | LANDLOCK_ACCESS_FS_MAKE_SYM | \
                  LANDLOCK_ACCESS_FS_TRUNCATE | LANDLOCK_ACCESS_FS_REFER)
#define FS_ALL (LANDLOCK_ACCESS_FS_EXECUTE | FS_READ | FS_WRITE | LANDLOCK_ACCESS_FS_MAKE_CHAR | \
                LANDLOCK_ACCESS_FS_MAKE_SOCK | LANDLOCK_ACCESS_FS_MAKE_FIFO | LANDLOCK_ACCESS_FS_MAKE_BLOCK)

static unsigned long long handled;

static void allow(int ruleset, const char *list, unsigned long long access) {
    if (!list || !*list) return;
    char *copy = strdup(list), *save = NULL;
    if (!copy) die("strdup");
    for (char *path = strtok_r(copy, ":", &save); path; path = strtok_r(NULL, ":", &save)) {
        int fd = open(path, O_PATH | O_CLOEXEC);
        if (fd < 0) continue; /* an absent path needs no rule */
        struct landlock_path_beneath_attr rule = {.allowed_access = access & handled, .parent_fd = fd};
        if (syscall(SYS_landlock_add_rule, ruleset, LANDLOCK_RULE_PATH_BENEATH, &rule, 0) != 0) {
            /* a file (not a directory) accepts only file rights */
            rule.allowed_access &= FS_FILE;
            if (syscall(SYS_landlock_add_rule, ruleset, LANDLOCK_RULE_PATH_BENEATH, &rule, 0) != 0) die(path);
        }
        close(fd);
    }
    free(copy);
}

static void landlock(void) {
    long abi = syscall(SYS_landlock_create_ruleset, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION);
    if (abi < 1) die("Landlock is not available");
    handled = FS_ALL;
    if (abi < 2) handled &= ~LANDLOCK_ACCESS_FS_REFER;
    if (abi < 3) handled &= ~LANDLOCK_ACCESS_FS_TRUNCATE;
    struct landlock_ruleset_attr attr = {.handled_access_fs = handled};
    int ruleset = syscall(SYS_landlock_create_ruleset, &attr, sizeof(attr), 0);
    if (ruleset < 0) die("landlock_create_ruleset");
    allow(ruleset, getenv("PBSANDBOX_RO"), FS_READ);
    allow(ruleset, getenv("PBSANDBOX_RW"), FS_READ | FS_WRITE);
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) die("no_new_privs");
    if (syscall(SYS_landlock_restrict_self, ruleset, 0) != 0) die("landlock_restrict_self");
    close(ruleset);
}

#define DENY(nr, err) BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (nr), 0, 1), \
                      BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | (err))

static void noprocesses(void) {
    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        /* the x32 system call ABI is not used by this program */
        BPF_JUMP(BPF_JMP | BPF_JGE | BPF_K, __X32_SYSCALL_BIT, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
        DENY(SYS_execve, EPERM),
        DENY(SYS_execveat, EPERM),
        DENY(SYS_fork, EPERM),
        DENY(SYS_vfork, EPERM),
        DENY(SYS_clone3, ENOSYS),
        DENY(SYS_setsid, EPERM),
        DENY(SYS_setpgid, EPERM),
        /* clone: only threads (CLONE_THREAD in the flags argument) */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_clone, 0, 4),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[0])),
        BPF_JUMP(BPF_JMP | BPF_JSET | BPF_K, CLONE_THREAD, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    };
    struct sock_fprog prog = {.len = sizeof(filter) / sizeof(filter[0]), .filter = filter};
    if (prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog, 0, 0) != 0) die("seccomp");
}

__attribute__((constructor)) static void pbsandbox(void) {
    unsetenv("LD_PRELOAD");
    if (!getenv("PBSANDBOX_RW") || !*getenv("PBSANDBOX_RW")) {
        errno = EINVAL;
        die("PBSANDBOX_RW");
    }
    /* Locale and time zone data, and the unwinder glibc loads on demand when a thread is cancelled, are
     * loaded before file access is confined. */
    setlocale(LC_ALL, "");
    tzset();
    if (!dlopen("libgcc_s.so.1", RTLD_NOW | RTLD_NODELETE)) {
        errno = ENOENT;
        die("libgcc_s.so.1");
    }
    landlock();
    noprocesses();
}
