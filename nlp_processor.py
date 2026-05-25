"""
Alternative NLP and extraction methods
Uses EasyOCR (no system software needed) instead of Tesseract
Uses Google Speech API (already working)
"""
import re
import logging
from config import EXPENSE_PATTERNS, EXPENSE_CATEGORIES

logger = logging.getLogger(__name__)

class ExpenseParser:
    """Reuse existing parser (same as original)"""
    def __init__(self):
        self.amount_pattern = r'(\d+(?:[.,]\d{2})?)'
        self.currency_symbols = ['₹', '$', '€', '£', 'rs', 'rupees', 'dollars']
    
    def parse_expense(self, text):
        """
        Parse expense from receipt or text
        Priority: Explicit fields (amount:, category:) → Money symbols → Keywords
        Returns: (amount, category, description)
        """
        text_str = text or ""
        
        # STEP 1: Extract explicit "category:" field from receipt
        category = self._extract_explicit_category(text_str)
        
        # STEP 2: Extract amount using smart logic
        amount = self._extract_amount(text_str)
        if not amount:
            return None, None, None

        # STEP 3: Build description - clean full text
        description = text_str
        # Remove amount tokens with optional currency words/symbols around them
        amt_pattern = r"(?:[$€£₹]|rs\.?|rupees?|inr|usd|dollars?)?\s*\d+(?:[.,]\d{1,2})?\s*(?:[$€£₹]|rs\.?|rupees?|inr|usd|dollars?)?"
        description = re.sub(amt_pattern, "", description, flags=re.IGNORECASE, count=1)
        # Remove explicit field labels (amount: 100, category: food, etc)
        description = re.sub(r'(?:amount|category|total|cost|price)\s*:?\s*[^\n]*', '', description, flags=re.IGNORECASE)
        # Remove leftover standalone currency words/symbols
        description = re.sub(r'[$€£₹]', ' ', description)
        description = re.sub(r'\b(?:rs\.?|rupees?|inr|usd|dollars?)\b', ' ', description, flags=re.IGNORECASE)
        # Collapse whitespace and strip
        description = re.sub(r"\s{2,}", " ", description).strip()
        description = description.strip(" -:;,.\n\t")

        # Fallback: if description is empty or too short, use original text
        if not description or len(description) < 3:
            description = text_str.strip()

        # If still no category from explicit field, extract from description/keywords
        if not category or category == "Other":
            category = self._extract_category(description.lower())

        return amount, category, description

    def is_valid_expense(self, amount, category):
        """Validate parsed expense fields."""
        try:
            value = float(amount)
        except (TypeError, ValueError):
            return False

        if value <= 0 or value >= 1000000:
            return False

        if not category:
            return False

        category_lower = str(category).strip().lower()
        allowed = {name.lower() for name in EXPENSE_CATEGORIES}
        return category_lower in allowed

    def parse_multiple_expenses(self, text):
        """
        Parse multiple expense items from multiline input.
        Returns a list of tuples: (amount, category, description)
        """
        text = (text or "").strip()
        if not text:
            return []

        expenses = []
        item_blocks = []

        # Strong separators used in many OCR/manual lists.
        if "---" in text or "===" in text:
            blocks = re.split(r'---+|===+', text)
            item_blocks = [block.strip() for block in blocks if block.strip()]
        else:
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            lines_with_numbers = sum(1 for line in lines if re.search(r'\d', line))

            # Common case: one expense per line.
            if lines_with_numbers >= 2 and len(lines) >= 2:
                item_blocks = lines
            else:
                item_blocks = [text]

        for block in item_blocks:
            amount, category, description = self.parse_expense(block)
            if not category:
                category = "Other"
            if self.is_valid_expense(amount, category):
                expenses.append((amount, category, description or block))

        return expenses

    def extract_bill_totals(self, text):
        """
        Extract subtotal/total/grand_total values from receipt text.
        Returns dict: {"subtotal": float|None, "total": float|None, "grand_total": float|None}
        """
        text = text or ""
        totals = {
            "subtotal": None,
            "total": None,
            "grand_total": None,
        }

        if not text.strip():
            return totals

        def _line_amount(line):
            numbers = re.findall(r'(\d+(?:[.,]\d{1,2})?)', line)
            if not numbers:
                return None
            # Right-most value is usually the payable value in receipts.
            return self._parse_amount_string(numbers[-1])

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            lowered = line.lower()
            amount = _line_amount(line)
            if amount is None:
                continue

            if "grand total" in lowered:
                totals["grand_total"] = amount
            elif "subtotal" in lowered or "sub total" in lowered:
                totals["subtotal"] = amount
            elif re.search(r'\btotal\b', lowered) and "sub" not in lowered and "grand" not in lowered:
                totals["total"] = amount

        return totals

    def extract_simple_receipt(self, receipt_text):
        """
        Lightweight receipt extraction used by helper scripts.
        Returns: dict with final_amount/category + key totals.
        """
        text = (receipt_text or "").strip()
        result = {
            "category": "Other",
            "final_amount": None,
            "subtotal": None,
            "total": None,
            "grand_total": None,
            "items": [],
            "raw_text": text,
        }

        if not text:
            return result

        def _to_float(value):
            try:
                if value is None:
                    return None
                parsed = float(value)
                return parsed if parsed > 0 else None
            except (TypeError, ValueError):
                return None

        analysis = self.analyze_receipt(text)
        if isinstance(analysis, dict):
            result["items"] = analysis.get("items") or []

        bill_totals = self.extract_bill_totals(text)
        subtotal = _to_float(bill_totals.get("subtotal"))
        total = _to_float(bill_totals.get("total"))
        grand_total = _to_float(bill_totals.get("grand_total"))

        if isinstance(analysis, dict):
            subtotal = subtotal or _to_float(analysis.get("subtotal"))
            total = total or _to_float(analysis.get("total"))
            grand_total = grand_total or _to_float(analysis.get("grand_total"))

        parsed_amount = None
        if isinstance(analysis, dict):
            parsed_amount = _to_float(analysis.get("final_amount") or analysis.get("amount"))
        if not parsed_amount:
            amount, _, _ = self.parse_expense(text)
            parsed_amount = _to_float(amount)

        final_amount = grand_total or total or parsed_amount or subtotal

        item_categories = []
        for item in result["items"]:
            if not isinstance(item, dict):
                continue
            category = (item.get("category") or "").strip()
            if category and category != "Other":
                item_categories.append(category)

        if item_categories:
            result["category"] = item_categories[0]
        else:
            inferred = self._extract_category(text.lower())
            result["category"] = inferred if inferred else "Other"

        result["subtotal"] = subtotal
        result["total"] = total
        result["grand_total"] = grand_total
        result["final_amount"] = final_amount
        return result

    def format_receipt_plain_text(self, analysis):
        """
        Convert structured receipt analysis dict into plain readable text.
        """
        if not isinstance(analysis, dict):
            return "No receipt analysis data available."

        def _fmt_amount(value):
            try:
                if value is None:
                    return None
                return f"{float(value):.2f}"
            except (TypeError, ValueError):
                return None

        lines = ["Food Items:"]
        items = analysis.get("items") or []
        rendered_items = 0

        for item in items:
            if not isinstance(item, dict):
                continue
            name = (item.get("name") or "").strip()
            if not name:
                continue
            price = (
                item.get("total_price")
                if item.get("total_price") is not None
                else item.get("amount")
            )
            if price is None:
                price = item.get("unit_price")
            amount_text = _fmt_amount(price)
            if amount_text:
                lines.append(f"{rendered_items + 1}. {name} - {amount_text}")
            else:
                lines.append(f"{rendered_items + 1}. {name}")
            rendered_items += 1

        if rendered_items == 0:
            lines.append("No line items detected")

        subtotal = _fmt_amount(analysis.get("subtotal"))
        if subtotal:
            lines.append(f"Subtotal: {subtotal}")

        tax_value = analysis.get("tax")
        if isinstance(tax_value, dict):
            gst = _fmt_amount(tax_value.get("gst"))
            other_tax = _fmt_amount(tax_value.get("other"))
            if gst:
                lines.append(f"Tax: {gst}")
            elif other_tax:
                lines.append(f"Tax: {other_tax}")
        else:
            tax = _fmt_amount(tax_value)
            if tax:
                lines.append(f"Tax: {tax}")

        final_amount = _fmt_amount(
            analysis.get("final_amount")
            or analysis.get("grand_total")
            or analysis.get("total")
        )
        if final_amount:
            lines.append(f"Total Amount: {final_amount}")
        else:
            lines.append("Total Amount: N/A")

        category = analysis.get("category")
        if not category:
            category = self._extract_category("\n".join(lines).lower())
        lines.append(f"Category: {category or 'Other'}")
        return "\n".join(lines)

    def _extract_pattern_keyword(self, text_lower, category=None):
        """Return matched keyword from EXPENSE_PATTERNS, preferring the given category."""
        if not text_lower:
            return None

        category_order = []
        category_lower = (category or "").strip().lower()
        if category_lower in EXPENSE_PATTERNS:
            category_order.append(category_lower)

        for cat in EXPENSE_PATTERNS:
            if cat not in category_order:
                category_order.append(cat)

        for cat in category_order:
            keywords = sorted(EXPENSE_PATTERNS.get(cat, []), key=len, reverse=True)
            for keyword in keywords:
                pattern = rf"\b{re.escape(keyword.lower())}\b"
                if re.search(pattern, text_lower):
                    return keyword.lower()

        return None

    def normalize_description_for_voice(self, description, category=None):
        """Normalize voice descriptions for storage/export. Example: 'coffee rs' -> 'coffee'."""
        text = (description or "").lower()
        text = re.sub(r'[$€£₹]', ' ', text)
        text = re.sub(r'\b(?:rs\.?|rupees?|inr|usd|dollars?)\b', ' ', text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:spent|spend|paid|pay|for|on|at|expense|bill|cost|price|amount)\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"[^a-z\s]", " ", text)
        text = re.sub(r"\s{2,}", " ", text).strip()

        keyword = self._extract_pattern_keyword(text, category)
        if keyword:
            return keyword

        if text:
            return text

        if category and category != "Other":
            return category.lower()

        return (description or "").strip()
    
    def _extract_explicit_category(self, text):
        """Extract category from explicit 'category:' field in receipt"""
        # Pattern: "category: biryani" or "category : biryani" or "category:biryani"
        pattern = r'category\s*:?\s*([^\n:,]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            category_text = match.group(1).lower().strip()
            
            # First, try direct match against category names
            for cat_name in EXPENSE_CATEGORIES:
                if category_text == cat_name.lower():
                    return cat_name
            
            # Second, try keyword matching in EXPENSE_PATTERNS
            for category, keywords in EXPENSE_PATTERNS.items():
                for keyword in keywords:
                    if keyword.lower() == category_text or keyword.lower() in category_text:
                        # Map pattern key to category name
                        for cat_name in EXPENSE_CATEGORIES:
                            if cat_name.lower() == category.lower():
                                return cat_name
        
        return None

    def _extract_amount(self, text):
        """Extract amount from text - prioritizes 'amount:' field, then money symbols"""
        text_lower = text.lower()
        
        # HIGHEST PRIORITY: Look for explicit "amount:" field in receipt
        # Pattern: "amount : 100" or "amount: 100" or "amount 100"
        amount_pattern = r'amount\s*:?\s*([₹\$\€\£])?\s*(\d+(?:[.,]\d{2})?)'
        match = re.search(amount_pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(2) if match.group(2) else match.group(1)
            amount = self._parse_amount_string(amount_str)
            if amount:
                return amount
        
        # PRIORITY 2: Look for "total" or "grand total" fields (common in receipts)
        total_keywords = ['total', 'grand total', 'final amount', 'amount due', 'total amount', 'total cost']
        for keyword in total_keywords:
            pattern = rf'{keyword}\s*:?\s*([₹\$\€\£])?\s*(\d+(?:[.,]\d{{2}}))'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(2) if match.group(2) else match.group(1)
                amount = self._parse_amount_string(amount_str)
                if amount:
                    return amount
        
        # PRIORITY 3: Look for money symbols (₹, $, €, £, Rs, rupees, dollars)
        has_currency = bool(re.search(r'[₹\$\€\£]|Rs\.|Rs |rupee|rupees|dollar', text, re.IGNORECASE))
        
        if has_currency:
            # RECEIPT MODE: Extract from lines with currency
            money_lines = []
            lines = text.split('\n')
            
            for line in lines:
                if re.search(r'[₹\$\€\£]|Rs\.|Rs |rupee|rupees|dollar', line, re.IGNORECASE):
                    money_lines.append(line)
            
            amounts_found = []
            for line in money_lines:
                # Skip item/product lines (these are not totals)
                if re.search(r'item|product|qty|quantity|x\d|each|piece', line, re.IGNORECASE):
                    continue
                
                # Pattern 1: Currency symbol followed by number
                match = re.search(r'[₹\$\€\£]\s*(\d+(?:[.,]\d{2})?)', line)
                if match:
                    amount = self._parse_amount_string(match.group(1))
                    if amount:
                        amounts_found.append(amount)
                
                # Pattern 2: Rs/rupees/dollars followed by number
                match = re.search(r'(?:Rs\.|Rs|rupees?|dollars?)\s*:?\s*(\d+(?:[.,]\d{2})?)', line, re.IGNORECASE)
                if match:
                    amount = self._parse_amount_string(match.group(1))
                    if amount:
                        amounts_found.append(amount)
            
            if amounts_found:
                # Return the largest amount (usually the total)
                return max(amounts_found)
        
        # PRIORITY 4: TEXT MODE (simple text input like "Spent 500 for biryani")
        # Look for numbers with 2 decimal places first
        decimal_pattern = r'(\d+[.,]\d{2})'
        matches = re.findall(decimal_pattern, text)
        if matches:
            for match in sorted(matches, key=lambda x: float(x.replace(',', '.')), reverse=True):
                amount = self._parse_amount_string(match)
                if amount:
                    return amount
        
        # PRIORITY 5: Look for any number (but skip obvious pincodes at start)
        all_matches = re.findall(r'(\d+(?:[.,]\d{2})?)', text)
        for idx, match in enumerate(all_matches):
            amount = self._parse_amount_string(match)
            if amount:
                # Skip likely pincodes: 5-6 digit integers without decimals at start
                is_pincode = (len(match) in [5, 6] and '.' not in match and ',' not in match and idx == 0)
                if not is_pincode:
                    return amount
        
        return None
    
    def _parse_amount_string(self, amount_str):
        """Helper to parse amount string to float"""
        try:
            amount_str = amount_str.replace(',', '.')
            amount = float(amount_str)
            # Valid range for expenses
            if 0 < amount < 1000000:
                return amount
        except (ValueError, TypeError):
            pass
        return None
    
    def _extract_category(self, text_lower):
        """Extract category from text using keyword matching"""
        for category, keywords in EXPENSE_PATTERNS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    for cat_name in EXPENSE_CATEGORIES:
                        if cat_name.lower() == category.lower():
                            return cat_name
        
        return "Other"
    
    def analyze_receipt(self, receipt_text):
        """
        Advanced receipt analysis for structured data extraction.
        Extracts: restaurant details, items, quantities, prices, taxes, totals.
        
        Returns: dict with fields for restaurant, items, subtotal, tax, service_charge, discount, final_amount, currency, payment_method, confidence
        """
        text = (receipt_text or "").strip()
        
        if not text:
            return {
                'restaurant': {'name': None, 'address': None, 'phone': None},
                'items': [],
                'subtotal': None,
                'tax': {'gst': None, 'other': None},
                'service_charge': None,
                'discount': None,
                'final_amount': None,
                'currency': 'INR',
                'payment_method': None,
                'confidence': 'low',
                'error': 'Empty receipt text'
            }
        
        result = {
            'restaurant': {'name': None, 'address': None, 'phone': None},
            'items': [],
            'subtotal': None,
            'tax': {'gst': None, 'other': None},
            'service_charge': None,
            'discount': None,
            'final_amount': None,
            'currency': 'INR',
            'payment_method': None,
            'confidence': 'medium'
        }
        
        # Extract restaurant details
        lines = text.split('\n')[:5]
        for line in lines:
            clean_line = line.strip()
            if clean_line and len(clean_line) > 3 and len(clean_line) < 50:
                if not any(char.isdigit() for char in clean_line[:5]):
                    result['restaurant']['name'] = clean_line
                    break
        
        # Extract phone
        phone_match = re.search(r'\b\d{10}\b', text)
        if phone_match:
            result['restaurant']['phone'] = phone_match.group()
        
        # Extract items - look for lines with prices
        text_lines = [line.strip() for line in text.split('\n') if line.strip()]
        item_pattern = r'^([a-zA-Z\s]+?)\s+(?:[\-\.]|x\s*)?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)\s*(?:\(.*?\))?$'
        
        for line in text_lines:
            match = re.match(item_pattern, line, re.IGNORECASE)
            if match:
                item_name = match.group(1).strip()
                price_str = match.group(3)
                if price_str:
                    try:
                        price = float(price_str.replace(',', '.'))
                        category = self._extract_category(item_name.lower())
                        result['items'].append({
                            'name': item_name,
                            'quantity': None,
                            'unit_price': None,
                            'total_price': price,
                            'category': category
                        })
                    except ValueError:
                        pass
        
        # Extract subtotal
        subtotal_patterns = [
            r'subtotal\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'sub[\s-]?total\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
        ]
        for pattern in subtotal_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    result['subtotal'] = float(match.group(2).replace(',', '.'))
                    break
                except (ValueError, IndexError):
                    pass
        
        # Extract taxes
        gst_patterns = [
            r'(?:sgst|cgst|gst)\s*(?:\d+%?)?\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'gst\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
        ]
        for pattern in gst_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    result['tax']['gst'] = float(match.group(2).replace(',', '.'))
                    break
                except (ValueError, IndexError):
                    pass
        
        # Extract service charge
        service_patterns = [
            r'service\s*charge\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'service\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
        ]
        for pattern in service_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    result['service_charge'] = float(match.group(2).replace(',', '.'))
                    break
                except (ValueError, IndexError):
                    pass
        
        # Extract discount
        discount_patterns = [
            r'discount\s*:?\s*[-]?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'offer\s*:?\s*[-]?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
        ]
        for pattern in discount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    result['discount'] = float(match.group(2).replace(',', '.'))
                    break
                except (ValueError, IndexError):
                    pass
        
        # Extract final amount
        total_patterns = [
            r'(?:total|final|payable)\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'grand\s+total\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
        ]
        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    result['final_amount'] = float(match.group(2).replace(',', '.'))
                    break
                except (ValueError, IndexError):
                    pass
        
        # Detect payment method
        payment_patterns = {
            'Cash': r'\bcash\b',
            'Card': r'\bcard\b',
            'UPI': r'\bupi\b',
        }
        for method, pattern in payment_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                result['payment_method'] = method
                break
        
        # Detect currency
        if '₹' in text or 'Rs' in text.upper() or 'INR' in text.upper():
            result['currency'] = 'INR'
        elif '$' in text or 'USD' in text.upper():
            result['currency'] = 'USD'
        elif '€' in text:
            result['currency'] = 'EUR'
        
        # Confidence level
        if result['items'] and result['final_amount']:
            result['confidence'] = 'high'
        elif result['items'] or result['final_amount']:
            result['confidence'] = 'medium'
        else:
            result['confidence'] = 'low'
        
        return result


        """
        Parse multiple expenses from receipt with multiple items
        Extracts items separated by newlines, each with category and amount
        Returns: list of (amount, category, description) tuples
        
        Handles formats:
        1. Explicit fields (Item: X, Amount: Y, Category: Z) with --- separators
        2. Line-by-line: "Biryani - 250" or "Biryani Rs 250"
        3. Double newlines: Blank lines between items
        """
        expenses = []
        
        # Try to detect item blocks separated by "---", "===", or blank lines
        item_blocks = []
        
        # Split by common separators first (strongest signal)
        if "---" in text or "===" in text:
            blocks = re.split(r'---+|===+', text)
            item_blocks = [block.strip() for block in blocks if block.strip()]
        else:
            # Check if this looks like line-by-line format (each line has amount)
            lines = text.split('\n')
            lines = [line.strip() for line in lines if line.strip()]
            
            # Count how many lines have numbers (potential items)
            lines_with_numbers = sum(1 for line in lines if re.search(r'\d+', line))
            
            # If multiple lines have numbers, treat each as a separate item
            if lines_with_numbers >= 2 and len(lines) >= 2:
                item_blocks = lines
            else:
                # Single item or blank lines as separators
                current_block = []
                for line in lines:
                    if not line:
                        if current_block:
                            item_blocks.append('\n'.join(current_block))
                            current_block = []
                    else:
                        current_block.append(line)
                
                if current_block:
                    item_blocks.append('\n'.join(current_block))
        
        # Process each block
        for block in item_blocks:
            if not block:
                continue
            
            # Try to parse the block as a single expense
            amount, category, description = self.parse_expense(block)
            
            if amount:  # Only add if we found an amount
                expenses.append((amount, category, description))
        
        return expenses
    
    def analyze_receipt(self, receipt_text):
        """
        Advanced receipt analysis for structured data extraction.
        Extracts: restaurant details, items, quantities, prices, taxes, totals.
        
        Returns: dict with following structure:
        {
            'restaurant': {
                'name': str or None,
                'address': str or None,
                'phone': str or None
            },
            'items': [
                {
                    'name': str,
                    'quantity': float or None,
                    'unit_price': float or None,
                    'total_price': float,
                    'category': str
                },
                ...
            ],
            'subtotal': float or None,
            'tax': {
                'gst': float or None,
                'other': float or None
            },
            'service_charge': float or None,
            'discount': float or None,
            'final_amount': float,
            'currency': str,
            'payment_method': str or None,
            'confidence': str  # 'high', 'medium', 'low'
        }
        """
        text = (receipt_text or "").strip()
        
        if not text:
            return {
                'restaurant': {'name': None, 'address': None, 'phone': None},
                'items': [],
                'subtotal': None,
                'tax': {'gst': None, 'other': None},
                'service_charge': None,
                'discount': None,
                'final_amount': None,
                'currency': 'INR',
                'payment_method': None,
                'confidence': 'low',
                'error': 'Empty receipt text'
            }
        
        result = {
            'restaurant': self._extract_restaurant_details(text),
            'items': [],
            'subtotal': None,
            'tax': {'gst': None, 'other': None},
            'service_charge': None,
            'discount': None,
            'final_amount': None,
            'currency': self._detect_currency(text),
            'payment_method': None,
            'confidence': 'medium'
        }
        
        # Extract items
        result['items'] = self._extract_receipt_items(text)
        
        # Extract financial details
        result['subtotal'] = self._extract_subtotal(text)
        result['tax'] = self._extract_taxes(text)
        result['service_charge'] = self._extract_service_charge(text)
        result['discount'] = self._extract_discount(text)
        result['final_amount'] = self._extract_final_amount(text)
        result['payment_method'] = self._extract_payment_method(text)
        
        # Determine confidence level
        if result['items'] and result['final_amount']:
            result['confidence'] = 'high'
        elif result['items'] or result['final_amount']:
            result['confidence'] = 'medium'
        else:
            result['confidence'] = 'low'
        
        return result
    
    def _extract_restaurant_details(self, text):
        """Extract restaurant name, address, phone"""
        restaurant = {'name': None, 'address': None, 'phone': None}
        
        lines = text.split('\n')[:5]  # Check first few lines
        
        # Restaurant name (usually first meaningful line)
        for line in lines:
            clean_line = line.strip()
            if clean_line and len(clean_line) > 3 and len(clean_line) < 50:
                if not any(char.isdigit() for char in clean_line[:5]):
                    restaurant['name'] = clean_line
                    break
        
        # Phone number (10 digits)
        phone_match = re.search(r'\b\d{10}\b', text)
        if phone_match:
            restaurant['phone'] = phone_match.group()
        
        # Address (lines with mix of letters and numbers, typically 2-4 words)
        for line in lines:
            clean = line.strip()
            if 'address' in clean.lower() or 'location' in clean.lower():
                restaurant['address'] = re.sub(r'address|location', '', clean, flags=re.IGNORECASE).strip()
        
        return restaurant
    
    def _extract_receipt_items(self, text):
        """Extract food items with quantities and prices"""
        items = []
        
        # Split into lines
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Pattern for item lines (name + price pattern)
        # Looks for: "Item Name    Price" or "Item Name - Price"
        item_pattern = r'^([a-zA-Z\s]+?)\s+(?:[\-\.]|x\s*)?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)\s*(?:\(.*?\))?$'
        
        for line in lines:
            match = re.match(item_pattern, line, re.IGNORECASE)
            if match:
                item_name = match.group(1).strip()
                price_str = match.group(3)
                
                if price_str:
                    try:
                        price = float(price_str.replace(',', '.'))
                        
                        # Detect category
                        category = self._extract_category(item_name.lower())
                        
                        items.append({
                            'name': item_name,
                            'quantity': None,  # Not explicitly provided in simple format
                            'unit_price': None,
                            'total_price': price,
                            'category': category
                        })
                    except ValueError:
                        pass
        
        return items
    
    def _extract_subtotal(self, text):
        """Extract subtotal amount"""
        patterns = [
            r'subtotal\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'sub[\s-]?total\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'items\s*total\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(2).replace(',', '.'))
                except (ValueError, IndexError):
                    pass
        
        return None
    
    def _extract_taxes(self, text):
        """Extract GST and other taxes"""
        taxes = {'gst': None, 'other': None}
        
        # GST/SGST/CGST patterns
        gst_patterns = [
            r'(?:sgst|cgst|gst)\s*(?:\d+%?)?\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'gst\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
        ]
        
        for pattern in gst_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    taxes['gst'] = float(match.group(2).replace(',', '.'))
                    break
                except (ValueError, IndexError):
                    pass
        
        # Other tax patterns
        other_patterns = [
            r'tax\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'vat\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
        ]
        
        for pattern in other_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    taxes['other'] = float(match.group(2).replace(',', '.'))
                    break
                except (ValueError, IndexError):
                    pass
        
        return taxes
    
    def _extract_service_charge(self, text):
        """Extract service charge/tip"""
        patterns = [
            r'service\s*charge\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'service\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'tip\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(2).replace(',', '.'))
                except (ValueError, IndexError):
                    pass
        
        return None
    
    def _extract_discount(self, text):
        """Extract discount amount"""
        patterns = [
            r'discount\s*:?\s*[-]?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'offer\s*:?\s*[-]?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'promotion\s*:?\s*[-]?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(2).replace(',', '.'))
                except (ValueError, IndexError):
                    pass
        
        return None
    
    def _extract_final_amount(self, text):
        """Extract final payable amount"""
        patterns = [
            r'(?:total|final|payable|amount|due|bill)\s*(?:amount)?\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)\s*$',
            r'(?:total|final|payable)\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
            r'(?:grand\s+total|total\s+due)\s*:?\s*(₹|Rs|rs|\$|€|£)?\s*(\d+(?:[.,]\d{1,2})?)',
        ]
        
        # Look for patterns from the end (likely at bottom of receipt)
        text_lines = text.split('\n')
        text_reversed = '\n'.join(reversed(text_lines))
        
        for pattern in patterns:
            match = re.search(pattern, text_reversed, re.IGNORECASE | re.MULTILINE)
            if match:
                try:
                    return float(match.group(2).replace(',', '.'))
                except (ValueError, IndexError):
                    pass
        
        return None
    
    def _extract_payment_method(self, text):
        """Extract payment method (Cash, Card, UPI, etc)"""
        patterns = {
            'Cash': r'\bcash\b',
            'Credit Card': r'credit\s*card',
            'Debit Card': r'debit\s*card',
            'Card': r'\bcard\b',
            'UPI': r'\bupi\b',
            'Digital Wallet': r'wallet|paytm|googlepay|phonepay',
            'Cheque': r'cheque|check',
            'Net Banking': r'net\s*banking|online',
        }
        
        for method, pattern in patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                return method
        
        return None
    
    def _detect_currency(self, text):
        """Detect currency from receipt text"""
        if '₹' in text or 'Rs' in text.upper() or 'INR' in text.upper():
            return 'INR'
        elif '$' in text or 'USD' in text.upper():
            return 'USD'
        elif '€' in text or 'EUR' in text.upper():
            return 'EUR'
        elif '£' in text or 'GBP' in text.upper():
            return 'GBP'
        else:
            return 'INR'  # Default


# ============================================================================
# ORIGINAL METHOD: Tesseract OCR
# ============================================================================

class OCRProcessor:
    """Extract text from images using Tesseract OCR."""

    def __init__(self):
        self.parser = ExpenseParser()
        self._configure_tesseract()

    def _configure_tesseract(self):
        """Configure Tesseract path on Windows when installed in default location."""
        try:
            import os
            import pytesseract

            default_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(default_path):
                pytesseract.pytesseract.tesseract_cmd = default_path
        except Exception:
            # Keep default pytesseract resolution if explicit path setup fails.
            pass

    def extract_text_from_image(self, image_path):
        """Extract OCR text from image path."""
        try:
            import os
            from PIL import Image
            import pytesseract

            if not os.path.exists(image_path):
                logger.error("Image file not found: %s", image_path)
                return ""

            with Image.open(image_path) as image:
                return (pytesseract.image_to_string(image) or "").strip()
        except Exception as ocr_error:
            logger.error("Tesseract OCR failed: %s", ocr_error)
            return ""

    def parse_receipt(self, image_path):
        """Parse OCR output and return normalized receipt fields."""
        text = self.extract_text_from_image(image_path)

        if not text:
            return {
                "amount": None,
                "category": None,
                "description": None,
                "source": "receipt",
                "text": None,
                "raw_text": None,
                "error": "Could not extract text from image",
            }

        amount, category, description = self.parser.parse_expense(text)
        return {
            "amount": amount,
            "category": category,
            "description": description or text[:100],
            "source": "receipt",
            "text": text,
            "raw_text": text,
        }


# ============================================================================
# ALTERNATIVE METHOD 1: EasyOCR (No system software needed!)
# ============================================================================

class EasyOCRProcessor:
    """
    Extract text from images using EasyOCR
    Advantages:
    - ✅ No system software installation needed
    - ✅ Pip installable only
    - ✅ Very accurate
    - ✅ Faster than Tesseract
    
    Installation: pip install easyocr
    """
    
    def __init__(self):
        self.parser = ExpenseParser()
        self.reader = None
        self._initialize_reader()
    
    def _initialize_reader(self):
        """Initialize EasyOCR reader (loads model on first use)"""
        try:
            import easyocr
            logger.info("📊 Initializing EasyOCR reader...")
            self.reader = easyocr.Reader(['en'], gpu=False)
            logger.info("✓ EasyOCR reader initialized successfully")
        except ImportError:
            logger.error("❌ easyocr not installed. Run: pip install easyocr")
            self.reader = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize EasyOCR: {e}")
            self.reader = None
    
    def extract_text_from_image(self, image_path):
        """
        Extract text from image using EasyOCR
        Returns: extracted text string
        """
        try:
            import os
            
            # Validate image file
            if not os.path.exists(image_path):
                logger.error(f"❌ Image file not found: {image_path}")
                return ""
            
            # Check if reader initialized
            if self.reader is None:
                logger.error("❌ EasyOCR not initialized")
                return ""
            
            logger.info(f"🔍 EasyOCR extracting text from: {image_path}")
            
            # Extract text
            results = self.reader.readtext(image_path)
            
            # Combine all text results
            extracted_text = "\n".join([text[1] for text in results])
            
            logger.info(f"✓ Text extracted successfully. Length: {len(extracted_text)} chars")
            return extracted_text
        
        except Exception as e:
            logger.error(f"❌ EasyOCR extraction failed: {e}")
            return ""
    
    def parse_receipt(self, image_path):
        """
        Parse receipt image and extract amount + category
        Returns: dict with amount, category, description, source
        """
        text = self.extract_text_from_image(image_path)
        
        if not text:
            return {
                'amount': None,
                'category': None,
                'description': None,
                'source': 'receipt',
                'error': 'Could not extract text from image'
            }
        
        amount, category, description = self.parser.parse_expense(text)
        
        return {
            'amount': amount,
            'category': category,
            'description': description or text[:100],
            'source': 'receipt',
            'text': text,
            'raw_text': text
        }


# ============================================================================
# ALTERNATIVE METHOD 2: PaddleOCR (Even faster, super lightweight)
# ============================================================================

class PaddleOCRProcessor:
    """
    Extract text from images using PaddleOCR
    Advantages:
    - ✅ No system software installation needed
    - ✅ Pip installable only
    - ✅ Very fast (faster than EasyOCR)
    - ✅ Lower memory footprint
    - ✅ Great for mobile-optimized models
    
    Installation: pip install paddleocr paddlepaddle
    """
    
    def __init__(self):
        self.parser = ExpenseParser()
        self.ocr = None
        self._initialize_ocr()
    
    def _initialize_ocr(self):
        """Initialize PaddleOCR"""
        try:
            from paddleocr import PaddleOCR
            logger.info("📊 Initializing PaddleOCR...")
            self.ocr = PaddleOCR(use_angle_cls=True, lang='en')
            logger.info("✓ PaddleOCR initialized successfully")
        except ImportError:
            logger.error("❌ paddleocr not installed. Run: pip install paddleocr paddlepaddle")
            self.ocr = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize PaddleOCR: {e}")
            self.ocr = None
    
    def extract_text_from_image(self, image_path):
        """
        Extract text from image using PaddleOCR
        Returns: extracted text string
        """
        try:
            import os
            
            # Validate image file
            if not os.path.exists(image_path):
                logger.error(f"❌ Image file not found: {image_path}")
                return ""
            
            # Check if OCR initialized
            if self.ocr is None:
                logger.error("❌ PaddleOCR not initialized")
                return ""
            
            logger.info(f"🔍 PaddleOCR extracting text from: {image_path}")
            
            # Extract text
            result = self.ocr.ocr(image_path, cls=True)
            
            # Combine all text results
            extracted_text = "\n".join(
                [line[0][1] for line in result if line]
            )
            
            logger.info(f"✓ Text extracted successfully. Length: {len(extracted_text)} chars")
            return extracted_text
        
        except Exception as e:
            logger.error(f"❌ PaddleOCR extraction failed: {e}")
            return ""
    
    def parse_receipt(self, image_path):
        """
        Parse receipt image and extract amount + category
        Returns: dict with amount, category, description, source
        """
        text = self.extract_text_from_image(image_path)
        
        if not text:
            return {
                'amount': None,
                'category': None,
                'description': None,
                'source': 'receipt',
                'error': 'Could not extract text from image'
            }
        
        amount, category, description = self.parser.parse_expense(text)
        
        return {
            'amount': amount,
            'category': category,
            'description': description or text[:100],
            'source': 'receipt',
            'text': text,
            'raw_text': text
        }


# ============================================================================
# VOICE METHOD: Google Speech API (Already working)
# ============================================================================

class VoiceProcessor:
    """
    Convert voice messages to text using Google Speech API
    Already tested and working!
    """
    
    def __init__(self):
        self.parser = ExpenseParser()

    def _normalize_transcribed_text(self, text):
        """
        Normalize common ASR artifacts before parsing.
        Example: "t10" -> "tea 10"
        """
        if not text:
            return text

        normalized = text.strip()
        # Split merged alpha+number tokens: "tea10" -> "tea 10", "t10" -> "t 10"
        normalized = re.sub(r"\b([A-Za-z]+)(\d+(?:[.,]\d+)?)\b", r"\1 \2", normalized)
        normalized = re.sub(r"\s{2,}", " ", normalized).strip()

        # Common voice miss-hear: "t 10" when user says "tea 10"
        normalized = re.sub(
            r"^(t)\s+(\d+(?:[.,]\d+)?)\b",
            r"tea \2",
            normalized,
            flags=re.IGNORECASE,
        )
        return normalized
    
    def _prepare_audio_file(self, voice_path):
        """
        Convert unsupported audio formats (like Telegram .ogg/.opus) to WAV.
        Returns: (audio_path_to_read, temp_file_to_cleanup_or_none)
        """
        import os
        ext = os.path.splitext(voice_path)[1].lower()
        if ext in (".wav", ".aiff", ".aif", ".flac"):
            return voice_path, None
        try:
            from pydub import AudioSegment
        except ImportError:
            logger.error("? pydub not installed. Run: pip install pydub")
            return None, None
        try:
            import tempfile
            # Telegram voice notes are usually OGG/OPUS containers.
            fmt = "ogg" if ext in (".ogg", ".oga", ".opus") else ext.lstrip(".")
            audio = AudioSegment.from_file(voice_path, format=fmt)
            audio = audio.set_channels(1).set_frame_rate(16000)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                temp_wav = tmp.name
            audio.export(temp_wav, format="wav")
            logger.info("Audio converted for transcription: %s -> %s", voice_path, temp_wav)
            return temp_wav, temp_wav
        except Exception as e:
            logger.error("? Audio conversion failed (install ffmpeg and add it to PATH): %s", e)
            return None, None
    def transcribe_voice(self, voice_path):
        """
        Transcribe voice file to text using Google Speech API
        Fallback to Sphinx if Google API fails
        Returns: transcribed text or None if failed
        """
        try:
            import speech_recognition as sr
            import os
            # File validation
            if not os.path.exists(voice_path):
                logger.error(f"? Voice file not found: {voice_path}")
                return None
            logger.info(f"?? Loading voice file: {voice_path}")
            recognizer = sr.Recognizer()
            temp_audio = None
            try:
                audio_path, temp_audio = self._prepare_audio_file(voice_path)
                if not audio_path:
                    return None
                with sr.AudioFile(audio_path) as source:
                    audio = recognizer.record(source)
            except Exception as e:
                logger.error("? Failed to read audio for transcription: %s", e)
                return None
            finally:
                if temp_audio and os.path.exists(temp_audio):
                    try:
                        os.remove(temp_audio)
                    except OSError:
                        pass
            # Try Google Speech API first
            try:
                logger.info("?? Trying Google Speech API...")
                text = recognizer.recognize_google(audio)
                logger.info("? Google Speech API successful")
                normalized_text = self._normalize_transcribed_text(text)
                if normalized_text != text:
                    logger.info("Voice text normalized: '%s' -> '%s'", text, normalized_text)
                return normalized_text
            except sr.UnknownValueError:
                logger.warning("?? Google Speech API could not understand audio")
            except sr.RequestError as e:
                logger.warning(f"?? Google Speech API request failed: {e}")
            # Fallback to Sphinx
            try:
                logger.info("??? Trying Sphinx fallback...")
                text = recognizer.recognize_sphinx(audio)
                logger.info("? Sphinx transcription successful")
                normalized_text = self._normalize_transcribed_text(text)
                if normalized_text != text:
                    logger.info("Voice text normalized: '%s' -> '%s'", text, normalized_text)
                return normalized_text
            except Exception as e:
                logger.error(f"? Sphinx recognition failed: {e}")
                return None
        except ImportError:
            logger.error("? speech_recognition not installed. Run: pip install SpeechRecognition")
            return None
        except Exception as e:
            logger.error(f"? Voice transcription error: {e}")
            return None
    def parse_voice(self, voice_path):
        """
        Parse voice message and extract amount + category
        Returns: dict with amount, category, description
        """
        text = self.transcribe_voice(voice_path)
        
        if not text:
            return {
                'amount': None,
                'category': None,
                'description': None,
                'source': 'voice',
                'error': 'Could not transcribe voice'
            }
        
        amount, category, description = self.parser.parse_expense(text)
        
        return {
            'amount': amount,
            'category': category,
            'description': description,
            'source': 'voice',
            'raw_text': text
        }

