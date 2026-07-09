#!/usr/bin/env python3
"""Stage VayBooks-BMS application for desktop installer packaging."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time

import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BMS_DIR = REPO_ROOT
DEFAULT_OUTPUT = REPO_ROOT / "installer" / "dist" / "staging"

PYTHON_EMBED_URL = (
    "https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip"
)
PYTHON_VERSION = "3.11.9"
NSSM_URL = "https://nssm.cc/release/nssm-2.24.zip"
MONGODB_MSI_URL = (
    "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-7.0.14-signed.msi"
)

EXCLUDE_DIRS = {
    "tests",
    "__pycache__",
    ".pytest_cache",
    ".git",
    "venv",
    "installer",
    "dev-orchestrator-output",
    "qa-output",
    "tasks",
    ".github",
}


def _ignore_app_copy(_dir: str, names: list[str]) -> set[str]:
    return {name for name in names if name in EXCLUDE_DIRS}


def _configure_embeddable_pth(python_dir: Path) -> None:
    pth_files = list(python_dir.glob("python*._pth"))
    if not pth_files:
        return
    pth_file = pth_files[0]
    lines = [line.strip() for line in pth_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not any("site-packages" in line for line in lines):
        lines.append("Lib\\site-packages")
    if not any(line.startswith("import site") for line in lines):
        lines.append("import site")
    pth_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_app_version() -> str:
    init_py = BMS_DIR / "vaybooks" / "bms" / "__init__.py"
    text = init_py.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return match.group(1) if match else "1.0.0"


def download_file(url: str, dest: Path, retries: int = 3) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            print(f"Downloading {url} -> {dest} (attempt {attempt}/{retries})")
            urllib.request.urlretrieve(url, dest)
            return
        except Exception as exc:
            if attempt == retries:
                raise
            print(f"Download failed: {exc}; retrying in {attempt * 5}s")
            time.sleep(attempt * 5)


def setup_embedded_python(output: Path) -> Path:
    python_dir = output / "python"
    if python_dir.exists():
        shutil.rmtree(python_dir)
    python_dir.mkdir(parents=True)

    embed_zip = output / "downloads" / f"python-{PYTHON_VERSION}-embed-amd64.zip"
    download_file(PYTHON_EMBED_URL.format(version=PYTHON_VERSION), embed_zip)
    with zipfile.ZipFile(embed_zip) as zf:
        zf.extractall(python_dir)

    site_packages = python_dir / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    _configure_embeddable_pth(python_dir)

    pip_bootstrap = output / "downloads" / "get-pip.py"
    if not pip_bootstrap.exists():
        download_file("https://bootstrap.pypa.io/get-pip.py", pip_bootstrap)

    py_exe = str(python_dir / "python.exe")
    subprocess.check_call([py_exe, str(pip_bootstrap), "--no-warn-script-location"], cwd=python_dir)
    subprocess.check_call([py_exe, "-m", "pip", "--version"])

    requirements = [BMS_DIR / "requirements.txt", BMS_DIR / "requirements-desktop.txt"]
    for req in requirements:
        subprocess.check_call(
            [py_exe, "-m", "pip", "install", "-r", str(req), "--no-warn-script-location"]
        )
    return python_dir


def copy_app(output: Path) -> Path:
    app_dir = output / "app"
    if app_dir.exists():
        shutil.rmtree(app_dir)
    shutil.copytree(
        BMS_DIR,
        app_dir,
        ignore=_ignore_app_copy,
    )
    secrets = app_dir / ".streamlit" / "secrets.toml"
    if secrets.exists():
        secrets.unlink()
    secrets_example = app_dir / ".streamlit" / "secrets.toml.example"
    secrets = app_dir / ".streamlit" / "secrets.toml"
    if secrets_example.exists() and not secrets.exists():
        shutil.copy(secrets_example, secrets)
    return app_dir


def download_tools(output: Path) -> None:
    if sys.platform != "win32":
        return

    tools_dir = output / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    nssm_zip = output / "downloads" / "nssm.zip"
    download_file(NSSM_URL, nssm_zip)
    with zipfile.ZipFile(nssm_zip) as zf:
        for name in zf.namelist():
            if name.endswith("/win64/nssm.exe"):
                zf.extract(name, output / "downloads")
                src = output / "downloads" / name
                shutil.copy(src, tools_dir / "nssm.exe")
                break

    mongo_msi = output / "downloads" / "mongodb.msi"
    if not mongo_msi.exists():
        download_file(MONGODB_MSI_URL, mongo_msi)


def copy_service_scripts(output: Path) -> None:
    service_src = REPO_ROOT / "installer" / "windows" / "service"
    service_dst = output / "service"
    if service_src.exists():
        if service_dst.exists():
            shutil.rmtree(service_dst)
        shutil.copytree(service_src, service_dst)

    scripts_src = REPO_ROOT / "installer" / "windows" / "scripts"
    scripts_dst = output / "scripts"
    if scripts_src.exists():
        if scripts_dst.exists():
            shutil.rmtree(scripts_dst)
        shutil.copytree(scripts_src, scripts_dst)

    nssm_src = REPO_ROOT / "installer" / "windows" / "nssm"
    nssm_dst = output / "nssm"
    if nssm_src.exists():
        if nssm_dst.exists():
            shutil.rmtree(nssm_dst)
        shutil.copytree(nssm_src, nssm_dst)


def build_launcher(output: Path) -> None:
    launcher_src = REPO_ROOT / "installer" / "windows" / "scripts" / "launcher.py"
    tools_dir = output / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "PyInstaller",
                "--onefile",
                "--name",
                "VayBooks-Launcher",
                "--distpath",
                str(tools_dir),
                "--workpath",
                str(output / "build" / "launcher"),
                "--specpath",
                str(output / "build" / "launcher"),
                "--clean",
                str(launcher_src),
            ]
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("PyInstaller not available; copying launcher.py script fallback")
        shutil.copy(launcher_src, tools_dir / "launcher.py")


def write_build_info(output: Path, version: str) -> None:
    info = output / "BUILD_INFO.txt"
    info.write_text(
        f"version={version}\npython={PYTHON_VERSION}\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage VayBooks-BMS installer payload")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-python", action="store_true")
    parser.add_argument("--skip-downloads", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    version = _read_app_version()

    if not args.skip_python:
        if sys.platform != "win32":
            print("Embedded Python bundling is Windows-only; use --skip-python on other platforms.")
        else:
            setup_embedded_python(output)
    copy_app(output)
    copy_service_scripts(output)
    if not args.skip_downloads:
        download_tools(output)
    build_launcher(output)
    write_build_info(output, version)

    print(f"Staging complete: {output} (v{version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
