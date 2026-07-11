"""Streamlit server + database fixtures for Playwright E2E tests."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

BMS_ROOT = Path(__file__).resolve().parents[1]
E2E_PORT = os.environ.get("E2E_PORT", "8502")
DEFAULT_BASE_URL = f"http://localhost:{E2E_PORT}"


def pytest_addoption(parser):
    parser.addoption(
        "--e2e-base-url",
        default=DEFAULT_BASE_URL,
        help="Base URL for Streamlit E2E tests",
    )
    parser.addoption(
        "--e2e-slowmo",
        type=int,
        default=0,
        help="Slow motion delay in ms between Playwright actions (use with --headed)",
    )


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args, pytestconfig):
    """Slow down actions when watching tests with --headed."""
    slowmo = pytestconfig.getoption("--e2e-slowmo")
    if not slowmo and pytestconfig.getoption("--headed"):
        slowmo = 400
    args = {**browser_type_launch_args}
    if slowmo:
        args["slow_mo"] = slowmo
    return args


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 900},
    }


@pytest.fixture(scope="session")
def e2e_base_url(pytestconfig):
    return pytestconfig.getoption("--e2e-base-url")


def _read_secrets_toml() -> dict[str, str]:
    secrets_path = BMS_ROOT / ".streamlit" / "secrets.toml"
    if not secrets_path.exists():
        return {}
    try:
        import tomllib

        return {k: str(v) for k, v in tomllib.loads(secrets_path.read_text(encoding="utf-8")).items()}
    except Exception:
        return {}


def _apply_e2e_mongo_env() -> None:
    """Use Mongo settings from .streamlit/secrets.toml (same as the running app)."""
    secrets = _read_secrets_toml()
    if secrets.get("MONGODB_URI"):
        os.environ["MONGODB_URI"] = secrets["MONGODB_URI"]
    if secrets.get("MONGODB_DATABASE"):
        os.environ["MONGODB_DATABASE"] = secrets["MONGODB_DATABASE"]


def _streamlit_env() -> dict[str, str]:
    _apply_e2e_mongo_env()
    return {**os.environ}


def _write_streamlit_secrets() -> None:
    if os.environ.get("E2E_PRESERVE_SECRETS", "").lower() in ("1", "true", "yes"):
        secrets_path = BMS_ROOT / ".streamlit" / "secrets.toml"
        if not secrets_path.exists():
            pytest.skip("E2E_PRESERVE_SECRETS set but .streamlit/secrets.toml is missing")
        return

    secrets_dir = BMS_ROOT / ".streamlit"
    secrets_dir.mkdir(exist_ok=True)
    uri = os.environ.get("MONGODB_URI", "") or _read_secrets_toml().get("MONGODB_URI", "")
    if not uri:
        pytest.skip("MONGODB_URI is required for E2E tests")
    db = _read_secrets_toml().get("MONGODB_DATABASE") or os.environ.get(
        "MONGODB_DATABASE", "zahcci_customization"
    )
    secrets_dir.joinpath("secrets.toml").write_text(
        f'MONGODB_URI = "{uri}"\nMONGODB_DATABASE = "{db}"\n',
        encoding="utf-8",
    )


def _health_ok(base_url: str) -> bool:
    try:
        return requests.get(f"{base_url}/_stcore/health", timeout=2).ok
    except Exception:
        return False


@pytest.fixture(scope="session")
def streamlit_server(e2e_base_url):
    """Start Streamlit when no server is already running."""
    _write_streamlit_secrets()
    env = _streamlit_env()

    if _health_ok(e2e_base_url):
        yield e2e_base_url
        return

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.port",
            E2E_PORT,
            "--server.headless",
            "true",
            "--server.fileWatcherType",
            "poll",
        ],
        cwd=str(BMS_ROOT),
        env=env,
    )
    try:
        for _ in range(90):
            if _health_ok(e2e_base_url):
                break
            time.sleep(1)
        else:
            proc.kill()
            pytest.fail(f"Streamlit did not start at {e2e_base_url}")
        yield e2e_base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session", autouse=True)
def _e2e_run_banner(streamlit_server):
    print(f"\n{'=' * 60}")
    print(f"E2E app: {streamlit_server}")
    print(f"Categories: {streamlit_server}/inventory-categories")
    print("Watch in browser: add --headed --e2e-slowmo 500")
    print(f"{'=' * 60}\n")
    yield


@pytest.fixture(scope="session", autouse=True)
def seed_e2e_database(streamlit_server):
    """Ensure indexes and seed baseline E2E records (skipped when E2E_SKIP_SEED=1)."""
    if os.environ.get("E2E_SKIP_SEED", "").lower() in ("1", "true", "yes"):
        yield
        return
    from e2e.helpers.seed import seed_database

    seed_database()
    yield
