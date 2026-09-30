import sys, types, tempfile, os, importlib.util, shutil
# minimal import-only Flask/Werkzeug substitutes: route bodies are not exercised
fl=types.ModuleType('flask')
class Flask:
    def __init__(self,*a,**k): self.config={}; self.secret_key=None
    def route(self,*a,**k): return lambda f:f
    def after_request(self,f): return f
    def before_request(self,f): return f
    def run(self,*a,**k): pass
fl.Flask=Flask
fl.request=types.SimpleNamespace(files={},form={},remote_addr='127.0.0.1')
fl.send_file=lambda *a,**k: None
fl.jsonify=lambda *a,**k: a[0] if len(a)==1 else a
sys.modules['flask']=fl
w=types.ModuleType('werkzeug'); wu=types.ModuleType('werkzeug.utils'); wu.secure_filename=lambda x:x; w.utils=wu
sys.modules['werkzeug']=w; sys.modules['werkzeug.utils']=wu

td=tempfile.mkdtemp(prefix='audit_v9_'); old=os.getcwd(); os.chdir(td)
try:
    spec=importlib.util.spec_from_file_location('audit_v9','/mnt/data/DEEPCOMPRESS_TOPO_v9.py')
    m=importlib.util.module_from_spec(spec); sys.modules['audit_v9']=m; spec.loader.exec_module(m)
    src=os.path.join(td,'src.bin'); arc=os.path.join(td,'a.sltop'); out1=os.path.join(td,'same.bin'); out2=os.path.join(td,'fresh.bin')
    data=(b'ABCD'*20000)  # 80 KB, highly repetitive
    open(src,'wb').write(data)
    a=m.TopoArchiver(); okc=a.compress_file(src,arc); ok_same=a.decompress_file(arc,out1)
    print('compress_ok',okc,'archive_size',os.path.getsize(arc),'same_process_decompress_ok',ok_same,'same_equal',open(out1,'rb').read()==data if os.path.exists(out1) else False)
    print('dict_entries_after_compress',len(m.topo_dict._exact_index),'dict_file_exists',os.path.exists(m.DICT_FILE))
    # Simulate fresh process: no in-memory dictionary and no saved dictionary file.
    m.topo_dict=m.TopologicalDictionary()
    ok_fresh=m.TopoArchiver().decompress_file(arc,out2)
    print('fresh_dictionary_decompress_ok',ok_fresh,'fresh_output_exists',os.path.exists(out2),'fresh_equal',open(out2,'rb').read()==data if os.path.exists(out2) else False)
finally:
    os.chdir(old); shutil.rmtree(td,ignore_errors=True)
