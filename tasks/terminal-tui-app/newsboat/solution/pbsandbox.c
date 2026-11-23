/* Process sandbox for Newsboat, loaded with LD_PRELOAD into the unmodified newsboat process.
 * Its constructor (1) preloads locale/timezone resources, then confines all file contents to the instance
 * and terminal devices with Landlock. System directories and the installation are no longer readable.
 * Terminal navigation is confined through libc chdir/fchdir interception. It then (2) installs
 * a seccomp filter that refuses execve/execveat with EPERM, so no external program can be started.
 * If either layer cannot be installed the process exits: the product never runs unconfined. */
#define _GNU_SOURCE
#include <errno.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <limits.h>
#include <locale.h>
#include <linux/filter.h>
#include <linux/landlock.h>
#include <linux/seccomp.h>
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

static char instance_root[PATH_MAX];
/* Landlock controls data access but does not control chdir. Confine directory navigation as well,
 * including relative names and symbolic links. The reference cannot execute arbitrary code, and all
 * product navigation calls use these libc entry points. */
static int inside_instance(const char *path) {
    size_t n = strlen(instance_root);
    return n && !strncmp(path, instance_root, n) && (path[n] == '/' || path[n] == 0);
}

int chdir(const char *path) {
    char resolved[PATH_MAX];
    if (!realpath(path, resolved) || !inside_instance(resolved)) { errno = EACCES; return -1; }
    int fd = open(resolved, O_PATH | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0) return -1;
    char descriptor[64], actual[PATH_MAX];
    snprintf(descriptor,sizeof(descriptor),"/proc/self/fd/%d",fd);
    ssize_t count=readlink(descriptor,actual,sizeof(actual)-1);
    if (count<0) {close(fd);errno=EACCES;return -1;}
    actual[count]=0;
    int result=-1;
    if (inside_instance(actual)) result=syscall(SYS_fchdir,fd);
    else errno=EACCES;
    close(fd);
    return result;
}

int fchdir(int fd) {
    char descriptor[64], actual[PATH_MAX];
    snprintf(descriptor,sizeof(descriptor),"/proc/self/fd/%d",fd);
    ssize_t count=readlink(descriptor,actual,sizeof(actual)-1);
    if(count<0) {errno=EACCES;return -1;}
    actual[count]=0;
    if(!inside_instance(actual)) {errno=EACCES;return -1;}
    return syscall(SYS_fchdir,fd);
}

#ifndef AUDIT_ARCH_X86_64
#define AUDIT_ARCH_X86_64 0xC000003E
#endif

static void die(const char *what) {
    dprintf(2, "pbsandbox: %s: %s\n", what, strerror(errno));
    _exit(126);
}

#define FS_READ (LANDLOCK_ACCESS_FS_EXECUTE | LANDLOCK_ACCESS_FS_READ_FILE | LANDLOCK_ACCESS_FS_READ_DIR)
#define FS_WRITE (LANDLOCK_ACCESS_FS_WRITE_FILE | LANDLOCK_ACCESS_FS_REMOVE_DIR | LANDLOCK_ACCESS_FS_REMOVE_FILE | \
                  LANDLOCK_ACCESS_FS_MAKE_DIR | LANDLOCK_ACCESS_FS_MAKE_REG | LANDLOCK_ACCESS_FS_MAKE_SYM | \
                  LANDLOCK_ACCESS_FS_TRUNCATE | LANDLOCK_ACCESS_FS_REFER)
#define FS_ALL (FS_READ | FS_WRITE | LANDLOCK_ACCESS_FS_MAKE_CHAR | LANDLOCK_ACCESS_FS_MAKE_SOCK | \
                LANDLOCK_ACCESS_FS_MAKE_FIFO | LANDLOCK_ACCESS_FS_MAKE_BLOCK)

static unsigned long long handled_access;

static void allow(int ruleset, const char *list, unsigned long long access) {
    access &= handled_access;
    if (!list || !*list) return;
    char *copy = strdup(list), *save = NULL;
    for (char *path = strtok_r(copy, ":", &save); path; path = strtok_r(NULL, ":", &save)) {
        int fd = open(path, O_PATH | O_CLOEXEC);
        if (fd < 0) continue; /* an absent directory needs no rule */
        struct landlock_path_beneath_attr rule = {.allowed_access = access, .parent_fd = fd};
        if (syscall(SYS_landlock_add_rule, ruleset, LANDLOCK_RULE_PATH_BENEATH, &rule, 0) != 0) {
            /* a regular file accepts only file rights */
            rule.allowed_access &= LANDLOCK_ACCESS_FS_EXECUTE | LANDLOCK_ACCESS_FS_READ_FILE |
                                   LANDLOCK_ACCESS_FS_WRITE_FILE | LANDLOCK_ACCESS_FS_TRUNCATE;
            if (syscall(SYS_landlock_add_rule, ruleset, LANDLOCK_RULE_PATH_BENEATH, &rule, 0) != 0)
                die(path);
        }
        close(fd);
    }
    free(copy);
}

static void landlock(void) {
    int abi = syscall(SYS_landlock_create_ruleset, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION);
    if (abi < 1) die("landlock support is required");
    handled_access = FS_ALL;
    if (abi < 2) handled_access &= ~LANDLOCK_ACCESS_FS_REFER;
    if (abi < 3) handled_access &= ~LANDLOCK_ACCESS_FS_TRUNCATE;
    struct landlock_ruleset_attr attr = {.handled_access_fs = handled_access};
    int ruleset = syscall(SYS_landlock_create_ruleset, &attr, sizeof(attr), 0);
    if (ruleset < 0) die("landlock_create_ruleset");
    allow(ruleset, getenv("PBSANDBOX_RO"), LANDLOCK_ACCESS_FS_EXECUTE | LANDLOCK_ACCESS_FS_READ_FILE);
    allow(ruleset, getenv("PBSANDBOX_RW"), FS_READ | FS_WRITE);
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) die("no_new_privs");
    if (syscall(SYS_landlock_restrict_self, ruleset, 0) != 0) die("landlock_restrict_self");
    close(ruleset);
}

static void noexec(void) {
    struct sock_filter filter[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_execve, 2, 0),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_execveat, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
    };
    struct sock_fprog prog = {.len = sizeof(filter) / sizeof(filter[0]), .filter = filter};
    if (prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog, 0, 0) != 0) die("seccomp");
}

__attribute__((constructor)) static void pbsandbox(void) {
    unsetenv("LD_PRELOAD");
    if (!getenv("DATA_DIR") || !realpath(getenv("DATA_DIR"),instance_root)) die("instance root");
    /* Load process runtime resources before restricting all later application file reads. Shared
     * objects are already mapped by the loader. Locale, timezone and terminal descriptions must not
     * require blanket access to system directories once the product accepts user paths. */
    setlocale(LC_ALL, "");
    tzset();
    int (*setup)(char *, int, int *) = dlsym(RTLD_DEFAULT,"setupterm");
    if(setup) {int error; setup(NULL,STDOUT_FILENO,&error);}
    landlock();
    noexec();
}
