#!/usr/bin/env python3
"""Explicit local PostgreSQL schema initializer for the financial assistant."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import schema


def main() -> int:
    try:
        schema.initialize_database(os.getenv("DATABASE_URL"))
    except schema.SchemaInitializationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("Financial Assistant public schema is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
