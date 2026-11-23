#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/landlock.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>

#ifndef LANDLOCK_ACCESS_FS_REFER
#define LANDLOCK_ACCESS_FS_REFER (1ULL << 13)
#endif
#ifndef LANDLOCK_ACCESS_FS_TRUNCATE
#define LANDLOCK_ACCESS_FS_TRUNCATE (1ULL << 14)
#endif

/* Limit application writes to its profile/documents and child execution to
 * installed native helpers. This boundary is inherited by child processes. */
static int allow_path(int rules, const char *path, uint64_t access) {
    int fd = open(path, O_PATH | O_CLOEXEC);
    if (fd < 0) return errno == ENOENT ? 0 : -1;
    struct landlock_path_beneath_attr rule = {
        .allowed_access = access,
        .parent_fd = fd,
    };
    int result = syscall(SYS_landlock_add_rule, rules, LANDLOCK_RULE_PATH_BENEATH, &rule, 0);
    close(fd);
    return result;
}

int protect_application(const char *executables) {
    int abi = syscall(SYS_landlock_create_ruleset, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION);
    if (abi < 1) return -1;
    uint64_t writes = LANDLOCK_ACCESS_FS_WRITE_FILE | LANDLOCK_ACCESS_FS_REMOVE_DIR |
        LANDLOCK_ACCESS_FS_REMOVE_FILE | LANDLOCK_ACCESS_FS_MAKE_DIR | LANDLOCK_ACCESS_FS_MAKE_REG |
        LANDLOCK_ACCESS_FS_MAKE_SOCK | LANDLOCK_ACCESS_FS_MAKE_FIFO | LANDLOCK_ACCESS_FS_MAKE_SYM |
        LANDLOCK_ACCESS_FS_MAKE_CHAR | LANDLOCK_ACCESS_FS_MAKE_BLOCK;
    if (abi >= 2) writes |= LANDLOCK_ACCESS_FS_REFER;
    if (abi >= 3) writes |= LANDLOCK_ACCESS_FS_TRUNCATE;
    struct landlock_ruleset_attr attr = {.handled_access_fs = writes | LANDLOCK_ACCESS_FS_EXECUTE};
    int rules = syscall(SYS_landlock_create_ruleset, &attr, sizeof(attr), 0);
    if (rules < 0) return -1;
    int result = -1;
    const char *variables[] = {
        "DATA_DIR", "HOME", "TMPDIR", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
        "XDG_RUNTIME_DIR", "PBP_DOCUMENTS_ROOT", "PBP_MUSIC", "PBP_INBOX",
        "PBP_COLLECTION_DIR", "PBP_INPUT_DIR", "PBP_OUTPUT_DIR", NULL
    };
    for (int index = 0; variables[index]; ++index) {
        const char *path = getenv(variables[index]);
        if (path && *path && allow_path(rules, path, writes) < 0) goto done;
    }
    /* Shared memory and the null device support the supplied desktop/audio session. */
    if (allow_path(rules, "/dev/shm", writes) < 0 ||
        allow_path(rules, "/dev/null", LANDLOCK_ACCESS_FS_WRITE_FILE) < 0) goto done;
    if (executables && *executables) {
        if (allow_path(rules, executables, LANDLOCK_ACCESS_FS_EXECUTE) < 0 ||
            allow_path(rules, "/lib64/ld-linux-x86-64.so.2", LANDLOCK_ACCESS_FS_EXECUTE) < 0) goto done;
    }
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) < 0) goto done;
    result = syscall(SYS_landlock_restrict_self, rules, 0);
done:
    close(rules);
    return result;
}

__attribute__((constructor)) static void native_application_guard(void) {
    char executable[PATH_MAX];
    ssize_t length = readlink("/proc/self/exe", executable, sizeof(executable) - 1);
    if (length < 0) return;
    executable[length] = 0;
    const char *name = strrchr(executable, '/');
    name = name ? name + 1 : executable;
    if (strcmp(name, "mscore4portable") && strcmp(name, "strawberry") &&
        strcmp(name, "strawberry-tagreader")) return;
    Dl_info location;
    char runtime[PATH_MAX];
    if (!dladdr((void *)native_application_guard, &location) ||
        !realpath(location.dli_fname, runtime)) _exit(125);
    char *slash = strrchr(runtime, '/');
    if (!slash || (size_t)(slash - runtime) + sizeof("/runtime") > sizeof(runtime)) _exit(125);
    strcpy(slash, "/runtime");
    if (protect_application(runtime) < 0) {
        fputs("application process isolation is unavailable\n", stderr);
        _exit(125);
    }
}
