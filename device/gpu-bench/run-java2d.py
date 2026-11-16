import datetime, json, os, subprocess
from pathlib import Path
state=Path('/home/kali/.local/state/sheng-gpu-bench')
gpu=Path('/sys/class/devfreq/3d00000.gpu')
old={k:(gpu/k).read_text() for k in ['min_freq','max_freq']}
jre=Path('/home/kali/.local/opt/BurpSuite/jre')
auth=next(Path('/run/user/1000').glob('xauth_*'))
report={'started_at':datetime.datetime.now().astimezone().isoformat(),'runs':[],'clock_hz':550000000}
try:
    (gpu/'max_freq').write_text('550000000'); (gpu/'min_freq').write_text('550000000')
    for repeat in range(3):
        for mode in (['freedreno','zink-turnip'] if repeat%2==0 else ['zink-turnip','freedreno']):
            name=f'java2d-{repeat+1}-{mode}'
            env={'XDG_RUNTIME_DIR':'/run/user/1000','DISPLAY':':0','XAUTHORITY':str(auth),'VK_DRIVER_FILES':'/usr/share/vulkan/icd.d/freedreno_icd.json'}
            if mode=='zink-turnip': env.update(GALLIUM_DRIVER='zink',MESA_LOADER_DRIVER_OVERRIDE='zink')
            base=['/usr/sbin/runuser','-u','kali','--','/usr/bin/taskset','-c','4-7','/usr/bin/env']+[f'{k}={v}' for k,v in env.items()]
            identity=subprocess.run(base+['glxinfo','-B'],capture_output=True,text=True,timeout=15,check=True)
            (state/'results'/(name+'-renderer.txt')).write_text(identity.stdout+identity.stderr)
            result=subprocess.run(base+[str(jre/'bin/java'),'-Xms128m','-Xmx512m','-Dsun.java2d.opengl=true','-cp',str(state),'Java2DDriverBench'],capture_output=True,text=True,timeout=30,check=True)
            (state/'results'/(name+'.log')).write_text(result.stdout+result.stderr)
            report['runs'].append({'repeat':repeat+1,'path':mode,'data':json.loads(result.stdout)})
            print('JAVA2D',name,flush=True)
    report['completed']=True
finally:
    (gpu/'min_freq').write_text(old['min_freq']); (gpu/'max_freq').write_text(old['max_freq'])
    report['restored_limits']={k:(gpu/k).read_text().strip() for k in old}
    (state/'java2d-report.json').write_text(json.dumps(report,indent=2))
