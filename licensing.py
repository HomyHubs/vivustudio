from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import re
import uuid
from datetime import date, datetime
from pathlib import Path


# Keep license_admin.py private. This key must remain unchanged after licenses
# have been issued, otherwise previously issued activation codes stop working.
_ACTIVATION_KEY = bytes.fromhex(
    "d2cf4eb4180e17aa66e47db40327705cb83eef053203d50e37e49cd485bc2c9a"
)
_REQUEST_SALT = "VIVU-STUDIO-REQUEST-ID-v1"


def _windows_machine_guid() -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg

        access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            access,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value).strip()
    except OSError:
        return ""


def hardware_request_id() -> str:
    """Return a stable, non-reversible identifier; never expose raw hardware IDs."""
    machine_guid = _windows_machine_guid()
    # MachineGuid is deliberately preferred alone: computer names and network
    # adapters can change during normal use and must not invalidate a license.
    identity = machine_guid or f"{platform.node().strip()}|{uuid.getnode():012x}"
    parts = [_REQUEST_SALT, identity, platform.machine().strip()]
    normalized = "|".join(part.upper() for part in parts if part)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest().upper()
    return "-".join(digest[index : index + 4] for index in range(0, 20, 4))


def normalize_request_id(value: str) -> str:
    return re.sub(r"[^A-F0-9]", "", value.upper())


def normalize_activation_code(value: str) -> str:
    return re.sub(r"\D", "", value)


def _expiry_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def activation_code_for(request_id: str, expires_on: date | str) -> str:
    request = normalize_request_id(request_id)
    if len(request) != 20:
        raise ValueError("Request ID must contain 20 hexadecimal characters.")
    expiry = _expiry_date(expires_on)
    if not 2020 <= expiry.year <= 2099:
        raise ValueError("Expiry year must be between 2020 and 2099.")
    expiry_digits = expiry.strftime("%y%m%d")
    message = f"{request}|{expiry_digits}".encode("ascii")
    digest = hmac.new(_ACTIVATION_KEY, message, hashlib.sha256).digest()
    signature = int.from_bytes(digest[:8], "big") % (10**10)
    return f"{expiry_digits}{signature:010d}"


def format_activation_code(value: str) -> str:
    digits = normalize_activation_code(value)[:16]
    return "-".join(digits[index : index + 4] for index in range(0, len(digits), 4))


def activation_expiry(code: str) -> date | None:
    supplied = normalize_activation_code(code)
    if len(supplied) != 16:
        return None
    try:
        return date(
            2000 + int(supplied[0:2]),
            int(supplied[2:4]),
            int(supplied[4:6]),
        )
    except ValueError:
        return None


def is_valid_activation_code(
    request_id: str,
    code: str,
    on_date: date | None = None,
) -> bool:
    supplied = normalize_activation_code(code)
    expiry = activation_expiry(supplied)
    if expiry is None or expiry < (on_date or date.today()):
        return False
    try:
        expected = activation_code_for(request_id, expiry)
    except ValueError:
        return False
    return hmac.compare_digest(expected, supplied)


def license_path(data_dir: Path) -> Path:
    return data_dir / "activation.json"


def is_activated(data_dir: Path, request_id: str | None = None) -> bool:
    request_id = request_id or hardware_request_id()
    try:
        payload = json.loads(license_path(data_dir).read_text(encoding="utf-8"))
        return (
            normalize_request_id(str(payload.get("request_id", "")))
            == normalize_request_id(request_id)
            and is_valid_activation_code(request_id, str(payload.get("activation_code", "")))
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def saved_activation_expiry(data_dir: Path, request_id: str | None = None) -> date | None:
    request_id = request_id or hardware_request_id()
    try:
        payload = json.loads(license_path(data_dir).read_text(encoding="utf-8"))
        saved_request = str(payload.get("request_id", ""))
        code = str(payload.get("activation_code", ""))
        if normalize_request_id(saved_request) != normalize_request_id(request_id):
            return None
        if not is_valid_activation_code(request_id, code):
            return None
        return activation_expiry(code)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def save_activation(data_dir: Path, request_id: str, code: str) -> None:
    if not is_valid_activation_code(request_id, code):
        raise ValueError("Invalid activation code.")
    data_dir.mkdir(parents=True, exist_ok=True)
    destination = license_path(data_dir)
    temporary = destination.with_suffix(".tmp")
    payload = {
        "version": 2,
        "request_id": request_id,
        "activation_code": normalize_activation_code(code),
        "expires_on": activation_expiry(code).isoformat(),
    }
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, destination)
