#!/usr/bin/env python3
"""One-shot, reversible device privacy policy for the sheng tablet."""
import base64
import contextlib
import fcntl
import grp
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import time

PRIVATE = pathlib.Path('/var/lib/sheng-privacy')
PUBLIC = pathlib.Path('/run/sheng-privacy')
STATE_FILE = PRIVATE/'state.json'
MARKER = PRIVATE/'blocked'
LOCATION_UNITS = ['geoclue.service', 'gpsd.service', 'gpsd.socket']
CAMERA_DRIVERS = [('platform', 'qcom-camss'), ('usb', 'uvcvideo')]
GUARD = '/usr/libexec/sheng-privacy-bpf'
CGROUP = pathlib.Path('/sys/fs/cgroup')
FROZEN = CGROUP/'sheng-privacy-frozen'
BUS_POLICIES = {
    pathlib.Path('/etc/dbus-1/session.d/51-sheng-privacy.conf'): [
        '<deny send_interface="org.freedesktop.portal.Camera"/>',
        '<deny send_interface="org.freedesktop.portal.Location"/>',
        '<deny send_interface="org.freedesktop.portal.Microphone"/>'],
    pathlib.Path('/etc/dbus-1/system.d/51-sheng-privacy.conf'): [
        '<deny send_destination="org.freedesktop.GeoClue2"/>',
        '<deny send_interface="org.freedesktop.GeoClue2.Manager"/>',
        '<deny send_interface="org.freedesktop.GeoClue2.Client"/>',
        '<deny send_interface="org.freedesktop.GeoClue2.Location"/>',
        '<deny receive_sender="org.freedesktop.GeoClue2"/>']}


def command(args, check=True):
    result = subprocess.run(args, text=True, capture_output=True, timeout=8, env={**os.environ, 'LC_ALL':'C.UTF-8'})
    if check and result.returncode:
        raise RuntimeError(' '.join(args[:2])+': '+result.stderr.strip()[:250])
    return result


def user_command(args, check=False):
    return command(['runuser','-u','kali','--','env','XDG_RUNTIME_DIR=/run/user/1000',
                    'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus',*args],check)


def save_json(path, value, mode=0o600):
    temp = path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temp.chmod(mode)
    temp.replace(path)


def camera_bindings():
    found = []
    for bus, driver in CAMERA_DRIVERS:
        directory = pathlib.Path('/sys/bus')/bus/'drivers'/driver
        if not directory.exists(): continue
        for path in directory.iterdir():
            if path.is_symlink() and str(path.resolve()).startswith('/sys/devices/'):
                found.append({'bus':bus,'driver':driver,'device':path.name})
    return found


def capture_nodes():
    nodes = list(pathlib.Path('/dev/snd').glob('pcmC*D*c'))
    for path in pathlib.Path('/sys/class/video4linux').glob('*'):
        driver = (path/'device/driver').resolve().name
        if driver in ('qcom-camss','uvcvideo'):
            node = pathlib.Path('/dev')/path.name
            if node.exists(): nodes.append(node)
    return nodes


def node_identity(path):
    if path.parent == pathlib.Path('/dev/snd') and re.fullmatch(r'pcmC\d+D\d+c',path.name):
        return path.name
    if path.parent == pathlib.Path('/dev') and re.fullmatch(r'(video|v4l-subdev)\d+',path.name):
        item = pathlib.Path('/sys/class/video4linux')/path.name
        if (item/'device/driver').resolve().name in ('qcom-camss','uvcvideo'):
            return (item/'name').read_text().strip()
    raise RuntimeError('Unexpected capture device')


def remember_nodes(saved):
    for path in capture_nodes():
        key = str(path)
        if key in saved['nodes']: continue
        info = path.stat()
        if not stat.S_ISCHR(info.st_mode): continue
        try: acl = base64.b64encode(os.getxattr(path,'system.posix_acl_access')).decode()
        except OSError: acl = None
        saved['nodes'][key] = {'uid':info.st_uid,'gid':info.st_gid,'mode':stat.S_IMODE(info.st_mode),
                               'acl':acl,'identity':node_identity(path)}


