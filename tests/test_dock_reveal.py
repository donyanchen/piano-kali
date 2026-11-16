# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise temporary Dock dismissal without touching a desktop session."""
import ast
import pathlib
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Timers:
    def __init__(self):
        self.callbacks = {}
        self.next_id = 1

    def timeout_add(self, interval, callback):
        identifier = self.next_id
        self.next_id += 1
        self.callbacks[identifier] = (interval, callback)
        return identifier

    def source_remove(self, identifier):
        del self.callbacks[identifier]


class DockRevealTest(unittest.TestCase):
    def setUp(self):
        self.timers = Timers()
        self.desktop_requests = []
        kwin = types.SimpleNamespace(showDesktop=self.desktop_requests.append)
        decorator = lambda *args, **kwargs: lambda function: function
        namespace = {'dbus': types.SimpleNamespace(service=types.SimpleNamespace(Object=object, method=decorator, signal=decorator), Interface=lambda *args: kwin), 'GLib': self.timers, 'BUS': types.SimpleNamespace(get_object=lambda *args: kwin)}
        tree = ast.parse((ROOT / 'device/desktop-policy/desktop-policy.py').read_text(encoding='utf-8'))
        definition = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Policy')
        exec(compile(ast.Module(body=[definition], type_ignores=[]), '<dock-policy-test>', 'exec'), namespace)
        self.policy = namespace['Policy'].__new__(namespace['Policy'])
        self.policy.dock_hidden = True
        self.policy.dock_revealed = False
        self.policy.showing_desktop = False
        self.policy.reveal_timeout = 0
        self.policy.visibility_published = True
        self.scripts = []
        self.visibility = []
        self.policy.script = self.scripts.append
        self.policy.DockVisibilityChanged = self.visibility.append
        self.policy.save_state = lambda: None

    def test_outside_dismiss_cancels_timeout_and_requests_native_hide(self):
        self.policy.RevealDock()
        timer = self.policy.reveal_timeout
        self.assertEqual(self.timers.callbacks[timer][0], 8000)
        self.assertEqual(self.visibility, [False])
        self.policy.DismissDock()
        self.assertNotIn(timer, self.timers.callbacks)
        self.assertFalse(self.policy.dock_revealed)
        self.assertEqual(self.policy.reveal_timeout, 0)
        self.assertTrue(self.policy.dock_hidden)
        self.assertEqual(self.visibility, [False, True])
        self.assertIn('p.hiding="autohide"', self.scripts[-1])
        count = len(self.scripts)
        self.policy.DismissDock()
        self.assertEqual(len(self.scripts), count)

    def test_regular_visible_dock_is_not_dismissed(self):
        self.policy.dock_hidden = False
        self.policy.DismissDock()
        self.assertFalse(self.scripts)
        self.assertFalse(self.timers.callbacks)
        self.assertFalse(self.visibility)

    def test_reveal_after_dismiss_uses_a_fresh_timeout(self):
        self.policy.RevealDock()
        old_timer = self.policy.reveal_timeout
        self.policy.DismissDock()
        self.policy.RevealDock()
        new_timer = self.policy.reveal_timeout
        self.assertNotEqual(old_timer, new_timer)
        self.assertNotIn(old_timer, self.timers.callbacks)
        self.assertTrue(self.policy.dock_revealed)
        self.timers.callbacks.pop(new_timer)[1]()
        self.assertFalse(self.policy.dock_revealed)
        self.assertEqual(self.visibility, [False, True, False, True])

    def test_home_keeps_dock_visible_and_uses_native_show_desktop(self):
        self.policy.RevealDock()
        self.policy.ShowDesktop()
        self.assertEqual(self.desktop_requests, [True])
        self.policy.showing_desktop_changed(True)
        self.assertTrue(self.policy.dock_hidden)
        self.assertFalse(self.policy.dock_revealed)
        self.assertFalse(self.timers.callbacks)
        self.assertEqual(self.visibility, [False])
        self.assertIn('p.hiding="windowsgobelow"', self.scripts[-1])
        # The compositor policy can hide again after returning to the app.
        self.policy.showing_desktop_changed(False)
        self.assertEqual(self.visibility, [False, True])

    def test_desktop_keeps_dock_visible_for_regular_window(self):
        self.policy.RevealDock()
        self.policy.ShowDesktop()
        self.policy.showing_desktop_changed(True)
        self.policy.SetDockHidden(False)
        self.policy.showing_desktop_changed(False)
        self.assertEqual(self.visibility, [False])
        self.assertIn('p.hiding="windowsgobelow"', self.scripts[-1])

    def test_home_requires_a_temporarily_revealed_dock(self):
        self.policy.ShowDesktop()
        self.assertFalse(self.desktop_requests)
        self.policy.dock_hidden = False
        self.policy.ShowDesktop()
        self.assertFalse(self.desktop_requests)


if __name__ == '__main__':
    unittest.main()
