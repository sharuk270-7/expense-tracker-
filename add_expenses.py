"""
Script to add multiple expenses at once
"""
from database import ExpenseDatabase
from nlp_processor import ExpenseParser

# Initialize
db = ExpenseDatabase()
parser = ExpenseParser()

# Test user ID (change as needed)
user_id = 12345678  # Replace with your actual Telegram user ID

# List of expense descriptions
expenses = [
    "Coffee 30",
    "Apple 150",
    "Tea 40",
    "Biriyani 150",
    "Petrol 150"
]

# Add user first
db.add_user(user_id, "testuser", "Test")

# Process each expense
print("Adding expenses...")
for desc in expenses:
    amount, category, description = parser.parse_expense(desc)
    
    if amount and category:
        is_valid = parser.is_valid_expense(amount, category)
        if is_valid:
            db.add_expense(user_id, amount, category, description, source="bulk")
            print(f"✅ Added: {description} | Amount: ₹{amount:.2f} | Category: {category}")
        else:
            print(f"❌ Invalid: {description} (Category: {category})")
    else:
        print(f"❌ Could not parse: {description}")

# Show summary
print("\n📊 Expense Summary:")
summary = db.get_summary(user_id)
if isinstance(summary, dict):
    for category, (total, count) in summary.items():
        print(f"  {category}: ₹{total:.2f} ({count} transactions)")
else:
    print(f"  Summary: {summary}")
