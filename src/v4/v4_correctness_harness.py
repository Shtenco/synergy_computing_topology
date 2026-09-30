#!/usr/bin/env python3
import os,sys,time,tempfile,shutil,hashlib,json,subprocess,importlib.util,random
import numpy as np
ROOT=os.path.dirname(os.path.abspath(__file__))

def load(name,fn):
    p=os.path.join(ROOT,fn);spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

print('=== V4 CORRECTNESS HARNESS ===')
v4=load('thpc_v4','TURBO_HPC_SHTENCO_OS_v4.py')
rng=np.random.default_rng(20260930)
h=v4.HPCEngine()
batch=rng.integers(0,256,size=(128,256),dtype=np.uint8)
seq=[h.qpipe_fused(row.tobytes(),0.17) for row in batch]
runs=[]
for _ in range(5):
    om=np.zeros(128,np.int32); osig=np.zeros(128,np.float32); oe=np.zeros(128,np.float32)
    v4._qpipe_batch(batch,0.17,om,osig,oe)
    runs.append((om.copy(),osig.copy(),oe.copy()))
meq=all(int(runs[0][0][i])==int(seq[i]['meas']) for i in range(128))
seq_ent=np.array([x['entropy'] for x in seq],dtype=np.float32)
seq_sig=np.array([x['signal'] for x in seq],dtype=np.float32)
ents=np.max(np.abs(runs[0][2]-seq_ent)); sigs=np.max(np.abs(runs[0][1]-seq_sig))
det=all(np.array_equal(runs[0][0],r[0]) and np.array_equal(runs[0][1],r[1]) and np.array_equal(runs[0][2],r[2]) for r in runs[1:])
print('BATCH_EQ_SEQ', 'PASS' if meq and ents<1e-5 and sigs<1e-6 else 'FAIL', 'entropy_max_abs',float(ents),'signal_max_abs',float(sigs))
print('BATCH_DETERMINISTIC','PASS' if det else 'FAIL')
if not(meq and ents<1e-5 and sigs<1e-6 and det): sys.exit(10)
q=v4.QubitCore(h); d=bytes(range(256)); a=q.pipe(d,0.01); b=q.pipe(d,0.99)
cache_ok=(a['hits']!=b['hits'])
print('CACHE_THRESHOLD_KEY','PASS' if cache_ok else 'FAIL',a['hits'],b['hits'])
if not cache_ok: sys.exit(11)

td=tempfile.mkdtemp(prefix='shtenco_v4_')
try:
    manifest=[]; dc=v4.DeepCompressTurbo(); py_rng=random.Random(20260930)
    for i in range(1000):
        sz=py_rng.randrange(0,16385)
        kind=i%5
        if kind==0: data=b'\x00'*sz
        elif kind==1: data=(b'SHTENCO-V4-TEST|'*((sz+15)//16))[:sz]
        elif kind==2: data=os.urandom(sz)
        elif kind==3: data=bytes(((j*37+i*11)&255) for j in range(sz))
        else:
            ba=bytearray(sz)
            for _ in range(max(1,sz//128) if sz else 0):
                if sz: ba[py_rng.randrange(sz)]=py_rng.randrange(1,256)
            data=bytes(ba)
        c,meta=dc.compress(data)
        ap=os.path.join(td,f'a{i:04d}.bin');open(ap,'wb').write(c)
        manifest.append({'archive':ap,'size':len(data),'sha256':hashlib.sha256(data).hexdigest(),'method':meta['method']})
    mp=os.path.join(td,'manifest.json');json.dump(manifest,open(mp,'w'))
    child=os.path.join(ROOT,'v4_fresh_decompress_child.py')
    cp=subprocess.run([sys.executable,child,os.path.join(ROOT,'TURBO_HPC_SHTENCO_OS_v4.py'),mp],text=True,capture_output=True)
    print(cp.stdout.strip())
    if cp.returncode!=0: print(cp.stderr);sys.exit(12)
    print('SHA256_1000_CORPORA PASS')
    ap=manifest[777]['archive']; corrupt=bytearray(open(ap,'rb').read())
    if len(corrupt)>40: corrupt[len(corrupt)//2]^=0x5A
    rejected=False
    try: v4.DeepCompressTurbo().decompress(bytes(corrupt),manifest[777]['size'])
    except Exception: rejected=True
    print('CORRUPTED_ARCHIVE_REJECT','PASS' if rejected else 'FAIL')
    if not rejected: sys.exit(13)
finally:
    shutil.rmtree(td,ignore_errors=True)

cachem=load('cache_v2','turbo_cache_accelerator_v2.py')
td=tempfile.mkdtemp(prefix='shtenco_cache_v4_')
try:
    l2=os.path.join(td,'l2.bin');l3=os.path.join(td,'l3.bin')
    c=cachem.TurboCache32GB(l2_path=l2,l3_path=l3,l2_size_mb=2,l3_size_mb=2,slot_kb=1,enable_l3=True);c.start();
    assert c.put('persist',b'abc123'); c.stop()
    c2=cachem.TurboCache32GB(l2_path=l2,l3_path=l3,l2_size_mb=2,l3_size_mb=2,slot_kb=1,enable_l3=True);c2.start();pv=c2.get('persist');persist=(pv==b'abc123');delok=c2.delete('persist');after=c2.get('persist');c2.stop()
    print('CACHE_RESTART_RECOVERY','PASS' if persist else 'FAIL')
    print('CACHE_DELETE','PASS' if delok and after is None else 'FAIL')
    if not(persist and delok and after is None):sys.exit(14)
    a=cachem.TurboAccelerator(l2_path=os.path.join(td,'a2.bin'),l3_path=os.path.join(td,'a3.bin'),l2_size_mb=2,l3_size_mb=2,slot_kb=1,enable_l3=True,n_qt_cores=4,enable_watchdog=False);a.start()
    d1=bytes([i%251 for i in range(1024)]);d2=d1+b'Z';o1,_=a.accelerate(d1,key='a');o2,_=a.accelerate(d2,key='b');a.stop()
    tail=not np.array_equal(o1,o2)
    print('NO_TAIL_LOSS','PASS' if tail else 'FAIL','max_abs_delta',float(np.max(np.abs(o1-o2))))
    if not tail:sys.exit(15)
finally:shutil.rmtree(td,ignore_errors=True)
print('V4_CORRECTNESS_ALL=PASS')
