#!/usr/bin/python3
"""Restore the pre-theme desktop configuration, without closing applications."""
from pathlib import Path
import json,os,shutil,subprocess

home=Path.home(); state=home/'.local/state/sheng-theme'
backup=Path((state/'latest-backup').read_text().strip())
if not backup.is_relative_to(state) or not (backup/'manifest.json').is_file():
    raise SystemExit('Invalid desktop backup path')
manifest=json.loads((backup/'manifest.json').read_text())
env=os.environ.copy(); env['XDG_RUNTIME_DIR']='/run/user/'+str(os.getuid()); env['DBUS_SESSION_BUS_ADDRESS']='unix:path='+env['XDG_RUNTIME_DIR']+'/bus'
subprocess.run(['systemctl','--user','stop','plasma-plasmashell.service'],env=env,check=True)
try:
    for name in manifest['present']:
        if Path(name).name!=name: raise RuntimeError('Invalid backup filename')
        shutil.copy2(backup/name,home/'.config'/name)
    for name in manifest['absent']:
        if Path(name).name!=name: raise RuntimeError('Invalid backup filename')
        (home/'.config'/name).unlink(missing_ok=True)
finally:
    subprocess.run(['systemctl','--user','start','plasma-plasmashell.service'],env=env,check=True)
subprocess.run(['qdbus6','org.kde.KWin','/KWin','reconfigure'],env=env,check=True)
print('Restored desktop configuration from '+str(backup))
