
import argparse
import ctypes
import datetime
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import uuid
import warnings
from ctypes import wintypes

try:
    import winsound
except ImportError:
    winsound = None

import cv2
import mss
import numpy as np
import psutil

import config
import log_utils
import sync_client
import statistics_parser
from version import APP_VERSION

screen_utils = None


def load_statistics_state():
    try:
        with open(config.STATISTICS_STATE_FILE, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
        return {
            "snapshotId": str(state.get("snapshotId") or "") or None,
            "syncedAtEpoch": float(state.get("syncedAtEpoch") or 0),
        }
    except (OSError, ValueError, TypeError):
        return {"snapshotId": None, "syncedAtEpoch": 0.0}


def save_statistics_state(snapshot_id):
    path = os.path.abspath(config.STATISTICS_STATE_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as state_file:
        json.dump(
            {"snapshotId": snapshot_id, "syncedAtEpoch": time.time()},
            state_file,
            ensure_ascii=False,
            indent=2,
        )
    os.replace(temporary, path)


def enable_dpi_awareness():
    try:
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


enable_dpi_awareness()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def initialize_ocr():
    global screen_utils
    if screen_utils is None:
        warnings.filterwarnings(
            "ignore",
            message=r"torch\.quantize_per_tensor.*deprecated.*",
            category=UserWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message=r".*pin_memory.*no accelerator.*",
            category=UserWarning,
        )
        import screen_utils as screen_utils_module

        screen_utils = screen_utils_module


def normalize_text(value):
    text = str(value or "").replace("İ", "I").replace("ı", "i").casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"[^a-z0-9ğüşöç]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_process_running(process_name):
    wanted = process_name.casefold()
    for process in psutil.process_iter(["name"]):
        try:
            if str(process.info.get("name") or "").casefold() == wanted:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def foreground_game_context():
    user32 = ctypes.windll.user32
    window = user32.GetForegroundWindow()
    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
    rectangle = wintypes.RECT()
    if not window or not user32.GetWindowRect(window, ctypes.byref(rectangle)):
        return {"gameForeground": False, "fullscreen": False}

    try:
        process_name = psutil.Process(process_id.value).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        process_name = ""

    class MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    monitor = user32.MonitorFromWindow(window, 2)
    monitor_info = MonitorInfo()
    monitor_info.cbSize = ctypes.sizeof(MonitorInfo)
    has_monitor = monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info))
    monitor_bounds = monitor_info.rcMonitor if has_monitor else wintypes.RECT(
        0,
        0,
        user32.GetSystemMetrics(0),
        user32.GetSystemMetrics(1),
    )
    bounds = {
        "left": int(rectangle.left),
        "top": int(rectangle.top),
        "right": int(rectangle.right),
        "bottom": int(rectangle.bottom),
    }
    tolerance = 24
    fullscreen = (
        bounds["left"] <= monitor_bounds.left + tolerance
        and bounds["top"] <= monitor_bounds.top + tolerance
        and bounds["right"] >= monitor_bounds.right - tolerance
        and bounds["bottom"] >= monitor_bounds.bottom - tolerance
    )
    game_foreground = process_name.casefold() == config.GAME_PROCESS_NAME.casefold()
    return {
        "gameForeground": game_foreground,
        "fullscreen": fullscreen,
        "foregroundProcess": process_name,
        "windowBounds": bounds,
        "monitorBounds": {
            "left": int(monitor_bounds.left),
            "top": int(monitor_bounds.top),
            "right": int(monitor_bounds.right),
            "bottom": int(monitor_bounds.bottom),
        },
        "screenWidth": int(monitor_bounds.right - monitor_bounds.left),
        "screenHeight": int(monitor_bounds.bottom - monitor_bounds.top),
    }


def primary_screen_size():
    with mss.MSS() as capture:
        monitor = capture.monitors[1]
        return int(monitor["width"]), int(monitor["height"])


def scale_region(region, screen_size):
    reference_width, reference_height = config.REFERENCE_RESOLUTION
    screen_width, screen_height = screen_size
    scale_x = screen_width / reference_width
    scale_y = screen_height / reference_height
    left, top, width, height = region
    return (
        round(left * scale_x),
        round(top * scale_y),
        max(1, round(width * scale_x)),
        max(1, round(height * scale_y)),
    )


def crop_region(image, region):
    left, top, width, height = region
    return image[top : top + height, left : left + width]


def upscale(image):
    if image is None or config.OCR_SCALE <= 1:
        return image
    height, width = image.shape[:2]
    return cv2.resize(
        image,
        (width * config.OCR_SCALE, height * config.OCR_SCALE),
        interpolation=cv2.INTER_CUBIC,
    )


