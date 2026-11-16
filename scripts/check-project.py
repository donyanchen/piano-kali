#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only source and publication checks. Never print matched secret values."""
import ast
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse
import xml.etree.ElementTree as ET

PROJECT = pathlib.Path(__file__).resolve().parents[1]
RULES = {
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY'),
    'GitHub credential': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})'),
    'AWS access key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'JWT credential': re.compile(r'\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}'),
}
FORBIDDEN_SUFFIXES = {'.pem', '.key', '.img', '.deb', '.rpm', '.plasmoid', '.zip', '.sqlite', '.db', '.burp'}


def main():
    process = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                             cwd=PROJECT, stdout=subprocess.PIPE, check=True)
    names = sorted(set(n for n in process.stdout.decode('utf-8').split('\0') if n))
    problems = []
    counts = {'python': 0, 'json': 0, 'xml': 0, 'markdown': 0}
    for name in names:
        path = PROJECT / name
        # Tracked files remain visible here even if somebody adds an ignore rule.
        parts = pathlib.PurePosixPath(name).parts
        if parts[0] in ('.work', 'out') or path.suffix in FORBIDDEN_SUFFIXES or path.name.startswith('.env'):
            problems.append(name + ': forbidden publication path')
        if not path.is_file():
            problems.append(name + ': missing file')
            continue
        if path.stat().st_size > 5 * 1024 * 1024:
            problems.append(name + ': unexpected large file')
        if path.suffix.lower() in ('.jpg', '.jpeg', '.png') or name == 'parted':
            continue  # Existing upstream historical files, documented in THIRD_PARTY.md.
        try:
            data = path.read_text(encoding='utf-8')
            for number, line in enumerate(data.splitlines(), 1):
                for rule, expression in RULES.items():
                    if expression.search(line):
                        problems.append(f'{name}:{number}: {rule}')
            if path.suffix == '.py':
                ast.parse(data, filename=name)
                counts['python'] += 1
            elif path.suffix == '.json':
                json.loads(data)
                counts['json'] += 1
            elif path.suffix in ('.xml', '.svg') or (path.suffix == '.conf' and '<fontconfig' in data):
                ET.fromstring(data)
                counts['xml'] += 1
            elif path.suffix == '.md':
                counts['markdown'] += 1
                # Inline links only; strip fenced examples before checking paths.
                prose = re.sub(r'```.*?```', '', data, flags=re.S)
                for link in re.findall(r'\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)', prose):
                    link = link.strip('<>')
                    if urllib.parse.urlsplit(link).scheme or link.startswith(('#', '//')):
                        continue
                    relative = urllib.parse.unquote(link.split('#', 1)[0])
                    if relative and not (path.parent / relative).exists():
                        problems.append(name + ': broken local link: ' + relative)
        except (UnicodeError, SyntaxError, ValueError, ET.ParseError) as error:
            problems.append(name + ': parse error (' + type(error).__name__ + ')')
    for problem in problems:
        print(problem)
    print(json.dumps({'files': len(names), 'checked': counts, 'problems': len(problems)}))
    return bool(problems)


if __name__ == '__main__':
    sys.exit(main())
