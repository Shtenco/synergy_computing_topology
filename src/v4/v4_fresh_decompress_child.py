#!/usr/bin/env python3
import json,sys,hashlib,importlib.util,os
module_path,manifest_path=sys.argv[1:3]
spec=importlib.util.spec_from_file_location('shtenco_v4',module_path)
m=importlib.util.module_from_spec(spec);sys.modules['shtenco_v4']=m;spec.loader.exec_module(m)
items=json.load(open(manifest_path))
dc=m.DeepCompressTurbo()
for i,it in enumerate(items):
    c=open(it['archive'],'rb').read()
    out=dc.decompress(c,it['size'])
    if len(out)!=it['size'] or hashlib.sha256(out).hexdigest()!=it['sha256']:
        print('FAIL',i);sys.exit(2)
print('FRESH_PROCESS_1000_PASS',len(items))
