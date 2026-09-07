#!/usr/bin/env python3
"""Create a release archive from an exact, relative file allowlist.

Allowlist rows are ``source<TAB>archive-path<TAB>sha256``. Only regular source
files named by those rows are read; the one supported generated row is
``@generated:start.sh``.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import shutil
import stat
import sys
import tarfile
from pathlib import Path, PurePosixPath


START_SCRIPT = b'#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")/backend"\npython -m uvicorn api_server:app --host 127.0.0.1 --port 8000\n'


def fail(message: str) -> None:
    raise ValueError(message)


def safe_relative(value: str, label: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or str(path) == "." or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        fail(f"unsafe {label}: {value!r}")
    return path


def read_allowlist(path: Path) -> list[tuple[str, PurePosixPath, str]]:
    entries: list[tuple[str, PurePosixPath, str]] = []
    targets: set[PurePosixPath] = set()
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        fail(f"cannot read allowlist: {type(error).__name__}")
    for number, row in enumerate(rows, 1):
        if not row or row.startswith("#"):
            continue
        try:
            source, target, expected_sha256 = row.split("\t")
        except ValueError:
            fail(f"invalid allowlist row {number}")
        if source != "@generated:start.sh":
            safe_relative(source, "source path")
        archive_path = safe_relative(target, "archive path")
        if archive_path in targets:
            fail(f"duplicate archive path: {archive_path}")
        if any(existing in archive_path.parents or archive_path in existing.parents for existing in targets):
            fail(f"archive path ancestor collision: {archive_path}")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            fail(f"invalid allowlist hash on row {number}")
        targets.add(archive_path)
        entries.append((source, archive_path, expected_sha256))
    if not entries:
        fail("empty allowlist")
    return entries


def checked_source_file(root: Path, relative: str):
    current = root
    for component in PurePosixPath(relative).parts:
        current = current / component
        try:
            details = os.lstat(current)
        except OSError as error:
            fail(f"missing allowlisted source {relative!r}: {type(error).__name__}")
        if stat.S_ISLNK(details.st_mode):
            fail(f"symlink is not permitted in allowlisted source: {relative!r}")
        if component != PurePosixPath(relative).parts[-1] and not stat.S_ISDIR(details.st_mode):
            fail(f"non-directory ancestor in allowlisted source: {relative!r}")
    if not stat.S_ISREG(details.st_mode):
        fail(f"unsupported allowlisted source entry: {relative!r}")
    try:
        descriptor = os.open(current, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        fail(f"cannot securely open allowlisted source {relative!r}: {type(error).__name__}")
    opened = os.fstat(descriptor)
    if not stat.S_ISREG(opened.st_mode):
        os.close(descriptor)
        fail(f"unsupported allowlisted source entry: {relative!r}")
    return os.fdopen(descriptor, "rb"), stat.S_IMODE(opened.st_mode)


def add_bytes(archive: tarfile.TarFile, target: PurePosixPath, data: bytes, mode: int) -> None:
    entry = tarfile.TarInfo(str(target))
    entry.size = len(data)
    entry.mode = mode
    entry.mtime = 0
    archive.addfile(entry, io.BytesIO(data))


def package(source_root: Path, allowlist: Path, archive_path: Path, stage: Path | None = None) -> None:
    root_info = os.lstat(source_root)
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        fail("source root must be a real directory, not a symlink")
    entries = read_allowlist(allowlist)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if stage is not None:
        if stage.exists() or stage.is_symlink():
            fail("stage directory must not already exist")
        stage.mkdir(parents=True)
    try:
        with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            for source, target, expected_sha256 in entries:
                if source == "@generated:start.sh":
                    data = START_SCRIPT
                    mode = 0o755
                else:
                    input_file, mode = checked_source_file(source_root, source)
                    with input_file:
                        data = input_file.read()
                if hashlib.sha256(data).hexdigest() != expected_sha256:
                    fail(f"allowlisted source hash mismatch: {source!r}")
                add_bytes(archive, target, data, mode)
                if stage is not None:
                    destination = stage / target
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with destination.open("wb") as output_file:
                        output_file.write(data)
                    os.chmod(destination, mode)
    except Exception:
        archive_path.unlink(missing_ok=True)
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--allowlist", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--stage", type=Path)
    args = parser.parse_args()
    try:
        package(args.source, args.allowlist, args.archive, args.stage)
    except (OSError, ValueError, tarfile.TarError) as error:
        print(f"release packaging refused: {error}", file=sys.stderr)
        return 2
    print(f"created archive with {len(read_allowlist(args.allowlist))} allowlisted entries: {args.archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
