#!/usr/bin/env python3
"""Sync version from git tag or CLI arg into app and Inno Setup defines."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INIT_PY = REPO_ROOT / "vaybooks" / "bms" / "__init__.py"
INNO_ISS = REPO_ROOT / "installer" / "windows" / "inno" / "VayBooks-BMS.iss"


def _git_tag_version() -> str | None:
    try:
        tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
        return tag.lstrip("v")
    except Exception:
        return None


def update_init_py(version: str) -> None:
    text = INIT_PY.read_text(encoding="utf-8")
    new_text = re.sub(
        r'__version__\s*=\s*["\'][^"\']+["\']',
        f'__version__ = "{version}"',
        text,
    )
    INIT_PY.write_text(new_text, encoding="utf-8")


def update_inno(version: str) -> None:
    if not INNO_ISS.exists():
        return
    text = INNO_ISS.read_text(encoding="utf-8")
    if "#define MyAppVersion" in text:
        new_text = re.sub(
            r'#define MyAppVersion\s+"[^"]*"',
            f'#define MyAppVersion "{version}"',
            text,
        )
    else:
        new_text = f'#define MyAppVersion "{version}"\n' + text
    INNO_ISS.write_text(new_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=None)
    args = parser.parse_args()
    version = args.version or _git_tag_version() or "1.0.0"
    update_init_py(version)
    update_inno(version)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