def deny_nodes():
    for path in capture_nodes():
        node_identity(path)
        with contextlib.suppress(OSError): os.removexattr(path,'system.posix_acl_access')
        os.chown(path,0,0)
        os.chmod(path,0o600)


def restore_nodes(saved):
    for filename, info in saved['nodes'].items():
        path = pathlib.Path(filename)
        if not path.exists(): continue
        if node_identity(path) != info['identity']: continue
        os.chown(path,info['uid'],info['gid'])
        os.chmod(path,info['mode'])
        if info['acl']: os.setxattr(path,'system.posix_acl_access',base64.b64decode(info['acl']))
        else:
            with contextlib.suppress(OSError): os.removexattr(path,'system.posix_acl_access')


def mixers():
    found = {}
    for path in pathlib.Path('/sys/class/sound').glob('card*'):
        if not (path/'id').is_file() or (path/'id').read_text().strip() != 'XiaomiPad6SPro': continue
        card = path.name.removeprefix('card')
        text = command(['amixer','-c',card,'controls']).stdout
        for line in text.splitlines():
            match = re.search(r"numid=(\d+).*name='(TX [SD]MIC MUX\d+)'",line)
            if not match: continue
            number, name = match.groups()
            detail = command(['amixer','-c',card,'cget','numid='+number]).stdout
            value = re.search(r': values=([0-9,]+)',detail)
            if value and "Item #0 'ZERO'" in detail:
                found[name] = {'card':card,'numid':number,'value':value[1]}
    return found


def sources():
    result = user_command(['pactl','--format=json','list','sources'])
    try: data = json.loads(result.stdout)
    except ValueError: return []
    return [{'name':item['name'],'muted':bool(item.get('mute'))} for item in data if not item['name'].endswith('.monitor')]


def bus_policy(blocked):
    for path, rules in BUS_POLICIES.items():
        text = '<busconfig>\n'
        if blocked: text += '<policy context="mandatory">\n'+'\n'.join(rules)+'\n</policy>\n'
        path.write_text(text+'</busconfig>\n')
    reload = ['dbus-send','--print-reply','--dest=org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus.ReloadConfig']
    if pathlib.Path('/run/dbus/system_bus_socket').exists(): command([reload[0],'--system',*reload[1:]])
    if pathlib.Path('/run/user/1000/bus').exists(): user_command([reload[0],'--session',*reload[1:]],True)


def process_identity(pid):
    try:
        text = pathlib.Path('/proc',str(pid),'stat').read_text()
        return text.rsplit(')',1)[1].split()[19]
    except (OSError,IndexError): return None


def capture_holders():
    protected = set()
    paths = list(pathlib.Path('/dev/snd').glob('pcmC*D*c'))+list(pathlib.Path('/dev').glob('gnss*'))
    for path in paths:
        with contextlib.suppress(OSError): protected.add(path.stat().st_rdev)
    holders = []
    for process in pathlib.Path('/proc').iterdir():
        if not process.name.isdigit() or int(process.name)==os.getpid(): continue
        try:
            for fd in (process/'fd').iterdir():
                try: info = fd.stat()
                except OSError: continue
                if stat.S_ISCHR(info.st_mode) and info.st_rdev in protected:
                    holders.append(int(process.name));break
        except OSError: pass
    return holders


