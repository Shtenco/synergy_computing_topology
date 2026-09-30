// SHTENCO TURBO HPC CORE V4 — fixed-point Ring-0 correctness closure
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/fs.h>
#include <linux/cdev.h>
#include <linux/device.h>
#include <linux/uaccess.h>
#include <linux/slab.h>
#include <linux/vmalloc.h>
#include <linux/rwlock.h>
#include <linux/atomic.h>
#include <linux/ktime.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/ioctl.h>
#include <linux/string.h>
#include <linux/bitops.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Evgeniy Koshtenko / V4 correctness closure");
MODULE_DESCRIPTION("SHTENCO TURBO HPC CORE V4 fixed-point, no kernel FPU");
MODULE_VERSION("4.0");

#define DEVICE_NAME "sqcore_turbo_v4"
#define CLASS_NAME  "sqasm_turbo_v4"
#define SQ_MAGIC 'T'
#define SQ_STATES 256
#define SQ_PSI_REGS 32
#define QSHIFT 16
#define QONE (1LL<<QSHIFT)
#define SQ_MAX_DATA (4<<20)

struct sq_args_v4 {
    __u32 psi_idx, reg_idx, data_len;
    __u64 data_ptr;
    __u32 threshold_f32_bits;
    __s64 result_i;
    __u32 result_f32_bits;
    __u8 key[32];
    __u32 flags;
    __u64 timestamp_ns;
};
struct sq_stat_v4 { __u64 qpipe_calls, qenc_calls, fwht_calls, grov_calls, meas_calls, qent_calls; };
#define SQASM_QENC   _IOWR(SQ_MAGIC,0x10,struct sq_args_v4)
#define SQASM_FWHT   _IOWR(SQ_MAGIC,0x11,struct sq_args_v4)
#define SQASM_GROV   _IOWR(SQ_MAGIC,0x12,struct sq_args_v4)
#define SQASM_MEAS   _IOWR(SQ_MAGIC,0x13,struct sq_args_v4)
#define SQASM_QENT   _IOWR(SQ_MAGIC,0x14,struct sq_args_v4)
#define SQASM_QPIPE  _IOWR(SQ_MAGIC,0x16,struct sq_args_v4)
#define SQASM_STAT   _IOR (SQ_MAGIC,0x70,struct sq_stat_v4)
#define SQASM_RESET  _IO  (SQ_MAGIC,0xFF)

typedef struct { s32 re, im; } qcx;
static qcx psi[SQ_PSI_REGS][SQ_STATES];
static rwlock_t psi_lock;
static atomic64_t c_qpipe=ATOMIC64_INIT(0),c_qenc=ATOMIC64_INIT(0),c_fwht=ATOMIC64_INIT(0),c_grov=ATOMIC64_INIT(0),c_meas=ATOMIC64_INIT(0),c_qent=ATOMIC64_INIT(0);
static dev_t devno; static struct cdev cdev_v4; static struct class *cls; static struct device *devobj; static struct proc_dir_entry *proc_entry;

static s32 f32bits_to_q16(u32 bits){
    u32 sign=bits>>31, exp=(bits>>23)&0xff, frac=bits&0x7fffff; s64 m; int e;
    if(exp==0) return 0;
    if(exp==255) return sign?-(s32)QONE:(s32)QONE;
    m=(s64)(0x800000|frac); e=(int)exp-127-23+QSHIFT;
    if(e>=0){ if(e>30) m=(s64)INT_MAX; else m<<=e; } else { int sh=-e; m=(sh>=63)?0:(m>>sh); }
    if(m>INT_MAX) m=INT_MAX;
    return sign?-(s32)m:(s32)m;
}
static u32 q16_to_f32bits(s32 q){
    if(q==0) return 0;
    u32 sign=q<0; u32 a=q<0?(u32)(-(s64)q):(u32)q; int p=31-__builtin_clz(a); int exp=p-QSHIFT+127;
    if(exp<=0) return sign<<31;
    if(exp>=255) return (sign<<31)|0x7f800000;
    u32 mant;
    if(p>=23) mant=(a>>(p-23))&0x7fffff; else mant=(a<<(23-p))&0x7fffff;
    return (sign<<31)|((u32)exp<<23)|mant;
}
static inline s64 mag2(qcx z){ return (s64)z.re*z.re+(s64)z.im*z.im; }

