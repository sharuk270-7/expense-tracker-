"""
Extract food receipt details from an image and output plain text (NOT JSON).

Usage:
  python extract_receipt_text.py <image_path>
  python extract_receipt_text.py receipt.jpg

Output format:
  Food Items:
  1. <Food Name> - <Price>
  2. ...
  Subtotal: <Amount>
  Tax: <Amount> (if available)
  Total Amount: <Final Bill Amount>
"""
import sys
import os

def get_ocr_text(image_path):
    """Get text from image using configured OCR or fallbacks."""
    if not os.path.exists(image_path):
        return None
    text = None
    try:
        from ocr_config import get_ocr_processor
        ocr = get_ocr_processor()
        if ocr:
            result = ocr.parse_receipt(image_path)
            text = result.get('text') if result else None
    except Exception:
        pass
    if not text:
        try:
            from nlp_processor import EasyOCRProcessor
            ocr = EasyOCRProcessor()
            result = ocr.parse_receipt(image_path)
            text = result.get('text') if result else None
        except Exception:
            pass
    if not text:
        try:
            from nlp_processor import OCRProcessor
            ocr = OCRProcessor()
            text = ocr.extract_text_from_image(image_path)
        except Exception:
            pass
    return text

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_receipt_text.py <image_path>")
        print("Example: python extract_receipt_text.py receipt.jpg")
        sys.exit(1)
    image_path = sys.argv[1].strip()
    if not os.path.exists(image_path):
        print(f"Error: File not found: {image_path}")
        sys.exit(1)
    ocr_text = get_ocr_text(image_path)
    if not ocr_text or not ocr_text.strip():
        print("Error: Could not extract text from image. Check OCR setup (Tesseract/EasyOCR).")
        sys.exit(1)
    from nlp_processor import ExpenseParser
    parser = ExpenseParser()
    analysis = parser.analyze_receipt(ocr_text)
    plain = parser.format_receipt_plain_text(analysis)
    print(plain)

if __name__ == "__main__":
    main()
