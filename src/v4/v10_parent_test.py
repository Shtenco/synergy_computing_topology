import sys,types,importlib.util,tempfile,os,subprocess,hashlib,shutil
fl=types.ModuleType('flask')
class Flask:
 def __init__(self,*a,**k): self.config={};self.secret_key=None
 def route(self,*a,**k): return lambda f:f
 def after_request(self,f): return f
 def before_request(self,f): return f
 def run(self,*a,**k): pass
fl.Flask=Flask;fl.request=types.SimpleNamespace(files={},form={},remote_addr='127.0.0.1');fl.send_file=lambda *a,**k:None;fl.jsonify=lambda *a,**k:a[0] if len(a)==1 else a
sys.modules['flask']=fl
w=types.ModuleType('werkzeug');wu=types.ModuleType('werkzeug.utils');wu.secure_filename=lambda x:x;w.utils=wu;sys.modules['werkzeug']=w;sys.modules['werkzeug.utils']=wu
ROOT=os.path.dirname(os.path.abspath(__file__));mod=os.path.join(ROOT,'DEEPCOMPRESS_TOPO_v10_V4.py')
td=tempfile.mkdtemp(prefix='v10test_');old=os.getcwd();os.chdir(td)
try:
 spec=importlib.util.spec_from_file_location('v10',mod);m=importlib.util.module_from_spec(spec);sys.modules['v10']=m;spec.loader.exec_module(m)
 cases=[(b'ABCD'*20000,'repeat'),(bytes((i*37)&255 for i in range(65536)),'structured')]
 for data,name in cases:
  src=os.path.join(td,name+'.bin');arc=os.path.join(td,name+'.slt10');out=os.path.join(td,name+'.out');open(src,'wb').write(data)
  ok=m.TopoArchiver().compress_file(src,arc);assert ok
  cp=subprocess.run([sys.executable,os.path.join(ROOT,'v10_child.py'),mod,arc,out],text=True,capture_output=True,cwd=td)
  print(name,'compress',ok,'archive',os.path.getsize(arc),'child_rc',cp.returncode,cp.stdout.strip(),'equal',os.path.exists(out) and open(out,'rb').read()==data)
  if cp.returncode or not os.path.exists(out) or hashlib.sha256(open(out,'rb').read()).digest()!=hashlib.sha256(data).digest():sys.exit(2)
 print('TOPO_V10_SELF_CONTAINED=PASS')
finally:
 os.chdir(old);shutil.rmtree(td,ignore_errors=True)
