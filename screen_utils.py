import os
import sys

import cv2
import easyocr
import mss
import numpy as np


# ============================================================
# OCR INITIALIZATION
# ============================================================

print("Initializing EasyOCR Reader...")

reader = None

try:
    reader_kwargs = {"gpu": False}
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled_models = os.path.join(sys._MEIPASS, "easyocr-models")
        if os.path.isdir(bundled_models):
            reader_kwargs.update(
                model_storage_directory=bundled_models,
                download_enabled=False,
            )
    reader = easyocr.Reader(
        ["en"],
        **reader_kwargs,
    )
    print("EasyOCR initialized successfully (CPU).")

except Exception as exc:
    print(f"EasyOCR initialization failed: {exc}")


# ============================================================
# SCREEN CAPTURE
# ============================================================

def capture_region(region, filename=None):
    """
    Captures a rectangular region of the screen.

    Region format:
        (left, top, width, height)

    Returns:
        OpenCV BGR numpy array, or None on failure.
    """

    left, top, width, height = region

    monitor = {
        "top": int(top),
        "left": int(left),
        "width": int(width),
        "height": int(height),
    }

    try:
        with mss.MSS() as sct:
            screenshot = sct.grab(monitor)

        image = np.array(
            screenshot,
            dtype=np.uint8,
        )

        image_bgr = cv2.cvtColor(
            image,
            cv2.COLOR_BGRA2BGR,
        )

        if filename:
            output_dir = os.path.dirname(filename)

            if output_dir:
                os.makedirs(
                    output_dir,
                    exist_ok=True,
                )

            if not cv2.imwrite(
                filename,
                image_bgr,
            ):
                print(
                    f"Could not save screenshot: {filename}"
                )

        return image_bgr

    except mss.ScreenShotError as exc:
        print(
            f"Screen capture failed for {region}: {exc}"
        )
        return None

    except Exception as exc:
        print(
            f"Screen capture error: {exc}"
        )
        return None


# ============================================================
# OCR
# ============================================================

def perform_ocr(image_path_or_array, allowlist=None):
    """
    Performs OCR on either an image path or a numpy array.

    Returns:
        (detected_texts, raw_results)
    """

    if reader is None:
        print(
            "EasyOCR reader is not initialized."
        )
        return [], []

    try:
        if isinstance(
            image_path_or_array,
            str,
        ):
            if not os.path.exists(
                image_path_or_array
            ):
                print(
                    "OCR image not found: "
                    f"{image_path_or_array}"
                )
                return [], []

            image = cv2.imread(
                image_path_or_array
            )

            if image is None:
                print(
                    "Could not read OCR image: "
                    f"{image_path_or_array}"
                )
                return [], []

        elif isinstance(
            image_path_or_array,
            np.ndarray,
        ):
            image = image_path_or_array

        else:
            print("Invalid OCR input.")
            return [], []

        ocr_kwargs = {
            "detail": 1,
            "paragraph": False,
        }

        if allowlist:
            ocr_kwargs["allowlist"] = allowlist

        result = reader.readtext(
            image,
            **ocr_kwargs,
        )

        detected_texts = [
            text
            for _, text, _ in result
        ]

        return detected_texts, result

    except Exception as exc:
        print(
            f"OCR error: {exc}"
        )
        return [], []


# ============================================================
# TEXT DETECTION
# ============================================================

def check_text_in_region(
    region,
    target_text,
    confidence_threshold=0.5,
):
    """
    Captures a screen region and checks whether
    the requested text is detected with sufficient
    OCR confidence.
    """

    image = capture_region(region)

    if image is None:
        return False

    _, raw_results = perform_ocr(image)

    if not raw_results:
        return False

    target = str(target_text).lower()

    for _, text, confidence in raw_results:
        if confidence < confidence_threshold:
            continue

        if target in text.lower():
            return True

    return False
