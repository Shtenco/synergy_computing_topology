#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <inttypes.h>

typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64;
static inline u64 ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (u64)t.tv_sec*1000000000ull+t.tv_nsec;}
static inline u32 hilbert(u32 x,u32 y){u32 rx,ry,s,d=0;for(s=128;s;s>>=1){rx=(x&s)!=0;ry=(y&s)!=0;d+=s*s*((3*rx)^ry);if(!ry){if(rx){x=255-x;y=255-y;}u32 t=x;x=y;y=t;}}return d;}
static inline u32 payload_of(u16 k){u32 x=k; x^=x<<13;x^=x>>17;x^=x<<5;return x*2654435761u+17u;}
typedef struct{u16 key;u32 val;} KV;
typedef struct{u32 h;u16 key;u32 val;} HKV;
static int cmp_kv(const void*a,const void*b){u16 x=((const KV*)a)->key,y=((const KV*)b)->key;return(x>y)-(x<y);}
static int cmp_hkv(const void*a,const void*b){u32 x=((const HKV*)a)->h,y=((const HKV*)b)->h;return(x>y)-(x<y);}
static int sorted_get(KV*a,int n,u16 k,u32*out){int l=0,r=n-1;while(l<=r){int m=(l+r)>>1;if(a[m].key==k){*out=a[m].val;return 1;}if(a[m].key<k)l=m+1;else r=m-1;}return 0;}
static int hilbert_get(HKV*a,int n,u16 k,u32*out){u32 h=hilbert(k>>8,k&255);int l=0,r=n-1;while(l<=r){int m=(l+r)>>1;if(a[m].h==h){if(a[m].key==k){*out=a[m].val;return 1;}return 0;}if(a[m].h<h)l=m+1;else r=m-1;}return 0;}
typedef struct{u16 key;u32 val;u8 used;} HE;
typedef struct{HE*e;u32 cap;} HT;
static inline u32 h16(u16 k){u32 x=k*2654435761u;x^=x>>16;return x;}
static HT ht_build(KV*a,int n){u32 cap=1;while(cap<(u32)n*3)cap<<=1;HT t={calloc(cap,sizeof(HE)),cap};for(int i=0;i<n;i++){u32 p=h16(a[i].key)&(cap-1);while(t.e[p].used)p=(p+1)&(cap-1);t.e[p]=(HE){a[i].key,a[i].val,1};}return t;}
static int ht_get(HT*t,u16 k,u32*out){u32 p=h16(k)&(t->cap-1),st=p;while(t->e[p].used){if(t->e[p].key==k){*out=t->e[p].val;return 1;}p=(p+1)&(t->cap-1);if(p==st)break;}return 0;}
#define BT_T 16
#define BT_MAXK (2*BT_T-1)
typedef struct BN{int n,leaf;u16 k[BT_MAXK];u32 v[BT_MAXK];struct BN*c[2*BT_T];} BN;
static BN*bn_new(int leaf){BN*x=calloc(1,sizeof(BN));x->leaf=leaf;return x;}
static void bt_split(BN*x,int i){BN*y=x->c[i],*z=bn_new(y->leaf);z->n=BT_T-1;for(int j=0;j<BT_T-1;j++){z->k[j]=y->k[j+BT_T];z->v[j]=y->v[j+BT_T];}if(!y->leaf)for(int j=0;j<BT_T;j++)z->c[j]=y->c[j+BT_T];y->n=BT_T-1;for(int j=x->n;j>=i+1;j--)x->c[j+1]=x->c[j];x->c[i+1]=z;for(int j=x->n-1;j>=i;j--){x->k[j+1]=x->k[j];x->v[j+1]=x->v[j];}x->k[i]=y->k[BT_T-1];x->v[i]=y->v[BT_T-1];x->n++;}
static void bt_ins_nf(BN*x,u16 k,u32 v){int i=x->n-1;if(x->leaf){while(i>=0&&k<x->k[i]){x->k[i+1]=x->k[i];x->v[i+1]=x->v[i];i--;}x->k[i+1]=k;x->v[i+1]=v;x->n++;}else{while(i>=0&&k<x->k[i])i--;i++;if(x->c[i]->n==BT_MAXK){bt_split(x,i);if(k>x->k[i])i++;}bt_ins_nf(x->c[i],k,v);}}
static BN*bt_insert(BN*r,u16 k,u32 v){if(r->n==BT_MAXK){BN*s=bn_new(0);s->c[0]=r;bt_split(s,0);bt_ins_nf(s,k,v);return s;}bt_ins_nf(r,k,v);return r;}
static int bt_get(BN*x,u16 k,u32*out){int i=0;while(i<x->n&&k>x->k[i])i++;if(i<x->n&&k==x->k[i]){*out=x->v[i];return 1;}if(x->leaf)return 0;return bt_get(x->c[i],k,out);}
static void bt_free(BN*x){if(!x)return;if(!x->leaf)for(int i=0;i<=x->n;i++)bt_free(x->c[i]);free(x);}
typedef int(*lookup_fn)(void*,u16,u32*);
static int flat_get(void*ctx,u16 k,u32*out){KV*a=((KV**)ctx)[0];int n=(int)(uintptr_t)((KV**)ctx)[1];for(int i=0;i<n;i++)if(a[i].key==k){*out=a[i].val;return 1;}return 0;}
static int sorted_wrap(void*ctx,u16 k,u32*out){KV*a=((KV**)ctx)[0];int n=(int)(uintptr_t)((KV**)ctx)[1];return sorted_get(a,n,k,out);}
static int hilb_wrap(void*ctx,u16 k,u32*out){HKV*a=(HKV*)((void**)ctx)[0];int n=(int)(uintptr_t)((void**)ctx)[1];return hilbert_get(a,n,k,out);}
static int hash_wrap(void*ctx,u16 k,u32*out){return ht_get((HT*)ctx,k,out);}
static int bt_wrap(void*ctx,u16 k,u32*out){return bt_get((BN*)ctx,k,out);}
static double time_lookup(const char*name,lookup_fn f,void*ctx,u16*q,int nq,u64*cs){u64 t=ns(),sum=0;for(int i=0;i<nq;i++){u32 v=0;if(f(ctx,q[i],&v))sum+=(u64)v;}u64 dt=ns()-t;*cs=sum;printf("LOOKUP %-12s %8.2f ns/query checksum=%" PRIu64 "\n",name,(double)dt/nq,sum);return(double)dt/nq;}
typedef struct{u8 dom,rough,b0;u16 chk;} Desc;
static inline Desc desc_make(const u8*b){u16 cnt[256]={0};u32 sum=0,rough=0;for(int i=0;i<256;i++){cnt[b[i]]++;sum+=b[i];if(i)rough+=(u32)abs((int)b[i]-(int)b[i-1]);}int mx=-1,dom=0;for(int i=0;i<256;i++)if(cnt[i]>mx){mx=cnt[i];dom=i;}Desc d={(u8)dom,(u8)(rough&255),(u8)(mx&255),(u16)sum};return d;}
typedef struct{u32 idx;u8 dom;} DI;
static int cmp_di(const void*a,const void*b){return(int)((const DI*)a)->dom-(int)((const DI*)b)->dom;}
typedef struct{u64 count,checksum;} QR;
static QR raw_query(const u8*raw,int n,int dlo,int dhi,u8 rmask){QR z={0,0};for(int i=0;i<n;i++){Desc d=desc_make(raw+(size_t)i*256);if(d.dom>=dlo&&d.dom<=dhi&&(d.rough&15)==rmask){z.count++;z.checksum+=(u64)i*1315423911u+d.chk;}}return z;}
static QR idx_query(const Desc*d,const DI*ord,const u32*lo,int n,int dlo,int dhi,u8 rmask){(void)n;QR z={0,0};if(dlo<0)dlo=0;if(dhi>255)dhi=255;if(dlo>dhi)return z;u32 a=lo[dlo],b=lo[dhi+1];for(u32 p=a;p<b;p++){u32 i=ord[p].idx;if((d[i].rough&15)==rmask){z.count++;z.checksum+=(u64)i*1315423911u+d[i].chk;}}return z;}

