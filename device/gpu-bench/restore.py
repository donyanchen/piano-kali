import json
from pathlib import Path
state=Path('/home/kali/.local/state/sheng-gpu-bench')
snapshot=state/'limits-before.json'
if snapshot.exists():
    old=json.loads(snapshot.read_text())
    gpu=Path('/sys/class/devfreq/3d00000.gpu')
    (gpu/'min_freq').write_text(old['min_freq'])
    (gpu/'max_freq').write_text(old['max_freq'])
    (state/'limits-restored.json').write_text(json.dumps({k:(gpu/k).read_text().strip() for k in ['min_freq','max_freq','governor']},indent=2))
