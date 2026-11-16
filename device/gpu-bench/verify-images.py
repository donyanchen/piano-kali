import hashlib,json,sys
from pathlib import Path
state=Path('/home/kali/.local/state/sheng-gpu-bench')
tag=sys.argv[1] if len(sys.argv)>1 else 'balanced'
assert tag.isalnum()
report=json.loads((state/('run-report-'+tag+'.json')).read_text())
hashes={}
for run in report['runs']:
    path=state/('results-'+tag)/(run['prefix']+'.rgba')
    hashes[run['prefix']]=hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
validation={'format':'3048x2032 RGBA8, no MSAA, identical clear/scissor/blend/shader arithmetic','sha256':hashes,'all_paths_identical_by_workload':{workload:len({v for k,v in hashes.items() if '-'+workload+'-' in k})==1 for workload in ['fill','ui','alu']}}
(state/('image-validation-'+tag+'.json')).write_text(json.dumps(validation,indent=2))
print(json.dumps(validation['all_paths_identical_by_workload']))
