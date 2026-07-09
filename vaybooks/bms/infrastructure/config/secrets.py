"""Windows DPAPI / fallback secret encryption."""

from __future__ import annotations

import base64
import json
import sys
from ctypes import POINTER, Structure, byref, cast, c_char, c_ulong, create_string_buffer, string_at
from pathlib import Path
from typing import Any

DWORD = c_ulong


class _DATA_BLOB(Structure):
    _fields_ = [("cbData", DWORD), ("pbData", POINTER(c_char))]


def _dpapi_encrypt(data: bytes) -> bytes:
    from ctypes import windll

    buffer = create_string_buffer(data)
    blob_in = _DATA_BLOB(len(data), cast(buffer, POINTER(c_char)))
    blob_out = _DATA_BLOB()
    if not windll.crypt32.CryptProtectData(
        byref(blob_in), None, None, None, None, 0, byref(blob_out)
    ):
        raise RuntimeError("CryptProtectData failed")
    return string_at(blob_out.pbData, blob_out.cbData)


def _dpapi_decrypt(data: bytes) -> bytes:
    from ctypes import windll

    buffer = create_string_buffer(data)
    blob_in = _DATA_BLOB(len(data), cast(buffer, POINTER(c_char)))
    blob_out = _DATA_BLOB()
    if not windll.crypt32.CryptUnprotectData(
        byref(blob_in), None, None, None, None, 0, byref(blob_out)
    ):
        raise RuntimeError("CryptUnprotectData failed")
    return string_at(blob_out.pbData, blob_out.cbData)


def _dpapi_available() -> bool:
    return sys.platform == "win32"


def encrypt_secrets(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data).encode("utf-8")
    if _dpapi_available():
        try:
            path.write_bytes(_dpapi_encrypt(payload))
            return
        except Exception:
            pass
    path.write_text(base64.b64encode(payload).decode("ascii"))


def decrypt_secrets(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = path.read_bytes()
    if _dpapi_available():
        try:
            decrypted = _dpapi_decrypt(raw)
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            pass
    try:
        decoded = base64.b64decode(path.read_text().encode("ascii"))
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return {}


def encrypt_mongo_uri(uri: str, secrets_path: Path) -> str:
    secrets = decrypt_secrets(secrets_path)
    secrets["MONGO_URI"] = uri
    encrypt_secrets(secrets, secrets_path)
    return "dpapi://secrets.enc"


def resolve_mongo_uri(config_uri: str, secrets_path: Path | None) -> str:
    if config_uri.startswith("dpapi://") and secrets_path:
        secrets = decrypt_secrets(secrets_path)
        return secrets.get("MONGO_URI", "")
    return config_uri
