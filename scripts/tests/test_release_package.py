#!/usr/bin/env python3
"""Regression tests for the fail-closed release archive packager."""

import hashlib
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


CANDIDATE_ROOT = Path(__file__).resolve().parents[2]
PACKAGER = CANDIDATE_ROOT / "scripts" / "release_package.py"


class ReleasePackageTests(unittest.TestCase):
    def test_only_explicit_regular_allowlisted_files_reach_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture"
            (root / "backend").mkdir(parents=True)
            (root / "frontend" / "dist" / "assets").mkdir(parents=True)
            (root / "README.md").write_text("public readme\n", encoding="utf-8")
            (root / ".env.example").write_text("PUBLIC_SETTING=example\n", encoding="utf-8")
            (root / "backend" / "api_server.py").write_text("print('public')\n", encoding="utf-8")
            (root / "frontend" / "dist" / "index.html").write_text("<main></main>\n", encoding="utf-8")
            (root / "frontend" / "dist" / "assets" / "app.js").write_text("console.log('public')\n", encoding="utf-8")

            # Poisoned unlisted inputs must not be recursively packaged.
            (root / ".env.production").write_text("not-a-real-secret\n", encoding="utf-8")
            (root / "backend" / "app.sqlite3").write_text("not-a-real-db\n", encoding="utf-8")
            (root / "backend" / "uploads").mkdir()
            (root / "backend" / "uploads" / "statement.csv").write_text("not-a-real-upload\n", encoding="utf-8")
            (root / "backend" / ".venv" / "bin").mkdir(parents=True)
            (root / "backend" / ".venv" / "bin" / "python").write_text("not-a-real-runtime\n", encoding="utf-8")

            allowlist = Path(temporary) / "allowlist.txt"
            digest = lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest()
            readme_hash = digest("public readme\n")
            env_hash = digest("PUBLIC_SETTING=example\n")
            api_hash = digest("print('public')\n")
            html_hash = digest("<main></main>\n")
            js_hash = digest("console.log('public')\n")
            start_hash = digest('#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")/backend"\npython api_server.py\n')
            allowlist.write_text(
                f"README.md\tREADME.md\t{readme_hash}\n"
                f".env.example\t.env.example\t{env_hash}\n"
                f"backend/api_server.py\tbackend/api_server.py\t{api_hash}\n"
                f"frontend/dist/index.html\tbackend/frontend_dist/index.html\t{html_hash}\n"
                f"frontend/dist/assets/app.js\tbackend/frontend_dist/assets/app.js\t{js_hash}\n"
                f"@generated:start.sh\tstart.sh\t{start_hash}\n",
                encoding="utf-8",
            )
            archive = Path(temporary) / "financial-assistant-test.tar.gz"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGER),
                    "--source",
                    str(root),
                    "--allowlist",
                    str(allowlist),
                    "--archive",
                    str(archive),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            with tarfile.open(archive, "r:gz") as package:
                names = sorted(member.name[2:] if member.name.startswith("./") else member.name for member in package.getmembers() if member.isfile())
            self.assertEqual(
                names,
                sorted(
                    [
                        "README.md",
                        ".env.example",
                        "backend/api_server.py",
                        "backend/frontend_dist/index.html",
                        "backend/frontend_dist/assets/app.js",
                        "start.sh",
                    ]
                ),
            )
            self.assertFalse(any(".env.production" in name or ".sqlite" in name or "uploads/" in name or ".venv/" in name for name in names))

    def test_rejects_an_allowlisted_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture"
            root.mkdir()
            (root / "public.txt").write_text("public\n", encoding="utf-8")
            (root / "linked.txt").symlink_to("public.txt")
            allowlist = Path(temporary) / "allowlist.txt"
            allowlist.write_text(
                "linked.txt\tlinked.txt\t" + hashlib.sha256(b"public\n").hexdigest() + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(PACKAGER), "--source", str(root), "--allowlist", str(allowlist), "--archive", str(Path(temporary) / "out.tar.gz")],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("symlink", completed.stderr.lower())

    def test_rejects_a_file_that_no_longer_matches_allowlisted_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture"
            root.mkdir()
            (root / "public.txt").write_text("changed after review\n", encoding="utf-8")
            allowlist = Path(temporary) / "allowlist.txt"
            allowlist.write_text(
                "public.txt\tpublic.txt\t" + "0" * 64 + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(PACKAGER), "--source", str(root), "--allowlist", str(allowlist), "--archive", str(Path(temporary) / "out.tar.gz")],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("hash", completed.stderr.lower())

    def test_rejects_dot_as_an_archive_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture"
            root.mkdir()
            payload = b"public\n"
            (root / "public.txt").write_bytes(payload)
            allowlist = Path(temporary) / "allowlist.txt"
            allowlist.write_text(
                "public.txt\t.\t" + hashlib.sha256(payload).hexdigest() + "\n",
                encoding="utf-8",
            )
            archive = Path(temporary) / "out.tar.gz"
            completed = subprocess.run(
                [sys.executable, str(PACKAGER), "--source", str(root), "--allowlist", str(allowlist), "--archive", str(archive)],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("unsafe archive path", completed.stderr.lower())
            self.assertFalse(archive.exists())

    def test_rejects_archive_target_ancestor_collisions_in_either_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture"
            root.mkdir()
            first_payload = b"first\n"
            second_payload = b"second\n"
            (root / "first.txt").write_bytes(first_payload)
            (root / "second.txt").write_bytes(second_payload)
            first_row = "first.txt\tfoo\t" + hashlib.sha256(first_payload).hexdigest()
            second_row = "second.txt\tfoo/bar\t" + hashlib.sha256(second_payload).hexdigest()
            for rows in ((first_row, second_row), (second_row, first_row)):
                with self.subTest(rows=rows):
                    allowlist = Path(temporary) / "allowlist.txt"
                    allowlist.write_text("\n".join(rows) + "\n", encoding="utf-8")
                    archive = Path(temporary) / "out.tar.gz"
                    completed = subprocess.run(
                        [sys.executable, str(PACKAGER), "--source", str(root), "--allowlist", str(allowlist), "--archive", str(archive)],
                        text=True,
                        capture_output=True,
                    )
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("ancestor collision", completed.stderr.lower())
                    self.assertFalse(archive.exists())


if __name__ == "__main__":
    unittest.main()
