import datetime
import hashlib
import json
import re

import config


SUMMARY_CARDS = {
    # Only the lime value is cropped. Reading an entire card caused labels and
    # icons to be mistaken for digits, especially for a genuine zero value.
    "daysInGame": (245, 140, 95, 45),
    "experiencePoints": (365, 140, 160, 45),
    "experienceToNextLevel": (575, 140, 135, 45),
    "brokenRods": (810, 140, 80, 45),
    "brokenReels": (995, 140, 80, 45),
    "cafeOrdersCompleted": (1170, 140, 95, 45),
    "competitionsPlayed": (1350, 140, 95, 45),
    "competitionsWon": (1540, 140, 90, 45),
    "fishKept": (1730, 140, 90, 45),
    "fishCaught": (620, 245, 100, 45),
    "awardFishCaught": (810, 245, 85, 45),
    "rareAwardFishCaught": (995, 245, 70, 45),
    "recordFishCaught": (1170, 245, 90, 45),
    "recordTotalWeightKg": (1325, 240, 160, 55),
}

RECORD_CARDS = {
    "recordCast": (258, 336, 357, 191),
    "recordCatch": (628, 336, 356, 191),
    "recordFloatCatch": (997, 336, 356, 191),
    "recordSpinCatch": (1367, 336, 356, 191),
    "recordBottomCatch": (258, 539, 357, 193),
    "strongestOpponent": (628, 539, 356, 193),
    "riskiestCatch": (997, 539, 356, 193),
    "mostExperience": (1367, 539, 356, 193),
    "mostSilver": (810, 743, 358, 193),
}


def _normalize(value):
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def is_statistics_screen(results):
    text = _normalize(" ".join(str(item.get("text") or "") for item in results))
    has_title = any(word in text for word in config.STATISTICS_TITLE_WORDS)
    has_tab = any(word in text for word in config.STATISTICS_TAB_WORDS)
    return has_title and has_tab


def _center(item, crop_region, screen_size):
    points = item.get("box") or []
    if not points:
        return None
    reference_width, reference_height = config.REFERENCE_RESOLUTION
    screen_width, screen_height = screen_size
    scale_x = screen_width / reference_width
    scale_y = screen_height / reference_height
    x = sum(float(point[0]) for point in points) / len(points) / config.OCR_SCALE
    y = sum(float(point[1]) for point in points) / len(points) / config.OCR_SCALE
    return crop_region[0] + x / scale_x, crop_region[1] + y / scale_y


def _inside(point, rectangle):
    if point is None:
        return False
    x, y = point
    left, top, width, height = rectangle
    return left <= x <= left + width and top <= y <= top + height


def _assign(results, crop_region, screen_size, rectangles):
    assigned = {key: [] for key in rectangles}
    for item in results:
        point = _center(item, crop_region, screen_size)
        for key, rectangle in rectangles.items():
            if _inside(point, rectangle):
                assigned[key].append(item)
                break
    return assigned


def _numeric_token(items):
    candidates = []
    for item in items:
        text = str(item.get("text") or "").strip()
        match = re.search(r"\d[\d\s.,]*", text)
        if not match:
            continue
        candidates.append((float(item.get("confidence") or 0), match.group(0).strip(), text))
    if not candidates:
        return None
    candidates.sort(key=lambda value: value[0], reverse=True)
    return candidates[0][1]


def _parse_integer(token):
    digits = re.sub(r"\D", "", str(token or ""))
    return int(digits) if digits else None


def _parse_decimal(token):
    text = re.sub(r"[^\d,.]", "", str(token or ""))
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return None


def _serialize(items):
    return [
        {
            "text": str(item.get("text") or ""),
            "confidence": round(float(item.get("confidence") or 0), 4),
            "box": [[round(float(point[0]), 2), round(float(point[1]), 2)] for point in item.get("box") or []],
        }
        for item in items
    ]


def _record_length(lines, record_key):
    candidates = []
    for line_index, line in enumerate(lines):
        normalized = _normalize(line)
        for match in re.finditer(r"(\d+[,.]?\d*)\s*(cm|m)\b", line, re.IGNORECASE):
            value = _parse_decimal(match.group(1))
            if value is None:
                continue
            score = 0
            if record_key == "recordCast":
                score += 100 if re.search(r"[,.]", match.group(1)) else 0
                if any(word in normalized for word in ("rod", "kamış", "kamis", "carp", "reel", "makine")):
                    score -= 200
                if match.group(2).lower() == "m" and 1 <= value <= 250:
                    score += 20
            candidates.append((score, -line_index, value, match.group(2).lower()))
    if not candidates:
        return None, None
    candidates.sort(reverse=True)
    return candidates[0][2], candidates[0][3]


def _record_payload(items, record_key=None):
    ordered = sorted(
        items,
        key=lambda item: (
            min((float(point[1]) for point in item.get("box") or []), default=0),
            min((float(point[0]) for point in item.get("box") or []), default=0),
        ),
    )
    lines = [str(item.get("text") or "").strip() for item in ordered if str(item.get("text") or "").strip()]
    joined = " | ".join(lines)
    weight_match = re.search(r"(\d+[,.]\d+)\s*k", joined, re.IGNORECASE)
    length, length_unit = _record_length(lines, record_key)
    return {
        "lines": lines,
        "weightKg": _parse_decimal(weight_match.group(1)) if weight_match else None,
        "length": length,
        "lengthUnit": length_unit,
        "rawOcr": _serialize(ordered),
    }


def build_statistics_payload(
    summary_results,
    record_results,
    screen_size,
    summary_card_results=None,
    record_card_results=None,
):
    summary_groups = summary_card_results or _assign(
        summary_results,
        config.STATISTICS_SUMMARY_REGION,
        screen_size,
        SUMMARY_CARDS,
    )
    record_groups = record_card_results or _assign(
        record_results,
        config.STATISTICS_RECORDS_REGION,
        screen_size,
        RECORD_CARDS,
    )

    summary = {}
    for key, items in summary_groups.items():
        token = _numeric_token(items)
        summary[key] = (
            _parse_decimal(token)
            if key == "recordTotalWeightKg"
            else _parse_integer(token)
        )

    records = {
        key: _record_payload(items, key)
        for key, items in record_groups.items()
    }
    stable = {"summary": summary, "records": {key: value["lines"] for key, value in records.items()}}
    snapshot_hash = hashlib.sha256(
        json.dumps(stable, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "schemaVersion": 1,
        "snapshotId": snapshot_hash,
        "capturedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "screen": {"width": int(screen_size[0]), "height": int(screen_size[1]), "uiScale": 0.75},
        "summary": summary,
        "records": records,
        "rawOcr": {
            "summary": (
                {key: _serialize(items) for key, items in summary_groups.items()}
                if summary_card_results
                else _serialize(summary_results)
            ),
            "records": (
                {key: _serialize(items) for key, items in record_groups.items()}
                if record_card_results
                else _serialize(record_results)
            ),
        },
    }


def is_valid_statistics_payload(payload, minimum_summary_values=5):
    summary = payload.get("summary") if isinstance(payload, dict) else None
    if not isinstance(summary, dict):
        return False
    readable_values = sum(
        value is not None and isinstance(value, (int, float)) and value >= 0
        for value in summary.values()
    )
    return readable_values >= minimum_summary_values
