
import csv
import datetime
import json
import os

import config

RAW_OCR_COLUMNS = ["Timestamp", "Region", "RawOCRResult"]
CATCH_COLUMNS = [
    "Timestamp", "EventId", "FishName", "TrophyType",
    "OCRConfidence", "ScreenshotPath", "SyncStatus",
]


def _append_row(filename, columns, row):
    parent = os.path.dirname(os.path.abspath(filename))
    os.makedirs(parent, exist_ok=True)
    exists = os.path.exists(filename)
    with open(filename, "a", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=columns)
        if not exists:
            writer.writeheader()
        writer.writerow({column: row.get(column, "") for column in columns})


def append_to_raw_ocr_log(region_name, raw_ocr_result):
    _append_row(
        config.RAW_OCR_LOG_FILE,
        RAW_OCR_COLUMNS,
        {
            "Timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "Region": region_name,
            "RawOCRResult": json.dumps(raw_ocr_result, ensure_ascii=False, default=str),
        },
    )


def append_to_catch_log(data):
    _append_row(config.CATCH_LOG_FILE, CATCH_COLUMNS, data)

