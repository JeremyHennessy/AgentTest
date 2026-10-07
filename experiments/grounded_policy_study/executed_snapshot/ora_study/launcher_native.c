/* Review-only integrated launcher. Every payload below is authored arithmetic.
 * No simulator, API, policy, Core, selector, network or arbitrary-command path.
 * This trusted-source resource fixture is NOT a hostile-code sandbox.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <poll.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define MIB (1024ULL * 1024ULL)
#define RESERVE MIB
#define STREAM_CAP 16384U
#define REPORT_CAP 8192U
#define FINAL_OFFSET 65536
#define MAX_WALL_MS 850000ULL
#define REVIEWED_WALL_MS 1500000ULL
#define MAGIC 0x4f524131U
#ifndef ORA_PYTHON_PATH
#define ORA_PYTHON_PATH ""
#endif
#ifndef ORA_PY_CONTROLLER_SOURCE
#define ORA_PY_CONTROLLER_SOURCE ""
#endif
#ifndef ORA_PACKAGE_ROOT
#define ORA_PACKAGE_ROOT ""
#endif
#ifndef ORA_MANIFEST_PATH
#define ORA_MANIFEST_PATH ""
#endif
#ifndef ORA_MANIFEST_SHA256
#define ORA_MANIFEST_SHA256 ""
#endif
#ifndef ORA_CHILD_EXE
#define ORA_CHILD_EXE ""
#endif
#ifndef ORA_NATIVE_FIXTURE_BINDING
#define ORA_NATIVE_FIXTURE_BINDING 0
#endif
#ifndef ORA_FIXTURE_PROFILE_PATH
#define ORA_FIXTURE_PROFILE_PATH ""
#endif
#ifndef ORA_FIXTURE_PROFILE_SHA256
#define ORA_FIXTURE_PROFILE_SHA256 ""
#endif
#ifndef ORA_FIXTURE_OUTPUT_ROOT
#define ORA_FIXTURE_OUTPUT_ROOT ""
#endif

/* Not a build argument, CLI option or environment switch. A separately
 * reviewed source/profile decision is required to change this guard. */
static const int native_fixture_admission_reviewed = 1;
static const char reviewed_native_fixture_profile_sha256[] = "608522ab51895175a5eb2a835c04d02894622481a590dc1d69a49b231adc8bda";

static char out_buf[STREAM_CAP], err_buf[STREAM_CAP];
static volatile sig_atomic_t interrupted;
static volatile sig_atomic_t expiry_group = -1;
static timer_t expiry_timer;
static int event_json;
static int native_fixture_mode;
static void expire(int n) {
    (void)n;
    sig_atomic_t group=expiry_group;
    if(group>0) (void)kill(-(pid_t)group,SIGKILL);
    _exit(124);
}
static int arm_expiry(uint64_t deadline) {
    struct sigaction action={0};action.sa_handler=expire;sigemptyset(&action.sa_mask);
    if(sigaction(SIGALRM,&action,NULL)||sigaction(SIGUSR2,&action,NULL)) return -1;
    sigset_t unblocked;sigemptyset(&unblocked);sigaddset(&unblocked,SIGUSR2);sigaddset(&unblocked,SIGALRM);
    if(sigprocmask(SIG_UNBLOCK,&unblocked,NULL)) return -1;
    struct sigevent notification={0};
    notification.sigev_notify=SIGEV_SIGNAL;notification.sigev_signo=SIGUSR2;
    if(timer_create(CLOCK_BOOTTIME,&notification,&expiry_timer)) return -1;
    struct itimerspec t={0};
    t.it_value.tv_sec=(time_t)(deadline/1000000000ULL);
    t.it_value.tv_nsec=(long)(deadline%1000000000ULL);
    return timer_settime(expiry_timer,TIMER_ABSTIME,&t,NULL);
}
static int one_cpu(void) {
    cpu_set_t available,selected;CPU_ZERO(&available);CPU_ZERO(&selected);
    if(sched_getaffinity(0,sizeof available,&available)) return -1;
    for(int i=0;i<CPU_SETSIZE;i++) if(CPU_ISSET(i,&available)) {
        CPU_SET(i,&selected);
        return sched_setaffinity(0,sizeof selected,&selected) ? -1 : i;
    }
    return -1;
}
static int affinity_cpu(void) {
    cpu_set_t mask;CPU_ZERO(&mask);
    if(sched_getaffinity(0,sizeof mask,&mask)||CPU_COUNT(&mask)!=1) return -1;
    for(int i=0;i<CPU_SETSIZE;i++)if(CPU_ISSET(i,&mask))return i;
    return -1;
}
static void on_signal(int n) { interrupted = n; }
static uint64_t now_ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_BOOTTIME, &t)) return 0;
    return (uint64_t)t.tv_sec * 1000000000ULL + (uint64_t)t.tv_nsec;
}
static int limit(int which, rlim_t soft, rlim_t hard) {
    struct rlimit r = {soft, hard};
    return setrlimit(which, &r);
}
static int limits(unsigned as_mib, unsigned cpu, int worker) {
    rlim_t cpu_hard=native_fixture_mode ? 850 : cpu;
    rlim_t file_hard=native_fixture_mode ? 2*MIB : RESERVE;
    rlim_t file_soft=native_fixture_mode && as_mib!=32 ? 2*MIB : RESERVE;
    return limit(RLIMIT_AS, as_mib*MIB, 384*MIB) ||
        limit(RLIMIT_CPU, cpu, cpu_hard) || limit(RLIMIT_CORE, 0, 0) ||
        limit(RLIMIT_FSIZE, file_soft, file_hard) || limit(RLIMIT_NOFILE, 32, 32) ||
        (worker && limit(RLIMIT_NPROC, 1, 1));
}
static int write_all(int fd, const void *p, size_t n) {
    const char *q = p;
    while (n) {
        ssize_t k = write(fd, q, n);
        if (k < 0 && errno == EINTR) continue;
        if (k <= 0) return -1;
        q += k; n -= (size_t)k;
    }
    return 0;
}
static int pwrite_all(int fd, const void *p, size_t n, off_t off) {
    const char *q = p;
    while (n) {
        ssize_t k = pwrite(fd, q, n, off);
        if (k < 0 && errno == EINTR) continue;
        if (k <= 0) return -1;
        q += k; off += k; n -= (size_t)k;
    }
    return 0;
}
static int read_small(const char *path, char *buf, size_t cap) {
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return -1;
    ssize_t n = read(fd, buf, cap-1);
    close(fd);
    if (n <= 0 || (size_t)n == cap-1) return -1;
    buf[n] = 0;
    return 0;
}
/* proc stat field22 is a floor-rounded, boot-relative process birth time.
 * Linux proc uses start_boottime, including time-namespace offsets. We use
 * CLOCK_BOOTTIME throughout, a monotonic clock that also counts suspend.
 */
