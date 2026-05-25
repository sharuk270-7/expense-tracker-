"""
Telegram bot command handlers
"""
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import ExpenseDatabase
from config import CURRENCY, EXPENSE_CATEGORIES
from datetime import datetime
from excel_exporter import ExcelExporter

db = ExpenseDatabase()
exporter = ExcelExporter()


def _parse_positive_amount(raw_value):
    """Parse amount strings like '500', '1,500', '₹500' into positive float."""
    if raw_value is None:
        raise ValueError("missing")

    cleaned = str(raw_value).strip()
    cleaned = re.sub(r"(?i)\b(?:rs|inr)\.?\b", "", cleaned)
    cleaned = cleaned.replace(",", "")
    cleaned = cleaned.replace("₹", "").replace("$", "")
    # Keep only numeric signs/decimal separator.
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned).strip()

    amount = float(cleaned)
    if amount <= 0:
        raise ValueError("non_positive")
    return amount

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler"""
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    welcome_text = f"""
👋 Welcome to Expense Tracker AI Agent, {user.first_name}!

I help you track your expenses automatically. Just send me messages like:
• "Spent 150 for biriyani"
• "150 on transport"
• "200 for movie"

I'll extract the amount and category, then store it automatically.

🔍 **What I can do:**
• 📝 Parse text expenses
• 📸 Process receipt photos using OCR
• 📊 Generate weekly/monthly summaries
• 📈 Track expenses by category
• ✏️ Edit or delete expenses

Use /help for available commands.
    """
    
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help command handler"""
    help_text = f"""
*EXPENSE TRACKER BOT - COMPLETE GUIDE*

*BASIC COMMANDS:*
/start - Welcome message
/help - This help message

*VIEW EXPENSES:*
/summary - Last 30 days summary
/weekly - Last 7 days summary
/month - Last 30 days summary
/today - Today's total
/list - Show last 10 expenses
/stats - Detailed statistics

*BUDGET MANAGEMENT:*
/setdaily or /set_daily <amount> - Set daily budget limit
/setweekly or /set_weekly <amount> - Set weekly budget limit  
/setmonthly or /set_monthly <amount> - Set monthly budget limit
/limits or /limit - View current budget status

*REPORTS:*
/week - Weekly report with breakdown
/month - Monthly report with breakdown

*EXPORT DATA:*
/export - Excel export (all expenses)
/exporttoday or /export_today - Excel export (today)
/exportweekly or /export_weekly - Excel export (last 7 days)
/exportmonthly or /export_monthly - Excel export (last 30 days)
/exportrange <start> <end> - Excel export (custom range, YYYY-MM-DD)
/exportcsv or /export_csv - CSV format export
/pdf - PDF export (last 30 days)
/graph - Graph visualization (last 30 days)

*MANAGE DATA:*
/categories - Show all categories
/delete - Delete last expense
/list - Show last 10 expenses

*HOW TO ADD EXPENSES:*
Send natural language messages:
• "Spent 150 for biriyani"
• "50 on transport"
• "200 for movie"

*PHOTO RECEIPTS:*
Send a photo of your receipt to auto-extract amount and category

*VOICE MESSAGES:*
Send voice message describing expense - I'll transcribe and record it

*ONLINE PAYMENTS:*
Send payment screenshot with caption:
TXID: xyz123
Account: MyBank

*CATEGORIES:*
{', '.join(EXPENSE_CATEGORIES)}

Use /limits to monitor your budget usage!
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE, days: int = 30) -> None:
    """Show expense summary"""
    user_id = update.effective_user.id
    expenses = db.get_summary(user_id, days)
    
    if not expenses:
        await update.message.reply_text("No expenses found for this period.")
        return
    
    summary_text = f"📊 **Expense Summary (Last {days} days)**\n\n"
    total = 0
    
    for category, amount, count in expenses:
        summary_text += f"🏷️ {category}: {CURRENCY}{amount:.2f} ({count} items)\n"
        total += amount
    
    summary_text += f"\n💰 **Total: {CURRENCY}{total:.2f}**"
    
    await update.message.reply_text(summary_text, parse_mode='Markdown')

async def weekly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show weekly summary"""
    await summary(update, context, days=7)

