#!/usr/bin/env python3
"""Generate SHA256 checksum for release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument("--write-json", type=Path, default=None)
    args = parser.parse_args()

    checksum = sha256_file(args.file)
    print(checksum)

    if args.write_json:
        payload = {"file": args.file.name, "sha256": checksum}
        args.write_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
