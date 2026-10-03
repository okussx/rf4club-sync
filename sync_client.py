
import json
import os
from pathlib import Path

import requests

import config


def _token_path():
    target = Path(config.DEVICE_TOKEN_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    legacy = Path.cwd() / ".rf4club-device.json"
    if not target.exists() and legacy.exists():
        try:
            target.write_bytes(legacy.read_bytes())
        except OSError:
            pass
    return target


def load_device_credentials():
    path = _token_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        token = str(data.get("token") or "").strip()
        if not token:
            return None
        return {
            "token": token,
            "apiBaseUrl": str(data.get("apiBaseUrl") or "").strip().rstrip("/"),
            "device": data.get("device"),
        }
    except (OSError, ValueError, TypeError):
        return None


def load_device_token():
    credentials = load_device_credentials()
    return credentials["token"] if credentials else None


def configured_api_base_url(override=None):
    if override:
        return override.rstrip("/")
    credentials = load_device_credentials()
    if credentials and credentials.get("apiBaseUrl"):
        saved_url = credentials["apiBaseUrl"]
        if "localhost" not in saved_url and "127.0.0.1" not in saved_url:
            return saved_url
    return config.API_BASE_URL


def pair_device(code, api_base_url=None, device_name=None):
    base_url = configured_api_base_url(api_base_url)
    response = requests.post(
        f"{base_url}/api/sync/pair",
        json={"code": code, "deviceName": device_name or config.DEVICE_NAME},
        timeout=config.HTTP_TIMEOUT_SECONDS,
    )
    if not response.ok:
        try:
            message = str(response.json().get("error") or "").strip()
        except (ValueError, TypeError, AttributeError):
            message = ""
        raise RuntimeError(
            message or f"Eşleştirme başarısız oldu (HTTP {response.status_code})."
        )
    payload = response.json()
    token = str(payload.get("token") or "").strip()
    if not token:
        raise RuntimeError("Sunucu cihaz anahtarı döndürmedi.")
    _token_path().write_text(
        json.dumps(
            {"token": token, "apiBaseUrl": base_url, "device": payload.get("device")},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return payload


def send_catch(metadata, screenshot_path=None, token=None, api_base_url=None):
    device_token = token or load_device_token()
    if not device_token:
        raise RuntimeError("Cihaz eşleştirilmemiş.")
    base_url = configured_api_base_url(api_base_url)
    files = None
    screenshot_handle = None
    try:
        if screenshot_path:
            screenshot_handle = open(screenshot_path, "rb")
            files = {
                "screenshot": (
                    os.path.basename(screenshot_path), screenshot_handle, "image/png",
                )
            }
        response = requests.post(
            f"{base_url}/api/sync/catches",
            headers={"Authorization": f"Bearer {device_token}"},
            data={"metadata": json.dumps(metadata, ensure_ascii=False)},
            files=files,
            timeout=config.HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    finally:
        if screenshot_handle is not None:
            screenshot_handle.close()


def send_statistics(payload, token=None, api_base_url=None):
    device_token = token or load_device_token()
    if not device_token:
        raise RuntimeError("Cihaz eşleştirilmemiş.")
    base_url = configured_api_base_url(api_base_url)
    response = requests.post(
        f"{base_url}/api/sync/statistics",
        headers={"Authorization": f"Bearer {device_token}"},
        json=payload,
        timeout=config.HTTP_TIMEOUT_SECONDS,
    )
    if not response.ok:
        try:
            message = str(response.json().get("error") or "").strip()
        except (ValueError, TypeError, AttributeError):
            message = ""
        raise RuntimeError(
            message or f"İstatistik senkronizasyonu başarısız (HTTP {response.status_code})."
        )
    return response.json()


def queue_pending(metadata, screenshot_path=None):
    return _queue_pending("catch", metadata, screenshot_path)


def queue_pending_statistics(payload):
    return _queue_pending("statistics", payload)


def _queue_pending(kind, payload, screenshot_path=None):
    directory = Path(config.PENDING_SYNC_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    identifier = payload.get("eventId") or payload.get("snapshotId") or "pending"
    path = directory / f"{kind}-{identifier}.json"
    path.write_text(
        json.dumps(
            {"kind": kind, "payload": payload, "screenshotPath": screenshot_path},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def flush_pending(limit=None):
    directory = Path(config.PENDING_SYNC_DIR)
    if not directory.exists() or not load_device_token():
        return {"sent": 0, "failed": 0}
    sent = 0
    failed = 0
    max_items = limit or config.MAX_PENDING_RETRIES_PER_CYCLE
    for path in sorted(directory.glob("*.json"))[:max_items]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            kind = payload.get("kind") or "catch"
            body = payload.get("payload") or payload.get("metadata")
            if kind == "statistics":
                send_statistics(body)
            else:
                send_catch(body, payload.get("screenshotPath"))
            path.unlink()
            sent += 1
        except Exception as exc:
            failed += 1
            print(f"Bekleyen senkronizasyon gönderilemedi ({path.name}): {exc}")
    return {"sent": sent, "failed": failed}