static void qenc(unsigned r,const u8 *data,u32 len){
    u64 sum=0; if(r>=SQ_PSI_REGS)return; if(len>SQ_STATES)len=SQ_STATES;
    for(u32 i=0;i<len;i++) sum+=data[i];
    if(!sum) sum=1;
    write_lock(&psi_lock);
    for(u32 i=0;i<SQ_STATES;i++){u64 v=i<len?data[i]:0; psi[r][i].re=(s32)((v<<QSHIFT)/sum); psi[r][i].im=0;}
    write_unlock(&psi_lock); atomic64_inc(&c_qenc);
}
static void fwht(unsigned r){
    if(r>=SQ_PSI_REGS) return;
    write_lock(&psi_lock);
    for(int h=1;h<SQ_STATES;h<<=1)for(int i=0;i<SQ_STATES;i+=h<<1)for(int j=i;j<i+h;j++){
        s32 ar=psi[r][j].re, br=psi[r][j+h].re, ai=psi[r][j].im, bi=psi[r][j+h].im;
        s64 x=(s64)ar+br,y=(s64)ar-br,u=(s64)ai+bi,v=(s64)ai-bi;
        psi[r][j].re=clamp_t(s64,x,INT_MIN,INT_MAX); psi[r][j+h].re=clamp_t(s64,y,INT_MIN,INT_MAX);
        psi[r][j].im=clamp_t(s64,u,INT_MIN,INT_MAX); psi[r][j+h].im=clamp_t(s64,v,INT_MIN,INT_MAX);
    }
    write_unlock(&psi_lock); atomic64_inc(&c_fwht);
}
static int grov(unsigned r,s32 threshold_q16){
    s64 mx=0,cut;int hits=0;if(r>=SQ_PSI_REGS)return -EINVAL;if(threshold_q16<0)threshold_q16=0;if(threshold_q16>QONE)threshold_q16=QONE;
    write_lock(&psi_lock);for(int i=0;i<SQ_STATES;i++){s64 m=mag2(psi[r][i]);if(m>mx)mx=m;}cut=(mx*(QONE-threshold_q16))>>QSHIFT;
    for(int i=0;i<SQ_STATES;i++)if(mag2(psi[r][i])>=cut){psi[r][i].re=-psi[r][i].re;psi[r][i].im=-psi[r][i].im;hits++;}
    write_unlock(&psi_lock);atomic64_inc(&c_grov);return hits;
}
static int meas(unsigned r){int bi=0;s64 bm=-1;if(r>=SQ_PSI_REGS)return -EINVAL;read_lock(&psi_lock);for(int i=0;i<SQ_STATES;i++){s64 m=mag2(psi[r][i]);if(m>bm){bm=m;bi=i;}}read_unlock(&psi_lock);atomic64_inc(&c_meas);return bi;}
static s32 entropy_q16(unsigned r){
    u64 total=0,weighted=0;if(r>=SQ_PSI_REGS)return 0;read_lock(&psi_lock);
    for(int i=0;i<SQ_STATES;i++){u64 m=(u64)mag2(psi[r][i]);total+=m;}
    if(total){int lt=fls64(total)-1;for(int i=0;i<SQ_STATES;i++){u64 m=(u64)mag2(psi[r][i]);if(m){int lm=fls64(m)-1;weighted += m*(u64)lm;}}read_unlock(&psi_lock);atomic64_inc(&c_qent);return (s32)(((s64)lt<<QSHIFT)-((s64)(weighted<<QSHIFT)/(s64)total));}
    read_unlock(&psi_lock);atomic64_inc(&c_qent);return 0;
}
static int qpipe(unsigned r,const u8*d,u32 len,s32 thr,s32*ent){qenc(r,d,len);fwht(r);(void)grov(r,thr);int m=meas(r);*ent=entropy_q16(r);atomic64_inc(&c_qpipe);return m;}