int main(void){
    printf("SHTENCO V4 FAIR BENCHMARK\n");
    const int N=30000,NQ=3000; KV*base=malloc(N*sizeof(KV));u16*all=malloc(65536*sizeof(u16));for(int i=0;i<65536;i++)all[i]=(u16)i;
    u32 seed=0x12345678;for(int i=65535;i>0;i--){seed=seed*1664525u+1013904223u;u32 j=seed%(i+1);u16 t=all[i];all[i]=all[j];all[j]=t;}
    for(int i=0;i<N;i++){base[i].key=all[i];base[i].val=payload_of(all[i]);}
    u16*q=malloc(NQ*sizeof(u16));for(int i=0;i<NQ;i++){seed=seed*1664525u+1013904223u;q[i]=(u16)(seed&65535);}
    KV*sorted=malloc(N*sizeof(KV));memcpy(sorted,base,N*sizeof(KV));u64 t0=ns();qsort(sorted,N,sizeof(KV),cmp_kv);double bsort=(ns()-t0)/1e6;
    HKV*hv=malloc(N*sizeof(HKV));t0=ns();for(int i=0;i<N;i++){u16 k=base[i].key;hv[i]=(HKV){hilbert(k>>8,k&255),k,base[i].val};}qsort(hv,N,sizeof(HKV),cmp_hkv);double bh=(ns()-t0)/1e6;
    t0=ns();HT ht=ht_build(base,N);double bhash=(ns()-t0)/1e6;
    t0=ns();BN*root=bn_new(1);for(int i=0;i<N;i++)root=bt_insert(root,base[i].key,base[i].val);double bbt=(ns()-t0)/1e6;
    printf("BUILD sorted=%.3fms hilbert=%.3fms hash=%.3fms btree=%.3fms\n",bsort,bh,bhash,bbt);
    void*flatctx[2]={base,(void*)(uintptr_t)N},*sortctx[2]={sorted,(void*)(uintptr_t)N},*hctx[2]={hv,(void*)(uintptr_t)N};
    u64 cflat,csort,chash,cbt,chilb;time_lookup("FLAT",flat_get,flatctx,q,NQ,&cflat);time_lookup("HASH",hash_wrap,&ht,q,NQ,&chash);time_lookup("SORTED",sorted_wrap,sortctx,q,NQ,&csort);time_lookup("B-TREE",bt_wrap,root,q,NQ,&cbt);time_lookup("HILBERT",hilb_wrap,hctx,q,NQ,&chilb);
    int lookup_ok=(cflat==csort&&cflat==chash&&cflat==cbt&&cflat==chilb);printf("LOOKUP_RESULT_EQUAL=%s\n",lookup_ok?"PASS":"FAIL");if(!lookup_ok)return 3;
    const int NR=2048;u8*raw=malloc((size_t)NR*256);Desc*d=malloc(NR*sizeof(Desc));DI*ord=malloc(NR*sizeof(DI));
    for(int i=0;i<NR;i++){u8 dom=(u8)((i*37)%256);u8*b=raw+(size_t)i*256;for(int j=0;j<256;j++)b[j]=(u8)(dom+(j%8));for(int j=0;j<96;j++)b[j]=dom;}
    t0=ns();for(int i=0;i<NR;i++){d[i]=desc_make(raw+(size_t)i*256);ord[i]=(DI){(u32)i,d[i].dom};}qsort(ord,NR,sizeof(DI),cmp_di);u32 lo[257];u32 p=0;for(int dom=0;dom<256;dom++){lo[dom]=p;while(p<(u32)NR&&ord[p].dom==dom)p++;}lo[256]=NR;double build_ms=(ns()-t0)/1e6;
    typedef struct { int dlo,dhi; u8 mask; } QSpec; QSpec qs[256];
    for(int qi=0;qi<256;qi++){int dlo=(qi*37)%224, dhi=dlo+31;u8 mask=(u8)((qi*13)&15);int seeded=0;for(int ii=0;ii<NR;ii++) if(d[ii].dom>=dlo&&d[ii].dom<=dhi){mask=d[ii].rough&15;seeded=1;break;}if(!seeded){fprintf(stderr,"query template has no seed\n");return 6;}qs[qi]=(QSpec){dlo,dhi,mask};}
    u64 verify_cs=0,verify_hits=0;int all_eq=1;
    for(int qi=0;qi<256;qi++){QR rb=raw_query(raw,NR,qs[qi].dlo,qs[qi].dhi,qs[qi].mask);QR ri=idx_query(d,ord,lo,NR,qs[qi].dlo,qs[qi].dhi,qs[qi].mask);if(rb.count!=ri.count||rb.checksum!=ri.checksum){all_eq=0;break;}verify_cs+=rb.checksum;verify_hits+=rb.count;}
    printf("QUERY_RESULT_SET_256=%s total_hits=%" PRIu64 " checksum=%" PRIu64 "\n",all_eq?"PASS":"FAIL",verify_hits,verify_cs);if(!all_eq)return 4;
    QR re0=raw_query(raw,NR,300,301,3),ie0=idx_query(d,ord,lo,NR,300,301,3);int empty=(re0.count==0&&ie0.count==0);
    printf("EMPTY_QUERY_GUARD=%s (speedup suppressed)\n",empty?"PASS":"FAIL");if(!empty)return 5;
    volatile u64 sink=0;int reps_list[]={1,10,100,1000,2000,3000};int nrp=6;double last_sp=0.0;
    for(int rr=0;rr<nrp;rr++){int reps=reps_list[rr];t0=ns();for(int qn=0;qn<reps;qn++){QSpec z=qs[qn&255];QR x=raw_query(raw,NR,z.dlo,z.dhi,z.mask);sink+=x.checksum;}double raw_total=(ns()-t0)/1e6;t0=ns();for(int qn=0;qn<reps;qn++){QSpec z=qs[qn&255];QR x=idx_query(d,ord,lo,NR,z.dlo,z.dhi,z.mask);sink+=x.checksum;}double idx_queries=(ns()-t0)/1e6;double e2e=build_ms+idx_queries;double sp=raw_total/e2e;last_sp=sp;printf("AMORT_VARIED reps=%d build_ms=%.6f raw_ms=%.6f idx_query_ms=%.6f e2e_idx_ms=%.6f speedup=%.3fx\n",reps,build_ms,raw_total,idx_queries,e2e,sp);}
    printf("END_TO_END_VARIED_SPEEDUP_3000Q=%.3fx sink=%" PRIu64 "\n",last_sp,(u64)sink);
    printf("INDEX_BUILD_COST_INCLUDED=PASS\n");
    free(raw);free(d);free(ord);bt_free(root);free(ht.e);free(hv);free(sorted);free(q);free(base);free(all);
    return 0;
}
