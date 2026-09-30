import sys,types,importlib.util,os
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
mod,arc,out=sys.argv[1:4]
spec=importlib.util.spec_from_file_location('v10fresh',mod);m=importlib.util.module_from_spec(spec);sys.modules['v10fresh']=m;spec.loader.exec_module(m)
ok=m.TopoArchiver().decompress_file(arc,out)
print('V10_FRESH_PROCESS',ok)
sys.exit(0 if ok else 2)
