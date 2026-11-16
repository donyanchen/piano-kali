// SPDX-License-Identifier: MIT
#define _GNU_SOURCE
#include <linux/bpf.h>
#include <linux/magic.h>
#include <sys/syscall.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/mount.h>
#include <sys/sysmacros.h>
#include <unistd.h>
#include <fcntl.h>
#include <dirent.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>

#define ROOT "/sys/fs/bpf/sheng-privacy"
#define MAJORS ROOT "/sensor-majors"
#define ALLOW ROOT "/allowed-devices"
#define DENY ROOT "/denied-devices"
#define PROGRAM ROOT "/device-guard"
#define INS(c,d,s,o,v) ((struct bpf_insn){.code=(c),.dst_reg=(d),.src_reg=(s),.off=(o),.imm=(v)})

static int bpf_call(enum bpf_cmd cmd, union bpf_attr *attr) {
    return syscall(__NR_bpf,cmd,attr,sizeof(*attr));
}
static void fail(const char *what) { perror(what); exit(1); }
static int object_get(const char *path) {
    union bpf_attr a={0};a.pathname=(uintptr_t)path;return bpf_call(BPF_OBJ_GET,&a);
}
static void object_pin(int fd,const char *path) {
    union bpf_attr a={0};a.pathname=(uintptr_t)path;a.bpf_fd=fd;
    if(bpf_call(BPF_OBJ_PIN,&a)<0)fail("pin privacy guard");
}
static int new_map(unsigned key_size,unsigned capacity,const char *name) {
    union bpf_attr a={0};a.map_type=BPF_MAP_TYPE_HASH;a.key_size=key_size;a.value_size=4;a.max_entries=capacity;
    snprintf(a.map_name,sizeof(a.map_name),"%s",name);
    int fd=bpf_call(BPF_MAP_CREATE,&a);if(fd<0)fail("create privacy map");return fd;
}
static void put(int fd,const void *key) {
    uint32_t yes=1;union bpf_attr a={0};a.map_fd=fd;a.key=(uintptr_t)key;a.value=(uintptr_t)&yes;a.flags=BPF_ANY;
    if(bpf_call(BPF_MAP_UPDATE_ELEM,&a)<0)fail("update privacy map");
}
static void remove_key(int fd,const void *key) {
    union bpf_attr a={0};a.map_fd=fd;a.key=(uintptr_t)key;bpf_call(BPF_MAP_DELETE_ELEM,&a);
}
static int load_guard(int majors,int allowed,int denied) {
    struct bpf_insn p[48];int n=0;
#define EMIT(x) (p[n++]=(x))
#define MAP(fd) do {EMIT(INS(BPF_LD|BPF_DW|BPF_IMM,1,BPF_PSEUDO_MAP_FD,0,fd));EMIT(INS(0,0,0,0,0));} while(0)
    EMIT(INS(BPF_ALU64|BPF_MOV|BPF_X,6,1,0,0));
    EMIT(INS(BPF_LDX|BPF_W|BPF_MEM,2,6,0,0));
    EMIT(INS(BPF_ALU64|BPF_AND|BPF_K,2,0,0,0xffff));
    int not_char=n;EMIT(INS(BPF_JMP|BPF_JNE|BPF_K,2,0,0,BPF_DEVCG_DEV_CHAR));
    EMIT(INS(BPF_LDX|BPF_W|BPF_MEM,2,6,4,0));
    EMIT(INS(BPF_STX|BPF_W|BPF_MEM,10,2,-4,0));
    EMIT(INS(BPF_ALU64|BPF_LSH|BPF_K,2,0,0,32));
    EMIT(INS(BPF_LDX|BPF_W|BPF_MEM,3,6,8,0));
    EMIT(INS(BPF_ALU64|BPF_OR|BPF_X,2,3,0,0));
    EMIT(INS(BPF_STX|BPF_DW|BPF_MEM,10,2,-16,0));
    MAP(denied);
    EMIT(INS(BPF_ALU64|BPF_MOV|BPF_X,2,10,0,0));
    EMIT(INS(BPF_ALU64|BPF_ADD|BPF_K,2,0,0,-16));
    EMIT(INS(BPF_JMP|BPF_CALL,0,0,0,BPF_FUNC_map_lookup_elem));
    int explicitly_denied=n;EMIT(INS(BPF_JMP|BPF_JNE|BPF_K,0,0,0,0));
    MAP(majors);
    EMIT(INS(BPF_ALU64|BPF_MOV|BPF_X,2,10,0,0));
    EMIT(INS(BPF_ALU64|BPF_ADD|BPF_K,2,0,0,-4));
    EMIT(INS(BPF_JMP|BPF_CALL,0,0,0,BPF_FUNC_map_lookup_elem));
    int unrelated=n;EMIT(INS(BPF_JMP|BPF_JEQ|BPF_K,0,0,0,0));
    MAP(allowed);
    EMIT(INS(BPF_ALU64|BPF_MOV|BPF_X,2,10,0,0));
    EMIT(INS(BPF_ALU64|BPF_ADD|BPF_K,2,0,0,-16));
    EMIT(INS(BPF_JMP|BPF_CALL,0,0,0,BPF_FUNC_map_lookup_elem));
    int permitted=n;EMIT(INS(BPF_JMP|BPF_JNE|BPF_K,0,0,0,0));
    int deny=n;EMIT(INS(BPF_ALU64|BPF_MOV|BPF_K,0,0,0,0));EMIT(INS(BPF_JMP|BPF_EXIT,0,0,0,0));
    int allow=n;EMIT(INS(BPF_ALU64|BPF_MOV|BPF_K,0,0,0,1));EMIT(INS(BPF_JMP|BPF_EXIT,0,0,0,0));
    p[not_char].off=allow-not_char-1;p[unrelated].off=allow-unrelated-1;p[permitted].off=allow-permitted-1;
    p[explicitly_denied].off=deny-explicitly_denied-1;
    static char log[65536];const char license[]="Dual MIT/GPL";union bpf_attr a={0};
    a.prog_type=BPF_PROG_TYPE_CGROUP_DEVICE;a.expected_attach_type=BPF_CGROUP_DEVICE;
    a.insn_cnt=n;a.insns=(uintptr_t)p;a.license=(uintptr_t)license;
    a.log_level=1;a.log_size=sizeof(log);a.log_buf=(uintptr_t)log;
    snprintf(a.prog_name,sizeof(a.prog_name),"sheng_privacy");
    int fd=bpf_call(BPF_PROG_LOAD,&a);if(fd<0){fprintf(stderr,"%s\n",log);fail("load privacy guard");}return fd;
}
static int cgroup(void) {int fd=open("/sys/fs/cgroup",O_RDONLY|O_DIRECTORY|O_CLOEXEC);if(fd<0)fail("open root cgroup");return fd;}
static void attach(int prog) {
    int cg=cgroup();
    struct bpf_prog_info info={0};union bpf_attr details={0};
    details.info.bpf_fd=prog;details.info.info_len=sizeof(info);details.info.info=(uintptr_t)&info;
    uint32_t ids[256];union bpf_attr query={0};
    query.query.target_fd=cg;query.query.attach_type=BPF_CGROUP_DEVICE;query.query.prog_cnt=256;query.query.prog_ids=(uintptr_t)ids;
    if(!bpf_call(BPF_OBJ_GET_INFO_BY_FD,&details)&&!bpf_call(BPF_PROG_QUERY,&query)){
        for(uint32_t i=0;i<query.query.prog_cnt;i++)if(ids[i]==info.id){close(cg);return;}
    }
    union bpf_attr a={0};a.target_fd=cg;a.attach_bpf_fd=prog;a.attach_type=BPF_CGROUP_DEVICE;a.attach_flags=BPF_F_ALLOW_MULTI;
    if(bpf_call(BPF_PROG_ATTACH,&a)<0 && errno!=EEXIST)fail("attach privacy guard");
    close(cg);
}
static void detach(int prog) {
    int cg=cgroup();union bpf_attr a={0};a.target_fd=cg;a.attach_bpf_fd=prog;a.attach_type=BPF_CGROUP_DEVICE;
    if(bpf_call(BPF_PROG_DETACH,&a)<0 && errno!=ENOENT && errno!=EINVAL)fail("detach privacy guard");
    close(cg);
}
static void allow_path(int fd,const char *path) {
    struct stat st;if(stat(path,&st)||!S_ISCHR(st.st_mode))return;
    uint64_t key=((uint64_t)major(st.st_rdev)<<32)|minor(st.st_rdev);put(fd,&key);
}
static void populate(int maj,int allowed,int denied) {
    DIR *dir=opendir("/dev/snd");struct dirent *entry;char path[PATH_MAX];
    if(dir){while((entry=readdir(dir))){
        size_t len=strlen(entry->d_name);
        if(!strncmp(entry->d_name,"pcmC",4)&&len&&entry->d_name[len-1]=='c'){
            snprintf(path,sizeof(path),"/dev/snd/%s",entry->d_name);allow_path(denied,path);continue;
        }
        snprintf(path,sizeof(path),"/dev/snd/%s",entry->d_name);allow_path(allowed,path);
    }closedir(dir);}
    dir=opendir("/sys/class/video4linux");
    if(dir){while((entry=readdir(dir))){
        char link[PATH_MAX],resolved[PATH_MAX];
        snprintf(link,sizeof(link),"/sys/class/video4linux/%s/device/driver",entry->d_name);
        if(realpath(link,resolved)&&strstr(resolved,"/qcom-iris")){
            snprintf(path,sizeof(path),"/dev/%s",entry->d_name);allow_path(allowed,path);
        }
    }closedir(dir);}
    uint32_t video=81,sound=116;put(maj,&video);put(maj,&sound);
    dir=opendir("/sys/bus/usb/devices");
    if(dir){while((entry=readdir(dir))){
        char parent[256],attr[PATH_MAX];unsigned kind,bus,device;
        const char *colon=strchr(entry->d_name,':');if(!colon)continue;
        snprintf(attr,sizeof(attr),"/sys/bus/usb/devices/%s/bInterfaceClass",entry->d_name);
        FILE *f=fopen(attr,"r");if(!f)continue;int ok=fscanf(f,"%x",&kind);fclose(f);
        if(ok!=1||(kind!=1&&kind!=14))continue;
        size_t length=(size_t)(colon-entry->d_name);if(length>=sizeof(parent))continue;
        memcpy(parent,entry->d_name,length);parent[length]=0;
        snprintf(attr,sizeof(attr),"/sys/bus/usb/devices/%s/busnum",parent);
        f=fopen(attr,"r");if(!f)continue;ok=fscanf(f,"%u",&bus);fclose(f);if(ok!=1)continue;
        snprintf(attr,sizeof(attr),"/sys/bus/usb/devices/%s/devnum",parent);
        f=fopen(attr,"r");if(!f)continue;ok=fscanf(f,"%u",&device);fclose(f);if(ok!=1)continue;
        snprintf(path,sizeof(path),"/dev/bus/usb/%03u/%03u",bus,device);allow_path(denied,path);
    }closedir(dir);}
    dir=opendir("/dev");
    if(dir){while((entry=readdir(dir))){
        if(strncmp(entry->d_name,"gnss",4))continue;
        snprintf(path,sizeof(path),"/dev/%s",entry->d_name);struct stat st;
        if(!stat(path,&st)&&S_ISCHR(st.st_mode)){uint32_t m=major(st.st_rdev);put(maj,&m);}
    }closedir(dir);}
}
static void ensure_mount(void) {
    struct statfs fs;
    if(statfs("/sys/fs/bpf",&fs)||fs.f_type!=BPF_FS_MAGIC)
        if(mount("bpffs","/sys/fs/bpf","bpf",MS_NOSUID|MS_NODEV|MS_NOEXEC,NULL))fail("mount bpffs");
}
int main(int argc,char **argv) {
    if(geteuid()!=0||argc<2)return 2;
    umask(0077);
    if(!strcmp(argv[1],"prepare")){ensure_mount();return 0;}
    if(!strcmp(argv[1],"probe")){
        int m=new_map(4,64,"sheng_major"),a=new_map(8,1024,"sheng_allowed"),d=new_map(8,1024,"sheng_denied"),p=load_guard(m,a,d);
        attach(p);detach(p);close(p);close(d);close(a);close(m);puts("cgroup device guard supported");return 0;
    }
    if(!strcmp(argv[1],"disable")){
        int p=object_get(PROGRAM);if(p>=0){detach(p);close(p);}
        unlink(PROGRAM);unlink(DENY);unlink(ALLOW);unlink(MAJORS);rmdir(ROOT);return 0;
    }
    if(!strcmp(argv[1],"allow")||!strcmp(argv[1],"deny")||!strcmp(argv[1],"deny-major")){
        if(argc<3)return 2;
        unsigned m=(unsigned)strtoul(argv[2],NULL,10);int fd=object_get(!strcmp(argv[1],"deny-major")?MAJORS:ALLOW);
        if(fd<0)return 0;
        if(!strcmp(argv[1],"deny-major")){uint32_t key=m;put(fd,&key);}
        else {
            if(argc!=4){close(fd);return 2;}
            uint64_t key=((uint64_t)m<<32)|(unsigned)strtoul(argv[3],NULL,10);
            int d=object_get(DENY);if(d<0){close(fd);return 0;}
            if(!strcmp(argv[1],"allow")){remove_key(d,&key);put(fd,&key);}
            else {remove_key(fd,&key);put(d,&key);}
            close(d);
        }
        close(fd);return 0;
    }
    if(strcmp(argv[1],"enable"))return 2;
    ensure_mount();if(mkdir(ROOT,0700)&&errno!=EEXIST)fail("create privacy pin directory");
    int m=object_get(MAJORS),a=object_get(ALLOW),d=object_get(DENY),p=object_get(PROGRAM);
    if(m>=0||a>=0||d>=0||p>=0){if(m<0||a<0||d<0||p<0){fprintf(stderr,"Incomplete privacy pins\n");return 1;}}
    else{m=new_map(4,64,"sheng_major");a=new_map(8,1024,"sheng_allowed");d=new_map(8,1024,"sheng_denied");p=load_guard(m,a,d);object_pin(m,MAJORS);object_pin(a,ALLOW);object_pin(d,DENY);object_pin(p,PROGRAM);}
    populate(m,a,d);attach(p);close(p);close(d);close(a);close(m);puts("process device access blocked");return 0;
}
