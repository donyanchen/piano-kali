#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Package the pinned open-source Linexin launcher without restarting Plasma."""
import argparse
import hashlib
import io
import json
import pathlib
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

PROJECT=pathlib.Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=pathlib.Path)
    parser.add_argument('--output',type=pathlib.Path,default=PROJECT/'out/packages/sheng-desktop-drawer.plasmoid')
    args=parser.parse_args()
    pin=json.loads((PROJECT/'device/desktop-policy/drawer-provenance.json').read_text(encoding='utf-8'))
    if args.archive:data=args.archive.read_bytes()
    else:
        url=pin['upstream'].replace('https://github.com/','https://codeload.github.com/')+'/tar.gz/'+pin['commit']
        with urllib.request.urlopen(url,timeout=60) as response:data=response.read()
    if hashlib.sha256(data).hexdigest()!=pin['archive_sha256']:raise SystemExit('Archive SHA-256 mismatch')
    files={}
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
        for entry in archive.getmembers():
            parts=pathlib.PurePosixPath(entry.name).parts[1:]
            if '..' in parts or any('\\' in p or ':' in p for p in parts):raise SystemExit('Unsafe archive entry')
            if not entry.isfile():continue
            if len(parts)>1 and parts[0]==pin['package_directory']:files['/'.join(parts[1:])]=archive.extractfile(entry).read()
            elif parts==('LICENSE',):files['LICENSE']=archive.extractfile(entry).read()
    overlay=(PROJECT/'device/linexin-dock/CompactRepresentation.qml').read_bytes().replace(b'\r\n',b'\n')
    patch=(PROJECT/'device/linexin-dock/touch-edit.patch').read_bytes().replace(b'\r\n',b'\n')
    shared=(PROJECT/'device/linexin-dock/ShengDock.qml').read_bytes().replace(b'\r\n',b'\n')
    inner=(PROJECT/'device/linexin-dock/DrawerDock.qml').read_bytes().replace(b'\r\n',b'\n')
    icon=(PROJECT/'device/linexin-dock/apps-grid.svg').read_bytes().replace(b'\r\n',b'\n')
    burp_icon=(PROJECT/'device/theme/icons/burpsuite-rounded.svg').read_bytes().replace(b'\r\n',b'\n')
    recipe=pathlib.Path(__file__).read_bytes().replace(b'\r\n',b'\n')
    revision=hashlib.sha256(overlay+patch+shared+inner+icon+burp_icon+recipe).hexdigest()[:12]
    with tempfile.TemporaryDirectory(prefix='sheng-linexin-source-') as tmp:
        stage=pathlib.Path(tmp)
        for name,content in files.items():
            target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content.replace(b'\r\n',b'\n'))
        subprocess.run(['git','apply','--check','-'],input=patch,cwd=stage,check=True)
        subprocess.run(['git','apply','-'],input=patch,cwd=stage,check=True)
        files={p.relative_to(stage).as_posix():p.read_bytes().replace(b'\r\n',b'\n') for p in stage.rglob('*') if p.is_file()}
    metadata=json.loads(files['metadata.json'])
    if metadata['KPlugin']['Id']!=pin['plugin']:raise SystemExit('Unexpected plugin ID')
    metadata['KPlugin']['Id']='org.sheng.linexin.launcher.'+revision
    metadata['KPlugin']['Name']='Linexin Launcher + Dock'
    metadata['KPlugin']['Name[zh_CN]']='Linexin 应用抽屉与 Dock'
    metadata['KPlugin']['Version']='1.2.1-sheng-dock3'
    files['metadata.json']=(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n').encode()
    files['contents/ui/CompactRepresentation.qml']=overlay
    files['contents/ui/ShengDock.qml']=shared
    files['contents/icons/sheng-apps-grid.svg']=icon
    files['contents/icons/sheng-burp-rounded.svg']=burp_icon
    files['contents/ui/main.qml']=files['contents/ui/main.qml'].replace(b'    id: kicker',b'    id: kicker\n    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground',1)
    config=files['contents/config/main.xml'].decode()
    config=config.replace('<group name="General">','<group name="General">\n    <entry name="launchers" type="StringList"><default></default></entry>',1)
    files['contents/config/main.xml']=config.encode()
    dashboard=files['contents/ui/DashboardRepresentation.qml'].decode()
    dashboard=dashboard.replace('import QtQuick 2.15','import QtQuick',1)
    dashboard=dashboard.replace('import QtQml 2.15','import QtQml\nimport QtQuick.Window',1)
    # KWin constrains the real panel above the tagged fullscreen launcher.
    # The single Dock stays outside the launcher's fade/scale animations.
    dashboard=dashboard.replace('    id: root\n','''    id: root
    title: "Sheng Application Drawer"
    function toggleWithDock() {
        if (visible) closeWithAnimation();
        else { showFullScreen(); requestActivate(); }
    }
''',1)
    start=dashboard.index('        // Running apps only (no launchers)')
    end=dashboard.index('        // =============================================\n        //       SYSTEM ACTIONS',start)
    dashboard=dashboard[:start]+inner.decode()+'\n\n'+dashboard[end:]
    dashboard=dashboard.replace('runningRepeater','runningDockContainer.taskRepeater')
    dashboard=dashboard.replace('source: model.icon || ""','source: /^Burp Suite/.test(String(model.name || "")) ? Qt.resolvedUrl("../icons/sheng-burp-rounded.svg") : (model.icon || "")')
    dashboard=dashboard.replace('source: model.icon\n','source: /^Burp Suite/.test(String(model.name || "")) ? Qt.resolvedUrl("../icons/sheng-burp-rounded.svg") : model.icon\n')
    for delegate in ['ItemGridDelegate.qml','ItemListDelegate.qml']:
        name='contents/ui/'+delegate
        files[name]=files[name].replace(b'source: model.decoration',b'source: /^Burp Suite/.test(String(model.display || "")) ? Qt.resolvedUrl("../icons/sheng-burp-rounded.svg") : model.decoration')
    old="||t==='org.kde.plasma.expandingiconstaskmanager'){"
    new="||t==='org.kde.plasma.expandingiconstaskmanager'||t.indexOf('org.sheng.linexin.launcher')===0){"
    if old not in dashboard:raise SystemExit('Upstream Task Manager integration changed')
    files['contents/ui/DashboardRepresentation.qml']=dashboard.replace(old,new,1).encode()
    files['NOTICE.sheng']=('Linexin Launcher by Petexy, GPL-3.0-or-later.\nSource: '+pin['upstream']+'\nCommit: '+pin['commit']+'\nPackaged for Sheng desktop touch gestures.\n').encode()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED) as output:
        for name,content in sorted(files.items()):
            item=zipfile.ZipInfo(name,(1980,1,1,0,0,0));item.create_system=3;item.external_attr=0o100644<<16;item.compress_type=zipfile.ZIP_DEFLATED
            output.writestr(item,content.replace(b'\r\n',b'\n') if name.endswith(('.qml','.js','.xml','.json','.svg')) else content)
    result={'upstream':pin['upstream'],'commit':pin['commit'],'plugin':metadata['KPlugin']['Id'],'revision':revision,'artifact':args.output.name,'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}
    args.output.with_suffix('.manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
