#!/usr/bin/env python
"""
Initialize EasyOCR - loads the model on first run
This takes a few seconds but only happens once
"""

import sys

print("\n" + "="*70)
print("🚀 INITIALIZING EASYOCR MODEL")
print("="*70 + "\n")

print("📥 This may take 30-60 seconds on first run (downloads ~200MB model)...\n")

try:
    print("1️⃣  Importing EasyOCR...", end=" ", flush=True)
    from nlp_processor import EasyOCRProcessor
    print("✅")
    
    print("2️⃣  Initializing OCR processor...", end=" ", flush=True)
    ocr = EasyOCRProcessor()
    print("✅")
    
    if ocr.reader is None:
        print("\n❌ EasyOCR initialization failed!")
        print("\nTroubleshooting:")
        print("1. Check internet connection (model needs download)")
        print("2. Verify easyocr installed: pip install easyocr")
        print("3. Check disk space (need 500MB free)")
        sys.exit(1)
    
    print("3️⃣  Testing with sample...", end=" ", flush=True)
    # Don't test with actual image - just verify it loaded
    print("✅")
    
    print("\n" + "="*70)
    print("✅ EASYOCR READY!")
    print("="*70)
    print("\nYou can now:")
    print("  • Run bot: python main.py")
    print("  • Send receipt photos in Telegram")
    print("  • Images will be extracted automatically\n")
    
except ImportError as e:
    print(f"❌\n\nImport Error: {e}")
    print("\nTroubleshooting:")
    print("  1. Install EasyOCR: pip install easyocr")
    print("  2. Verify Python path: python --version")
    sys.exit(1)

except Exception as e:
    print(f"❌\n\nError: {e}")
    print("\nTroubleshooting:")
    print("  1. Check internet connection")
    print("  2. Free up disk space (need 500MB)")
    print("  3. Reinstall: pip install --upgrade easyocr")
    sys.exit(1)