def capture_full_screen(client_context=None):
    with mss.MSS() as capture:
        bounds = (client_context or {}).get("monitorBounds")
        monitor = (
            {
                "left": bounds["left"],
                "top": bounds["top"],
                "width": bounds["right"] - bounds["left"],
                "height": bounds["bottom"] - bounds["top"],
            }
            if bounds
            else capture.monitors[1]
        )
        pixels = np.asarray(capture.grab(monitor), dtype=np.uint8)
    return cv2.cvtColor(pixels, cv2.COLOR_BGRA2BGR)


def ocr_region(image, region, name, allowlist=None):
    if screen_utils is None:
        raise RuntimeError("OCR motoru başlatılmadı.")
    cropped = crop_region(image, region)
    if cropped.size == 0:
        return []
    _, raw = screen_utils.perform_ocr(upscale(cropped), allowlist=allowlist)
    serializable = [
        {
            "box": [[float(point[0]), float(point[1])] for point in box],
            "text": text,
            "confidence": float(confidence),
        }
        for box, text, confidence in raw
    ]
    log_utils.append_to_raw_ocr_log(name, serializable)
    return serializable


def contains_any(text, words):
    normalized = normalize_text(text)
    return any(word in normalized for word in words)


def keep_is_visible(results):
    return any(
        item["confidence"] >= config.KEEP_MIN_CONFIDENCE
        and contains_any(item["text"], config.KEEP_TRIGGER_WORDS)
        for item in results
    )


def detect_trophy_type(results):
    normalized = normalize_text(" ".join(str(item["text"]) for item in results))
    if any(word in normalized for word in config.SUPER_TROPHY_WORDS):
        return "SUPER_TROPHY"
    if any(word in normalized for word in config.TROPHY_WORDS):
        return "TROPHY"
    return "NORMAL"


def detect_valuable(results):
    return any(
        item["confidence"] >= config.VALUABLE_MIN_CONFIDENCE
        and contains_any(item["text"], config.VALUABLE_WORDS)
        for item in results
    )


def result_top(item):
    return min((point[1] for point in item.get("box") or []), default=0)


def extract_fish_name(results):
    candidates = []
    for item in results:
        text = re.sub(r"\s+", " ", str(item["text"])).strip()
        if not text or item["confidence"] < config.FISH_NAME_MIN_CONFIDENCE:
            continue
        if contains_any(text, config.TROPHY_WORDS):
            continue
        if contains_any(text, config.KEEP_TRIGGER_WORDS):
            continue
        candidates.append(item | {"cleanText": text})
    if not candidates:
        return "", 0.0
    candidates.sort(key=lambda item: (result_top(item), -item["confidence"]))
    selected = candidates[0]
    return selected["cleanText"], float(selected["confidence"])


