#!/usr/bin/env python3
import json
import pathlib
import subprocess
import sys

operation = sys.argv[1] if len(sys.argv)>1 else 'status'
result = None
if operation in ('on','off'):
    result = subprocess.run(['systemctl','start','--no-ask-password','sheng-privacy@'+operation+'.service'],capture_output=True,text=True)
elif operation != 'status': raise SystemExit(2)
try: status = json.loads(pathlib.Path('/run/sheng-privacy/status.json').read_text())
except (OSError,ValueError): status = {'enabled':False,'busy':False,'lastError':'隐私服务尚未就绪'}
if status.get('busy'):
    jobs = subprocess.run(['systemctl','show','sheng-privacy@on.service','sheng-privacy@off.service','-p','ActiveState','--value'],capture_output=True,text=True)
    if 'activating' not in jobs.stdout.splitlines():
        status['busy'] = False
        status['lastError'] = status.get('lastError') or '上次隐私切换未完成，请重试'
if result is not None and result.returncode:
    status['lastError'] = status.get('lastError') or '无法切换隐私权限'
print(json.dumps(status,ensure_ascii=False))
