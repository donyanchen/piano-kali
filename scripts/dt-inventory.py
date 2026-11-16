#!/usr/bin/env python3
"""Very small DT source (`dtc -O dts`) parser + hardware inventory printer.

Usage:  dtc -I dtb -O dts -o foo.dts foo.dtb
        python3 scripts/dt-inventory.py foo.dts [--buses] [--compat REGEX] [--path NODE]

Why not libfdt: the dts text from dtc is a faithful, already resolved view of the
tree (phandles, labels, overlays applied), and we only need structure + a few
properties, so a 60 line brace counter is enough and needs no extra deps.
"""
import re
import sys
import argparse

NODE_RE = re.compile(r'^\s*([A-Za-z0-9,._+@#-]+)\s*\{')
PROP_RE = re.compile(r'^\s*([A-Za-z0-9,._+@#-]+)\s*=\s*(.*);\s*$')
PROP_EMPTY_RE = re.compile(r'^\s*([A-Za-z0-9,._+@#-]+)\s*;\s*$')


class Node:
    __slots__ = ('name', 'props', 'children', 'parent')

    def __init__(self, name, parent=None):
        self.name = name
        self.props = {}
        self.children = []
        self.parent = parent

    def path(self):
        if self.parent is None:
            return '/'
        p = self.parent.path()
        return (p if p.endswith('/') else p + '/') + self.name

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def get(self, key, default=None):
        return self.props.get(key, default)


def parse(path):
    root = Node('/')
    cur = root
    with open(path, 'r', errors='replace') as fh:
        for line in fh:
            if line.startswith('/dts-v1/') or line.startswith('/memreserve') or line.startswith('/plugin/'):
                continue
            m = NODE_RE.match(line)
            if m and m.group(1) != 'root':
                n = Node(m.group(1), cur)
                cur.children.append(n)
                cur = n
                continue
            if line.strip().startswith('};'):
                if cur.parent is not None:
                    cur = cur.parent
                continue
            m = PROP_RE.match(line) or PROP_EMPTY_RE.match(line)
            if m:
                cur.props[m.group(1)] = (m.group(2) if m.lastindex and m.lastindex > 1 else '').strip()
    return root


def unquote(v):
    if v is None:
        return None
    v = v.strip()
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    return ' '.join(re.findall(r'"([^"]*)"', v)) or v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dts')
    ap.add_argument('--buses', action='store_true', help='dump every bus and its children')
    ap.add_argument('--compat', help='list nodes whose compatible matches this regex')
    ap.add_argument('--path', help='print properties of nodes whose path matches regex')
    ap.add_argument('--stats', action='store_true')
    a = ap.parse_args()

    root = parse(a.dts)
    nodes = list(root.walk())

    if a.stats:
        print('nodes: %d' % len(nodes))
        compat = [(n, unquote(n.get('compatible'))) for n in nodes if n.get('compatible')]
        print('nodes with compatible: %d' % len(compat))
        models = [unquote(n.get('model')) for n in nodes if n.get('model')]
        print('models:', models[:5])

    if a.compat:
        rx = re.compile(a.compat, re.I)
        for n, c in [(n, unquote(n.get('compatible'))) for n in nodes if n.get('compatible')]:
            if c and rx.search(c):
                print('%-70s %s' % (n.path(), c.replace('\x00', '|')[:120]))
                reg = n.get('reg')
                if reg:
                    print('      reg = %s' % reg)

    if a.path:
        rx = re.compile(a.path)
        for n in nodes:
            if rx.search(n.path()):
                print('=== %s' % n.path())
                for k, v in n.props.items():
                    print('    %s = %s' % (k, v[:160]))

    if a.buses:
        BUS = re.compile(r'(i2c|spi|geni|slim|soundwire|swr|i3c)')
        for n in nodes:
            if not BUS.search(n.name):
                continue
            if 'pinctrl' in n.path() or not n.children:
                continue
            if not any(c.get('compatible') for c in n.children):
                continue
            print('\n## %s   (%s)' % (n.path(), unquote(n.get('compatible')) or '?'))
            for c in n.children:
                print('   - %-38s %-60s %s' % (
                    c.name,
                    (unquote(c.get('compatible')) or '').replace('\x00', '|')[:58],
                    ('reg=' + c.get('reg', '')) if c.get('reg') else ''))


if __name__ == '__main__':
    main()