def freeze_clients(state):
    saved = state['saved']
    boot = pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    entries = []
    for entry in saved.get('frozen',[]):
        try: group=pathlib.Path('/proc',str(entry['pid']),'cgroup').read_text()
        except OSError: continue
        if entry.get('boot')==boot and process_identity(entry['pid'])==entry['identity'] and '0::/sheng-privacy-frozen\n' in group:
            entries.append(entry)
    saved['frozen'] = entries
    # Suspend has normally closed PipeWire's capture FD. If a source is still
    # retained, remove just that input node before pausing direct device users.
    holders = capture_holders()
    pipewire_held = False
    for pid in holders:
        with contextlib.suppress(OSError): pipewire_held |= pathlib.Path('/proc',str(pid),'comm').read_text().strip()=='pipewire'
    if pipewire_held:
        dump = user_command(['pw-dump'])
        try: objects = json.loads(dump.stdout)
        except ValueError: objects = []
        for item in objects:
            if item.get('info',{}).get('props',{}).get('media.class')=='Audio/Source':
                user_command(['pw-cli','destroy',str(item['id'])])
        time.sleep(.2)
        holders = capture_holders()
    if holders:
        FROZEN.mkdir(exist_ok=True)
        (FROZEN/'cgroup.freeze').write_text('1')
    for pid in holders:
        if any(x['pid']==pid for x in entries): continue
        identity = process_identity(pid)
        if identity is None: continue
        try: original = next(x.split('::',1)[1] for x in pathlib.Path('/proc',str(pid),'cgroup').read_text().splitlines() if x.startswith('0::'))
        except (OSError,StopIteration): continue
        entry = {'pid':pid,'identity':identity,'boot':boot,'cgroup':original}
        entries.append(entry)
        save_json(STATE_FILE,state)
        if process_identity(pid)==identity:
            with contextlib.suppress(ProcessLookupError): (FROZEN/'cgroup.procs').write_text(str(pid))
    if holders:
        for _ in range(40):
            if 'frozen 1' in (FROZEN/'cgroup.events').read_text(): break
            time.sleep(.025)
        else: raise RuntimeError('Existing capture client could not be suspended')


def resume_clients(saved):
    boot = pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    for entry in saved.get('frozen',[]):
        if entry.get('boot')!=boot or process_identity(entry['pid'])!=entry['identity']: continue
        target = (CGROUP/entry['cgroup'].lstrip('/')).resolve()
        if not target.is_relative_to(CGROUP): raise RuntimeError('Invalid saved process group')
        if not target.exists(): target.mkdir(parents=True,exist_ok=True)
        (target/'cgroup.procs').write_text(str(entry['pid']))
    if FROZEN.exists():
        (FROZEN/'cgroup.freeze').write_text('0')
        with contextlib.suppress(OSError): FROZEN.rmdir()
    saved['frozen'] = []


def publish(state, busy=False, error=''):
    gps = bool(list(pathlib.Path('/dev').glob('gnss*')))
    enabled = bool(state.get('enabled'))
    status = {'enabled':enabled,'busy':busy,'gpsHardware':gps,'lastError':error,
              'processGuard':enabled and pathlib.Path('/sys/fs/bpf/sheng-privacy/device-guard').exists(),
              'pausedCaptureProcesses':len(state.get('saved',{}).get('frozen',[])),
              'cameraSupported':bool(state.get('saved',{}).get('bindings') or camera_bindings()),
              'hint':('已拦截应用和进程的摄像头、麦克风、定位请求' if enabled else '允许摄像头、麦克风和定位请求')
                     +('；GPS 定位随隐私开关控制' if gps else '；未检测到 GPS 硬件')}
    if status['pausedCaptureProcesses']: status['hint'] += '；直连采集进程已暂停，关闭隐私后恢复'
    save_json(PUBLIC/'status.json',status,0o644)


