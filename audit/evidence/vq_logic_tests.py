import sys,types,zlib,hashlib,importlib.util,os
class H:
    def __init__(self,b=b''): self.b=bytes(b)
    def digest(self): return hashlib.blake2b(self.b,digest_size=8).digest()
    def hexdigest(self): return self.digest().hex()
xx=types.ModuleType('xxhash'); xx.xxh64=lambda b=b'',*a,**k:H(b); xx.xxh3_64=lambda b=b'',*a,**k:H(b); xx.xxh3_64_hexdigest=lambda b=b'',*a,**k:H(b).hexdigest(); xx.xxh128=lambda b=b'',*a,**k:H(b)
sys.modules['xxhash']=xx
zs=types.ModuleType('zstandard')
class C:
  def __init__(self,level=1,*a,**k): self.level=level
  def compress(self,b): return zlib.compress(bytes(b),1 if self.level<=1 else 9)
class D:
  def decompress(self,b): return zlib.decompress(bytes(b))
zs.ZstdCompressor=C; zs.ZstdDecompressor=D; sys.modules['zstandard']=zs

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); sys.modules[name]=m; spec.loader.exec_module(m); return m
for ver,path in [('v1','/mnt/data/virtual_qubit_hpc_v1.py'),('v2','/mnt/data/virtual_qubit_hpc_v2.py')]:
    print('===',ver,'===')
    m=load('audit_'+ver,path)
    q=m.VirtualQubit(0); data=bytes(range(256)); q.encode(data); n0=float((abs(q.psi)**2).sum()); q.hadamard(); n1=float((abs(q.psi)**2).sum()); imag=float(abs(q.psi.imag).max()); q.qft(); n2=float((abs(q.psi)**2).sum()); print('norms',n0,n1,n2,'imag_after_hadamard_max',imag)
    reg=m.QubitRegister(); dc=m.DeepCompressV6(reg); src=os.urandom(4096); c,meta=dc.compress(src); same=dc.decompress(c,meta); dc2=m.DeepCompressV6(m.QubitRegister()); fresh=dc2.decompress(c,meta)
    print('same_engine_roundtrip',same==src,'fresh_engine_roundtrip',fresh==src,'fresh_len',len(fresh),'compressed_len',len(c))
