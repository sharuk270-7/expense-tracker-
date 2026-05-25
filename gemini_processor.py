"""
Gemini AI processor for receipt analysis.
"""
import json
import logging
import re
import time
import warnings

import PIL.Image

from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        import google.generativeai as genai
except ImportError as import_error:
    logger.error("google-generativeai import failed: %s", import_error)
    genai = None


class GeminiProcessor:
    """Wrapper around Gemini image analysis with safe fallbacks."""

    def __init__(self):
        self.model = None
        self.model_name = None
        self._init_error = None
        self._model_cache = {}
        self._available_generation_models = set()
        self._candidates = []
        self._blocked_models = set()
        self._cooldown_until = 0.0

        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY is not set")
            self._init_error = "GEMINI_API_KEY is not set"
            return

        if not genai:
            logger.warning("Gemini SDK unavailable, image analysis will use OCR fallback")
            self._init_error = "Gemini SDK import failed"
            return

        try:
            genai.configure(api_key=GEMINI_API_KEY)
            self._available_generation_models = self._discover_generate_content_models()
            self._candidates = self._build_candidate_models()
            if not self._candidates:
                raise RuntimeError("No Gemini models available for generateContent")
            self.model_name = self._candidates[0]
            self.model = self._get_model(self.model_name)
            logger.info("Gemini initialized with model: %s", self.model_name)
        except Exception as init_error:
            logger.error("Gemini initialization failed: %s", init_error)
            self._init_error = str(init_error)
            self.model = None
            self.model_name = None

    def _discover_generate_content_models(self):
        """Discover model IDs that support generateContent."""
        available = set()
        try:
            for model in genai.list_models():
                methods = getattr(model, "supported_generation_methods", []) or []
                if "generateContent" not in methods:
                    continue

                name = getattr(model, "name", "") or ""
                if name.startswith("models/"):
                    name = name.split("/", 1)[1]

                if name and name.startswith("gemini"):
                    available.add(name)
        except Exception as discover_error:
            logger.warning(
                "Could not discover Gemini models dynamically. Falling back to static list. Error: %s",
                discover_error,
            )

        return available

    def _build_candidate_models(self):
        """Build prioritized candidates, preferring known stable model names."""
        preferred = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
            "gemini-flash-latest",
            "gemini-1.5-flash-latest",
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]

        if not self._available_generation_models:
            return preferred

        candidates = [name for name in preferred if name in self._available_generation_models]
        for name in sorted(self._available_generation_models):
            if name in candidates:
                continue
            if not self._is_reasonable_fallback_model(name):
                continue
            candidates.append(name)

        return candidates

    def _is_reasonable_fallback_model(self, model_name):
        lowered = model_name.lower()
        blocked_tokens = [
            "embedding",
            "aqa",
            "tts",
            "imagen",
            "veo",
            "robotics",
            "computer-use",
            "deep-research",
            "customtools",
            "image-generation",
            "flash-image",
            "preview",
            "-exp",
            "experimental",
        ]
        return not any(token in lowered for token in blocked_tokens)

    def analyze_receipt(self, image_path):
        """
        Analyze a receipt image and return structured receipt fields.
        Expected keys:
        - merchant
        - date
        - subtotal
        - total
        - grand_total
        - final_amount
        """
        if not self.model:
            payload = {
                "error": "Gemini model not initialized",
                "code": "not_initialized",
                "hint": "Set a valid GEMINI_API_KEY and ensure Gemini API billing/quota is enabled.",
            }
            if self._init_error:
                payload["details"] = self._compact_error(self._init_error)
            return payload

        now = time.time()
        if now < self._cooldown_until:
            retry_after = int(self._cooldown_until - now)
            return {
                "error": "Gemini temporarily in cooldown due to quota/rate limits",
                "code": "quota_cooldown",
                "hint": "Gemini quota/rate limit reached. OCR fallback is active until cooldown expires.",
                "retry_after_seconds": retry_after,
            }

        prompt = (
            "Analyze this image (receipt OR UPI payment screenshot) and extract structured data. "
            "Return JSON only with keys: "
            "\"image_type\" (one of: receipt, upi, unknown), "
            "\"merchant\" (string or null), "
            "\"date\" (string or null), "
            "\"transaction_time\" (string with date + time if visible, else null), "
            "\"subtotal\" (number or null), "
            "\"total\" (number or null), "
            "\"grand_total\" (number or null), "
            "\"final_amount\" (number or null), "
            "\"amount\" (number or null), "
            "\"upi_to\" (string or null), "
            "\"upi_from\" (string or null), "
            "\"upi_transaction_id\" (string or null), "
            "\"items\" (array of objects with keys: name, quantity, unit_price, total_price, category). "
            "If this is a UPI screenshot, prioritize amount/to/from/transaction_time/upi_transaction_id. "
            "For transaction_time, include clock time (HH:MM with am/pm if present in image)."
        )

        try:
            with PIL.Image.open(image_path) as image:
                image.load()
                response = self._generate_content([prompt, image])

            data = self._parse_response_json(response)
            self._normalize_receipt(data)
            return data
        except Exception as analyze_error:
            retry_after = None
            error_code = "unknown_error"
            hint = "Gemini request failed. OCR fallback will be used."
            if self._is_quota_or_rate_limit_error(analyze_error):
                error_code = "quota_exceeded"
                hint = "Gemini quota exceeded. Enable billing/increase quota for this API key."
                retry_after = self._extract_retry_delay_seconds(str(analyze_error))
                cooldown_seconds = max(retry_after, 60)
                # If daily quota was hit, back off longer to avoid repeated failures.
                error_text = str(analyze_error).lower()
                if "perday" in error_text or "per day" in error_text:
                    cooldown_seconds = max(cooldown_seconds, 3600)
                self._cooldown_until = time.time() + cooldown_seconds
                logger.warning(
                    "Gemini quota/rate-limit detected. Cooldown for %ss.",
                    cooldown_seconds,
                )
            elif self._is_auth_or_permission_error(analyze_error):
                error_code = "auth_or_permission_error"
                hint = "Gemini API key is invalid or lacks project permissions/billing."
            elif self._is_model_not_available_error(analyze_error):
                error_code = "model_not_available"
                hint = "Configured Gemini model is not available for this API version/key."
            elif self._is_json_parse_error(analyze_error):
                error_code = "response_parse_error"
                hint = "Gemini returned an unstructured response. OCR fallback will be used."

            logger.error("Gemini receipt analysis failed: %s", analyze_error)
            payload = {
                "error": str(analyze_error),
                "code": error_code,
                "hint": hint,
            }
            if retry_after:
                payload["retry_after_seconds"] = retry_after
            return payload

    def _get_model(self, model_name):
        cached = self._model_cache.get(model_name)
        if cached is None:
            cached = genai.GenerativeModel(model_name)
            self._model_cache[model_name] = cached
        return cached

    def _generate_content(self, content):
        """Try model candidates in order."""
        ordered_candidates = [m for m in self._candidates if m not in self._blocked_models]
        if self.model_name in ordered_candidates:
            ordered_candidates = [self.model_name] + [m for m in ordered_candidates if m != self.model_name]
        if not ordered_candidates:
            raise RuntimeError("No Gemini models left to try after filtering blocked models")

        last_error = None
        for idx, model_name in enumerate(ordered_candidates):
            try:
                model = self._get_model(model_name)
                response = model.generate_content(content)
                self.model = model
                self.model_name = model_name
                return response
            except Exception as model_error:
                last_error = model_error
                if self._is_model_not_available_error(model_error):
                    self._blocked_models.add(model_name)
                if not self._should_retry(model_error):
                    raise
                if idx < len(ordered_candidates) - 1:
                    logger.warning(
                        "Gemini model '%s' failed (%s), trying next model",
                        model_name,
                        self._compact_error(model_error),
                    )
        raise last_error

    def _should_retry(self, error):
        error_text = str(error).lower()
        retry_signals = [
            "404",
            "not found",
            "unsupported",
            "not supported",
            "unknown model",
            "429",
            "quota exceeded",
            "rate limit",
            "resource exhausted",
        ]
        return any(signal in error_text for signal in retry_signals)

    def _is_model_not_available_error(self, error):
        text = str(error).lower()
        signals = [
            "404",
            "not found",
            "unknown model",
            "not supported for generatecontent",
            "is not supported for generatecontent",
            "does not support",
        ]
        return any(signal in text for signal in signals)

    def _is_auth_or_permission_error(self, error):
        text = str(error).lower()
        signals = [
            "401",
            "403",
            "permission denied",
            "api key not valid",
            "invalid api key",
            "access denied",
            "authentication",
            "unauthorized",
        ]
        return any(signal in text for signal in signals)

    def _compact_error(self, error):
        text = str(error).replace("\n", " ").strip()
        if len(text) > 220:
            return text[:220] + "..."
        return text

    def _is_json_parse_error(self, error):
        text = str(error).lower()
        signals = [
            "could not locate json object",
            "did not contain text",
            "expecting value",
            "json decode",
        ]
        return any(signal in text for signal in signals)

    def _is_quota_or_rate_limit_error(self, error):
        error_text = str(error).lower()
        return (
            "429" in error_text
            or "quota exceeded" in error_text
            or "rate limit" in error_text
            or "resource exhausted" in error_text
        )

    def _extract_retry_delay_seconds(self, error_text):
        text = (error_text or "").lower()

        # Example: "Please retry in 28.224100157s."
        match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", text)
        if match:
            return max(1, int(float(match.group(1))))

        # Example protobuf-style text: retry_delay { seconds: 28 }
        match = re.search(r"retry_delay\s*\{[^}]*seconds:\s*(\d+)", text, flags=re.DOTALL)
        if match:
            return max(1, int(match.group(1)))

        # Conservative fallback
        return 60

    def _parse_response_json(self, response):
        raw = ""
        try:
            raw = (response.text or "").strip()
        except Exception:
            raw = ""

        if not raw:
            raise ValueError("Gemini response did not contain text")

        # Fast path: raw response is JSON.
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Remove markdown code fences if present.
        fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE | re.MULTILINE)
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            pass

        # Extract first JSON object from explanatory text.
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            fallback = self._parse_key_value_receipt(raw)
            if fallback:
                return fallback
            raise ValueError("Could not locate JSON object in Gemini response")

        return json.loads(match.group(0))

    def _parse_key_value_receipt(self, raw_text):
        """
        Best-effort parser for responses like:
        merchant: XYZ
        total: 123.45
        """
        if not raw_text:
            return None

        target_keys = {"merchant", "date", "subtotal", "total", "grand_total", "final_amount"}
        result = {}

        for line in raw_text.splitlines():
            match = re.match(r"^\s*([a-zA-Z_ ]+)\s*:\s*(.+?)\s*$", line)
            if not match:
                continue
            key = match.group(1).strip().lower().replace(" ", "_")
            value = match.group(2).strip()
            if key not in target_keys:
                continue
            if value.lower() in {"null", "none", "n/a", "not found"}:
                result[key] = None
            else:
                result[key] = value

        return result if result else None

    def _normalize_receipt(self, data):
        normalized_items = []
        for item in (data.get("items") or []):
            if not isinstance(item, dict):
                continue
            name = (item.get("name") or "").strip()
            quantity_val = self._to_float(item.get("quantity"))
            unit_price = self._to_float(item.get("unit_price") or item.get("price"))
            total_price = self._to_float(item.get("total_price") or item.get("amount"))
            if total_price is None and unit_price and quantity_val:
                total_price = round(unit_price * quantity_val, 2)

            quantity = None
            if quantity_val is not None and quantity_val > 0:
                quantity = int(quantity_val) if float(quantity_val).is_integer() else quantity_val
            elif total_price is not None:
                quantity = 1

            category = (item.get("category") or "").strip() or None
            if not name and total_price is None:
                continue
            if not name:
                name = "Receipt Item"

            normalized_items.append({
                "name": name,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "category": category,
            })

        data["items"] = normalized_items
        image_type = (data.get("image_type") or "").strip().lower()
        if image_type:
            if "upi" in image_type or "payment" in image_type:
                image_type = "upi"
            elif image_type in {"receipt", "bill", "invoice"}:
                image_type = "receipt"
            else:
                image_type = "unknown"
        data["image_type"] = image_type or None

        data["merchant"] = (data.get("merchant") or "").strip() or None
        data["date"] = (data.get("date") or "").strip() or None
        data["transaction_time"] = (data.get("transaction_time") or "").strip() or data["date"]
        data["upi_to"] = (data.get("upi_to") or "").strip() or None
        data["upi_from"] = (data.get("upi_from") or "").strip() or None
        data["upi_transaction_id"] = (data.get("upi_transaction_id") or "").strip() or None
        data["subtotal"] = self._to_float(data.get("subtotal"))
        data["total"] = self._to_float(data.get("total"))
        data["grand_total"] = self._to_float(data.get("grand_total"))
        data["final_amount"] = self._to_float(data.get("final_amount"))
        data["amount"] = (
            self._to_float(data.get("amount"))
            or data["final_amount"]
            or data["grand_total"]
            or data["total"]
            or data["subtotal"]
        )

    def _to_float(self, value):
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = value.replace(",", ".").strip()
            number = float(value)
            if number <= 0:
                return None
            return number
        except (ValueError, TypeError):
            return None