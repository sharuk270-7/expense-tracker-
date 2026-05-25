#!/usr/bin/env python3
"""
Verification script for export commands
Tests that all export functions exist and are properly configured
"""
import sys
sys.path.insert(0, r'c:\Users\PRAVEEN\Desktop\Expense Tracer AI Agent')

def verify_exports():
    """Verify all export commands are available"""
    from bot_commands import (
        export_all,
        export_monthly,
        export_weekly,
        export_today_data,
        export_csv,
        export_pdf,
        export_graph
    )
    import inspect
    
    print("=" * 60)
    print("EXPORT COMMANDS VERIFICATION")
    print("=" * 60)
    
    commands = [
        ("/export", export_all),
        ("/export_monthly", export_monthly),
        ("/export_weekly", export_weekly),
        ("/export_today", export_today_data),
        ("/export_csv", export_csv),
        ("/pdf", export_pdf),
        ("/graph", export_graph),
    ]
    
    all_ok = True
    for cmd_name, func in commands:
        is_async = inspect.iscoroutinefunction(func)
        status = "OK" if is_async else "ERROR"
        print(f"{status}: {cmd_name:<20} - {func.__name__:<20} (async={is_async})")
        if not is_async:
            all_ok = False
    
    print("=" * 60)
    
    if all_ok:
        print("SUCCESS: All export commands are properly defined!")
        print("\nAvailable export commands:")
        print("  /export         - Export ALL expenses to Excel")
        print("  /export_today   - Export TODAY'S expenses")
        print("  /export_weekly  - Export LAST 7 DAYS expenses")
        print("  /export_monthly - Export LAST 30 DAYS expenses")
        print("  /export_csv     - Export as CSV format")
        print("  /pdf            - PDF export (coming soon)")
        print("  /graph          - Graph visualization (coming soon)")
        return True
    else:
        print("ERROR: Some export commands are not properly defined!")
        return False

if __name__ == "__main__":
    try:
        success = verify_exports()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
