#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/landlock.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

static void fail(const char *s) { perror(s); _exit(126); }
static void allow(int rules,const char *path,uint64_t rights,int optional) {
    if(!path || !*path) fail("missing instance directory");
    int fd=open(path,O_PATH|O_CLOEXEC);
    if(fd<0) { if(optional && errno==ENOENT)return;fail("sandbox path"); }
    struct stat st;
    if(fstat(fd,&st))fail("sandbox stat");
    if(!S_ISDIR(st.st_mode))rights&=~LANDLOCK_ACCESS_FS_READ_DIR;
    struct landlock_path_beneath_attr rule={.allowed_access=rights,.parent_fd=fd};
    if(syscall(SYS_landlock_add_rule,rules,LANDLOCK_RULE_PATH_BENEATH,&rule,0))fail("sandbox rule");
    close(fd);
}

__attribute__((constructor)) static void confine(void) {
    unsetenv("LD_PRELOAD");
    int abi=syscall(SYS_landlock_create_ruleset,NULL,0,LANDLOCK_CREATE_RULESET_VERSION);
    if(abi<1)fail("sandbox unavailable");
    uint64_t all=(1ULL<<13)-1,read=LANDLOCK_ACCESS_FS_READ_FILE|LANDLOCK_ACCESS_FS_READ_DIR;
    if(abi>=2)all|=1ULL<<13; /* REFER */
    if(abi>=3)all|=1ULL<<14; /* TRUNCATE */
    struct landlock_ruleset_attr attr={.handled_access_fs=all};
    int fd=syscall(SYS_landlock_create_ruleset,&attr,sizeof(attr),0);
    if(fd<0)fail("sandbox create");
    const char *ro[]={"/usr/lib","/usr/share/terminfo","/etc/terminfo","/usr/share/git-core",
                      "/etc/ld.so.cache","/etc/passwd","/etc/nsswitch.conf","/etc/localtime",NULL};
    for(int i=0;ro[i];i++)allow(fd,ro[i],read,1);
    const char *dirs[]={"DATA_DIR","HOME","TMPDIR","XDG_CACHE_HOME","XDG_CONFIG_HOME",NULL};
    for(int i=0;dirs[i];i++)allow(fd,getenv(dirs[i]),all&~LANDLOCK_ACCESS_FS_EXECUTE,0);
    allow(fd,"/usr/bin/git",LANDLOCK_ACCESS_FS_EXECUTE|LANDLOCK_ACCESS_FS_READ_FILE,0);
    /* Git's built-in dispatch may use the installed git-* entry points. */
    allow(fd,"/usr/lib/git-core/git",LANDLOCK_ACCESS_FS_EXECUTE|LANDLOCK_ACCESS_FS_READ_FILE,0);
    allow(fd,"/lib64/ld-linux-x86-64.so.2",LANDLOCK_ACCESS_FS_EXECUTE|LANDLOCK_ACCESS_FS_READ_FILE,0);
    allow(fd,"/dev/pts",read|LANDLOCK_ACCESS_FS_WRITE_FILE,0);
    const char *devices[]={"/dev/tty","/dev/null","/dev/urandom",NULL};
    for(int i=0;devices[i];i++)allow(fd,devices[i],LANDLOCK_ACCESS_FS_READ_FILE|LANDLOCK_ACCESS_FS_WRITE_FILE,0);
    if(prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)||syscall(SYS_landlock_restrict_self,fd,0))fail("sandbox apply");
    close(fd);
}
