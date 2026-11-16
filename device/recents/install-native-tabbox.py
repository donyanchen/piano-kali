#!/usr/bin/env python3
"""Keep the installed KWin Alt+Tab layout, disabling arrow-key wrap only."""
import hashlib
import json
import pathlib
import subprocess

source = pathlib.Path('/usr/share/kwin-wayland/tabbox/thumbnail_grid')
plugin_id = 'sheng-native-tabbox-spatial1'
target = pathlib.Path.home()/'.local/share/kwin-wayland/tabbox'/plugin_id
qml = (source/'contents/ui/main.qml').read_bytes()
assert qml.count(b'keyNavigationWraps: true') == 1
patched = qml.replace(b'keyNavigationWraps: true', b'keyNavigationWraps: false')
(target/'contents/ui').mkdir(parents=True, exist_ok=True)
(target/'contents/ui/main.qml').write_bytes(patched)
metadata = json.loads((source/'metadata.json').read_text())
metadata['KPlugin']['Id'] = plugin_id
(target/'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
state = pathlib.Path.home()/'.local/state/sheng-recents/native-tabbox-manifest.json'
state.write_text(json.dumps({'id':plugin_id, 'source':str(source), 'source_sha256':hashlib.sha256(qml).hexdigest(),
                             'installed_sha256':hashlib.sha256(patched).hexdigest(),
                             'changes':['keyNavigationWraps: true -> false'],
                             'upstream_license':metadata['KPlugin'].get('License')},indent=2)+'\n')
subprocess.run(['kwriteconfig6','--file','kwinrc','--group','TabBox','--key','LayoutName',plugin_id],check=True)
subprocess.run(['qdbus6','org.kde.KWin','/KWin','org.kde.KWin.reconfigure'],check=True)
print('Native Alt+Tab layout retained; arrow navigation stops at its edges')