async def monthly_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show monthly summary"""
    await summary(update, context, days=30)

async def today_total(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show today's total"""
    user_id = update.effective_user.id
    total = db.get_total_today(user_id)
    
    message = f"💸 **Today's Spending: {CURRENCY}{total:.2f}**"
    await update.message.reply_text(message, parse_mode='Markdown')

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all categories"""
    categories_text = "📂 **Expense Categories:**\n\n"
    for category in EXPENSE_CATEGORIES:
        categories_text += f"• {category}\n"
    
    await update.message.reply_text(categories_text, parse_mode='Markdown')

async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List last 10 expenses"""
    user_id = update.effective_user.id
    expenses = db.get_expenses(user_id)[:10]
    
    if not expenses:
        await update.message.reply_text("No expenses found.")
        return
    
    list_text = "📝 **Last 10 Expenses:**\n\n"
    for idx, (exp_id, amount, category, description, date, _) in enumerate(expenses, 1):
        date_obj = datetime.fromisoformat(date)
        date_str = date_obj.strftime("%d-%m-%Y %H:%M")
        list_text += f"{idx}. {category} - {CURRENCY}{amount:.2f} ({date_str})\n"
    
    await update.message.reply_text(list_text, parse_mode='Markdown')

async def delete_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete last expense"""
    user_id = update.effective_user.id
    expenses = db.get_expenses(user_id)
    
    if not expenses:
        await update.message.reply_text("No expenses to delete.")
        return
    
    exp_id = expenses[0][0]
    db.delete_expense(exp_id, user_id)
    
    await update.message.reply_text("✅ Last expense deleted!")

async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed statistics"""
    user_id = update.effective_user.id
    expenses_30 = db.get_summary(user_id, 30)
    expenses_7 = db.get_summary(user_id, 7)
    
    stats_text = "📈 **Detailed Statistics**\n\n"
    
    # Last 7 days
    stats_text += "**Last 7 Days:**\n"
    total_7 = 0
    if expenses_7:
        for category, amount, count in expenses_7:
            stats_text += f"  {category}: {CURRENCY}{amount:.2f}\n"
            total_7 += amount
        stats_text += f"  **Total: {CURRENCY}{total_7:.2f}**\n\n"
    else:
        stats_text += "  No expenses\n\n"
    
    # Last 30 days
    stats_text += "**Last 30 Days:**\n"
    total_30 = 0
    if expenses_30:
        for category, amount, count in expenses_30:
            stats_text += f"  {category}: {CURRENCY}{amount:.2f}\n"
            total_30 += amount
        stats_text += f"  **Total: {CURRENCY}{total_30:.2f}**\n"
    else:
        stats_text += "  No expenses\n"
    
    # Daily average
    if expenses_30:
        daily_avg = total_30 / 30
        stats_text += f"\n💡 **Daily Average: {CURRENCY}{daily_avg:.2f}**"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')
async def export_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export all expenses to Excel file"""
    user_id = update.effective_user.id
    
    await update.message.reply_text("📊 Generating Excel file with all your expenses...", parse_mode='Markdown')
    
    try:
        # Generate Excel file
        filename = exporter.export_all_expenses(user_id)
        
        # Send file to user
        with open(filename, 'rb') as excel_file:
            await update.message.reply_document(
                document=excel_file,
                caption=f"📊 **All Expenses Report**\n\nGenerated on: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\nSheets included:\n• All Expenses\n• Summary\n• Monthly Breakdown",
                parse_mode='Markdown'
            )
        
        # Clean up
        if os.path.exists(filename):
            os.remove(filename)
        
        await update.message.reply_text("✅ Excel file exported successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating Excel file: {str(e)}")

async def export_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export monthly expenses to Excel file"""
    user_id = update.effective_user.id
    
    await update.message.reply_text("📊 Generating monthly expense report...", parse_mode='Markdown')
    
    try:
        # Generate Excel file
        filename = exporter.export_monthly_expenses(user_id)
        
        # Send file to user
        with open(filename, 'rb') as excel_file:
            await update.message.reply_document(
                document=excel_file,
                caption=f"📊 **Monthly Expense Report**\n\nGenerated on: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\nPeriod: Last 30 days\n\nSheets included:\n• Summary by Category\n• Detailed Transactions",
                parse_mode='Markdown'
            )
        
        # Clean up
        if os.path.exists(filename):
            os.remove(filename)
        
        await update.message.reply_text("✅ Monthly report exported successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating report: {str(e)}")

