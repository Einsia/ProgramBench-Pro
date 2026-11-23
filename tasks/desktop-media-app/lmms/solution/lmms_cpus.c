/* Report at most LMMS_CPUS online/configured processors to the LMMS process.
 *
 * LMMS 1.2.2 starts QThread::idealThreadCount() - 1 mixer workers, and Qt 5.9 takes that count from
 * sysconf(_SC_NPROCESSORS_ONLN), which reports every host processor regardless of the container's CPU quota or
 * affinity. Under a CPU quota the surplus workers spin and the cgroup is throttled. This preload caps the reported
 * count; it changes nothing else. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdlib.h>
#include <unistd.h>

static long limit(void)
{
	const char *value = getenv("LMMS_CPUS");
	if (!value || !*value)
		return 0;
	char *end;
	long n = strtol(value, &end, 10);
	return (*end == '\0' && n > 0) ? n : 0;
}

long sysconf(int name)
{
	static long (*real)(int);
	if (!real)
		real = (long (*)(int))dlsym(RTLD_NEXT, "sysconf");
	long result = real(name);
	if (name == _SC_NPROCESSORS_ONLN || name == _SC_NPROCESSORS_CONF) {
		long n = limit();
		if (n && (result <= 0 || result > n))
			result = n;
	}
	return result;
}

int get_nprocs(void)
{
	long n = sysconf(_SC_NPROCESSORS_ONLN);
	return n > 0 ? (int)n : 1;
}

int get_nprocs_conf(void)
{
	long n = sysconf(_SC_NPROCESSORS_CONF);
	return n > 0 ? (int)n : 1;
}
