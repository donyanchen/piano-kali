import datetime, hashlib, json, os, signal, statistics, subprocess, sys, threading, time
from pathlib import Path

state=Path('/home/kali/.local/state/sheng-gpu-bench')
tag=sys.argv[1] if len(sys.argv)>1 else 'balanced'
assert tag.isalnum()
resultdir=state/('results-'+tag)
resultdir.mkdir(exist_ok=True)
os.chown(resultdir,1000,1000)
gpu=Path('/sys/class/devfreq/3d00000.gpu')
stop=threading.Event()
telemetry=[]
thermal_paths={p.name:p for p in Path('/sys/class/thermal').glob('thermal_zone*') if 'gpuss' in (p/'type').read_text()}
def read(path):
    try: return Path(path).read_text().strip()
    except OSError: return None
def sample():
    while not stop.wait(.1):
        telemetry.append({'monotonic':time.monotonic(),'gpu_hz':int(read(gpu/'cur_freq') or 0),'gpu_temperatures_mc':{p.name:int(read(p/'temp') or 0) for p in thermal_paths.values()},'cpu7_khz':int(read('/sys/devices/system/cpu/cpu7/cpufreq/scaling_cur_freq') or 0)})

def term(signum,frame): raise RuntimeError('Benchmark terminated: '+str(signum))
signal.signal(signal.SIGTERM,term)
signal.signal(signal.SIGINT,term)

old={k:read(gpu/k) for k in ['min_freq','max_freq','governor']}
(state/'limits-before.json').write_text(json.dumps(old,indent=2))
target=550000000
assert int(old['min_freq'])<=target<=int(old['max_freq'])
runs=[]
report={'started_at':datetime.datetime.now().astimezone().isoformat(),'tag':tag,'gpu_clock_target_hz':target,'old_limits':old,'thermal_sensors':{p.name:read(p/'type') for p in thermal_paths.values()},'sources_sha256':{name:hashlib.sha256((state/name).read_bytes()).hexdigest() for name in ['bench.cpp','scene.vert','scene.frag','run.py']},'runs':runs}
try:
    (gpu/'max_freq').write_text(str(target))
    (gpu/'min_freq').write_text(str(target))
    thread=threading.Thread(target=sample,daemon=True); thread.start()
    # Latin-square order rotates APIs and workloads to reduce order/heat bias.
    apis=['freedreno','turnip','zink-turnip']
    work=['fill','ui','alu']
    for repeat in range(3):
        for wi in range(3):
            workload=work[(wi+repeat)%3]
            for ai in range(3):
                api=apis[(ai+repeat+2*wi)%3]
                prefix=f'{repeat+1}-{workload}-{api}'
                env={'XDG_RUNTIME_DIR':'/run/user/1000','VK_DRIVER_FILES':'/usr/share/vulkan/icd.d/freedreno_icd.json','EGL_PLATFORM':'surfaceless'}
                if api=='zink-turnip': env.update(GALLIUM_DRIVER='zink',MESA_LOADER_DRIVER_OVERRIDE='zink')
                command=['/usr/sbin/runuser','-u','kali','--','/usr/bin/taskset','-c','4-7','/usr/bin/env']+[f'{k}={v}' for k,v in env.items()]+[str(state/'bench'),'vk' if api=='turnip' else 'gl',workload,'4',str(resultdir/prefix)]
                begin=time.monotonic()
                print('RUN',prefix,flush=True)
                result=subprocess.run(command,cwd=state,capture_output=True,text=True,timeout=65)
                end=time.monotonic()
                (resultdir/(prefix+'.log')).write_text(result.stdout+result.stderr)
                print(result.stdout.strip(),flush=True)
                if result.returncode: raise RuntimeError(prefix+' failed: '+result.stderr)
                data=json.loads((resultdir/(prefix+'.json')).read_text())
                assert data['frames']>0 and data['width']==3048 and data['height']==2032
                assert (resultdir/(prefix+'.rgba')).stat().st_size==3048*2032*4
                runs.append({'repeat':repeat+1,'workload':workload,'path':api,'prefix':prefix,'begin':begin,'end':end})
                (state/('progress-'+tag+'.json')).write_text(json.dumps(report,indent=2))
                time.sleep(.5)
    report['completed']=True
except Exception as exc:
    report['completed']=False; report['error']=repr(exc); raise
finally:
    stop.set()
    (gpu/'min_freq').write_text(old['min_freq'])
    (gpu/'max_freq').write_text(old['max_freq'])
    report['finished_at']=datetime.datetime.now().astimezone().isoformat()
    report['restored_limits']={k:read(gpu/k) for k in ['min_freq','max_freq','governor']}
    (state/('run-report-'+tag+'.json')).write_text(json.dumps(report,indent=2))
    (state/('telemetry-'+tag+'.json')).write_text(json.dumps(telemetry,separators=(',',':')))
