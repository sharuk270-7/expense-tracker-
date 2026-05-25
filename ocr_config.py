"""
OCR method configuration and loader.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Available OCR methods:
# - "tesseract": Original Tesseract-OCR (system software required)
# - "easyocr": EasyOCR (pip installable, heavier first initialization)
# - "paddleocr": PaddleOCR
#
# Default is tesseract to avoid heavy model initialization stalls on startup.
CURRENT_OCR_METHOD = os.getenv("OCR_METHOD", "tesseract").strip().lower()

OCR_METHODS = {
    "tesseract": {
        "class": "OCRProcessor",
        "module": "nlp_processor",
        "description": "Original Tesseract-OCR",
        "requires_system_software": True,
        "pip_installable": False,
        "speed": "Medium",
        "accuracy": "Excellent",
    },
    "easyocr": {
        "class": "EasyOCRProcessor",
        "module": "nlp_processor",
        "description": "EasyOCR",
        "requires_system_software": False,
        "pip_installable": True,
        "speed": "Fast",
        "accuracy": "Excellent",
    },
    "paddleocr": {
        "class": "PaddleOCRProcessor",
        "module": "nlp_processor",
        "description": "PaddleOCR",
        "requires_system_software": False,
        "pip_installable": True,
        "speed": "Very Fast",
        "accuracy": "Excellent",
    },
}

_PROCESSOR_CACHE = {}


def _build_method_order():
    """Build a safe method fallback order."""
    selected = CURRENT_OCR_METHOD if CURRENT_OCR_METHOD in OCR_METHODS else "tesseract"
    if selected != CURRENT_OCR_METHOD:
        logger.warning(
            "Unknown OCR method '%s'. Falling back to '%s'.",
            CURRENT_OCR_METHOD,
            selected,
        )

    order = [selected]
    for fallback in ("tesseract", "easyocr", "paddleocr"):
        if fallback not in order:
            order.append(fallback)
    return order


def _load_processor(method_name):
    """Instantiate a processor for one method."""
    method_config = OCR_METHODS[method_name]
    module = __import__(method_config["module"], fromlist=[method_config["class"]])
    processor_class = getattr(module, method_config["class"])
    return processor_class()


def get_ocr_processor():
    """
    Dynamically load OCR processor with caching and fallbacks.
    Usage: processor = get_ocr_processor()
    """
    for method_name in _build_method_order():
        if method_name in _PROCESSOR_CACHE:
            return _PROCESSOR_CACHE[method_name]

        try:
            processor = _load_processor(method_name)
            _PROCESSOR_CACHE[method_name] = processor
            logger.info("Using OCR method: %s", method_name)
            return processor
        except ImportError as import_error:
            logger.warning(
                "OCR method '%s' import failed: %s",
                method_name,
                import_error,
            )
        except Exception as init_error:
            logger.warning(
                "OCR method '%s' initialization failed: %s",
                method_name,
                init_error,
            )

    logger.error("No OCR processor could be initialized")
    return None


def check_method_available(method_name):
    """Check if a specific OCR method is available."""
    if method_name not in OCR_METHODS:
        return False

    try:
        method_config = OCR_METHODS[method_name]
        module = __import__(method_config["module"], fromlist=[method_config["class"]])
        getattr(module, method_config["class"])
        return True
    except Exception:
        return False


def get_available_methods():
    """Return list of available OCR methods."""
    available = []
    for method_name in OCR_METHODS:
        if check_method_available(method_name):
            available.append(
                {
                    "name": method_name,
                    "description": OCR_METHODS[method_name]["description"],
                    "speed": OCR_METHODS[method_name]["speed"],
                    "accuracy": OCR_METHODS[method_name]["accuracy"],
                }
            )
    return available
