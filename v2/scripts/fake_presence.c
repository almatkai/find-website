/* QA only, never packaged: replace application-presence producers before launch. */
#include <sys/stat.h>
#include <unistd.h>
#include <dlfcn.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include <errno.h>
#include <fcntl.h>
static const char *mapped(const char *path,char out[PATH_MAX]) {
  if (!path || strncmp(path,"/Applications/",14)) return path;
  const char *root=getenv("FIND_WEBSITE_QA_APPLICATIONS");
  if (!root || root[0]!='/') {errno=ENOENT;return NULL;}
  if (snprintf(out,PATH_MAX,"%s/%s",root,path+14)>=PATH_MAX) {errno=ENAMETOOLONG;return NULL;}
  const char *audit=getenv("FIND_WEBSITE_QA_PRESENCE_AUDIT");
  if (audit) {int fd=open(audit,O_WRONLY|O_CREAT|O_APPEND,0600);if(fd>=0){write(fd,path,strlen(path));write(fd,"\n",1);close(fd);}}
  return out;
}
static int qa_stat(const char *path,struct stat *buf) {
  char target[PATH_MAX];const char *p=mapped(path,target);if(!p)return -1;
  return stat(p,buf);
}
static int qa_lstat(const char *path,struct stat *buf) {
  char target[PATH_MAX];const char *p=mapped(path,target);if(!p)return -1;
  return lstat(p,buf);
}
static int qa_access(const char *path,int mode) {
  char target[PATH_MAX];const char *p=mapped(path,target);if(!p)return -1;
  return access(p,mode);
}
#define INTERPOSE(replacement,replacee) \
 __attribute__((used)) static struct {const void *r;const void *o;} \
 ip_##replacee __attribute__((section("__DATA,__interpose")))={(const void*)&replacement,(const void*)&replacee};
INTERPOSE(qa_stat,stat)
INTERPOSE(qa_lstat,lstat)
INTERPOSE(qa_access,access)
