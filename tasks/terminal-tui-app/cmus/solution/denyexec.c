#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/landlock.h>
#include <linux/seccomp.h>
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <sys/prctl.h>
#include <sys/select.h>
#include <sys/syscall.h>
#include <unistd.h>
#ifndef LANDLOCK_ACCESS_FS_REFER
#define LANDLOCK_ACCESS_FS_REFER (1ULL << 13)
#endif
#ifndef LANDLOCK_ACCESS_FS_TRUNCATE
#define LANDLOCK_ACCESS_FS_TRUNCATE (1ULL << 14)
#endif
static __thread int restricted;
static void fail(void){const char msg[]="Reference process restriction could not be installed.\n";write(2,msg,sizeof(msg)-1);_exit(125);}
static void allow(int fd,const char *path,uint64_t rights,int optional){
 int p=open(path,O_PATH|O_CLOEXEC); if(p<0){if(optional)return;fail();}
 struct landlock_path_beneath_attr a={.allowed_access=rights,.parent_fd=p};
 if(syscall(SYS_landlock_add_rule,fd,LANDLOCK_RULE_PATH_BENEATH,&a,0))fail(); close(p);
}
static void filesystem(void){
 if(restricted)return;
 restricted=1;
 int abi=syscall(SYS_landlock_create_ruleset,NULL,0,LANDLOCK_CREATE_RULESET_VERSION);
 if(abi<1)fail();
 uint64_t all=(1ULL<<13)-1;
 if(abi>=2)all|=LANDLOCK_ACCESS_FS_REFER;
 if(abi>=3)all|=LANDLOCK_ACCESS_FS_TRUNCATE;
 struct landlock_ruleset_attr a={.handled_access_fs=all};
 int fd=syscall(SYS_landlock_create_ruleset,&a,sizeof(a),0); if(fd<0)fail();
 const char *data=getenv("DATA_DIR"),*themes=getenv("CMUS_PUBLIC_THEMES");
 if(!data)fail();
 allow(fd,data,all & ~LANDLOCK_ACCESS_FS_EXECUTE,0);
 if(themes)allow(fd,themes,LANDLOCK_ACCESS_FS_READ_FILE|LANDLOCK_ACCESS_FS_READ_DIR,0);
 allow(fd,"/dev/null",LANDLOCK_ACCESS_FS_READ_FILE|LANDLOCK_ACCESS_FS_WRITE_FILE,0);
 allow(fd,"/dev/urandom",LANDLOCK_ACCESS_FS_READ_FILE,0);
 if(syscall(SYS_landlock_restrict_self,fd,0))fail(); close(fd);
}
__attribute__((constructor)) static void initialize(void){
 if(prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0))fail();
 struct sock_filter f[]={
 BPF_STMT(BPF_LD|BPF_W|BPF_ABS,4),
 BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,AUDIT_ARCH_X86_64,1,0),
 BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_KILL_PROCESS),
 BPF_STMT(BPF_LD|BPF_W|BPF_ABS,0),
 BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_execve,2,0),
 BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_execveat,1,0),
 BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW),
 BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM)};
 struct sock_fprog p={.len=sizeof(f)/sizeof(f[0]),.filter=f};
 if(prctl(PR_SET_SECCOMP,SECCOMP_MODE_FILTER,&p))fail();
}
struct thread_call{void*(*fn)(void*);void *arg;};
static void *run(void *v){struct thread_call c=*(struct thread_call*)v;free(v);filesystem();return c.fn(c.arg);}
int pthread_create(pthread_t *t,const pthread_attr_t *a,void*(*fn)(void*),void *v){
 int(*real)(pthread_t*,const pthread_attr_t*,void*(*)(void*),void*)=dlsym(RTLD_NEXT,"pthread_create");
 struct thread_call *c=malloc(sizeof(*c));if(!c)return ENOMEM; c->fn=fn;c->arg=v;
 int rc=real(t,a,run,c);if(rc)free(c);return rc;
}
int select(int n,fd_set *r,fd_set *w,fd_set *e,struct timeval *t){
 int(*real)(int,fd_set*,fd_set*,fd_set*,struct timeval*)=dlsym(RTLD_NEXT,"select");
 filesystem();return real(n,r,w,e,t);
}
int pselect(int n,fd_set *r,fd_set *w,fd_set *e,const struct timespec *t,const sigset_t *m){
 int(*real)(int,fd_set*,fd_set*,fd_set*,const struct timespec*,const sigset_t*)=dlsym(RTLD_NEXT,"pselect");
 filesystem();return real(n,r,w,e,t,m);
}
