import os,sys,time,statistics,importlib.util
import numpy as np
ROOT=os.path.dirname(os.path.abspath(__file__))
p=os.path.join(ROOT,'TURBO_HPC_SHTENCO_OS_v4.py')
spec=importlib.util.spec_from_file_location('thpc_v4',p);m=importlib.util.module_from_spec(spec);sys.modules['thpc_v4']=m;spec.loader.exec_module(m)
rng=np.random.default_rng(123456);h=m.HPCEngine()
print('NUMBA',m.NUMBA_OK)
for N in [1,8,64,256,1024]:
 payloads=[rng.integers(0,256,size=256,dtype=np.uint8).tobytes() for _ in range(N)]
 h.qpipe_batch(payloads,0.17)
 bt=[]; st=[]
 for _ in range(5):
  t=time.perf_counter();br=h.qpipe_batch(payloads,0.17);bt.append(time.perf_counter()-t)
  t=time.perf_counter();sr=[h.qpipe_fused(x,0.17) for x in payloads];st.append(time.perf_counter()-t)
 ok=br['meas']==[x['meas'] for x in sr]
 bmed=statistics.median(bt);smed=statistics.median(st)
 print(f'QPIPE N={N} batch_pipe_s={N/bmed:.1f} seq_pipe_s={N/smed:.1f} batch_vs_seq={smed/bmed:.3f}x equal={ok}')
