#define _GNU_SOURCE
#include <sys/prctl.h>
#include <sys/resource.h>
#include <unistd.h>

/* A piped core handler can ignore RLIMIT_CORE; suppress dumpability as well.
 * This keeps a deliberately reproduced crash from invoking system Apport.
 * LD_PRELOAD repeats the guard after each nonprivileged exec in this test. */
__attribute__((constructor)) static void disable_core(void) {
    struct rlimit limit = {0, 0};
    if (setrlimit(RLIMIT_CORE, &limit) || prctl(PR_SET_DUMPABLE, 0, 0, 0, 0)) {
        static const char message[] = "Hardware_Test: cannot suppress core dumps\n";
        write(STDERR_FILENO, message, sizeof(message) - 1);
        _exit(125);
    }
}