def block(state):
    saved = state.setdefault('saved',{'nodes':{},'mixers':{},'sources':[],'bindings':[],'location':{}})
    remember_nodes(saved)
    current_mixers = mixers()
    for name, item in current_mixers.items(): saved['mixers'].setdefault(name,item)
    existing_sources = sources()
    if not saved['sources']: saved['sources'] = existing_sources
    for binding in camera_bindings():
        if binding not in saved['bindings']: saved['bindings'].append(binding)
    for unit in LOCATION_UNITS:
        if unit not in saved['location']:
            enabled = command(['systemctl','is-enabled',unit],False).stdout.strip()
            active = command(['systemctl','is-active',unit],False).stdout.strip() == 'active'
            saved['location'][unit] = {'masked':enabled.startswith('masked'),'active':active}
    state['enabled'] = True
    save_json(STATE_FILE,state)
    MARKER.touch(mode=0o600,exist_ok=True)
    publish(state,True)
    for source in existing_sources:
        # Revoke the capture path without persisting a temporary software mute
        # into WirePlumber's state for a later recreated input node.
        user_command(['pactl','suspend-source',source['name'],'1'])
    for item in current_mixers.values():
        command(['amixer','-c',item['card'],'cset','numid='+item['numid'],'0'])
    deny_nodes()
    for binding in camera_bindings():
        directory = pathlib.Path('/sys/bus')/binding['bus']/'drivers'/binding['driver']
        if (directory/binding['device']).exists(): (directory/'unbind').write_text(binding['device'])
    for unit, previous in saved['location'].items():
        if not previous['masked']:
            command(['systemctl','mask','--runtime',unit])
            if previous['active']: command(['systemctl','stop',unit])
    bus_policy(True)
    command([GUARD,'enable'])
    freeze_clients(state)
    save_json(STATE_FILE,state)
    publish(state)


def allow(state):
    saved = state.get('saved',{'nodes':{},'mixers':{},'sources':[],'bindings':[],'location':{}})
    command([GUARD,'disable'])
    bus_policy(False)
    resume_clients(saved)
    MARKER.unlink(missing_ok=True)
    for binding in saved['bindings']:
        assert (binding['bus'],binding['driver']) in CAMERA_DRIVERS
        assert re.fullmatch(r'[A-Za-z0-9_.:-]+',binding['device'])
        if not (pathlib.Path('/sys/bus')/binding['bus']/'devices'/binding['device']).exists(): continue
        directory = pathlib.Path('/sys/bus')/binding['bus']/'drivers'/binding['driver']
        if directory.exists() and not (directory/binding['device']).exists():
            (directory/'bind').write_text(binding['device'])
    command(['udevadm','settle','--timeout=5'],False)
    restore_nodes(saved)
    for path in capture_nodes():
        if str(path) not in saved['nodes']:
            group = 'audio' if path.parent == pathlib.Path('/dev/snd') else 'video'
            os.chown(path,0,grp.getgrnam(group).gr_gid)
            os.chmod(path,0o660)
    current_mixers = mixers()
    for name, before in saved['mixers'].items():
        if name in current_mixers:
            item = current_mixers[name]
            command(['amixer','-c',item['card'],'cset','numid='+item['numid'],before['value']])
    deadline = time.monotonic()+4
    current_sources = sources()
    while not current_sources and list(pathlib.Path('/dev/snd').glob('pcmC*D*c')) and time.monotonic()<deadline:
        time.sleep(0.25)
        current_sources = sources()
    for source in current_sources:
        user_command(['pactl','suspend-source',source['name'],'0'])
        user_command(['pactl','set-source-mute',source['name'],'0'],True)
    for unit, previous in saved['location'].items():
        if not previous['masked']: command(['systemctl','unmask','--runtime',unit])
        if previous['active']: command(['systemctl','start',unit])
    state = {'enabled':False}
    save_json(STATE_FILE,state)
    publish(state)
    return state


def main():
    if os.geteuid() != 0: raise SystemExit('Run through the authorized privacy service')
    action = sys.argv[1]
    if action not in ('on','off','restore'): raise SystemExit('Invalid privacy action')
    PRIVATE.mkdir(mode=0o700,parents=True,exist_ok=True)
    PUBLIC.mkdir(mode=0o755,parents=True,exist_ok=True)
    if action == 'restore': command([GUARD,'prepare'])
    with (PUBLIC/'lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {'enabled':False}
        was_enabled = state.get('enabled',False)
        try:
            if action == 'on' or (action == 'restore' and was_enabled): block(state)
            elif action == 'off': state = allow(state)
            else: publish(state)
        except Exception as error:
            if not was_enabled:
                with contextlib.suppress(Exception): state = allow(state)
            elif action == 'off':
                with contextlib.suppress(Exception): block(state)
            publish(state,error=str(error))
            raise


if __name__ == '__main__': main()
