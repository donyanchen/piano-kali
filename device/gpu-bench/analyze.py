"""Analyze downloaded sheng GPU measurements; requires numpy on the host."""
import json,statistics,sys
from pathlib import Path
import numpy as np

directory=Path(sys.argv[1] if len(sys.argv)>1 else 'out/gpu-bench')
run_report=json.loads((directory/'run-report.json').read_text())
assert run_report['completed'], 'Benchmark did not complete'
if run_report.get('tag'):
    for workload in ['fill','ui','alu']:
        orders=[[r['path'] for r in run_report['runs'] if r['repeat']==repeat and r['workload']==workload] for repeat in (1,2,3)]
        for path in ['freedreno','turnip','zink-turnip']:
            assert sorted(order.index(path) for order in orders)==[0,1,2], 'Driver order is not counterbalanced'
telemetry=json.loads((directory/'telemetry.json').read_text())
validation=json.loads((directory/'image-validation.json').read_text())
assert all(validation['all_paths_identical_by_workload'].values()), 'Rendered images differ'
runs=[]
for run in run_report['runs']:
    data=json.loads((directory/'results'/(run['prefix']+'.json')).read_text())
    samples=np.array(data.pop('samples'))
    record={**run,**data,'fps':data['frames']/data['elapsed_s'],'wall_mean_ms':float(samples[:,0].mean()),'wall_p95_ms':float(np.percentile(samples[:,0],95)),'cpu_mean_ms':float(samples[:,1].mean()),'gpu_mean_ms':float(samples[:,2].mean())}
    interval=[t for t in telemetry if run['begin']<=t['monotonic']<=run['end']]
    clocks=[t['gpu_hz'] for t in interval]
    temps=[v for t in interval for v in t['gpu_temperatures_mc'].values() if v>0]
    record['gpu_clock_min_hz']=min(clocks); record['gpu_clock_max_hz']=max(clocks)
    record['gpu_temperature_min_c']=min(temps)/1000; record['gpu_temperature_max_c']=max(temps)/1000
    runs.append(record)
summary=[]
for workload in ['fill','ui','alu']:
    for path in ['freedreno','turnip','zink-turnip']:
        group=[r for r in runs if r['workload']==workload and r['path']==path]
        row={'workload':workload,'path':path,'repeats':len(group)}
        for key in ['fps','wall_mean_ms','wall_p95_ms','cpu_mean_ms','gpu_mean_ms','rss_kib','pss_kib']:
            row[key]=round(statistics.median(r[key] for r in group),5)
        row['fps_min']=round(min(r['fps'] for r in group),3); row['fps_max']=round(max(r['fps'] for r in group),3)
        summary.append(row)
paired=[]
for workload in ['fill','ui','alu']:
    for path in ['turnip','zink-turnip']:
        ratios=[]
        for repeat in (1,2,3):
            base=next(r for r in runs if r['workload']==workload and r['path']=='freedreno' and r['repeat']==repeat)
            other=next(r for r in runs if r['workload']==workload and r['path']==path and r['repeat']==repeat)
            ratios.append((other['fps']/base['fps']-1)*100)
        paired.append({'workload':workload,'path':path,'fps_change_vs_freedreno_percent_by_repeat':ratios,'median_percent':statistics.median(ratios)})
result={'method':{'hardware':'Xiaomi Pad 6S Pro / Adreno 740','mesa':'26.1.6','resolution':[3048,2032],'format':'RGBA8','msaa':1,'depth':False,'present':False,'vsync':False,'gpu_clock_hz':550000000,'cpu_affinity':'4-7, existing schedutil governor retained','warmup_s':1,'measurement_s_per_run':4,'repeats':3,'ordering':'rotated API and workload order; balanced tag gives each path each order position once per workload','frames_in_flight':1,'vulkan_command_buffers':'re-recorded every frame','readback':'outside timing and memory snapshots','reported_group_value':'median of three run values','workloads':{'fill':'One full-screen gradient triangle','ui':'2048 scissored alpha-blended draws, two 32x32 grids','alu':'One full-screen triangle, 64 dependent vector/sine iterations'},'limits':['Small synthetic workload suite; not a universal driver ranking','Native GL versus native Vulkan also compares API and application implementations','Zink uses the exact same OpenGL application and shaders as freedreno','Offscreen results are not visible KDE refresh rate or a real Burp benchmark','No direct electrical power measurement; no joules-per-frame claim','Process RSS/PSS excludes unmapped GPU allocations; not total graphics memory','CPU and memory-system clocks remain adaptive; thermal conditions vary and are recorded']},'image_validation':validation['all_paths_identical_by_workload'],'total_measured_frames':sum(r['frames'] for r in runs),'gpu_clock_observed_hz':sorted({t['gpu_hz'] for t in telemetry}),'gpu_temperature_range_c':[min(r['gpu_temperature_min_c'] for r in runs),max(r['gpu_temperature_max_c'] for r in runs)],'restored_limits':run_report['restored_limits'],'summary':summary,'paired_comparisons':paired,'runs':runs}
java_path=directory/'java2d-report.json'
if java_path.exists() and java_path.stat().st_size:
    java=json.loads(java_path.read_text()); rows=[]
    for path in ['freedreno','zink-turnip']:
        group=[r for r in java['runs'] if r['path']==path]
        times=[]; cpus=[]
        for r in group:
            passes=[p for p in r['data']['passes'] if not p['warmup']]
            frames=r['data']['frames_per_pass']
            times.append(statistics.mean(p['wall_ms']/frames for p in passes))
            cpus.append(statistics.mean(p['cpu_ms']/frames for p in passes))
        if times: rows.append({'path':path,'wall_mean_ms_per_paint':statistics.median(times),'cpu_mean_ms_per_paint':statistics.median(cpus),'run_wall_ms_per_paint':times})
    result['java2d_supplement']={'completed':java.get('completed',False),'resolution':[1600,1000],'frames_per_pass':120,'passes_per_run':5,'first_pass_excluded':True,'repeats':3,'completion':'VolatileImage.getSnapshot after each pass to force readback/completion','scope':'Synthetic table/text/alpha Java2D painting; not full Burp responsiveness','summary':rows}
(directory/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
print('workload path           fps    wall_ms p95_ms cpu_ms gpu_ms RSS_MiB')
for r in summary:
    print(f"{r['workload']:8} {r['path']:13} {r['fps']:7.1f} {r['wall_mean_ms']:7.3f} {r['wall_p95_ms']:7.3f} {r['cpu_mean_ms']:6.3f} {r['gpu_mean_ms']:6.3f} {r['rss_kib']/1024:7.1f}")
print('frames',result['total_measured_frames'],'clock',result['gpu_clock_observed_hz'],'temperature',result['gpu_temperature_range_c'])
if 'java2d_supplement' in result: print(json.dumps(result['java2d_supplement']['summary'],indent=2))
