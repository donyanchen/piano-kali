#!/usr/bin/env python3
"""Event-driven pointer detection and native Plasma Dock policy."""
import json
import pathlib
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)
BUS = dbus.SessionBus()
STATE = pathlib.Path.home()/'.local/state/sheng-desktop-policy'
STATE.mkdir(parents=True, exist_ok=True)


class Policy(dbus.service.Object):
    def __init__(self):
        self.name = dbus.service.BusName('org.sheng.DesktopPolicy', BUS)
        super().__init__(self.name, '/org/sheng/DesktopPolicy')
        try: previous = json.loads((STATE/'state.json').read_text())
        except (OSError,ValueError): previous = {}
        self.dock_hidden = bool(previous.get('dock_hidden',False))
        self.dock_revealed = False
        self.showing_desktop = self.read_showing_desktop()
        self.reveal_timeout = 0
        self.visibility_published = None
        self.pointers = []
        self.pending = 0
        self.sync_pending = 0
        self.published = None
        self.dock_attached = self.read_dock_attached()
        BUS.add_signal_receiver(self.inputs_changed, dbus_interface='org.kde.KWin.InputDeviceManager', path='/org/kde/KWin/InputDevice')
        BUS.add_signal_receiver(self.owner_changed, signal_name='NameOwnerChanged', dbus_interface='org.freedesktop.DBus', arg0='org.kde.plasmashell')
        BUS.add_signal_receiver(self.inputs_changed, signal_name='NameOwnerChanged', dbus_interface='org.freedesktop.DBus', arg0='org.kde.KWin')
        BUS.add_signal_receiver(self.showing_desktop_changed, signal_name='showingDesktopChanged', dbus_interface='org.kde.KWin', path='/KWin')
        self.rescan()
        GLib.timeout_add(250,self.watch_dock)

    def read_dock_attached(self):
        try: return pathlib.Path('/sys/class/misc/nanosic_hinge/keyboard_attached').read_text().strip() == '1'
        except OSError: return True

    def read_showing_desktop(self):
        try:
            properties = dbus.Interface(BUS.get_object('org.kde.KWin', '/KWin'), 'org.freedesktop.DBus.Properties')
            return bool(properties.Get('org.kde.KWin', 'showingDesktop'))
        except dbus.DBusException:
            return False

    def showing_desktop_changed(self, showing):
        self.showing_desktop = bool(showing)
        if self.showing_desktop:
            self.cancel_reveal()
        self.apply_dock()

    def watch_dock(self):
        attached = self.read_dock_attached()
        if attached != self.dock_attached:
            self.dock_attached = attached
            self.rescan()
        return True

    def script(self, text):
        try:
            obj = BUS.get_object('org.kde.plasmashell', '/PlasmaShell')
            return str(dbus.Interface(obj, 'org.kde.PlasmaShell').evaluateScript(text, timeout=8))
        except dbus.DBusException:
            return ''

    def inputs_changed(self, *args):
        if self.pending:
            GLib.source_remove(self.pending)
        self.pending = GLib.timeout_add(400, self.rescan)

    def owner_changed(self, name, old, new):
        if new:
            self.published = None
            GLib.timeout_add(900, self.sync)

    def rescan(self):
        self.pending = 0
        self.showing_desktop = self.read_showing_desktop()
        found = []
        try:
            manager = dbus.Interface(BUS.get_object('org.kde.KWin', '/org/kde/KWin/InputDevice'), 'org.freedesktop.DBus.Properties')
            names = manager.Get('org.kde.KWin.InputDeviceManager', 'devicesSysNames')
            for name in names:
                try:
                    prop = dbus.Interface(BUS.get_object('org.kde.KWin', '/org/kde/KWin/InputDevice/'+str(name)), 'org.freedesktop.DBus.Properties')
                    values = prop.GetAll('org.kde.KWin.InputDevice')
                    if str(values.get('name','')) in ('Xiaomi Keyboard','Xiaomi Touchpad') and not self.read_dock_attached():
                        continue
                    if values.get('enabled') and not values.get('isVirtual') and (values.get('pointer') or values.get('touchpad')):
                        found.append(str(values.get('name', name)))
                except dbus.DBusException:
                    pass
        except dbus.DBusException:
            self.pending = GLib.timeout_add(1500, self.rescan)
            return False
        self.pointers = found
        self.sync()
        return False

    def sync(self):
        present = bool(self.pointers)
        if self.published != present:
            self.PointerPresenceChanged(present)
            value = 'true' if present else 'false'
            result = self.script('var n=0; panels().concat(desktops()).forEach(function(p){p.widgets().forEach(function(w){if(w.type==="org.kontrol.center" || w.type.indexOf("org.sheng.desktop-gesture")===0){w.currentConfigGroup=["Appearance"];w.writeConfig("pointerPresent",'+value+');w.reloadConfig();n++;}})}); print(n);')
            if result.strip() not in ('', '0'):
                self.published = present
            elif not self.sync_pending:
                self.sync_pending = GLib.timeout_add(1500,self.retry_sync)
        self.apply_dock()
        self.save_state()
        return False

    def save_state(self):
        (STATE/'state.json').write_text(json.dumps({'pointer_present':bool(self.pointers), 'pointer_devices':self.pointers, 'dock_hidden':self.dock_hidden},ensure_ascii=False)+'\n')

    def retry_sync(self):
        self.sync_pending = 0
        return self.sync()

    @dbus.service.signal('org.sheng.DesktopPolicy', signature='b')
    def PointerPresenceChanged(self, present):
        pass

    @dbus.service.signal('org.sheng.DesktopPolicy', signature='b')
    def DockVisibilityChanged(self, hidden):
        pass

    def apply_dock(self):
        effective_hidden = self.dock_hidden and not self.dock_revealed and not self.showing_desktop
        hiding = 'autohide' if effective_hidden else 'windowsgobelow'
        self.script('panels().forEach(function(p){p.currentConfigGroup=["General"];if(p.readConfig("ShengThemeRole","")==="dock" && p.hiding!=="'+hiding+'")p.hiding="'+hiding+'";});')
        if self.visibility_published != effective_hidden:
            self.visibility_published = effective_hidden
            self.DockVisibilityChanged(effective_hidden)

    @dbus.service.method('org.sheng.DesktopPolicy', in_signature='b', out_signature='')
    def SetDockHidden(self, hidden):
        if self.dock_hidden != bool(hidden):
            self.cancel_reveal()
        self.dock_hidden = bool(hidden)
        self.apply_dock()
        self.save_state()

    def cancel_reveal(self):
        if self.reveal_timeout:
            GLib.source_remove(self.reveal_timeout)
            self.reveal_timeout = 0
        self.dock_revealed = False

    @dbus.service.method('org.sheng.DesktopPolicy', in_signature='', out_signature='')
    def RevealDock(self):
        if not self.dock_hidden:
            return
        self.cancel_reveal()
        self.dock_revealed = True
        self.apply_dock()
        self.reveal_timeout = GLib.timeout_add(8000, self.finish_reveal)

    @dbus.service.method('org.sheng.DesktopPolicy', in_signature='', out_signature='')
    def DismissDock(self):
        if not self.dock_revealed:
            return
        self.cancel_reveal()
        self.apply_dock()

    @dbus.service.method('org.sheng.DesktopPolicy', in_signature='', out_signature='')
    def ShowDesktop(self):
        if not (self.dock_hidden and self.dock_revealed):
            return
        self.cancel_reveal()
        kwin = BUS.get_object('org.kde.KWin', '/KWin')
        try:
            dbus.Interface(kwin, 'org.kde.KWin').showDesktop(True)
        except dbus.DBusException:
            self.apply_dock()
            raise

    def finish_reveal(self):
        self.reveal_timeout = 0
        self.dock_revealed = False
        self.apply_dock()
        return False

    @dbus.service.method('org.sheng.DesktopPolicy', in_signature='', out_signature='s')
    def GetState(self):
        return json.dumps({'pointer_present':bool(self.pointers), 'pointer_devices':self.pointers, 'dock_hidden':self.dock_hidden, 'dock_revealed':self.dock_revealed, 'showing_desktop':self.showing_desktop},ensure_ascii=False)

    @dbus.service.method('org.sheng.DesktopPolicy', in_signature='', out_signature='')
    def OpenControlCenter(self):
        identifier = self.script('var id=0;panels().forEach(p=>p.widgets().forEach(w=>{if(w.type==="org.kontrol.center")id=w.id}));print(id);').strip()
        if not identifier.isdigit() or identifier == '0': return
        obj = BUS.get_object('org.kde.kglobalaccel','/component/plasmashell')
        dbus.Interface(obj,'org.kde.kglobalaccel.Component').invokeShortcut('activate widget '+identifier)

    @dbus.service.method('org.sheng.DesktopPolicy', in_signature='', out_signature='')
    def OpenAppDrawer(self):
        identifier = self.script('var id=0;panels().concat(desktops()).forEach(p=>p.widgets().forEach(w=>{if(w.type.indexOf("org.sheng.linexin.launcher")===0)id=w.id}));print(id);').strip()
        if not identifier.isdigit() or identifier == '0':
            return
        obj = BUS.get_object('org.kde.kglobalaccel','/component/plasmashell')
        dbus.Interface(obj,'org.kde.kglobalaccel.Component').invokeShortcut('activate widget '+identifier)


policy = Policy()
GLib.MainLoop().run()