async def export_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export weekly expenses to Excel file"""
    user_id = update.effective_user.id
    
    await update.message.reply_text("📊 Generating weekly expense report...", parse_mode='Markdown')
    
    try:
        # Generate Excel file
        filename = exporter.export_custom_period(user_id, days=7)
        
        # Send file to user
        with open(filename, 'rb') as excel_file:
            await update.message.reply_document(
                document=excel_file,
                caption=f"📊 **Weekly Expense Report**\n\nGenerated on: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\nPeriod: Last 7 days",
                parse_mode='Markdown'
            )
        
        # Clean up
        if os.path.exists(filename):
            os.remove(filename)
        
        await update.message.reply_text("✅ Weekly report exported successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating report: {str(e)}")

async def export_today_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export today's expenses to Excel file"""
    user_id = update.effective_user.id
    
    await update.message.reply_text("📊 Generating today's expense report...", parse_mode='Markdown')
    
    try:
        # Generate Excel file
        filename = exporter.export_custom_period(user_id, days=1)
        
        # Send file to user
        with open(filename, 'rb') as excel_file:
            await update.message.reply_document(
                document=excel_file,
                caption=f"📊 **Today's Expense Report**\n\nGenerated on: {datetime.now().strftime('%d-%m-%Y %H:%M')}",
                parse_mode='Markdown'
            )
        
        # Clean up
        if os.path.exists(filename):
            os.remove(filename)
        
        await update.message.reply_text("✅ Today's report exported successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating report: {str(e)}")

async def export_date_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export expenses to Excel for a custom date range."""
    user_id = update.effective_user.id
    if len(context.args) != 2:
        await update.message.reply_text(
            "\u274c Usage: /exportrange <start_date> <end_date>\n"
            "\U0001F4C5 Example: /exportrange 2026-02-01 2026-02-23",
            parse_mode='Markdown'
        )
        return
    start_date = context.args[0].strip()
    end_date = context.args[1].strip()
    try:
        start_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_obj = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text(
            "\u274c Invalid date format.\n"
            "\U0001F4C5 Use YYYY-MM-DD.\n"
            "Example: /exportrange 2026-02-01 2026-02-23",
            parse_mode='Markdown'
        )
        return
    if start_obj > end_obj:
        await update.message.reply_text("\u274c Start date must be before or equal to end date.")
        return
    await update.message.reply_text(
        f"\U0001F4CA Generating custom range report...\n"
        f"\U0001F4C5 Period: {start_date} to {end_date}",
        parse_mode='Markdown'
    )
    try:
        filename = exporter.export_date_range(user_id, start_date, end_date)
        with open(filename, 'rb') as excel_file:
            await update.message.reply_document(
                document=excel_file,
                caption=(
                    f"\U0001F4CA **Custom Range Expense Report**\n\n"
                    f"\U0001F4C5 Period: {start_date} to {end_date}\n"
                    f"\U0001F552 Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M')}"
                ),
                parse_mode='Markdown'
            )
        if os.path.exists(filename):
            os.remove(filename)
        await update.message.reply_text("\u2705 Custom range report exported successfully!")
    except Exception as e:
        await update.message.reply_text(f"\u274c Error generating custom range report: {str(e)}")

# ===== BUDGET LIMIT COMMANDS =====

async def set_daily_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set daily budget limit"""
    user_id = update.effective_user.id
    if len(context.args) != 1:
        await update.message.reply_text(
            "\u274c Usage: /setdaily or /set_daily <amount>\nExample: /setdaily 500"
        )
        return
    try:
        amount = _parse_positive_amount(context.args[0])
        db.set_budget_limit(user_id, 'daily', amount)
        await update.message.reply_text(f"\u2705 Daily limit set to {CURRENCY}{amount:.2f}")
    except ValueError:
        await update.message.reply_text(
            "\u274c Invalid amount. Enter a positive number (example: 500 or 1,500)."
        )
async def set_weekly_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set weekly budget limit"""
    user_id = update.effective_user.id
    if len(context.args) != 1:
        await update.message.reply_text(
            "\u274c Usage: /setweekly or /set_weekly <amount>\nExample: /setweekly 3500"
        )
        return
    try:
        amount = _parse_positive_amount(context.args[0])
        db.set_budget_limit(user_id, 'weekly', amount)
        await update.message.reply_text(f"\u2705 Weekly limit set to {CURRENCY}{amount:.2f}")
    except ValueError:
        await update.message.reply_text(
            "\u274c Invalid amount. Enter a positive number (example: 3500 or 3,500)."
        )
async def set_monthly_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set monthly budget limit"""
    user_id = update.effective_user.id
    if len(context.args) != 1:
        await update.message.reply_text(
            "\u274c Usage: /setmonthly or /set_monthly <amount>\nExample: /setmonthly 15000"
        )
        return
    try:
        amount = _parse_positive_amount(context.args[0])
        db.set_budget_limit(user_id, 'monthly', amount)
        await update.message.reply_text(f"\u2705 Monthly limit set to {CURRENCY}{amount:.2f}")
    except ValueError:
        await update.message.reply_text(
            "\u274c Invalid amount. Enter a positive number (example: 15000 or 15,000)."
        )

