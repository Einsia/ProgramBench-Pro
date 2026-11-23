/* Preloaded into the Money Manager Ex processes of the reference installation (LD_PRELOAD in start.sh).
 *
 * The product evaluates amount fields and general reports with Lua and can hand URLs and files to other programs. This
 * guard keeps the Lua standard libraries closed, so that Lua can only calculate, and refuses to start any program except
 * the web content helpers of WebKit (the product's dashboards and reports) and the uname and lsb_release lookups of its
 * window title. Everything else is unchanged; the product is not modified.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <limits.h>
#include <spawn.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef struct lua_State lua_State;

static int allowed_program(const char *path)
{
    static const char *helpers[] = {
        "/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1/WebKitWebProcess",
        "/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1/WebKitNetworkProcess",
        "/usr/lib/x86_64-linux-gnu/webkit2gtk-4.1/WebKitGPUProcess"
    };
    char resolved[PATH_MAX];
    if (path == NULL || path[0] != '/' || realpath(path, resolved) == NULL) return 0;
    for (size_t i = 0; i < sizeof(helpers) / sizeof(helpers[0]); ++i)
        if (strcmp(resolved, helpers[i]) == 0) return 1;
    return 0;
}

static int allowed_command(const char *command)
{
    const char *args, *flags, *end;
    if (command == NULL) return 0;
    if (strncmp(command, "uname ", 6) == 0) {
        args = command + 6;
        flags = "asnrvmpio";
    } else if (strncmp(command, "lsb_release ", 12) == 0) {
        args = command + 12;
        flags = "aidsrc";
    } else {
        return 0;
    }
    end = command + strlen(command);
    /* wxWidgets appends this fixed stderr destination to its system-information queries. */
    const char suffix[] = " 2>/dev/null";
    if ((size_t)(end - args) >= sizeof(suffix) - 1 &&
        strcmp(end - (sizeof(suffix) - 1), suffix) == 0)
        end -= sizeof(suffix) - 1;
    /* Only fixed system-information options and the fixed stderr destination. */
    int options = 0;
    while (args < end) {
        while (args < end && *args == ' ') ++args;
        if (args == end) break;
        if (*args++ != '-' || args == end) return 0;
        while (args < end && *args != ' ')
            if (strchr(flags, *args++) == NULL) return 0;
        ++options;
    }
    return options > 0;
}

static void refuse(const char *what, const char *name)
{
    fprintf(stderr, "mmex_guard: %s refused: %.200s\n", what, name ? name : "");
    errno = EPERM;
}

int execve(const char *path, char *const argv[], char *const envp[])
{
    static int (*next)(const char *, char *const[], char *const[]);
    if (!next) next = (int (*)(const char *, char *const[], char *const[]))dlsym(RTLD_NEXT, "execve");
    if (!allowed_program(path)) { refuse("program start", path); return -1; }
    return next(path, argv, envp);
}

int execv(const char *path, char *const argv[])
{
    static int (*next)(const char *, char *const[]);
    if (!next) next = (int (*)(const char *, char *const[]))dlsym(RTLD_NEXT, "execv");
    if (!allowed_program(path)) { refuse("program start", path); return -1; }
    return next(path, argv);
}

int execvp(const char *file, char *const argv[])
{
    static int (*next)(const char *, char *const[]);
    if (!next) next = (int (*)(const char *, char *const[]))dlsym(RTLD_NEXT, "execvp");
    if (!allowed_program(file)) { refuse("program start", file); return -1; }
    return next(file, argv);
}

int execvpe(const char *file, char *const argv[], char *const envp[])
{
    static int (*next)(const char *, char *const[], char *const[]);
    if (!next) next = (int (*)(const char *, char *const[], char *const[]))dlsym(RTLD_NEXT, "execvpe");
    if (!allowed_program(file)) { refuse("program start", file); return -1; }
    return next(file, argv, envp);
}

int execl(const char *path, const char *arg, ...)
{
    (void)arg;
    refuse("program start", path);
    return -1;
}

int execlp(const char *file, const char *arg, ...)
{
    (void)arg;
    refuse("program start", file);
    return -1;
}

int execle(const char *path, const char *arg, ...)
{
    (void)arg;
    refuse("program start", path);
    return -1;
}

int posix_spawn(pid_t *pid, const char *path, const posix_spawn_file_actions_t *actions,
                const posix_spawnattr_t *attributes, char *const argv[], char *const envp[])
{
    static int (*next)(pid_t *, const char *, const posix_spawn_file_actions_t *, const posix_spawnattr_t *,
                       char *const[], char *const[]);
    if (!next) next = (int (*)(pid_t *, const char *, const posix_spawn_file_actions_t *, const posix_spawnattr_t *,
                               char *const[], char *const[]))dlsym(RTLD_NEXT, "posix_spawn");
    if (!allowed_program(path)) { refuse("program start", path); return EPERM; }
    return next(pid, path, actions, attributes, argv, envp);
}

int posix_spawnp(pid_t *pid, const char *file, const posix_spawn_file_actions_t *actions,
                 const posix_spawnattr_t *attributes, char *const argv[], char *const envp[])
{
    static int (*next)(pid_t *, const char *, const posix_spawn_file_actions_t *, const posix_spawnattr_t *,
                       char *const[], char *const[]);
    if (!next) next = (int (*)(pid_t *, const char *, const posix_spawn_file_actions_t *, const posix_spawnattr_t *,
                               char *const[], char *const[]))dlsym(RTLD_NEXT, "posix_spawnp");
    if (!allowed_program(file)) { refuse("program start", file); return EPERM; }
    return next(pid, file, actions, attributes, argv, envp);
}

int system(const char *command)
{
    refuse("command", command);
    return -1;
}

FILE *popen(const char *command, const char *type)
{
    static FILE *(*next)(const char *, const char *);
    if (!next) next = (FILE *(*)(const char *, const char *))dlsym(RTLD_NEXT, "popen");
    if (!allowed_command(command)) { refuse("command", command); return NULL; }
    return next(command, type);
}

/* Lua evaluates the amount fields and general reports. Without its standard libraries a chunk can only calculate: no
 * files, no programs, no loading of other code. */
void luaL_openlibs(lua_State *state)
{
    (void)state;
}
