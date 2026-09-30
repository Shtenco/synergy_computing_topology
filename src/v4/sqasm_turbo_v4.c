#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

typedef uint8_t u8; typedef uint64_t u64;

void sq_amplitude_encode(u8 *data, int len, float *re, float *im){
    float sum=0.0f; if(len<0) len=0; if(len>256) len=256;
    for(int i=0;i<len;i++) sum += (float)data[i];
    if(sum<=0.0f) sum=1.0f;
    const float twopi=6.2831853071795864769f;
    for(int i=0;i<256;i++){
        float v=i<len?(float)data[i]:0.0f;
        float a=sqrtf(v/sum), ph=twopi*(float)i/256.0f;
        re[i]=a*cosf(ph); im[i]=a*sinf(ph);
    }
}
void sq_fwht(float *a,int n){
    for(int h=1;h<n;h<<=1) for(int i=0;i<n;i+=h<<1) for(int j=i;j<i+h;j++){
        float x=a[j],y=a[j+h]; a[j]=x+y; a[j+h]=x-y;
    }
}
int sq_grover(float *re,float *im,int n,float threshold){
    float mx=0.0f; for(int i=0;i<n;i++){float m=re[i]*re[i]+im[i]*im[i]; if(m>mx)mx=m;}
    float cut=mx*(1.0f-threshold); int hits=0;
    for(int i=0;i<n;i++){float m=re[i]*re[i]+im[i]*im[i]; if(m>=cut){re[i]=-re[i];im[i]=-im[i];hits++;}}
    return hits;
}
int sq_measure(float *re,float *im,int n){
    int bi=0; float bm=-1.0f; for(int i=0;i<n;i++){float m=re[i]*re[i]+im[i]*im[i]; if(m>bm){bm=m;bi=i;}} return bi;
}
float sq_entropy(float *re,float *im,int n){
    double tot=0.0; for(int i=0;i<n;i++) tot+=(double)re[i]*re[i]+(double)im[i]*im[i];
    if(tot<=0.0) return 0.0f;
    double H=0.0;
    for(int i=0;i<n;i++){double p=((double)re[i]*re[i]+(double)im[i]*im[i])/tot; if(p>0.0)H-=p*log2(p);} return (float)H;
}
float sq_qpipe_fused(u8 *data,int len,float thr,int *meas_out,float *ent_out){
    float re[256],im[256]; sq_amplitude_encode(data,len,re,im);
    sq_fwht(re,256); sq_fwht(im,256);
    (void)sq_grover(re,im,256,thr);
    int m=sq_measure(re,im,256); float e=sq_entropy(re,im,256);
    if(meas_out) *meas_out=m;
    if(ent_out) *ent_out=e;
    return e;
}
u64 sq_xxhash64_ll(u8 *d,u64 n){
    u64 h=2870177450012600261ULL+n; const u64 P1=11400714785074694791ULL,P2=14029467366897019727ULL,P5=2870177450012600261ULL;
    u64 i=0; while(i+4<=n){uint32_t v;memcpy(&v,d+i,4);h^=(u64)v*P2;h=((h<<27)|(h>>37))*P1+9650029242287828579ULL;i+=4;}
    while(i<n){h^=(u64)d[i]*P5;h=((h<<11)|(h>>53))*P1;i++;}
    h^=h>>33;h*=P2;h^=h>>29;h*=1609587929392839161ULL;h^=h>>32;return h;
}
float sq_cyber_scan(u8 *data,int len){
    if(len<=0) return 0.0f;
    unsigned cnt[256]={0}; for(int i=0;i<len;i++)cnt[data[i]]++;
    double H=0.0;for(int i=0;i<256;i++)if(cnt[i]){double p=(double)cnt[i]/len;H-=p*log2(p);} return (float)(H/8.0);
}
int sq_deepcompress(u8 *src,int slen,u8 *dst,int dmax){
    int i=0,o=0;while(i<slen){if(src[i]==0){int r=0;while(i<slen&&src[i]==0&&r<255){i++;r++;} if(o+2>dmax)return -1;dst[o++]=0;dst[o++]=(u8)r;}
    else {int st=i,c=0;while(i<slen&&src[i]!=0&&c<127){i++;c++;} if(o+2+c>dmax)return -1;dst[o++]=(u8)(0x80|c);dst[o++]=(u8)c;memcpy(dst+o,src+st,c);o+=c;}} return o;
}
void sq_batch_pipeline(u8 **arr,int *lens,int n,float thr,int *mo,float *eo){for(int i=0;i<n;i++)sq_qpipe_fused(arr[i],lens[i],thr,&mo[i],&eo[i]);}

#ifndef SQASM_NO_MAIN
int main(void){
    u8 d[256];for(int i=0;i<256;i++)d[i]=(u8)(11+i%37);int m=-1;float e=-1.0f;
    sq_qpipe_fused(d,256,0.1f,&m,&e); printf("[QPIPE-V4] meas=%d entropy=%.6f hash=%llu\n",m,e,(unsigned long long)sq_xxhash64_ll(d,256));
    if(!(e>=0.0f && e<=8.0001f) || m<0 || m>=256) return 2;
    return 0;
}
#endif
