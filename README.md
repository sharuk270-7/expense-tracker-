# 💸 Expense Tracker AI Agent

A feature-rich Telegram bot that helps you track daily expenses using natural language, receipt photos, voice messages, and payment screenshots — with Excel, PDF, CSV, and graph export support.

---

## ✨ Features

- **Natural Language Parsing** — Send messages like `"Spent 150 for biriyani"` and the bot extracts the amount and category automatically.
- **Receipt Photo OCR** — Photograph a receipt and the bot extracts individual line items, subtotals, taxes, and totals.
- **Voice Messages** — Describe an expense by voice; the bot transcribes and records it.
- **Payment Screenshots** — Upload UPI/bank screenshots with a caption to log online payments.
- **Budget Limits** — Set daily, weekly, and monthly spending limits with automatic warnings at 75%, 90%, and 100%.
- **Export Options** — Export your data as Excel (.xlsx), CSV, PDF, or a category-wise spending graph.
- **Multi-Item Receipts** — Supports bulk entry (one expense per line) in a single message.
- **Detailed Analytics** — Weekly/monthly summaries, daily averages, category breakdowns.

---

## 🗂️ Project Structure

```
expense-tracker-bot/
├── main.py                   # Bot entry point & message handlers
├── bot_commands.py           # All Telegram command handlers
├── database.py               # SQLite database layer
├── nlp_processor.py          # NLP parsing, OCR, voice processing
├── gemini_processor.py       # Google Gemini AI receipt analysis
├── excel_exporter.py         # Excel (.xlsx) export engine
├── ocr_config.py             # OCR method selection & fallback logic
├── analytics.py              # Advanced analytics utilities
├── config.py                 # Configuration & constants
├── add_expenses.py           # Bulk expense import script
├── extract_receipt_text.py   # CLI receipt text extractor
├── initialize_easyocr.py     # EasyOCR model pre-loader
├── startup.py                # Dependency & config diagnostics
├── requirements.txt          # Python dependencies
└── tests/
    ├── test_parser.py
    ├── test_multi_item_receipt.py
    ├── test_receipt_analysis.py
    ├── test_budget_features.py
    ├── test_excel_export.py
    ├── test_voice_features.py
    ├── test_alternative_methods.py
    └── test_simple_extract.py
```

---

## ⚙️ Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/p-premkumar/Expense-Tracker-AI-Agent
cd expense-tracker-bot
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_google_gemini_api_key_here
OCR_METHOD=tesseract   # Options: tesseract | easyocr | paddleocr
```

> **Note:** The Telegram Bot Token is currently hardcoded in `config.py`. For production use, move it to your `.env` file and load it with `os.getenv("BOT_TOKEN")`.

### 4. (Optional) Install an OCR engine

| Method | Command | Notes |
|---|---|---|
| **Tesseract** | [Download installer](https://github.com/UB-Mannheim/tesseract/wiki) | Requires system software |
| **EasyOCR** | `pip install easyocr` | Downloads ~200 MB model on first run |
| **PaddleOCR** | `pip install paddleocr paddlepaddle` | Fastest option |

Pre-load the EasyOCR model (avoids delay on first receipt scan):

```bash
python initialize_easyocr.py
```

### 5. Run the bot

```bash
python main.py
```

### 6. Verify your setup

```bash
python startup.py
```

---

## 🤖 Bot Commands

### Viewing Expenses

| Command | Description |
|---|---|
| `/summary` | Last 30 days by category |
| `/weekly` | Last 7 days summary |
| `/monthly` | Last 30 days summary |
| `/today` | Today's total spending |
| `/list` | Last 10 expense entries |
| `/stats` | Detailed 7-day and 30-day statistics |
| `/categories` | Show all supported categories |

### Budget Management

| Command | Description |
|---|---|
| `/setdaily <amount>` | Set a daily spending limit |
| `/setweekly <amount>` | Set a weekly spending limit |
| `/setmonthly <amount>` | Set a monthly spending limit |
| `/limits` | View current budget status and usage |

### Reports

| Command | Description |
|---|---|
| `/week` | Weekly category report |
| `/month` | Monthly category report |

### Exporting Data

| Command | Description |
|---|---|
| `/export` | All expenses → Excel |
| `/exporttoday` | Today's expenses → Excel |
| `/exportweekly` | Last 7 days → Excel |
| `/exportmonthly` | Last 30 days → Excel |
| `/exportrange <start> <end>` | Custom date range → Excel (format: `YYYY-MM-DD`) |
| `/exportcsv` | All expenses → CSV |
| `/pdf` | Last 30 days → PDF report |
| `/graph` | Last 30 days → bar + pie chart image |

### Managing Data

| Command | Description |
|---|---|
| `/delete` | Delete the most recent expense |
| `/help` | Full command reference |

---

## 💬 Adding Expenses

### Text Messages

Send any natural language message:

```
Spent 150 for biriyani
50 on transport
Movie tickets 250
Coffee 80
```

### Bulk Entry (Multiple Lines)

Send multiple expenses in a single message — one per line:

```
Coffee 30
Apple 150
Tea 40
Biriyani 150
Petrol 150
```

### Receipt Photos

Send a photo of a paper receipt. The bot will:
1. Extract all line items with quantities and prices.
2. Detect subtotal, taxes, and grand total.
3. Save each item individually with its inferred category.

### Voice Messages

Record a voice note describing your expense (e.g. *"Spent two hundred on groceries"*). The bot transcribes it using Google Speech API and logs the expense.

### Payment Screenshots

Send a payment confirmation screenshot with a caption containing payment details:

```
TXID: UPI123456789
Account: HDFC Bank
```

---

## 📂 Supported Categories

| Category | Example Keywords |
|---|---|
| Food | biryani, pizza, lunch, dinner |
| Transport | petrol, taxi, bus, metro, fuel |
| Entertainment | movie, concert, game, show |
| Shopping | clothes, shoes, gift, shirt |
| Utilities | electricity, internet, phone, bill |
| Health | medicine, doctor, hospital |
| Education | book, course, tuition, training |
| Travel | hotel, flight, trip, vacation |
| Work | office, project, meeting |
| Meat | chicken, fish, mutton, beef |
| Vegetables | carrot, tomato, onion, potato |
| Fruits | apple, banana, mango, grapes |
| Hot Drinks | coffee, tea, cappuccino, latte |
| Other | *(anything unrecognised)* |

---

## 🏗️ Architecture Overview

```
Telegram User
     │
     ▼
