#!/usr/bin/env python3
"""Small fail-closed Git payload guard; not a full secret/privacy audit.

Checks the exact staged blobs by default; --tree HEAD checks a committed tree.
Never prints matched values. Run alongside manual review and a mature scanner.
"""
import argparse
import re
import subprocess
import sys
from pathlib import PurePosixPath

PATTERNS = {
    'github-token': re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})'),
    'provider-key': re.compile(rb'\bsk-[A-Za-z0-9_-]{20,}'),
    'aws-access-key': re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'private-key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
}

def git(*args):
    return subprocess.check_output(['git', *args])

def forbidden_path(path):
    p = PurePosixPath(path)
    return (
        (p.name == '.env' or (p.name.startswith('.env.') and p.name != '.env.example'))
        or p.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.pem', '.key'}
        or any(part in {'node_modules', '.venv', '.venv-runtime', '__pycache__'} for part in p.parts)
    )

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', help='Check all blobs of this commit/tree instead of index')
    args = parser.parse_args()
    if args.tree:
        raw = git('ls-tree', '-rz', args.tree)
        entries = []
        for row in raw.split(b'\0'):
            if not row:
                continue
            meta, path = row.split(b'\t', 1)
            mode, kind, oid = meta.split()
            entries.append((mode, oid, path.decode('utf-8')))
    else:
        entries = []
        for row in git('ls-files', '--stage', '-z').split(b'\0'):
            if not row:
                continue
            meta, path = row.split(b'\t', 1)
            mode, oid, stage = meta.split()
            if stage != b'0':
                raise RuntimeError('Unmerged index cannot pass release guard')
            entries.append((mode, oid, path.decode('utf-8')))
    if not entries:
        raise RuntimeError('Empty payload: nothing has been checked')
    findings = []
    total = 0
    for mode, oid, path in entries:
        if mode not in {b'100644', b'100755'}:
            findings.append((path, 0, 'unsupported-file-mode'))
            continue
        if forbidden_path(path):
            findings.append((path, 0, 'private-or-generated-path'))
        data = git('cat-file', 'blob', oid.decode('ascii'))
        total += len(data)
        for line_number, line in enumerate(data.splitlines(), 1):
            for rule, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((path, line_number, rule))
    print(f'Checked {len(entries)} Git entries, {total} bytes; findings={len(findings)}')
    for path, line, rule in findings:
        print(f'{path}:{line}: {rule}')
    return bool(findings)

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Release guard could not complete: {type(error).__name__}', file=sys.stderr)
        raise SystemExit(2)
