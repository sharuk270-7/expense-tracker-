"""
Main Telegram Bot Handler for Expense Tracker
"""
import logging
import re
import time
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import TelegramError

from config import BOT_TOKEN, CURRENCY, GEMINI_API_KEY
from database import ExpenseDatabase
from nlp_processor import ExpenseParser
from bot_commands import (
    start,
    help_command,
    summary,
    weekly_summary,
    monthly_summary,
    today_total,
    show_categories,
    list_expenses,
    delete_expense,
    statistics,
    export_all,
    export_monthly,
    export_weekly,
    export_today_data,
    export_date_range,
    set_daily_limit,
    set_weekly_limit,
    set_monthly_limit,
    check_limits,
    report_week,
    report_month,
    export_csv,
    export_pdf,
    export_graph,
)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database and parser
db = ExpenseDatabase()
parser = ExpenseParser()
gemini = None
if GEMINI_API_KEY:
    try:
        from gemini_processor import GeminiProcessor
        gemini = GeminiProcessor()
    except Exception as gemini_error:
        logger.warning("Gemini disabled due to initialization error: %s", gemini_error)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages for expense tracking"""
    
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    text = update.message.text.strip()
    
    # Skip if it's a command
    if text.startswith('/'):
        return
    
    # Check if it's multiple expenses (contains newlines)
    if '\n' in text:
        # Parse multiple expenses
        expenses = parser.parse_multiple_expenses(text)
        
        if not expenses:
            await update.message.reply_text(
                "❌ Could not parse any expenses from your input.\n\n"
                "Format: Each line should have amount and description\n"
                "Example:\n"
                "Coffee 30\n"
                "Apple 150\n"
                "Tea 40"
            )
            return
        
        # Store all expenses
        success_count = 0
        response_lines = ["✅ **Multiple Expenses Recorded!**\n"]
        
        for amount, category, description in expenses:
            if parser.is_valid_expense(amount, category):
                db.add_expense(user.id, amount, category, description, source="text")
                success_count += 1
                response_lines.append(f"✓ {description}")
                response_lines.append(f"  Amount: {CURRENCY}{amount:.2f} | Category: {category}")
        
        if success_count > 0:
            response_lines.append(f"\n📊 Total: {success_count} expenses recorded")
            response_lines.append("Use /summary to see your spending patterns!")
            confirmation = "\n".join(response_lines)
            await update.message.reply_text(confirmation, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Could not process any of the expenses. Please check the format.")
        
        return
    
    # Single expense parsing
    amount, category, description = parser.parse_expense(text)
    
    if not amount:
        await update.message.reply_text(
            "❌ I couldn't extract amount from your message.\n\n"
            "Try:\n"
            "• 'Spent 150 for biriyani'\n"
            "• '50 on transport'\n"
            "• '200 for movie'\n\n"
            "Or for multiple expenses, send each on a new line:\n"
            "Coffee 30\n"
            "Apple 150\n"
            "Tea 40"
        )
        return
    
    # Validate
    if not parser.is_valid_expense(amount, category):
        await update.message.reply_text("❌ Invalid expense data. Please try again.")
        return
    
    # Store in database
    db.add_expense(user.id, amount, category, description, source="text")
    
    # Send confirmation
    confirmation = (
        f"✅ **Expense Recorded!**\n\n"
        f"💰 Amount: {CURRENCY}{amount:.2f}\n"
        f"🏷️ Category: {category}\n"
        f"📝 Description: {description}\n\n"
        f"Use /summary to see your spending patterns!"
    )
    
    await update.message.reply_text(confirmation, parse_mode='Markdown')
    
    # Check budget limits and send warning if needed
    daily_limit, weekly_limit, monthly_limit = db.get_budget_limits(user.id)
    
    if any([daily_limit, weekly_limit, monthly_limit]):
        today_total = db.get_total_today(user.id)
        week_total = db.get_total_week(user.id)
        month_total = db.get_total_month(user.id)
        
        warnings = []
        
        # Check daily limit
        if daily_limit:
            daily_percentage = (today_total / daily_limit) * 100
            if daily_percentage >= 100:
                warnings.append(f"🔴 Daily limit EXCEEDED: {CURRENCY}{today_total:.2f} / {CURRENCY}{daily_limit:.2f}")
            elif daily_percentage >= 90:
                warnings.append(f"⚠️ Daily limit at 90%: {CURRENCY}{today_total:.2f} / {CURRENCY}{daily_limit:.2f}")
            elif daily_percentage >= 75:
                warnings.append(f"⚡ Daily limit at 75%: {CURRENCY}{today_total:.2f} / {CURRENCY}{daily_limit:.2f}")
        
        # Check weekly limit
        if weekly_limit:
            weekly_percentage = (week_total / weekly_limit) * 100
            if weekly_percentage >= 100:
                warnings.append(f"🔴 Weekly limit EXCEEDED: {CURRENCY}{week_total:.2f} / {CURRENCY}{weekly_limit:.2f}")
            elif weekly_percentage >= 90:
                warnings.append(f"⚠️ Weekly limit at 90%: {CURRENCY}{week_total:.2f} / {CURRENCY}{weekly_limit:.2f}")
            elif weekly_percentage >= 75:
                warnings.append(f"⚡ Weekly limit at 75%: {CURRENCY}{week_total:.2f} / {CURRENCY}{weekly_limit:.2f}")
        
        # Check monthly limit
        if monthly_limit:
            monthly_percentage = (month_total / monthly_limit) * 100
            if monthly_percentage >= 100:
                warnings.append(f"🔴 Monthly limit EXCEEDED: {CURRENCY}{month_total:.2f} / {CURRENCY}{monthly_limit:.2f}")
            elif monthly_percentage >= 90:
                warnings.append(f"⚠️ Monthly limit at 90%: {CURRENCY}{month_total:.2f} / {CURRENCY}{monthly_limit:.2f}")
            elif monthly_percentage >= 75:
                warnings.append(f"⚡ Monthly limit at 75%: {CURRENCY}{month_total:.2f} / {CURRENCY}{monthly_limit:.2f}")
        
        # Send warning if any
        if warnings:
            warning_text = "*Budget Alert:*\n" + "\n".join(warnings)
            await update.message.reply_text(warning_text, parse_mode='Markdown')


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo uploads for receipt processing."""

    if not update.message.photo:
        return

    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    try:
        await file.download_to_drive("temp_receipt.jpg")

        analysis = None
        ocr_text = None
        gemini_issue = None

        def _gemini_issue_note(issue):
            if not isinstance(issue, dict):
                return None

            code = issue.get("code")
            retry_after = issue.get("retry_after_seconds")

            if code in ("quota_exceeded", "quota_cooldown"):
                if retry_after:
                    return f"Note: Gemini unavailable (quota/rate limit). OCR fallback used. Retry in ~{int(retry_after)}s."
                return "Note: Gemini unavailable (quota/rate limit). OCR fallback used."
            if code == "auth_or_permission_error":
                return "Note: Gemini API key/permission issue detected. OCR fallback used."
            if code == "not_initialized":
                return "Note: Gemini not initialized. Check GEMINI_API_KEY and billing/quota."
            if issue.get("error"):
                return "Note: Gemini request failed. OCR fallback used."
            return None

        # Primary path: Gemini image analysis
        if gemini:
            gemini_result = gemini.analyze_receipt("temp_receipt.jpg")
            if gemini_result and not gemini_result.get("error"):
                analysis = gemini_result
                logger.info("Gemini receipt analysis successful")
            else:
                gemini_issue = gemini_result if isinstance(gemini_result, dict) else {"error": str(gemini_result)}
                retry_after = gemini_issue.get("retry_after_seconds") if isinstance(gemini_issue, dict) else None
                if retry_after:
                    logger.warning(
                        "Gemini unavailable (quota/rate limit). OCR fallback active for %ss.",
                        retry_after,
                    )
                else:
                    logger.warning("Gemini failed, switching to OCR fallback.")
                analysis = None

        # Fallback path: OCR + parser analysis (priority: EasyOCR -> Tesseract)
        if not analysis:
            if not ocr_text:
                _, ocr_text = _run_easyocr_receipt("temp_receipt.jpg")

            if not ocr_text:
                _, ocr_text = _run_tesseract_receipt("temp_receipt.jpg")

            if ocr_text:
                analysis = parser.analyze_receipt(ocr_text)

        if not analysis and not ocr_text:
            extra_hint = ""
            issue_note = _gemini_issue_note(gemini_issue)
            if issue_note:
                extra_hint = f"\n\n{issue_note}"
            await update.message.reply_text(
                "Could not extract text from image.\n\n"
                "Try:\n"
                "- Upload a clearer image\n"
                "- Ensure good lighting\n"
                "- Or type: 'Spent 500 for food'"
                f"{extra_hint}"
            )
            return

        if not analysis:
            analysis = {}

        def _safe_float(value):
            try:
                if value is None:
                    return None
                amount = float(value)
                return amount if amount > 0 else None
            except (TypeError, ValueError):
                return None

        bill_totals = parser.extract_bill_totals(ocr_text) if ocr_text else {
            "subtotal": None,
            "total": None,
            "grand_total": None,
        }

        subtotal = bill_totals.get("subtotal") or _safe_float(analysis.get("subtotal"))
        total = bill_totals.get("total") or _safe_float(analysis.get("total"))
        grand_total = bill_totals.get("grand_total") or _safe_float(analysis.get("grand_total"))

        amount_value = _safe_float(analysis.get("amount"))
        if not amount_value and ocr_text:
            parsed_amount, _, _ = parser.parse_expense(ocr_text)
            amount_value = _safe_float(parsed_amount)

        chosen_amount = None
        chosen_label = None

        if grand_total:
            chosen_amount = grand_total
            chosen_label = "Bill Grand Total"
        elif total:
            chosen_amount = total
            chosen_label = "Bill Total"
        elif subtotal:
            chosen_amount = subtotal
            chosen_label = "Bill Subtotal"
        elif amount_value:
            chosen_amount = amount_value
            chosen_label = "Bill Amount"

        if not chosen_amount:
            await update.message.reply_text(
                "Could not find total amount in receipt.\n\n"
                "Please manually enter: 'Spent [amount] for [category]'\n"
                "Example: 'Spent 500 for food'"
            )
            return

        parsed_items = []
        category_values = []
        for item in (analysis.get("items") or []):
            if not isinstance(item, dict):
                continue

            item_name = (item.get("name") or "").strip() or "Receipt Item"
            item_category = (item.get("category") or "").strip()
            if not item_category or item_category == "Other":
                inferred_item_category = parser._extract_category(item_name.lower())
                item_category = inferred_item_category if inferred_item_category else "Other"

            quantity_value = _safe_float(item.get("quantity"))
            unit_price = _safe_float(item.get("unit_price") or item.get("price"))
            item_amount = _safe_float(item.get("total_price") or item.get("amount"))

            if item_amount is None and quantity_value and unit_price:
                item_amount = round(quantity_value * unit_price, 2)
            if item_amount is None and unit_price:
                item_amount = unit_price

            if item_amount is None:
                continue

            if item_category != "Other" and item_category not in category_values:
                category_values.append(item_category)

            parsed_items.append({
                "amount": item_amount,
                "category": item_category,
                "description": item_name,
            })

        if not category_values and ocr_text:
            inferred_category = parser._extract_category(ocr_text.lower())
            if inferred_category and inferred_category != "Other":
                category_values.append(inferred_category)
        bill_category = ", ".join(category_values) if category_values else "Other"

        bill_ref = f"BILL-{user.id}-{int(time.time() * 1000)}"
        saved_item_count = 0

        for item_entry in parsed_items:
            db.add_expense(
                user.id,
                item_entry["amount"],
                item_entry["category"],
                item_entry["description"],
                source="image",
                transaction_id=bill_ref,
                payment_method="receipt",
            )
            saved_item_count += 1

        if saved_item_count == 0:
            fallback_label = chosen_label if chosen_label else "Amount"
            db.add_expense(
                user.id,
                chosen_amount,
                bill_category,
                f"Receipt Total ({fallback_label})",
                source="image",
                transaction_id=bill_ref,
                payment_method="receipt",
            )
            saved_item_count = 1

        bill_entries = []
        if subtotal:
            bill_entries.append(("Bill Subtotal", subtotal))
        if total:
            bill_entries.append(("Bill Total", total))
        if grand_total:
            bill_entries.append(("Bill Grand Total", grand_total))
        bill_entries.append(("Bill Amount", chosen_amount))

        unique_entries = []
        seen = set()
        for label, value in bill_entries:
            key = (label, round(float(value), 2))
            if key in seen:
                continue
            seen.add(key)
            unique_entries.append((label, value))

        for label, value in unique_entries:
            db.add_expense(
                user.id,
                value,
                bill_category,
                label,
                source="image",
                transaction_id=bill_ref,
                payment_method="receipt",
            )

        lines = [
            "Bill analysis:",
            f"Category: {bill_category}",
            f"Total: {CURRENCY}{total:.2f}" if total else "Total: N/A",
            f"Items Saved: {saved_item_count}",
        ]
        await update.message.reply_text("\n".join(lines))

    except Exception as e:
        logger.error("Error processing receipt: %s", str(e))
        await update.message.reply_text(
            f"Error processing receipt: {str(e)}\n"
            f"Please try again or manually enter the amount."
        )
    finally:
        # Clean up temp file even on early returns.
        import os
        if os.path.exists("temp_receipt.jpg"):
            os.remove("temp_receipt.jpg")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages for bill tracking"""
    
    if not update.message.voice:
        return
    
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    await update.message.reply_text("🎤 Processing voice message...")
    
    try:
        # Get the voice file
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        
        # Download voice file
        await file.download_to_drive("temp_voice.ogg")
        
        # Convert to text using speech recognition
        from nlp_processor import VoiceProcessor
        voice_processor = VoiceProcessor()
        text = voice_processor.transcribe_voice("temp_voice.ogg")
        
        if not text:
            await update.message.reply_text(
                "Couldn't process voice message.\n\n"
                "1) **OGG conversion needs ffmpeg** – install and add to PATH:\n"
                "   https://ffmpeg.org (or: choco install ffmpeg)\n\n"
                "2) Internet required for Google Speech API.\n"
                "3) Speak clearly; or type: 'Spent 150 for food'"
            )
            return
        
        # Parse the transcribed text
        amount, category, description = parser.parse_expense(text)
        description = parser.normalize_description_for_voice(description, category)
        
        if not amount:
            await update.message.reply_text(
                f"📝 Transcribed: {text}\n\n"
                "❌ Couldn't extract amount. Please try saying:\n"
                "• 'Spent 150 for biriyani'\n"
                "• '50 on transport'\n"
                "• '200 for movie'"
            )
            return
        
        # Store expense
        db.add_expense(user.id, amount, category, description, source="voice")
        
        confirmation = (
            f"✅ **Voice Bill Recorded!**\n\n"
            f"🎤 Transcribed: {text}\n"
            f"💰 Amount: {CURRENCY}{amount:.2f}\n"
            f"🏷️ Category: {category}\n"
            f"📝 Description: {description}\n\n"
            f"Use /summary to see your spending!"
        )
        
        await update.message.reply_text(confirmation, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error processing voice: {str(e)}")
        await update.message.reply_text(
            f"❌ Error processing voice: {str(e)}\n"
            f"Please try again or manually enter the amount."
        )
    finally:
        # Clean up temp file even on early returns.
        import os
        if os.path.exists("temp_voice.ogg"):
            os.remove("temp_voice.ogg")


def _extract_ocr_text(result):
    """Extract best available OCR text from parser output."""
    if not isinstance(result, dict):
        return ""

    for key in ("raw_text", "text", "description"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _gemini_result_to_text(gemini_result):
    """Convert Gemini structured analysis into searchable text lines."""
    if not isinstance(gemini_result, dict):
        return ""

    text_parts = []
    key_map = {
        "image_type": "Image Type",
        "merchant": "Merchant",
        "date": "Date",
        "transaction_time": "Date/Time",
        "amount": "Amount",
        "subtotal": "Subtotal",
        "total": "Total",
        "grand_total": "Grand Total",
        "final_amount": "Final Amount",
        "upi_to": "To",
        "upi_from": "From",
        "upi_transaction_id": "UPI transaction ID",
    }
    for key in (
        "image_type",
        "merchant",
        "date",
        "transaction_time",
        "amount",
        "subtotal",
        "total",
        "grand_total",
        "final_amount",
        "upi_to",
        "upi_from",
        "upi_transaction_id",
    ):
        value = gemini_result.get(key)
        if value is not None and str(value).strip():
            text_parts.append(f"{key_map.get(key, key)}: {value}")

    for item in (gemini_result.get("items") or []):
        if not isinstance(item, dict):
            continue
        item_name = (item.get("name") or "").strip()
        item_total = item.get("total_price") or item.get("amount")
        if not item_name:
            continue
        text_parts.append(f"{item_name} {item_total}" if item_total else item_name)

    return "\n".join(text_parts).strip()


def _run_easyocr_receipt(image_path):
    """Run EasyOCR receipt parser and return (result, text)."""
    try:
        from nlp_processor import EasyOCRProcessor
        ocr = EasyOCRProcessor()
        result = ocr.parse_receipt(image_path)
        text = _extract_ocr_text(result)
        if text:
            logger.info("EasyOCR successful")
        return result, text
    except Exception as easyocr_error:
        logger.warning("EasyOCR failed: %s", easyocr_error)
        return None, ""


def _run_tesseract_receipt(image_path):
    """Run Tesseract OCR fallback and return (result, text)."""
    try:
        import pytesseract
        from PIL import Image

        with Image.open(image_path) as image:
            text = (pytesseract.image_to_string(image) or "").strip()

        if not text:
            return None, ""

        amount, category, description = parser.parse_expense(text)
        result = {
            "amount": amount,
            "category": category,
            "description": description or text[:120],
            "raw_text": text,
            "source": "tesseract",
        }
        logger.info("Tesseract successful")
        return result, text
    except Exception as tesseract_error:
        logger.warning("Tesseract failed: %s", tesseract_error)
        return None, ""


def _classify_image_kind(caption, ocr_text):
    """
    Classify uploaded image as:
    - 'upi' for payment screenshots
    - 'receipt' for bill receipts (default fallback)
    """
    combined = f"{caption or ''}\n{ocr_text or ''}".lower()

    upi_keywords = [
        "upi",
        "transaction id",
        "upi transaction id",
        "utr",
        "google pay",
        "gpay",
        "phonepe",
        "paytm",
        "completed",
        "paid to",
        "sent to",
        "from:",
        "to:",
    ]
    receipt_keywords = [
        "invoice",
        "receipt",
        "subtotal",
        "grand total",
        "tax",
        "gst",
        "qty",
        "quantity",
        "item",
        "bill no",
    ]

    upi_score = sum(1 for token in upi_keywords if token in combined)
    receipt_score = sum(1 for token in receipt_keywords if token in combined)

    strong_upi_tokens = ("upi", "transaction id", "google pay", "gpay", "phonepe", "paytm", "utr")
    if any(token in combined for token in strong_upi_tokens):
        return "upi"

    if upi_score >= 2 and upi_score >= receipt_score:
        return "upi"
    if receipt_score >= 2 and receipt_score > upi_score:
        return "receipt"
    return "receipt"


def _clean_upi_party(value):
    """Normalize extracted payer/payee names."""
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" :-|")
    cleaned = re.sub(r"\s*\(.*?\)\s*$", "", cleaned).strip()
    return cleaned or None


def _extract_upi_amount(text):
    """Extract transaction amount from UPI screenshot OCR text."""
    if not text:
        return None

    normalized = text.replace(",", "")

    label_patterns = [
        r"(?:amount|paid|sent|debited|received)\s*[:\-]?\s*[^0-9]{0,6}\s*([0-9]+(?:\.[0-9]{1,2})?)",
        r"(?:\u20B9|rs\.?|inr)\s*([0-9]+(?:\.[0-9]{1,2})?)",
    ]
    for pattern in label_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            try:
                value = float(match.group(1))
                if value > 0:
                    return value
            except (ValueError, TypeError):
                continue

    # Fallback: detect isolated amount line like "100" or "₹100".
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        line_match = re.fullmatch(
            r"(?:[^\dA-Za-z]{0,3}\s*)?([0-9]+(?:\.[0-9]{1,2})?)",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not line_match:
            continue
        try:
            value = float(line_match.group(1))
            if 0 < value < 100000:
                return value
        except (TypeError, ValueError):
            continue

    return None


def _extract_upi_datetime(text):
    """Extract transaction date/time as text from OCR."""
    if not text:
        return None

    patterns = [
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4},?\s+\d{1,2}:\d{2}\s*(?:am|pm)?\b",
        r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}[, ]+\d{1,2}:\d{2}\s*(?:am|pm)?\b",
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return None


def _has_time_component(value):
    """Return True if value contains a clock time like HH:MM."""
    if not value:
        return False
    return bool(re.search(r"\b\d{1,2}:\d{2}\b", str(value)))


def _extract_upi_transaction_id(text):
    """Extract UPI transaction ID/UTR from OCR text."""
    if not text:
        return None

    patterns = [
        r"(?:upi\s*transaction\s*id|transaction\s*id|txn\s*id|utr(?:\s*number)?)\s*[:#-]?\s*([A-Za-z0-9\-]{8,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_upi_party(text, field_name):
    """Extract To/From party from OCR text."""
    if not text:
        return None

    key = "to" if field_name == "to" else "from"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        match = re.match(rf"^{key}\s*[:\-]\s*(.+)$", line, flags=re.IGNORECASE)
        if match:
            return _clean_upi_party(match.group(1))

    if key == "to":
        match = re.search(r"(?:^|\n)\s*to\s+([A-Za-z][A-Za-z0-9 .]{2,80})", text, flags=re.IGNORECASE)
        if match:
            return _clean_upi_party(match.group(1))

    if key == "from":
        match = re.search(r"(?:^|\n)\s*from\s+([A-Za-z][A-Za-z0-9 .]{2,80})", text, flags=re.IGNORECASE)
        if match:
            return _clean_upi_party(match.group(1))

    return None


def _extract_upi_details(ocr_text, caption):
    """Extract structured UPI screenshot fields."""
    text = f"{ocr_text or ''}\n{caption or ''}".strip()
    return {
        "to": _extract_upi_party(text, "to"),
        "from": _extract_upi_party(text, "from"),
        "amount": _extract_upi_amount(text),
        "date_time": _extract_upi_datetime(text),
        "upi_transaction_id": _extract_upi_transaction_id(text),
    }


def _extract_upi_details_from_gemini(gemini_result):
    """Extract UPI detail fields from Gemini structured output."""
    if not isinstance(gemini_result, dict):
        return {
            "to": None,
            "from": None,
            "amount": None,
            "date_time": None,
            "upi_transaction_id": None,
        }

    def _to_float(value):
        try:
            if value is None:
                return None
            amount = float(value)
            return amount if amount > 0 else None
        except (TypeError, ValueError):
            return None

    amount = (
        _to_float(gemini_result.get("amount"))
        or _to_float(gemini_result.get("final_amount"))
        or _to_float(gemini_result.get("grand_total"))
        or _to_float(gemini_result.get("total"))
        or _to_float(gemini_result.get("subtotal"))
    )

    return {
        "to": _clean_upi_party(gemini_result.get("upi_to")),
        "from": _clean_upi_party(gemini_result.get("upi_from")),
        "amount": amount,
        "date_time": (gemini_result.get("transaction_time") or gemini_result.get("date") or "").strip() or None,
        "upi_transaction_id": (gemini_result.get("upi_transaction_id") or "").strip() or None,
    }


async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle screenshots by auto-classifying receipt vs UPI payment image."""
    if not update.message.photo:
        return

    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    await update.message.reply_text("Image received. Processing...")

    caption = update.message.caption or ""
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    try:
        await file.download_to_drive("temp_payment.jpg")

        result = None
        ocr_text = ""
        image_kind = "receipt"
        gemini_upi_details = {
            "to": None,
            "from": None,
            "amount": None,
            "date_time": None,
            "upi_transaction_id": None,
        }

        # Analyzer priority: Gemini -> EasyOCR -> Tesseract
        if gemini:
            try:
                gemini_result = gemini.analyze_receipt("temp_payment.jpg")
                if gemini_result and not gemini_result.get("error"):
                    result = gemini_result
                    gemini_upi_details = _extract_upi_details_from_gemini(gemini_result)
                    ocr_text = _gemini_result_to_text(gemini_result)
                    image_type = str(gemini_result.get("image_type") or "").strip().lower()
                    if "upi" in image_type or "payment" in image_type:
                        image_kind = "upi"
                    elif image_type in {"receipt", "bill", "invoice"}:
                        image_kind = "receipt"
                    else:
                        image_kind = _classify_image_kind(caption, ocr_text)
                    logger.info("Gemini screenshot analysis successful")
                else:
                    logger.warning("Gemini screenshot analysis failed, falling back to OCR")
            except Exception as gemini_error:
                logger.warning("Gemini screenshot analysis exception: %s", gemini_error)

        # If Gemini already identifies this as a receipt, use receipt flow directly.
        # This keeps Gemini as the primary analyzer for bill receipts.
        if image_kind == "receipt":
            gemini_upi_probe = _extract_upi_details(ocr_text, caption)
            combined_probe = f"{caption or ''}\n{ocr_text or ''}".lower()
            gemini_has_upi_signals = bool(
                gemini_upi_probe.get("upi_transaction_id")
                or (gemini_upi_probe.get("to") and gemini_upi_probe.get("from"))
                or ("upi" in combined_probe and gemini_upi_probe.get("amount"))
                or ("transaction id" in combined_probe and gemini_upi_probe.get("amount"))
                or ("google pay" in combined_probe and gemini_upi_probe.get("amount"))
                or ("gpay" in combined_probe and gemini_upi_probe.get("amount"))
            )
            if not gemini_has_upi_signals:
                await handle_photo(update, context)
                return

        # OCR fallback only when Gemini did not produce a clear UPI/receipt decision.
        if image_kind != "upi":
            easy_result, easy_text = _run_easyocr_receipt("temp_payment.jpg")
            if easy_text:
                result = easy_result
                ocr_text = easy_text
                image_kind = _classify_image_kind(caption, ocr_text)

        if image_kind != "upi":
            tess_result, tess_text = _run_tesseract_receipt("temp_payment.jpg")
            if tess_text:
                result = tess_result
                ocr_text = tess_text
                image_kind = _classify_image_kind(caption, ocr_text)

        upi_details = _extract_upi_details(ocr_text, caption)
        # Prefer Gemini fields when available; fill remaining fields from OCR text.
        for key in ("to", "from", "date_time", "upi_transaction_id"):
            if not upi_details.get(key) and gemini_upi_details.get(key):
                upi_details[key] = gemini_upi_details[key]
        if gemini_upi_details.get("amount"):
            upi_details["amount"] = gemini_upi_details["amount"]

        # If date exists without time, try one OCR pass to enrich transaction time.
        if not _has_time_component(upi_details.get("date_time")):
            easy_result_dt, easy_text_dt = _run_easyocr_receipt("temp_payment.jpg")
            if easy_text_dt:
                maybe_dt = _extract_upi_datetime(easy_text_dt)
                if _has_time_component(maybe_dt):
                    upi_details["date_time"] = maybe_dt
                # Backfill missing UPI id and parties from OCR text if needed.
                if not upi_details.get("upi_transaction_id"):
                    upi_details["upi_transaction_id"] = _extract_upi_transaction_id(easy_text_dt)
                if not upi_details.get("to"):
                    upi_details["to"] = _extract_upi_party(easy_text_dt, "to")
                if not upi_details.get("from"):
                    upi_details["from"] = _extract_upi_party(easy_text_dt, "from")
                if not upi_details.get("amount") and isinstance(easy_result_dt, dict):
                    try:
                        amt = easy_result_dt.get("amount")
                        upi_details["amount"] = float(amt) if amt else upi_details.get("amount")
                    except (TypeError, ValueError):
                        pass

        # Guard against false "receipt" classification for real UPI screenshots.
        combined_for_signal = f"{caption or ''}\n{ocr_text or ''}".lower()
        has_upi_signals = bool(
            upi_details.get("upi_transaction_id")
            or (upi_details.get("to") and upi_details.get("from"))
            or ("upi" in combined_for_signal and upi_details.get("amount"))
            or ("transaction id" in combined_for_signal and upi_details.get("amount"))
            or ("google pay" in combined_for_signal and upi_details.get("amount"))
            or ("gpay" in combined_for_signal and upi_details.get("amount"))
        )

        if image_kind == "receipt" and not has_upi_signals:
            await handle_photo(update, context)
            return

        amount = upi_details.get("amount")

        if not amount and isinstance(result, dict):
            result_amount = result.get("amount")
            try:
                amount = float(result_amount) if result_amount else None
            except (TypeError, ValueError):
                amount = None

        if not amount and ocr_text:
            parsed_amount, _, _ = parser.parse_expense(ocr_text)
            amount = parsed_amount

        if not amount:
            await update.message.reply_text(
                "Could not extract UPI amount from screenshot.\n"
                "Please upload a clearer screenshot or type amount manually."
            )
            return

        to_value = upi_details.get("to")
        from_value = upi_details.get("from")
        txn_time = upi_details.get("date_time")
        upi_txn_id = upi_details.get("upi_transaction_id")

        description = "UPI payment"
        if to_value:
            description = f"UPI payment to {to_value}"

        db.add_expense(
            user.id,
            float(amount),
            "Other",
            description,
            source="online_payment",
            transaction_id=upi_txn_id,
            account_name=from_value,
            payment_method="upi",
            upi_to=to_value,
            upi_from=from_value,
            transaction_time=txn_time,
        )

        response_lines = [
            "✅ **UPI Screenshot Processed!**",
            "",
            f"💰 Amount: {CURRENCY}{float(amount):.2f}",
        ]
        if to_value:
            response_lines.append(f"👤 To: {to_value}")
        if from_value:
            response_lines.append(f"👤 From: {from_value}")
        if txn_time:
            response_lines.append(f"🕒 Date/Time: {txn_time}")
        if upi_txn_id:
            response_lines.append(f"🔑 UPI Transaction ID: `{upi_txn_id}`")
        response_lines.append("")
        response_lines.append("Saved to database and will appear in Excel UPI Details sheet.")

        await update.message.reply_text("\n".join(response_lines), parse_mode='Markdown')

    except Exception as e:
        logger.error("Error processing payment screenshot: %s", str(e))
        await update.message.reply_text(
            f"❌ Error processing screenshot: {str(e)}\n"
            "Please try again with a clearer image or manually enter the details."
        )

    finally:
        # Clean up temp file regardless of branch/return.
        import os
        if os.path.exists("temp_payment.jpg"):
            os.remove("temp_payment.jpg")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)