main.py  ──────────────────────────────────────────────────┐
  │  handle_message()   (text / bulk)                      │
  │  handle_photo()     (receipt / screenshot)             │
  │  handle_voice()     (voice note)                       │
  │                                                        │
  ├──► nlp_processor.py                                    │
  │      ExpenseParser      — amount & category extraction │
  │      OCRProcessor       — Tesseract receipt OCR        │
  │      EasyOCRProcessor   — EasyOCR receipt OCR          │
  │      VoiceProcessor     — Google Speech transcription  │
  │                                                        │
  ├──► gemini_processor.py                                 │
  │      GeminiProcessor    — Gemini AI receipt analysis   │
  │                                                        │
  ├──► database.py                                         │
  │      ExpenseDatabase    — SQLite CRUD & queries        │
  │                                                        │
  ├──► bot_commands.py                                     │
  │      Command handlers   — /summary, /export, etc.     │
  │                                                        │
  └──► excel_exporter.py                                   │
         ExcelExporter      — Multi-sheet .xlsx reports    │
```

---

## 🗃️ Database Schema

The SQLite database (`expenses.db`) contains four tables:

- **users** — Telegram user profiles
- **expenses** — All recorded expense entries (amount, category, description, date, source, transaction_id, account_name, payment_method)
- **categories** — User-defined category metadata
- **budget_limits** — Per-user daily/weekly/monthly budget limits

---

## 📊 Excel Export Sheets

Each exported `.xlsx` file contains multiple sheets for deep analysis:

| Sheet | Contents |
|---|---|
| All Expenses / Custom Range | Full transaction list |
| Summary | 7-day and 30-day totals by category |
| Monthly Breakdown | Total spending per calendar month |
| Detailed | Timestamped transaction detail |
| Bill Totals | Receipt subtotal/total/grand total rows |
| Bill Analysis | Per-receipt category and total breakdown |
| Bill Items | Individual receipt line items with quantity |
| Pattern Summary | Keyword-based spending patterns |

---

## 🧪 Running Tests

```bash
# Test NLP parser
python test_parser.py

# Test multi-item receipt parsing
python test_multi_item_receipt.py

# Test receipt analysis
python test_receipt_analysis.py

# Test budget features
python test_budget_features.py

# Test Excel export
python test_excel_export.py

# Test OCR methods
python test_alternative_methods.py

# Test voice features
python test_voice_features.py
```

---

## 🛠️ Bulk Import

To add multiple expenses programmatically (useful for testing or migration):

```bash
python add_expenses.py
```

Edit the `expenses` list and `user_id` inside the file before running.

---

## 📋 Requirements

- Python 3.10+
- `python-telegram-bot >= 22.6`
- `openpyxl` — Excel export
- `Pillow` — Image processing
- `reportlab` — PDF export
- `matplotlib` — Graph export
- `SpeechRecognition` + `pydub` — Voice transcription
- `google-generativeai` — Gemini AI receipt analysis
- `python-dotenv` — Environment variable loading
- One of: `pytesseract` / `easyocr` / `paddleocr` — OCR

See `requirements.txt` for pinned versions.

---

## 🔒 Security Notes

- The bot token in `config.py` should be moved to a `.env` file and excluded from version control.
- Add `expenses.db` and `*.env` to your `.gitignore`.
- Each user's data is isolated by their Telegram user ID.

---

## 📄 License

MIT License — free to use, modify, and distribute.
