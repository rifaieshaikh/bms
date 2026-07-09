#!/usr/bin/env python3
"""Build version.json for GitHub Releases."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vaybooks.bms.version import __version__  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-url", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--release-notes", default="")
    parser.add_argument("--output", type=Path, default=Path("version.json"))
    parser.add_argument("--mandatory", action="store_true")
    args = parser.parse_args()

    payload = {
        "latest_version": __version__,
        "download_url": args.download_url,
        "sha256": args.sha256,
        "release_notes": args.release_notes,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "mandatory": args.mandatory,
    }
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
