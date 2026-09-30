import sys,importlib.util,tempfile,os,subprocess,hashlib,shutil
ROOT=os.path.dirname(os.path.abspath(__file__));mod=os.path.join(ROOT,'DEEPCOMPRESS_TOPO_v10_V4.py')
td=tempfile.mkdtemp(prefix='v10plain_');old=os.getcwd();os.chdir(td)
try:
 spec=importlib.util.spec_from_file_location('v10',mod);m=importlib.util.module_from_spec(spec);sys.modules['v10']=m;spec.loader.exec_module(m)
 data=(b'ABCD'*20000);src='in.bin';arc='a.slt10';out='out.bin';open(src,'wb').write(data)
 assert m.TopoArchiver().compress_file(src,arc)
 cp=subprocess.run([sys.executable,os.path.join(ROOT,'v10_child_plain.py'),mod,os.path.abspath(arc),os.path.abspath(out)],text=True,capture_output=True,cwd=td)
 print(cp.stdout.strip()); print('equal',os.path.exists(out) and open(out,'rb').read()==data)
 if cp.returncode or open(out,'rb').read()!=data:sys.exit(2)
 print('TOPO_V10_PLAIN_FRESH_PROCESS=PASS')
finally:os.chdir(old);shutil.rmtree(td,ignore_errors=True)
