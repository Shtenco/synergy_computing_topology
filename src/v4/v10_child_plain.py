import sys,importlib.util
mod,arc,out=sys.argv[1:4]
spec=importlib.util.spec_from_file_location('v10fresh',mod);m=importlib.util.module_from_spec(spec);sys.modules['v10fresh']=m;spec.loader.exec_module(m)
ok=m.TopoArchiver().decompress_file(arc,out)
print('V10_FRESH_PROCESS',ok,'WEB_UI_OK',m.WEB_UI_OK)
sys.exit(0 if ok else 2)