def main():
    """Start the bot"""
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("summary", summary))
    application.add_handler(CommandHandler("weekly", weekly_summary))
    application.add_handler(CommandHandler("monthly", monthly_summary))
    application.add_handler(CommandHandler("today", today_total))
    application.add_handler(CommandHandler("categories", show_categories))
    application.add_handler(CommandHandler("list", list_expenses))
    application.add_handler(CommandHandler("delete", delete_expense))
    application.add_handler(CommandHandler("stats", statistics))
    
    # Export commands
    application.add_handler(CommandHandler("export", export_all))
    application.add_handler(CommandHandler(["export_monthly", "exportmonthly"], export_monthly))
    application.add_handler(CommandHandler(["export_weekly", "exportweekly"], export_weekly))
    application.add_handler(CommandHandler(["export_today", "exporttoday"], export_today_data))
    application.add_handler(CommandHandler(["exportrange", "export_range"], export_date_range))
    application.add_handler(CommandHandler(["export_csv", "exportcsv"], export_csv))
    application.add_handler(CommandHandler("pdf", export_pdf))
    application.add_handler(CommandHandler("graph", export_graph))
    
    # Budget limit commands
    application.add_handler(CommandHandler(["setdaily", "set_daily"], set_daily_limit))
    application.add_handler(CommandHandler(["setweekly", "set_weekly"], set_weekly_limit))
    application.add_handler(CommandHandler(["setmonthly", "set_monthly"], set_monthly_limit))
    application.add_handler(CommandHandler(["limits", "limit"], check_limits))
    
    # Report commands
    application.add_handler(CommandHandler("week", report_week))
    application.add_handler(CommandHandler("month", report_month))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start polling
    logger.info("Bot started polling...")
    print("[*] Expense Tracker Bot is running!")
    print("[*] Press Ctrl+C to stop.")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

