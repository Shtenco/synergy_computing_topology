import os, sys, types, zlib, hashlib, tempfile, shutil, importlib.util
import numpy as np

# Logic-only substitutes for unavailable external packages. NOT performance substitutes.
class H:
    def __init__(self,b=b''):
        self.b=bytes(b)
    def digest(self): return hashlib.blake2b(self.b,digest_size=8).digest()
    def hexdigest(self): return self.digest().hex()
xx=types.ModuleType('xxhash')
xx.xxh64=lambda b=b'', *a, **k: H(b)
xx.xxh3_64=lambda b=b'', *a, **k: H(b)
xx.xxh3_64_hexdigest=lambda b=b'', *a, **k: H(b).hexdigest()
xx.xxh3_64_intdigest=lambda b=b'', *a, **k: int.from_bytes(H(b).digest(),'little')
xx.xxh128=lambda b=b'', *a, **k: type('H128',(),{'digest':lambda self:hashlib.blake2b(bytes(b),digest_size=16).digest(),'hexdigest':lambda self:hashlib.blake2b(bytes(b),digest_size=16).hexdigest()})()
sys.modules['xxhash']=xx
zs=types.ModuleType('zstandard')
class C:
    def __init__(self,level=1,*a,**k): self.level=level
    def compress(self,b): return zlib.compress(bytes(b),1 if self.level<=1 else 9)
class D:
    def decompress(self,b): return zlib.decompress(bytes(b))
zs.ZstdCompressor=C; zs.ZstdDecompressor=D
sys.modules['zstandard']=zs

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec); sys.modules[name]=m; spec.loader.exec_module(m); return m

print('=== UNIFIED V3 ===')
sys.path.insert(0,'/mnt/data/shtenco_audit_evidence'); import audit_thpc_v3 as v3
# batch race test with actual numba if enabled
rng=np.random.default_rng(20260930)
batch=rng.integers(0,256,size=(64,256),dtype=np.uint8)
h=v3.HPCEngine()
om=np.zeros(64,np.int32); osig=np.zeros(64,np.float32); oe=np.zeros(64,np.float32)
v3._qpipe_batch(batch,0.1,om,osig,oe)
seq=[h.qpipe_fused(row.tobytes(),0.1) for row in batch]
meas_mismatch=sum(int(om[i])!=int(seq[i]['meas']) for i in range(64))
ent_max=max(abs(float(oe[i])-float(seq[i]['entropy'])) for i in range(64))
print('batch_seq_measurement_mismatch',meas_mismatch,'of 64')
print('batch_seq_entropy_max_abs_diff',ent_max)
runs=[]
for _ in range(3):
    om2=np.zeros(64,np.int32); os2=np.zeros(64,np.float32); oe2=np.zeros(64,np.float32)
    v3._qpipe_batch(batch,0.1,om2,os2,oe2)
    runs.append((tuple(map(int,om2)), tuple(round(float(e),6) for e in oe2)))
print('batch_repeat_deterministic', runs[0]==runs[1]==runs[2])

# threshold cache-key bug
q=v3.QubitCore(h)
d=bytes(range(256))
a=q.pipe(d,0.01); b=q.pipe(d,0.99)
f1=h.qpipe_fused(d,0.01); f2=h.qpipe_fused(d,0.99)
print('cache_threshold_same_object_result',a==b)
print('fresh_threshold_hits',f1.get('hits'),f2.get('hits'))
print('cache_hits_after_second',q._hits)

# advertised zeros path roundtrip
zdc=v3.DeepCompressTurbo()
z=b'\x00'*4096
c,meta=zdc.compress(z)
out=zdc.decompress(c,len(z))
print('deepcompress_zero_method',meta['method'],'compressed',len(c),'roundtrip',out==z,'outlen',len(out))

print('\n=== TURBO CACHE ACCELERATOR ===')
import audit_turbo_cache as tc
td=tempfile.mkdtemp(prefix='audit_tc_')
try:
    cache=tc.TurboCache32GB(l2_path=os.path.join(td,'l2.bin'),l3_path=os.path.join(td,'l3.bin'),l2_size_mb=2,l3_size_mb=2,slot_kb=1,enable_l3=True)
    cache.start(); cache.put('k',b'value'); before=cache.get('k'); deleted=cache.delete('k'); after=cache.get('k'); cache.stop()
    print('delete_before',before,'delete_return',deleted,'after_delete',after,'stale_revived',after==b'value')

    a=tc.TurboAccelerator(l2_path=os.path.join(td,'a2.bin'),l3_path=os.path.join(td,'a3.bin'),l2_size_mb=2,l3_size_mb=2,slot_kb=1,enable_l3=True,n_qt_cores=4,enable_watchdog=False)
    a.start()
    d1=bytes([i%251 for i in range(1024)])
    d2=d1+b'Z'
    o1,_=a.accelerate(d1,key='a'); o2,_=a.accelerate(d2,key='b')
    same=all(np.array_equal(x,y) for x,y in zip(o1,o2))
    print('accelerate_1024_vs_1025_same_outputs',same)
    a.stop()

    # persistence check
    p2=os.path.join(td,'p2.bin'); p3=os.path.join(td,'p3.bin')
    c1=tc.TurboCache32GB(l2_path=p2,l3_path=p3,l2_size_mb=2,l3_size_mb=2,slot_kb=1,enable_l3=True); c1.start(); c1.put('persist',b'abc'); c1.stop()
    c2=tc.TurboCache32GB(l2_path=p2,l3_path=p3,l2_size_mb=2,l3_size_mb=2,slot_kb=1,enable_l3=True); c2.start(); pv=c2.get('persist'); c2.stop()
    print('fresh_instance_persistence_value',pv)
finally:
    shutil.rmtree(td,ignore_errors=True)