static uint64_t birth_ns(void) {
    char buf[4096], *last, *save = NULL, *tok;
    if (read_small("/proc/self/stat", buf, sizeof buf)) return 0;
    last = strrchr(buf, ')');
    if (!last || last[1] != ' ') return 0;
    unsigned field = 3;
    for (tok = strtok_r(last+2, " ", &save); tok; tok = strtok_r(NULL, " ", &save), field++) {
        if (field == 22) {
            char *end;
            unsigned long long ticks = strtoull(tok, &end, 10);
            long hz = sysconf(_SC_CLK_TCK);
            if (*end || hz <= 0) return 0;
            return ticks * (1000000000ULL / (uint64_t)hz);
        }
    }
    return 0;
}
static int source_checks(void) {
    char buf[16384];
    if (geteuid() == 0 || getuid() != geteuid() || getgid() != getegid()) return -1;
    if (read_small("/proc/self/status", buf, sizeof buf)) return -1;
    char *threads=strstr(buf,"Threads:");
    if(!threads || strtol(threads+8,NULL,10)!=1) return -1;
    const char *names[] = {"CapEff:", "CapPrm:", "CapAmb:"};
    for (unsigned i = 0; i < 3; i++) {
        char *p = strstr(buf, names[i]);
        if (!p || strtoull(p + strlen(names[i]), NULL, 16)) return -1;
    }
    /* No dynamically chosen executable is permitted by this fixture. This is
     * an executable-identity check, not a complete loaded-source freeze. */
    int fd = open("/proc/self/exe", O_RDONLY | O_CLOEXEC);
    struct stat st;
    if (fd < 0) return -1;
    int ok = !fstat(fd, &st) && S_ISREG(st.st_mode) && st.st_uid == geteuid();
    close(fd);
    return ok ? 0 : -1;
}
static int mode_valid(const char *mode) {
    const char *modes[] = {"success", "source_failure", "startup_failure", "child_failure",
        "controller_failure", "controller_orphan", "controller_early_death", "hang", "cpu", "stdout_flood", "stderr_flood",
        "allocation", "nproc", "report_failure", "seal_failure", "report_hang", "finalize_hang", "finalize_blocked_write", "supervisor_hang", "python_controller", "native_fixture_controller"};
    for (unsigned i = 0; i < sizeof modes/sizeof *modes; i++) if (!strcmp(mode, modes[i])) return 1;
    return 0;
}
struct event {
    uint32_t magic;
    int phase, pid, value, code, affinity_cpu;
    uint64_t as_soft, as_hard, cpu_soft, cpu_hard, nproc_soft;
    uint64_t user_ns, system_ns;
};
static void emit_event(int fd, int phase, int value, int code) {
    struct event e = {.magic=MAGIC, .phase=phase, .pid=(int)getpid(), .value=value, .code=code, .affinity_cpu=affinity_cpu()};
    struct rlimit r;
    if (!getrlimit(RLIMIT_AS, &r)) { e.as_soft=r.rlim_cur; e.as_hard=r.rlim_max; }
    if (!getrlimit(RLIMIT_CPU, &r)) { e.cpu_soft=r.rlim_cur; e.cpu_hard=r.rlim_max; }
    if (!getrlimit(RLIMIT_NPROC, &r)) e.nproc_soft=r.rlim_cur;
    struct rusage u;
    if (!getrusage(RUSAGE_SELF, &u)) {
        e.user_ns=(uint64_t)u.ru_utime.tv_sec*1000000000ULL+(uint64_t)u.ru_utime.tv_usec*1000;
        e.system_ns=(uint64_t)u.ru_stime.tv_sec*1000000000ULL+(uint64_t)u.ru_stime.tv_usec*1000;
    }
    if(event_json) {
        char line[768];
        int n=snprintf(line,sizeof line,
            "{\"phase\":%d,\"pid\":%d,\"value\":%d,\"code\":%d,"
            "\"as_soft\":%" PRIu64 ",\"as_hard\":%" PRIu64 ",\"cpu_soft\":%" PRIu64 ",\"cpu_hard\":%" PRIu64 ","
            "\"nproc_soft\":%" PRIu64 ",\"affinity_cpu\":%d,\"user_ns\":%" PRIu64 ",\"system_ns\":%" PRIu64 "}\n",
            e.phase,e.pid,e.value,e.code,e.as_soft,e.as_hard,e.cpu_soft,e.cpu_hard,e.nproc_soft,e.affinity_cpu,e.user_ns,e.system_ns);
        if(n<=0 || (size_t)n>=sizeof line || write_all(fd,line,(size_t)n)) _exit(88);
    } else if (write_all(fd, &e, sizeof e)) _exit(88);
}
static int parse_json_event(const char *line, struct event *e) {
    int consumed=0;
    memset(e,0,sizeof *e);e->magic=MAGIC;
    int n=sscanf(line,
        "{\"phase\":%d,\"pid\":%d,\"value\":%d,\"code\":%d,"
        "\"as_soft\":%" SCNu64 ",\"as_hard\":%" SCNu64 ",\"cpu_soft\":%" SCNu64 ",\"cpu_hard\":%" SCNu64 ","
        "\"nproc_soft\":%" SCNu64 ",\"affinity_cpu\":%d,\"user_ns\":%" SCNu64 ",\"system_ns\":%" SCNu64 "}%n",
        &e->phase,&e->pid,&e->value,&e->code,&e->as_soft,&e->as_hard,&e->cpu_soft,&e->cpu_hard,&e->nproc_soft,&e->affinity_cpu,&e->user_ns,&e->system_ns,&consumed);
    return n==12 && consumed>0 && line[consumed]=='\n' && line[consumed+1]=='\0' ? 0 : -1;
}
static void hang(void) { for (;;) pause(); }
static void worker(const char *mode, int eventfd, int report, pid_t creator) {
    if (!strcmp(mode,"controller_early_death")) {
        struct timespec t={0,50000000};nanosleep(&t,NULL);
    }
    if (prctl(PR_SET_PDEATHSIG, SIGKILL)) _exit(80);
    if (getppid() != creator) { emit_event(eventfd,8,(int)creator,(int)getppid());_exit(74); }
    if (limits(384, report ? 10 : 1, 1) || affinity_cpu()<0) _exit(80);
    emit_event(eventfd, report ? 4 : 2, 0, 0);
    if (report) {
        if (!strcmp(mode, "report_hang")) hang();
        if (!strcmp(mode, "report_failure")) _exit(65);
        (void)write_all(STDOUT_FILENO, "authored reporter: zero scientific rows\n", sizeof("authored reporter: zero scientific rows\n")-1);
        _exit(0);
    }
    if (!strcmp(mode, "hang") || !strcmp(mode, "controller_orphan") || !strcmp(mode,"supervisor_hang")) hang();
    if (!strcmp(mode, "cpu")) { volatile uint64_t n=0; for (;;) n++; }
    if (!strcmp(mode, "stdout_flood") || !strcmp(mode, "stderr_flood")) {
        char x[4096]; memset(x, 'x', sizeof x);
        int fd=!strcmp(mode, "stdout_flood") ? STDOUT_FILENO : STDERR_FILENO;
        for (;;) if (write_all(fd, x, sizeof x)) _exit(67);
    }
    if (!strcmp(mode, "allocation")) {
        void *p=mmap(NULL, 512*MIB, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
        if (p != MAP_FAILED) { munmap(p, 512*MIB); _exit(66); }
    }
    if (!strcmp(mode, "nproc")) {
        pid_t p=fork();
        if (p == 0) _exit(68);
        if (p > 0) { (void)waitpid(p, NULL, 0); _exit(68); }
        if (errno != EAGAIN) _exit(69);
    }
    if (!strcmp(mode, "child_failure")) _exit(64);
    (void)write_all(STDOUT_FILENO, "authored fixture: 2 + 3 = 5\n", sizeof("authored fixture: 2 + 3 = 5\n")-1);
    _exit(0);
}
static int wait_one(pid_t pid) {
    int status;
    while (waitpid(pid, &status, 0) < 0) if (errno != EINTR) return 255;
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128+WTERMSIG(status);
}
static void controller(const char *mode, int eventfd, pid_t creator, uint64_t deadline) {
    unsigned controller_cpu=native_fixture_mode ? 850 : 10;
    if (setpgid(0,0) || prctl(PR_SET_PDEATHSIG, SIGKILL) || getppid()!=creator || limits(96,controller_cpu,0) || affinity_cpu()<0) _exit(79);
    emit_event(eventfd, 1, 0, 0);
    if (!strcmp(mode,"controller_failure")) _exit(63);
    if(!strcmp(mode,"python_controller") || native_fixture_mode) {
        if(!*ORA_PYTHON_PATH || !*ORA_PY_CONTROLLER_SOURCE || !*ORA_MANIFEST_SHA256) _exit(73);
        if(eventfd!=3) { if(dup2(eventfd,3)<0) _exit(73);close(eventfd); }
        if(fcntl(3,F_SETFD,0)) _exit(73);
        char *args[]={(char *)ORA_PYTHON_PATH,"-I","-S","-B","-c",(char *)ORA_PY_CONTROLLER_SOURCE,NULL};
        char deadline_environment[64];
        int n=snprintf(deadline_environment,sizeof deadline_environment,"ORA_LAUNCHER_DEADLINE_NS=%" PRIu64,deadline);
        if(n<=0 || (size_t)n>=sizeof deadline_environment) _exit(73);
        char *environment[]={"LANG=C","LC_ALL=C",
            "ORA_LAUNCHER_PACKAGE_ROOT=" ORA_PACKAGE_ROOT,
            "ORA_LAUNCHER_MANIFEST_PATH=" ORA_MANIFEST_PATH,
            "ORA_LAUNCHER_MANIFEST_SHA256=" ORA_MANIFEST_SHA256,
            "ORA_LAUNCHER_CHILD_EXE=" ORA_CHILD_EXE,
            "ORA_LAUNCHER_PROFILE_PATH=" ORA_FIXTURE_PROFILE_PATH,
            "ORA_LAUNCHER_PROFILE_SHA256=" ORA_FIXTURE_PROFILE_SHA256,
            deadline_environment,NULL};
        execve(ORA_PYTHON_PATH,args,environment);
        _exit(73);
    }
    pid_t own_pid=getpid();
    pid_t p=fork();
    if (p < 0) _exit(78);
    if (p == 0) worker(mode,eventfd,0,own_pid);
    if (!strcmp(mode,"controller_early_death")) _exit(61);
    emit_event(eventfd, 5, (int)p, 0);
    if (!strcmp(mode,"controller_orphan")) {
        /* Wait for authored child startup, then die while it remains alive. */
        struct timespec t={0,30000000}; nanosleep(&t,NULL); _exit(62);
    }
    int code=wait_one(p);
    emit_event(eventfd,3,0,code);
    if (code) _exit(code);
    p=fork();
    if (p < 0) _exit(77);
    if (p == 0) worker(mode,eventfd,1,own_pid);
    emit_event(eventfd,6,(int)p,0);
    code=wait_one(p);
    emit_event(eventfd,7,0,code);
    _exit(code);
}
static int output_file(int dirfd, const char *name, const void *buf, size_t size) {
    int fd=openat(dirfd,name,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    if (fd<0) return -1;
    int ok=write_all(fd,buf,size) || fsync(fd);
    if (close(fd)) ok=-1;
    return ok;
}
static int reserve_status(int dirfd, uint64_t birth, uint64_t deadline, int cpu) {
    int fd=openat(dirfd,"launcher.status",O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    if (fd<0) return -1;
    char initial[1024];
    int n=snprintf(initial,sizeof initial,
        "{\"schema\":\"ora.launcher.stub.v1\",\"classification\":\"incomplete\",\"phase\":\"startup\","
        "\"reason\":\"terminal_record_not_committed\",\"science_transition_invocations\":0,"
        "\"scientific_execution_allowed\":false,\"stub_counts_known\":false,\"kernel_expiry_armed\":true,"
        "\"window_start_ns\":%" PRIu64 ",\"deadline_ns\":%" PRIu64 ",\"selected_cpu\":%d,"
        "\"no_live_launcher_helper\":true,\"internal_wall_ceiling_ms\":850000}\n",birth,deadline,cpu);
    if(n<=0 || (size_t)n>=sizeof initial || write_all(fd,initial,(size_t)n) || fsync(fd) || fsync(dirfd)) { close(fd);return -1; }
    /* Make the fallback usable before filling the remaining reserved bytes. */
    char zeros[4096]={0};size_t left=RESERVE-(size_t)n;
    while(left) {
        size_t chunk=left<sizeof zeros?left:sizeof zeros;
        if(write_all(fd,zeros,chunk)) { close(fd);return -1; }
        left-=chunk;
    }
    if(fsync(fd)||fsync(dirfd)) { close(fd);return -1; }
    return fd;
}
int main(int argc,char **argv) {
    if(argc==3 && !strcmp(argv[1],"--authored-child")) {
        char *end;long creator=strtol(argv[2],&end,10);
        if(*end || creator<=0 || creator>INT_MAX) return 90;
        event_json=1;
        worker("success",3,0,(pid_t)creator);
    }
    uint64_t entry=now_ns(), birth=birth_ns();
    const char *classification="incomplete", *phase="startup", *reason="startup_not_completed";
    uint64_t wall_ms=0, cleanup_ms=0, window_start=0;
    int selected_cpu=-1;
    int dirfd=-1, reservefd=-1, status=0, reaped=0, killed=0, error=0;
    size_t outlen=0, errlen=0, eventlen=0;
    unsigned char eventbuf[1025];
    int python_mode=0,python_ready=0,event_records=0,python_nulls=0;
    int dispatches=0,active_child=0,declared_child=0,worker_failure_seen=0;
    int transition_receipt=0,selection_receipt=0;
    int fixture_transitions=0,fixture_api_workers=0,fixture_selections=0,fixture_producers=0;
    struct event controller_e={.affinity_cpu=-1}, worker_e={.affinity_cpu=-1}, reporter_e={.affinity_cpu=-1};
    int worker_count=0, reporter_count=0, worker_code=-1, reporter_code=-1, early_parent_death_guard=0;
    pid_t controller_pid=-1, worker_pid=-1, reporter_pid=-1;
    int op[2]={-1,-1},ep[2]={-1,-1},vp[2]={-1,-1};
    int streams_open=0;
    if (argc!=4 || strlen(argv[1])>PATH_MAX-1 || strlen(argv[2])>32 || strlen(argv[3])>7 || !mode_valid(argv[2])) return 90;
    native_fixture_mode=!strcmp(argv[2],"native_fixture_controller");
    python_mode=!strcmp(argv[2],"python_controller") || native_fixture_mode;event_json=python_mode;
    char *end; errno=0; wall_ms=strtoull(argv[3],&end,10);
    if (errno || *end || wall_ms<250 || wall_ms>MAX_WALL_MS) return 90;
    if(native_fixture_mode && wall_ms!=MAX_WALL_MS) return 90;
    window_start=birth;
    if(!window_start) return 90;
    cleanup_ms=wall_ms<5000 ? wall_ms/2 : 2000;
    if (!birth || birth>entry || !entry) return 91;
    /* Floor-rounded procfs birth is conservatively before actual entry. */
    uint64_t deadline=window_start+wall_ms*1000000ULL;
    uint64_t stop=deadline-cleanup_ms*1000000ULL;
    /* Kernel-owned absolute timer precedes all source validation, reserve
     * setup, child startup and finalization. Never disarm it before exit. */
    if(arm_expiry(deadline)) return 98;
    if(now_ns()>=deadline) expire(0);
    /* Ambient credentials, loader controls and application configuration do
     * not cross this point. run_launcher also execs with this exact env. */
    if (clearenv() || setenv("LANG","C",1) || setenv("LC_ALL","C",1)) return 92;
    if (limits(32,10,0) || (selected_cpu=one_cpu())<0) return 93;
    if (prctl(PR_SET_CHILD_SUBREAPER,1)) return 94;
    struct sigaction sa={0};sa.sa_handler=on_signal;sigemptyset(&sa.sa_mask);
    if (sigaction(SIGTERM,&sa,NULL) || sigaction(SIGINT,&sa,NULL)) return 94;
    if (mkdir(argv[1],0700)) return 95; /* Never reuse, reset, retry or choose another path. */
    dirfd=open(argv[1],O_RDONLY|O_DIRECTORY|O_CLOEXEC|O_NOFOLLOW);
    if (dirfd<0 || (reservefd=reserve_status(dirfd,window_start,deadline,selected_cpu))<0) return 96;
    phase="source_validation";
    if (!strcmp(argv[2],"source_failure") || source_checks()) { classification="invalid";reason="source_validation_failed";goto finish; }
    if(python_mode && ORA_NATIVE_FIXTURE_BINDING && !native_fixture_mode) {
        classification="invalid";reason="compiled_controller_role_mismatch";goto finish;
    }
    if(native_fixture_mode) {
        if(!ORA_NATIVE_FIXTURE_BINDING || strcmp(argv[1],ORA_FIXTURE_OUTPUT_ROOT)) {
            classification="invalid";reason="fixed_fixture_profile_mismatch";goto finish;
        }
        if(!native_fixture_admission_reviewed || strlen(reviewed_native_fixture_profile_sha256)!=64 ||
           strcmp(reviewed_native_fixture_profile_sha256,ORA_FIXTURE_PROFILE_SHA256)) {
            classification="invalid";reason="native_fixture_source_profile_review_pending";goto finish;
        }
    }
    if (now_ns()>=stop) { reason="startup_deadline";goto finish; }
    phase="worker_startup";
    if (!strcmp(argv[2],"startup_failure")) { reason="injected_startup_failure";goto finish; }
    if (pipe2(op,O_CLOEXEC) || pipe2(ep,O_CLOEXEC) || pipe2(vp,O_CLOEXEC)) { reason="pipe_creation_failed";goto finish; }
    pid_t outer_pid=getpid();
    controller_pid=fork();
    if (controller_pid<0) { reason="controller_fork_failed";goto finish; }
    if (controller_pid==0) {
        close(op[0]);close(ep[0]);close(vp[0]);close(dirfd);close(reservefd);
        if (dup2(op[1],STDOUT_FILENO)<0 || dup2(ep[1],STDERR_FILENO)<0) _exit(76);
        close(op[1]);close(ep[1]);
        /* Only the bounded binary event stream and stdout/stderr survive. */
        int nullfd=open("/dev/null",O_RDONLY|O_CLOEXEC);
        if (nullfd<0 || dup2(nullfd,STDIN_FILENO)<0) _exit(75);
        if(nullfd!=STDIN_FILENO)close(nullfd);
        controller(argv[2],vp[1],outer_pid,deadline);
    }
    expiry_group=(sig_atomic_t)controller_pid;
    if (setpgid(controller_pid,controller_pid) && errno!=EACCES && errno!=ESRCH) { reason="process_group_setup_failed";goto stop_children; }
    close(op[1]);op[1]=-1;close(ep[1]);ep[1]=-1;close(vp[1]);vp[1]=-1;
    if (fcntl(op[0],F_SETFL,O_NONBLOCK) || fcntl(ep[0],F_SETFL,O_NONBLOCK) || fcntl(vp[0],F_SETFL,O_NONBLOCK)) { reason="nonblocking_setup_failed";goto stop_children; }
    streams_open=3; phase="worker";
    if(!strcmp(argv[2],"supervisor_hang")) hang();
    if (!strcmp(argv[2],"controller_early_death")) {
        /* Force death before child installs PDEATHSIG, without delaying the
         * normal path. The child must reject its new parent, not adopt it. */
        struct timespec t={0,100000000};nanosleep(&t,NULL);
    }
    while (streams_open) {
        if (interrupted || now_ns()>=stop) { reason=interrupted ? "external_termination" : "wall_budget_finalization_reserve";goto stop_children; }
        struct pollfd p[3]={{op[0],POLLIN,0},{ep[0],POLLIN,0},{vp[0],POLLIN,0}};
        if (poll(p,3,10)<0 && errno!=EINTR) { reason="poll_failed";goto stop_children; }
        for (int i=0;i<3;i++) {
            if (p[i].fd<0 || !(p[i].revents&(POLLIN|POLLHUP|POLLERR))) continue;
            char block[4096];ssize_t n=read(p[i].fd,block,sizeof block);
            if (n<0 && (errno==EAGAIN || errno==EINTR)) continue;
            if (n<=0) { close(p[i].fd);if(i==0)op[0]=-1;else if(i==1)ep[0]=-1;else vp[0]=-1;streams_open--;continue; }
            if(i<2) {
                size_t *used=i==0?&outlen:&errlen;char *buf=i==0?out_buf:err_buf;
                size_t room=STREAM_CAP-*used, copy=(size_t)n<room?(size_t)n:room;
                memcpy(buf+*used,block,copy);*used+=copy;
                if(copy!=(size_t)n) { reason=i==0?"stdout_cap":"stderr_cap";goto stop_children; }
            } else {
                for(ssize_t j=0;j<n;j++) {
                    if(eventlen>=1024) { classification="invalid";reason="event_line_overflow";goto stop_children; }
                    eventbuf[eventlen++]=(unsigned char)block[j];
                    if(python_mode ? block[j]=='\n' : eventlen==sizeof(struct event)) {
                        struct event e;
                        if(python_mode) {
                            eventbuf[eventlen]=0;
                            if(parse_json_event((const char *)eventbuf,&e)) { classification="invalid";reason="malformed_json_event";goto stop_children; }
                        } else memcpy(&e,eventbuf,sizeof e);
                        eventlen=0;
                        if(++event_records>(native_fixture_mode?64:16)) { classification="invalid";reason="event_inventory_exceeded";goto stop_children; }
                        if(e.magic!=MAGIC) { classification="invalid";reason="malformed_event";goto stop_children; }
                        if(e.phase==1 || e.phase==9 || (native_fixture_mode && (e.phase==10 || e.phase==11))) {
                            unsigned expected_controller_cpu=native_fixture_mode?850:10;
                            if(e.pid!=(int)controller_pid || e.as_soft!=96*MIB || e.as_hard!=384*MIB ||
                               e.cpu_soft!=expected_controller_cpu || e.cpu_hard!=expected_controller_cpu || e.affinity_cpu!=selected_cpu) {
                                classification="invalid";reason="controller_limit_event_mismatch";goto stop_children;
                            }
                        }
                        if(e.phase==2 || e.phase==4) {
                            unsigned expected_cpu=native_fixture_mode?850:(e.phase==2?1:10);
                            if(e.as_soft!=384*MIB || e.as_hard!=384*MIB || e.cpu_soft!=expected_cpu ||
                               e.cpu_hard!=expected_cpu || e.nproc_soft!=1 || e.affinity_cpu!=selected_cpu) {
                                classification="invalid";reason="child_limit_event_mismatch";goto stop_children;
                            }
                        }
                        if(e.phase==1)controller_e=e;
                        else if(e.phase==2) {
                            if(native_fixture_mode) {
                                if(active_child || transition_receipt || selection_receipt ||
                                   (declared_child && declared_child!=e.pid)) {
                                    classification="invalid";reason="overlapping_or_late_child";goto stop_children;
                                }
                                active_child=e.pid;
                            }
                            worker_e=e;worker_count++;
                        }
                        else if(e.phase==3) {
                            if(native_fixture_mode) {
                                if(e.pid!=(int)controller_pid || !declared_child ||
                                   (active_child && active_child!=declared_child) || (!active_child && !e.code)) {
                                    classification="invalid";reason="unmatched_child_completion";goto stop_children;
                                }
                                active_child=0;declared_child=0;
                                if(e.code)worker_failure_seen=1;
                            }
                            worker_code=e.code;
                        }
                        else if(e.phase==4) { reporter_e=e;reporter_count++;phase="reporting"; }
                        else if(e.phase==5) {
                            if(native_fixture_mode) {
                                if(e.pid!=(int)controller_pid || e.value<=0 || declared_child ||
                                   transition_receipt || selection_receipt || (active_child && active_child!=e.value) || ++dispatches>15) {
                                    classification="invalid";reason="invalid_child_dispatch";goto stop_children;
                                }
                                declared_child=e.value;
                            }
                            worker_pid=e.value;
                        }
                        else if(e.phase==6)reporter_pid=e.value;
                        else if(e.phase==7)reporter_code=e.code;
                        else if(e.phase==8)early_parent_death_guard=1;
                        else if(e.phase==9 && python_mode && !python_ready) {
                            if(e.value!=(native_fixture_mode?4:128) ||
                               (native_fixture_mode && (!transition_receipt || !selection_receipt || active_child || declared_child))) {
                                classification="invalid";reason="python_fixture_schedule_mismatch";goto stop_children;
                            }
                            python_ready=1;python_nulls=e.value;
                        }
                        else if(e.phase==10 && native_fixture_mode && !transition_receipt) {
                            if(active_child || declared_child || e.value<0 || e.value>6 || e.code<0 || e.code>12) {
                                classification="invalid";reason="invalid_fixture_transition_receipt";goto stop_children;
                            }
                            transition_receipt=1;fixture_transitions=e.value;fixture_api_workers=e.code;
                        }
                        else if(e.phase==11 && native_fixture_mode && !selection_receipt) {
                            if(active_child || declared_child || e.value<0 || e.value>4 || e.code<0 || e.code>2) {
                                classification="invalid";reason="invalid_fixture_selection_receipt";goto stop_children;
                            }
                            selection_receipt=1;fixture_selections=e.value;fixture_producers=e.code;
                        }
                        else { classification="invalid";reason="unknown_event";goto stop_children; }
                        if(worker_count>(native_fixture_mode?15:1) || reporter_count>(native_fixture_mode?0:1)) { classification="invalid";reason="dispatch_inventory_exceeded";goto stop_children; }
                    }
                }
            }
        }
        pid_t w=waitpid(controller_pid,&status,WNOHANG);
        if(w==controller_pid) {
            reaped=1;
            if(!WIFEXITED(status)||WEXITSTATUS(status)) {
                if(python_mode && !python_ready && WIFEXITED(status) && WEXITSTATUS(status)==91) {
                    classification="invalid";reason="python_source_validation_failed";
                } else reason="controller_or_child_failure";
                goto stop_children;
            }
        } else if(w<0 && errno!=ECHILD && errno!=EINTR) { reason="wait_failed";goto stop_children; }
    }
    if(!reaped) { int code=wait_one(controller_pid);status=code<<8;reaped=1; }
    int workers_incomplete=native_fixture_mode ?
        (worker_count<1 || worker_count!=dispatches || active_child || declared_child || worker_failure_seen || !transition_receipt || !selection_receipt) : worker_count!=1;
    if(eventlen || workers_incomplete || worker_code || worker_e.pid!=(int)worker_pid || (python_mode ? (!python_ready || reporter_count!=0) : (reporter_count!=1 || reporter_code || reporter_e.pid!=(int)reporter_pid)) || !WIFEXITED(status) || WEXITSTATUS(status)) {
        if(python_mode && !python_ready && WIFEXITED(status) && WEXITSTATUS(status)==91) {
            classification="invalid";reason="python_source_validation_failed";
        } else reason="incomplete_child_protocol";
        goto stop_children;
    }
    classification="fixture_complete";reason=native_fixture_mode?"bounded_software_fixture_completed":"authored_stubs_completed";
stop_children:
    /* Always signal the entire group, even if its leader already exited. */
    if(controller_pid>0) {
        if(kill(-controller_pid,SIGKILL)==0 || errno==ESRCH) killed=1;
        while(now_ns()<deadline) {
            int s;pid_t p=waitpid(-1,&s,WNOHANG);
            if(p>0) { if(p==controller_pid) { status=s;reaped=1; }continue; }
            if(p<0 && errno==ECHILD)break;
            if(p<0 && errno!=EINTR) { error=1;break; }
            struct timespec t={0,1000000};nanosleep(&t,NULL);
        }
        if(kill(-controller_pid,0)==0 || errno!=ESRCH) { classification="incomplete";reason="cleanup_unverified"; }
        else expiry_group=-1;
    }
finish:
    if(native_fixture_mode && controller_pid>0 && (!transition_receipt || !selection_receipt)) {
        classification="invalid";reason="software_fixture_call_counts_unknown";
    }
    phase=!strcmp(classification,"fixture_complete")?"sealing":phase;
    if(!strcmp(argv[2],"finalize_hang")) hang();
    if(!strcmp(argv[2],"finalize_blocked_write")) {
        int blocked[2];char data[8192]={0};
        if(pipe(blocked)||fcntl(blocked[1],F_SETPIPE_SZ,4096)<0) return 99;
        /* A real blocking write with no draining reader; expiry must interrupt
         * the finalization path independently of the controller poll loop. */
        (void)write_all(blocked[1],data,sizeof data);
        return 99;
    }
    for(int i=0;i<2;i++){if(op[i]>=0)close(op[i]);if(ep[i]>=0)close(ep[i]);if(vp[i]>=0)close(vp[i]);}
    if(output_file(dirfd,"launcher.stdout",out_buf,outlen) || output_file(dirfd,"launcher.stderr",err_buf,errlen)) {
        classification="incomplete";reason="bounded_log_write_failed";
    }
    if(!strcmp(argv[2],"seal_failure")) { classification="incomplete";reason="injected_seal_failure"; }
    if(now_ns()>=deadline) { classification="incomplete";reason="finalization_deadline_exceeded"; }
    struct rusage usage;memset(&usage,0,sizeof usage);getrusage(RUSAGE_CHILDREN,&usage);
    uint64_t children_cpu=(uint64_t)(usage.ru_utime.tv_sec+usage.ru_stime.tv_sec)*1000000000ULL+
        (uint64_t)(usage.ru_utime.tv_usec+usage.ru_stime.tv_usec)*1000;
    struct rusage self_usage;memset(&self_usage,0,sizeof self_usage);getrusage(RUSAGE_SELF,&self_usage);
    uint64_t self_cpu=(uint64_t)(self_usage.ru_utime.tv_sec+self_usage.ru_stime.tv_sec)*1000000000ULL+
        (uint64_t)(self_usage.ru_utime.tv_usec+self_usage.ru_stime.tv_usec)*1000;
    struct rlimit as;getrlimit(RLIMIT_AS,&as);
    char transition_count[24]="0",api_worker_count[24]="0",selection_count[24]="0",producer_count[24]="0";
    if(native_fixture_mode && controller_pid>0) {
        strcpy(transition_count,"null");strcpy(api_worker_count,"null");
        strcpy(selection_count,"null");strcpy(producer_count,"null");
        if(transition_receipt) {
            snprintf(transition_count,sizeof transition_count,"%d",fixture_transitions);
            snprintf(api_worker_count,sizeof api_worker_count,"%d",fixture_api_workers);
        }
        if(selection_receipt) {
            snprintf(selection_count,sizeof selection_count,"%d",fixture_selections);
            snprintf(producer_count,sizeof producer_count,"%d",fixture_producers);
        }
    }
    char report[REPORT_CAP];
    int n=snprintf(report,sizeof report,
        "{\"schema\":\"ora.launcher.stub.v1\",\"classification\":\"%s\",\"phase\":\"%s\",\"reason\":\"%s\","
        "\"mode\":\"%s\",\"science_transition_invocations\":0,\"policy_invocations\":%s,\"scientific_execution_allowed\":false,"
        "\"fixture_kind\":\"%s\",\"native_fixture_admission_reviewed\":%s,\"native_fixture_profile_sha256\":\"%s\",\"actual_api_invocations\":%s,"
        "\"software_fixture_actual_transition_entries\":%s,\"software_fixture_api_workers_observed\":%s,"
        "\"software_fixture_actual_selecting_backend_calls\":%s,\"software_fixture_actual_producer_calls\":%s,"
        "\"software_fixture_dispatches_observed\":%d,\"native_owned_output_reservation_bytes\":1081344,"
        "\"clock\":\"CLOCK_BOOTTIME\",\"window_start_ns\":%" PRIu64 ",\"birth_ns\":%" PRIu64 ",\"entry_ns\":%" PRIu64 ",\"last_snapshot_ns\":%" PRIu64 ","
        "\"deadline_ns\":%" PRIu64 ",\"work_stop_ns\":%" PRIu64 ",\"finalization_reserve_ms\":%" PRIu64 ","
        "\"kernel_expiry_armed\":true,\"entry_route\":\"%s\",\"selected_cpu\":%d,\"controller_affinity_cpu\":%d,\"worker_affinity_cpu\":%d,\"reporter_affinity_cpu\":%d,"
        "\"internal_wall_ceiling_ms\":850000,\"reviewed_wall_ceiling_ms\":1500000,\"terminal_state\":\"prepared_before_exit\",\"no_live_launcher_helper\":true,\"python_controller_bootstrap_verified\":%s,\"authored_null_decisions\":%d,"
        "\"outer_as\":[%llu,%llu],\"controller_as\":[%" PRIu64 ",%" PRIu64 "],\"worker_as\":[%" PRIu64 ",%" PRIu64 "],\"reporter_as\":[%" PRIu64 ",%" PRIu64 "],"
        "\"controller_cpu\":[%" PRIu64 ",%" PRIu64 "],\"worker_cpu\":[%" PRIu64 ",%" PRIu64 "],\"reporter_cpu\":[%" PRIu64 ",%" PRIu64 "],"
        "\"worker_nproc\":%" PRIu64 ",\"stub_workers_observed_started\":%d,\"stub_reporters_observed_started\":%d,\"early_parent_death_guard\":%s,\"stub_counts_known\":%s,"
        "\"outer_pid\":%d,\"controller_pid\":%d,\"worker_pid\":%d,\"reporter_pid\":%d,\"worker_code\":%d,\"reporter_code\":%d,"
        "\"whole_group_termination_attempted\":%s,\"controller_reaped\":%s,\"stdout_bytes\":%zu,\"stderr_bytes\":%zu,"
        "\"output_cap_bytes\":201326592,\"failure_reserve_bytes\":1048576,\"stub_inventory_bound_bytes\":1081344,"
        "\"child_cpu_observed_ns\":%" PRIu64 ",\"outer_cpu_observed_ns\":%" PRIu64 ",\"aggregate_cpu_observed_ns\":%" PRIu64 ",\"cpu_candidate_seconds\":850,\"cpu_allowance_proved\":false,\"cpu_composition\":\"singleton_cpu_elapsed_lifetime\",\"aggregate_cpu_kernel_enforcement\":true,"
        "\"full_lifetime_hard_wall_proved\":false,\"native_bootstrap_memory_proved\":false,\"scientific_output_inventory_proved\":false,"
        "\"ambient_environment_forwarded\":false,\"restarts\":0,\"cleanup_error\":%d}\n",
        classification,phase,reason,argv[2],selection_count,
        native_fixture_mode?"native_api_software_fixture":"authored_zero_world",
        native_fixture_admission_reviewed?"true":"false",ORA_FIXTURE_PROFILE_SHA256,
        native_fixture_mode && controller_pid>0?"null":"0",transition_count,api_worker_count,selection_count,producer_count,
        dispatches,window_start,birth,entry,now_ns(),deadline,stop,cleanup_ms,
        "direct-native",selected_cpu,controller_e.affinity_cpu,worker_e.affinity_cpu,reporter_e.affinity_cpu,python_ready?"true":"false",python_nulls,
        (unsigned long long)as.rlim_cur,(unsigned long long)as.rlim_max,
        controller_e.as_soft,controller_e.as_hard,worker_e.as_soft,worker_e.as_hard,reporter_e.as_soft,reporter_e.as_hard,
        controller_e.cpu_soft,controller_e.cpu_hard,worker_e.cpu_soft,worker_e.cpu_hard,reporter_e.cpu_soft,reporter_e.cpu_hard,
        worker_e.nproc_soft,worker_count,reporter_count,early_parent_death_guard?"true":"false",
        (controller_pid<0 || !strcmp(classification,"fixture_complete"))?"true":"false",(int)getpid(),(int)controller_pid,(int)worker_pid,(int)reporter_pid,worker_code,reporter_code,
        killed?"true":"false",reaped?"true":"false",outlen,errlen,children_cpu,self_cpu,children_cpu+self_cpu,error);
    int rc=97;
    if(n>0 && (size_t)n<sizeof report && !pwrite_all(reservefd,report,(size_t)n,FINAL_OFFSET) && !fsync(reservefd) && !fsync(dirfd)) {
        /* Stdout is at most one fixed report. Persisted report precedes this.
         * The observer/helper reaps our actual exit; this snapshot does not. */
        if(!write_all(STDOUT_FILENO,report,(size_t)n))rc=!strcmp(classification,"fixture_complete")?0:2;
    }
    close(reservefd);close(dirfd);
    return rc;
}