def save_trophy_screenshot(image, event_id):
    os.makedirs(config.TROPHY_SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(config.TROPHY_SCREENSHOT_DIR, f"{event_id}.png")
    if not cv2.imwrite(path, image):
        raise RuntimeError("Trophy ekran görüntüsü kaydedilemedi.")
    return path


def play_sync_sound():
    if not config.SYNC_SOUND_ENABLED or winsound is None:
        return
    try:
        winsound.PlaySound(
            "SystemAsterisk",
            winsound.SND_ALIAS | winsound.SND_ASYNC,
        )
    except RuntimeError:
        pass


def handle_sync_events(result):
    for event in result.get("events") or []:
        if event.get("type") != "CARD_DROP":
            continue
        payload = event.get("payload") or {}
        fish_name = payload.get("fishName") or "Bilinmeyen balık"
        rarity = str(payload.get("rarity") or "COMMON").replace("_", " ")
        message = payload.get("message") or "Collection'a eklendi"
        artwork_url = payload.get("artworkUrl") or ""
        print("\n" + "=" * 56)
        print(f"KART DÜŞTÜ: {fish_name} | {rarity}")
        print(message)
        if artwork_url:
            print(f"Kart görseli: {artwork_url}")
        print("=" * 56 + "\n")
        if config.SYNC_SOUND_ENABLED and winsound is not None:
            try:
                winsound.PlaySound(
                    "SystemExclamation",
                    winsound.SND_ALIAS | winsound.SND_ASYNC,
                )
            except RuntimeError:
                pass


def build_event_id(image, fish_name, trophy_type, caught_at):
    digest = hashlib.sha256()
    digest.update(fish_name.encode("utf-8", errors="ignore"))
    digest.update(trophy_type.encode("ascii"))
    digest.update(caught_at.encode("ascii"))
    digest.update(image[::32, ::32].tobytes())
    digest.update(uuid.uuid4().bytes)
    return digest.hexdigest()[:32]


def capture_integrity(image):
    proof = hashlib.sha256(image.tobytes()).hexdigest()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    differences = resized[:, 1:] > resized[:, :-1]
    fingerprint = f"{sum(int(bit) << index for index, bit in enumerate(differences.flatten())):016x}"
    return proof, fingerprint


def record_catch(full_screen, fish_results, client_context, trophy_results=None):
    fish_name, confidence = extract_fish_name(fish_results)
    classification_results = list(fish_results) + list(trophy_results or [])
    trophy_type = detect_trophy_type(classification_results)
    is_valuable = detect_valuable(classification_results)
    if not fish_name:
        print("Balık adı güvenilir biçimde okunamadı; kayıt gönderilmedi.")
        return
    caught_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    event_id = build_event_id(full_screen, fish_name, trophy_type, caught_at)
    proof_hash, fingerprint = capture_integrity(full_screen)
    screenshot_path = None
    if trophy_type != "NORMAL":
        screenshot_path = save_trophy_screenshot(full_screen, event_id)
    metadata = {
        "eventId": event_id,
        "fishName": fish_name,
        "trophyType": trophy_type,
        "isValuable": is_valuable,
        "caughtAt": caught_at,
        "ocrConfidence": confidence,
        "rawOcr": classification_results,
        "captureProofHash": proof_hash,
        "captureFingerprint": fingerprint,
        "clientContext": client_context,
    }
    sync_status = "PENDING"
    try:
        result = sync_client.send_catch(metadata, screenshot_path)
        sync_status = "DUPLICATE" if result.get("duplicate") else "SYNCED"
        if not result.get("duplicate"):
            play_sync_sound()
            handle_sync_events(result)
        print(f"Yakalama senkronize edildi: {fish_name} | {trophy_type} | {sync_status}")
    except Exception as exc:
        sync_client.queue_pending(metadata, screenshot_path)
        print(f"Yakalama yerel kuyruğa alındı: {exc}")
    log_utils.append_to_catch_log(
        {
            "Timestamp": caught_at,
            "EventId": event_id,
            "FishName": fish_name,
            "TrophyType": trophy_type,
            "OCRConfidence": f"{confidence:.4f}",
            "ScreenshotPath": screenshot_path or "",
            "SyncStatus": sync_status,
        }
    )


def record_statistics(full_screen, screen_size, previous_snapshot=None):
    records_region = scale_region(config.STATISTICS_RECORDS_REGION, screen_size)
    print("İstatistik ekranı okunuyor; bu işlem kısa bir süre alabilir...")
    summary_card_results = {}
    for key, reference_region in statistics_parser.SUMMARY_CARDS.items():
        summary_card_results[key] = ocr_region(
            full_screen,
            scale_region(reference_region, screen_size),
            f"StatisticsSummary.{key}",
            allowlist="0123456789.,kg ",
        )
    record_results = ocr_region(full_screen, records_region, "StatisticsRecords")
    payload = statistics_parser.build_statistics_payload(
        [],
        record_results,
        screen_size,
        summary_card_results=summary_card_results,
    )
    if payload["snapshotId"] == previous_snapshot:
        print("İstatistik ekranı değişmedi; tekrar gönderilmedi.")
        return payload["snapshotId"], True
    try:
        result = sync_client.send_statistics(payload)
        if result.get("duplicate"):
            print("İstatistik ekranı daha önce senkronize edilmiş; tekrar kaydedilmedi.")
        elif result.get("throttled"):
            print("İstatistik senkronizasyonu 5 dakikalık bekleme aralığında.")
        else:
            print("Oyuncu istatistikleri RF4Club profiline senkronize edildi.")
            play_sync_sound()
        return payload["snapshotId"], True
    except Exception as exc:
        sync_client.queue_pending_statistics(payload)
        print(f"İstatistikler yerel kuyruğa alındı: {exc}")
        return payload["snapshotId"], True


def ensure_paired(pairing_code=None, api_base_url=None):
    if sync_client.load_device_token():
        return
    code = pairing_code or input(
        "RF4Club profilindeki 8 karakterli eşleştirme kodunu gir: "
    ).strip()
    code = re.sub(r"[^A-Z0-9]", "", code.upper())
    if not re.fullmatch(r"[A-HJ-NP-Z2-9]{8}", code):
        raise RuntimeError(
            "Kod biçimi geçersiz. Profilde 'Eşleştirme Kodu Oluştur' düğmesine "
            "basıp üretilen 8 karakterli kodu kullan (0, 1, I ve O kullanılmaz)."
        )
    payload = sync_client.pair_device(code, api_base_url=api_base_url)
    print(f"Cihaz eşleştirildi: {payload['device']['name']}")


def monitor(pairing_code=None, api_base_url=None):
    ensure_paired(pairing_code, api_base_url)
    initialize_ocr()
    screen_size = primary_screen_size()
    armed = True
    absent_since = time.monotonic()
    last_process_warning = 0.0
    last_window_warning = 0.0
    context_absent_since = None
    last_statistics_probe = 0.0
    statistics_state = load_statistics_state()
    state_age = max(0.0, time.time() - statistics_state["syncedAtEpoch"])
    last_statistics_sync = (
        time.monotonic() - state_age
        if state_age < config.STATISTICS_SYNC_INTERVAL_SECONDS
        else 0.0
    )
    last_statistics_snapshot = statistics_state["snapshotId"]
    print(f"RF4Club Sync v{APP_VERSION} çalışıyor.")
    print("Salt okunur mod: klavye/fare girdisi gönderilmez.")
    print(f"Ekran: {screen_size[0]}x{screen_size[1]}")
    sync_client.flush_pending()
    while True:
        if not is_process_running(config.GAME_PROCESS_NAME):
            if time.monotonic() - last_process_warning > 30:
                print("RF4 bekleniyor...")
                last_process_warning = time.monotonic()
            time.sleep(2)
            continue
        client_context = foreground_game_context()
        if not client_context.get("gameForeground") or not client_context.get("fullscreen"):
            if context_absent_since is None:
                context_absent_since = time.monotonic()
            elif time.monotonic() - context_absent_since >= config.KEEP_REARM_DELAY_SECONDS:
                # The KEEP screen may have disappeared while RF4 was not observable.
                # Rearm so the next real catch is not skipped after returning to RF4.
                armed = True
                absent_since = None
            if time.monotonic() - last_window_warning > 15:
                process = client_context.get("foregroundProcess") or "bilinmiyor"
                bounds = client_context.get("windowBounds") or {}
                print(
                    "RF4 penceresi bekleniyor "
                    f"(ön plan: {process}, sınırlar: {bounds})..."
                )
                last_window_warning = time.monotonic()
            time.sleep(1)
            continue
        context_absent_since = None
        full_screen = capture_full_screen(client_context)
        frame_size = (full_screen.shape[1], full_screen.shape[0])
        keep_region = scale_region(config.KEEP_REGION, frame_size)
        fish_region = scale_region(config.FISH_HEADER_REGION, frame_size)
        trophy_label_region = scale_region(config.TROPHY_LABEL_REGION, frame_size)
        keep_results = ocr_region(full_screen, keep_region, "KeepTrigger")
        visible = keep_is_visible(keep_results)
        if visible and armed:
            fish_results = ocr_region(full_screen, fish_region, "FishHeader")
            trophy_results = ocr_region(
                full_screen,
                trophy_label_region,
                "TrophyLabel",
            )
            record_catch(
                full_screen,
                fish_results,
                client_context,
                trophy_results,
            )
            armed = False
            absent_since = None
            sync_client.flush_pending()
        elif not visible:
            if absent_since is None:
                absent_since = time.monotonic()
            elif time.monotonic() - absent_since >= config.KEEP_REARM_DELAY_SECONDS:
                armed = True
        now = time.monotonic()
        if not visible and now - last_statistics_probe >= config.STATISTICS_TRIGGER_POLL_SECONDS:
            last_statistics_probe = now
            statistics_region = scale_region(config.STATISTICS_TRIGGER_REGION, frame_size)
            statistics_results = ocr_region(
                full_screen,
                statistics_region,
                "StatisticsTrigger",
            )
            if (
                statistics_parser.is_statistics_screen(statistics_results)
                and now - last_statistics_sync >= config.STATISTICS_SYNC_INTERVAL_SECONDS
            ):
                snapshot_id, attempted = record_statistics(
                    full_screen,
                    frame_size,
                    last_statistics_snapshot,
                )
                last_statistics_snapshot = snapshot_id
                if attempted:
                    last_statistics_sync = time.monotonic()
                    save_statistics_state(snapshot_id)
                sync_client.flush_pending()
        time.sleep(config.POLL_INTERVAL_SECONDS)


def main():
    parser = argparse.ArgumentParser(
        description="RF4 KEEP/TUT ekranını salt okunur biçimde RF4Club profiline aktarır."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"RF4Club Sync {APP_VERSION}",
    )
    parser.add_argument(
        "--pair",
        metavar="CODE",
        help="RF4Club profilinden alınan tek kullanımlık eşleştirme kodu.",
    )
    parser.add_argument(
        "--server",
        metavar="URL",
        help="RF4Club adresi (ilk eşleştirmede cihaz ayarına kaydedilir).",
    )
    args = parser.parse_args()
    try:
        monitor(args.pair, args.server)
    except KeyboardInterrupt:
        print("\nRF4Club Sync durduruldu.")
    except Exception as exc:
        print(f"\nLogger başlatılamadı: {exc}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