def get_limit_status(current, limit):
    """Get budget warning status"""
    if not limit:
        return None
    
    percentage = (current / limit) * 100
    
    if percentage >= 100:
        return "🔴", percentage
    elif percentage >= 90:
        return "⚠️", percentage
    elif percentage >= 75:
        return "⚡", percentage
    else:
        return "✅", percentage

async def check_limits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check budget status"""
    user_id = update.effective_user.id
    
    daily_limit, weekly_limit, monthly_limit = db.get_budget_limits(user_id)
    
    if not any([daily_limit, weekly_limit, monthly_limit]):
        await update.message.reply_text(
            "❌ No limits set.\n\nSet limits using:\n"
            "/setdaily or /set_daily <amount>\n"
            "/setweekly or /set_weekly <amount>\n"
            "/setmonthly or /set_monthly <amount>"
        )
        return
    
    today_total = db.get_total_today(user_id)
    week_total = db.get_total_week(user_id)
    month_total = db.get_total_month(user_id)
    
    limits_text = "💰 **Budget Status**\n\n"
    
    if daily_limit:
        status, percentage = get_limit_status(today_total, daily_limit)
        limits_text += f"{status} **Daily:** {CURRENCY}{today_total:.2f} / {CURRENCY}{daily_limit:.2f} ({percentage:.0f}%)\n"
    
    if weekly_limit:
        status, percentage = get_limit_status(week_total, weekly_limit)
        limits_text += f"{status} **Weekly:** {CURRENCY}{week_total:.2f} / {CURRENCY}{weekly_limit:.2f} ({percentage:.0f}%)\n"
    
    if monthly_limit:
        status, percentage = get_limit_status(month_total, monthly_limit)
        limits_text += f"{status} **Monthly:** {CURRENCY}{month_total:.2f} / {CURRENCY}{monthly_limit:.2f} ({percentage:.0f}%)\n"
    
    await update.message.reply_text(limits_text, parse_mode='Markdown')

async def report_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show weekly report"""
    user_id = update.effective_user.id
    expenses = db.get_summary(user_id, 7)
    
    if not expenses:
        await update.message.reply_text("No expenses found for this week.")
        return
    
    report_text = "📊 **Weekly Report (Last 7 Days)**\n\n"
    total = 0
    
    for category, amount, count in expenses:
        report_text += f"🏷️ {category}: {CURRENCY}{amount:.2f} ({count} items)\n"
        total += amount
    
    report_text += f"\n💰 **Total: {CURRENCY}{total:.2f}**"
    
    await update.message.reply_text(report_text, parse_mode='Markdown')

async def report_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show monthly report"""
    user_id = update.effective_user.id
    expenses = db.get_summary(user_id, 30)
    
    if not expenses:
        await update.message.reply_text("No expenses found for this month.")
        return
    
    report_text = "📊 **Monthly Report (Last 30 Days)**\n\n"
    total = 0
    
    for category, amount, count in expenses:
        report_text += f"🏷️ {category}: {CURRENCY}{amount:.2f} ({count} items)\n"
        total += amount
    
    report_text += f"\n💰 **Total: {CURRENCY}{total:.2f}**"
    
    await update.message.reply_text(report_text, parse_mode='Markdown')

async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export all expenses as CSV"""
    user_id = update.effective_user.id
    expenses = db.get_expenses(user_id)
    
    if not expenses:
        await update.message.reply_text("No expenses to export.")
        return
    
    # Create CSV content
    csv_content = "Date,Category,Amount,Description\n"
    for exp_id, amount, category, description, date, *_ in expenses:
        csv_content += f'"{date}","{category}","{amount}","{description}"\n'
    
    # Save to file
    filename = f"expenses_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, 'w') as f:
        f.write(csv_content)
    
    # Send file
    with open(filename, 'rb') as csv_file:
        await update.message.reply_document(
            document=csv_file,
            caption="📊 Expenses CSV Export",
            filename=filename
        )
    
    # Clean up
    if os.path.exists(filename):
        os.remove(filename)
    
    await update.message.reply_text("✅ CSV exported successfully!")

