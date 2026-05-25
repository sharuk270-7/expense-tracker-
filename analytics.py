"""
Advanced expense tracking features
"""
from datetime import datetime, timedelta
from database import ExpenseDatabase
from config import CURRENCY

class ExpenseAnalytics:
    def __init__(self):
        self.db = ExpenseDatabase()
    
    def get_trending_category(self, user_id, days=30):
        """Get most spending category"""
        expenses = self.db.get_summary(user_id, days)
        if not expenses:
            return None
        return expenses[0][0]  # Category with highest amount
    
    def get_daily_average(self, user_id, days=30):
        """Calculate daily average spending"""
        expenses = self.db.get_summary(user_id, days)
        if not expenses:
            return 0
        total = sum(amount for _, amount, _ in expenses)
        return total / days
    
    def predict_monthly_spending(self, user_id):
        """Predict monthly spending based on last 7 days"""
        expenses = self.db.get_summary(user_id, 7)
        if not expenses:
            return 0
        total_7 = sum(amount for _, amount, _ in expenses)
        return total_7 * (30 / 7)
    
    def get_budget_warning(self, user_id, budget=5000):
        """Check if spending exceeds budget"""
        expenses = self.db.get_summary(user_id, 30)
        if not expenses:
            return None
        
        total = sum(amount for _, amount, _ in expenses)
        percentage = (total / budget) * 100
        
        if percentage > 100:
            return f"⚠️ Warning: You've exceeded your monthly budget! Spent {percentage:.0f}%"
        elif percentage > 80:
            return f"💡 Caution: You've spent {percentage:.0f}% of your monthly budget"
        return None


class BudgetManager:
    """Manage spending budgets by category"""
    
    def __init__(self):
        self.db = ExpenseDatabase()
    
    def set_category_budget(self, user_id, category, amount):
        """Set budget for specific category"""
        # This would require a new table in the database
        pass
    
    def check_category_budget(self, user_id, category):
        """Check if category spending exceeds budget"""
        pass


class ExpenseRecurring:
    """Track recurring expenses"""
    
    def __init__(self):
        self.db = ExpenseDatabase()
    
    def add_recurring_expense(self, user_id, amount, category, description, frequency="monthly"):
        """Add recurring expense (monthly, weekly, daily)"""
        # Frequency: daily, weekly, monthly, yearly
        pass
    
    def auto_add_recurring(self):
        """Automatically add recurring expenses on schedule"""
        pass