static long ioctl_v4(struct file*f,unsigned cmd,unsigned long arg){
    struct sq_args_v4 a; u8 *buf=NULL; s32 ent=0,thr; int rc=0;(void)f;
    if(cmd==SQASM_STAT){struct sq_stat_v4 s={atomic64_read(&c_qpipe),atomic64_read(&c_qenc),atomic64_read(&c_fwht),atomic64_read(&c_grov),atomic64_read(&c_meas),atomic64_read(&c_qent)};return copy_to_user((void __user*)arg,&s,sizeof(s))?-EFAULT:0;}
    if(cmd==SQASM_RESET){write_lock(&psi_lock);memset(psi,0,sizeof(psi));write_unlock(&psi_lock);return 0;}
    if(copy_from_user(&a,(void __user*)arg,sizeof(a))) return -EFAULT;
    if(a.psi_idx>=SQ_PSI_REGS) return -EINVAL;
    if((cmd==SQASM_QENC||cmd==SQASM_QPIPE)&&a.data_len){if(a.data_len>SQ_MAX_DATA)return -E2BIG;buf=memdup_user((void __user*)(uintptr_t)a.data_ptr,a.data_len);if(IS_ERR(buf))return PTR_ERR(buf);}
    thr=f32bits_to_q16(a.threshold_f32_bits);
    switch(cmd){
      case SQASM_QENC:qenc(a.psi_idx,buf,a.data_len);break;
      case SQASM_FWHT:fwht(a.psi_idx);break;
      case SQASM_GROV:a.result_i=grov(a.psi_idx,thr);break;
      case SQASM_MEAS:a.result_i=meas(a.psi_idx);break;
      case SQASM_QENT:ent=entropy_q16(a.psi_idx);a.result_f32_bits=q16_to_f32bits(ent);break;
      case SQASM_QPIPE:a.result_i=qpipe(a.psi_idx,buf,a.data_len,thr,&ent);a.result_f32_bits=q16_to_f32bits(ent);break;
      default:rc=-ENOTTY;
    }
    a.timestamp_ns=ktime_get_ns();kfree(buf);if(rc)return rc;return copy_to_user((void __user*)arg,&a,sizeof(a))?-EFAULT:0;
}
static int open_v4(struct inode*i,struct file*f){(void)i;(void)f;return 0;}static int release_v4(struct inode*i,struct file*f){(void)i;(void)f;return 0;}
static const struct file_operations fops={.owner=THIS_MODULE,.open=open_v4,.release=release_v4,.unlocked_ioctl=ioctl_v4,.compat_ioctl=ioctl_v4};
static int proc_show(struct seq_file*m,void*v){(void)v;seq_printf(m,"version=4.0 fixed_point=1 qpipe=%lld qenc=%lld fwht=%lld grov=%lld meas=%lld qent=%lld\n",atomic64_read(&c_qpipe),atomic64_read(&c_qenc),atomic64_read(&c_fwht),atomic64_read(&c_grov),atomic64_read(&c_meas),atomic64_read(&c_qent));return 0;}
static int proc_open_v4(struct inode*i,struct file*f){return single_open(f,proc_show,NULL);}static const struct proc_ops pops={.proc_open=proc_open_v4,.proc_read=seq_read,.proc_lseek=seq_lseek,.proc_release=single_release};
static int __init init_v4(void){int r;rwlock_init(&psi_lock);memset(psi,0,sizeof(psi));r=alloc_chrdev_region(&devno,0,1,DEVICE_NAME);if(r)return r;cdev_init(&cdev_v4,&fops);r=cdev_add(&cdev_v4,devno,1);if(r)goto e1;cls=class_create(CLASS_NAME);if(IS_ERR(cls)){r=PTR_ERR(cls);goto e2;}devobj=device_create(cls,NULL,devno,NULL,DEVICE_NAME);if(IS_ERR(devobj)){r=PTR_ERR(devobj);goto e3;}proc_entry=proc_create("sqcore_turbo_v4",0444,NULL,&pops);pr_info("sqcore_turbo_v4 loaded: fixed-point, no FPU\n");return 0;e3:class_destroy(cls);e2:cdev_del(&cdev_v4);e1:unregister_chrdev_region(devno,1);return r;}
static void __exit exit_v4(void){if(proc_entry)proc_remove(proc_entry);device_destroy(cls,devno);class_destroy(cls);cdev_del(&cdev_v4);unregister_chrdev_region(devno,1);pr_info("sqcore_turbo_v4 unloaded\n");}
module_init(init_v4);module_exit(exit_v4);