async def export_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export expenses to a PDF report (last 30 days)."""
    user_id = update.effective_user.id
    expenses = db.get_expenses(user_id, days=30)

    if not expenses:
        await update.message.reply_text("No expenses found for the last 30 days.")
        return

    await update.message.reply_text("📄 Generating PDF report...", parse_mode='Markdown')

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError:
        await update.message.reply_text(
            "❌ PDF support is not installed.\nInstall dependency: `pip install reportlab`",
            parse_mode='Markdown'
        )
        return

    try:
        filename = f"expenses_pdf_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        doc = SimpleDocTemplate(filename, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
        styles = getSampleStyleSheet()
        elements = []

        total_amount = sum(float(row[1] or 0) for row in expenses)
        generated_on = datetime.now().strftime("%d-%m-%Y %H:%M")

        elements.append(Paragraph("Expense Report (Last 30 Days)", styles["Title"]))
        elements.append(Paragraph(f"Generated on: {generated_on}", styles["Normal"]))
        elements.append(Paragraph(f"Total Expenses: {len(expenses)}", styles["Normal"]))
        elements.append(Paragraph(f"Total Amount: {CURRENCY}{total_amount:.2f}", styles["Normal"]))
        elements.append(Spacer(1, 8))

        table_data = [["Date", "Category", "Amount", "Description"]]
        for _, amount, category, description, date, *_ in expenses[:200]:
            date_val = (date or "")[:16]
            category_val = category or "Other"
            amount_val = f"{CURRENCY}{float(amount):.2f}"
            desc_val = (description or "").replace("\n", " ").strip()
            if len(desc_val) > 55:
                desc_val = desc_val[:52] + "..."
            table_data.append([date_val, category_val, amount_val, desc_val])

        table = Table(table_data, colWidths=[36 * mm, 30 * mm, 26 * mm, 86 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
        ]))
        elements.append(table)

        if len(expenses) > 200:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(f"Note: Showing first 200 rows out of {len(expenses)} expenses.", styles["Italic"]))

        doc.build(elements)

        with open(filename, "rb") as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                caption=f"📄 **PDF Expense Report**\n\nPeriod: Last 30 days\nTotal: {CURRENCY}{total_amount:.2f}",
                filename=filename,
                parse_mode='Markdown'
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating PDF report: {str(e)}")
        return
    finally:
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)

async def export_graph(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export category-wise spending graph image (last 30 days)."""
    user_id = update.effective_user.id
    summary_data = db.get_summary(user_id, 30)

    if not summary_data:
        await update.message.reply_text("No expenses found for the last 30 days.")
        return

    await update.message.reply_text("📈 Generating spending graph...", parse_mode='Markdown')

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        await update.message.reply_text(
            "❌ Graph support is not installed.\nInstall dependency: `pip install matplotlib`",
            parse_mode='Markdown'
        )
        return

    try:
        categories = [row[0] for row in summary_data]
        amounts = [float(row[1] or 0) for row in summary_data]
        total_amount = sum(amounts)

        filename = f"expense_graph_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        fig, axes = plt.subplots(1, 2, figsize=(13, 5), dpi=120)
        fig.suptitle("Expense Analysis - Last 30 Days", fontsize=14, fontweight="bold")

        # Bar chart
        axes[0].bar(categories, amounts, color="#2563eb")
        axes[0].set_title("Category Totals")
        axes[0].set_ylabel(f"Amount ({CURRENCY})")
        axes[0].tick_params(axis='x', rotation=35)
        axes[0].grid(axis='y', linestyle='--', alpha=0.35)

        # Pie chart
        axes[1].pie(amounts, labels=categories, autopct="%1.1f%%", startangle=140)
        axes[1].set_title("Category Share")

        plt.tight_layout()
        plt.savefig(filename, bbox_inches="tight")
        plt.close(fig)

        with open(filename, "rb") as img_file:
            await update.message.reply_photo(
                photo=img_file,
                caption=f"📈 **Spending Graph (Last 30 Days)**\n\nTotal: {CURRENCY}{total_amount:.2f}",
                parse_mode='Markdown'
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error generating graph: {str(e)}")
        return
    finally:
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)








